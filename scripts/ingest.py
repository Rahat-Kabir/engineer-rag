from rag_core.ingest.pipeline import run_ingest


def main() -> None:
    print("Ingesting articles...")
    stats = run_ingest()
    print(f"\nDone. {stats.documents} documents, {stats.chunks} chunks.")


if __name__ == "__main__":
    main()
