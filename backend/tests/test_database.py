from app.ai.rag.articles import LawArticle
from app.ai.rag.database import ensure_schema, upsert_articles


class FakeCursor:
    def __init__(self) -> None:
        self.queries: list[tuple[str, tuple[object, ...] | None]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        self.queries.append((query, params))


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1


def test_schema_creates_vector_table_with_unique_article_key():
    connection = FakeConnection()

    ensure_schema(connection, dimensions=384)

    queries = [query for query, _ in connection.cursor_instance.queries]
    assert "CREATE EXTENSION IF NOT EXISTS vector" in queries[0]
    assert "embedding vector(384)" in queries[1]
    assert "UNIQUE (law, article)" in queries[1]
    assert connection.commits == 1


def test_upsert_updates_existing_article_instead_of_duplicating_it():
    connection = FakeConnection()
    article = LawArticle(
        law_name="OG 21/1992",
        article_number="1",
        text="Text",
        source_url="https://example.test/law",
    )

    upsert_articles(connection, [article], [[0.1, 0.2]])

    query, params = connection.cursor_instance.queries[0]
    assert "ON CONFLICT (law, article) DO UPDATE" in query
    assert params == ("OG 21/1992", "1", "Text", "https://example.test/law", [0.1, 0.2])
    assert connection.commits == 1
