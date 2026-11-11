"""Consultation bills, (demo) payments and PDF receipts."""
import os
import re
import uuid
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import settings
from app.models.appointment import AppointmentStatus
from app.models.billing import Bill, Payment, PaymentStatus

CURRENCY = "$"          # same symbol the rest of the app uses
DEMO_PAYMENTS = True    # no real gateway yet: receipts say so. Set False once you connect a real one.

PAYMENT_METHODS = {
    "card": "Credit / Debit Card",
    "easypaisa": "Easypaisa",
    "jazzcash": "JazzCash",
    "bank_transfer": "Bank Transfer",
}
STAFF_ONLY_METHODS = {"cash": "Cash (front desk)"}


def method_label(method: str) -> str:
    return {**PAYMENT_METHODS, **STAFF_ONLY_METHODS}.get(method, method or "—")


def doctor_label(full_name: str) -> str:
    n = (full_name or "").strip()
    return n if n.lower().startswith("dr") else f"Dr. {n}"


# ───────────────────────── payment details ─────────────────────────
def _luhn_ok(number: str) -> bool:
    total, flip = 0, False
    for ch in reversed(number):
        d = int(ch)
        if flip:
            d *= 2
            d -= 9 if d > 9 else 0
        total += d
        flip = not flip
    return total % 10 == 0


def normalize_pk_mobile(value: str) -> str | None:
    """+92 300 1234567 / 0092300... / 0300-1234567  ->  03001234567 (None if not a valid mobile number)."""
    n = re.sub(r"[\s\-()]", "", value or "")
    n = re.sub(r"^(\+92|0092|92)", "0", n)
    return n if re.fullmatch(r"03\d{9}", n) else None


def validate_payment_details(method: str, d) -> str:
    """Check the number the patient typed for the chosen method and return a MASKED reference
    (safe to store and print). The full card number and the CVV are never saved."""
    def bad(msg):
        raise HTTPException(status_code=400, detail=msg)

    if method == "card":
        num = re.sub(r"[\s\-]", "", d.card_number or "")
        if not re.fullmatch(r"\d{13,19}", num) or not _luhn_ok(num):
            bad("Please enter a valid card number.")
        m = re.fullmatch(r"(\d{2})\s*/\s*(\d{2})", (d.card_expiry or "").strip())
        if not m or not 1 <= int(m.group(1)) <= 12:
            bad("Enter the card expiry as MM/YY.")
        today = date.today()
        if (2000 + int(m.group(2)), int(m.group(1))) < (today.year, today.month):
            bad("This card has expired.")
        if not re.fullmatch(r"\d{3,4}", (d.cvv or "").strip()):
            bad("Please enter the 3 or 4 digit security code (CVV).")
        if len((d.card_holder or "").strip()) < 3:
            bad("Please enter the name on the card.")
        return f"•••• {num[-4:]}"

    if method in ("easypaisa", "jazzcash"):
        mobile = normalize_pk_mobile(d.account_number)
        if not mobile:
            bad(f"Please enter your {PAYMENT_METHODS[method]} mobile number (e.g. 0300 1234567).")
        return f"{mobile[:4]}•••{mobile[-4:]}"

    if method == "bank_transfer":
        acct = re.sub(r"[\s\-]", "", (d.account_number or "")).upper()
        if not (re.fullmatch(r"PK\d{2}[A-Z]{4}\d{16}", acct) or re.fullmatch(r"\d{8,20}", acct)):
            bad("Please enter a valid bank account number or IBAN (PK00BANK0000000000000000).")
        return f"•••• {acct[-4:]}"

    bad("Please choose a valid payment method.")


# ───────────────────────── bills & payments ─────────────────────────
def create_consultation_bill(db: Session, appointment, doctor):
    """Every booking gets an (unpaid) bill for the doctor's consultation fee. Caller commits.
    A free consultation (fee 0) has nothing to pay, so no bill is created."""
    fee = float(doctor.consultation_fee or 0)
    if fee <= 0:
        return None
    bill = Bill(
        patient_id=appointment.patient_id,
        appointment_id=appointment.id,
        items=[{"description": f"Consultation - {doctor_label(doctor.user.full_name)}",
                "quantity": 1, "unit_price": fee}],
        subtotal=fee, discount=0.0, tax=0.0, total=fee,
        payment_status=PaymentStatus.PENDING,
    )
    db.add(bill)
    return bill


def cancel_pending_bill(db: Session, appointment) -> None:
    """If an appointment is cancelled, an unpaid bill is cancelled too. Paid bills stay (refunds are manual). Caller commits."""
    bill = appointment.bill
    if bill and bill.payment_status == PaymentStatus.PENDING:
        bill.payment_status = PaymentStatus.CANCELLED


def pay_bill(db: Session, bill: Bill, method: str, allow_staff_methods: bool = False, details=None):
    """Record a (demo) payment, mark the bill paid and confirm the appointment."""
    allowed = {**PAYMENT_METHODS, **(STAFF_ONLY_METHODS if allow_staff_methods else {})}
    if bill.payment_status == PaymentStatus.PAID:
        raise HTTPException(status_code=409, detail="This bill is already paid.")
    if bill.payment_status == PaymentStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="This bill was cancelled (its appointment was cancelled).")
    if (bill.total or 0) > 0 and method not in allowed:
        raise HTTPException(status_code=400, detail="Please choose a valid payment method.")

    masked = None
    if details is not None and method in PAYMENT_METHODS and (bill.total or 0) > 0:
        masked = validate_payment_details(method, details)   # asks for the number; stores only the masked form

    payment = None
    if (bill.total or 0) > 0:
        payment = Payment(bill_id=bill.id, patient_id=bill.patient_id, amount=bill.total, method=method,
                          reference="TXN" + uuid.uuid4().hex[:10].upper(), account_masked=masked)
        db.add(payment)
        bill.payment_method = method
    bill.payment_status = PaymentStatus.PAID
    if bill.appointment and bill.appointment.status == AppointmentStatus.PENDING:
        bill.appointment.status = AppointmentStatus.CONFIRMED   # paid = confirmed
    try:
        db.commit()
    except IntegrityError:           # two clicks at once: the unique bill_id stops a double payment
        db.rollback()
        raise HTTPException(status_code=409, detail="This bill is already paid.")
    db.refresh(bill)
    return payment


# ───────────────────────── PDF receipt ─────────────────────────
def _p(value) -> str:
    """Escape text for reportlab's Paragraph (it reads <b>, &amp; etc.)."""
    return escape(str(value)) if value not in (None, "") else "—"


LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         "frontend", "logo-icon.png")


def build_receipt_pdf(bill: Bill) -> bytes:
    payment = bill.payment
    patient = bill.patient
    appt = bill.appointment
    doctor = appt.doctor if appt else None

    navy, teal, grey = colors.HexColor("#0a1628"), colors.HexColor("#0d9488"), colors.HexColor("#64748b")
    line, soft, green = colors.HexColor("#e2e8f0"), colors.HexColor("#f1f5f9"), colors.HexColor("#16a34a")
    W = 170 * mm   # printable width (A4 minus 20 mm margins)

    ss = getSampleStyleSheet()
    def st(name, **kw):
        return ParagraphStyle(name, parent=ss["Normal"], fontName=kw.pop("font", "Helvetica"), **kw)
    body = st("body", fontSize=9.5, leading=13)
    bold = st("bold", fontSize=9.5, leading=13, font="Helvetica-Bold")
    lbl = st("lbl", fontSize=8, leading=11, textColor=grey)
    right = st("right", fontSize=9.5, leading=13, alignment=2)
    right_b = st("rightb", fontSize=9.5, leading=13, alignment=2, font="Helvetica-Bold")
    th = st("th", fontSize=8.5, leading=11, textColor=colors.white, font="Helvetica-Bold")
    th_r = st("thr", fontSize=8.5, leading=11, textColor=colors.white, font="Helvetica-Bold", alignment=2)
    sec = st("sec", fontSize=8.5, leading=11, textColor=teal, font="Helvetica-Bold")

    def kv(rows):
        return [[Paragraph(_p(k), lbl), Paragraph(_p(v), bold)] for k, v in rows]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=14 * mm, bottomMargin=22 * mm, title=f"Receipt {bill.receipt_no}",
                            author=settings.HOSPITAL_NAME)
    story = []

    # ── header band: logo + hospital details | receipt title ──
    logo = Image(LOGO_PATH, 15 * mm, 15 * mm) if os.path.exists(LOGO_PATH) else Spacer(15 * mm, 15 * mm)
    brand = [Paragraph(f"<font color='white' size='17'><b>{_p(settings.HOSPITAL_NAME)}</b></font>", st("hn", leading=21)),
             Paragraph(f"<font color='#9fb3cf'>{_p(settings.HOSPITAL_ADDRESS)}<br/>"
                       f"{_p(settings.HOSPITAL_PHONE)}  |  {_p(settings.HOSPITAL_EMAIL)}</font>", st("ha", fontSize=8, leading=11))]
    title = [Paragraph("<font color='white' size='13'><b>PAYMENT RECEIPT</b></font>", st("rt", alignment=2, leading=17)),
             Paragraph(f"<font color='#9fb3cf'>No. {_p(bill.receipt_no)}<br/>"
                       f"{payment.paid_at.strftime('%d %b %Y, %I:%M %p')}</font>", st("rd", fontSize=8.5, leading=12, alignment=2))]
    head = Table([[logo, brand, title]], colWidths=[20 * mm, 90 * mm, 60 * mm])
    head.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), navy), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 8), ("RIGHTPADDING", (-1, 0), (-1, 0), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, 0), 3, teal),
    ]))
    story += [head, Spacer(1, 8)]

    # ── PAID banner ──
    paid = Table([[Paragraph(f"<font color='#166534'><b>PAID</b>  —  Thank you, your payment of "
                             f"<b>{CURRENCY}{bill.total:,.2f}</b> was received.</font>", st("pd", fontSize=9.5, leading=13))]],
                 colWidths=[W])
    paid.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dcfce7")),
                              ("LINEBEFORE", (0, 0), (0, -1), 3, green),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [paid, Spacer(1, 10)]

    # ── patient | appointment side by side ──
    p_rows = kv([("Name", patient.user.full_name if patient and patient.user else None),
                 ("Patient ID", patient.id if patient else None),
                 ("Phone", patient.user.phone if patient and patient.user else None)])
    a_rows = kv([("Doctor", doctor_label(doctor.user.full_name) if doctor else None),
                 ("Specialization", doctor.specialization if doctor else None),
                 ("Date & time", appt.appointment_date.strftime("%d %b %Y, %I:%M %p") if appt else None),
                 ("Reason", appt.reason if appt else None)])
    def box(title_text, rows):
        t = Table([[Paragraph(title_text, sec), ""]] + rows, colWidths=[27 * mm, 54 * mm])
        t.setStyle(TableStyle([("SPAN", (0, 0), (1, 0)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                               ("LINEBELOW", (0, 0), (-1, 0), 0.6, line), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        return t
    two = Table([[box("PATIENT", p_rows), box("APPOINTMENT", a_rows)]], colWidths=[W / 2, W / 2])
    two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (0, 0), 10)]))
    story += [two, Spacer(1, 12)]

    # ── charges ──
    rows = [[Paragraph("DESCRIPTION", th), Paragraph("QTY", th_r), Paragraph("UNIT PRICE", th_r), Paragraph("AMOUNT", th_r)]]
    for it in (bill.items or []):
        qty, price = it.get("quantity", 1), float(it.get("unit_price", 0))
        rows.append([Paragraph(_p(it.get("description")), body), Paragraph(str(qty), right),
                     Paragraph(f"{CURRENCY}{price:,.2f}", right), Paragraph(f"{CURRENCY}{qty * price:,.2f}", right)])
    n_items = len(rows)
    if bill.discount:
        rows.append(["", "", Paragraph("Discount", right), Paragraph(f"-{CURRENCY}{bill.discount:,.2f}", right)])
    if bill.tax:
        rows.append(["", "", Paragraph(f"Tax ({bill.tax:g}%)", right), Paragraph(f"{CURRENCY}{bill.subtotal * bill.tax / 100:,.2f}", right)])
    rows.append(["", "", Paragraph("TOTAL PAID", right_b), Paragraph(f"{CURRENCY}{bill.total:,.2f}", right_b)])
    charges = Table(rows, colWidths=[85 * mm, 15 * mm, 36 * mm, 34 * mm])
    ts = [("BACKGROUND", (0, 0), (-1, 0), navy), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 1), (-1, n_items - 1), 0.4, line),
          ("BACKGROUND", (2, -1), (-1, -1), soft), ("LINEABOVE", (2, -1), (-1, -1), 1.2, navy)]
    charges.setStyle(TableStyle(ts))
    story += [charges, Spacer(1, 12)]

    # ── payment details ──
    pay = Table([[Paragraph("PAYMENT DETAILS", sec), "", "", ""],
                 [Paragraph("Method", lbl), Paragraph(_p(method_label(payment.method)), bold),
                  Paragraph("Account / card", lbl), Paragraph(_p(payment.account_masked), bold)],
                 [Paragraph("Transaction ref", lbl), Paragraph(_p(payment.reference), bold),
                  Paragraph("Status", lbl), Paragraph("<font color='#166534'>PAID</font>", bold)]],
                colWidths=[30 * mm, 55 * mm, 30 * mm, 55 * mm])
    pay.setStyle(TableStyle([("SPAN", (0, 0), (-1, 0)), ("BOX", (0, 0), (-1, -1), 0.8, line),
                             ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                             ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 4),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [pay, Spacer(1, 14)]

    note = "This is a computer-generated receipt and does not require a signature."
    if DEMO_PAYMENTS:
        note += " <b>Demo payment: no real money was charged.</b>"
    story.append(Paragraph(note, st("note", fontSize=8, leading=11, textColor=grey)))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setStrokeColor(line); canvas.setLineWidth(0.6)
        canvas.line(20 * mm, 17 * mm, A4[0] - 20 * mm, 17 * mm)
        canvas.setFont("Helvetica", 7.5); canvas.setFillColor(grey)
        canvas.drawString(20 * mm, 12.5 * mm, f"{settings.HOSPITAL_NAME}  |  {settings.HOSPITAL_PHONE}  |  {settings.HOSPITAL_EMAIL}")
        canvas.drawRightString(A4[0] - 20 * mm, 12.5 * mm, f"Receipt {bill.receipt_no}  |  Page {d.page}")
        canvas.setFillColor(navy); canvas.setFont("Helvetica-Bold", 8)
        canvas.drawCentredString(A4[0] / 2, 7.5 * mm, "Thank you for choosing us. Wishing you good health.")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
