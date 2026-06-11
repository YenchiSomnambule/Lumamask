"""
restore.py — Restore real values from a placeholder map into AI reply text.

Key invariants (spec §4.5):
  - Longest tokens replaced first to avoid partial matches ([AMT_1] vs [AMT_11]).
  - Unknown token guard: raises ValueError if AI invented or modified a token.
  - Text with no tokens is returned unchanged.
"""

from __future__ import annotations
import re

_TOKEN_PATTERN = re.compile(r"\[[A-Z]+_\d+\]")


def restore(ai_text: str, pmap: dict) -> str:
    """
    Replace every placeholder token in *ai_text* with its real_value from *pmap*.

    Args:
        ai_text: the AI reply, still containing [TYPE_N] tokens
        pmap:    the placeholder map dict (as returned by pseudonymize())

    Returns:
        The AI reply with all tokens replaced by their real values.

    Raises:
        ValueError: if *ai_text* contains a token not present in *pmap*
                    (unknown-token guard — the AI may have invented a token).
    """
    entries = pmap.get("entries", [])
    token_map: dict[str, str] = {e["token"]: e["real_value"] for e in entries}

    # Unknown-token guard: scan for anything matching [TYPE_N] not in our map
    found_tokens = set(_TOKEN_PATTERN.findall(ai_text))
    unknown = found_tokens - set(token_map.keys())
    if unknown:
        raise ValueError(
            f"Unknown token(s) in AI reply not present in placeholder map: "
            f"{sorted(unknown)}. "
            f"The AI may have invented, renumbered, or modified a token."
        )

    if not token_map:
        return ai_text

    # Sort tokens longest-first to prevent [AMT_1] matching inside [AMT_11]
    sorted_tokens = sorted(token_map.keys(), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(t) for t in sorted_tokens))
    return pattern.sub(lambda m: token_map[m.group(0)], ai_text)
