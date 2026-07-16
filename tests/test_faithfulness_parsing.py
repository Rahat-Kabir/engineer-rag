from rag_core.eval.faithfulness import _merge_orphan_citations, _parse_claims


def test_orphan_citation_merges_into_following_content_line() -> None:
    answer = "[1]\nGrounded content follows."

    assert _merge_orphan_citations(answer) == "[1] Grounded content follows."


def test_blank_lines_between_orphan_marker_and_content_are_swallowed() -> None:
    answer = "[1]\n\n\nGrounded content follows."

    assert _merge_orphan_citations(answer) == "[1] Grounded content follows."


def test_trailing_orphan_marker_is_kept() -> None:
    answer = "Grounded content appears first.\n[2]"

    assert _merge_orphan_citations(answer) == "Grounded content appears first.\n[2]"


def test_parse_claims_treats_bullets_as_separate_claims() -> None:
    answer = (
        "- First grounded claim appears here. [1]\n"
        "* Second grounded claim appears here. [2]"
    )

    claims, uncited_count, parse_skipped_count = _parse_claims(
        answer, max_chunks=2
    )

    assert claims == [
        ("First grounded claim appears here.", [1]),
        ("Second grounded claim appears here.", [2]),
    ]
    assert uncited_count == 0
    assert parse_skipped_count == 0


def test_parse_claims_splits_long_prose_on_sentence_boundaries() -> None:
    first_sentence = (
        "This first grounded sentence contains enough repeated explanation "
        + "context " * 24
        + "to make the full prose line longer than two hundred characters[1]."
    )
    second_sentence = "This second grounded sentence is separate[2]."
    answer = f"{first_sentence} {second_sentence}"

    claims, uncited_count, parse_skipped_count = _parse_claims(
        answer, max_chunks=2
    )

    assert len(answer) > 200
    assert claims == [
        (
            first_sentence.replace("[1]", ""),
            [1],
        ),
        ("This second grounded sentence is separate.", [2]),
    ]
    assert uncited_count == 0
    assert parse_skipped_count == 0


def test_parse_claims_counts_short_marked_line_as_parse_skipped() -> None:
    claims, uncited_count, parse_skipped_count = _parse_claims(
        "Too short. [1]", max_chunks=1
    )

    assert claims == []
    assert uncited_count == 0
    assert parse_skipped_count == 1


def test_parse_claims_counts_worded_line_without_marker_as_uncited() -> None:
    claims, uncited_count, parse_skipped_count = _parse_claims(
        "This sentence has enough words but no marker.", max_chunks=2
    )

    assert claims == []
    assert uncited_count == 1
    assert parse_skipped_count == 0


def test_parse_claims_drops_out_of_range_markers_but_keeps_valid_ones() -> None:
    answer = (
        "This claim has one valid and one invalid marker. [2][9]\n"
        "This claim has only an invalid marker. [8]"
    )

    claims, uncited_count, parse_skipped_count = _parse_claims(
        answer, max_chunks=3
    )

    assert claims == [
        ("This claim has one valid and one invalid marker.", [2]),
    ]
    assert uncited_count == 1
    assert parse_skipped_count == 0


def test_parse_claims_strips_markers_from_claim_text() -> None:
    claims, uncited_count, parse_skipped_count = _parse_claims(
        "The cited claim combines two sources. [1][3]", max_chunks=3
    )

    assert claims == [
        ("The cited claim combines two sources.", [1, 3]),
    ]
    assert uncited_count == 0
    assert parse_skipped_count == 0
