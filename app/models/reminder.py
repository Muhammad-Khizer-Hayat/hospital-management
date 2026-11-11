from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class AppointmentReminder(Base):
    """Remembers which appointments already got a reminder email (so none is sent twice)."""
    __tablename__ = "appointment_reminders"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), unique=True, nullable=False)
    sent_at = Column(DateTime, server_default=func.now())