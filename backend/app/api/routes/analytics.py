"""Analytics and model-performance routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.schemas.analytics import AnalyticsSummary, ModelPerformance
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def summary(
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=90)] = 14,
) -> AnalyticsSummary:
    """Every figure on the analytics page, in one request.

    Bundled rather than split across six endpoints so the panels cannot
    disagree with each other by being computed seconds apart, and so the page
    costs one round trip instead of six.
    """
    return AnalyticsSummary.model_validate(await analytics_service.summary(session, days=days))


@router.get("/model", response_model=ModelPerformance)
async def model_performance() -> ModelPerformance:
    """Offline evaluation metrics from the last training run."""
    metrics = analytics_service.model_performance()
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No trained model found. Run: python -m ml.train",
        )
    return ModelPerformance.model_validate(metrics)
