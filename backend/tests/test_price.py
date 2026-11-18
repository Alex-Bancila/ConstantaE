import pytest

from app.schemas import PageData
from app.services.price import find_reference
from app.services.trust import run_trust_checks


def price_check(title: str | None, price: float | None, currency: str | None = "RON"):
    page = PageData(url="https://shop.ro", title=title, price=price, currency=currency)
    checks = run_trust_checks(page).checks
    return next((check for check in checks if check.id == "suspicious_price"), None)


def test_far_below_typical_price_fails_and_explains_why():
    check = price_check("iPhone 16 Pro Max 256GB Titanium Blue - Sigilat", 850)

    assert check.passed is False
    assert "87% below" in check.message
    assert "iPhone 16 Pro Max" in check.message
    assert "850" in check.message
    assert "6 500" in check.message


def test_normal_price_passes():
    check = price_check("Apple iPhone 16 Pro Max 256GB", 6199)

    assert check.passed is True
    assert "iPhone 16 Pro Max" in check.message


def test_price_just_above_half_is_not_flagged():
    assert price_check("iPhone 16 Pro Max", 3300).passed is True
    assert price_check("iPhone 16 Pro Max", 3200).passed is False


@pytest.mark.parametrize(
    "title",
    [
        "Husa silicon pentru iPhone 16 Pro Max",
        "Folie sticla iPhone 16 Pro Max",
        "iPhone 16 Pro Max folosit, stare buna",
        "iPhone 16 Pro Max second hand",
    ],
)
def test_accessories_and_used_goods_are_not_judged(title):
    assert price_check(title, 60) is None


def test_unknown_product_is_skipped():
    assert price_check("Bicicleta trekking Riverside 500", 750) is None
    assert price_check(None, 100) is None


@pytest.mark.parametrize(
    ("price", "currency"), [(None, "RON"), (0, "RON"), (-5, "RON"), (100, "EUR"), (100, None)]
)
def test_missing_or_foreign_price_is_skipped(price, currency):
    assert price_check("iPhone 16 Pro Max", price, currency) is None


def test_most_specific_product_wins():
    assert find_reference("iPhone 16 Pro Max 512GB").name == "iPhone 16 Pro Max"
    assert find_reference("iPhone 16 Pro 256GB").name == "iPhone 16 Pro"
    assert find_reference("iPhone 16 128GB").name == "iPhone 16"


def test_matching_ignores_case_and_diacritics():
    assert find_reference("PLAYSTATION 5 Slim, Edi?ie Digitala").name == "PlayStation 5"


def test_a_different_model_does_not_match():
    assert find_reference("iPhone 14 128GB") is None
