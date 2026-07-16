"""Faithfulness eval CLI: measure how often the LLM's answers stay grounded.

Usage:
    uv run python -m scripts.eval_faithfulness
"""
from __future__ import annotations
import sys

from rag_core.config import settings
from rag_core.eval.faithfulness import FaithfulnessSummary, run_faithfulness
from scripts._profile import apply_corpus_profile_flag

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _print_summary(s: FaithfulnessSummary) -> None:
    print(f"\nFaithfulness eval — {s.total} questions")
    print("=" * 60)
    print(f"  Answered: {s.answered}    Refused: {s.refused}\n")

    graded = s.claims_total - s.claims_errored
    if graded:
        print(f"Per-claim (N = {graded} graded claims):")
        print(f"  Supported:    {s.claims_supported / graded:.3f}  ({s.claims_supported} / {graded})")
        print(f"  Partial:      {s.claims_partial / graded:.3f}  ({s.claims_partial} / {graded})")
        print(f"  Unsupported:  {s.claims_unsupported / graded:.3f}  ({s.claims_unsupported} / {graded})   ← hallucination rate")
        if s.claims_errored:
            print(f"  (Judge errors: {s.claims_errored})")
    else:
        print("No claims graded.")

    print(f"\nUncited sentences (no [N] marker): {s.uncited_total}")
    print(f"Parser-skipped (citation marker but no real claim text): {s.parse_skipped_total}")

    if s.answered:
        print(f"\nPer-answer (N = {s.answered}):")
        print(f"  Fully grounded:     {s.fully_grounded_rate:.3f}  ({s.fully_grounded_answers} / {s.answered})")
        print(f"  Has hallucination:  {s.answers_with_hallucination / s.answered:.3f}  ({s.answers_with_hallucination} / {s.answered})")


def _print_bad_cases(s: FaithfulnessSummary) -> None:
    bad = [
        (q, c)
        for q in s.per_question
        for c in q.claims
        if c.verdict in {"no", "partial"}
    ]
    if not bad:
        return
    print(f"\nBad cases ({len(bad)} claims):")
    print("-" * 60)
    for q, c in bad:
        tag = "[unsupported]" if c.verdict == "no" else "[partial]    "
        print(f"  {tag} Q: {q.question[:80]}")
        print(f"               claim: {c.sentence[:140]}")
        print(f"               cited: {', '.join(c.cited_chunk_ids)}\n")


def main() -> None:
    apply_corpus_profile_flag()
    gold_path = settings.gold_path
    if not gold_path.exists():
        print(f"Gold file not found: {gold_path}")
        raise SystemExit(1)

    print(
        f"Corpus: {settings.corpus_profile} — gold set: {gold_path}, "
        f"collection: '{settings.qdrant_collection}'"
    )
    print("Running faithfulness eval. This calls Claude as judge for each cited claim.")
    print("Expect 1–2 minutes for 50 questions.\n")

    summary = run_faithfulness(gold_path, top_k=6)
    _print_summary(summary)
    _print_bad_cases(summary)


if __name__ == "__main__":
    main()
