from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel, Field


class GoldItem(BaseModel):
    question: str
    expected_chunk_ids: list[str] = Field(default_factory=list)

    @property
    def is_refusal(self) -> bool:
        """True if no chunk is expected to answer this (negative / out-of-corpus question)."""
        return len(self.expected_chunk_ids) == 0


def load_gold(path: Path) -> list[GoldItem]:
    """Load a JSONL gold file. One JSON object per line; blank lines and # comments allowed."""
    items: list[GoldItem] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{i}: invalid JSON: {e}") from e
        items.append(GoldItem(**data))
    return items
