"""Looks up a company in ANAF's free public VAT register (owner: David).

Docs: https://static.anaf.ro/static/10/Anaf/Informatii_R/Servicii_web/doc_WS_V9.txt
ANAF allows at most 1 request per second per client.
Results are cached in Redis so the same CUI is not looked up twice. Every failure
(network, timeout, bad response, Redis down) is reported as "unavailable", so the
caller can skip the check instead of failing it.
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Final

from redis import RedisError

from app.config import get_settings
from app.workers.queue import get_redis_connection

logger = logging.getLogger(__name__)

ANAF_URL: Final[str] = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"
KEY_PREFIX: Final[str] = "anaf:"


@dataclass(frozen=True)
class CompanyInfo:
    cui: str
    name: str
    active: bool


class CompanyNotFound(Exception):
    """ANAF answered, and the CUI is not in its register."""


class AnafUnavailable(Exception):
    """ANAF could not be reached or returned something unusable."""


def _fetch(cui: str, timeout: float) -> CompanyInfo:
    body = json.dumps([{"cui": int(cui), "data": date.today().isoformat()}]).encode()
    request = urllib.request.Request(
        ANAF_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.load(response)
        if not payload.get("found"):
            if payload.get("notFound"):
                raise CompanyNotFound(cui)
            raise AnafUnavailable(f"unexpected ANAF answer: {str(payload)[:200]}")
        entry = payload["found"][0]
        general = entry["date_generale"]
        inactive = bool((entry.get("stare_inactiv") or {}).get("statusInactivi"))
        return CompanyInfo(cui=cui, name=str(general["denumire"]).strip(), active=not inactive)
    except (CompanyNotFound, AnafUnavailable):
        raise
    except urllib.error.HTTPError as error:
        # For a CUI that does not exist, ANAF answers 404 with an empty body.
        if error.code == 404:
            raise CompanyNotFound(cui) from error
        raise AnafUnavailable(str(error)) from error
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise AnafUnavailable(str(error)) from error


def _cache_get(cui: str) -> CompanyInfo | None:
    try:
        data = get_redis_connection().get(KEY_PREFIX + cui)
        if data is None:
            return None
        values = json.loads(data)
        return CompanyInfo(cui=cui, name=values["name"], active=values["active"])
    except (RedisError, ValueError, KeyError, TypeError) as error:
        logger.warning("ANAF cache read failed: %s", error)
        return None


def _cache_set(info: CompanyInfo) -> None:
    ttl = get_settings().anaf_cache_ttl_seconds
    value = json.dumps({"name": info.name, "active": info.active})
    try:
        get_redis_connection().set(KEY_PREFIX + info.cui, value, ex=ttl)
    except RedisError as error:
        logger.warning("ANAF cache write failed: %s", error)


def lookup_company(cui: str) -> CompanyInfo:
    """Return the company for a normalized CUI (digits only).

    Raises CompanyNotFound if ANAF does not know it, AnafUnavailable on any other failure.
    """
    cached = _cache_get(cui)
    if cached is not None:
        return cached
    info = _fetch(cui, get_settings().anaf_timeout_seconds)
    _cache_set(info)
    return info
