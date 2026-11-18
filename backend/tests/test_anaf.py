import io
import json
import urllib.error

import pytest

from app.config import get_settings
from app.schemas import PageData, Seller
from app.services import anaf
from app.services.trust import run_trust_checks

CUI = "14399840"


def found(name="ACME SRL", inactive=False):
    return {
        "found": [
            {
                "date_generale": {"cui": int(CUI), "denumire": name},
                "stare_inactiv": {"statusInactivi": inactive},
            }
        ],
        "notFound": [],
    }


@pytest.fixture
def anaf_on(monkeypatch):
    monkeypatch.setenv("ANAF_CHECK", "true")
    get_settings.cache_clear()


@pytest.fixture
def anaf_reply(monkeypatch, anaf_on):
    """Fake the HTTP call. Set anaf_reply.payload (or .error) and read anaf_reply.calls."""

    class Reply:
        payload: dict = found()
        error: Exception | None = None
        calls = 0

    def fake_urlopen(request, timeout):
        Reply.calls += 1
        if Reply.error:
            raise Reply.error
        return io.BytesIO(json.dumps(Reply.payload).encode())

    monkeypatch.setattr(anaf.urllib.request, "urlopen", fake_urlopen)
    return Reply


def anaf_check(cui: str | None = CUI):
    page = PageData(url="https://shop.ro", seller=Seller(cui=cui))
    checks = run_trust_checks(page).checks
    return next((check for check in checks if check.id == "cui_anaf"), None)


def test_active_company_passes_and_shows_name(anaf_reply):
    check = anaf_check()

    assert check.passed is True
    assert "ACME SRL" in check.message


def test_inactive_company_fails(anaf_reply):
    anaf_reply.payload = found(inactive=True)

    check = anaf_check()

    assert check.passed is False
    assert "ACME SRL" in check.message
    assert "inactive" in check.message


def test_unknown_company_fails(anaf_reply):
    anaf_reply.payload = {"found": [], "notFound": [{"cui": int(CUI)}]}

    check = anaf_check()

    assert check.passed is False
    assert "no company" in check.message


def test_http_404_means_unknown_company(anaf_reply):
    anaf_reply.error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)

    check = anaf_check()

    assert check.passed is False
    assert "no company" in check.message


def test_http_500_skips_the_check(anaf_reply):
    anaf_reply.error = urllib.error.HTTPError("url", 500, "Server Error", {}, None)

    assert anaf_check() is None


@pytest.mark.parametrize(
    "error",
    [TimeoutError(), urllib.error.URLError("down"), json.JSONDecodeError("bad", "", 0)],
)
def test_slow_or_broken_anaf_skips_the_check(anaf_reply, error):
    anaf_reply.error = error

    assert anaf_check() is None


def test_unexpected_anaf_answer_skips_the_check(anaf_reply):
    anaf_reply.payload = {"cod": 500, "message": "error"}

    assert anaf_check() is None


def test_skipped_check_does_not_change_the_score(anaf_reply):
    anaf_reply.error = TimeoutError()
    page = PageData(url="https://shop.ro", seller=Seller(cui=CUI))

    report = run_trust_checks(page)

    assert [check.id for check in report.checks].count("cui_anaf") == 0
    assert len(report.checks) == 5
    assert report.score == 40  # https and the CUI check digit pass


def test_same_cui_is_looked_up_once(anaf_reply):
    anaf_check()
    anaf_check("RO 14399840")

    assert anaf_reply.calls == 1


def test_invalid_cui_is_not_sent_to_anaf(anaf_reply):
    assert anaf_check("14399841") is None
    assert anaf_check(None) is None
    assert anaf_reply.calls == 0


def test_check_can_be_turned_off(anaf_reply, monkeypatch):
    monkeypatch.setenv("ANAF_CHECK", "false")
    get_settings.cache_clear()

    assert anaf_check() is None
    assert anaf_reply.calls == 0


def test_request_sends_the_cui_and_timeout(monkeypatch, anaf_on):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["body"] = json.loads(request.data)
        seen["timeout"] = timeout
        return io.BytesIO(json.dumps(found()).encode())

    monkeypatch.setattr(anaf.urllib.request, "urlopen", fake_urlopen)

    anaf.lookup_company(CUI)

    assert seen["body"][0]["cui"] == int(CUI)
    assert seen["timeout"] == 3.0
