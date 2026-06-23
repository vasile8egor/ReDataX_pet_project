from revolut_app.fx_lab.shared.constants import (
    MID_RATE_PRECISION,
    USD_MARKS as DEFAULT_USD_MARKS,
)
from revolut_app.fx_lab.shared.enums import Currency


class StaticMidRateProvider:
    USD_MARKS = DEFAULT_USD_MARKS

    def get_mid_rate(
        self,
        base_currency: Currency,
        quote_currency: Currency,
    ) -> float:
        base_usd = self.USD_MARKS[base_currency.value]
        quote_usd = self.USD_MARKS[quote_currency.value]
        return round(base_usd / quote_usd, MID_RATE_PRECISION)
