#!/usr/bin/env python3
"""Typewriter-style cat party display.

Reads party files from the parties/ directory and prints them line by
line with a typewriter effect.  Lines containing '---PAUSE---' stop
and wait for the user to press Enter.

Usage:
    python3 cat_party.py              # show the latest party
    python3 cat_party.py --rewind 1   # show the previous party
    python3 cat_party.py --list       # list all available parties
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

CHAR_DELAY = 0.015  # seconds between characters
FAST_DELAY = 0.003  # faster for whitespace-heavy lines
LINE_DELAY = 0.05  # pause between lines
PAUSE_MARKER = "---PAUSE---"
PARTIES_DIR = Path(__file__).parent / "parties"


def get_parties() -> list[Path]:
    """Return party files sorted by name (oldest first)."""
    if not PARTIES_DIR.is_dir():
        return []
    return sorted(PARTIES_DIR.glob("*.txt"))


def typewriter(line: str) -> None:
    """Print a line character by character."""
    decorators = line.count("~") + line.count("*") + line.count(".")
    delay = FAST_DELAY if decorators > len(line) * 0.5 else CHAR_DELAY
    for ch in line:
        sys.stdout.write(ch)
        sys.stdout.flush()
        if ch in (" ", "\t"):
            time.sleep(delay * 0.3)
        elif ch in ("~", "*", ".", "+", "-", "="):
            time.sleep(delay * 0.5)
        else:
            time.sleep(delay)


def display(party_file: Path) -> None:
    """Display a party file with typewriter effect."""
    lines = party_file.read_text().splitlines()
    for line in lines:
        if line.strip() == PAUSE_MARKER:
            print()
            input("  [ Press Enter to continue... ] ")
            print()
            continue
        typewriter(line)
        print()
        time.sleep(LINE_DELAY)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cat party viewer.")
    parser.add_argument(
        "--rewind",
        type=int,
        default=0,
        metavar="N",
        help="Go back N parties (0 = latest, 1 = previous, etc.)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_parties",
        help="List all available parties and exit",
    )
    args = parser.parse_args()

    parties = get_parties()
    if not parties:
        print(f"No party files found in {PARTIES_DIR}/")
        sys.exit(1)

    if args.list_parties:
        print(f"Available parties ({len(parties)} total):\n")
        for i, p in enumerate(reversed(parties)):
            label = "(latest)" if i == 0 else f"(--rewind {i})"
            print(f"  {p.name}  {label}")
        return

    idx = len(parties) - 1 - args.rewind
    if idx < 0 or idx >= len(parties):
        print(f"Cannot rewind {args.rewind} — only {len(parties)} parties exist.")
        sys.exit(1)

    chosen = parties[idx]
    print(f"  Playing: {chosen.name}\n")
    display(chosen)


if __name__ == "__main__":
    main()
