"""
test_roundtrip.py — Full pipeline round-trip test (Phase 3).

IMPORTANT: This test calls detect() which loads the spaCy model.
The session-scoped 'warm_analyzer' fixture in conftest.py ensures the model
is loaded once before this test runs.

NO network calls are made — the AI reply is simulated.
"""

import pytest
from lumamask.detect import detect
from lumamask.pseudonymize import pseudonymize
from lumamask.restore import restore


def test_full_roundtrip_simulated():
    """
    Full round-trip WITHOUT any network call.

    1. Original text with several entities, including a person referred 3 ways.
    2. detect → pseudonymize → assert no real value in masked text.
    3. Simulate an AI reply reusing the tokens.
    4. restore the simulated reply.
    5. Assert real values are correctly restored.
    """
    original = (
        "Invoice INV-00123 from Acme Corp is addressed to John Smith. "
        "Mr. Smith approved the total of $45,000.00. "
        "Please confirm with Smith directly at j.smith@acmecorp.com."
    )

    # Step 1: detect
    detections = detect(original)
    assert len(detections) > 0, "detect() returned no results"

    # Step 2: pseudonymize
    masked, pmap = pseudonymize(original, detections)

    # Assert no real values leaked into masked text
    sensitive = ["John Smith", "Acme Corp", "$45,000.00",
                 "INV-00123", "j.smith@acmecorp.com"]
    for val in sensitive:
        assert val not in masked, f"Real value leaked into masked text: {val!r}"

    # Assert tokens are present
    assert "[" in masked and "_" in masked, "No tokens found in masked text"

    # Step 3: build a simulated AI reply that reuses the tokens from the map
    # We use the actual tokens assigned during masking
    token_lookup = {e["real_value"]: e["token"] for e in pmap["entries"]}

    # Find the tokens we expect to be in the map
    inv_token    = next((e["token"] for e in pmap["entries"]
                         if e["entity_type"] == "INVOICE_NUMBER"), None)
    org_token    = next((e["token"] for e in pmap["entries"]
                         if e["entity_type"] == "ORGANIZATION"), None)
    person_token = next((e["token"] for e in pmap["entries"]
                         if e["entity_type"] == "PERSON"
                         and "John Smith" in e.get("variants", [])), None)
    amt_token    = next((e["token"] for e in pmap["entries"]
                         if e["entity_type"] == "MONEY_AMOUNT"), None)
    email_token  = next((e["token"] for e in pmap["entries"]
                         if e["entity_type"] == "EMAIL_ADDRESS"), None)

    # Confirm coreference: "Mr. Smith" and "Smith" share person_token with "John Smith"
    if person_token:
        person_entry = next(e for e in pmap["entries"] if e["token"] == person_token)
        variants = person_entry.get("variants", [])
        assert "Mr. Smith" in variants or "Smith" in variants, (
            "Coreference failed: Mr. Smith / Smith should share token with John Smith. "
            f"Actual variants: {variants}"
        )

    # Build simulated AI reply using the actual tokens
    simulated_reply = (
        f"{org_token} issued {inv_token} to {person_token}. "
        f"The amount {amt_token} is due. Contact {person_token} at {email_token}."
    )

    # Step 4: restore
    restored = restore(simulated_reply, pmap)

    # Step 5: assert real values are back
    assert "Acme Corp" in restored
    assert "INV-00123" in restored
    assert "John Smith" in restored
    assert "$45,000.00" in restored
    assert "j.smith@acmecorp.com" in restored
    assert "[" not in restored or "_" not in restored.split("[")[-1].split("]")[0], \
        "Unreplaced tokens remain in restored text"
