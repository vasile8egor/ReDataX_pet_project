from fastapi import APIRouter, status

from revolut_app.api_service.schemas.fx import (
    DaySimulationRequest,
    DaySimulationResponse,
    FXQuoteRequest,
    FXQuoteResponse,
    HedgeExecutionRequest,
    HedgeExecutionResponse,
    HedgeRecommendationResponse,
    HedgeRecommendationRequest,
    PnLSnapshotResponse,
    PolicyComparisonRequest,
    PolicyComparisonResponse,
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
def quote_fx(request: FXQuoteRequest):
    return fx_quote_service.quote(request)


@router.post(
    '/stress-shock',
    response_model=RiskSnapshotResponse,
    status_code=status.HTTP_200_OK,
)
def run_stress(request: StressShockRequest):
    return fx_quote_service.apply_stress_shock(
        volatility_multiplier=request.volatility_multiplier,
        hedge_capacity_multiplier=request.hedge_capacity_multiplier,
    )


@router.post(
    '/simulate-day',
    response_model=DaySimulationResponse,
    status_code=status.HTTP_200_OK,
)
def simulate_day(request: DaySimulationRequest):
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
):
    return fx_quote_service.hedge_recommendation(request)


@router.post(
    '/execute-hedge',
    response_model=HedgeExecutionResponse,
    status_code=status.HTTP_200_OK,
)
def hedge_execution(
    request: HedgeExecutionRequest,
):
    return fx_quote_service.execute_hedge(request)


@router.post(
    '/policy-comparison',
    response_model=PolicyComparisonResponse,
    status_code=status.HTTP_200_OK,
)
def policy_comparison(
    request: PolicyComparisonRequest,
):
    return fx_quote_service.policy_comparison(request)


@router.get(
    '/risk-snapshot',
    response_model=RiskSnapshotResponse,
    status_code=status.HTTP_200_OK,
)
def get_risk_snapshot():
    return fx_quote_service.risk_snapshot()


@router.get(
    '/pnl-snapshot',
    response_model=PnLSnapshotResponse,
    status_code=status.HTTP_200_OK,
)
def pnl_snapshot():
    return fx_quote_service.pnl_snapshot()
