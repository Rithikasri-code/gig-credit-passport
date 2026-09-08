"""
OCR ingestion for gig-platform earnings screenshots/statements.

This is a SUPPLEMENTARY, self-reported signal — never a substitute for
AA-verified transaction data. It fills a real gap AA can't: platform-native
context like trip count, rating, and tenure that never appears in a bank
narration line.

Trust model:
- extraction_confidence reflects how much of the expected fields we
  actually parsed cleanly (not a fraud-detection score).
- is_verified stays False by default. It only flips True if a
  cross-check job later matches the claimed total_earnings against real
  AA-sourced CREDIT transactions from the same platform within the same
  window (see scoring/cross_verify.py, added when we build the scoring
  pipeline) — that's what makes this safe to blend in as a minor signal
  rather than a spoofable one.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from io import BytesIO

import pytesseract
from PIL import Image

from app.models.models import SelfReportedEarning

PLATFORM_KEYWORDS = {
    "SWIGGY": r"swiggy",
    "ZOMATO": r"zomato",
    "UBER": r"uber",
    "OLA": r"\bola\b",
    "URBAN_COMPANY": r"urban\s*company",
}

# Loose patterns for common earnings-dashboard phrasing — real-world
# screenshots vary a lot, so this is intentionally forgiving and each
# field is independently optional.
TOTAL_EARNINGS_PATTERN = re.compile(r"(?:total\s*earnings?|you\s*earned|net\s*payout)\D{0,10}(?:rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)
TRIP_COUNT_PATTERN = re.compile(r"(\d+)\s*(?:trips?|orders?|deliveries)", re.IGNORECASE)
RATING_PATTERN = re.compile(r"rating\D{0,5}([1-5]\.\d{1,2})", re.IGNORECASE)


def _detect_platform(text: str) -> str:
    text_lower = text.lower()
    for platform, pattern in PLATFORM_KEYWORDS.items():
        if re.search(pattern, text_lower):
            return platform
    return "UNKNOWN"


def _extract_fields(text: str) -> dict:
    fields_found = 0
    total_fields_attempted = 3

    total_earnings = None
    if m := TOTAL_EARNINGS_PATTERN.search(text):
        total_earnings = float(m.group(1).replace(",", ""))
        fields_found += 1

    trip_count = None
    if m := TRIP_COUNT_PATTERN.search(text):
        trip_count = int(m.group(1))
        fields_found += 1

    rating = None
    if m := RATING_PATTERN.search(text):
        rating = float(m.group(1))
        fields_found += 1

    confidence = fields_found / total_fields_attempted
    return {
        "total_earnings": total_earnings,
        "trip_or_order_count": trip_count,
        "rating": rating,
        "extraction_confidence": round(confidence, 2),
    }


def extract_from_image_bytes(image_bytes: bytes) -> dict:
    """Runs OCR on a screenshot (PNG/JPG) and extracts structured fields."""
    image = Image.open(BytesIO(image_bytes))
    raw_text = pytesseract.image_to_string(image)

    platform = _detect_platform(raw_text)
    fields = _extract_fields(raw_text)

    return {
        "source_platform": platform,
        "document_type": "SCREENSHOT",
        "raw_ocr_text": raw_text[:5000],
        **fields,
    }


def build_self_reported_earning(user_id: str, extracted: dict) -> SelfReportedEarning:
    """Maps extracted OCR fields to a persistable, clearly-labeled record."""
    return SelfReportedEarning(
        user_id=user_id,
        source_platform=extracted["source_platform"],
        document_type=extracted["document_type"],
        total_earnings=extracted.get("total_earnings"),
        trip_or_order_count=extracted.get("trip_or_order_count"),
        rating=extracted.get("rating"),
        raw_ocr_text=extracted.get("raw_ocr_text", ""),
        extraction_confidence=extracted.get("extraction_confidence", 0.0),
        is_verified=False,  # never set True here — only the cross-verify job can do that
        uploaded_at=datetime.now(timezone.utc),
    )
