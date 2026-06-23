"""DEPRECATED: use revolut_app.fx_lab.pricing.policies instead."""

from revolut_app.fx_lab.pricing.policies import (
    InventoryAwareQuotePolicy,
    NaiveQuotePolicy,
    PlatformQuotePolicy,
    QuotePolicy,
    QuotePolicyName,
    RiskAwareQuotePolicy,
    build_quote_policy,
)

__all__ = [
    'InventoryAwareQuotePolicy',
    'NaiveQuotePolicy',
    'PlatformQuotePolicy',
    'QuotePolicy',
    'QuotePolicyName',
    'RiskAwareQuotePolicy',
    'build_quote_policy',
]
