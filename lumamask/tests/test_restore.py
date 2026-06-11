"""
test_restore.py — Unit tests for restore.py (Phase 3).
"""

import pytest
from lumamask.restore import restore


def _pmap(*entries):
    """Build a minimal pmap dict from (token, real_value) pairs."""
    return {
        "entries": [
            {"token": t, "entity_type": "PERSON", "real_value": v, "variants": [v]}
            for t, v in entries
        ]
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_basic_restore():
    """Tokens in AI reply are replaced with correct real values."""
    pmap = _pmap(
        ("[PERSON_1]", "John Smith"),
        ("[ORG_1]",    "Acme Corp"),
        ("[AMT_1]",    "$45,000.00"),
    )
    # Override entity_type to be accurate (doesn't affect restore logic)
    pmap["entries"][1]["entity_type"] = "ORGANIZATION"
    pmap["entries"][2]["entity_type"] = "MONEY_AMOUNT"

    ai_reply = "[ORG_1] owes [AMT_1]; please contact [PERSON_1]."
    result = restore(ai_reply, pmap)

    assert result == "Acme Corp owes $45,000.00; please contact John Smith."


def test_longest_token_first():
    """[AMT_1] and [AMT_11] are each restored to their own correct value."""
    pmap = {
        "entries": [
            {"token": "[AMT_1]",  "entity_type": "MONEY_AMOUNT",
             "real_value": "$100.00", "variants": ["$100.00"]},
            {"token": "[AMT_11]", "entity_type": "MONEY_AMOUNT",
             "real_value": "$9,999.00", "variants": ["$9,999.00"]},
        ]
    }
    ai_reply = "Total A is [AMT_11] and total B is [AMT_1]."
    result = restore(ai_reply, pmap)

    assert result == "Total A is $9,999.00 and total B is $100.00."
    # Ensure no partial corruption
    assert "$100.00" in result
    assert "$9,999.00" in result


def test_unknown_token_raises():
    """A token in the AI reply that is not in the map raises ValueError."""
    pmap = _pmap(("[PERSON_1]", "John Smith"))
    ai_reply = "Contact [PERSON_1] or [PERSON_9]."

    with pytest.raises(ValueError, match=r"\[PERSON_9\]"):
        restore(ai_reply, pmap)


def test_no_token_no_change():
    """A reply containing no tokens is returned unchanged."""
    pmap = _pmap(("[PERSON_1]", "John Smith"))
    ai_reply = "Please review the attached document and respond at your earliest convenience."
    result = restore(ai_reply, pmap)

    assert result == ai_reply
