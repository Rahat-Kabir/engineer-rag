from __future__ import annotations
from pathlib import Path

from rag_core.eval.run import EvalSummary, QuestionResult, run_eval

GOLD_PATH = Path("data/eval/gold.jsonl")


def _print_per_question(per_question: list[QuestionResult]) -> None:
    print("Per-question:")
    for q in per_question:
        if q.is_refusal_q:
            tag = "[refuse-ok]" if q.refused else "[refuse-FAIL]"
            print(f"  {tag}  {q.question}")
            if not q.refused:
                print(f"               (top-3 retrieved: {', '.join(q.retrieved[:3])})")
            continue
        if q.hit_at_5:
            print(f"  [hit@{q.rank}]    {q.question}")
        elif q.hit_at_10:
            print(f"  [hit@{q.rank} >5] {q.question}")
        else:
            print(f"  [miss]     {q.question}")
            print(f"             expected: {', '.join(q.expected)}")
            print(f"             top-5:    {', '.join(q.retrieved[:5])}")


def _print_summary(s: EvalSummary) -> None:
    print(f"Eval results — {s.total} questions, top-K = 10")
    print("=" * 60)
    print()
    print(f"Retrieval ({s.retrieval_questions} questions):")
    print(f"  Recall@5:   {s.recall_at_5:.3f}  ({int(s.recall_at_5 * s.retrieval_questions)}/{s.retrieval_questions})")
    print(f"  Recall@10:  {s.recall_at_10:.3f}  ({int(s.recall_at_10 * s.retrieval_questions)}/{s.retrieval_questions})")
    print(f"  MRR:        {s.mrr:.3f}")
    if s.refusal_correct is not None:
        print()
        print(f"Refusal ({s.refusal_questions} questions):")
        n_ok = int(round(s.refusal_correct * s.refusal_questions))
        print(f"  Refusal-correct: {s.refusal_correct:.3f}  ({n_ok}/{s.refusal_questions})")
    print()


def main() -> None:
    if not GOLD_PATH.exists():
        print(f"Gold file not found: {GOLD_PATH}")
        raise SystemExit(1)

    summary = run_eval(GOLD_PATH, top_k=10)
    _print_summary(summary)
    _print_per_question(summary.per_question)


if __name__ == "__main__":
    main()
