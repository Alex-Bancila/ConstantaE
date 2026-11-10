"""Rule-based checks of whether the seller and the offer look legitimate (owner: David).

Each check takes the page data and returns a TrustCheck. To add a check, write a
function and add it to CHECKS.

TODO(David):
- cui_valid: validate the CUI check digit, not just its presence
- optional: confirm the CUI exists with ANAF's free public API
- suspicious_price: flag prices far below what the product usually costs
"""

from collections.abc import Callable

from app.schemas import PageData, TrustCheck, TrustReport


def check_https(page: PageData) -> TrustCheck:
    passed = page.url.startswith("https://")
    message = "The site uses HTTPS." if passed else "The site does not use HTTPS."
    return TrustCheck(id="https", passed=passed, message=message)


def check_cui_present(page: PageData) -> TrustCheck:
    passed = bool(page.seller.cui)
    message = (
        f"Company registration number found: {page.seller.cui}."
        if passed
        else "No company registration number (CUI) was found on the page."
    )
    return TrustCheck(id="cui_present", passed=passed, message=message)


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
    check_cui_present,
    check_anpc_link,
    check_sol_link,
    check_return_policy,
]


def run_trust_checks(page: PageData) -> TrustReport:
    checks = [check(page) for check in CHECKS]
    score = round(100 * sum(check.passed for check in checks) / len(checks))
    return TrustReport(score=score, checks=checks)
