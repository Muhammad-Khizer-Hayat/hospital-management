"""Front desk: the patient is standing at the counter. No separate registration step:
the desk picks a doctor, types the patient's details once, and gets a token."""
import re
import uuid
from datetime import date, datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.appointment import AppointmentCreate, WalkInBooking
from app.services.appointment_service import create_appointment
from app.services.availability import check_available, is_available, doctor_label, check_bookable_in_advance
from app.utils.helpers import hash_password


def _digits(s) -> str:
    return re.sub(r"\D", "", s or "")


def _dob_from_age(age):
    return date(date.today().year - age, 1, 1) if age is not None else None


def _find_or_create_patient(db: Session, data: WalkInBooking) -> Patient:
    """Same name + same phone = the same person coming back: reuse their record (and history)."""
    name, digits = data.full_name, _digits(data.phone)
    same_name = (db.query(Patient).join(User, Patient.user_id == User.id)
                 .filter(func.lower(User.full_name) == name.lower()).all())
    for p in same_name:
        if p.user and _digits(p.user.phone) == digits:
            if not p.gender and data.gender:
                p.gender = data.gender
            if not p.date_of_birth and data.age is not None:
                p.date_of_birth = _dob_from_age(data.age)
            if not p.address and data.address:
                p.address = data.address
            return p
    user = User(full_name=name, email=f"walkin-{uuid.uuid4().hex[:10]}@walkin.local", phone=data.phone,
                role=UserRole.PATIENT, hashed_password=hash_password(uuid.uuid4().hex))  # no password: can sign up online later
    db.add(user)
    db.flush()
    patient = Patient(user_id=user.id, gender=data.gender, address=data.address, date_of_birth=_dob_from_age(data.age))
    db.add(patient)
    db.flush()
    return patient


def book_walk_in(db: Session, data: WalkInBooking) -> Appointment:
    doctor = db.query(Doctor).filter(Doctor.id == data.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    now = datetime.now().replace(second=0, microsecond=0)
    if data.appointment_date:                     # booked for a later day/time (advance booking at the desk)
        when = data.appointment_date.replace(second=0, microsecond=0)
        check_bookable_in_advance(when)           # not in the past, not beyond the advance window
        check_available(doctor, when)             # doctor's working day + hours
        clash = db.query(Appointment.id).filter(
            Appointment.doctor_id == doctor.id, Appointment.appointment_date == when,
            Appointment.status.notin_([AppointmentStatus.CANCELLED])).first()
        if clash:
            raise HTTPException(status_code=409, detail="Doctor already has an appointment at this time")
        patient = _find_or_create_patient(db, data)
        payload = AppointmentCreate(doctor_id=doctor.id, appointment_date=when, reason=data.reason or "Appointment booked at reception")
        return create_appointment(db, payload, patient.id, source="walk_in")

    check_available(doctor, now)                  # doctor off duty? stop before anything is saved
    patient = _find_or_create_patient(db, data)

    when = now                                    # the next free minute (5-minute steps) inside the doctor's hours
    for _ in range(48):
        ok, _reason = is_available(doctor, when)
        if not ok:
            raise HTTPException(status_code=400, detail=f"No free time is left today for {doctor_label(doctor)}.")
        clash = db.query(Appointment.id).filter(
            Appointment.doctor_id == doctor.id, Appointment.appointment_date == when,
            Appointment.status.notin_([AppointmentStatus.CANCELLED])).first()
        if not clash:
            break
        when += timedelta(minutes=5)
    else:
        raise HTTPException(status_code=409, detail=f"{doctor_label(doctor)} is fully booked right now.")

    payload = AppointmentCreate(doctor_id=doctor.id, appointment_date=when, reason=data.reason or "Walk-in consultation")
    return create_appointment(db, payload, patient.id, source="walk_in")
