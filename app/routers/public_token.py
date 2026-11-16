"""Public (no login) pages behind the QR code on a printed token: live queue status + the QR image."""
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.services.availability import doctor_label
from app.services.token_service import make_code, parse_code, qr_svg

router = APIRouter(prefix="/api/public/token", tags=["Token"])
_OPEN = [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]


def _load(db: Session, code: str) -> Appointment:
    appt_id = parse_code(code)
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first() if appt_id else None
    if not appt:
        raise HTTPException(status_code=404, detail="Token not found")
    return appt


@router.get("/{code}")
def token_status(code: str, db: Session = Depends(get_db)):
    appt = _load(db, code)
    day = appt.appointment_date.replace(hour=0, minute=0, second=0, microsecond=0)
    waiting = [a.token_no for a in db.query(Appointment).filter(
        Appointment.doctor_id == appt.doctor_id, Appointment.status.in_(_OPEN),
        Appointment.appointment_date >= day, Appointment.appointment_date < day + timedelta(days=1)).all()
        if a.token_no is not None]
    mine_open = appt.status in _OPEN
    parts = (appt.patient_name or "").split()
    return {
        "token_no": appt.token_no, "status": appt.status.value,
        "patient": (parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")) if parts else "",
        "doctor": doctor_label(appt.doctor) if appt.doctor else "", "appointment_date": appt.appointment_date,
        "now_serving": min(waiting) if waiting else None,
        "ahead": len([t for t in waiting if t < (appt.token_no or 0)]) if mine_open else 0,
        "payment_status": appt.payment_status,
    }


@router.get("/{code}/qr.svg")
def token_qr(code: str, request: Request, base: Optional[str] = None, db: Session = Depends(get_db)):
    appt = _load(db, code)
    root = base if base and base.startswith(("http://", "https://")) and len(base) < 200 else str(request.base_url)
    svg = qr_svg(f"{root.rstrip('/')}/t/{make_code(appt.id)}")
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})
