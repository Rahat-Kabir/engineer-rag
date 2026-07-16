"""Shared --demo / --private flag for the CLI scripts.

Every script accepts an optional corpus-profile flag that overrides
CORPUS_PROFILE (from .env) for that one run:

    uv run python -m scripts.ingest --private
    uv run python -m scripts.eval --demo
"""
from __future__ import annotations
import sys

from rag_core.config import settings


def apply_corpus_profile_flag() -> None:
    """Pop --demo / --private from sys.argv and override settings.corpus_profile.

    The flag is removed from sys.argv so each script's own argument handling
    (query's positional question, inspect's subcommands) stays unchanged.
    """
    demo_requested = "--demo" in sys.argv
    private_requested = "--private" in sys.argv
    if demo_requested and private_requested:
        print("Pass either --demo or --private, not both.")
        sys.exit(1)
    if demo_requested:
        sys.argv.remove("--demo")
        settings.corpus_profile = "demo"
    if private_requested:
        sys.argv.remove("--private")
        settings.corpus_profile = "private"
