"""Keeps finished analyses in Redis so the API and worker share results (owner: Marius).

Results survive API restarts and expire after a set time (default: 24 hours).
"""

from typing import Final

from redis import Redis

from app.config import get_settings
from app.schemas import AnalysisResponse
from app.workers.queue import get_redis_connection as _get_default_connection

KEY_PREFIX: Final[str] = "analysis:"
DEFAULT_TTL_SECONDS: Final[int] = 24 * 60 * 60  # 24 hours


def get_redis_connection() -> Redis:
    """Returns a Redis connection for the result store."""
    return _get_default_connection()


def _make_key(analysis_id: str) -> str:
    return f"{KEY_PREFIX}{analysis_id}"


def save(
    result: AnalysisResponse,
    ttl: int | None = None,
    connection: Redis | None = None,
) -> None:
    """Saves an analysis response to Redis with an expiration TTL."""
    conn = connection or get_redis_connection()
    if ttl is None:
        ttl = get_settings().result_ttl_seconds
    key = _make_key(result.analysis_id)
    conn.set(key, result.model_dump_json(), ex=ttl)


def load(analysis_id: str, connection: Redis | None = None) -> AnalysisResponse | None:
    """Loads an analysis response from Redis by ID, or None if expired/not found."""
    conn = connection or get_redis_connection()
    key = _make_key(analysis_id)
    data = conn.get(key)
    if data is None:
        return None
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return AnalysisResponse.model_validate_json(data)


def get_ttl(analysis_id: str, connection: Redis | None = None) -> int:
    """Returns the remaining TTL in seconds for an analysis in Redis."""
    conn = connection or get_redis_connection()
    key = _make_key(analysis_id)
    return conn.ttl(key)


def delete(analysis_id: str, connection: Redis | None = None) -> bool:
    """Deletes an analysis from Redis."""
    conn = connection or get_redis_connection()
    key = _make_key(analysis_id)
    return bool(conn.delete(key))
