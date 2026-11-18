import pytest

from app.schemas import LegalLinks, PageData, Seller
from app.services.trust import is_valid_cui, normalize_cui, run_trust_checks


def checks_by_id(page: PageData) -> dict[str, bool]:
    return {check.id: check.passed for check in run_trust_checks(page).checks}


def cui_check(cui: str | None):
    page = PageData(url="https://shop.ro", seller=Seller(cui=cui))
    return next(check for check in run_trust_checks(page).checks if check.id == "cui_valid")


def test_missing_anpc_link_fails():
    page = PageData(url="https://shop.ro", legal_links=LegalLinks(anpc=False, sol=True))

    assert checks_by_id(page)["anpc_link"] is False
    assert checks_by_id(page)["sol_link"] is True


def test_http_site_fails_https_check():
    assert checks_by_id(PageData(url="http://shop.ro"))["https"] is False


def test_score_is_share_of_passed_checks():
    assert run_trust_checks(PageData(url="http://shop.ro")).score == 0


VALID_CUIS = ["14399840", "RO14399840", "ro14399840", "RO 14399840", " 18189442 ", "12345674"]
WRONG_CHECK_DIGIT_CUIS = ["14399841", "RO14399841", "12345678", "RO12345678"]
ARABIC_INDIC_DIGITS = "\u0661\u0664\u0663\u0669\u0669\u0668\u0664\u0660"  # "14399840", non-ASCII
MALFORMED_CUIS = ["ABC", "RO", "1", "12345678901", "RO-1439A840", ARABIC_INDIC_DIGITS]


@pytest.mark.parametrize("cui", VALID_CUIS)
def test_valid_cui_passes(cui):
    check = cui_check(cui)

    assert check.passed is True
    assert is_valid_cui(cui) is True


@pytest.mark.parametrize("cui", WRONG_CHECK_DIGIT_CUIS)
def test_wrong_check_digit_fails_with_clear_message(cui):
    check = cui_check(cui)

    assert check.passed is False
    assert "check digit" in check.message
    assert is_valid_cui(cui) is False


@pytest.mark.parametrize("cui", MALFORMED_CUIS)
def test_malformed_cui_fails(cui):
    check = cui_check(cui)

    assert check.passed is False
    assert "not in a valid format" in check.message
    assert is_valid_cui(cui) is False


@pytest.mark.parametrize("cui", [None, "", "   "])
def test_missing_cui_fails(cui):
    check = cui_check(cui)

    assert check.passed is False
    assert "No company registration number" in check.message


def test_normalize_cui_strips_ro_prefix_and_spaces():
    assert normalize_cui("RO 14399840") == "14399840"
    assert normalize_cui("14399840") == "14399840"
    assert normalize_cui("RO-14399840") is None
