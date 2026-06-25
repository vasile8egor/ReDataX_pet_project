from enum import Enum


class ScaleAwareDiagnosticPreset(str, Enum):
    RG_LOCAL_B16_V1 = "rg-local-b16-v1"


class HamiltonianControllerPreset(str, Enum):
    symmetric_v1 = 'symmetric-v1'
    directional_v2 = 'directional-v2'


class HamiltonianPreset(str, Enum):
    local_v1 = 'local-v1'
    coupled_v1 = 'coupled-v1'


class Currency(str, Enum):
    GBP = 'GBP'
    EUR = 'EUR'
    USD = 'USD'


class FXSide(str, Enum):
    buy = 'buy'
    sell = 'sell'


class CustomerSegment(str, Enum):
    retail = 'retail'
    premium = 'premium'
    business = 'business'


class StressRegime(str, Enum):
    calm = 'calm'
    elevated = 'elevated'
    stress = 'stress'
