"""
Seed script — creates default admin, departments, and sample doctors.
Run once after first startup:
    python seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, create_tables
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.utils.helpers import hash_password

create_tables()
db = SessionLocal()


def seed():
    # ── Departments ────────────────────────────────────────────
    dept_data = [
        {"name": "General Medicine",      "floor": "1", "phone_extension": "101"},
        {"name": "Cardiology",            "floor": "2", "phone_extension": "201"},
        {"name": "Neurology",             "floor": "2", "phone_extension": "202"},
        {"name": "Orthopedics",           "floor": "3", "phone_extension": "301"},
        {"name": "Pediatrics",            "floor": "1", "phone_extension": "102"},
        {"name": "Gynecology",            "floor": "3", "phone_extension": "302"},
        {"name": "Ophthalmology",         "floor": "4", "phone_extension": "401"},
        {"name": "Dermatology",           "floor": "4", "phone_extension": "402"},
        {"name": "ENT",                   "floor": "4", "phone_extension": "403"},
        {"name": "Emergency Department",  "floor": "G", "phone_extension": "000"},
    ]
    departments = {}
    for d in dept_data:
        existing = db.query(Department).filter(Department.name == d["name"]).first()
        if not existing:
            dept = Department(**d)
            db.add(dept)
            db.flush()
            departments[d["name"]] = dept
            print(f"  ✅ Department: {d['name']}")
        else:
            departments[d["name"]] = existing
    db.commit()

    # ── Admin user ─────────────────────────────────────────────
    if not db.query(User).filter(User.email == "admin@hospital.com").first():
        admin = User(
            full_name="System Administrator",
            email="admin@hospital.com",
            phone="+1234567890",
            hashed_password=hash_password("Admin@1234"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.commit()
        print("  ✅ Admin user: admin@hospital.com / Admin@1234")
    else:
        print("  ⏭️  Admin already exists")

    # ── Sample doctors ─────────────────────────────────────────
    doctors_data = [
        {
            "user": {"full_name": "Dr. Sarah Johnson", "email": "sarah.johnson@hospital.com", "phone": "+1234567891"},
            "profile": {"specialization": "Cardiologist", "qualification": "MD, FACC", "experience_years": 12,
                        "consultation_fee": 150.0, "department": "Cardiology",
                        "bio": "Specialist in interventional cardiology and heart failure management."}
        },
        {
            "user": {"full_name": "Dr. James Williams", "email": "james.williams@hospital.com", "phone": "+1234567892"},
            "profile": {"specialization": "Neurologist", "qualification": "MD, PhD", "experience_years": 15,
                        "consultation_fee": 175.0, "department": "Neurology",
                        "bio": "Expert in stroke management and neurodegenerative disorders."}
        },
        {
            "user": {"full_name": "Dr. Emily Chen", "email": "emily.chen@hospital.com", "phone": "+1234567893"},
            "profile": {"specialization": "Pediatrician", "qualification": "MD, FAAP", "experience_years": 8,
                        "consultation_fee": 120.0, "department": "Pediatrics",
                        "bio": "Dedicated to comprehensive child health and preventive care."}
        },
        {
            "user": {"full_name": "Dr. Michael Brown", "email": "michael.brown@hospital.com", "phone": "+1234567894"},
            "profile": {"specialization": "Orthopedic Surgeon", "qualification": "MD, FAAOS", "experience_years": 20,
                        "consultation_fee": 200.0, "department": "Orthopedics",
                        "bio": "Expert in joint replacement and sports injury management."}
        },
        {
            "user": {"full_name": "Dr. Aisha Patel", "email": "aisha.patel@hospital.com", "phone": "+1234567895"},
            "profile": {"specialization": "General Physician", "qualification": "MBBS, MD", "experience_years": 6,
                        "consultation_fee": 80.0, "department": "General Medicine",
                        "bio": "Primary care physician focused on preventive healthcare."}
        },
    ]

    for item in doctors_data:
        if db.query(User).filter(User.email == item["user"]["email"]).first():
            print(f"  ⏭️  Doctor {item['user']['full_name']} already exists")
            continue
        user = User(
            full_name=item["user"]["full_name"],
            email=item["user"]["email"],
            phone=item["user"]["phone"],
            hashed_password=hash_password("Doctor@1234"),
            role=UserRole.DOCTOR,
            is_active=True
        )
        db.add(user)
        db.flush()

        dept = departments.get(item["profile"]["department"])
        prof = item["profile"]
        doctor = Doctor(
            user_id=user.id,
            department_id=dept.id if dept else None,
            specialization=prof["specialization"],
            qualification=prof["qualification"],
            experience_years=prof["experience_years"],
            consultation_fee=prof["consultation_fee"],
            bio=prof["bio"],
            available_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            available_from="09:00",
            available_to="17:00"
        )
        db.add(doctor)
        db.commit()
        print(f"  ✅ Doctor: {item['user']['full_name']} ({prof['specialization']})")

    # ── Sample patient ─────────────────────────────────────────
    if not db.query(User).filter(User.email == "patient@hospital.com").first():
        pat_user = User(
            full_name="John Patient",
            email="patient@hospital.com",
            phone="+1234567899",
            hashed_password=hash_password("Patient@1234"),
            role=UserRole.PATIENT,
            is_active=True
        )
        db.add(pat_user)
        db.flush()
        patient = Patient(user_id=pat_user.id, gender="Male", blood_group="O+")
        db.add(patient)
        db.commit()
        print("  ✅ Patient: patient@hospital.com / Patient@1234")
    else:
        print("  ⏭️  Sample patient already exists")

    # ── Receptionist ───────────────────────────────────────────
    if not db.query(User).filter(User.email == "reception@hospital.com").first():
        rec = User(
            full_name="Front Desk Reception",
            email="reception@hospital.com",
            phone="+1234567898",
            hashed_password=hash_password("Reception@1234"),
            role=UserRole.RECEPTIONIST,
            is_active=True
        )
        db.add(rec)
        db.commit()
        print("  ✅ Receptionist: reception@hospital.com / Reception@1234")

    print("\n✅ Seed complete!")
    print("\n📋 Default Login Credentials:")
    print("   Admin:        admin@hospital.com       / Admin@1234")
    print("   Doctor:       sarah.johnson@hospital.com / Doctor@1234")
    print("   Receptionist: reception@hospital.com   / Reception@1234")
    print("   Patient:      patient@hospital.com     / Patient@1234")
    print("\n🚀 Start the app: python run.py")
    print("🌐 Visit: http://localhost:8000")
    print("📖 API Docs: http://localhost:8000/api/docs")


if __name__ == "__main__":
    print("\n🌱 Seeding database...\n")
    seed()
    db.close()
