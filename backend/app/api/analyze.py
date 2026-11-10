from fastapi import APIRouter, HTTPException

from app.schemas import AnalysisResponse, PageData
from app.services import analysis

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(page: PageData) -> AnalysisResponse:
    return analysis.start(page)


@router.get("/analyze/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str) -> AnalysisResponse:
    result = analysis.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result
