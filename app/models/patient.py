from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20))
    blood_group = Column(String(10))
    address = Column(Text)
    emergency_contact = Column(String(100))
    emergency_phone = Column(String(20))
    allergies = Column(Text)
    chronic_conditions = Column(Text)
    insurance_provider = Column(String(100))
    insurance_number = Column(String(100))

    REQUIRED_FIELDS = {"date_of_birth": "Date of birth", "gender": "Gender", "blood_group": "Blood group",
                       "address": "Address", "emergency_contact": "Emergency contact name",
                       "emergency_phone": "Emergency contact phone"}

    @property
    def missing_fields(self):
        """Labels of the required profile details that are still empty."""
        missing = [label for f, label in self.REQUIRED_FIELDS.items() if not getattr(self, f)]
        if not (self.user and self.user.phone):
            missing.insert(0, "Mobile number")
        return missing

    @property
    def profile_complete(self):
        return not self.missing_fields

    user = relationship("User", back_populates="patient_profile")
    appointments = relationship("Appointment", back_populates="patient")
    prescriptions = relationship("Prescription", back_populates="patient")
    bills = relationship("Bill", back_populates="patient")
