"""Postgres storage for law article embeddings (owner: Lucas)."""

from collections.abc import Sequence
from typing import Any

from app.ai.rag.articles import LawArticle

# Postgres ships a Romanian Snowball stemmer, so "retragere" and "retragerea" match.
FULL_TEXT_CONFIG = "romanian"


def connect_database(database_url: str) -> Any:
    try:
        import psycopg
        from pgvector.psycopg import register_vector
    except ImportError as error:
        raise RuntimeError("psycopg and pgvector are required for law ingestion") from error

    connection = psycopg.connect(database_url)
    register_vector(connection)
    return connection


def ensure_schema(connection: Any, dimensions: int) -> None:
    if dimensions <= 0:
        raise ValueError("Embedding dimensions must be positive")

    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS law_chunks (
                id BIGSERIAL PRIMARY KEY,
                law TEXT NOT NULL,
                article TEXT NOT NULL,
                text TEXT NOT NULL,
                link TEXT NOT NULL,
                embedding vector({dimensions}) NOT NULL,
                UNIQUE (law, article)
            )
            """
        )
        # Full-text half of the hybrid search. A generated column stays in sync with
        # `text` on every upsert; ADD COLUMN IF NOT EXISTS upgrades tables created
        # before this column existed.
        cursor.execute(
            f"""
            ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS search_vector tsvector
            GENERATED ALWAYS AS (to_tsvector('{FULL_TEXT_CONFIG}', text)) STORED
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS law_chunks_search_idx "
            "ON law_chunks USING GIN (search_vector)"
        )
    connection.commit()


def upsert_articles(
    connection: Any,
    articles: Sequence[LawArticle],
    embeddings: Sequence[Sequence[float]],
) -> None:
    if len(articles) != len(embeddings):
        raise ValueError("Every law article must have exactly one embedding")

    with connection.cursor() as cursor:
        for article, embedding in zip(articles, embeddings, strict=True):
            cursor.execute(
                """
                INSERT INTO law_chunks (law, article, text, link, embedding)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (law, article) DO UPDATE SET
                    text = EXCLUDED.text,
                    link = EXCLUDED.link,
                    embedding = EXCLUDED.embedding
                """,
                (
                    article.law_name,
                    article.article_number,
                    article.text,
                    article.source_url,
                    embedding,
                ),
            )
    connection.commit()
