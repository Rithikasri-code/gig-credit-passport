"""
Accounts service: once a consent is ACTIVE, this pulls the actual financial
data and persists it as FinancialAccount + Transaction rows.
Also does lightweight categorization (is this a gig payout? which platform?)
so the scoring layer doesn't have to re-parse narrations every time.
"""
import re
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import ConsentArtifact, ConsentStatus, FinancialAccount, Transaction
from app.services.aa_client import get_aa_client

GIG_PLATFORM_PATTERNS = {
    "SWIGGY": r"swiggy",
    "ZOMATO": r"zomato",
    "UBER": r"uber",
    "OLA": r"\bola\b",
    "URBAN_COMPANY": r"urban\s*company|urbanclap",
    "ZEPTO": r"zepto",
    "BLINKIT": r"blinkit",
}


def categorize_transaction(narration: str, txn_type: str) -> tuple[str, str | None]:
    """Returns (category, source_platform)."""
    narration_lower = narration.lower()
    if txn_type == "CREDIT":
        for platform, pattern in GIG_PLATFORM_PATTERNS.items():
            if re.search(pattern, narration_lower):
                return "GIG_INCOME", platform
        if "upi" in narration_lower or "credit" in narration_lower:
            return "OTHER_INCOME", None
        return "UNCATEGORIZED_CREDIT", None
    else:
        if "rent" in narration_lower:
            return "RENT", None
        if "emi" in narration_lower:
            return "EMI", None
        if any(w in narration_lower for w in ["grocery", "fuel", "recharge"]):
            return "ESSENTIAL_EXPENSE", None
        return "OTHER_DEBIT", None


async def sync_financial_data(db: AsyncSession, consent: ConsentArtifact) -> list[FinancialAccount]:
    if consent.status != ConsentStatus.ACTIVE:
        raise ValueError(f"Consent {consent.id} is not ACTIVE (status={consent.status.value}); cannot fetch data.")

    aa_client = get_aa_client()
    fi_data = await aa_client.fetch_financial_data(consent.aa_consent_handle)

    account_ref_to_id: dict[str, str] = {}
    saved_accounts = []

    for acc in fi_data["accounts"]:
        account = FinancialAccount(
            user_id=consent.user_id,
            consent_id=consent.id,
            fip_id=acc["fip_id"],
            masked_account_number=acc["masked_account_number"],
            account_type=acc["account_type"],
        )
        db.add(account)
        await db.flush()  # get the generated id without committing yet
        account_ref_to_id[acc["account_ref"]] = account.id
        saved_accounts.append(account)

    for txn in fi_data["transactions"]:
        account_id = account_ref_to_id.get(txn["account_ref"])
        if not account_id:
            continue
        category, platform = categorize_transaction(txn["narration"], txn["type"])
        # Allow the mock client's explicit source_platform to override inference
        platform = txn.get("source_platform") or platform

        db.add(Transaction(
            account_id=account_id,
            txn_date=datetime.fromisoformat(txn["date"]),
            amount=txn["amount"],
            txn_type=txn["type"],
            narration=txn["narration"],
            category=category,
            source_platform=platform,
        ))

    await db.commit()
    for acc in saved_accounts:
        await db.refresh(acc)
    return saved_accounts


async def get_user_transactions(db: AsyncSession, user_id: str) -> list[Transaction]:
    result = await db.execute(
        select(Transaction)
        .join(FinancialAccount)
        .where(FinancialAccount.user_id == user_id)
        .order_by(Transaction.txn_date.desc())
    )
    return list(result.scalars().all())
