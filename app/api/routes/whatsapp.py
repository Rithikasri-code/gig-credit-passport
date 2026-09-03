"""
WhatsApp-style webhook.

In production, this would be the endpoint WhatsApp Business API / Twilio
calls when a message arrives, and the reply would be sent back via their
API rather than returned in the HTTP response. Since there's no real
provider wired up yet, this endpoint IS the simulator: POST a phone number
and message, get the reply text directly — same conversation logic that
would run in production, just without the actual message-delivery hop.

No auth on this route by design — a real WhatsApp webhook is authenticated
by the provider (signature verification), not a user-held JWT, since the
"user" here is identified by their phone number in the message itself.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.db import session as db_session
from app.services import whatsapp_service

router = APIRouter()


class IncomingMessage(BaseModel):
    from_number: str
    body: str


class WhatsAppReply(BaseModel):
    reply: str


@router.post("/webhook", response_model=WhatsAppReply)
async def whatsapp_webhook(payload: IncomingMessage):
    # Accessed via the module (not imported by value) so this always uses
    # whatever session-maker is currently active — matters for tests,
    # which swap in a differently-bound engine after this module is first
    # imported (see tests/conftest.py for why).
    async with db_session.AsyncSessionLocal() as db:
        reply = await whatsapp_service.handle_message(db, payload.from_number, payload.body)
    return WhatsAppReply(reply=reply)
