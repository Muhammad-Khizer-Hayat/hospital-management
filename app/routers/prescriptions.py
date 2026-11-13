from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.prescription import Prescription
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.appointment import Appointment, AppointmentStatus
from app.services.prescription_service import build_prescription_pdf
from app.models.user import User, UserRole
from app.schemas.prescription import PrescriptionCreate, PrescriptionUpdate, PrescriptionOut
from app.utils.dependencies import require_doctor, get_current_user

router = APIRouter(prefix="/api/prescriptions", tags=["Prescriptions"])


def _can_view(db, rx, user):
    """Patients see their own prescriptions, doctors the ones they wrote, staff everything."""
    if user.role == UserRole.PATIENT:
        p = db.query(Patient).filter(Patient.user_id == user.id).first()
        return bool(p) and rx.patient_id == p.id
    if user.role == UserRole.DOCTOR:
        d = db.query(Doctor).filter(Doctor.user_id == user.id).first()
        return bool(d) and rx.doctor_id == d.id
    return True


@router.get("/", response_model=List[PrescriptionOut])
def list_prescriptions(patient_id: int = None, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    query = db.query(Prescription)
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient:
            return []
        query = query.filter(Prescription.patient_id == patient.id)
    elif current_user.role == UserRole.DOCTOR:
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor:
            return []
        query = query.filter(Prescription.doctor_id == doctor.id)
    elif patient_id:
        query = query.filter(Prescription.patient_id == patient_id)
    return query.all()


@router.post("/", response_model=PrescriptionOut, status_code=201)
def create_prescription(data: PrescriptionCreate, db: Session = Depends(get_db),
                         current_user: User = Depends(require_doctor)):
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    appt = None
    patient_id = data.patient_id
    if data.appointment_id:
        appt = db.query(Appointment).filter(Appointment.id == data.appointment_id).first()
        if not appt or (doctor and appt.doctor_id != doctor.id):
            raise HTTPException(status_code=404, detail="Appointment not found")
        if appt.status == AppointmentStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="This appointment was cancelled.")
        patient_id = appt.patient_id
    if not patient_id or not db.query(Patient).filter(Patient.id == patient_id).first():
        raise HTTPException(status_code=404, detail="Patient not found")
    prescription = Prescription(
        doctor_id=doctor.id if doctor else (appt.doctor_id if appt else 1),
        appointment_id=appt.id if appt else None,
        patient_id=patient_id,
        diagnosis=data.diagnosis,
        medicines=[m.model_dump() for m in (data.medicines or [])],
        instructions=data.instructions,
        follow_up_date=data.follow_up_date
    )
    db.add(prescription)
    if appt:
        appt.status = AppointmentStatus.COMPLETED      # writing the prescription finishes the visit - visible everywhere
    db.commit()
    db.refresh(prescription)
    return prescription


@router.get("/{rx_id}", response_model=PrescriptionOut)
def get_prescription(rx_id: int, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    rx = db.query(Prescription).filter(Prescription.id == rx_id).first()
    if not rx or not _can_view(db, rx, current_user):
        raise HTTPException(status_code=404, detail="Prescription not found")
    return rx


@router.get("/{rx_id}/pdf")
def prescription_pdf(rx_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    rx = db.query(Prescription).filter(Prescription.id == rx_id).first()
    if not rx or not _can_view(db, rx, current_user):
        raise HTTPException(status_code=404, detail="Prescription not found")
    return Response(content=build_prescription_pdf(rx), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="prescription-RX-{rx.id:05d}.pdf"'})


@router.put("/{rx_id}", response_model=PrescriptionOut)
def update_prescription(rx_id: int, data: PrescriptionUpdate, db: Session = Depends(get_db),
                         current_user: User = Depends(require_doctor)):
    rx = db.query(Prescription).filter(Prescription.id == rx_id).first()
    if not rx or not _can_view(db, rx, current_user):
        raise HTTPException(status_code=404, detail="Prescription not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "medicines" and value:
            value = [m.model_dump() for m in value]
        setattr(rx, field, value)
    db.commit()
    db.refresh(rx)
    return rx
