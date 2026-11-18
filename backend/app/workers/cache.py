"""Cache for AI image detection results (owner: Marius).

Stores ImageResult objects in Redis, keyed by the SHA-256 hash of the image URL.
Prevents re-running slow vision models for images that have already been analysed.
"""

import hashlib
from collections.abc import Callable
from typing import Final

from redis import Redis

from app.config import get_settings
from app.schemas import ImageResult
from app.workers.queue import get_redis_connection as _get_default_connection

KEY_PREFIX: Final[str] = "image:"
DEFAULT_CACHE_TTL_SECONDS: Final[int] = 7 * 24 * 60 * 60  # 7 days


def get_redis_connection() -> Redis:
    """Returns a Redis connection for the image cache."""
    return _get_default_connection()


def hash_url(image_url: str) -> str:
    """Computes a SHA-256 hash of the image URL."""
    return hashlib.sha256(image_url.strip().encode("utf-8")).hexdigest()


def make_cache_key(image_url: str) -> str:
    """Constructs the Redis key for an image URL."""
    return f"{KEY_PREFIX}{hash_url(image_url)}"


def get(image_url: str, connection: Redis | None = None) -> ImageResult | None:
    """Retrieves a cached ImageResult for the URL, or None if not cached or expired."""
    conn = connection or get_redis_connection()
    key = make_cache_key(image_url)
    data = conn.get(key)
    if data is None:
        return None
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return ImageResult.model_validate_json(data)


def set(
    image_url: str,
    result: ImageResult,
    ttl: int | None = None,
    connection: Redis | None = None,
) -> None:
    """Stores an ImageResult in Redis with a configurable TTL."""
    conn = connection or get_redis_connection()
    if ttl is None:
        ttl = get_settings().image_cache_ttl_seconds
    key = make_cache_key(image_url)
    conn.set(key, result.model_dump_json(), ex=ttl)


def get_ttl(image_url: str, connection: Redis | None = None) -> int:
    """Returns the remaining TTL in seconds for an image cache entry."""
    conn = connection or get_redis_connection()
    key = make_cache_key(image_url)
    return conn.ttl(key)


def delete(image_url: str, connection: Redis | None = None) -> bool:
    """Deletes an image cache entry."""
    conn = connection or get_redis_connection()
    key = make_cache_key(image_url)
    return bool(conn.delete(key))


def detect_with_cache(
    image_url: str,
    detector: Callable[[str], ImageResult] | None = None,
    ttl: int | None = None,
    connection: Redis | None = None,
) -> ImageResult:
    """Returns the cached ImageResult or runs the detector and caches the result."""
    cached = get(image_url, connection=connection)
    if cached is not None:
        return cached

    if detector is None:
        from app.ai.vision import detect as default_detect

        detector = default_detect

    result = detector(image_url)
    set(image_url, result, ttl=ttl, connection=connection)
    return result
