from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MedicineItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str


class PrescriptionBase(BaseModel):
    patient_id: Optional[int] = None      # taken from the appointment when appointment_id is given
    appointment_id: Optional[int] = None
    diagnosis: Optional[str] = None
    medicines: Optional[List[MedicineItem]] = []
    instructions: Optional[str] = None
    follow_up_date: Optional[datetime] = None


class PrescriptionCreate(PrescriptionBase):
    pass


class PrescriptionUpdate(BaseModel):
    diagnosis: Optional[str] = None
    medicines: Optional[List[MedicineItem]] = None
    instructions: Optional[str] = None
    follow_up_date: Optional[datetime] = None


class PrescriptionOut(PrescriptionBase):
    id: int
    doctor_id: int
    created_at: datetime
    doctor_name: Optional[str] = None
    doctor_specialization: Optional[str] = None
    patient_name: Optional[str] = None
    appointment_id: Optional[int] = None

    class Config:
        from_attributes = True
