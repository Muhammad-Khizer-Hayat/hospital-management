from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.doctor import Doctor
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.appointment import Appointment
from app.models.prescription import Prescription
from app.schemas.doctor import DoctorRegister, DoctorUpdate, DoctorOut
from app.utils.helpers import hash_password
from app.utils.dependencies import require_admin, require_doctor, get_current_user

router = APIRouter(prefix="/api/doctors", tags=["Doctors"])


@router.get("/", response_model=List[DoctorOut])
def list_doctors(department_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Doctor).join(User, Doctor.user_id == User.id).filter(User.is_active == True)
    if department_id:
        query = query.filter(Doctor.department_id == department_id)
    return query.all()


@router.get("/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.post("/", response_model=DoctorOut, status_code=201)
def create_doctor(data: DoctorRegister, db: Session = Depends(get_db), _=Depends(require_admin)):
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.query(User).filter(func.lower(User.email) == str(data.email).lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if data.department_id and not db.query(Department).filter(Department.id == data.department_id).first():
        raise HTTPException(status_code=404, detail="Department not found")

    user = User(
        full_name=data.full_name, email=str(data.email), phone=data.phone,
        hashed_password=hash_password(data.password), role=UserRole.DOCTOR
    )
    db.add(user)
    db.flush()  # get user.id

    doctor_fields = data.model_dump(exclude={"full_name", "email", "phone", "password"})
    doctor = Doctor(user_id=user.id, **doctor_fields)
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.delete("/{doctor_id}")
def delete_doctor(doctor_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    user = doctor.user
    has_history = (
        db.query(Appointment).filter(Appointment.doctor_id == doctor_id).first()
        or db.query(Prescription).filter(Prescription.doctor_id == doctor_id).first()
    )
    if has_history:
        # Keep medical records intact: deactivate instead of deleting
        user.is_active = False
        db.commit()
        return {"deleted": False,
                "detail": "Doctor has appointment/prescription history, so the account was deactivated instead of deleted."}

    db.delete(doctor)
    db.flush()
    db.delete(user)
    db.commit()
    return {"deleted": True, "detail": "Doctor deleted."}


@router.put("/{doctor_id}", response_model=DoctorOut)
def update_doctor(doctor_id: int, data: DoctorUpdate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    # Doctor can update own profile; admin can update any
    if current_user.role != UserRole.ADMIN and doctor.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(doctor, field, value)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.get("/{doctor_id}/schedule")
def get_doctor_schedule(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {
        "doctor_id": doctor_id,
        "available_days": doctor.available_days,
        "available_from": doctor.available_from,
        "available_to": doctor.available_to,
    }
