from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.agent_log import AgentCallLog, CallbackRequest
from app.services.agent_service import run_agent, get_session
from app.utils.dependencies import require_admin
from app.utils.rate_limit import rate_limit

router = APIRouter(prefix="/api/agent", tags=["AI Helpline Agent"])


class AgentRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=1000)


class AgentReply(BaseModel):
    session_id: str
    reply: str


@router.post("/chat", response_model=AgentReply, dependencies=[Depends(rate_limit(30, 60, "agent"))])
def agent_chat(req: AgentRequest, db: Session = Depends(get_db)):
    """Text/browser-voice entry point."""
    session_id, reply = run_agent(db, req.session_id, req.message, channel="web")
    return AgentReply(session_id=session_id, reply=reply)


# ───────── Real phone calls (Twilio Voice webhook) ─────────
def _twiml(text: str) -> Response:
    xml = ('<?xml version="1.0" encoding="UTF-8"?><Response>'
           '<Gather input="speech" action="/api/agent/twilio/voice" method="POST" '
           'speechTimeout="auto" language="en-US">'
           f'<Say>{escape(text)}</Say></Gather>'
           '<Say>I did not hear anything. Goodbye.</Say><Hangup/></Response>')
    return Response(content=xml, media_type="application/xml")


@router.post("/twilio/voice")
def twilio_voice(CallSid: str = Form(...), SpeechResult: str | None = Form(None),
                 db: Session = Depends(get_db)):
    if not SpeechResult:  # call just started
        get_session(CallSid, allow_custom_id=True, channel="phone")
        return _twiml(f"Hello, thank you for calling {settings.HOSPITAL_NAME}. "
                      "I am the virtual assistant. How can I help you today?")
    _, reply = run_agent(db, CallSid, SpeechResult, allow_custom_id=True, channel="phone")
    return _twiml(reply)


# ───────── Admin: call log + callback requests ─────────
@router.get("/calls")
def list_calls(limit: int = 100, db: Session = Depends(get_db), _=Depends(require_admin)):
    rows = db.query(AgentCallLog).order_by(AgentCallLog.id.desc()).limit(min(max(limit, 1), 500)).all()
    return [{
        "id": c.id, "channel": c.channel, "outcome": c.outcome,
        "patient": c.patient.user.full_name if c.patient and c.patient.user else None,
        "turns": (c.transcript or "").count("Caller:"),
        "started_at": c.started_at, "updated_at": c.updated_at,
    } for c in rows]


@router.get("/calls/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    c = db.query(AgentCallLog).filter(AgentCallLog.id == call_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Call not found")
    return {"id": c.id, "channel": c.channel, "outcome": c.outcome, "transcript": c.transcript,
            "patient": c.patient.user.full_name if c.patient and c.patient.user else None,
            "started_at": c.started_at}


@router.get("/callbacks")
def list_callbacks(status: str | None = None, db: Session = Depends(get_db), _=Depends(require_admin)):
    q = db.query(CallbackRequest)
    if status:
        q = q.filter(CallbackRequest.status == status)
    return [{"id": r.id, "name": r.name, "phone": r.phone, "reason": r.reason,
             "status": r.status, "created_at": r.created_at, "call_log_id": r.call_log_id}
            for r in q.order_by(CallbackRequest.id.desc()).limit(200).all()]


@router.put("/callbacks/{cb_id}/done")
def mark_callback_done(cb_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    r = db.query(CallbackRequest).filter(CallbackRequest.id == cb_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Callback request not found")
    r.status = "done"
    db.commit()
    return {"detail": "Marked as done."}