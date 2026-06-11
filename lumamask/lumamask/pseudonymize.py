"""
pseudonymize.py — Mask sensitive spans and build the placeholder map.

Token format: [ALIAS_N] where N is assigned in order of first appearance.

Type aliases:
  PERSON→PERSON, ORGANIZATION→ORG, EMAIL_ADDRESS→EMAIL, PHONE_NUMBER→PHONE,
  LOCATION→LOC, MONEY_AMOUNT→AMT, INVOICE_NUMBER→INV, ACCOUNT_NUMBER→ACCT,
  CREDIT_CARD→CC, IBAN_CODE→IBAN, US_SSN→SSN

Coreference rules ensure the same real-world entity always maps to the same
token, even when referred to in multiple surface forms (spec §4.2).
"""

from __future__ import annotations
import re

# ---------------------------------------------------------------------------
# Token alias mapping
# ---------------------------------------------------------------------------
TYPE_ALIAS: dict[str, str] = {
    "PERSON":         "PERSON",
    "ORGANIZATION":   "ORG",
    "EMAIL_ADDRESS":  "EMAIL",
    "PHONE_NUMBER":   "PHONE",
    "LOCATION":       "LOC",
    "MONEY_AMOUNT":   "AMT",
    "INVOICE_NUMBER": "INV",
    "ACCOUNT_NUMBER": "ACCT",
    "CREDIT_CARD":    "CC",
    "IBAN_CODE":      "IBAN",
    "US_SSN":         "SSN",
}

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_HONORIFICS = re.compile(
    r"^\s*(?:mr\.?|mrs\.?|ms\.?|miss\.?|dr\.?|prof\.?)\s+",
    re.IGNORECASE,
)

_ORG_SUFFIXES = re.compile(
    r"\b(?:incorporated|corporation|company|limited|inc\.?|corp\.?|ltd\.?|"
    r"llc|l\.l\.c\.?|co\.?)\s*$",
    re.IGNORECASE,
)


def _norm_person(text: str) -> tuple[str, str, list[str]]:
    """
    Normalise a person name.
    Returns (normalised_full, surname, given_names_list).
    Strips honorifics, lowercases, collapses whitespace.
    """
    s = _HONORIFICS.sub("", text).strip()
    s = re.sub(r"\s+", " ", s).lower()
    parts = s.split()
    if not parts:
        return s, "", []
    surname = parts[-1]
    given_names = parts[:-1]
    return s, surname, given_names


def _given_names_conflict(existing_given: list[str], new_given: list[str]) -> bool:
    """
    Return True ONLY if given names are clearly incompatible (two different full names).

    Initials (single letter, with or without trailing period) are treated as
    potentially compatible with any full name starting with that letter.

    Examples (all already lowercased by _norm_person):
      ["john"] vs ["john"]  → False  (same)
      ["john"] vs ["jane"]  → True   (conflict)
      ["j."]   vs ["john"]  → False  (initial "j" matches "john")
      ["j."]   vs ["jane"]  → False  (initial "j" matches "jane") ← intentional;
                                      see spec §4.2 — when ambiguous, later logic
                                      handles it via the multiple-surname-match branch
      ["j."]   vs ["k..."]  → True   (initial "j" doesn't match "k...")
      []       vs [...]     → False  (bare surname, never conflicts)
    """
    if not existing_given or not new_given:
        return False
    # Compare first given-name token (most discriminating)
    e = existing_given[0].rstrip(".")   # already lowercase from _norm_person
    n = new_given[0].rstrip(".")
    # One or both sides are single-letter initials
    if len(e) == 1 and len(n) >= 1:
        return not n.startswith(e)
    if len(n) == 1 and len(e) >= 1:
        return not e.startswith(n)
    # Both are full given names
    return e != n


def _norm_org(text: str) -> str:
    """Lowercase, strip known corporate suffixes and trailing punctuation."""
    s = text.strip().lower()
    s = _ORG_SUFFIXES.sub("", s).strip(" .,;:")
    return s


def _norm_phone(text: str) -> str:
    """Keep digits only."""
    return re.sub(r"\D", "", text)


def _norm_email(text: str) -> str:
    return text.strip().lower()


def _norm_money(text: str) -> str:
    """
    Normalise to a comparable numeric string.
    '$45,000.00', 'USD 45000', 'CAD 45,000' → '45000.00'
    """
    s = re.sub(r"(?i)[\$\s,]", "", text)
    s = re.sub(r"(?i)^(usd|cad|eur|gbp)", "", s).strip()
    try:
        return f"{float(s):.2f}"
    except ValueError:
        return s.lower()


def _norm_generic(text: str) -> str:
    """Strip spaces and dashes, lowercase."""
    return re.sub(r"[\s\-]", "", text).lower()


_NORM_FN = {
    "PERSON":         lambda t: _norm_person(t)[0],
    "ORGANIZATION":   _norm_org,
    "EMAIL_ADDRESS":  _norm_email,
    "PHONE_NUMBER":   _norm_phone,
    "MONEY_AMOUNT":   _norm_money,
    "LOCATION":       lambda t: t.strip().lower(),
}


def _normalize(entity_type: str, text: str) -> str:
    return _NORM_FN.get(entity_type, _norm_generic)(text)


# ---------------------------------------------------------------------------
# Placeholder map
# ---------------------------------------------------------------------------

class _PseudonymMap:
    """
    Mutable state built during a single pseudonymize() call.

    Maintains:
      entries   — list of map entry dicts (serialisable)
      _index    — normalised_surface → token (fast lookup)
      _counters — alias → last N assigned
    """

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self._index: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_token(self, entity_type: str) -> str:
        alias = TYPE_ALIAS.get(entity_type, entity_type)
        self._counters[alias] = self._counters.get(alias, 0) + 1
        return f"[{alias}_{self._counters[alias]}]"

    def _register(
        self,
        token: str,
        entity_type: str,
        real_value: str,
        variants: list[str],
        ambiguous: bool = False,
    ) -> None:
        entry: dict = {
            "token":       token,
            "entity_type": entity_type,
            "real_value":  real_value,
            "variants":    list(variants),
        }
        if ambiguous:
            entry["ambiguous"] = True
        self.entries.append(entry)
        for v in variants:
            norm = _normalize(entity_type, v)
            if norm not in self._index:
                self._index[norm] = token

    def _add_variant(self, token: str, entity_type: str, surface: str) -> None:
        """
        Record *surface* as an additional variant of *token*.
        Adds to the reverse index and to the entry's variants list (if new).
        """
        norm = _normalize(entity_type, surface)
        if norm not in self._index:
            self._index[norm] = token
        for entry in self.entries:
            if entry["token"] == token:
                if surface not in entry["variants"]:
                    entry["variants"].append(surface)
                break

    def _person_entries(self) -> list[dict]:
        return [e for e in self.entries if e["entity_type"] == "PERSON"]

    # ------------------------------------------------------------------
    # PERSON coreference (spec §4.2)
    # ------------------------------------------------------------------

    def _get_person_token(self, surface: str) -> str:
        norm_full, surname, given_names = _norm_person(surface)

        # 1. Exact normalised match
        if norm_full in self._index:
            token = self._index[norm_full]
            self._add_variant(token, "PERSON", surface)
            return token

        # 2. Find existing entries with matching surname
        surname_matches = []
        for entry in self._person_entries():
            _, esurname, _ = _norm_person(entry["real_value"])
            if esurname == surname:
                surname_matches.append(entry)

        # 3. No surname match → new entry
        if not surname_matches:
            token = self._next_token("PERSON")
            self._register(token, "PERSON", surface, [surface])
            return token

        # 4. Exactly one surname match
        if len(surname_matches) == 1:
            entry = surname_matches[0]
            if not given_names:
                # Bare surname, unambiguous → reuse
                self._add_variant(entry["token"], "PERSON", surface)
                return entry["token"]
            # Has given names → check for conflict across ALL existing variants
            for v in entry["variants"]:
                _, _, existing_given = _norm_person(v)
                if _given_names_conflict(existing_given, given_names):
                    # Clear conflict (e.g. "Jane" vs "John") → new token
                    token = self._next_token("PERSON")
                    self._register(token, "PERSON", surface, [surface])
                    return token
            # No conflict (including initial matches like "J." vs "John") → reuse
            self._add_variant(entry["token"], "PERSON", surface)
            return entry["token"]

        # 5. Multiple surname matches
        if given_names:
            # Find compatible entries (no given-name conflict with any variant)
            compatible = []
            for entry in surname_matches:
                conflict = False
                for v in entry["variants"]:
                    _, _, existing_given = _norm_person(v)
                    if _given_names_conflict(existing_given, given_names):
                        conflict = True
                        break
                if not conflict:
                    compatible.append(entry)
            if len(compatible) == 1:
                self._add_variant(compatible[0]["token"], "PERSON", surface)
                return compatible[0]["token"]

        # Ambiguous — cannot safely assign to any existing entry
        token = self._next_token("PERSON")
        self._register(token, "PERSON", surface, [surface], ambiguous=True)
        return token

    # ------------------------------------------------------------------
    # ORGANIZATION coreference (spec §4.2)
    # ------------------------------------------------------------------

    def _get_org_token(self, surface: str) -> str:
        norm = _norm_org(surface)

        # Fast path: already in index
        if norm in self._index:
            token = self._index[norm]
            self._add_variant(token, "ORGANIZATION", surface)
            return token

        # Slow path: compare normalised canonical of existing entries
        for entry in self.entries:
            if entry["entity_type"] == "ORGANIZATION":
                if _norm_org(entry["real_value"]) == norm:
                    self._add_variant(entry["token"], "ORGANIZATION", surface)
                    return entry["token"]

        # New org
        token = self._next_token("ORGANIZATION")
        self._register(token, "ORGANIZATION", surface, [surface])
        return token

    # ------------------------------------------------------------------
    # Generic (exact normalised match, spec §4.2)
    # ------------------------------------------------------------------

    def _get_generic_token(self, entity_type: str, surface: str) -> str:
        norm = _normalize(entity_type, surface)
        if norm in self._index:
            token = self._index[norm]
            self._add_variant(token, entity_type, surface)
            return token
        token = self._next_token(entity_type)
        self._register(token, entity_type, surface, [surface])
        return token

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def get_token(self, entity_type: str, surface: str) -> str:
        if entity_type == "PERSON":
            return self._get_person_token(surface)
        if entity_type == "ORGANIZATION":
            return self._get_org_token(surface)
        return self._get_generic_token(entity_type, surface)

    def to_dict(self) -> dict:
        return {"entries": self.entries}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pseudonymize(text: str, detections: list[dict]) -> tuple[str, dict]:
    """
    Replace each detected span in *text* with a placeholder token.

    Args:
        text:       original document text
        detections: list of detection dicts from detect.detect()

    Returns:
        masked_text: text with real values replaced by [TYPE_N] tokens
        pmap:        the placeholder map (dict with 'entries' key, JSON-serialisable)

    Spans are replaced from LAST to FIRST to preserve earlier char offsets.
    Token numbers are assigned in first-appearance (start offset ascending) order,
    ensuring deterministic output for a given input.
    """
    pmap = _PseudonymMap()

    # Process in start-offset order (first-appearance) for deterministic numbering
    ordered = sorted(detections, key=lambda d: d["start"])

    # Assign tokens, building the map
    span_tokens: list[tuple[int, int, str]] = []
    for d in ordered:
        token = pmap.get_token(d["entity_type"], d["text"])
        span_tokens.append((d["start"], d["end"], token))

    # Replace spans from LAST to FIRST (preserves earlier offsets)
    masked = text
    for start, end, token in reversed(span_tokens):
        masked = masked[:start] + token + masked[end:]

    return masked, pmap.to_dict()
