import hashlib
import time

from app.config import get_settings
from app.schemas import ImageResult
from app.workers import cache


def test_cache_key_is_sha256_hash_of_url():
    url = "https://example.com/products/watch-photo-1.png"
    expected_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

    key = cache.make_cache_key(url)

    assert key == f"image:{expected_hash}"
    assert cache.hash_url(url) == expected_hash


def test_set_and_get_image_result(fake_redis):
    url = "https://example.com/shoes.jpg"
    result = ImageResult(
        url=url,
        ai_probability=0.88,
        signals=["[TEST] high frequency noise", "[TEST] c2pa missing"],
    )

    cache.set(url, result, connection=fake_redis)
    cached = cache.get(url, connection=fake_redis)

    assert cached is not None
    assert cached.url == url
    assert cached.ai_probability == 0.88
    assert cached.signals == ["[TEST] high frequency noise", "[TEST] c2pa missing"]


def test_configurable_ttl(fake_redis):
    url = "https://example.com/bag.jpg"
    result = ImageResult(url=url, ai_probability=0.12, signals=[])

    cache.set(url, result, ttl=3600, connection=fake_redis)
    ttl = cache.get_ttl(url, connection=fake_redis)

    assert 3590 <= ttl <= 3600


def test_default_ttl_uses_settings(fake_redis, monkeypatch):
    monkeypatch.setenv("IMAGE_CACHE_TTL_SECONDS", "7200")
    get_settings.cache_clear()

    url = "https://example.com/shirt.jpg"
    result = ImageResult(url=url, ai_probability=0.05, signals=[])

    cache.set(url, result, connection=fake_redis)
    ttl = cache.get_ttl(url, connection=fake_redis)

    assert 7190 <= ttl <= 7200


def test_cache_expiration(fake_redis):
    url = "https://example.com/temp.jpg"
    result = ImageResult(url=url, ai_probability=0.45, signals=[])

    cache.set(url, result, ttl=1, connection=fake_redis)
    assert cache.get(url, connection=fake_redis) is not None

    time.sleep(1.1)
    assert cache.get(url, connection=fake_redis) is None


def test_detect_with_cache_avoids_running_detector(fake_redis):
    url = "https://example.com/jacket.jpg"
    call_count = 0

    def mock_detector(image_url: str) -> ImageResult:
        nonlocal call_count
        call_count += 1
        return ImageResult(url=image_url, ai_probability=0.77, signals=["mock-detector"])

    # First call: runs the detector
    res1 = cache.detect_with_cache(url, detector=mock_detector, connection=fake_redis)
    assert call_count == 1
    assert res1.ai_probability == 0.77

    # Second call: fetches from cache, detector is NOT run again
    res2 = cache.detect_with_cache(url, detector=mock_detector, connection=fake_redis)
    assert call_count == 1
    assert res2.ai_probability == 0.77
    assert res2.signals == ["mock-detector"]


def test_analysing_same_page_twice_does_not_run_model_again(
    client, fake_redis, monkeypatch, example_page
):
    call_count = 0
    from app.ai.vision.detector import detect as original_detect

    def spy_detect(image_url: str) -> ImageResult:
        nonlocal call_count
        call_count += 1
        return original_detect(image_url)

    monkeypatch.setattr("app.ai.vision.detect", spy_detect)

    num_images = len(example_page["images"])
    assert num_images > 0

    # First analysis: model runs once for each image on the page
    res1 = client.post("/analyze", json=example_page)
    assert res1.status_code == 200
    assert call_count == num_images

    # Second analysis: analysing the same page MUST NOT run the model again
    res2 = client.post("/analyze", json=example_page)
    assert res2.status_code == 200
    assert call_count == num_images  # Call count remains unchanged!

    # Verify results match
    body1 = res1.json()
    body2 = res2.json()
    assert len(body2["images"]) == num_images
    assert body1["images"] == body2["images"]


def test_delete_and_missing(fake_redis):
    assert cache.get("https://example.com/missing.jpg", connection=fake_redis) is None
    assert cache.delete("https://example.com/missing.jpg", connection=fake_redis) is False

    dummy = ImageResult(url="https://example.com/del.jpg", ai_probability=0.2, signals=[])
    cache.set("https://example.com/del.jpg", dummy, connection=fake_redis)
    assert cache.get("https://example.com/del.jpg", connection=fake_redis) is not None

    assert cache.delete("https://example.com/del.jpg", connection=fake_redis) is True
    assert cache.get("https://example.com/del.jpg", connection=fake_redis) is None
