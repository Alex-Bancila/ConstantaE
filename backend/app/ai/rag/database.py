"""Postgres storage for law article embeddings (owner: Lucas)."""

from collections.abc import Sequence
from typing import Any

from app.ai.rag.articles import LawArticle


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
