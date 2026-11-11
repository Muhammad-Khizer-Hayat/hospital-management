"""AI helpline agent: talks to callers, verifies identity, books/cancels appointments,
logs every call and can hand over to a human via a callback request."""
import json
import threading
import time
import uuid
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from groq import Groq
from sqlalchemy.orm import Session

from app.config import settings
from app.models.agent_log import AgentCallLog, CallbackRequest
from app.models.appointment import Appointment, AppointmentStatus
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import create_appointment
from app.services.billing_service import cancel_pending_bill

client = Groq(api_key=settings.GROQ_API_KEY)

SESSION_TTL = 30 * 60      # forget a conversation after 30 minutes of silence
MAX_FAILED_VERIFY = 3      # lock the session after 3 wrong verification attempts
SLOT_MINUTES = 30
MAX_TRANSCRIPT_CHARS = 60000

SESSIONS: dict = {}
_LOCK = threading.Lock()


# ───────────────────────── sessions ─────────────────────────
def get_session(session_id: str | None, allow_custom_id: bool = False, channel: str = "web"):
    now = time.time()
    with _LOCK:
        for k in [k for k, v in SESSIONS.items() if now - v["last"] > SESSION_TTL]:
            del SESSIONS[k]
        if not session_id or session_id not in SESSIONS:
            if not (allow_custom_id and session_id):
                session_id = uuid.uuid4().hex
            SESSIONS[session_id] = {"id": session_id, "channel": channel, "messages": [],
                                    "patient_id": None, "failed": 0, "outcome": "info", "last": now}
        s = SESSIONS[session_id]
        s["last"] = now
        return session_id, s


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _doctor_label(full_name: str) -> str:
    n = (full_name or "").strip()
    return n if n.lower().startswith("dr") else f"Dr. {n}"


def _not_verified():
    return {"ok": False, "error": "Caller is not verified yet. Ask for their full name, patient ID and date of birth, then call verify_caller."}


# ───────────────────────── call log ─────────────────────────
def _get_log(db: Session, s: dict) -> AgentCallLog:
    log = db.query(AgentCallLog).filter(AgentCallLog.session_id == s["id"]).first()
    if not log:
        log = AgentCallLog(session_id=s["id"], channel=s["channel"], transcript="")
        db.add(log)
        db.flush()
    return log


def _log_turn(db: Session, s: dict, user_text: str, reply: str):
    """Save the conversation. A logging problem must never break the call."""
    try:
        log = _get_log(db, s)
        text = (log.transcript or "") + f"Caller: {user_text}\nAgent: {reply}\n"
        log.transcript = text[-MAX_TRANSCRIPT_CHARS:]
        log.outcome = s["outcome"]
        if s["patient_id"]:
            log.patient_id = s["patient_id"]
        db.commit()
    except Exception:
        db.rollback()


def _track_outcome(name: str, result: dict, s: dict):
    if result.get("ok") and name == "book_appointment":
        s["outcome"] = "booked"
    elif result.get("ok") and name == "cancel_appointment":
        s["outcome"] = "cancelled"
    elif result.get("ok") and name == "request_callback":
        s["outcome"] = "callback_requested"
    elif name == "verify_caller" and not result.get("ok") and s["outcome"] in ("info", "verification_failed"):
        s["outcome"] = "locked" if result.get("locked") else "verification_failed"


# ───────────────────────── tools ─────────────────────────
def t_verify_caller(db: Session, s: dict, full_name: str = "", patient_id=None, date_of_birth: str = ""):
    if s["patient_id"]:
        return {"ok": True, "note": "Already verified in this conversation."}
    if s["failed"] >= MAX_FAILED_VERIFY:
        return {"ok": False, "locked": True,
                "error": "Too many failed attempts. Tell the caller you cannot continue with account actions and offer a callback request."}
    try:
        pid = int(str(patient_id).strip().lstrip("#"))
    except (TypeError, ValueError):
        pid = None
    patient = db.query(Patient).filter(Patient.id == pid).first() if pid else None
    user = patient.user if patient else None
    name_ok = bool(user and user.is_active and _norm(user.full_name) == _norm(full_name))

    try:
        dob = date.fromisoformat((date_of_birth or "").strip())
    except ValueError:
        dob = None

    if not name_ok or dob is None or dob != patient.date_of_birth:
        s["failed"] += 1
        result = {"ok": False, "error": "The details could not be verified."}
        if s["failed"] >= MAX_FAILED_VERIFY:
            result["locked"] = True
            result["error"] = "Too many failed attempts. Tell the caller you cannot continue with account actions and offer a callback request."
        return result

    s["patient_id"] = patient.id
    s["failed"] = 0
    return {"ok": True, "patient_name": user.full_name}


def t_list_departments(db: Session, s: dict):
    return {"departments": [{"name": d.name, "floor": d.floor} for d in db.query(Department).all()]}


def t_list_doctors(db: Session, s: dict, department_name: str = ""):
    q = (db.query(Doctor).join(User, Doctor.user_id == User.id)
         .filter(User.is_active == True))  # noqa: E712
    if department_name:
        q = q.join(Department, Doctor.department_id == Department.id).filter(
            Department.name.ilike(f"%{department_name}%"))
    return {"doctors": [{
        "doctor_id": d.id, "name": _doctor_label(d.user.full_name),
        "specialization": d.specialization,
        "department": d.department.name if d.department else None,
        "consultation_fee": d.consultation_fee,
        "available_days": d.available_days,
        "hours": f"{d.available_from} to {d.available_to}",
    } for d in q.all()]}


def _slots_for(db: Session, doctor: Doctor, day: datetime):
    if day.strftime("%A") not in (doctor.available_days or []):
        return []
    h1, m1 = map(int, (doctor.available_from or "09:00").split(":"))
    h2, m2 = map(int, (doctor.available_to or "17:00").split(":"))
    start = day.replace(hour=h1, minute=m1, second=0, microsecond=0)
    end = day.replace(hour=h2, minute=m2, second=0, microsecond=0)
    booked = {a.appointment_date for a in db.query(Appointment).filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date >= start, Appointment.appointment_date < end,
        Appointment.status != AppointmentStatus.CANCELLED).all()}
    now, slots, t = datetime.now(), [], start
    while t < end:
        if t > now and t not in booked:
            slots.append(t)
        t += timedelta(minutes=SLOT_MINUTES)
    return slots


def t_get_available_slots(db: Session, s: dict, doctor_id=None, date: str = ""):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        return {"ok": False, "error": "Doctor not found."}
    try:
        day = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"ok": False, "error": "Date must be in YYYY-MM-DD format."}
    slots = _slots_for(db, doctor, day)
    if not slots:
        return {"ok": True, "slots": [], "note": f"No free slots on {date} (doctor works on {doctor.available_days})."}
    return {"ok": True, "slots": [t.strftime("%H:%M") for t in slots][:12]}


def t_book_appointment(db: Session, s: dict, doctor_id=None, appointment_datetime: str = "", reason: str = ""):
    if not s["patient_id"]:
        return _not_verified()
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        return {"ok": False, "error": "Doctor not found."}
    try:
        when = datetime.strptime(appointment_datetime, "%Y-%m-%dT%H:%M")
    except ValueError:
        return {"ok": False, "error": "Datetime must be YYYY-MM-DDTHH:MM."}
    if when not in _slots_for(db, doctor, when.replace(hour=0, minute=0)):
        return {"ok": False, "error": "That time is not available. Call get_available_slots and offer another time."}
    try:
        appt = create_appointment(db, AppointmentCreate(
            doctor_id=doctor.id, appointment_date=when, reason=reason or None,
            notes="Booked via AI helpline agent"), patient_id=s["patient_id"])
    except HTTPException as e:
        return {"ok": False, "error": str(e.detail)}
    fee = appt.bill.total if appt.bill else 0
    result = {"ok": True, "appointment_id": appt.id, "doctor": _doctor_label(doctor.user.full_name),
              "when": when.strftime("%A %d %B %Y at %I:%M %p"), "status": "pending",
              "consultation_fee": fee}
    if fee:
        result["payment_note"] = ("Fee is unpaid. The patient pays online in the patient portal "
                                  "(Appointments or Billing page, where the receipt can be downloaded) or at the hospital.")
    return result


def t_list_my_appointments(db: Session, s: dict):
    if not s["patient_id"]:
        return _not_verified()
    rows = db.query(Appointment).filter(
        Appointment.patient_id == s["patient_id"],
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
        Appointment.appointment_date >= datetime.now()).order_by(Appointment.appointment_date).all()
    return {"ok": True, "appointments": [{
        "appointment_id": a.id, "doctor": _doctor_label(a.doctor.user.full_name),
        "when": a.appointment_date.strftime("%A %d %B %Y at %I:%M %p"),
        "status": a.status.value, "reason": a.reason} for a in rows]}


def t_cancel_appointment(db: Session, s: dict, appointment_id=None):
    if not s["patient_id"]:
        return _not_verified()
    try:
        aid = int(appointment_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Invalid appointment id."}
    # Always scoped to the VERIFIED patient: callers can never touch someone else's booking.
    appt = db.query(Appointment).filter(
        Appointment.id == aid, Appointment.patient_id == s["patient_id"]).first()
    if not appt:
        return {"ok": False, "error": "No such appointment on this patient's account."}
    if appt.status not in (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED):
        return {"ok": False, "error": f"This appointment is already {appt.status.value} and cannot be cancelled."}
    if appt.appointment_date < datetime.now():
        return {"ok": False, "error": "This appointment is in the past."}
    appt.status = AppointmentStatus.CANCELLED
    appt.notes = ((appt.notes or "") + " | Cancelled via AI helpline agent").strip(" |")
    cancel_pending_bill(db, appt)   # an unpaid consultation bill is cancelled with the appointment
    db.commit()
    return {"ok": True, "cancelled_appointment_id": appt.id,
            "was": appt.appointment_date.strftime("%A %d %B %Y at %I:%M %p")}


def t_request_callback(db: Session, s: dict, name: str = "", phone: str = "", reason: str = ""):
    """Human handoff: staff will phone the caller back. Works without verification."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not (name or "").strip() or len(digits) < 7:
        return {"ok": False, "error": "A name and a valid phone number are required."}
    log = _get_log(db, s)
    cb = CallbackRequest(call_log_id=log.id, patient_id=s["patient_id"], name=name.strip()[:120],
                         phone=phone.strip()[:30], reason=(reason or "").strip()[:1000])
    db.add(cb)
    db.commit()
    return {"ok": True, "request_id": cb.id}


TOOL_FUNCS = {
    "verify_caller": t_verify_caller, "list_departments": t_list_departments,
    "list_doctors": t_list_doctors, "get_available_slots": t_get_available_slots,
    "book_appointment": t_book_appointment, "list_my_appointments": t_list_my_appointments,
    "cancel_appointment": t_cancel_appointment, "request_callback": t_request_callback,
}


def _tool(name, description, props=None, required=None):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}


TOOLS = [
    _tool("verify_caller", "Verify the caller's identity. Needs full name, patient ID AND date of birth. Required before booking, listing or cancelling appointments.",
          {"full_name": {"type": "string"}, "patient_id": {"type": "string", "description": "digits only"},
           "date_of_birth": {"type": "string", "description": "YYYY-MM-DD"}},
          ["full_name", "patient_id", "date_of_birth"]),
    _tool("list_departments", "List hospital departments."),
    _tool("list_doctors", "List doctors, optionally for one department.",
          {"department_name": {"type": "string"}}),
    _tool("get_available_slots", "Free 30-minute slots for a doctor on a date.",
          {"doctor_id": {"type": "integer"}, "date": {"type": "string", "description": "YYYY-MM-DD"}},
          ["doctor_id", "date"]),
    _tool("book_appointment", "Book an appointment for the verified caller. Only after the caller confirmed doctor, date and time.",
          {"doctor_id": {"type": "integer"}, "appointment_datetime": {"type": "string", "description": "YYYY-MM-DDTHH:MM"},
           "reason": {"type": "string"}}, ["doctor_id", "appointment_datetime"]),
    _tool("list_my_appointments", "List the verified caller's upcoming appointments."),
    _tool("cancel_appointment", "Cancel one of the verified caller's appointments. Only after the caller confirmed which one.",
          {"appointment_id": {"type": "integer"}}, ["appointment_id"]),
    _tool("request_callback", "Ask hospital staff to phone the caller back. Use when the caller wants a human, or you cannot help.",
          {"name": {"type": "string"}, "phone": {"type": "string"}, "reason": {"type": "string"}},
          ["name", "phone", "reason"]),
]


def _system_prompt() -> str:
    now = datetime.now().strftime("%A, %d %B %Y, %I:%M %p")
    return f"""You are the phone helpline assistant of {settings.HOSPITAL_NAME}. Current local date and time: {now}.
You talk to callers by voice, so: short natural sentences, no markdown, no lists, one question at a time.

Start by greeting the caller. For anything about their own appointments, ask for their full name, patient ID and date of birth (one at a time). Spoken numbers may arrive as words ("one two" = 12) and dates as words: convert them to digits and to YYYY-MM-DD.
- You may share general info (departments, doctors, fees, hours, free slots) with anyone.
- Before booking, listing or cancelling appointments you MUST call verify_caller. If it fails, say the details could not be verified and ask them to repeat; never say which part was wrong. If the caller says they never gave a date of birth to the hospital, tell them they can add it in the patient portal after logging in, or you can arrange a callback. If it says locked, stop account actions and offer a callback request.
- Booking: find the right department/doctor, check slots with get_available_slots, then READ BACK doctor, date and time and wait for a clear "yes" before calling book_appointment. Convert dates like "tomorrow" using the current date above. After booking, tell the caller the appointment number. If there is a consultation fee, tell them the amount and that it can be paid in the patient portal (Appointments or Billing page, where the receipt can be downloaded) or at the hospital.
- Cancelling: list their appointments, confirm which one, wait for a clear "yes", then call cancel_appointment.
- Human help: if the caller asks for a person, is upset, or you cannot help, offer a callback. Ask for their name, phone number and reason (one at a time), read the number back, then call request_callback and tell them staff will call back.
- Never reveal or discuss any other patient's information. Never mention tools or internal ids except the appointment number after booking.
- No medical diagnosis or treatment advice. For emergencies tell the caller to hang up and call the emergency number or go to the Emergency Department immediately.
- Hospital phone: {settings.HOSPITAL_PHONE}."""


def run_agent(db: Session, session_id: str | None, user_text: str,
              allow_custom_id: bool = False, channel: str = "web"):
    session_id, s = get_session(session_id, allow_custom_id, channel)
    messages = s["messages"]
    messages.append({"role": "user", "content": user_text})
    reply = None
    try:
        for _ in range(6):
            resp = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "system", "content": _system_prompt()}] + messages,
                tools=TOOLS, tool_choice="auto", max_tokens=400, temperature=0.3)
            msg = resp.choices[0].message
            if not msg.tool_calls:
                reply = msg.content or "Sorry, could you say that again?"
                messages.append({"role": "assistant", "content": reply})
                break
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                func = TOOL_FUNCS.get(tc.function.name)
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    result = func(db, s, **args) if func else {"ok": False, "error": "Unknown tool."}
                except Exception:
                    db.rollback()
                    result = {"ok": False, "error": "Something went wrong running that action."}
                _track_outcome(tc.function.name, result, s)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
    except Exception:
        reply = None
    if reply is None:
        reply = f"I'm sorry, I'm having trouble right now. Please call {settings.HOSPITAL_PHONE}."
    _log_turn(db, s, user_text, reply)
    return session_id, reply
