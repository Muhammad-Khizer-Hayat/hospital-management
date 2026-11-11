from pydantic import BaseModel, EmailStr
from typing import Optional, List
from app.schemas.user import UserOut
from app.schemas.department import DepartmentOut


class DoctorBase(BaseModel):
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    experience_years: Optional[int] = 0
    consultation_fee: Optional[float] = 0.0
    bio: Optional[str] = None
    available_days: Optional[List[str]] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    available_from: Optional[str] = "09:00"
    available_to: Optional[str] = "17:00"
    license_number: Optional[str] = None
    department_id: Optional[int] = None


class DoctorCreate(DoctorBase):
    pass


class DoctorUpdate(DoctorBase):
    pass


class DoctorRegister(DoctorBase):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    password: str


class DoctorOut(DoctorBase):
    id: int
    user_id: int
    user: Optional[UserOut] = None
    department: Optional[DepartmentOut] = None

    class Config:
        from_attributes = True