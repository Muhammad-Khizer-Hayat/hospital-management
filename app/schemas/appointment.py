from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime
from app.models.appointment import AppointmentStatus


class AppointmentBase(BaseModel):
    doctor_id: int
    appointment_date: datetime
    duration_minutes: Optional[int] = 30
    reason: Optional[str] = None
    notes: Optional[str] = None


RELATIONS = ["Mother", "Father", "Spouse", "Son", "Daughter", "Brother", "Sister", "Grandparent", "Friend", "Other"]


class AppointmentCreate(AppointmentBase):
    patient_id: Optional[int] = None  # set from token for patient role
    # Fill these when the appointment is for somebody else (leave empty = for the account holder)
    booked_for_name: Optional[str] = None
    booked_for_relation: Optional[str] = None
    booked_for_age: Optional[int] = None
    booked_for_gender: Optional[str] = None
    booked_for_phone: Optional[str] = None

    @model_validator(mode="after")
    def check_booked_for(self):
        name = " ".join((self.booked_for_name or "").split())
        if not name:
            self.booked_for_name = self.booked_for_relation = self.booked_for_age = self.booked_for_gender = self.booked_for_phone = None
            return self
        if len(name) < 3 or not any(c.isalpha() for c in name):
            raise ValueError("Please enter the patient's full name")
        if self.booked_for_relation not in RELATIONS:
            raise ValueError("Please choose how this person is related to you")
        if self.booked_for_age is None or not 0 <= self.booked_for_age <= 120:
            raise ValueError("Please enter the patient's age (0-120)")
        self.booked_for_name = name
        return self


class AppointmentUpdate(BaseModel):
    appointment_date: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = None
    duration_minutes: Optional[int] = None


class AppointmentOut(AppointmentBase):
    id: int
    patient_id: int
    status: AppointmentStatus
    created_at: datetime
    # names + consultation bill (so the portal and admin can show Pay / Receipt buttons)
    doctor_name: Optional[str] = None
    patient_name: Optional[str] = None        # who the doctor will see
    account_name: Optional[str] = None        # who booked (account holder)
    patient_phone: Optional[str] = None
    booked_for_name: Optional[str] = None
    booked_for_relation: Optional[str] = None
    booked_for_age: Optional[int] = None
    booked_for_gender: Optional[str] = None
    source: Optional[str] = None
    token_no: Optional[int] = None
    prescription_id: Optional[int] = None
    bill_id: Optional[int] = None
    amount: Optional[float] = None
    payment_status: Optional[str] = None   # pending | paid | cancelled
    receipt_no: Optional[str] = None

    class Config:
        from_attributes = True
