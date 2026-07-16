import pytest

from rag_core.eval.metrics import first_hit_rank, hit_at_k, reciprocal_rank


def test_hit_at_k_counts_hit_exactly_at_rank_k() -> None:
    retrieved = ["a", "b", "expected", "d"]

    assert hit_at_k(retrieved, ["expected"], k=3) is True


def test_hit_at_k_does_not_count_hit_at_rank_k_plus_one() -> None:
    retrieved = ["a", "b", "expected", "d"]

    assert hit_at_k(retrieved, ["expected"], k=2) is False


def test_first_hit_rank_is_one_indexed() -> None:
    assert first_hit_rank(["first", "second"], ["first"]) == 1
    assert first_hit_rank(["first", "second"], ["second"]) == 2


def test_first_hit_rank_returns_none_when_expected_id_is_absent() -> None:
    assert first_hit_rank(["first", "second"], ["missing"]) is None


def test_reciprocal_rank_returns_inverse_rank_on_hit() -> None:
    assert reciprocal_rank(["a", "b", "expected"], ["expected"]) == pytest.approx(
        1 / 3
    )


def test_reciprocal_rank_returns_zero_on_miss() -> None:
    assert reciprocal_rank(["a", "b"], ["missing"]) == 0.0


def test_multiple_expected_ids_use_earliest_retrieved_position() -> None:
    retrieved = ["other", "expected-later", "expected-earlier-in-list"]
    expected = ["expected-earlier-in-list", "expected-later"]

    assert first_hit_rank(retrieved, expected) == 2
    assert reciprocal_rank(retrieved, expected) == 0.5
