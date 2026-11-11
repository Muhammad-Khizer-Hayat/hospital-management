from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.billing_service import create_consultation_bill, cancel_pending_bill


def create_appointment(db: Session, data: AppointmentCreate, patient_id: int) -> Appointment:
    doctor = db.query(Doctor).filter(Doctor.id == data.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    # Check for conflicts
    conflict = db.query(Appointment).filter(
        Appointment.doctor_id == data.doctor_id,
        Appointment.appointment_date == data.appointment_date,
        Appointment.status.notin_([AppointmentStatus.CANCELLED])
    ).first()
    if conflict:
        raise HTTPException(status_code=409, detail="Doctor already has an appointment at this time")

    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=data.doctor_id,
        appointment_date=data.appointment_date,
        duration_minutes=data.duration_minutes,
        reason=data.reason,
        notes=data.notes,
        status=AppointmentStatus.PENDING
    )
    db.add(appointment)
    db.flush()                                          # get appointment.id
    create_consultation_bill(db, appointment, doctor)   # every booking gets a consultation bill
    db.commit()                                         # appointment + bill saved together
    db.refresh(appointment)
    return appointment


def get_appointments(db: Session, skip: int = 0, limit: int = 100, **filters):
    query = db.query(Appointment)
    if filters.get("patient_id"):
        query = query.filter(Appointment.patient_id == filters["patient_id"])
    if filters.get("doctor_id"):
        query = query.filter(Appointment.doctor_id == filters["doctor_id"])
    if filters.get("status"):
        query = query.filter(Appointment.status == filters["status"])
    return query.offset(skip).limit(limit).all()


def update_appointment(db: Session, appointment_id: int, data: AppointmentUpdate) -> Appointment:
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(appt, field, value)
    if appt.status == AppointmentStatus.CANCELLED:
        cancel_pending_bill(db, appt)
    db.commit()
    db.refresh(appt)
    return appt
