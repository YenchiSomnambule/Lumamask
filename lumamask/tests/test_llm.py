"""
test_llm.py — Unit tests for llm.ask_claude() using mocked Anthropic client.

These tests NEVER make a real network call.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lumamask.llm import ask_claude, SYSTEM_PROMPT, DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(texts: list[str]) -> MagicMock:
    """Build a fake anthropic Messages response with the given text blocks."""
    blocks = [SimpleNamespace(text=t) for t in texts]
    resp = MagicMock()
    resp.content = blocks
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAskClaude:

    def test_returns_reply_text(self):
        """Normal call: single text block reply is returned as-is."""
        fake_reply = "Here is a summary: [ORG_1] owes [AMT_1]."
        with patch("lumamask.llm.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_response([fake_reply])
            result = ask_claude("masked doc", "Summarise this.")
        assert result == fake_reply

    def test_concatenates_multiple_blocks(self):
        """Multiple text blocks in the response are concatenated in order."""
        with patch("lumamask.llm.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_response(
                ["Part one. ", "Part two."]
            )
            result = ask_claude("masked doc", "Explain.")
        assert result == "Part one. Part two."

    def test_sends_correct_system_prompt(self):
        """The call uses SYSTEM_PROMPT and the masked content in the right shape."""
        import anthropic as _anthropic

        with patch("lumamask.llm.anthropic.Anthropic") as MockClient:
            mock_create = MockClient.return_value.messages.create
            mock_create.return_value = _make_response(["ok"])
            ask_claude("my masked text", "Do something.", model="test-model")

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["system"] == SYSTEM_PROMPT
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        # instruction and masked text should both appear in user content
        assert "Do something." in messages[0]["content"]
        assert "my masked text" in messages[0]["content"]

    def test_default_model_used(self):
        """When no model is specified, DEFAULT_MODEL is used."""
        with patch("lumamask.llm.anthropic.Anthropic") as MockClient:
            mock_create = MockClient.return_value.messages.create
            mock_create.return_value = _make_response(["reply"])
            ask_claude("doc", "instruction")
        assert mock_create.call_args.kwargs["model"] == DEFAULT_MODEL

    def test_api_status_error_raises_runtime(self):
        """APIStatusError is converted to RuntimeError without leaking the key."""
        import anthropic as _anthropic

        err = _anthropic.APIStatusError(
            "Unauthorized",
            response=MagicMock(status_code=401),
            body={"error": {"message": "Invalid API key"}},
        )
        with patch("lumamask.llm.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = err
            with pytest.raises(RuntimeError, match="Claude API error"):
                ask_claude("doc", "instruction")

    def test_connection_error_raises_runtime(self):
        """APIConnectionError is converted to a friendly RuntimeError."""
        import anthropic as _anthropic

        with patch("lumamask.llm.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = (
                _anthropic.APIConnectionError(request=MagicMock())
            )
            with pytest.raises(RuntimeError, match="connect"):
                ask_claude("doc", "instruction")

    def test_tokens_in_reply_pass_through_unchanged(self):
        """Tokens from the AI reply are returned verbatim (restore happens upstream)."""
        tokenised_reply = "Invoice for [ORG_1]. Total: [AMT_1]. Contact [PERSON_1]."
        with patch("lumamask.llm.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_response(
                [tokenised_reply]
            )
            result = ask_claude("masked input", "Summarise.")
        assert result == tokenised_reply
