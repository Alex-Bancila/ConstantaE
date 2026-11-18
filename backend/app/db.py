"""Postgres storage for finished analyses and their image results (owner: David).

Who stores what:
- Redis (app/workers/store.py, Marius) holds the live result the API serves, including
  pending and failed ones. It expires after RESULT_TTL_SECONDS.
- Postgres (this module) keeps a permanent copy of every finished analysis. The API does
  not read it yet. It is written by analysis.run, once per finished analysis.

Without DATABASE_URL, nothing here does anything, so mock mode and the tests need no database.
A database error is logged and never breaks the analysis.

Create the tables once with `python -m app.db`.
"""

import logging
from typing import Any

from app.config import get_settings
from app.schemas import AnalysisResponse, PageData

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    page_url TEXT,
    page_title TEXT,
    status TEXT NOT NULL,
    trust_score INTEGER,
    trust JSONB,
    legal JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS image_results (
    id BIGSERIAL PRIMARY KEY,
    analysis_id TEXT NOT NULL REFERENCES analyses (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    url TEXT NOT NULL,
    ai_probability DOUBLE PRECISION NOT NULL CHECK (ai_probability BETWEEN 0 AND 1),
    signals JSONB NOT NULL DEFAULT '[]',
    UNIQUE (analysis_id, position)
);
"""


def connect(database_url: str | None = None) -> Any:
    """Open a connection from DATABASE_URL. Raises RuntimeError if it is not set."""
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    import psycopg

    return psycopg.connect(url)


def ensure_schema(connection: Any) -> None:
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA)
    connection.commit()


def save_analysis(connection: Any, result: AnalysisResponse, page: PageData | None = None) -> None:
    """Insert or replace an analysis and its image results."""
    from psycopg.types.json import Jsonb

    trust = result.trust.model_dump(mode="json", by_alias=True) if result.trust else None
    legal = result.legal.model_dump(mode="json", by_alias=True) if result.legal else None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO analyses (id, page_url, page_title, status, trust_score, trust, legal)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    page_url = EXCLUDED.page_url,
                    page_title = EXCLUDED.page_title,
                    status = EXCLUDED.status,
                    trust_score = EXCLUDED.trust_score,
                    trust = EXCLUDED.trust,
                    legal = EXCLUDED.legal
                """,
                (
                    result.analysis_id,
                    page.url if page else None,
                    page.title if page else None,
                    result.status.value,
                    result.trust.score if result.trust else None,
                    Jsonb(trust) if trust is not None else None,
                    Jsonb(legal) if legal is not None else None,
                ),
            )
            cursor.execute(
                "DELETE FROM image_results WHERE analysis_id = %s", (result.analysis_id,)
            )
            for position, image in enumerate(result.images):
                cursor.execute(
                    """
                    INSERT INTO image_results (analysis_id, position, url, ai_probability, signals)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        result.analysis_id,
                        position,
                        image.url,
                        image.ai_probability,
                        Jsonb(image.signals),
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def record(result: AnalysisResponse, page: PageData | None = None) -> None:
    """Save a finished analysis if DATABASE_URL is set. Never raises."""
    if not get_settings().database_url:
        return
    try:
        connection = connect()
        try:
            save_analysis(connection, result, page)
        finally:
            connection.close()
    except Exception as error:
        logger.warning("Could not save analysis %s to Postgres: %s", result.analysis_id, error)


def main() -> None:
    connection = connect()
    try:
        ensure_schema(connection)
    finally:
        connection.close()
    print("Tables analyses and image_results are ready.")


if __name__ == "__main__":
    main()
