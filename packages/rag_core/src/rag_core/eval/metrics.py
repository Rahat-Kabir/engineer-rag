from __future__ import annotations


def hit_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> bool:
    """True if any expected chunk appears in the top-k retrieved chunks."""
    return any(eid in retrieved_ids[:k] for eid in expected_ids)


def first_hit_rank(retrieved_ids: list[str], expected_ids: list[str]) -> int | None:
    """1-indexed rank of the first expected chunk in retrieved. None if no hit."""
    for i, rid in enumerate(retrieved_ids, 1):
        if rid in expected_ids:
            return i
    return None


def reciprocal_rank(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """1/rank of first hit, 0 if no hit. Used for MRR."""
    rank = first_hit_rank(retrieved_ids, expected_ids)
    return 1.0 / rank if rank else 0.0
