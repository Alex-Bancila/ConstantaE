"""Rule-based checks of whether the seller and the offer look legitimate (owner: David).

Each check takes the page data and returns a TrustCheck. To add a check, write a
function and add it to CHECKS.

TODO(David):
- optional: confirm the CUI exists with ANAF's free public API
- suspicious_price: flag prices far below what the product usually costs
"""

import re
from collections.abc import Callable

from app.schemas import PageData, TrustCheck, TrustReport

# Weights for the Romanian CUI/CIF check digit, applied to the digits before it.
_CUI_KEY = "753217532"
# Optional "RO" (VAT) prefix, then 2-10 digits; the last digit is the check digit.
_CUI_PATTERN = re.compile(r"(?:RO)?([0-9]{2,10})")


def normalize_cui(raw: str) -> str | None:
    """Return the CUI digits without the "RO" prefix, or None if the format is wrong."""
    cleaned = re.sub(r"\s+", "", raw).upper()
    match = _CUI_PATTERN.fullmatch(cleaned)
    return match.group(1) if match else None


def _cui_check_digit(base: str) -> int:
    padded = base.zfill(len(_CUI_KEY))
    total = sum(int(digit) * int(weight) for digit, weight in zip(padded, _CUI_KEY, strict=True))
    control = total * 10 % 11
    return 0 if control == 10 else control


def is_valid_cui(raw: str) -> bool:
    """True if the CUI is well formed and its check digit matches."""
    digits = normalize_cui(raw)
    return digits is not None and _cui_check_digit(digits[:-1]) == int(digits[-1])


def check_https(page: PageData) -> TrustCheck:
    passed = page.url.startswith("https://")
    message = "The site uses HTTPS." if passed else "The site does not use HTTPS."
    return TrustCheck(id="https", passed=passed, message=message)


def check_cui_valid(page: PageData) -> TrustCheck:
    cui = (page.seller.cui or "").strip()
    if not cui:
        passed = False
        message = "No company registration number (CUI) was found on the page."
    elif normalize_cui(cui) is None:
        passed = False
        message = f'The company registration number (CUI) "{cui}" is not in a valid format.'
    elif not is_valid_cui(cui):
        passed = False
        message = (
            f'The company registration number (CUI) "{cui}" is invalid: '
            "its check digit does not match."
        )
    else:
        passed = True
        message = f"Valid company registration number (CUI): {cui}."
    return TrustCheck(id="cui_valid", passed=passed, message=message)


def check_anpc_link(page: PageData) -> TrustCheck:
    passed = page.legal_links.anpc
    message = (
        "The ANPC link required by law is present."
        if passed
        else "The ANPC link required by law is missing."
    )
    return TrustCheck(id="anpc_link", passed=passed, message=message)


def check_sol_link(page: PageData) -> TrustCheck:
    passed = page.legal_links.sol
    message = (
        "The SOL (EU online dispute resolution) link is present."
        if passed
        else "The SOL (EU online dispute resolution) link is missing."
    )
    return TrustCheck(id="sol_link", passed=passed, message=message)


def check_return_policy(page: PageData) -> TrustCheck:
    passed = page.has_return_policy
    message = "A return policy was found." if passed else "No return policy was found."
    return TrustCheck(id="return_policy", passed=passed, message=message)


CHECKS: list[Callable[[PageData], TrustCheck]] = [
    check_https,
    check_cui_valid,
    check_anpc_link,
    check_sol_link,
    check_return_policy,
]


def run_trust_checks(page: PageData) -> TrustReport:
    checks = [check(page) for check in CHECKS]
    score = round(100 * sum(check.passed for check in checks) / len(checks))
    return TrustReport(score=score, checks=checks)
