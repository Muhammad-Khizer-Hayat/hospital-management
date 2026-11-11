import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
import logging

logger = logging.getLogger(__name__)


async def send_email(to_email: str, subject: str, body: str) -> bool:
    """Returns True only if the email was really sent."""
    if not settings.SMTP_USER:
        logger.info(f"Email not configured. Would send to {to_email}: {subject}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


async def send_appointment_confirmation(patient_email: str, patient_name: str,
                                         doctor_name: str, appointment_date: str) -> bool:
    subject = f"Appointment Confirmed - {settings.HOSPITAL_NAME}"
    body = f"""
    <h2>Appointment Confirmation</h2>
    <p>Dear {patient_name},</p>
    <p>Your appointment has been confirmed:</p>
    <ul>
        <li><strong>Doctor:</strong> Dr. {doctor_name}</li>
        <li><strong>Date & Time:</strong> {appointment_date}</li>
        <li><strong>Hospital:</strong> {settings.HOSPITAL_NAME}</li>
    </ul>
    <p>Please arrive 15 minutes early. For cancellations, contact us at {settings.HOSPITAL_PHONE}.</p>
    <p>Best regards,<br>{settings.HOSPITAL_NAME}</p>
    """
    return await send_email(patient_email, subject, body)


async def send_appointment_reminder(patient_email: str, patient_name: str,
                                     doctor_name: str, appointment_date: str) -> bool:
    subject = f"Appointment Reminder - {settings.HOSPITAL_NAME}"
    body = f"""
    <h2>Appointment Reminder</h2>
    <p>Dear {patient_name},</p>
    <p>This is a reminder for your upcoming appointment:</p>
    <ul>
        <li><strong>Doctor:</strong> Dr. {doctor_name}</li>
        <li><strong>Date & Time:</strong> {appointment_date}</li>
    </ul>
    <p>Please bring any previous medical records. Contact us at {settings.HOSPITAL_PHONE} if you need to reschedule.</p>
    """
    return await send_email(patient_email, subject, body)