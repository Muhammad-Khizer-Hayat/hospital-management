"""Doctor working days and hours.

ONE place decides whether a doctor can be booked at a given moment. Every way of booking
(patient portal, reception, admin, phone assistant) goes through create_appointment(), which calls
check_available(), so the rule applies everywhere.
"""
from datetime import datetime, time, date, timedelta
from fastapi import HTTPException

SLOT_MINUTES = 30          # one appointment every 30 minutes
MAX_ADVANCE_DAYS = 60      # patients may book up to 60 days ahead
ALLOW_START_AT_CLOSING = True   # True: 9:00 AM - 5:00 PM allows a 5:00 PM appointment; False: last start is 4:30 PM

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _parse_time(value, default: time) -> time:
    """Accepts 09:00, 9:00, 12.00pm, 12:00 PM, 4 pm ..."""
    s = str(value or "").strip().upper().replace(".", ":").replace(" ", "")
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M%p", "%I%p"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return default


def fmt_time(t: time) -> str:
    return datetime.combine(datetime.today(), t).strftime("%I:%M %p").lstrip("0")


def working_days(doctor) -> list:
    raw = doctor.available_days
    if raw is None:
        raw = _DAYS[:5]                                   # not set at all: Monday - Friday
    if isinstance(raw, str):
        raw = raw.replace(";", ",").split(",")
    keys = {str(x).strip()[:3].lower() for x in raw if str(x).strip()}
    return [d for d in _DAYS if d[:3].lower() in keys]


def working_hours(doctor):
    return _parse_time(doctor.available_from, time(9, 0)), _parse_time(doctor.available_to, time(17, 0))


def doctor_label(doctor) -> str:
    name = (doctor.user.full_name if getattr(doctor, "user", None) else "") or "The doctor"
    return name if name.lower().startswith("dr") else f"Dr. {name}"


def schedule_text(doctor) -> str:
    start, end = working_hours(doctor)
    return f"{', '.join(working_days(doctor)) or 'no working days'} · {fmt_time(start)} – {fmt_time(end)}"


def is_available(doctor, when: datetime):
    """Returns (True, "") or (False, "friendly reason")."""
    label = doctor_label(doctor)
    days = working_days(doctor)
    weekday = when.strftime("%A")
    start, end = working_hours(doctor)
    if not days:
        return False, f"{label} has no working days set, so appointments cannot be booked."
    if weekday not in days:
        return False, (f"{label} is not available on {weekday}. "
                       f"Working days: {', '.join(days)}, {fmt_time(start)} – {fmt_time(end)}.")
    t = when.time().replace(second=0, microsecond=0)
    if ALLOW_START_AT_CLOSING:
        inside = (start <= t <= end) if start < end else (t >= start or t <= end)
    else:
        inside = (start <= t < end) if start < end else (t >= start or t < end)
    if not inside:
        return False, (f"{label} is not available at {fmt_time(t)}. "
                       f"Working hours on {weekday}: {fmt_time(start)} – {fmt_time(end)}.")
    return True, ""


def check_available(doctor, when: datetime):
    ok, reason = is_available(doctor, when)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)


def slots_for_day(doctor, day: date, taken: set, now: datetime = None) -> dict:
    """All bookable times of one calendar day for a doctor.
    taken = set of "HH:MM" strings already booked. Past times (today) are marked not free.
    Returns {"working": bool, "reason": str, "schedule": str, "slots": [{"time","label","free"}]}"""
    now = now or datetime.now()
    out = {"working": False, "reason": "", "schedule": schedule_text(doctor), "slots": []}
    if day > now.date() + timedelta(days=MAX_ADVANCE_DAYS):
        out["reason"] = f"Appointments can be booked up to {MAX_ADVANCE_DAYS} days in advance."
        return out
    probe = datetime.combine(day, working_hours(doctor)[0])
    ok, reason = is_available(doctor, probe)
    if not ok and working_days(doctor) and probe.strftime("%A") not in working_days(doctor):
        out["reason"] = reason
        return out
    start, end = working_hours(doctor)
    cur = datetime.combine(day, start)
    stop = datetime.combine(day, end) if start < end else datetime.combine(day + timedelta(days=1), end)
    while (cur <= stop) if ALLOW_START_AT_CLOSING else (cur < stop):
        key = cur.strftime("%H:%M")
        free = key not in taken and cur > now
        out["slots"].append({"time": key, "label": fmt_time(cur.time()), "free": free})
        cur += timedelta(minutes=SLOT_MINUTES)
    out["working"] = True
    return out


def check_bookable_in_advance(when: datetime):
    """Online bookings: not in the past, not further than MAX_ADVANCE_DAYS ahead."""
    now = datetime.now()
    if when < now - timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="That time has already passed. Please choose a future date and time.")
    if when > now + timedelta(days=MAX_ADVANCE_DAYS):
        raise HTTPException(status_code=400, detail=f"Appointments can be booked up to {MAX_ADVANCE_DAYS} days in advance.")
