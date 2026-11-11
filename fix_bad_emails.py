"""Find and remove broken doctor accounts (invalid email) that crash the doctors list.
Run from the project folder:   python fix_bad_emails.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from email_validator import validate_email, EmailNotValidError
from app.database import SessionLocal, create_tables
from app.models.user import User, UserRole
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.prescription import Prescription

create_tables()
db = SessionLocal()


def is_valid(email: str) -> bool:
    try:
        validate_email(email or "", check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


bad = [u for u in db.query(User).all() if not is_valid(u.email)]
if not bad:
    print("✅ No accounts with invalid emails found.")
    sys.exit(0)

print("Accounts with invalid emails:")
for u in bad:
    print(f"  id={u.id}  role={u.role.value}  name={u.full_name!r}  email={u.email!r}")

removable, skipped = [], []
for u in bad:
    doc = db.query(Doctor).filter(Doctor.user_id == u.id).first()
    has_history = doc and (
        db.query(Appointment).filter(Appointment.doctor_id == doc.id).first()
        or db.query(Prescription).filter(Prescription.doctor_id == doc.id).first())
    if u.role == UserRole.DOCTOR and not has_history:
        removable.append((u, doc))
    else:
        skipped.append(u)

if skipped:
    print("\n⚠️  Not touched (not an empty doctor account):", [u.id for u in skipped])
if not removable:
    sys.exit(0)

answer = input(f"\nDelete {len(removable)} broken doctor account(s)? Type yes to confirm: ")
if answer.strip().lower() != "yes":
    print("Cancelled. Nothing was deleted.")
    sys.exit(0)

for u, doc in removable:
    if doc:
        db.delete(doc)
        db.flush()
    db.delete(u)
db.commit()
print(f"✅ Deleted {len(removable)} account(s). The doctors list works again.")