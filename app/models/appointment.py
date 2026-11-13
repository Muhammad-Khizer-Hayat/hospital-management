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
    # Booked for somebody else (parent, child, ...)? The account holder is the one who booked.
    booked_for_name = Column(String(100))
    booked_for_relation = Column(String(30))
    booked_for_age = Column(Integer)
    booked_for_gender = Column(String(10))
    booked_for_phone = Column(String(20))
    source = Column(String(20), default="online")      # online | walk_in | phone
    token_no = Column(Integer)                          # queue number for that doctor on that day

    patient = relationship("Patient", back_populates="appointments")
    prescriptions = relationship("Prescription", back_populates="appointment")
    doctor = relationship("Doctor", back_populates="appointments")
    bill = relationship("Bill", back_populates="appointment", uselist=False)

    # Read-only helpers so lists can show names and payment info without extra queries in the routers
    @property
    def doctor_name(self):
        return self.doctor.user.full_name if self.doctor and self.doctor.user else None

    @property
    def account_name(self):
        """The registered account holder (the person who booked)."""
        return self.patient.user.full_name if self.patient and self.patient.user else None

    @property
    def patient_name(self):
        """Name of the person who will actually be seen by the doctor."""
        return self.booked_for_name or self.account_name

    @property
    def patient_phone(self):
        return self.booked_for_phone or (self.patient.user.phone if self.patient and self.patient.user else None)

    @property
    def prescription_id(self):
        return self.prescriptions[-1].id if self.prescriptions else None

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
