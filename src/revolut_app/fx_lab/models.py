"""DEPRECATED: use bounded fx_lab packages instead."""

from revolut_app.fx_lab.experiments.models import FXEvent, FXEventDataset
from revolut_app.fx_lab.inventory.models import CurrencyState
from revolut_app.fx_lab.pricing.models import (
    FXQuote,
    FXQuoteComponents,
    QuoteRequest,
)
from revolut_app.fx_lab.shared.enums import (
    Currency,
    CustomerSegment,
    FXSide,
    HamiltonianPreset,
    StressRegime,
)

__all__ = [
    'Currency',
    'CurrencyState',
    'CustomerSegment',
    'FXEvent',
    'FXEventDataset',
    'FXQuote',
    'FXQuoteComponents',
    'FXSide',
    'HamiltonianPreset',
    'QuoteRequest',
    'StressRegime',
]
