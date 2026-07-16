from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""

    qdrant_url: str = "http://localhost:6333"

    # Which corpus every command runs against. "demo" is the default so a
    # fresh clone works out of the box; set CORPUS_PROFILE=private in .env
    # (or pass --private to any script) to use your own local corpus.
    # The profile derives articles dir + Qdrant collection + gold file
    # together (properties below) so the three can never be mismatched.
    corpus_profile: Literal["demo", "private"] = "demo"

    embed_model: str = "text-embedding-3-small"
    embed_dim: int = 1536

    llm_model: str = "gpt-5.4-mini"
    llm_max_tokens: int = 800
    llm_temperature: float = 0.2

    # Cross-encoder rerank (Phase 5b.2). Leave api key empty to disable.
    voyage_api_key: str = ""
    rerank_model: str = "rerank-2.5"
    rerank_prefetch: int = 30

    # Faithfulness eval (Phase 5c). Anthropic Claude as judge.
    anthropic_api_key: str = ""
    judge_model: str = "claude-opus-4-7"

    data_dir: Path = Path("./data")

    @property
    def articles_dir(self) -> Path:
        if self.corpus_profile == "private":
            return self.data_dir / "articles"
        return self.data_dir / "articles_demo"

    @property
    def qdrant_collection(self) -> str:
        if self.corpus_profile == "private":
            return "articles"
        return "articles_demo"

    @property
    def gold_path(self) -> Path:
        if self.corpus_profile == "private":
            return self.data_dir / "eval" / "private-gold.jsonl"
        return self.data_dir / "eval" / "demo-gold.jsonl"


settings = Settings()
