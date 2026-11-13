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
    """Tiny migration: adds columns introduced by newer versions to tables that already exist
    (create_all never alters existing tables)."""
    from sqlalchemy import inspect, text
    new_columns = {
        "payments": [("account_masked", "VARCHAR(40)")],
        "appointments": [("booked_for_name", "VARCHAR(100)"), ("booked_for_relation", "VARCHAR(30)"),
                         ("booked_for_age", "INTEGER"), ("booked_for_gender", "VARCHAR(10)"),
                         ("booked_for_phone", "VARCHAR(20)"), ("source", "VARCHAR(20)"), ("token_no", "INTEGER")],
        "prescriptions": [("appointment_id", "INTEGER")],
    }
    insp = inspect(engine)
    tables = insp.get_table_names()
    for table, cols in new_columns.items():
        if table not in tables:
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        for name, ddl in cols:
            if name not in have:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
