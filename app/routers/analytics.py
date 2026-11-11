from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.billing import Bill, PaymentStatus
from app.utils.dependencies import require_admin

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/dashboard")
def dashboard_stats(db: Session = Depends(get_db), _=Depends(require_admin)):
    total_patients = db.query(Patient).count()
    total_doctors = db.query(Doctor).count()
    total_appointments = db.query(Appointment).count()

    appointment_stats = db.query(
        Appointment.status,
        func.count(Appointment.id).label("count")
    ).group_by(Appointment.status).all()

    revenue = db.query(func.sum(Bill.total)).filter(
        Bill.payment_status == PaymentStatus.PAID
    ).scalar() or 0

    pending_bills = db.query(Bill).filter(
        Bill.payment_status == PaymentStatus.PENDING
    ).count()

    today_appointments = db.query(Appointment).filter(
        func.date(Appointment.appointment_date) == func.current_date()
    ).count()

    return {
        "total_patients": total_patients,
        "total_doctors": total_doctors,
        "total_appointments": total_appointments,
        "today_appointments": today_appointments,
        "appointment_breakdown": {s.value: c for s, c in appointment_stats},
        "total_revenue": round(revenue, 2),
        "pending_bills": pending_bills,
    }


@router.get("/appointments/monthly")
def monthly_appointments(db: Session = Depends(get_db), _=Depends(require_admin)):
    results = db.query(
        func.strftime("%Y-%m", Appointment.appointment_date).label("month"),
        func.count(Appointment.id).label("count")
    ).group_by("month").order_by("month").limit(12).all()
    return [{"month": r.month, "count": r.count} for r in results]
