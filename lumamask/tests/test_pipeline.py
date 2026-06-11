"""
test_pipeline.py — Tests for pipeline.run_pipeline() and cli.main().

All tests mock ask_claude so no real network calls are made.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from lumamask.pipeline import run_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TEXT = textwrap.dedent("""\
    Invoice from Acme Corp to John Smith.
    Amount due: $1,500.00
    Contact: john.smith@acme.com
""")


def _mock_ask(masked_text, instruction, model=None):
    """Simulate Claude echoing back a short summary with the tokens intact."""
    return (
        "[ORG_1] issued an invoice to [PERSON_1] for [AMT_1]. "
        "Contact: [EMAIL_1]."
    )


# ---------------------------------------------------------------------------
# pipeline tests
# ---------------------------------------------------------------------------

class TestRunPipeline:

    def test_returns_required_keys(self):
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            result = run_pipeline(SAMPLE_TEXT, "Summarise.")
        assert set(result.keys()) == {
            "original", "masked", "map", "ai_reply_tokenised", "ai_reply_restored"
        }

    def test_original_unchanged(self):
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            result = run_pipeline(SAMPLE_TEXT, "Summarise.")
        assert result["original"] == SAMPLE_TEXT

    def test_masked_has_no_real_values(self):
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            result = run_pipeline(SAMPLE_TEXT, "Summarise.")
        masked = result["masked"]
        assert "John Smith" not in masked
        assert "Acme Corp" not in masked
        assert "$1,500.00" not in masked
        assert "john.smith@acme.com" not in masked

    def test_ai_reply_tokenised_contains_tokens(self):
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            result = run_pipeline(SAMPLE_TEXT, "Summarise.")
        reply = result["ai_reply_tokenised"]
        assert "[ORG_1]" in reply
        assert "[PERSON_1]" in reply

    def test_restored_reply_has_real_values(self):
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            result = run_pipeline(SAMPLE_TEXT, "Summarise.")
        restored = result["ai_reply_restored"]
        assert "Acme Corp" in restored
        assert "John Smith" in restored
        assert "$1,500.00" in restored
        assert "john.smith@acme.com" in restored

    def test_restored_reply_has_no_tokens(self):
        import re
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            result = run_pipeline(SAMPLE_TEXT, "Summarise.")
        assert not re.search(r"\[[A-Z]+_\d+\]", result["ai_reply_restored"])

    def test_map_is_serialisable(self):
        """The map can be round-tripped through JSON without error."""
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            result = run_pipeline(SAMPLE_TEXT, "Summarise.")
        dumped = json.dumps(result["map"])
        loaded = json.loads(dumped)
        assert "entries" in loaded


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:

    def test_rejects_non_txt_file(self, tmp_path):
        from lumamask.cli import main
        doc = tmp_path / "doc.pdf"
        doc.write_text("content", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            main(["--input", str(doc), "--instruction", "Do something."])
        assert exc_info.value.code != 0

    def test_rejects_missing_file(self, tmp_path):
        from lumamask.cli import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--input", str(tmp_path / "ghost.txt"), "--instruction", "Do."])
        assert exc_info.value.code != 0

    def test_prints_four_sections(self, tmp_path, capsys):
        from lumamask.cli import main
        doc = tmp_path / "sample.txt"
        doc.write_text(SAMPLE_TEXT, encoding="utf-8")
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            main(["--input", str(doc), "--instruction", "Summarise."])
        out = capsys.readouterr().out
        assert "(1) WHAT WAS DETECTED" in out
        assert "(2) MASKED VERSION SENT TO AI" in out
        assert "(3) AI REPLY (as received, still masked)" in out
        assert "(4) FINAL ANSWER (restored)" in out

    def test_masked_section_has_no_real_values(self, tmp_path, capsys):
        from lumamask.cli import main
        doc = tmp_path / "sample.txt"
        doc.write_text(SAMPLE_TEXT, encoding="utf-8")
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            main(["--input", str(doc), "--instruction", "Summarise."])
        out = capsys.readouterr().out
        # Extract section 2 (between section 2 header and section 3 header)
        s2_start = out.index("(2) MASKED VERSION SENT TO AI")
        s3_start = out.index("(3) AI REPLY")
        masked_section = out[s2_start:s3_start]
        assert "John Smith" not in masked_section
        assert "Acme Corp" not in masked_section
        assert "$1,500.00" not in masked_section

    def test_restored_section_has_real_values(self, tmp_path, capsys):
        from lumamask.cli import main
        doc = tmp_path / "sample.txt"
        doc.write_text(SAMPLE_TEXT, encoding="utf-8")
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            main(["--input", str(doc), "--instruction", "Summarise."])
        out = capsys.readouterr().out
        s4_start = out.index("(4) FINAL ANSWER (restored)")
        restored_section = out[s4_start:]
        assert "Acme Corp" in restored_section
        assert "John Smith" in restored_section

    def test_save_map_writes_json(self, tmp_path, capsys):
        from lumamask.cli import main
        doc = tmp_path / "sample.txt"
        doc.write_text(SAMPLE_TEXT, encoding="utf-8")
        map_path = tmp_path / "out.map.json"
        with patch("lumamask.pipeline.ask_claude", side_effect=_mock_ask):
            main([
                "--input", str(doc),
                "--instruction", "Summarise.",
                "--save-map", str(map_path),
            ])
        assert map_path.exists()
        loaded = json.loads(map_path.read_text(encoding="utf-8"))
        assert "entries" in loaded
