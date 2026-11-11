from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.appointment import AppointmentStatus


class AppointmentBase(BaseModel):
    doctor_id: int
    appointment_date: datetime
    duration_minutes: Optional[int] = 30
    reason: Optional[str] = None
    notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    patient_id: Optional[int] = None  # set from token for patient role


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
    patient_name: Optional[str] = None
    bill_id: Optional[int] = None
    amount: Optional[float] = None
    payment_status: Optional[str] = None   # pending | paid | cancelled
    receipt_no: Optional[str] = None

    class Config:
        from_attributes = True
