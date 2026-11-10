from app.schemas import LegalLinks, PageData
from app.services.trust import run_trust_checks


def checks_by_id(page: PageData) -> dict[str, bool]:
    return {check.id: check.passed for check in run_trust_checks(page).checks}


def test_missing_anpc_link_fails():
    page = PageData(url="https://shop.ro", legal_links=LegalLinks(anpc=False, sol=True))

    assert checks_by_id(page)["anpc_link"] is False
    assert checks_by_id(page)["sol_link"] is True


def test_http_site_fails_https_check():
    assert checks_by_id(PageData(url="http://shop.ro"))["https"] is False


def test_score_is_share_of_passed_checks():
    assert run_trust_checks(PageData(url="http://shop.ro")).score == 0
