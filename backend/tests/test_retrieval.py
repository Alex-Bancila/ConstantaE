import os

import pytest

from app.ai.rag.articles import LawArticle
from app.ai.rag.retrieval import (
    ArticleReference,
    fuse_rankings,
    parse_references,
    retrieve,
)


def law_article(law: str, number: str, text: str = "Text") -> LawArticle:
    return LawArticle(
        law_name=law,
        article_number=number,
        text=text,
        source_url=f"https://example.test/{law}",
    )


ART_9 = law_article("OUG 34/2014", "9", "Dreptul de retragere ... 14 zile")
ART_6 = law_article("OUG 34/2014", "6", "Cerințe de informare")
OG_ART_9 = law_article("OG 21/1992", "9", "Produsele trebuie însoțite de instrucțiuni")
ART_16 = law_article("OUG 34/2014", "16", "Excepții de la dreptul de retragere")


def row(article: LawArticle, score: float = 0.5) -> tuple[str, str, str, str, float]:
    return (article.law_name, article.article_number, article.text, article.source_url, score)


class FakeCursor:
    """Answers each kind of query retrieve() sends with preset rows."""

    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.rows: list[tuple[object, ...]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self.connection.queries.append((query, params))
        if "WHERE article = %s AND law = %s" in query:
            number, law = params
            self.rows = [
                row(a)
                for a in self.connection.stored
                if a.article_number == number and a.law_name == law
            ]
        elif "WHERE article = %s" in query:
            (number,) = params
            self.rows = [row(a) for a in self.connection.stored if a.article_number == number]
        elif "to_tsvector" in query:
            self.rows = [row(a) for a in self.connection.full_text]
        elif "<=>" in query:
            self.rows = [row(a) for a in self.connection.by_meaning]
        else:
            raise AssertionError(f"Unexpected query: {query}")

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


class FakeConnection:
    def __init__(
        self,
        stored: list[LawArticle],
        full_text: list[LawArticle] | None = None,
        by_meaning: list[LawArticle] | None = None,
    ) -> None:
        self.stored = stored
        self.full_text = full_text or []
        self.by_meaning = by_meaning or []
        self.queries: list[tuple[str, tuple[object, ...]]] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)


def fake_embedding(question: str) -> list[float]:
    return [0.1, 0.2, 0.3]


def test_parse_references_ties_articles_to_the_named_law():
    assert parse_references("art. 9 OUG 34/2014") == [
        ArticleReference(article_number="9", law_name="OUG 34/2014")
    ]


def test_parse_references_understands_common_spellings():
    assert parse_references("Articolul 9^1 din O.G. nr. 21/1992") == [
        ArticleReference(article_number="9^1", law_name="OG 21/1992")
    ]
    assert parse_references("ce spune art 6?") == [ArticleReference(article_number="6")]
    assert parse_references("în cât timp pot returna un produs") == []


def test_parse_references_without_a_single_law_searches_every_law():
    references = parse_references("art. 9 din OUG 34/2014 și OG 21/1992")
    assert references == [ArticleReference(article_number="9", law_name=None)]


def test_fuse_rankings_puts_exact_references_first_without_duplicates():
    results = fuse_rankings(exact=[ART_9], rankings=[[ART_6, ART_9], [ART_16, ART_9]], k=3)

    assert [r.article for r in results] == [ART_9, ART_6, ART_16]
    assert results[0].score == 1.0


def test_fuse_rankings_prefers_articles_found_by_both_searches():
    results = fuse_rankings(exact=[], rankings=[[ART_6, ART_9], [ART_16, ART_9]], k=3)

    assert results[0].article == ART_9


def test_fuse_rankings_respects_k():
    assert len(fuse_rankings(exact=[], rankings=[[ART_6, ART_9, ART_16]], k=2)) == 2


def test_exact_reference_finds_the_article_of_the_named_law():
    connection = FakeConnection(
        stored=[ART_9, OG_ART_9, ART_6],
        full_text=[ART_6],
        by_meaning=[ART_16, ART_6],
    )

    results = retrieve("art. 9 OUG 34/2014", k=3, connection=connection, embed_query=fake_embedding)

    assert results[0].article == ART_9
    assert OG_ART_9 not in [r.article for r in results]


def test_everyday_question_is_found_through_vector_search():
    connection = FakeConnection(stored=[ART_9, ART_6], full_text=[], by_meaning=[ART_9, ART_6])

    results = retrieve(
        "în cât timp pot returna un produs",
        k=2,
        connection=connection,
        embed_query=fake_embedding,
    )

    assert results[0].article == ART_9
    assert results[0].article.law_name == "OUG 34/2014"
    assert results[0].article.source_url == "https://example.test/OUG 34/2014"


def test_retrieve_normalizes_cedilla_diacritics_before_searching():
    connection = FakeConnection(stored=[])
    seen: list[str] = []

    retrieve("şi ţară", connection=connection, embed_query=lambda q: seen.append(q) or [0.0])

    assert seen == ["și țară"]


def test_retrieve_sends_the_embedding_as_a_vector():
    connection = FakeConnection(stored=[])

    retrieve("retragere", connection=connection, embed_query=fake_embedding)

    vector_query, params = next(q for q in connection.queries if "<=>" in q[0])
    assert "%s::vector" in vector_query
    assert params[0] == [0.1, 0.2, 0.3]


def test_empty_query_returns_nothing_without_touching_the_database():
    connection = FakeConnection(stored=[ART_9])

    assert retrieve("   ", connection=connection, embed_query=fake_embedding) == []
    assert connection.queries == []


# Runs against a real database filled by `python -m app.ai.rag.ingest`.
# Set RAG_TEST_DATABASE_URL to run it; it is skipped otherwise.
RAG_TEST_DATABASE_URL = os.environ.get("RAG_TEST_DATABASE_URL")


@pytest.mark.skipif(not RAG_TEST_DATABASE_URL, reason="RAG_TEST_DATABASE_URL is not set")
@pytest.mark.parametrize(
    ("question", "law", "article"),
    [
        ("art. 9 OUG 34/2014", "OUG 34/2014", "9"),
        ("în cât timp pot returna un produs", "OUG 34/2014", "9"),
    ],
)
def test_real_database_finds_the_expected_article(question, law, article):
    from app.ai.rag.database import connect_database

    with connect_database(RAG_TEST_DATABASE_URL) as connection:
        results = retrieve(question, k=5, connection=connection)

    found = [(r.article.law_name, r.article.article_number) for r in results]
    assert (law, article) in found[:3], found
