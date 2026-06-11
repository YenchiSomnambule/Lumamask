"""
pipeline.py — Full reversible pseudonymisation round-trip.

Wires together: detect → pseudonymize → ask_claude → restore.
No real values are sent to the Claude API; only placeholder tokens leave
the local machine.
"""

from __future__ import annotations

from .detect import detect
from .pseudonymize import pseudonymize
from .restore import restore
from .llm import ask_claude, DEFAULT_MODEL


def run_pipeline(
    text: str,
    instruction: str,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Run the full pseudonymisation round-trip on *text*.

    Steps
    -----
    1. detect       — find sensitive spans in the original text
    2. pseudonymize — replace spans with tokens; build placeholder map
    3. ask_claude   — send masked text + instruction to Claude
    4. restore      — replace tokens in the reply with real values

    Parameters
    ----------
    text:        Original (unmasked) document text.
    instruction: What the user wants Claude to do (e.g. "Summarise this invoice").
    model:       Claude model string; defaults to DEFAULT_MODEL.

    Returns
    -------
    dict with keys:
        "original"            — the input text, unchanged
        "masked"              — text with all sensitive spans replaced by tokens
        "map"                 — the placeholder map (serialisable dict)
        "ai_reply_tokenised"  — Claude's raw reply (tokens still in place)
        "ai_reply_restored"   — Claude's reply with real values restored
    """
    detections = detect(text)
    masked_text, pmap = pseudonymize(text, detections)
    ai_reply_tokenised = ask_claude(masked_text, instruction, model=model)
    ai_reply_restored = restore(ai_reply_tokenised, pmap)

    return {
        "original": text,
        "masked": masked_text,
        "map": pmap,
        "ai_reply_tokenised": ai_reply_tokenised,
        "ai_reply_restored": ai_reply_restored,
    }
