"""Hybrid search over the stored law articles (owner: Lucas).

`retrieve(query, k)` combines three signals:

1. Exact references. "art. 9 OUG 34/2014" names the article outright, so those
   articles are looked up by (law, article) and always come first.
2. Full-text search with Postgres's Romanian stemmer, for questions that use the
   law's own wording ("dreptul de retragere").
3. Vector similarity with multilingual-e5, for questions in everyday words that
   the law never uses ("returna un produs" vs the law's "retragere ... bunuri").

Rankings 2 and 3 are merged with Reciprocal Rank Fusion, which only looks at
positions, so the two very different score scales never have to be compared.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.ai.rag.articles import LawArticle
from app.ai.rag.database import FULL_TEXT_CONFIG, connect_database
from app.ai.rag.text import normalize_diacritics
from app.config import get_settings

DEFAULT_K = 5
# How many candidates each search contributes before fusion.
CANDIDATES_PER_SEARCH = 20
# The usual RRF constant: it keeps a single first place from outweighing
# an article that ranks well in both searches.
RRF_CONSTANT = 60

_LAW_REFERENCE = re.compile(
    r"\b(?P<kind>O\.?\s*U\.?\s*G\.?|O\.?\s*G\.?)\s*(?:nr\.?\s*)?"
    r"(?P<number>\d+)\s*/\s*(?P<year>\d{4})\b",
    re.IGNORECASE,
)
_ARTICLE_REFERENCE = re.compile(
    r"\bart(?:icolul|icol|\.)?\s*(?P<number>\d+(?:\s*\^\s*\d+)?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RetrievedArticle:
    article: LawArticle
    score: float


@dataclass(frozen=True)
class ArticleReference:
    article_number: str
    law_name: str | None = None


def parse_references(query: str) -> list[ArticleReference]:
    """Find explicit article references such as "art. 9 OUG 34/2014".

    If the query names exactly one law, every article reference is tied to it.
    Otherwise the article number is looked up in every law.
    """
    laws = []
    for match in _LAW_REFERENCE.finditer(query):
        kind = "OUG" if "u" in match.group("kind").lower() else "OG"
        law = f"{kind} {match.group('number')}/{match.group('year')}"
        if law not in laws:
            laws.append(law)
    law_name = laws[0] if len(laws) == 1 else None

    references: list[ArticleReference] = []
    for match in _ARTICLE_REFERENCE.finditer(query):
        number = re.sub(r"\s+", "", match.group("number"))
        reference = ArticleReference(article_number=number, law_name=law_name)
        if reference not in references:
            references.append(reference)
    return references


def fuse_rankings(
    exact: Sequence[LawArticle],
    rankings: Sequence[Sequence[LawArticle]],
    k: int,
) -> list[RetrievedArticle]:
    """Exact references first, then the other rankings merged by Reciprocal Rank Fusion."""

    def key(article: LawArticle) -> tuple[str, str]:
        return (article.law_name, article.article_number)

    results: list[RetrievedArticle] = []
    seen: set[tuple[str, str]] = set()
    for article in exact:
        if key(article) not in seen:
            seen.add(key(article))
            results.append(RetrievedArticle(article=article, score=1.0))

    scores: dict[tuple[str, str], float] = {}
    articles: dict[tuple[str, str], LawArticle] = {}
    for ranking in rankings:
        for position, article in enumerate(ranking, start=1):
            if key(article) in seen:
                continue
            articles.setdefault(key(article), article)
            scores[key(article)] = scores.get(key(article), 0.0) + 1 / (RRF_CONSTANT + position)

    fused = sorted(scores, key=lambda item: scores[item], reverse=True)
    results.extend(RetrievedArticle(article=articles[item], score=scores[item]) for item in fused)
    return results[:k]


def _row_to_article(row: Sequence[Any]) -> LawArticle:
    law, article, text, link = row[:4]
    return LawArticle(law_name=law, article_number=article, text=text, source_url=link)


def find_references(connection: Any, references: Sequence[ArticleReference]) -> list[LawArticle]:
    found: list[LawArticle] = []
    with connection.cursor() as cursor:
        for reference in references:
            if reference.law_name is None:
                cursor.execute(
                    "SELECT law, article, text, link FROM law_chunks "
                    "WHERE article = %s ORDER BY law",
                    (reference.article_number,),
                )
            else:
                cursor.execute(
                    "SELECT law, article, text, link FROM law_chunks "
                    "WHERE article = %s AND law = %s",
                    (reference.article_number, reference.law_name),
                )
            found.extend(_row_to_article(row) for row in cursor.fetchall())
    return found


def full_text_search(connection: Any, query: str, limit: int) -> list[LawArticle]:
    # websearch_to_tsquery would AND every word, so a long question matches nothing.
    # Instead the question is stemmed with the same Romanian config as the articles
    # and its stems are OR-ed; ts_rank_cd then prefers articles with more of them.
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH q AS (
                SELECT to_tsquery(
                    'simple',
                    coalesce(string_agg(quote_literal(lexeme), ' | '), '')
                ) AS query
                FROM unnest(to_tsvector('{FULL_TEXT_CONFIG}', %s))
            )
            SELECT c.law, c.article, c.text, c.link, ts_rank_cd(c.search_vector, q.query)
            FROM law_chunks AS c, q
            WHERE c.search_vector @@ q.query
            ORDER BY 5 DESC, c.id
            LIMIT %s
            """,
            (query, limit),
        )
        return [_row_to_article(row) for row in cursor.fetchall()]


def vector_search(connection: Any, embedding: Sequence[float], limit: int) -> list[LawArticle]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT law, article, text, link, 1 - (embedding <=> %s::vector)
            FROM law_chunks
            ORDER BY embedding <=> %s::vector, id
            LIMIT %s
            """,
            (list(embedding), list(embedding), limit),
        )
        return [_row_to_article(row) for row in cursor.fetchall()]


@lru_cache
def _default_embedder() -> Any:
    # Imported here so that tests and AI_MODE=mock never load the model.
    from app.ai.rag.embeddings import ArticleEmbedder

    return ArticleEmbedder()


def retrieve(
    query: str,
    k: int = DEFAULT_K,
    *,
    connection: Any = None,
    embed_query: Callable[[str], Sequence[float]] | None = None,
) -> list[RetrievedArticle]:
    """Return the k most relevant law articles for a question, best first.

    `connection` and `embed_query` are for tests; by default the database comes
    from DATABASE_URL and the question is embedded with multilingual-e5.
    """
    if k <= 0:
        return []
    query = normalize_diacritics(query).strip()
    if not query:
        return []

    if embed_query is None:
        embed_query = _default_embedder().embed_query

    if connection is None:
        database_url = get_settings().database_url
        if not database_url:
            raise RuntimeError("DATABASE_URL must be set to search the law articles")
        with connect_database(database_url) as owned_connection:
            return retrieve(query, k, connection=owned_connection, embed_query=embed_query)

    limit = max(k, CANDIDATES_PER_SEARCH)
    exact = find_references(connection, parse_references(query))
    by_text = full_text_search(connection, query, limit)
    by_meaning = vector_search(connection, embed_query(query), limit)
    return fuse_rankings(exact, [by_text, by_meaning], k)
