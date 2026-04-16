from fastapi import APIRouter

from app.models import AnalysisRunSummary
from app.services.analysis_store import list_runs

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[AnalysisRunSummary])
def get_runs() -> list[AnalysisRunSummary]:
    return list_runs()
