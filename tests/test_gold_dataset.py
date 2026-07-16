import json

import pytest

from rag_core.eval.dataset import GoldItem, load_gold


def test_load_gold_skips_blank_lines_and_comments(tmp_path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    gold_path.write_text(
        "\n"
        "# This line is a comment.\n"
        '{"question": "What is RRF?", "expected_chunk_ids": ["doc#1"]}\n'
        "   \n"
        "# Another comment.\n"
        '{"question": "Unknown topic?", "expected_chunk_ids": []}\n',
        encoding="utf-8",
    )

    items = load_gold(gold_path)

    assert [item.question for item in items] == [
        "What is RRF?",
        "Unknown topic?",
    ]


def test_load_gold_invalid_json_reports_line_number(tmp_path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    gold_path.write_text(
        "# comment\n"
        '{"question": "Valid", "expected_chunk_ids": ["doc#1"]}\n'
        "{invalid json}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r":3: invalid JSON"):
        load_gold(gold_path)


def test_gold_item_with_empty_expected_ids_is_refusal() -> None:
    item = GoldItem(question="Unknown?", expected_chunk_ids=[])

    assert item.is_refusal is True


def test_gold_item_with_expected_ids_is_not_refusal() -> None:
    item = GoldItem(question="Known?", expected_chunk_ids=["doc#1"])

    assert item.is_refusal is False


def test_load_gold_preserves_expected_chunk_ids(tmp_path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    payload = {
        "question": "Which chunks answer this?",
        "expected_chunk_ids": ["doc#2", "doc#4"],
    }
    gold_path.write_text(json.dumps(payload), encoding="utf-8")

    item = load_gold(gold_path)[0]

    assert item.expected_chunk_ids == ["doc#2", "doc#4"]
