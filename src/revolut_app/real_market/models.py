from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path


class AggressorSide(str, Enum):
    BUY_BASE = 'buy_base'
    SELL_BASE = 'sell_base'


@dataclass(frozen=True, slots=True)
class BinanceAggTradeArchiveSpec:
    symbol: str
    trade_date: date

    def __post_init__(self):
        normalized_symbol = self.symbol.upper()

        if not normalized_symbol:
            raise ValueError(
                'symbol cannot be empty'
            )

        if not normalized_symbol.isalnum():
            raise ValueError(
                'symbol must contain only '
                'letters and digits'
            )

        object.__setattr__(
            self,
            'symbol',
            normalized_symbol,
        )

    @property
    def filename(self):
        return (
            f'''{self.symbol}-aggTrades-'''
            f'''{self.trade_date.isoformat()}.zip'''
        )

    @property
    def checksum_filename(self):
        return f'''{self.filename}.CHECKSUM'''

    @property
    def relative_path(self):
        return (
            'data/spot/daily/aggTrades/'
            f'''{self.symbol}/{self.filename}'''
        )


@dataclass(frozen=True, slots=True)
class DownloadedBinanceArchive:
    spec: BinanceAggTradeArchiveSpec

    archive_path: Path
    checksum_path: Path

    expected_sha256: str
    actual_sha256: str


@dataclass(frozen=True, slots=True)
class BinanceAggTrade:
    symbol: str

    aggregate_trade_id: int

    price: Decimal
    quantity: Decimal

    first_trade_id: int
    last_trade_id: int

    timestamp_us: int

    buyer_was_maker: bool
    best_price_match: bool

    aggressor_side: AggressorSide

    @property
    def quote_quantity(self):
        return self.price * self.quantity


@dataclass(frozen=True, slots=True)
class BinanceAggTradeArchiveSummary:
    symbol: str
    trade_date: date

    row_count: int

    first_aggregate_trade_id: int
    last_aggregate_trade_id: int

    first_timestamp_us: int
    last_timestamp_us: int

    buy_aggressor_count: int
    sell_aggressor_count: int

    missing_aggregate_trade_ids: int

    total_base_quantity: Decimal
    total_quote_notional: Decimal

    archive_sha256: str
