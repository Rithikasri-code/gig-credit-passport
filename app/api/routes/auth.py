from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import auth_service

router = APIRouter()


class OTPRequestPayload(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)


class OTPVerifyPayload(BaseModel):
    phone_number: str
    otp: str
    full_name: str | None = None  # used only if this is a first-time signup


@router.post("/otp/request")
async def request_otp(payload: OTPRequestPayload, db: AsyncSession = Depends(get_db)):
    try:
        return await auth_service.request_otp(db, payload.phone_number)
    except auth_service.RateLimitExceeded as e:
        raise HTTPException(429, e.message)


@router.post("/otp/verify")
async def verify_otp(payload: OTPVerifyPayload, db: AsyncSession = Depends(get_db)):
    result = await auth_service.verify_otp(db, payload.phone_number, payload.otp, payload.full_name)
    if not result["success"]:
        raise HTTPException(400, result["error"])
    return result
