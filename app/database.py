from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True,  # avoids "MySQL server has gone away" on idle connections
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from app.models import user, doctor, patient, appointment, department, prescription, billing, agent_log, reminder
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns():
    """Tiny migration: databases created before the payment-number update lack payments.account_masked."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "payments" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("payments")}
        if "account_masked" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE payments ADD COLUMN account_masked VARCHAR(40)"))
