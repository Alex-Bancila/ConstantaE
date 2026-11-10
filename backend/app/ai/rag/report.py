"""Generates the legal report for a page (owner: Lucas).

TODO(Lucas):
- turn each failed trust check into a question (e.g. missing CUI -> which seller
  details must be shown?) and always ask about the 14-day right of withdrawal
- retrieve the matching articles from pgvector (hybrid: full-text + vector search)
- ask the LLM for a short summary that cites ONLY the retrieved articles
- return those articles as citations
"""

from app.config import get_settings
from app.mock import mock_analysis
from app.schemas import LegalReport, PageData, TrustCheck


def generate_report(page: PageData, failed_checks: list[TrustCheck]) -> LegalReport:
    if get_settings().ai_mode == "mock":
        legal = mock_analysis().legal
        assert legal is not None
        return legal
    raise NotImplementedError("TODO(Lucas): real legal report. Use AI_MODE=mock for now.")
