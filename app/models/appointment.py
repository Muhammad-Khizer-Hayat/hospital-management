from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    appointment_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING)
    reason = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    bill = relationship("Bill", back_populates="appointment", uselist=False)

    # Read-only helpers so lists can show names and payment info without extra queries in the routers
    @property
    def doctor_name(self):
        return self.doctor.user.full_name if self.doctor and self.doctor.user else None

    @property
    def patient_name(self):
        return self.patient.user.full_name if self.patient and self.patient.user else None

    @property
    def bill_id(self):
        return self.bill.id if self.bill else None

    @property
    def amount(self):
        return self.bill.total if self.bill else None

    @property
    def payment_status(self):
        return self.bill.payment_status.value if self.bill and self.bill.payment_status else None

    @property
    def receipt_no(self):
        return self.bill.receipt_no if self.bill else None
