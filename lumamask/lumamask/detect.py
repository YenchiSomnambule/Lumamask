"""
detect.py — Sensitive entity detection using Microsoft Presidio + custom recognizers.

Detected entity types (MVP set):
  Built-in:  PERSON, ORGANIZATION, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION,
             CREDIT_CARD, IBAN_CODE, US_SSN
  Custom:    INVOICE_NUMBER, MONEY_AMOUNT, ACCOUNT_NUMBER

DATE_TIME is deliberately excluded (spec §2.2 — too aggressive on invoices,
fights MONEY_AMOUNT and corrupts the most safety-critical field).

Overlap resolution priority (highest first):
  CREDIT_CARD, IBAN_CODE, US_SSN, ACCOUNT_NUMBER, INVOICE_NUMBER,
  EMAIL_ADDRESS, PHONE_NUMBER, MONEY_AMOUNT, PERSON, ORGANIZATION, LOCATION
"""

from __future__ import annotations

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider

# ---------------------------------------------------------------------------
# Entity type priority (lower index = higher priority)
# ---------------------------------------------------------------------------
ENTITY_PRIORITY: list[str] = [
    "CREDIT_CARD",
    "IBAN_CODE",
    "US_SSN",
    "ACCOUNT_NUMBER",
    "INVOICE_NUMBER",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "MONEY_AMOUNT",
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
]

_PRIORITY_MAP: dict[str, int] = {e: i for i, e in enumerate(ENTITY_PRIORITY)}

MVP_ENTITIES: list[str] = ENTITY_PRIORITY  # same list, used as Presidio entity filter


def _priority(entity_type: str) -> int:
    """Lower value = higher priority. Unknown types get the lowest priority."""
    return _PRIORITY_MAP.get(entity_type, len(ENTITY_PRIORITY))


# ---------------------------------------------------------------------------
# Custom recognizers
# ---------------------------------------------------------------------------

def _make_invoice_recognizer() -> PatternRecognizer:
    """Matches: INV-00123, INVOICE #4567, Invoice No. 4567, INVOICE #Q-0047, etc.
    Supports both pure-digit and alphanumeric (letter-prefixed) reference codes.
    """
    return PatternRecognizer(
        supported_entity="INVOICE_NUMBER",
        patterns=[
            Pattern(
                name="invoice_number",
                regex=(
                    r"(?i)\binv(?:oice)?[-#\s.]*(?:no\.?|number)?[-#\s:]*"
                    r"(?:(?=[A-Z\-]*\d)[A-Z][A-Z0-9\-]{2,}|\d{3,})\b"
                ),
                score=0.75,
            )
        ],
    )


def _make_money_recognizer() -> PatternRecognizer:
    """Matches: $45,000, $45,000.00, USD 45000, CAD 1,200.50, CAD  8,500.00 (wide spacing).
    Known gap: unsigned amounts (e.g. 'Total: 45,000.00') are missed.
    """
    return PatternRecognizer(
        supported_entity="MONEY_AMOUNT",
        patterns=[
            Pattern(
                name="money_amount",
                # \s{0,4}: allow up to 4 spaces (e.g. "CAD  8,500.00" uses 2 spaces in tables)
                # score 0.75: within 0.1 of spaCy ORG (0.85) so priority-list wins (MONEY=7 < ORG=9)
                regex=r"(?i)(?:\$|usd|cad|eur|gbp)\s{0,4}\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b",
                score=0.75,
            )
        ],
    )


def _make_account_recognizer() -> PatternRecognizer:
    """Matches: Account: 123456789, Acct # 0099887, etc."""
    return PatternRecognizer(
        supported_entity="ACCOUNT_NUMBER",
        patterns=[
            Pattern(
                name="account_number",
                # score 0.75: within 0.1 of spaCy ORG (0.85) so priority-list wins (ACCT=3 < ORG=9)
                regex=r"(?i)\b(?:acct|account)[-#\s.]*(?:no\.?|number)?[-#\s:#]*(\d{4,})\b",
                score=0.75,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Cached AnalyzerEngine (loads spaCy model once per process)
# ---------------------------------------------------------------------------

_analyzer: AnalyzerEngine | None = None


def _get_analyzer() -> AnalyzerEngine:
    """Return the module-level AnalyzerEngine singleton, creating it on first call."""
    global _analyzer
    if _analyzer is None:
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_md"}],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()

        _analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=["en"],
        )
        _analyzer.registry.add_recognizer(_make_invoice_recognizer())
        _analyzer.registry.add_recognizer(_make_money_recognizer())
        _analyzer.registry.add_recognizer(_make_account_recognizer())

    return _analyzer


# ---------------------------------------------------------------------------
# Overlap resolution
# ---------------------------------------------------------------------------

def _beats(challenger: dict, incumbent: dict) -> bool:
    """Return True if challenger should replace incumbent in an overlap."""
    score_diff = challenger["score"] - incumbent["score"]
    if score_diff > 0.1:
        return True
    if score_diff < -0.1:
        return False
    # Near-tie (within 0.1): use entity type priority
    cp = _priority(challenger["entity_type"])
    ip = _priority(incumbent["entity_type"])
    if cp != ip:
        return cp < ip  # lower index = higher priority
    # Same type/priority: longer span wins
    return (challenger["end"] - challenger["start"]) > (incumbent["end"] - incumbent["start"])


def _resolve_overlaps(detections: list[dict]) -> list[dict]:
    """Return a non-overlapping subset of detections, applying _beats() for conflicts."""
    # Sort by start offset; secondary sort by span length desc (longer first)
    candidates = sorted(
        detections,
        key=lambda d: (d["start"], -(d["end"] - d["start"])),
    )

    kept: list[dict] = []
    for candidate in candidates:
        overlapping = [
            k for k in kept
            if candidate["start"] < k["end"] and candidate["end"] > k["start"]
        ]
        if not overlapping:
            kept.append(candidate)
        elif all(_beats(candidate, inc) for inc in overlapping):
            for inc in overlapping:
                kept.remove(inc)
            kept.append(candidate)
        # else: incumbent(s) win — discard candidate

    return sorted(kept, key=lambda d: d["start"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect(text: str, language: str = "en") -> list[dict]:
    """
    Detect sensitive entities in *text*.

    Returns a list of detection dicts, sorted by start offset (ascending),
    with no overlapping spans:
        {
            "entity_type": str,   # e.g. "PERSON"
            "start": int,         # char offset, inclusive
            "end": int,           # char offset, exclusive
            "score": float,
            "text": str           # text[start:end]
        }

    DATE_TIME is intentionally not detected (see module docstring).
    """
    analyzer = _get_analyzer()
    raw = analyzer.analyze(text=text, language=language, entities=MVP_ENTITIES)

    detections = [
        {
            "entity_type": r.entity_type,
            "start": r.start,
            "end": r.end,
            "score": round(r.score, 4),
            "text": text[r.start:r.end],
        }
        for r in raw
    ]

    return _resolve_overlaps(detections)
