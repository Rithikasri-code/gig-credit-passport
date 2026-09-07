"""
Trains the scoring model on synthetic data, using a gradient-boosted tree
model (XGBoost) instead of a straight-line logistic regression, with a
real held-out evaluation — not just "does it match the formula I wrote."

Why synthetic data, and why that's legitimate for now:
- We have no real repayment-outcome data yet (no real loans have been
  disbursed through this product). Every real fintech underwriting model
  starts this way — a hypothesis-driven synthetic/proxy dataset, later
  recalibrated on real outcomes once they exist.
- The relationships encoded below are drawn from published microfinance/
  alternative-credit research: income consistency and repayment history
  are the strongest predictors of default risk for thin-file borrowers,
  more so than raw income level.

Why XGBoost instead of logistic regression:
- A straight-line model can't capture interactions — e.g. "income
  consistency matters more when a worker only has one income source, less
  when they have four." Gradient-boosted trees can learn that kind of
  conditional pattern, which is closer to how real underwriting behaves.
- Paired with SHAP (see model.py), this gives genuine per-prediction
  attribution — the actual industry-standard explainability technique for
  credit scoring — rather than a coefficient-times-value approximation
  that only worked because the old model happened to be linear.

Honest limitation this does NOT fix: "training accuracy" below is
measured on synthetic data against a formula I wrote, not real repayment
outcomes. A proper train/test split at least gives an honest read on
whether the model generalizes to *that* formula, rather than just
memorizing the training rows — but it's still not a real-world skill
measurement. That only comes from real user outcomes.

Run: python -m app.scoring.train
"""
from __future__ import annotations

import numpy as np
import joblib
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score,
    accuracy_score,
    log_loss,
    brier_score_loss,
    balanced_accuracy_score,
    precision_recall_fscore_support,
    roc_curve,
)

from app.scoring.features import FEATURE_NAMES
from app.core.config import settings

RNG = np.random.default_rng(42)
N_SAMPLES = 20000


def generate_synthetic_dataset(n=N_SAMPLES):
    """
    Simulates a population of gig workers with varying financial behavior,
    and a 'repaid_on_time' outcome generated from a hypothesis-driven
    (not arbitrary) formula — this is what the model learns to predict.
    """
    income_consistency = RNG.beta(2, 2, n)  # 0-1
    avg_monthly_income = RNG.gamma(shape=4, scale=4000, size=n)  # skewed, realistic gig income spread
    income_trend = RNG.normal(0, 0.3, n).clip(-1, 1)
    num_active_platforms = RNG.integers(1, 5, n).astype(float)
    txn_frequency_per_month = RNG.gamma(shape=3, scale=2, size=n)
    essential_expense_ratio = RNG.beta(2, 3, n)
    months_of_history = RNG.integers(1, 25, n).astype(float)
    self_reported_confirmation_ratio = RNG.beta(3, 1, n)  # most self-reports roughly line up
    itr_filed = RNG.binomial(1, 0.3, n).astype(float)  # ~30% of gig workers currently file ITR

    X = np.column_stack([
        income_consistency,
        avg_monthly_income,
        income_trend,
        num_active_platforms,
        txn_frequency_per_month,
        essential_expense_ratio,
        months_of_history,
        self_reported_confirmation_ratio,
        itr_filed,
    ])

    # Ground-truth logit — deliberately includes an INTERACTION term
    # (consistency matters more when platform count is low) that a linear
    # model structurally cannot learn, but a tree model can. This is the
    # concrete reason a gradient-boosted model is a genuine upgrade here,
    # not just a fancier label on the same thing.
    platform_scarcity_penalty = np.clip(2.5 - num_active_platforms, 0, None)  # bigger when platforms are few
    interaction_term = 0.6 * income_consistency * platform_scarcity_penalty

    logit = (
        2.2 * income_consistency
        + interaction_term
        + 1.2 * income_trend
        + 0.35 * num_active_platforms
        + 0.15 * txn_frequency_per_month
        - 1.5 * (essential_expense_ratio - 0.5) ** 2  # penalize extremes, not the ratio itself
        + 0.06 * np.minimum(months_of_history, 12)
        + 0.8 * self_reported_confirmation_ratio
        + 0.5 * itr_filed
        + RNG.normal(0, 0.5, n)  # noise — real behavior isn't fully explained by these features
        - 2.0
    )
    prob_repaid = 1 / (1 + np.exp(-logit))
    y = RNG.binomial(1, prob_repaid)

    return X, y


def train_and_save():
    X, y = generate_synthetic_dataset()

    # Real held-out evaluation — the model never sees the test set during
    # training, so these numbers actually mean something (relative to the
    # synthetic ground truth), unlike a training-set-only accuracy figure.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    test_probs = model.predict_proba(X_test)[:, 1]
    test_preds = model.predict(X_test)  # uses XGBoost's default 0.5 threshold

    auc = roc_auc_score(y_test, test_probs)
    acc = accuracy_score(y_test, test_preds)
    loss = log_loss(y_test, test_probs)
    brier = brier_score_loss(y_test, test_probs)

    print(f"Held-out test AUC:        {auc:.4f}  (0.5 = random, 1.0 = perfect)")
    print(f"Held-out test accuracy:   {acc:.4f}  (misleading alone — see balanced accuracy below)")
    print(f"Held-out test log loss:   {loss:.4f}  (lower is better)")
    print(f"Held-out test Brier score: {brier:.4f}  (calibration quality, 0=perfect, lower is better)")

    # The population this model is trained on is realistically imbalanced
    # (~87% "good" — consistent with published gig/microfinance repayment
    # research), so plain accuracy at the default 0.5 threshold is
    # misleading: a model that always predicts "good" would already score
    # ~87% accuracy without learning anything. Balanced accuracy and
    # per-class recall are what actually reveal whether the model can
    # identify the minority (risky) class.
    bal_acc_default = balanced_accuracy_score(y_test, test_preds)
    print(f"\nBalanced accuracy @ 0.5 threshold: {bal_acc_default:.4f}  (0.5 = no better than guessing)")

    # Rather than distorting the model's probabilities to fix this
    # (tried: scale_pos_weight and isotonic calibration — both traded
    # away calibration quality for classification performance, a real
    # regression this caught rather than shipped), the correct fix is
    # choosing a better DECISION THRESHOLD on the model's already
    # well-calibrated probabilities. This changes nothing about the
    # continuous score this app actually serves (probability * 600 + 300)
    # — it only matters the moment a future feature needs a binary
    # approve/deny decision, at which point THIS threshold, not 0.5,
    # should be used.
    fpr, tpr, thresholds = roc_curve(y_test, test_probs)
    balanced_acc_per_thresh = (tpr + (1 - fpr)) / 2
    best_idx = int(np.argmax(balanced_acc_per_thresh))
    optimal_decision_threshold = float(thresholds[best_idx])

    smart_preds = (test_probs >= optimal_decision_threshold).astype(int)
    bal_acc_smart = balanced_accuracy_score(y_test, smart_preds)
    prec, rec, f1, support = precision_recall_fscore_support(y_test, smart_preds)

    print(f"Optimal decision threshold (via ROC curve): {optimal_decision_threshold:.4f}")
    print(f"Balanced accuracy @ optimal threshold:       {bal_acc_smart:.4f}")
    print("Per-class performance @ optimal threshold (0=defaulted, 1=repaid):")
    for i in range(2):
        print(f"  class {i}: precision={prec[i]:.4f}  recall={rec[i]:.4f}  support={support[i]}")

    importances = model.feature_importances_
    print("\nFeature importances (XGBoost gain-based):")
    for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda p: -p[1]):
        print(f"  {name}: {imp:.4f}")

    # Per-feature population distributions, for feature-level percentile
    # comparisons in the UI (e.g. "more consistent income than X% of the
    # modeled population"). Deliberately NOT an overall-score percentile —
    # this system's population is realistically skewed toward good
    # repayment behavior (consistent with published research on gig/
    # microfinance repayment rates), so most workers cluster at the high
    # end of the score range. Comparing a specific behavior (like income
    # consistency) is meaningful and rarely contradicts the score band;
    # comparing the composite score itself produced exactly that
    # contradiction in testing (a "Good" 751 landing at only the 12th
    # percentile) — an artifact of comparing two different reference
    # frames, not a bug, but confusing enough to avoid rather than explain
    # away in the UI.
    feature_population = {name: np.sort(X[:, i]) for i, name in enumerate(FEATURE_NAMES)}

    joblib.dump(
        {
            "model": model,
            "feature_names": FEATURE_NAMES,
            "version": settings.MODEL_VERSION,
            "test_auc": float(auc),
            "test_accuracy": float(acc),
            "test_balanced_accuracy": float(bal_acc_default),
            "test_brier_score": float(brier),
            # Only meaningful for a future binary approve/deny feature —
            # the continuous score this app actually serves never uses a
            # threshold at all. Documented here so nobody reaches for the
            # default 0.5 later and silently reintroduces the recall
            # collapse this training run found and fixed.
            "optimal_decision_threshold": optimal_decision_threshold,
            "feature_population": feature_population,
        },
        settings.MODEL_PATH,
    )
    print(f"\nSaved model to {settings.MODEL_PATH}")


if __name__ == "__main__":
    train_and_save()
