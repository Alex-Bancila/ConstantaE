"""The shared example files must always match the schemas."""

import json

from app.config import MOCK_ANALYSIS_FILE, REPO_ROOT
from app.schemas import AnalysisResponse, PageData


def test_mock_analysis_matches_schema():
    AnalysisResponse.model_validate_json(MOCK_ANALYSIS_FILE.read_text(encoding="utf-8"))


def test_example_page_matches_schema():
    data = json.loads((REPO_ROOT / "shared" / "example-page.json").read_text(encoding="utf-8"))
    PageData.model_validate(data)
