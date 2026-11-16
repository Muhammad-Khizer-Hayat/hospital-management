"""Signed token codes + QR images.

Every appointment has a token number (1, 2, 3 ... per doctor per day). The QR printed on the token
opens /t/<code>, a public page where the patient follows the queue live on their phone.
<code> = appointment id + a signature made with SECRET_KEY, so nobody can guess other people's pages.
"""
import hashlib
import hmac
from typing import Optional
from app.config import settings


def _sig(appt_id: int) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"token:{appt_id}".encode(), hashlib.sha256).hexdigest()[:12]


def make_code(appt_id: int) -> str:
    return f"{appt_id}-{_sig(appt_id)}"


def parse_code(code: str) -> Optional[int]:
    try:
        raw_id, sig = (code or "").split("-", 1)
        appt_id = int(raw_id)
    except ValueError:
        return None
    return appt_id if hmac.compare_digest(sig, _sig(appt_id)) else None


def qr_svg(url: str, size: int = 400) -> str:
    """A crisp vector QR code (reportlab is already used for PDFs, nothing new to install)."""
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.renderSVG import drawToString
    widget = QrCodeWidget(url, barLevel="M")
    x0, y0, x1, y1 = widget.getBounds()
    w, h = x1 - x0, y1 - y0
    drawing = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    drawing.add(widget)
    return drawToString(drawing)
