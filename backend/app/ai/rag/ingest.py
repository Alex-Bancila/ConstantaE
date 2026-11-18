"""Loads law texts into article records (owner: Lucas).

Run from the backend folder:  python -m app.ai.rag.ingest

TODO(Lucas):
- create embeddings (BGE-M3 or multilingual-e5) and store them in Postgres + pgvector
"""

from pathlib import Path

from app.ai.rag.articles import LawArticle, split_articles

LAWS_DIR = Path(__file__).resolve().parents[3] / "data" / "laws"
LAW_SOURCES = {
    "og-21-1992": {
        "law_name": "OG 21/1992",
        "source_url": "https://legislatie.just.ro/Public/DetaliiDocumentAfis/269119",
        "article_numbers": {str(number) for number in range(1, 70)}
        | {
            "9^1",
            "9^2",
            "9^3",
            "9^4",
            "9^5",
            "9^6",
            "9^7",
            "9^8",
            "9^9",
            "9^10",
            "9^11",
            "39^1",
            "58^1",
        },
    },
    "oug-34-2014": {
        "law_name": "OUG 34/2014",
        "source_url": "https://legislatie.just.ro/Public/DetaliiDocumentAfis/257171",
        "article_numbers": {str(number) for number in range(1, 30)} | {"6^1"},
    },
}


def load_articles() -> list[LawArticle]:
    files = sorted(LAWS_DIR.glob("*.txt"))
    if not files:
        print(f"No law texts found in {LAWS_DIR}. See data/laws/README.md.")
        return []

    articles: list[LawArticle] = []
    for path in files:
        metadata = LAW_SOURCES.get(path.stem)
        if metadata is None:
            raise ValueError(f"No source metadata configured for {path.name}")
        articles.extend(
            split_articles(
                path.read_text(encoding="utf-8"),
                law_name=metadata["law_name"],
                source_url=metadata["source_url"],
                article_numbers=metadata["article_numbers"],
            )
        )
    return articles


def main() -> None:
    articles = load_articles()
    counts: dict[str, int] = {}
    for article in articles:
        counts[article.law_name] = counts.get(article.law_name, 0) + 1
    for law_name, count in counts.items():
        print(f"{law_name}: {count} articles")


if __name__ == "__main__":
    main()
