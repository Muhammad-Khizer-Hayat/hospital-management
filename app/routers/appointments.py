from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentOut
from app.services.appointment_service import create_appointment, get_appointments, update_appointment
from app.services.billing_service import cancel_pending_bill
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


def _check_access(db: Session, appt: Appointment, user: User):
    """Patients see only their own appointments, doctors only their own. Others look 'not found'."""
    if user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient or appt.patient_id != patient.id:
            raise HTTPException(status_code=404, detail="Appointment not found")
    elif user.role == UserRole.DOCTOR:
        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
        if not doctor or appt.doctor_id != doctor.id:
            raise HTTPException(status_code=404, detail="Appointment not found")


@router.get("/", response_model=List[AppointmentOut])
def list_appointments(skip: int = 0, limit: int = 100,
                       status: Optional[str] = None,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    filters = {}
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if patient:
            filters["patient_id"] = patient.id
    elif current_user.role == UserRole.DOCTOR:
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if doctor:
            filters["doctor_id"] = doctor.id
    if status:
        filters["status"] = status
    return get_appointments(db, skip=skip, limit=limit, **filters)


@router.post("/", response_model=AppointmentOut, status_code=201)
def book_appointment(data: AppointmentCreate, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    patient_id = data.patient_id
    if current_user.role == UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Appointments are booked by patients or the front desk.")
    source = "walk_in" if current_user.role in (UserRole.RECEPTIONIST, UserRole.ADMIN) else "online"
    if source == "walk_in" and not patient_id:
        raise HTTPException(status_code=400, detail="Choose the patient first.")
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient:
            # Auto-create missing patient profile instead of failing
            patient = Patient(user_id=current_user.id)
            db.add(patient)
            db.commit()
            db.refresh(patient)
        patient_id = patient.id
        if not patient.profile_complete:
            raise HTTPException(status_code=400, detail="Please complete your profile before booking: "
                                + ", ".join(patient.missing_fields) + ".")

    # Booking creates the appointment AND its consultation bill (unpaid).
    # The patient pays and downloads the receipt later from the patient portal.
    return create_appointment(db, data, patient_id, source=source)


@router.get("/{appt_id}", response_model=AppointmentOut)
def get_appointment(appt_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _check_access(db, appt, current_user)
    return appt


@router.put("/{appt_id}", response_model=AppointmentOut)
def update_appt(appt_id: int, data: AppointmentUpdate, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _check_access(db, appt, current_user)
    if current_user.role == UserRole.PATIENT and data.status not in (None, AppointmentStatus.CANCELLED):
        raise HTTPException(status_code=403, detail="Patients can only cancel appointments.")
    return update_appointment(db, appt_id, data)


@router.delete("/{appt_id}", status_code=204)
def cancel_appointment(appt_id: int, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _check_access(db, appt, current_user)
    appt.status = AppointmentStatus.CANCELLED
    cancel_pending_bill(db, appt)
    db.commit()
