"""
Account Aggregator client.

Two implementations behind one interface:
- MockAAClient: generates realistic gig-worker transaction patterns locally.
  Works with zero credentials — this is what runs by default so the app is
  usable today.
- SetuAAClient: talks to Setu's real FIU sandbox/production API. Switch to
  this the moment AA_CLIENT_ID / AA_CLIENT_SECRET are set in .env.

Swapping later requires zero changes to any route or service that calls
this — they only ever depend on the AAClient interface.
"""
from __future__ import annotations

import random
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings


class AAClient(ABC):
    @abstractmethod
    async def create_consent(self, user_id: str, purpose: str) -> dict:
        """Kick off a consent request. Returns {consent_handle, redirect_url, status}."""

    @abstractmethod
    async def check_consent_status(self, consent_handle: str) -> str:
        """Returns one of PENDING, ACTIVE, REVOKED, EXPIRED."""

    @abstractmethod
    async def fetch_financial_data(self, consent_handle: str) -> dict:
        """
        Returns normalized FI data:
        {
          "accounts": [{"fip_id", "masked_account_number", "account_type"}],
          "transactions": [{"account_ref", "date", "amount", "type", "narration"}]
        }
        """


class MockAAClient(AAClient):
    """
    Simulates a gig worker's real bank data — irregular but pattern-rich
    income from multiple gig platforms, plus normal life expenses.
    Deterministic-ish but with realistic noise, so the scoring model has
    something meaningful to learn from and explain.
    """

    GIG_PLATFORMS = ["SWIGGY", "ZOMATO", "UBER", "OLA", "URBAN_COMPANY"]
    EXPENSE_NARRATIONS = ["RENT PAYMENT", "GROCERY UPI", "MOBILE RECHARGE", "FUEL", "EMI DEBIT"]

    async def create_consent(self, user_id: str, purpose: str) -> dict:
        handle = f"mock-consent-{uuid.uuid4()}"
        return {"consent_handle": handle, "redirect_url": None, "status": "ACTIVE"}

    async def check_consent_status(self, consent_handle: str) -> str:
        return "ACTIVE"

    async def fetch_financial_data(self, consent_handle: str) -> dict:
        account_ref = f"acc-{uuid.uuid4().hex[:10]}"
        accounts = [{
            "fip_id": "MOCK-BANK-001",
            "account_ref": account_ref,
            "masked_account_number": f"XXXXXX{random.randint(1000, 9999)}",
            "account_type": "SAVINGS",
        }]

        transactions = []
        today = datetime.now(timezone.utc)
        # Simulate 6 months of history
        for month_offset in range(6, 0, -1):
            month_date = today - timedelta(days=30 * month_offset)
            # 2-4 gig payouts per month, irregular amounts (this is the signal)
            num_payouts = random.randint(2, 4)
            for _ in range(num_payouts):
                platform = random.choice(self.GIG_PLATFORMS)
                amount = round(random.uniform(4000, 12000), 2)
                day_jitter = random.randint(0, 27)
                transactions.append({
                    "account_ref": account_ref,
                    "date": (month_date + timedelta(days=day_jitter)).isoformat(),
                    "amount": amount,
                    "type": "CREDIT",
                    "narration": f"UPI-{platform}-PAYOUT",
                    "source_platform": platform,
                })
            # Regular expenses
            for narration in random.sample(self.EXPENSE_NARRATIONS, k=3):
                transactions.append({
                    "account_ref": account_ref,
                    "date": (month_date + timedelta(days=random.randint(0, 27))).isoformat(),
                    "amount": round(random.uniform(500, 4000), 2),
                    "type": "DEBIT",
                    "narration": narration,
                    "source_platform": None,
                })

        return {"accounts": accounts, "transactions": transactions}


class SetuAAClient(AAClient):
    """
    Real integration against Setu's FIU sandbox/production API.
    Not wired up with live calls yet — fill in once AA_CLIENT_ID/SECRET
    are issued. Structure mirrors Setu's actual consent + FI-data-fetch
    API flow so swapping is a matter of implementation, not redesign.
    """

    def __init__(self):
        self.base_url = settings.AA_BASE_URL
        self.client_id = settings.AA_CLIENT_ID
        self.client_secret = settings.AA_CLIENT_SECRET
        self.product_instance_id = settings.AA_PRODUCT_INSTANCE_ID

    def _headers(self) -> dict:
        return {
            "client": self.client_id,
            "x-product-instance-id": self.product_instance_id,
            "Content-Type": "application/json",
        }

    async def create_consent(self, user_id: str, purpose: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.post(
                "/consents",
                headers=self._headers(),
                json={
                    "consentDuration": {"unit": "MONTH", "value": "6"},
                    "vua": user_id,
                    "dataRange": {
                        "from": (datetime.now(timezone.utc) - timedelta(days=180)).isoformat(),
                        "to": datetime.now(timezone.utc).isoformat(),
                    },
                    "purpose": purpose,
                    "consentTypes": ["TRANSACTIONS", "PROFILE"],
                    "fiTypes": ["DEPOSIT"],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "consent_handle": data.get("id"),
                "redirect_url": data.get("url"),
                "status": "PENDING",
            }

    async def check_consent_status(self, consent_handle: str) -> str:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.get(f"/consents/{consent_handle}", headers=self._headers())
            resp.raise_for_status()
            return resp.json().get("status", "PENDING")

    async def fetch_financial_data(self, consent_handle: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.post(
                "/sessions",
                headers=self._headers(),
                json={"consentId": consent_handle, "dataRange": {}},
            )
            resp.raise_for_status()
            session_id = resp.json().get("id")

            data_resp = await client.get(f"/sessions/{session_id}", headers=self._headers())
            data_resp.raise_for_status()
            # NOTE: real response needs XML/JSON FI-data parsing per Setu's spec —
            # implement the parser here once sandbox credentials are live and
            # you can see actual payload shape.
            return data_resp.json()


def get_aa_client() -> AAClient:
    """Factory — swap implementation based on whether real AA credentials exist."""
    if settings.AA_CLIENT_ID and settings.AA_CLIENT_SECRET:
        return SetuAAClient()
    return MockAAClient()
