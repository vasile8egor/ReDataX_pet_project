"""DEPRECATED: use revolut_app.fx_lab.inventory.hedging instead."""

from revolut_app.fx_lab.inventory.hedging import (
    HedgeAction,
    HedgeAmountDecision,
    HedgeEngine,
    HedgeRecommendation,
    HedgeRecommendationResult,
)

__all__ = [
    'HedgeAction',
    'HedgeAmountDecision',
    'HedgeEngine',
    'HedgeRecommendation',
    'HedgeRecommendationResult',
]
