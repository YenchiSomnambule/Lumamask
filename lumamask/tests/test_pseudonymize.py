"""
test_pseudonymize.py — Unit tests for pseudonymize.py (Phase 3).

Detection recall notes (Phase 1 exit check, synthetic test set — 3 documents):
  p1_invoice_01.txt : ~90% recall. FP: "Bill", "ON", "Invoice Date:" as ORG.
  p1_quote_01.txt   : ~90% recall. FP: "BC", service-line descriptions as ORG.
  p1_letter_01.txt  : ~90% recall. FP: "University Avenue" as ORG, "Albert Street"
                      as PERSON. NOTE: 2nd occurrence of INV-00391 tagged LOCATION
                      by spaCy (different position → not an overlap conflict, a
                      recall gap to address in Phase 4).
  Overall synthetic recall: ~90%. Main residual miss: unsigned amounts and
  second-occurrence invoice refs captured as LOCATION by spaCy NER.
"""

import pytest
from lumamask.pseudonymize import pseudonymize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _det(entity_type, start, end, text, score=0.85):
    return {"entity_type": entity_type, "start": start, "end": end,
            "text": text, "score": score}


def _get_entry(pmap, token):
    for e in pmap["entries"]:
        if e["token"] == token:
            return e
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_basic_masking():
    """One name, one org, one amount → correct token formats; map has 3 entries."""
    text = "John Smith works at Acme Corp and owes $45,000.00."
    detections = [
        _det("PERSON",        0,  10, "John Smith"),
        _det("ORGANIZATION", 20,  29, "Acme Corp"),
        _det("MONEY_AMOUNT", 39,  49, "$45,000.00"),
    ]
    masked, pmap = pseudonymize(text, detections)

    assert "[PERSON_1]" in masked
    assert "[ORG_1]" in masked
    assert "[AMT_1]" in masked
    assert "John Smith" not in masked
    assert "Acme Corp" not in masked
    assert "$45,000.00" not in masked
    assert len(pmap["entries"]) == 3


def test_coref_person_variants():
    """John Smith, Mr. Smith, Smith → all [PERSON_1]; map entry has all 3 variants."""
    text = "John Smith sent the invoice. Mr. Smith signed it. Smith approved."
    detections = [
        _det("PERSON",  0, 10, "John Smith"),
        _det("PERSON", 28, 37, "Mr. Smith"),
        _det("PERSON", 49, 54, "Smith"),
    ]
    masked, pmap = pseudonymize(text, detections)

    assert masked.count("[PERSON_1]") == 3
    assert "[PERSON_2]" not in masked

    entry = _get_entry(pmap, "[PERSON_1]")
    assert entry is not None
    assert "John Smith" in entry["variants"]
    assert "Mr. Smith" in entry["variants"]
    assert "Smith" in entry["variants"]


def test_coref_distinct_people():
    """John Smith and Jane Smith → [PERSON_1] and [PERSON_2] (must NOT merge)."""
    text = "John Smith and Jane Smith signed the contract."
    detections = [
        _det("PERSON",  0, 10, "John Smith"),
        _det("PERSON", 15, 25, "Jane Smith"),
    ]
    masked, pmap = pseudonymize(text, detections)

    assert "[PERSON_1]" in masked
    assert "[PERSON_2]" in masked
    assert "John Smith" not in masked
    assert "Jane Smith" not in masked
    assert len([e for e in pmap["entries"] if e["entity_type"] == "PERSON"]) == 2


def test_coref_ambiguous_bare_surname():
    """
    John Smith, Sarah Smith, then bare 'Smith' → Smith gets its own token
    and is flagged ambiguous=True. Must NOT merge into either known person.
    """
    text = "John Smith and Sarah Smith met. Smith was also present."
    detections = [
        _det("PERSON",  0, 10, "John Smith"),
        _det("PERSON", 15, 26, "Sarah Smith"),
        _det("PERSON", 32, 37, "Smith"),
    ]
    masked, pmap = pseudonymize(text, detections)

    # All three should be distinct tokens
    assert "[PERSON_1]" in masked
    assert "[PERSON_2]" in masked
    assert "[PERSON_3]" in masked

    # The bare "Smith" entry must be flagged ambiguous
    smith_entry = _get_entry(pmap, "[PERSON_3]")
    assert smith_entry is not None
    assert smith_entry.get("ambiguous") is True

    # Real values must not appear in masked text
    assert "John Smith" not in masked
    assert "Sarah Smith" not in masked


def test_coref_org_suffixes():
    """Acme Corp and Acme Corporation → both [ORG_1]."""
    text = "Acme Corp sent the quote. Acme Corporation is the vendor."
    detections = [
        _det("ORGANIZATION",  0,  9, "Acme Corp"),
        _det("ORGANIZATION", 25, 42, "Acme Corporation"),
    ]
    masked, pmap = pseudonymize(text, detections)

    assert masked.count("[ORG_1]") == 2
    assert "[ORG_2]" not in masked
    assert len([e for e in pmap["entries"] if e["entity_type"] == "ORGANIZATION"]) == 1


def test_distinct_amounts():
    """$45,000 and $1,200 → [AMT_1] and [AMT_2]."""
    text = "The fee is $45,000 and the retainer is $1,200."
    detections = [
        _det("MONEY_AMOUNT", 11, 18, "$45,000"),
        _det("MONEY_AMOUNT", 39, 45, "$1,200"),
    ]
    masked, pmap = pseudonymize(text, detections)

    assert "[AMT_1]" in masked
    assert "[AMT_2]" in masked
    assert "$45,000" not in masked
    assert "$1,200" not in masked
    assert len([e for e in pmap["entries"] if e["entity_type"] == "MONEY_AMOUNT"]) == 2


def test_identical_amounts():
    """$500 appearing twice → both become [AMT_1]; only one map entry."""
    text = "Invoice A: $500. Invoice B: $500."
    detections = [
        _det("MONEY_AMOUNT", 11, 15, "$500"),
        _det("MONEY_AMOUNT", 28, 32, "$500"),
    ]
    masked, pmap = pseudonymize(text, detections)

    assert masked.count("[AMT_1]") == 2
    assert "[AMT_2]" not in masked
    assert len([e for e in pmap["entries"] if e["entity_type"] == "MONEY_AMOUNT"]) == 1


def test_ordering_deterministic():
    """Same input run twice → identical masked text and identical map."""
    text = "Alice Brown at Globex Corp owes $9,000.00 to Bob Carter."
    detections = [
        _det("PERSON",        0, 11, "Alice Brown"),
        _det("ORGANIZATION", 15, 26, "Globex Corp"),
        _det("MONEY_AMOUNT", 31, 40, "$9,000.00"),
        _det("PERSON",       44, 54, "Bob Carter"),
    ]
    masked1, pmap1 = pseudonymize(text, detections)
    masked2, pmap2 = pseudonymize(text, detections)

    assert masked1 == masked2
    assert pmap1 == pmap2


def test_no_real_value_leaks():
    """No real values (names, amounts, emails) appear in masked_text."""
    text = (
        "Dr. Emily Watson of Pinnacle Ltd. will invoice $3,500.00 "
        "to contact@pinnacle.com."
    )
    detections = [
        _det("PERSON",        0, 16, "Dr. Emily Watson"),
        _det("ORGANIZATION", 20, 32, "Pinnacle Ltd."),
        _det("MONEY_AMOUNT", 47, 56, "$3,500.00"),
        _det("EMAIL_ADDRESS", 60, 80, "contact@pinnacle.com"),
    ]
    masked, pmap = pseudonymize(text, detections)

    real_values = ["Emily Watson", "Pinnacle", "$3,500.00", "contact@pinnacle.com"]
    for val in real_values:
        assert val not in masked, f"Real value leaked into masked text: {val!r}"


def test_coref_person_initial():
    """
    J. Smith should merge with John Smith (spec §4.2 explicit example).
    Spec states: "John Smith", "Mr. Smith", "J. Smith", "Smith" → all [PERSON_1].
    """
    text = "John Smith sent the invoice. J. Smith signed it. Mr. Smith approved."
    detections = [
        _det("PERSON",  0, 10, "John Smith"),
        _det("PERSON", 28, 36, "J. Smith"),
        _det("PERSON", 48, 57, "Mr. Smith"),
    ]
    masked, pmap = pseudonymize(text, detections)

    assert masked.count("[PERSON_1]") == 3
    assert "[PERSON_2]" not in masked

    entry = _get_entry(pmap, "[PERSON_1]")
    assert "John Smith" in entry["variants"]
    assert "J. Smith"   in entry["variants"]
    assert "Mr. Smith"  in entry["variants"]


def test_coref_initial_ambiguous_with_two_people():
    """
    J. Smith should NOT merge when both John and Jane Smith are known.
    In this case J. is ambiguous → new token, ambiguous=True.
    """
    text = "John Smith and Jane Smith met. J. Smith was present."
    detections = [
        _det("PERSON",  0, 10, "John Smith"),
        _det("PERSON", 15, 25, "Jane Smith"),
        _det("PERSON", 31, 39, "J. Smith"),
    ]
    masked, pmap = pseudonymize(text, detections)

    # Three distinct tokens
    assert "[PERSON_1]" in masked
    assert "[PERSON_2]" in masked
    assert "[PERSON_3]" in masked

    # J. Smith must be ambiguous
    j_entry = _get_entry(pmap, "[PERSON_3]")
    assert j_entry is not None
    assert j_entry.get("ambiguous") is True
