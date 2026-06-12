"""
test_app.py — Tests for the Flask UI backend (lumamask-ui/app.py).

run_pipeline is mocked throughout; no spaCy detection or network calls happen.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

import app as app_module
from app import (
    app,
    count_possible_misses,
    find_available_port,
    summarise_detections,
)


FAKE_RESULT = {
    "original": (
        "Invoice from Acme Corp to John Smith.\n"
        "Amount due: $1,500.00\n"
        "Contact: john.smith@acme.com\n"
    ),
    "masked": (
        "Invoice from [ORG_1] to [PERSON_1].\n"
        "Amount due: [AMT_1]\n"
        "Contact: [EMAIL_1]\n"
    ),
    "map": {
        "entries": [
            {"token": "[ORG_1]", "entity_type": "ORGANIZATION",
             "real_value": "Acme Corp", "variants": ["Acme Corp"]},
            {"token": "[PERSON_1]", "entity_type": "PERSON",
             "real_value": "John Smith", "variants": ["John Smith"]},
            {"token": "[AMT_1]", "entity_type": "MONEY_AMOUNT",
             "real_value": "$1,500.00", "variants": ["$1,500.00"]},
            {"token": "[EMAIL_1]", "entity_type": "EMAIL_ADDRESS",
             "real_value": "john.smith@acme.com",
             "variants": ["john.smith@acme.com"]},
        ]
    },
    "ai_reply_tokenised": "[ORG_1] billed [PERSON_1] [AMT_1].",
    "ai_reply_restored": "Acme Corp billed John Smith $1,500.00.",
}

VALID_PAYLOAD = {
    "api_key": "sk-ant-test",
    "text": FAKE_RESULT["original"],
    "instruction": "Summarise.",
}


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

class TestIndex:

    def test_serves_html(self, client):
        res = client.get("/")
        assert res.status_code == 200
        body = res.get_data(as_text=True)
        assert "Lumamask" in body
        assert "Sensitive document processor" in body


# ---------------------------------------------------------------------------
# POST /api/run — validation
# ---------------------------------------------------------------------------

class TestValidation:

    def test_missing_api_key(self, client):
        payload = dict(VALID_PAYLOAD, api_key="")
        res = client.post("/api/run", json=payload)
        assert res.status_code == 400
        assert "API key" in res.get_json()["error"]

    def test_missing_text(self, client):
        payload = dict(VALID_PAYLOAD, text="   ")
        res = client.post("/api/run", json=payload)
        assert res.status_code == 400
        assert "Document text" in res.get_json()["error"]

    def test_missing_instruction(self, client):
        payload = dict(VALID_PAYLOAD, instruction="")
        res = client.post("/api/run", json=payload)
        assert res.status_code == 400
        assert "Instruction" in res.get_json()["error"]

    def test_non_json_body(self, client):
        res = client.post("/api/run", data="not json",
                          content_type="text/plain")
        assert res.status_code == 400
        assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# POST /api/run — success path
# ---------------------------------------------------------------------------

class TestRunSuccess:

    def test_response_shape(self, client):
        with patch.object(app_module, "run_pipeline", return_value=FAKE_RESULT):
            res = client.post("/api/run", json=VALID_PAYLOAD)
        assert res.status_code == 200
        data = res.get_json()
        assert set(data.keys()) == {
            "detection_summary", "detection_samples", "possible_misses",
            "masked", "ai_reply_masked", "final_answer",
        }

    def test_summary_counts_from_map(self, client):
        with patch.object(app_module, "run_pipeline", return_value=FAKE_RESULT):
            data = client.post("/api/run", json=VALID_PAYLOAD).get_json()
        assert data["detection_summary"] == {
            "ORGANIZATION": 1, "PERSON": 1,
            "MONEY_AMOUNT": 1, "EMAIL_ADDRESS": 1,
        }

    def test_samples_from_map(self, client):
        with patch.object(app_module, "run_pipeline", return_value=FAKE_RESULT):
            data = client.post("/api/run", json=VALID_PAYLOAD).get_json()
        assert data["detection_samples"]["PERSON"] == ["John Smith"]
        assert data["detection_samples"]["MONEY_AMOUNT"] == ["$1,500.00"]

    def test_clean_masked_text_has_no_misses(self, client):
        with patch.object(app_module, "run_pipeline", return_value=FAKE_RESULT):
            data = client.post("/api/run", json=VALID_PAYLOAD).get_json()
        assert data["possible_misses"] == 0

    def test_placeholder_map_not_exposed(self, client):
        """Security (blueprint §11): token ↔ value map never reaches the client."""
        with patch.object(app_module, "run_pipeline", return_value=FAKE_RESULT):
            data = client.post("/api/run", json=VALID_PAYLOAD).get_json()
        assert "map" not in data

    def test_masked_and_replies_passed_through(self, client):
        with patch.object(app_module, "run_pipeline", return_value=FAKE_RESULT):
            data = client.post("/api/run", json=VALID_PAYLOAD).get_json()
        assert data["masked"] == FAKE_RESULT["masked"]
        assert data["ai_reply_masked"] == FAKE_RESULT["ai_reply_tokenised"]
        assert data["final_answer"] == FAKE_RESULT["ai_reply_restored"]

    def test_leftover_pii_in_masked_is_flagged(self, client):
        leaky = dict(FAKE_RESULT)
        leaky["masked"] = FAKE_RESULT["masked"] + "Backup contact: jane@other.org\n"
        with patch.object(app_module, "run_pipeline", return_value=leaky):
            data = client.post("/api/run", json=VALID_PAYLOAD).get_json()
        assert data["possible_misses"] == 1


# ---------------------------------------------------------------------------
# POST /api/run — error mapping and env hygiene
# ---------------------------------------------------------------------------

class TestErrorsAndEnv:

    def test_value_error_maps_to_400(self, client):
        with patch.object(app_module, "run_pipeline",
                          side_effect=ValueError("bad input")):
            res = client.post("/api/run", json=VALID_PAYLOAD)
        assert res.status_code == 400
        assert res.get_json()["error"] == "bad input"

    def test_runtime_error_maps_to_502(self, client):
        with patch.object(app_module, "run_pipeline",
                          side_effect=RuntimeError("Claude API error 401: Invalid API key")):
            res = client.post("/api/run", json=VALID_PAYLOAD)
        assert res.status_code == 502
        assert "401" in res.get_json()["error"]

    def test_api_key_removed_from_env_after_success(self, client):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with patch.object(app_module, "run_pipeline", return_value=FAKE_RESULT):
            client.post("/api/run", json=VALID_PAYLOAD)
        assert "ANTHROPIC_API_KEY" not in os.environ

    def test_api_key_removed_from_env_after_error(self, client):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with patch.object(app_module, "run_pipeline",
                          side_effect=RuntimeError("boom")):
            client.post("/api/run", json=VALID_PAYLOAD)
        assert "ANTHROPIC_API_KEY" not in os.environ

    def test_preexisting_api_key_is_restored(self, client):
        os.environ["ANTHROPIC_API_KEY"] = "operator-key"
        try:
            with patch.object(app_module, "run_pipeline", return_value=FAKE_RESULT):
                client.post("/api/run", json=VALID_PAYLOAD)
            assert os.environ["ANTHROPIC_API_KEY"] == "operator-key"
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_unexpected_exception_returns_json_500(self, client):
        """Never leak a raw HTML 500 page (blueprint §12.4)."""
        with patch.object(app_module, "run_pipeline",
                          side_effect=KeyError("totally unexpected")):
            res = client.post("/api/run", json=VALID_PAYLOAD)
        assert res.status_code == 500
        data = res.get_json()
        assert data is not None
        assert "error" in data
        # Generic message — must not echo internals or the API key
        assert "sk-ant" not in data["error"]
        assert "totally unexpected" not in data["error"]

    def test_env_clean_after_unexpected_exception(self, client):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with patch.object(app_module, "run_pipeline",
                          side_effect=KeyError("boom")):
            client.post("/api/run", json=VALID_PAYLOAD)
        assert "ANTHROPIC_API_KEY" not in os.environ


# ---------------------------------------------------------------------------
# find_available_port
# ---------------------------------------------------------------------------

class TestFindAvailablePort:

    def test_returns_a_bindable_port(self):
        import socket
        port = find_available_port()
        with socket.socket() as s:
            s.bind(("127.0.0.1", port))  # must not raise

    def test_falls_back_when_preferred_port_is_taken(self):
        import socket
        with socket.socket() as blocker:
            blocker.bind(("127.0.0.1", 0))
            taken = blocker.getsockname()[1]
            blocker.listen(1)
            port = find_available_port(preferred=taken)
        assert port != taken

    def test_uses_preferred_port_when_free(self):
        import socket
        # Find a free port first, then ask for it as preferred
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            free = probe.getsockname()[1]
        assert find_available_port(preferred=free) == free


# ---------------------------------------------------------------------------
# start_prewarm_thread
# ---------------------------------------------------------------------------

class TestPrewarm:

    def test_starts_daemon_thread_that_runs_prewarm(self):
        import threading
        called = threading.Event()
        with patch.object(app_module, "_prewarm", called.set):
            t = app_module.start_prewarm_thread()
            assert t.daemon is True
            assert called.wait(timeout=5.0)

    def test_prewarm_swallows_failures(self):
        """A broken analyzer load must not crash the thread."""
        with patch.dict(sys.modules, {"lumamask.detect": None}):
            app_module._prewarm()  # must not raise


# ---------------------------------------------------------------------------
# count_possible_misses
# ---------------------------------------------------------------------------

class TestCountPossibleMisses:

    def test_fully_masked_text_is_clean(self):
        assert count_possible_misses(
            "Invoice [INV_1] from [ORG_1], total [AMT_1], pay to [IBAN_1]."
        ) == 0

    def test_leftover_email(self):
        assert count_possible_misses("Contact bob@example.com today.") == 1

    def test_leftover_currency_amount(self):
        assert count_possible_misses("Total due: $4,250.00") == 1

    def test_unsigned_grouped_amount(self):
        # Documented detector gap (detect.py): amounts without currency marker
        assert count_possible_misses("Total: 45,000.00") == 1

    def test_leftover_ssn(self):
        assert count_possible_misses("SSN 123-45-6789 on file.") == 1

    def test_iban_counted_once_despite_digit_run_overlap(self):
        # The 14-digit run inside the IBAN must not be double-counted
        assert count_possible_misses("Pay to GB82WEST12345698765432.") == 1

    def test_multiple_distinct_leftovers(self):
        text = "Email a@b.co or wire $1,000.00 to account 123456789."
        assert count_possible_misses(text) == 3

    def test_short_numbers_and_dates_ignored(self):
        assert count_possible_misses(
            "Page 3 of 12, issued 2026-06-11, net 30 days."
        ) == 0


# ---------------------------------------------------------------------------
# summarise_detections
# ---------------------------------------------------------------------------

class TestSummariseDetections:

    def test_counts_and_samples(self):
        counts, samples = summarise_detections(FAKE_RESULT["map"])
        assert counts["PERSON"] == 1
        assert samples["EMAIL_ADDRESS"] == ["john.smith@acme.com"]

    def test_samples_capped_per_type(self):
        pmap = {"entries": [
            {"token": f"[AMT_{i}]", "entity_type": "MONEY_AMOUNT",
             "real_value": f"${i},000.00", "variants": []}
            for i in range(1, 9)
        ]}
        counts, samples = summarise_detections(pmap)
        assert counts["MONEY_AMOUNT"] == 8
        assert len(samples["MONEY_AMOUNT"]) == 5

    def test_empty_map(self):
        counts, samples = summarise_detections({"entries": []})
        assert counts == {}
        assert samples == {}
