from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AgentCallLog(Base):
    """One row per helpline conversation (browser or phone)."""
    __tablename__ = "agent_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    channel = Column(String(20), default="web")            # web | phone
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    outcome = Column(String(40), default="info")           # info | booked | cancelled | callback_requested | verification_failed | locked
    transcript = Column(Text, default="")
    started_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    patient = relationship("Patient")


class CallbackRequest(Base):
    """'Please call me back' requests created when the agent hands off to a human."""
    __tablename__ = "callback_requests"

    id = Column(Integer, primary_key=True, index=True)
    call_log_id = Column(Integer, ForeignKey("agent_call_logs.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(30), nullable=False)
    reason = Column(Text)
    status = Column(String(20), default="open")            # open | done
    created_at = Column(DateTime, server_default=func.now())