"""
Loads the trained XGBoost model and turns a feature dict into:
- a 300-900 score (CIBIL-like scale, familiar to Indian users/lenders)
- narrative reason codes: plain-language sentences describing what
  actually moved the score, derived from real SHAP (Shapley value)
  attribution — the industry-standard explainability technique for
  credit scoring, correctly accounting for feature interactions that a
  linear coefficient could never capture (e.g. income consistency
  mattering more when a worker has fewer platforms).
- a percentile against the synthetic training population, clearly
  labeled as a modeled reference (not real other users) until real
  outcome data exists to replace it.
"""
from __future__ import annotations

import joblib
import numpy as np
import shap

from app.core.config import settings
from app.scoring.features import FEATURE_NAMES

_MODEL_CACHE = None
_EXPLAINER_CACHE = None


def _load_model():
    global _MODEL_CACHE, _EXPLAINER_CACHE
    if _MODEL_CACHE is None:
        _MODEL_CACHE = joblib.load(settings.MODEL_PATH)
        _EXPLAINER_CACHE = shap.TreeExplainer(_MODEL_CACHE["model"])
    return _MODEL_CACHE, _EXPLAINER_CACHE


def feature_percentile(feature_name: str, value: float) -> int | None:
    """
    Where this worker's value for a specific feature (e.g. income
    consistency) falls against the synthetic training population, 0-100.
    Deliberately per-feature, not per-score — see the note in train.py on
    why comparing the composite score against the population produced a
    misleading contradiction, while comparing a specific behavior doesn't.
    """
    bundle, _ = _load_model()
    population = bundle.get("feature_population", {}).get(feature_name)
    if population is None or len(population) == 0:
        return None
    rank = int(np.searchsorted(population, value))
    return int(round(100 * rank / len(population)))


def _narrative(feature_name: str, value: float, shap_value: float, features: dict) -> str:
    """
    Plain-language, specific-to-this-worker sentences — not a coefficient
    dump. Each references the worker's actual value, not just direction.
    Where a meaningful population comparison exists, it's woven in
    naturally rather than shown as a separate, potentially contradictory
    number (see the note in train.py on why we compare per-feature, not
    the composite score, against the population).
    """
    helped = shap_value > 0
    pctl = feature_percentile(feature_name, value)

    if feature_name == "income_consistency":
        pct = round(value * 100)
        comparison = f". More consistent than {pctl}% of the modeled worker population" if pctl is not None else ""
        if helped:
            return f"Your income has stayed steady month to month ({pct}% consistency){comparison}. This is the single strongest thing working in your favor."
        return f"Your income swings quite a bit month to month ({pct}% consistency){comparison}. Smoothing this out would help more than almost anything else."

    if feature_name == "num_active_platforms":
        n = int(value)
        if helped:
            return f"You earn from {n} different platforms. Lenders see that as safer than depending on just one."
        return f"You're currently earning from only {n} platform{'s' if n != 1 else ''}. Adding another income source would strengthen this."

    if feature_name == "income_trend":
        if helped:
            return "Your income has been trending upward over your history. That momentum is helping your score."
        return "Your income has been trending downward recently. Reversing that would help your score recover."

    if feature_name == "txn_frequency_per_month":
        n = round(value, 1)
        if helped:
            return f"You get paid often, about {n} payouts a month. Frequent, regular payouts read as stability."
        return f"You get paid relatively rarely, about {n} payouts a month. More frequent payouts would help."

    if feature_name == "months_of_history":
        n = int(value)
        if helped:
            return f"You've built {n} months of financial history with us. The longer this runs, the more confident the score becomes."
        return f"You've only got {n} month{'s' if n != 1 else ''} of history so far. This will naturally improve as more data comes in."

    if feature_name == "essential_expense_ratio":
        pct = round(value * 100)
        if helped:
            return f"Your spending on essentials ({pct}% of income) looks balanced, not overextended and not suspiciously low."
        return f"Your essential spending ratio ({pct}% of income) is a bit outside the healthy range, either overleveraged or possibly underreported income."

    if feature_name == "self_reported_confirmation_ratio":
        if helped:
            return "The earnings screenshots you uploaded line up well with your actual bank data. That consistency builds trust."
        return "Your uploaded earnings didn't fully match your bank data. Uploads that align more closely would help."

    if feature_name == "itr_filed":
        if value >= 0.5:
            return "You've filed your income tax return. That formal financial footprint is working in your favor."
        return "You haven't filed an income tax return yet. Doing so would give your score a real, verifiable boost."

    if feature_name == "avg_monthly_income":
        return f"Your average monthly income (₹{value:,.0f}) has a small effect here. This score rewards consistency over raw amount."

    return f"{feature_name.replace('_', ' ').title()} had a {'positive' if helped else 'negative'} effect."


def compute_score(features: dict) -> dict:
    """
    features: dict matching FEATURE_NAMES keys (see features.compute_features).
    Returns: {score_value, reason_codes, raw_probability, model_version, percentile}
    """
    bundle, explainer = _load_model()
    model = bundle["model"]

    if features.get("months_of_history", 0) == 0:
        return {
            "score_value": None,
            "reason_codes": ["Not enough financial history yet. Link an account or upload earnings data to get scored."],
            "raw_probability": None,
            "model_version": bundle["version"],
        }

    x = np.array([[features[name] for name in FEATURE_NAMES]])
    prob = float(model.predict_proba(x)[0][1])  # probability of "good repayment behavior"
    score_value = int(round(300 + prob * 600))

    # Real Shapley values — correctly attribute the prediction to each
    # feature, accounting for interactions the tree model learned (e.g.
    # consistency mattering more when platform count is low), which a
    # linear coefficient could never do.
    shap_values = explainer.shap_values(x)[0]

    pairs = list(zip(FEATURE_NAMES, shap_values))

    # Don't surface "self-reported data" as a reason when the worker never
    # uploaded anything — there's nothing to explain, and showing it as a
    # negative reads as an unfair penalty for not uploading (a real bug
    # this exact check caught and fixed once already).
    if not features.get("_has_self_reported_data", True):
        pairs = [p for p in pairs if p[0] != "self_reported_confirmation_ratio"]

    ranked = sorted(pairs, key=lambda p: abs(p[1]), reverse=True)
    reason_codes = [_narrative(name, features[name], shap_val, features) for name, shap_val in ranked[:4]]

    return {
        "score_value": score_value,
        "reason_codes": reason_codes,
        "raw_probability": round(prob, 4),
        "model_version": bundle["version"],
    }
