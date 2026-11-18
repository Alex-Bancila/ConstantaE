"""Compares an offer's price with the typical price of the product (owner: David).

The reference prices are a small hand-maintained list in data/reference_prices.json.
A product is recognised from the listing title. Offers for products that are not in the
list are not judged, so the check is skipped for them.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

REFERENCE_FILE: Final[Path] = Path(__file__).resolve().parents[2] / "data" / "reference_prices.json"
CURRENCY: Final[str] = "RON"
# An offer below this share of the typical price is suspicious.
SUSPICIOUS_BELOW: Final[float] = 0.5
# Titles with these words are accessories or used goods, which legitimately cost far less.
IGNORED_WORDS: Final[frozenset[str]] = frozenset(
    {
        "husa",
        "huse",
        "folie",
        "cablu",
        "incarcator",
        "carcasa",
        "case",
        "cover",
        "protectie",
        "geam",
        "sticla",
        "suport",
        "accesoriu",
        "accesorii",
        "defect",
        "folosit",
        "folosita",
        "second",
        "hand",
        "used",
        "piese",
        "reconditionat",
        "schimb",
    }
)


@dataclass(frozen=True)
class ReferencePrice:
    name: str
    price: float
    keywords: frozenset[str]


def _words(text: str) -> set[str]:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return set(re.findall(r"[a-z0-9]+", ascii_text.lower()))


@lru_cache
def load_reference_prices(path: Path = REFERENCE_FILE) -> tuple[ReferencePrice, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        ReferencePrice(item["name"], float(item["price"]), frozenset(item["keywords"]))
        for item in data["products"]
    )


def find_reference(title: str | None) -> ReferencePrice | None:
    """Return the most specific product whose keywords all appear in the title."""
    if not title:
        return None
    words = _words(title)
    if words & IGNORED_WORDS:
        return None
    matches = [ref for ref in load_reference_prices() if ref.keywords <= words]
    return max(matches, key=lambda ref: len(ref.keywords), default=None)


def discount(price: float, reference: ReferencePrice) -> float:
    """Share of the typical price that the offer is below it, from 0 to 1 (negative if above)."""
    return 1 - price / reference.price


def is_suspicious(price: float, reference: ReferencePrice) -> bool:
    return price < reference.price * SUSPICIOUS_BELOW
