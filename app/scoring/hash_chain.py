"""
Tamper-evident score history via hash chaining.

Each score's record_hash covers its own content plus the previous score's
hash. This means altering any past score breaks every hash computed after
it — verifiable by anyone who recomputes the chain from the first score,
without needing to trust our database directly.

This is NOT a blockchain (no consensus, no distributed ledger) — it's the
same core idea (hash chaining) applied to a single append-only table,
which is sufficient for "can this specific institution's records be
quietly altered without detection" rather than "can multiple parties
agree on shared state."
"""
import hashlib
import json


def compute_record_hash(prev_hash: str, user_id: str, score_value: int, features: dict, computed_at_iso: str) -> str:
    """
    Deterministic hash over a score's content + the chain so far.
    Uses sort_keys=True so the same content always hashes identically
    regardless of dict ordering.
    """
    payload = {
        "prev_hash": prev_hash,
        "user_id": user_id,
        "score_value": score_value,
        "features": features,
        "computed_at": computed_at_iso,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_chain(scores_oldest_first: list[dict]) -> tuple[bool, str | None]:
    """
    Recomputes every hash in a user's score history in order and checks it
    matches what's stored. Returns (is_valid, first_broken_score_id_or_None).

    Each dict needs: id, prev_hash, record_hash, user_id, score_value,
    features_used, computed_at (iso string).

    Scores marked 'PRE_CHAIN_UNVERIFIED' predate hash chaining being added
    (a one-time migration backfill) and are skipped rather than counted as
    tampered — the chain simply restarts cleanly with the next real score.
    """
    expected_prev = ""
    for s in scores_oldest_first:
        if s["record_hash"] == "PRE_CHAIN_UNVERIFIED":
            expected_prev = ""
            continue
        if s["prev_hash"] != expected_prev:
            return False, s["id"]
        recomputed = compute_record_hash(
            s["prev_hash"], s["user_id"], s["score_value"], s["features_used"], s["computed_at"]
        )
        if recomputed != s["record_hash"]:
            return False, s["id"]
        expected_prev = s["record_hash"]
    return True, None
