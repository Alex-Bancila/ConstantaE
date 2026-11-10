"""Keeps finished analyses so GET /analyze/{id} can return them.

In memory for now, so results are lost when the server restarts and a separate
worker process cannot write here.
TODO(Marius, David): move this to Redis or Postgres.
"""

from app.schemas import AnalysisResponse

_results: dict[str, AnalysisResponse] = {}


def save(result: AnalysisResponse) -> None:
    _results[result.analysis_id] = result


def load(analysis_id: str) -> AnalysisResponse | None:
    return _results.get(analysis_id)
