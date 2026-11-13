from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from typing import List
import uuid
from sqlalchemy import or_
from app.utils.helpers import hash_password
from app.database import get_db
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.patient import PatientCreate, PatientUpdate, PatientOut, WalkInRegister
from app.utils.dependencies import require_staff, require_front_desk, get_current_user

router = APIRouter(prefix="/api/patients", tags=["Patients"])


@router.get("/", response_model=List[PatientOut])
def list_patients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db),
                   _=Depends(require_staff)):
    return db.query(Patient).offset(skip).limit(limit).all()


@router.get("/search", response_model=List[PatientOut])
def search_patients(q: str, db: Session = Depends(get_db), _=Depends(require_front_desk)):
    """Front desk: find a patient by name, phone, email or patient number."""
    q = (q or "").strip()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    cond = or_(User.full_name.ilike(like), User.phone.ilike(like), User.email.ilike(like))
    if q.lstrip("#").isdigit():
        cond = or_(cond, Patient.id == int(q.lstrip("#")))
    return db.query(Patient).join(User, Patient.user_id == User.id).filter(cond).limit(15).all()


@router.post("/walk-in", response_model=PatientOut, status_code=201)
def register_walk_in(data: WalkInRegister, db: Session = Depends(get_db), _=Depends(require_front_desk)):
    """Front desk: register a patient who is standing at the counter (no online account needed)."""
    email = (data.email or "").strip().lower() or f"walkin-{uuid.uuid4().hex[:10]}@walkin.local"
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="A patient with this email already exists - search for them instead.")
    user = User(full_name=data.full_name, email=email, phone=data.phone, role=UserRole.PATIENT,
                hashed_password=hash_password(uuid.uuid4().hex))       # no password: they can register online later
    db.add(user); db.flush()
    patient = Patient(user_id=user.id, gender=data.gender, address=data.address,
                      date_of_birth=date(date.today().year - data.age, 1, 1) if data.age is not None else None)
    db.add(patient); db.commit(); db.refresh(patient)
    return patient


@router.get("/me", response_model=PatientOut)
def get_my_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if current_user.role == UserRole.PATIENT and patient.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return patient


@router.put("/me", response_model=PatientOut)
def update_my_profile(data: PatientUpdate, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    changes = data.model_dump(exclude_unset=True)
    phone = changes.pop("phone", None)
    if phone:
        current_user.phone = phone
    # A date of birth can be added once by the patient. Changing it later needs the front desk,
    # because it is used to verify callers on the phone helpline.
    if ("date_of_birth" in changes and patient.date_of_birth is not None
            and changes["date_of_birth"] != patient.date_of_birth):
        raise HTTPException(status_code=403,
            detail="Your date of birth is already on file. Please ask the front desk to change it.")
    for field, value in changes.items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient


@router.put("/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: int, data: PatientUpdate, db: Session = Depends(get_db),
                    _=Depends(require_staff)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient
