"""Loads the shared mock data used when AI_MODE=mock."""

from functools import lru_cache

from app.config import MOCK_ANALYSIS_FILE
from app.schemas import AnalysisResponse


@lru_cache
def mock_analysis() -> AnalysisResponse:
    return AnalysisResponse.model_validate_json(MOCK_ANALYSIS_FILE.read_text(encoding="utf-8"))
