from rag_core.config import settings
from rag_core.ingest.pipeline import run_ingest
from scripts._profile import apply_corpus_profile_flag


def main() -> None:
    apply_corpus_profile_flag()
    print(
        f"Ingesting articles ({settings.corpus_profile} corpus: "
        f"{settings.articles_dir} -> collection '{settings.qdrant_collection}')..."
    )
    stats = run_ingest()
    print(f"\nDone. {stats.documents} documents, {stats.chunks} chunks.")


if __name__ == "__main__":
    main()
