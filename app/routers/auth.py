from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.user import UserCreate, Token, LoginRequest, UserOut
from app.schemas.patient import PatientRegister, PatientBase
from app.services.auth_service import register_user, login_user
from app.utils.dependencies import get_current_user, require_admin
from app.utils.rate_limit import (rate_limit, client_ip, login_locked_for,
                                  record_login_failure, clear_login_failures)
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _guarded_login(login_data: LoginRequest, request: Request, db: Session, admin_only: bool = False):
    """Login with brute-force protection: 5 wrong passwords => locked for 15 minutes."""
    ip = client_ip(request)
    wait = login_locked_for(login_data.email, ip)
    if wait:
        raise HTTPException(status_code=429,
                            detail=f"Too many failed attempts. Try again in {wait // 60 + 1} minutes.")
    try:
        result = login_user(db, login_data)
        if admin_only and result.user.role != UserRole.ADMIN:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
    except HTTPException as e:
        if e.status_code == 401:
            record_login_failure(login_data.email, ip)
        raise
    clear_login_failures(login_data.email, ip)
    return result


@router.post("/register", response_model=UserOut, status_code=201,
             dependencies=[Depends(rate_limit(10, 3600, "register"))])
def register(data: PatientRegister, db: Session = Depends(get_db)):
    # Public signup: always a patient, saved in users + patients
    patient_fields = data.model_dump(
        include=set(PatientBase.model_fields.keys()), exclude_none=True
    )
    user_data = UserCreate(
        full_name=data.full_name, email=data.email, phone=data.phone,
        password=data.password, role=UserRole.PATIENT
    )
    return register_user(db, user_data, patient_fields)


@router.post("/staff", response_model=UserOut, status_code=201)
def create_staff(user_data: UserCreate, db: Session = Depends(get_db),
                 _: User = Depends(require_admin)):
    # Only a logged-in admin can create admin/doctor/receptionist accounts
    return register_user(db, user_data)


@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit(30, 60, "login"))])
def login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return _guarded_login(login_data, request, db)


@router.post("/admin-login", response_model=Token, dependencies=[Depends(rate_limit(30, 60, "login"))])
def admin_login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return _guarded_login(login_data, request, db, admin_only=True)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user