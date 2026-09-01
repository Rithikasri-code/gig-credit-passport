"""
Core schema.

Design notes:
- We NEVER store raw AA credentials or bank login info — only what the AA
  framework hands back (account references, transaction data) after
  consent-based fetch.
- ConsentArtifact tracks exactly what a worker agreed to share, with whom,
  and for how long — this is the audit trail the DPDP Act requires.
- Score is versioned and always linked to a ScoreExplanation so no score
  is ever a black box.
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum, Numeric, JSON, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class ConsentStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    phone_number: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    itr_filed: Mapped[bool] = mapped_column(Boolean, default=False)  # self-declared, not independently verified yet
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    consents: Mapped[list["ConsentArtifact"]] = relationship(back_populates="user")
    accounts: Mapped[list["FinancialAccount"]] = relationship(back_populates="user")
    scores: Mapped[list["Score"]] = relationship(back_populates="user")


class ConsentArtifact(Base):
    """
    Mirrors an Account Aggregator consent artifact. One row per consent
    request — this is what powers the 'who accessed what, when, why' log
    the user sees in their app.
    """
    __tablename__ = "consent_artifacts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    aa_consent_handle: Mapped[str] = mapped_column(String(255))  # ID returned by the AA
    purpose: Mapped[str] = mapped_column(String(255))  # e.g. "Credit passport scoring"
    fi_types: Mapped[list] = mapped_column(JSON)  # e.g. ["DEPOSIT", "TERM_DEPOSIT"]
    status: Mapped[ConsentStatus] = mapped_column(Enum(ConsentStatus), default=ConsentStatus.PENDING)
    data_life_days: Mapped[int] = mapped_column(default=90)  # how long fetched data can be retained
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="consents")


class FinancialAccount(Base):
    """A bank/UPI-linked account discovered via the AA, not raw credentials."""
    __tablename__ = "financial_accounts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    consent_id: Mapped[str] = mapped_column(ForeignKey("consent_artifacts.id"))
    fip_id: Mapped[str] = mapped_column(String(120))  # Financial Info Provider (the bank) ID
    masked_account_number: Mapped[str] = mapped_column(String(50))
    account_type: Mapped[str] = mapped_column(String(50))  # SAVINGS, CURRENT, etc.
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    account_id: Mapped[str] = mapped_column(ForeignKey("financial_accounts.id"))
    txn_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    txn_type: Mapped[str] = mapped_column(String(10))  # CREDIT | DEBIT
    narration: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(50), default="UNCATEGORIZED")  # e.g. GIG_INCOME, RENT, UPI_TRANSFER
    source_platform: Mapped[str | None] = mapped_column(String(50), nullable=True)  # SWIGGY, UBER, etc. if inferable

    account: Mapped["FinancialAccount"] = relationship(back_populates="transactions")


class SelfReportedEarning(Base):
    """
    Extracted from a user-uploaded screenshot/PDF (Swiggy/Uber earnings
    dashboard, statement, etc.) via OCR.

    IMPORTANT: this is deliberately a separate table from Transaction.
    Data here is self-reported and unverified — it must never be silently
    merged with AA-verified transaction data. The scoring model treats
    this as a distinct, lower-trust-weighted feature group, and the UI
    must always label it "self-reported, not verified" wherever shown.
    """
    __tablename__ = "self_reported_earnings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    source_platform: Mapped[str] = mapped_column(String(50))  # SWIGGY, UBER, etc.
    document_type: Mapped[str] = mapped_column(String(30))  # SCREENSHOT | PDF_STATEMENT
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_earnings: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    trip_or_order_count: Mapped[int | None] = mapped_column(nullable=True)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    raw_ocr_text: Mapped[str] = mapped_column(String(5000), default="")
    extraction_confidence: Mapped[float] = mapped_column(default=0.0)  # 0-1, how much we trust the parse
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # always False unless cross-checked vs AA data
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship()


class OTPChallenge(Base):
    """
    Short-lived OTP for phone-based auth (no email needed — fits gig
    workers' actual usage pattern). Only the hash is stored, never the
    plaintext OTP, and it expires quickly.
    """
    __tablename__ = "otp_challenges"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    phone_number: Mapped[str] = mapped_column(String(15), index=True)
    otp_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Score(Base):
    """
    A single, versioned, explainable score computation for a user.

    Hash-chained for tamper-evidence: each score's `record_hash` is computed
    over its own content plus the previous score's hash (like a mini
    blockchain, no actual chain needed). This means nobody — including us —
    can quietly edit a past score without breaking every hash after it,
    which is verifiable by recomputing the chain from scratch.
    """
    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    model_version: Mapped[str] = mapped_column(String(20))
    score_value: Mapped[int] = mapped_column()  # e.g. 300-900 scale, CIBIL-like
    features_used: Mapped[dict] = mapped_column(JSON)  # raw feature values at scoring time
    reason_codes: Mapped[list] = mapped_column(JSON)  # ["Income consistency: strong (+40)", ...]
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prev_hash: Mapped[str] = mapped_column(String(64), default="")  # empty string for the first score in a chain
    record_hash: Mapped[str] = mapped_column(String(64))  # sha256(prev_hash + canonical content)

    user: Mapped["User"] = relationship(back_populates="scores")


class ScoreChangeEvent(Base):
    """
    A log of every time a score changed, and what triggered the
    recomputation — the backbone of "your score just moved" notifications.
    Not itself a push notification (no SMS/push gateway wired up), but the
    durable record a notification system would read from, and what makes
    the product feel like it's watching your finances rather than waiting
    for you to click a button.
    """
    __tablename__ = "score_change_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    previous_score: Mapped[int | None] = mapped_column(nullable=True)  # None if this is the worker's first-ever score
    new_score: Mapped[int] = mapped_column()
    delta: Mapped[int | None] = mapped_column(nullable=True)  # None when previous_score is None
    trigger: Mapped[str] = mapped_column(String(30))  # "manual" | "auto_sync" | "itr_status_change"
    seen: Mapped[bool] = mapped_column(Boolean, default=False)  # has the worker viewed this in the app yet
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped["User"] = relationship()


class PassportVerificationLog(Base):
    """
    Every time someone (anyone — this endpoint is deliberately public)
    checks a passport's validity. This is what makes it possible to
    detect abuse of a public, no-auth endpoint — e.g. one IP scraping
    every passport ID it can guess — which nothing else here would catch,
    since by design this endpoint doesn't require login or attribute the
    request to a known user.
    """
    __tablename__ = "passport_verification_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    passport_id: Mapped[str] = mapped_column(String(64), index=True)  # not a FK: a forged ID is still worth logging
    requester_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    was_valid: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)  # why it failed, if it did
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Passport(Base):
    """
    A shareable, verifiable credential a worker can hand to any lender,
    landlord, or platform — the technical realization of "you own your
    data", not just a UI dashboard.

    Deliberately does NOT expose the full feature breakdown to whoever
    holds the link — only the score band and a minimal trust signal. Full
    detail stays behind login. Verification (GET /passport/verify/{id})
    is public and requires no auth, so any third party can check validity
    without ever touching the worker's account.
    """
    __tablename__ = "passports"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    score_id: Mapped[str] = mapped_column(ForeignKey("scores.id"))
    score_value_snapshot: Mapped[int] = mapped_column()  # frozen at issue time, doesn't silently update
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signature: Mapped[str] = mapped_column(String(512))  # HMAC over the passport's content, prevents forged links

    user: Mapped["User"] = relationship()
    score: Mapped["Score"] = relationship()
