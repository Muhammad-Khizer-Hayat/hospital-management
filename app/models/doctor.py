from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    specialization = Column(String(150))
    qualification = Column(String(200))
    experience_years = Column(Integer, default=0)
    consultation_fee = Column(Float, default=0.0)
    bio = Column(Text)
    available_days = Column(JSON, default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    available_from = Column(String(10), default="09:00")
    available_to = Column(String(10), default="17:00")
    license_number = Column(String(100))

    user = relationship("User", back_populates="doctor_profile")
    department = relationship("Department", back_populates="doctors")
    appointments = relationship("Appointment", back_populates="doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")
