"""Hospital-style prescription slip (PDF) with the hospital logo, doctor and patient details."""
import os
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import settings
from app.models.prescription import Prescription
from app.services.billing_service import LOGO_PATH, _p, doctor_label


def _age(dob):
    if not dob:
        return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def build_prescription_pdf(rx: Prescription) -> bytes:
    doctor, patient = rx.doctor, rx.patient
    d_user = doctor.user if doctor else None
    p_user = patient.user if patient else None

    navy, teal, grey = colors.HexColor("#0a1628"), colors.HexColor("#0d9488"), colors.HexColor("#64748b")
    line, soft = colors.HexColor("#e2e8f0"), colors.HexColor("#f1f5f9")
    W = 170 * mm
    ss = getSampleStyleSheet()

    def st(name, **kw):
        return ParagraphStyle(name, parent=ss["Normal"], fontName=kw.pop("font", "Helvetica"), **kw)
    body = st("b", fontSize=9.5, leading=13)
    bold = st("bd", fontSize=9.5, leading=13, font="Helvetica-Bold")
    lbl = st("l", fontSize=8, leading=11, textColor=grey)
    th = st("th", fontSize=8.5, leading=11, textColor=colors.white, font="Helvetica-Bold")
    sec = st("s", fontSize=8.5, leading=11, textColor=teal, font="Helvetica-Bold")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=14 * mm,
                            bottomMargin=22 * mm, title=f"Prescription RX-{rx.id:05d}", author=settings.HOSPITAL_NAME)
    story = []

    # ── letterhead: logo + hospital | doctor ──
    logo = Image(LOGO_PATH, 15 * mm, 15 * mm) if os.path.exists(LOGO_PATH) else Spacer(15 * mm, 15 * mm)
    brand = [Paragraph(f"<font color='white' size='17'><b>{_p(settings.HOSPITAL_NAME)}</b></font>", st("hn", leading=21)),
             Paragraph(f"<font color='#9fb3cf'>{_p(settings.HOSPITAL_ADDRESS)}<br/>"
                       f"{_p(settings.HOSPITAL_PHONE)}  |  {_p(settings.HOSPITAL_EMAIL)}</font>", st("ha", fontSize=8, leading=11))]
    title = [Paragraph("<font color='white' size='13'><b>PRESCRIPTION</b></font>", st("rt", alignment=2, leading=17)),
             Paragraph(f"<font color='#9fb3cf'>Rx No. RX-{rx.id:05d}<br/>{rx.created_at.strftime('%d %b %Y, %I:%M %p')}</font>",
                       st("rd", fontSize=8.5, leading=12, alignment=2))]
    head = Table([[logo, brand, title]], colWidths=[20 * mm, 90 * mm, 60 * mm])
    head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), navy), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("LEFTPADDING", (0, 0), (0, 0), 8), ("RIGHTPADDING", (-1, 0), (-1, 0), 10),
                              ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                              ("LINEBELOW", (0, 0), (-1, 0), 3, teal)]))
    story += [head, Spacer(1, 8)]

    # ── doctor strip ──
    dname = doctor_label(d_user.full_name) if d_user else "—"
    sub_line = " · ".join(x for x in [doctor.qualification if doctor else None, doctor.specialization if doctor else None] if x)
    reg = f"Reg. No: {doctor.license_number}" if doctor and doctor.license_number else ""
    strip = Table([[Paragraph(f"<font size='13' color='#0a1628'><b>{_p(dname)}</b></font><br/>"
                              f"<font size='9' color='#475569'>{_p(sub_line)}</font>", st("dn", leading=16)),
                    Paragraph(f"<font size='8.5' color='#475569'>{_p(doctor.department.name if doctor and doctor.department else '')}<br/>"
                              f"{_p(reg) if reg else ''}</font>", st("dr", alignment=2, leading=12))]],
                  colWidths=[110 * mm, 60 * mm])
    strip.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), soft), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                               ("RIGHTPADDING", (-1, 0), (-1, 0), 10), ("TOPPADDING", (0, 0), (-1, -1), 7),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [strip, Spacer(1, 8)]

    # ── patient details ──
    age = _age(patient.date_of_birth) if patient else None
    cells = [("Patient", p_user.full_name if p_user else None), ("Patient ID", patient.id if patient else None),
             ("Age / Gender", " / ".join(str(x) for x in [f"{age} yrs" if age is not None else None, patient.gender if patient else None] if x) or None),
             ("Blood group", patient.blood_group if patient else None),
             ("Phone", p_user.phone if p_user else None), ("Date", rx.created_at.strftime("%d %b %Y"))]
    rows = [[Paragraph(_p(cells[i][0]), lbl), Paragraph(_p(cells[i][1]), bold),
             Paragraph(_p(cells[i + 1][0]), lbl), Paragraph(_p(cells[i + 1][1]), bold)] for i in range(0, 6, 2)]
    pt = Table(rows, colWidths=[24 * mm, 61 * mm, 24 * mm, 61 * mm])
    pt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, line), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
    story.append(pt)

    if patient and patient.allergies:
        al = Table([[Paragraph(f"<font color='#991b1b'><b>ALLERGIES:</b> {_p(patient.allergies)}</font>", st("al", fontSize=9, leading=12))]], colWidths=[W])
        al.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fee2e2")), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [Spacer(1, 4), al]
    story.append(Spacer(1, 10))

    # ── diagnosis ──
    if rx.diagnosis:
        story += [Paragraph("DIAGNOSIS", sec), Spacer(1, 2), Paragraph(_p(rx.diagnosis), body), Spacer(1, 10)]

    # ── Rx medicines ──
    story.append(Paragraph("<font size='22' color='#0d9488'><b>Rx</b></font>", st("rx", leading=26)))
    story.append(Spacer(1, 3))
    meds = rx.medicines or []
    mrows = [[Paragraph(h, th) for h in ("#", "MEDICINE", "DOSAGE", "FREQUENCY", "DURATION")]]
    for i, m in enumerate(meds, 1):
        mrows.append([Paragraph(str(i), body), Paragraph(f"<b>{_p(m.get('name'))}</b>", body), Paragraph(_p(m.get("dosage")), body),
                      Paragraph(_p(m.get("frequency")), body), Paragraph(_p(m.get("duration")), body)])
    if not meds:
        mrows.append(["", Paragraph("No medicines prescribed.", body), "", "", ""])
    mt = Table(mrows, colWidths=[10 * mm, 66 * mm, 32 * mm, 36 * mm, 26 * mm], repeatRows=1)
    mt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), navy), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("LINEBELOW", (0, 1), (-1, -1), 0.4, line), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")])]))
    story.append(mt)

    if rx.instructions:
        story += [Spacer(1, 12), Paragraph("ADVICE / INSTRUCTIONS", sec), Spacer(1, 2), Paragraph(_p(rx.instructions).replace("\n", "<br/>"), body)]
    if rx.follow_up_date:
        story += [Spacer(1, 8), Paragraph(f"<b>Follow-up:</b> {rx.follow_up_date.strftime('%d %b %Y')}", body)]

    # ── signature ──
    sig = Table([["", Paragraph(f"<b>{_p(dname)}</b><br/><font size='8' color='#64748b'>{_p(sub_line)}</font>", st("sg", alignment=1, leading=12))]],
                colWidths=[110 * mm, 60 * mm])
    sig.setStyle(TableStyle([("LINEABOVE", (1, 0), (1, 0), 0.8, navy), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    story += [Spacer(1, 40), sig, Spacer(1, 12),
              Paragraph("This prescription is valid only with the doctor's signature or stamp. Do not take medicines beyond the prescribed course.",
                        st("nt", fontSize=7.5, leading=10, textColor=grey))]

    def footer(c, d):
        c.saveState(); c.setStrokeColor(line); c.setLineWidth(0.6); c.line(20 * mm, 17 * mm, A4[0] - 20 * mm, 17 * mm)
        c.setFont("Helvetica", 7.5); c.setFillColor(grey)
        c.drawString(20 * mm, 12.5 * mm, f"{settings.HOSPITAL_NAME}  |  {settings.HOSPITAL_PHONE}  |  {settings.HOSPITAL_EMAIL}")
        c.drawRightString(A4[0] - 20 * mm, 12.5 * mm, f"RX-{rx.id:05d}  |  Page {d.page}")
        c.setFillColor(navy); c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(A4[0] / 2, 7.5 * mm, "Get well soon.")
        c.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()