from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    items = Column(JSON, default=[])
    # items format: [{"description": "...", "quantity": 1, "unit_price": 100.0}]
    subtotal = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_method = Column(String(50))
    notes = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="bills")
    appointment = relationship("Appointment", back_populates="bill")
    payment = relationship("Payment", back_populates="bill", uselist=False)

    # Receipt details come from the payment row (None until the bill is paid)
    @property
    def receipt_no(self):
        return f"RCPT-{self.payment.id:06d}" if self.payment else None

    @property
    def patient_name(self):
        return self.patient.user.full_name if self.patient and self.patient.user else None

    @property
    def paid_at(self):
        return self.payment.paid_at if self.payment else None

    @property
    def payment_account(self):
        return self.payment.account_masked if self.payment else None

    @property
    def transaction_ref(self):
        return self.payment.reference if self.payment else None


class Payment(Base):
    """One row per successful payment. A receipt is generated from this."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), unique=True, nullable=False)  # a bill can be paid only once
    patient_id = Column(Integer, ForeignKey("patients.id"))
    amount = Column(Float, nullable=False)
    method = Column(String(50), nullable=False)
    reference = Column(String(40), unique=True)
    account_masked = Column(String(40))   # e.g. "•••• 4242" - the full number / CVV are never stored
    paid_at = Column(DateTime, default=datetime.now)

    bill = relationship("Bill", back_populates="payment")
