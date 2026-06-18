from fastapi import APIRouter, status

from revolut_app.api_service.schemas.fx import (
    DaySimulationRequest,
    DaySimulationResponse,
    FXQuoteRequest,
    FXQuoteResponse,
    HedgeRecommendationResponse,
    HedgeRecommendationRequest,
    RGFlowRequest,
    RGFlowResponse,
    RiskSnapshotResponse,
    StressShockRequest,
)
from revolut_app.api_service.services.fx_quote_service import (
    FXQuoteService
)

router = APIRouter(prefix='/fx', tags=['fx'])

fx_quote_service = FXQuoteService()


@router.post(
    '/quote',
    response_model=FXQuoteResponse,
    status_code=status.HTTP_200_OK,
)
def quote_fx(request: FXQuoteRequest) -> FXQuoteResponse:
    return fx_quote_service.quote(request)


@router.post(
    '/stress-shock',
    response_model=RiskSnapshotResponse,
    status_code=status.HTTP_200_OK,
)
def run_stress(request: StressShockRequest) -> RiskSnapshotResponse:
    return fx_quote_service.apply_stress_shock(
        volatility_multiplier=request.volatility_multiplier,
        hedge_capacity_multiplier=request.hedge_capacity_multiplier,
    )


@router.post(
    '/simulate-day',
    response_model=DaySimulationResponse,
    status_code=status.HTTP_200_OK,
)
def simulate_day(request: DaySimulationRequest) -> DaySimulationResponse:
    return fx_quote_service.simulate_day(request)


@router.post(
    '/rg-flow',
    response_model=RGFlowResponse,
    status_code=status.HTTP_200_OK,
)
def rg_flow(request: RGFlowRequest):
    return fx_quote_service.rg_flow(request)


@router.post(
    '/hedge-recommendation',
    response_model=HedgeRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
def hedge_recommendation(
    request: HedgeRecommendationRequest,
) -> HedgeRecommendationResponse:
    return fx_quote_service.hedge_recommendation(request)


@router.get(
    '/risk-snapshot',
    response_model=RiskSnapshotResponse,
    status_code=status.HTTP_200_OK,
)
def get_risk_snapshot() -> RiskSnapshotResponse:
    return fx_quote_service.risk_snapshot()
