from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.billing_service import create_consultation_bill, cancel_pending_bill


def create_appointment(db: Session, data: AppointmentCreate, patient_id: int, source: str = "online") -> Appointment:
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

    # Queue number: 1, 2, 3 ... per doctor per day
    day_start = data.appointment_date.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    taken = db.query(Appointment).filter(
        Appointment.doctor_id == data.doctor_id,
        Appointment.appointment_date >= day_start, Appointment.appointment_date < day_start + timedelta(days=1),
        Appointment.status.notin_([AppointmentStatus.CANCELLED])).count()

    appointment = Appointment(
        booked_for_name=data.booked_for_name, booked_for_relation=data.booked_for_relation,
        booked_for_age=data.booked_for_age, booked_for_gender=data.booked_for_gender,
        booked_for_phone=data.booked_for_phone, source=source, token_no=taken + 1,
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
