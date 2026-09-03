from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import Passport
from app.services import passport_service
from app.api.deps import get_current_user_id, require_self

router = APIRouter()


class IssuePassportRequest(BaseModel):
    score_id: str


@router.post("/issue")
async def issue(
    req: IssuePassportRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    try:
        passport = await passport_service.issue_passport(db, current_user_id, req.score_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "id": passport.id,
        "score_value": passport.score_value_snapshot,
        "issued_at": passport.issued_at.isoformat(),
        "expires_at": passport.expires_at.isoformat(),
    }


@router.get("/mine")
async def list_mine(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(Passport).where(Passport.user_id == current_user_id).order_by(Passport.issued_at.desc())
    )
    passports = result.scalars().all()
    return [
        {
            "id": p.id,
            "score_value": p.score_value_snapshot,
            "issued_at": p.issued_at.isoformat(),
            "expires_at": p.expires_at.isoformat(),
            "revoked": p.revoked,
        }
        for p in passports
    ]


@router.post("/{passport_id}/revoke")
async def revoke(
    passport_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(Passport).where(Passport.id == passport_id))
    passport = result.scalar_one_or_none()
    if not passport:
        raise HTTPException(404, "Passport not found")
    require_self(passport.user_id, current_user_id)

    passport = await passport_service.revoke_passport(db, passport)
    return {"id": passport.id, "revoked": passport.revoked}


@router.get("/verify/{passport_id}")
async def verify(passport_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Public, no auth required — this is the whole point. A lender/landlord
    hits this with the ID from a shared link and gets a verified answer
    without ever needing an account or touching the worker's raw data.

    The requester's IP is logged (see PassportVerificationLog) precisely
    because this endpoint has no other form of attribution — it's the
    only way to notice abuse of a deliberately public endpoint.
    """
    requester_ip = request.client.host if request.client else None
    return await passport_service.verify_passport(db, passport_id, requester_ip=requester_ip)
