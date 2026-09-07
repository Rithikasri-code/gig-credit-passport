"""
Feature engineering for the credit passport score.

Every feature here is chosen to be:
1. Explainable in plain language to a non-technical worker.
2. Defensible — no proxy for protected characteristics (location, gender,
   religion inferred from name, etc.) ever enters this list.
3. Behavior-based, not income-amount-based — a worker earning less but
   consistently should be able to outscore one earning more erratically.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import numpy as np

FEATURE_NAMES = [
    "income_consistency",       # 0-1, inverse of coefficient of variation of monthly income
    "avg_monthly_income",       # rupees
    "income_trend",             # -1 to 1, is income growing/shrinking over the window
    "num_active_platforms",     # count of distinct gig platforms paying in
    "txn_frequency_per_month",  # avg number of credit transactions per month
    "essential_expense_ratio",  # essential debits / total credits (financial discipline signal)
    "months_of_history",        # how many months of real data we have
    "self_reported_confirmation_ratio",  # how much self-reported OCR data aligns with AA data
    "itr_filed",                # 0 or 1, self-declared income tax return filing status
]


def _monthly_buckets(transactions: list[dict]) -> dict[str, list[float]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for t in transactions:
        if t["txn_type"] != "CREDIT" or t["category"] != "GIG_INCOME":
            continue
        month_key = t["txn_date"][:7]  # "YYYY-MM"
        buckets[month_key].append(float(t["amount"]))
    return buckets


def compute_features(transactions: list[dict], self_reported: list[dict] | None = None, itr_filed: bool = False) -> dict:
    """
    transactions: list of dicts with keys txn_date (iso str), amount, txn_type,
                  category, source_platform.
    self_reported: list of dicts from SelfReportedEarning (optional, may be empty).
    itr_filed: self-declared by the worker — not independently verified yet
               (an ITR-verification integration would be the honest upgrade
               path here, same caveat as self-reported OCR earnings).
    """
    self_reported = self_reported or []

    monthly = _monthly_buckets(transactions)
    monthly_totals = {m: sum(v) for m, v in monthly.items()}
    months_sorted = sorted(monthly_totals.keys())

    if not months_sorted:
        # No income data at all — return a clearly "insufficient data" feature vector
        return {name: 0.0 for name in FEATURE_NAMES} | {"months_of_history": 0.0}

    totals = np.array([monthly_totals[m] for m in months_sorted])
    avg_income = float(np.mean(totals))
    std_income = float(np.std(totals))
    cv = (std_income / avg_income) if avg_income > 0 else 1.0
    income_consistency = float(max(0.0, 1.0 - min(cv, 1.0)))  # 1 = perfectly consistent, 0 = wildly erratic

    # Trend: simple linear slope normalized by average income
    if len(totals) >= 2:
        x = np.arange(len(totals))
        slope = float(np.polyfit(x, totals, 1)[0])
        income_trend = float(np.clip(slope / (avg_income + 1e-6), -1, 1))
    else:
        income_trend = 0.0

    platforms = {t["source_platform"] for t in transactions if t.get("source_platform")}

    total_credit_txns = sum(1 for t in transactions if t["txn_type"] == "CREDIT" and t["category"] == "GIG_INCOME")
    txn_frequency = total_credit_txns / max(len(months_sorted), 1)

    total_credits = sum(float(t["amount"]) for t in transactions if t["txn_type"] == "CREDIT")
    essential_debits = sum(float(t["amount"]) for t in transactions if t["txn_type"] == "DEBIT" and t["category"] == "ESSENTIAL_EXPENSE")
    essential_ratio = essential_debits / total_credits if total_credits > 0 else 0.0

    # Cross-check self-reported earnings against AA-verified totals, per platform/month —
    # this is what lets OCR data contribute to the score safely (see ocr_service.py notes).
    confirmation_scores = []
    for report in self_reported:
        if not report.get("total_earnings") or not report.get("source_platform"):
            continue
        platform = report["source_platform"]
        aa_platform_total = sum(
            float(t["amount"]) for t in transactions
            if t.get("source_platform") == platform and t["txn_type"] == "CREDIT"
        )
        if aa_platform_total == 0:
            confirmation_scores.append(0.0)
            continue
        ratio = min(report["total_earnings"], aa_platform_total) / max(report["total_earnings"], aa_platform_total)
        confirmation_scores.append(ratio)

    # IMPORTANT: absence of self-reported documents must be neutral, not penalized.
    # 0.0 would mean "self-reports actively contradict bank data" — wrong when there
    # simply are none. We default to the training population's mean confirmation
    # ratio (~0.75, matching the Beta(3,1) prior in train.py) so a worker who never
    # uploads anything is scored the same as one whose self-reports aren't being
    # cross-checked at all — not punished for a feature they had no way to submit.
    NEUTRAL_CONFIRMATION_DEFAULT = 0.75
    self_reported_confirmation = (
        float(np.mean(confirmation_scores)) if confirmation_scores else NEUTRAL_CONFIRMATION_DEFAULT
    )

    return {
        "income_consistency": round(income_consistency, 4),
        "avg_monthly_income": round(avg_income, 2),
        "income_trend": round(income_trend, 4),
        "num_active_platforms": float(len(platforms)),
        "txn_frequency_per_month": round(txn_frequency, 2),
        "essential_expense_ratio": round(min(essential_ratio, 1.0), 4),
        "months_of_history": float(len(months_sorted)),
        "self_reported_confirmation_ratio": round(self_reported_confirmation, 4),
        "itr_filed": 1.0 if itr_filed else 0.0,
        "_has_self_reported_data": bool(confirmation_scores),  # internal flag, not fed to the model
    }
