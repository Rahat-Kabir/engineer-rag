"""Faithfulness eval: does the LLM's answer stay grounded in the cited chunks?

Pipeline:
  1. For each gold question, run answer_question() → answer + retrieved chunks.
  2. Parse answer into sentences; extract [N] citation markers per sentence.
  3. For each cited sentence, ask judge LLM (Claude) whether the cited chunks
     support the claim. Verdict: yes | partial | no.
  4. Aggregate per-claim and per-answer metrics.

Refusals (answers with no [N] citations) are counted separately, not graded.
Uncited sentences (no [N] in a non-refused answer) are flagged but not graded.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from rag_core.config import settings
from rag_core.eval.dataset import load_gold
from rag_core.generation.answer import answer_question

_LINE_SPLIT = re.compile(r"\n+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+\.)\s+")
_CITE_RE = re.compile(r"\[(\d+)\]")
_WORD = re.compile(r"[A-Za-z]{2,}")

# A "claim" needs at least this many real words after stripping citation markers.
_MIN_WORDS = 3

_VALID_VERDICTS = {"yes", "partial", "no"}

_JUDGE_PROMPT = """You are evaluating whether a claim is supported by sources.

CLAIM: {claim}

SOURCES:
{sources}

Is the claim supported by the sources?
- "yes" — every part of the claim is directly stated or clearly implied by the sources.
- "partial" — some parts supported, but at least one detail is missing or extends beyond the sources.
- "no" — the claim contradicts the sources, OR the sources don't address the claim at all.

Respond with ONLY one word: yes, partial, or no."""


@dataclass
class ClaimVerdict:
    sentence: str
    cited_chunk_ids: list[str]
    verdict: str  # yes | partial | no | error


@dataclass
class QuestionFaithfulness:
    question: str
    answer: str
    refused: bool
    claims: list[ClaimVerdict] = field(default_factory=list)
    uncited_sentences: int = 0
    parse_skipped: int = 0  # citation markers found but no real claim text


@dataclass
class FaithfulnessSummary:
    total: int
    answered: int
    refused: int

    claims_total: int
    claims_supported: int
    claims_partial: int
    claims_unsupported: int
    claims_errored: int

    uncited_total: int
    parse_skipped_total: int  # parser couldn't extract a claim from a citation marker

    fully_grounded_answers: int  # all claims = yes
    answers_with_hallucination: int  # any claim = no

    per_question: list[QuestionFaithfulness] = field(default_factory=list)

    @property
    def supported_rate(self) -> float:
        graded_claim_count = self.claims_total - self.claims_errored
        return (
            self.claims_supported / graded_claim_count if graded_claim_count else 0.0
        )

    @property
    def hallucination_rate(self) -> float:
        graded_claim_count = self.claims_total - self.claims_errored
        return (
            self.claims_unsupported / graded_claim_count
            if graded_claim_count
            else 0.0
        )

    @property
    def fully_grounded_rate(self) -> float:
        return self.fully_grounded_answers / self.answered if self.answered else 0.0


def _merge_orphan_citations(text: str) -> str:
    """Merge lines that contain only [N] markers with the next content line.

    LLMs sometimes format answers like:
        [1]

        Start with a minimal prompt...

    This pattern strands the citation marker away from its claim. We pre-merge
    them so the marker stays attached to the sentence it cites.
    """
    lines = text.split("\n")
    merged_lines: list[str] = []
    pending_citation_markers = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Blank line. If we have pending markers, swallow it (don't emit
            # blank between the marker and the content we're about to merge it
            # with). Otherwise keep the blank.
            if not pending_citation_markers:
                merged_lines.append(line)
            continue
        # Is this line only citation markers (possibly with a bullet prefix)?
        text_without_markers = _CITE_RE.sub(
            "", _BULLET_PREFIX.sub("", stripped)
        ).strip()
        has_marker = bool(_CITE_RE.search(stripped))
        word_count = len(_WORD.findall(text_without_markers))
        if has_marker and word_count == 0:
            pending_citation_markers = (
                f"{pending_citation_markers} {stripped}".strip()
                if pending_citation_markers
                else stripped
            )
            continue
        # Real content line. Prepend any pending markers.
        if pending_citation_markers:
            merged_lines.append(f"{pending_citation_markers} {line.lstrip()}")
            pending_citation_markers = ""
        else:
            merged_lines.append(line)
    if pending_citation_markers:
        # Keep an orphan at the end so parse_skipped accounts for it.
        merged_lines.append(pending_citation_markers)
    return "\n".join(merged_lines)


def _parse_claims(
    answer: str, max_chunks: int
) -> tuple[list[tuple[str, list[int]]], int, int]:
    """Extract claims from an answer.

    Splits by newlines first (so markdown bullets become separate candidates),
    then by sentence terminators for long prose lines. Strips bullet prefixes
    and citation markers from the claim text sent to the judge.

    Returns:
        (cited_claims, uncited_count, parse_skipped_count)
        - cited_claims: [(cleaned_text, [chunk_indices])]
        - uncited_count: lines with real text but no [N] marker
        - parse_skipped_count: lines that had a [N] but no real claim text
          (parser failures — surfaced separately so they don't pollute the
          hallucination rate)
    """
    cited_claims: list[tuple[str, list[int]]] = []
    uncited_count = 0
    parse_skipped_count = 0

    # 0. Re-attach orphan citation markers to the next content line.
    answer = _merge_orphan_citations(answer)

    # 1. Split on newlines (handles bullets, paragraphs).
    lines = _LINE_SPLIT.split(answer.strip())

    # 2. For long prose lines, also split on sentence terminators.
    candidates: list[str] = []
    for line in lines:
        line = _BULLET_PREFIX.sub("", line.strip())
        if not line:
            continue
        if len(line) > 200 and _SENT_SPLIT.search(line):
            for sentence in _SENT_SPLIT.split(line):
                sentence = sentence.strip()
                if sentence:
                    candidates.append(sentence)
        else:
            candidates.append(line)

    # 3. Classify each candidate.
    for candidate in candidates:
        citation_indices = sorted(
            {
                int(citation_match.group(1))
                for citation_match in _CITE_RE.finditer(candidate)
            }
        )
        citation_indices = [
            citation_index
            for citation_index in citation_indices
            if 1 <= citation_index <= max_chunks
        ]
        # Strip [N] markers to check if there's a real claim left.
        claim_text = _CITE_RE.sub("", candidate).strip()
        word_count = len(_WORD.findall(claim_text))
        if word_count < _MIN_WORDS:
            if citation_indices:
                parse_skipped_count += 1
            # else: empty/junk line, drop silently
            continue
        if citation_indices:
            cited_claims.append((claim_text, citation_indices))
        else:
            uncited_count += 1

    return cited_claims, uncited_count, parse_skipped_count


def _judge(client: anthropic.Anthropic, claim: str, sources: list[str]) -> str:
    """Ask Claude whether the claim is supported. Returns 'yes' | 'partial' | 'no' | 'error'."""
    source_text = "\n\n---\n\n".join(sources)
    prompt = _JUDGE_PROMPT.format(claim=claim, sources=source_text)
    try:
        response = client.messages.create(
            model=settings.judge_model,
            max_tokens=10,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in response.content:
            block_text = getattr(block, "text", None)
            if block_text:
                text = block_text.strip().lower()
                break
    except Exception as error:  # noqa: BLE001
        print(f"  ! judge error: {error}")
        return "error"

    # Try exact match first, then fuzzy match.
    if text in _VALID_VERDICTS:
        return text
    for verdict in ("yes", "partial", "no"):
        if verdict in text:
            return verdict
    return "error"


def _eval_question(client: anthropic.Anthropic, question: str, top_k: int) -> QuestionFaithfulness:
    result = answer_question(question, top_k=top_k)
    cited_claims, uncited_count, parse_skipped_count = _parse_claims(
        result.answer, max_chunks=len(result.retrieved)
    )

    # No usable cited claims → treat as refusal (matches scripts.eval refusal logic).
    if not cited_claims:
        return QuestionFaithfulness(
            question=question,
            answer=result.answer,
            refused=True,
            claims=[],
            uncited_sentences=uncited_count,
            parse_skipped=parse_skipped_count,
        )

    claims: list[ClaimVerdict] = []
    for sentence, citation_indices in cited_claims:
        # Gather cited chunk texts. Index is 1-based in the answer; retrieved is 0-based.
        sources = [
            result.retrieved[citation_index - 1].chunk.text
            for citation_index in citation_indices
        ]
        cited_chunk_ids = [
            result.retrieved[citation_index - 1].chunk.chunk_id
            for citation_index in citation_indices
        ]
        verdict = _judge(client, sentence, sources)
        claims.append(ClaimVerdict(
            sentence=sentence,
            cited_chunk_ids=cited_chunk_ids,
            verdict=verdict,
        ))

    return QuestionFaithfulness(
        question=question,
        answer=result.answer,
        refused=False,
        claims=claims,
        uncited_sentences=uncited_count,
        parse_skipped=parse_skipped_count,
    )


def run_faithfulness(gold_path: Path, top_k: int = 6) -> FaithfulnessSummary:
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env to run faithfulness eval."
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    items = load_gold(gold_path)

    per_question: list[QuestionFaithfulness] = []
    for item_index, item in enumerate(items, 1):
        # Skip refusal-by-design questions (expected_chunk_ids=[]). They're for retrieval eval.
        if item.is_refusal:
            continue
        print(f"  [{item_index}/{len(items)}] {item.question[:70]}")
        per_question.append(_eval_question(client, item.question, top_k=top_k))

    answered_count = sum(1 for question_result in per_question if not question_result.refused)
    refused_count = sum(1 for question_result in per_question if question_result.refused)

    all_claims = [
        claim
        for question_result in per_question
        for claim in question_result.claims
    ]
    supported_count = sum(1 for claim in all_claims if claim.verdict == "yes")
    partial_count = sum(1 for claim in all_claims if claim.verdict == "partial")
    unsupported_count = sum(1 for claim in all_claims if claim.verdict == "no")
    errored_count = sum(1 for claim in all_claims if claim.verdict == "error")

    uncited_total = sum(
        question_result.uncited_sentences for question_result in per_question
    )
    parse_skipped_total = sum(
        question_result.parse_skipped for question_result in per_question
    )

    fully_grounded_count = sum(
        1
        for question_result in per_question
        if not question_result.refused
        and question_result.claims
        and all(claim.verdict == "yes" for claim in question_result.claims)
    )
    hallucination_answer_count = sum(
        1
        for question_result in per_question
        if not question_result.refused
        and any(claim.verdict == "no" for claim in question_result.claims)
    )

    return FaithfulnessSummary(
        total=len(per_question),
        answered=answered_count,
        refused=refused_count,
        claims_total=len(all_claims),
        claims_supported=supported_count,
        claims_partial=partial_count,
        claims_unsupported=unsupported_count,
        claims_errored=errored_count,
        uncited_total=uncited_total,
        parse_skipped_total=parse_skipped_total,
        fully_grounded_answers=fully_grounded_count,
        answers_with_hallucination=hallucination_answer_count,
        per_question=per_question,
    )
