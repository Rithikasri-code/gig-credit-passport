from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import User
from app.services.scoring_service import recompute_and_persist_score
from app.api.deps import get_current_user_id

router = APIRouter()


class UserCreate(BaseModel):
    phone_number: str
    full_name: str
    preferred_language: str = "en"


class UserResponse(BaseModel):
    id: str
    phone_number: str
    full_name: str
    preferred_language: str
    itr_filed: bool
    model_config = ConfigDict(from_attributes=True)


class ITRStatusUpdate(BaseModel):
    itr_filed: bool


@router.post("", response_model=UserResponse)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Minimal signup for now — no OTP/auth yet (that's next). Phone number
    is unique, so re-registering the same number returns a clear error
    rather than a duplicate.
    """
    existing = await db.execute(select(User).where(User.phone_number == payload.phone_number))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "A user with this phone number already exists.")

    user = User(
        phone_number=payload.phone_number,
        full_name=payload.full_name,
        preferred_language=payload.preferred_language,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(User).where(User.id == current_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    return user


@router.patch("/me/itr-status", response_model=UserResponse)
async def update_itr_status(
    payload: ITRStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Self-declared, not independently verified yet — same honesty caveat as
    self-reported OCR earnings. A real ITR-verification integration (e.g.
    via the Income Tax e-filing portal or an Account Aggregator FI type
    that covers tax data) would be the upgrade path here.
    """
    result = await db.execute(select(User).where(User.id == current_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    user.itr_filed = payload.itr_filed
    await db.commit()
    await db.refresh(user)

    try:
        await recompute_and_persist_score(db, current_user_id, trigger="itr_status_change")
    except Exception:
        pass  # status update itself succeeded; scoring can be retried manually

    return user
