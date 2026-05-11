from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "articles"

    embed_model: str = "text-embedding-3-small"
    embed_dim: int = 1536

    llm_model: str = "gpt-5.4-mini"
    llm_max_tokens: int = 800
    llm_temperature: float = 0.2

    data_dir: Path = Path("./data")

    @property
    def articles_dir(self) -> Path:
        return self.data_dir / "articles"


settings = Settings()
