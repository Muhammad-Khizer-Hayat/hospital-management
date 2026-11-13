from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import date
from app.schemas.user import UserOut, UserCreate


def _check_dob(v):
    """A date of birth must be real: not in the future, not more than 120 years ago."""
    if v is None:
        return v
    today = date.today()
    if v > today or v.year < today.year - 120:
        raise ValueError("Please enter a real date of birth")
    return v


class PatientBase(BaseModel):
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_number: Optional[str] = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(PatientBase):
    phone: Optional[str] = None      # lives on the user record; handled in the router

    @field_validator("phone", "emergency_phone")
    @classmethod
    def validate_phone(cls, v):
        if v in (None, ""):
            return None
        digits = "".join(c for c in v if c.isdigit())
        if not 10 <= len(digits) <= 15 or not all(c.isdigit() or c in "+-() " for c in v):
            raise ValueError("Please enter a valid phone number")
        return v.strip()

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v):
        return _check_dob(v)


class PatientOut(PatientBase):
    id: int
    user_id: int
    user: Optional[UserOut] = None
    profile_complete: bool = False
    missing_fields: List[str] = []

    class Config:
        from_attributes = True


class PatientRegister(UserCreate, PatientBase):
    """Public signup payload. Date of birth is REQUIRED (needed for the phone helpline)."""
    date_of_birth: date

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v):
        return _check_dob(v)

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v):
        v = " ".join((v or "").split())
        if len(v) < 3 or not any(c.isalpha() for c in v):
            raise ValueError("Please enter your full name")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v or "") < 8 or not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must be at least 8 characters and include a letter and a number")
        return v

    @field_validator("phone", "emergency_phone")
    @classmethod
    def validate_phone(cls, v):
        if v in (None, ""):
            return None
        digits = "".join(c for c in v if c.isdigit())
        if not 10 <= len(digits) <= 15 or not all(c.isdigit() or c in "+-() " for c in v):
            raise ValueError("Please enter a valid phone number")
        return v.strip()


class WalkInRegister(BaseModel):
    """What the front desk needs to register someone standing at the counter."""
    full_name: str
    phone: str
    age: Optional[int] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def v_name(cls, v):
        v = " ".join((v or "").split())
        if len(v) < 3 or not any(c.isalpha() for c in v):
            raise ValueError("Please enter the patient's full name")
        return v

    @field_validator("phone")
    @classmethod
    def v_phone(cls, v):
        digits = "".join(c for c in (v or "") if c.isdigit())
        if not 10 <= len(digits) <= 15:
            raise ValueError("Please enter a valid phone number")
        return v.strip()

    @field_validator("age")
    @classmethod
    def v_age(cls, v):
        if v is not None and not 0 <= v <= 120:
            raise ValueError("Age must be between 0 and 120")
        return v
