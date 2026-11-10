"""Background job queue for the slow AI work (owner: Marius).

Only used when ASYNC=true. Until it exists, keep ASYNC=false.

TODO(Marius):
- a Redis-backed queue (RQ or Celery) and a worker process
- one job per image; when all are done, save the finished AnalysisResponse
  with store.save() so GET /analyze/{id} returns it
- cache image results by a hash of the image URL, so a page seen before is instant
"""

from app.schemas import PageData


def enqueue(analysis_id: str, page: PageData) -> None:
    raise NotImplementedError("TODO(Marius): job queue. Use ASYNC=false for now.")
