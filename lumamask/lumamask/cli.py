"""
cli.py — Command-line interface for Lumamask.

Usage
-----
    python -m lumamask.cli --input <file.txt> --instruction "Summarise this invoice"
    python -m lumamask.cli --input <file.txt> --instruction "..." --save-map output.map.json

Prints four clearly labelled sections:
    (1) WHAT WAS DETECTED
    (2) MASKED VERSION SENT TO AI
    (3) AI REPLY (as received, still masked)
    (4) FINAL ANSWER (restored)

Security constraints:
    - NEVER prints ANTHROPIC_API_KEY.
    - The placeholder map is NOT written to disk unless --save-map is specified.
    - Only .txt input is supported in this MVP.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .pipeline import run_pipeline
from .llm import DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_SEP = "=" * 70


def _section(number: int, title: str, body: str) -> None:
    print(f"\n{_SEP}")
    print(f"({number}) {title}")
    print(_SEP)
    print(body)


def _detection_summary(pmap: dict) -> str:
    """Return a human-readable count of detected entities by type."""
    counts: Counter = Counter()
    for entry in pmap.get("entries", []):
        counts[entry["entity_type"]] += 1
    if not counts:
        return "  No sensitive entities detected."
    lines = [f"  {count} {etype}" for etype, count in sorted(counts.items())]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="lumamask",
        description=(
            "Pseudonymise a .txt business document, send the masked version "
            "to Claude, and restore real values in the reply."
        ),
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        metavar="FILE",
        help="Path to the input .txt file.",
    )
    parser.add_argument(
        "--instruction", "-n",
        required=True,
        metavar="TEXT",
        help="Instruction for Claude (e.g. 'Summarise this invoice').",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        metavar="MODEL",
        help=f"Claude model string (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--save-map",
        metavar="PATH",
        default=None,
        help=(
            "Write the placeholder map to this JSON file. "
            "WARNING: the map contains real values — keep it private and "
            "do not commit it. (Default: do not write to disk.)"
        ),
    )

    args = parser.parse_args(argv)

    # --- validate input file -----------------------------------------------
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if input_path.suffix.lower() != ".txt":
        print(
            "Error: only .txt files are supported in this version. "
            f"Got: {input_path.suffix or '(no extension)'}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        text = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error reading file: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- run pipeline -------------------------------------------------------
    try:
        result = run_pipeline(text, args.instruction, model=args.model)
    except RuntimeError as exc:
        # API errors from llm.py — friendly message, no key leak
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- print the four labelled sections -----------------------------------
    _section(1, "WHAT WAS DETECTED", _detection_summary(result["map"]))
    _section(2, "MASKED VERSION SENT TO AI", result["masked"])
    _section(3, "AI REPLY (as received, still masked)", result["ai_reply_tokenised"])
    _section(4, "FINAL ANSWER (restored)", result["ai_reply_restored"])
    print(f"\n{_SEP}")

    # --- optional map save --------------------------------------------------
    if args.save_map:
        map_path = Path(args.save_map)
        try:
            map_path.write_text(
                json.dumps(result["map"], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"\nPlaceholder map saved to: {map_path}")
            print("WARNING: this file contains real values — keep it private.")
        except OSError as exc:
            print(f"Warning: could not write map file: {exc}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    main()
