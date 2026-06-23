"""DEPRECATED: use revolut_app.fx_lab.pricing.quote_engine instead."""

from revolut_app.fx_lab.market.mid_rate import StaticMidRateProvider
from revolut_app.fx_lab.pricing.quote_engine import QuoteEngine

__all__ = ['QuoteEngine', 'StaticMidRateProvider']
