from typing import Dict, List

from groq import Groq
from sqlalchemy.orm import Session

from app.config import settings
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.user import User
from app.services.billing_service import CURRENCY, doctor_label

client = Groq(api_key=settings.GROQ_API_KEY)

BASE_PROMPT = f"""You are the friendly AI assistant of {settings.HOSPITAL_NAME}. You help patients and visitors with
hospital information, finding the right department or doctor, how to book an appointment, fees, timings and what to expect.

Hospital details:
- Name: {settings.HOSPITAL_NAME}
- Phone: {settings.HOSPITAL_PHONE}
- Email: {settings.HOSPITAL_EMAIL}
- Address: {settings.HOSPITAL_ADDRESS}
- Emergency department: open 24/7

Rules:
- Use ONLY the live hospital data below for doctors, departments, fees and timings. Never invent a doctor, department,
  fee or timing. If something is not in the data, say it is not listed and suggest calling {settings.HOSPITAL_PHONE}.
- To recommend a doctor, match the patient's concern to a department/specialization from the data and name the doctors listed there.
- To book: sign in to the patient portal and press "Book Appointment" (new patients: create an account and complete the profile first),
  or use the helpline assistant (phone icon on the site).
- Never diagnose or prescribe. For emergencies tell the person to go to the Emergency Department or call {settings.HOSPITAL_PHONE} immediately.
- Reply in the same language the user writes in. Keep answers short (voice-friendly), warm and professional.
- You may use simple markdown: **bold**, "- " bullet lists. Do not use tables.
"""


def _live_context(db: Session) -> str:
    depts = db.query(Department).all()
    docs = (db.query(Doctor).join(User, Doctor.user_id == User.id).filter(User.is_active == True).limit(60).all())
    lines = ["LIVE HOSPITAL DATA (from the hospital database):", "Departments: " +
             (", ".join(d.name + (f" (floor {d.floor})" if getattr(d, "floor", None) else "") for d in depts) or "none listed")]
    lines.append("Doctors:")
    for d in docs:
        days = d.available_days or []
        lines.append(
            f"- {doctor_label(d.user.full_name)} | {d.specialization or 'General'} | Dept: {d.department.name if d.department else 'General'}"
            f" | {d.qualification or 'qualification not listed'} | {d.experience_years or 0} yrs experience"
            f" | Fee: {CURRENCY}{(d.consultation_fee or 0):g} | Available: {', '.join(x[:3] for x in days) or 'not listed'}"
            f" {d.available_from or ''}-{d.available_to or ''}")
    if not docs:
        lines.append("- (no doctors listed yet)")
    return "\n".join(lines)


def get_chatbot_response(messages: List[Dict[str, str]], db: Session) -> str:
    """messages: list of {"role": "user"/"assistant", "content": "..."}"""
    try:
        system = BASE_PROMPT + "\n" + _live_context(db)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "system", "content": system}] + messages[-12:],
            max_tokens=450, temperature=0.4,
        )
        return response.choices[0].message.content
    except Exception:
        return f"I'm temporarily unavailable. Please call {settings.HOSPITAL_PHONE} for assistance."
