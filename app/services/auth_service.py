from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.user import UserCreate, LoginRequest, Token
from app.utils.helpers import hash_password, verify_password, create_access_token


def register_user(db: Session, user_data: UserCreate, patient_data: dict | None = None) -> User:
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        phone=user_data.phone,
        role=user_data.role,
        hashed_password=hash_password(user_data.password)
    )
    db.add(user)
    db.flush()  # gets user.id without committing yet

    # Patients also get a row in the patients table
    if user.role in (UserRole.PATIENT, "patient"):
        db.add(Patient(user_id=user.id, **(patient_data or {})))

    db.commit()  # users + patients saved together, or neither
    db.refresh(user)
    return user


def login_user(db: Session, login_data: LoginRequest) -> Token:
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return Token(access_token=token, token_type="bearer", user=user)