"""
llm.py — Claude API integration for Lumamask.

Sends masked (pseudonymised) text to Claude; returns the raw tokenised reply.
Real values are never sent — only the placeholder tokens leave the machine.

Security constraints (from spec §9):
  - NEVER hard-code or print ANTHROPIC_API_KEY.
  - NEVER log or expose the full traceback on API errors.
  - The system prompt MUST instruct Claude to preserve tokens exactly.
"""

from __future__ import annotations

import anthropic

# ---------------------------------------------------------------------------
# Model constant — change here to switch model globally
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# System prompt — CRITICAL: tells Claude to preserve placeholder tokens
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are helping process a business document in which sensitive details have been "
    "replaced with placeholder tokens of the form [TYPE_N] (for example [PERSON_1], "
    "[ORG_1], [AMT_1]). "
    "Treat each token as an opaque identifier standing for a real value you cannot see. "
    "When you refer to those values in your answer, reproduce the token EXACTLY as written, "
    "including the square brackets and underscore — never reword, split, translate, merge, "
    "renumber, or invent tokens. "
    "Answer the user's request normally in all other respects."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ask_claude(
    masked_text: str,
    user_instruction: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Send *masked_text* plus *user_instruction* to Claude and return the raw
    (still-tokenised) reply text.

    The user message is formatted as:
        <instruction>
        ---
        <masked document>

    The system prompt instructs Claude to preserve all [TYPE_N] tokens exactly.

    Parameters
    ----------
    masked_text:       The pseudonymised document (tokens only, no real values).
    user_instruction:  What the user wants Claude to do with the document.
    model:             Claude model string. Defaults to DEFAULT_MODEL.

    Returns
    -------
    str: Concatenated text of all TextBlock objects in the response.

    Raises
    ------
    RuntimeError: On any Anthropic API error (original error type / message
                  included, but API key is never surfaced).
    """
    user_content = f"{user_instruction}\n---\n{masked_text}"

    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.APIStatusError as exc:
        # Surface the HTTP status and message but not the key or full traceback
        raise RuntimeError(
            f"Claude API error {exc.status_code}: {exc.message}"
        ) from None
    except anthropic.APIConnectionError:
        raise RuntimeError(
            "Could not connect to the Claude API. "
            "Check your network connection and ANTHROPIC_API_KEY."
        ) from None
    except anthropic.APIError as exc:
        raise RuntimeError(f"Claude API error: {exc}") from None

    # Concatenate all text blocks (safe even if Claude returns multiple blocks)
    return "".join(
        block.text
        for block in response.content
        if hasattr(block, "text")
    )
