from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.billing import PaymentStatus


class BillItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float


class BillBase(BaseModel):
    patient_id: int
    appointment_id: Optional[int] = None
    items: List[BillItem] = []
    discount: Optional[float] = 0.0
    tax: Optional[float] = 0.0
    payment_method: Optional[str] = None
    notes: Optional[str] = None


class BillCreate(BillBase):
    pass


class BillUpdate(BaseModel):
    payment_status: Optional[PaymentStatus] = None
    payment_method: Optional[str] = None
    discount: Optional[float] = None
    notes: Optional[str] = None


class PayRequest(BaseModel):
    payment_method: str
    # What is needed depends on the method (checked in billing_service.validate_payment_details):
    #   card -> card_number, card_expiry (MM/YY), cvv, card_holder
    #   easypaisa / jazzcash -> account_number (mobile wallet number, 03XXXXXXXXX)
    #   bank_transfer -> account_number (account number or IBAN)
    account_number: Optional[str] = None
    card_number: Optional[str] = None
    card_expiry: Optional[str] = None
    card_holder: Optional[str] = None
    cvv: Optional[str] = None


class BillOut(BillBase):
    id: int
    subtotal: float
    total: float
    payment_status: PaymentStatus
    created_at: datetime
    patient_name: Optional[str] = None
    receipt_no: Optional[str] = None
    paid_at: Optional[datetime] = None
    transaction_ref: Optional[str] = None
    payment_account: Optional[str] = None

    class Config:
        from_attributes = True
