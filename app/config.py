from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "AI Hospital Management System"
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DATABASE_URL: str = "mysql+pymysql://root:@localhost:3306/hospital_db"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    HOSPITAL_NAME: str = "City General Hospital"
    HOSPITAL_PHONE: str = "+1-800-HOSPITAL"
    HOSPITAL_EMAIL: str = "info@cityhospital.com"
    HOSPITAL_ADDRESS: str = "123 Medical Drive, Health City"

    class Config:
        env_file = ".env"


settings = Settings()
