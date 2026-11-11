from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from app.services.chatbot_service import get_chatbot_response
from app.utils.rate_limit import rate_limit
router = APIRouter(prefix="/api/chatbot", tags=["AI Chatbot"])


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit(30, 60, "chatbot"))])
def chat(request: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    reply = get_chatbot_response(messages)
    return ChatResponse(reply=reply)
