from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.billing import Bill, PaymentStatus
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.billing import BillCreate, BillUpdate, BillOut, PayRequest
from app.services.billing_service import pay_bill, build_receipt_pdf
from app.utils.dependencies import require_staff, get_current_user

router = APIRouter(prefix="/api/billing", tags=["Billing"])


def calculate_totals(items: list, discount: float, tax: float):
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    tax_amount = subtotal * (tax / 100)
    total = subtotal - discount + tax_amount
    return subtotal, total


def _get_bill_for_user(db: Session, bill_id: int, user: User) -> Bill:
    """Patients can only see their own bills. Anyone else's bill looks like 'not found'."""
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient or bill.patient_id != patient.id:
            raise HTTPException(status_code=404, detail="Bill not found")
    return bill


@router.get("/", response_model=List[BillOut])
def list_bills(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Bill)
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient:
            return []          # no profile = no bills (never fall back to showing everyone's)
        query = query.filter(Bill.patient_id == patient.id)
    return query.order_by(Bill.id.desc()).all()


@router.post("/", response_model=BillOut, status_code=201)
def create_bill(data: BillCreate, db: Session = Depends(get_db), _=Depends(require_staff)):
    items = [i.model_dump() for i in data.items]
    subtotal, total = calculate_totals(items, data.discount or 0, data.tax or 0)

    bill = Bill(
        patient_id=data.patient_id,
        appointment_id=data.appointment_id,
        items=items,
        subtotal=subtotal,
        discount=data.discount or 0,
        tax=data.tax or 0,
        total=total,
        payment_method=data.payment_method,
        notes=data.notes
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


@router.get("/{bill_id}", response_model=BillOut)
def get_bill(bill_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_bill_for_user(db, bill_id, current_user)


@router.post("/{bill_id}/pay", response_model=BillOut)
def pay(bill_id: int, data: PayRequest, db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)):
    """Pay a pending bill (demo payment). Patients pay their own; staff can also record cash."""
    bill = _get_bill_for_user(db, bill_id, current_user)
    is_staff = current_user.role in (UserRole.ADMIN, UserRole.RECEPTIONIST)
    details = None if data.payment_method == "cash" else data   # cash at the front desk has no number
    pay_bill(db, bill, data.payment_method, allow_staff_methods=is_staff, details=details)
    return bill


@router.get("/{bill_id}/receipt")
def download_receipt(bill_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    """Downloadable PDF receipt (only once the bill has been paid)."""
    bill = _get_bill_for_user(db, bill_id, current_user)
    if not bill.payment:
        raise HTTPException(status_code=404, detail="No receipt yet: this bill has not been paid.")
    return Response(
        content=build_receipt_pdf(bill),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{bill.receipt_no}.pdf"',
                 "Cache-Control": "no-store"},
    )


@router.put("/{bill_id}", response_model=BillOut)
def update_bill(bill_id: int, data: BillUpdate, db: Session = Depends(get_db),
                 _=Depends(require_staff)):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    changes = data.model_dump(exclude_unset=True)
    new_status = changes.pop("payment_status", None)
    for field, value in changes.items():
        setattr(bill, field, value)
    if new_status == PaymentStatus.PAID and bill.payment_status != PaymentStatus.PAID:
        # marking a bill paid also records the payment, so a receipt exists
        pay_bill(db, bill, bill.payment_method or "cash", allow_staff_methods=True)
    else:
        if new_status is not None:
            bill.payment_status = new_status
        db.commit()
        db.refresh(bill)
    return bill
