from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from rag_core.eval.dataset import GoldItem, load_gold
from rag_core.eval.metrics import first_hit_rank, hit_at_k, reciprocal_rank
from rag_core.generation.answer import answer_question
from rag_core.retrieval.search import search


@dataclass
class QuestionResult:
    question: str
    expected: list[str]
    retrieved: list[str]
    is_refusal_q: bool

    # retrieval-question fields
    hit_at_5: bool = False
    hit_at_10: bool = False
    rank: int | None = None
    rr: float = 0.0

    # refusal-question fields
    refused: bool | None = None


@dataclass
class EvalSummary:
    total: int
    retrieval_questions: int
    refusal_questions: int
    recall_at_5: float
    recall_at_10: float
    mrr: float
    refusal_correct: float | None
    per_question: list[QuestionResult] = field(default_factory=list)


def _eval_retrieval_question(item: GoldItem, top_k: int) -> QuestionResult:
    retrieved = search(item.question, limit=top_k)
    retrieved_ids = [r.chunk.chunk_id for r in retrieved]
    return QuestionResult(
        question=item.question,
        expected=list(item.expected_chunk_ids),
        retrieved=retrieved_ids,
        is_refusal_q=False,
        hit_at_5=hit_at_k(retrieved_ids, item.expected_chunk_ids, 5),
        hit_at_10=hit_at_k(retrieved_ids, item.expected_chunk_ids, 10),
        rank=first_hit_rank(retrieved_ids, item.expected_chunk_ids),
        rr=reciprocal_rank(retrieved_ids, item.expected_chunk_ids),
    )


def _eval_refusal_question(item: GoldItem, top_k: int) -> QuestionResult:
    """Refusal questions need the full pipeline: retrieval + LLM."""
    result = answer_question(item.question, top_k=top_k)
    retrieved_ids = [r.chunk.chunk_id for r in result.retrieved]
    # We treat zero-citations as a refusal. Aligns with the answer prompt: when the
    # model can't find an answer in the chunks it produces no [N] markers, so no
    # citations are extracted.
    refused = len(result.citations) == 0
    return QuestionResult(
        question=item.question,
        expected=[],
        retrieved=retrieved_ids,
        is_refusal_q=True,
        refused=refused,
    )


def run_eval(gold_path: Path, top_k: int = 10) -> EvalSummary:
    items = load_gold(gold_path)
    per_question: list[QuestionResult] = []

    for item in items:
        if item.is_refusal:
            per_question.append(_eval_refusal_question(item, top_k))
        else:
            per_question.append(_eval_retrieval_question(item, top_k))

    retrieval_qs = [q for q in per_question if not q.is_refusal_q]
    refusal_qs = [q for q in per_question if q.is_refusal_q]

    n = len(retrieval_qs)
    recall_5 = sum(q.hit_at_5 for q in retrieval_qs) / n if n else 0.0
    recall_10 = sum(q.hit_at_10 for q in retrieval_qs) / n if n else 0.0
    mrr = sum(q.rr for q in retrieval_qs) / n if n else 0.0

    refusal_correct: float | None = None
    if refusal_qs:
        refusal_correct = sum(bool(q.refused) for q in refusal_qs) / len(refusal_qs)

    return EvalSummary(
        total=len(items),
        retrieval_questions=n,
        refusal_questions=len(refusal_qs),
        recall_at_5=recall_5,
        recall_at_10=recall_10,
        mrr=mrr,
        refusal_correct=refusal_correct,
        per_question=per_question,
    )
