import sys

from rag_core.generation.answer import answer_question
from scripts._profile import apply_corpus_profile_flag


def main() -> None:
    apply_corpus_profile_flag()
    if len(sys.argv) < 2:
        print('Usage: python -m scripts.query "your question" [--demo | --private]')
        sys.exit(1)
    question = " ".join(sys.argv[1:])

    result = answer_question(question, top_k=6)

    print(f"Q: {result.question}\n")
    print(f"{result.answer}\n")

    if result.citations:
        print("Sources:")
        for cit in result.citations:
            line = f"  [{cit.marker}] {cit.chunk_id}  —  {cit.title}"
            if cit.source_url:
                line += f"\n      {cit.source_url}"
            print(line)
    else:
        print("(no citations)")


if __name__ == "__main__":
    main()
