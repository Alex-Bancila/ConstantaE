"""Loads law texts into the vector database (owner: Lucas).

Run from the backend folder:  python -m app.ai.rag.ingest

TODO(Lucas):
- split each law into one chunk per article ("Art. 1", "Art. 2", ...)
- keep the law name, article number and a link to legislatie.just.ro with every chunk
- create embeddings (BGE-M3 or multilingual-e5) and store them in Postgres + pgvector
"""

from pathlib import Path

from app.ai.rag.text import normalize_diacritics

LAWS_DIR = Path(__file__).resolve().parents[3] / "data" / "laws"


def main() -> None:
    files = sorted(LAWS_DIR.glob("*.txt"))
    if not files:
        print(f"No law texts found in {LAWS_DIR}. See data/laws/README.md.")
        return
    for path in files:
        text = normalize_diacritics(path.read_text(encoding="utf-8"))
        print(f"{path.name}: {len(text)} characters")
    raise NotImplementedError("TODO(Lucas): split into articles, embed and store.")


if __name__ == "__main__":
    main()
