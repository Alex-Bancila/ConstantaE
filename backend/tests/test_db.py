import os

import pytest

from app import db
from app.config import get_settings
from app.schemas import (
    AnalysisResponse,
    AnalysisStatus,
    ImageResult,
    LegalReport,
    PageData,
    TrustCheck,
    TrustReport,
)
from app.services import analysis


class FakeCursor:
    def __init__(self) -> None:
        self.queries: list[tuple[str, tuple | None]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple | None = None) -> None:
        self.queries.append((" ".join(query.split()), params))


class FakeConnection:
    def __init__(self, fail_on: str | None = None) -> None:
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.fail_on = fail_on

    def cursor(self) -> FakeCursor:
        if self.fail_on:
            self.cursor_instance.execute = self._fail  # type: ignore[method-assign]
        return self.cursor_instance

    def _fail(self, *args: object) -> None:
        raise RuntimeError(self.fail_on)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def make_result() -> AnalysisResponse:
    return AnalysisResponse(
        analysis_id="abc123",
        status=AnalysisStatus.DONE,
        images=[
            ImageResult(url="https://x.ro/1.jpg", ai_probability=0.9, signals=["no camera data"]),
            ImageResult(url="https://x.ro/2.jpg", ai_probability=0.1),
        ],
        trust=TrustReport(score=80, checks=[TrustCheck(id="https", passed=True, message="ok")]),
        legal=LegalReport(summary="Fine.", citations=[]),
    )


def test_schema_has_both_tables_and_cascading_foreign_key():
    connection = FakeConnection()

    db.ensure_schema(connection)

    ((query, _),) = connection.cursor_instance.queries
    assert "CREATE TABLE IF NOT EXISTS analyses" in query
    assert "CREATE TABLE IF NOT EXISTS image_results" in query
    assert "REFERENCES analyses (id) ON DELETE CASCADE" in query
    assert connection.commits == 1


def test_save_analysis_writes_the_analysis_and_one_row_per_image():
    connection = FakeConnection()
    page = PageData(url="https://shop.ro/p", title="Product")

    db.save_analysis(connection, make_result(), page)

    queries = connection.cursor_instance.queries
    assert queries[0][0].startswith("INSERT INTO analyses")
    assert queries[0][1][:5] == ("abc123", "https://shop.ro/p", "Product", "done", 80)
    assert queries[1][0].startswith("DELETE FROM image_results")
    images = [params for query, params in queries if query.startswith("INSERT INTO image_results")]
    assert [(p[1], p[2], p[3]) for p in images] == [
        (0, "https://x.ro/1.jpg", 0.9),
        (1, "https://x.ro/2.jpg", 0.1),
    ]
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_save_analysis_rolls_back_on_error():
    connection = FakeConnection(fail_on="boom")

    with pytest.raises(RuntimeError):
        db.save_analysis(connection, make_result())

    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_record_does_nothing_without_database_url(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("must not connect")

    monkeypatch.setattr(db, "connect", fail)

    db.record(make_result())


def test_record_saves_and_closes_the_connection(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    get_settings.cache_clear()
    connection = FakeConnection()
    monkeypatch.setattr(db, "connect", lambda: connection)

    db.record(make_result(), PageData(url="https://shop.ro"))

    assert connection.commits == 1
    assert connection.closed is True


def test_record_swallows_database_errors(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    get_settings.cache_clear()

    def down():
        raise OSError("connection refused")

    monkeypatch.setattr(db, "connect", down)

    db.record(make_result())


def test_finished_analysis_is_recorded(monkeypatch, example_page):
    recorded = []
    monkeypatch.setattr(db, "record", lambda result, page=None: recorded.append((result, page)))

    result = analysis.run("id1", PageData.model_validate(example_page))

    assert recorded[0][0] is result
    assert recorded[0][1].url == example_page["url"]


# Runs against a real Postgres. Set TEST_DATABASE_URL to run it; it is skipped otherwise.
@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_round_trip_in_a_real_database():
    connection = db.connect(os.environ["TEST_DATABASE_URL"])
    try:
        db.ensure_schema(connection)
        db.ensure_schema(connection)  # running the setup twice is fine
        result = make_result()
        db.save_analysis(connection, result, PageData(url="https://shop.ro/p", title="Product"))
        db.save_analysis(connection, result, PageData(url="https://shop.ro/p", title="Product"))
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, trust_score, trust->>'score' FROM analyses WHERE id=%s", ("abc123",)
            )
            assert cursor.fetchone() == ("done", 80, "80")
            cursor.execute(
                "SELECT url, ai_probability, signals FROM image_results"
                " WHERE analysis_id=%s ORDER BY position",
                ("abc123",),
            )
            assert cursor.fetchall() == [
                ("https://x.ro/1.jpg", 0.9, ["no camera data"]),
                ("https://x.ro/2.jpg", 0.1, []),
            ]
            cursor.execute("DELETE FROM analyses WHERE id=%s", ("abc123",))
            cursor.execute("SELECT count(*) FROM image_results WHERE analysis_id=%s", ("abc123",))
            assert cursor.fetchone() == (0,)
        connection.commit()
    finally:
        connection.close()
