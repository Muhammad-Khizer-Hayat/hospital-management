from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    diagnosis = Column(Text)
    medicines = Column(JSON, default=[])
    # medicines format: [{"name": "...", "dosage": "...", "frequency": "...", "duration": "..."}]
    instructions = Column(Text)
    follow_up_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def doctor_name(self):
        return self.doctor.user.full_name if self.doctor and self.doctor.user else None

    @property
    def doctor_specialization(self):
        return self.doctor.specialization if self.doctor else None

    @property
    def patient_name(self):
        if self.appointment and self.appointment.booked_for_name:
            return self.appointment.booked_for_name
        return self.patient.user.full_name if self.patient and self.patient.user else None

    patient = relationship("Patient", back_populates="prescriptions")
    doctor = relationship("Doctor", back_populates="prescriptions")

    appointment = relationship("Appointment", back_populates="prescriptions")
