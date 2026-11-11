"""Sends one reminder email for every appointment starting within the next 24 hours."""
import asyncio
import logging
from datetime import datetime, timedelta

from app.config import settings
from app.database import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.reminder import AppointmentReminder
from app.services.notification_service import send_appointment_reminder

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 600     # look for due reminders every 10 minutes
REMIND_WITHIN_HOURS = 24


def _plain_name(full_name: str) -> str:
    """The email template already writes 'Dr.', so drop it from names that include it."""
    name = full_name.strip()
    return name[3:].strip() if name.lower().startswith("dr.") else name


async def run_reminder_cycle() -> int:
    """Send all due reminders once. Returns how many were sent."""
    db = SessionLocal()
    sent = 0
    try:
        now = datetime.now()
        already = db.query(AppointmentReminder.appointment_id)
        due = db.query(Appointment).filter(
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            Appointment.appointment_date > now,
            Appointment.appointment_date <= now + timedelta(hours=REMIND_WITHIN_HOURS),
            ~Appointment.id.in_(already),
        ).all()
        for appt in due:
            user = appt.patient.user if appt.patient else None
            if not user or not user.email:
                continue
            ok = await send_appointment_reminder(
                user.email, user.full_name, _plain_name(appt.doctor.user.full_name),
                appt.appointment_date.strftime("%A %d %B %Y at %I:%M %p"))
            if ok:  # only mark as sent when the email really went out
                db.add(AppointmentReminder(appointment_id=appt.id))
                db.commit()
                sent += 1
    finally:
        db.close()
    return sent


async def reminder_loop():
    if not settings.SMTP_USER:
        logger.info("Appointment reminders are OFF (set SMTP_USER / SMTP_PASSWORD / SMTP_FROM in .env to enable).")
        return
    logger.info("Appointment reminder service started.")
    while True:
        try:
            count = await run_reminder_cycle()
            if count:
                logger.info(f"Sent {count} appointment reminder(s).")
        except Exception:
            logger.exception("Reminder cycle failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)