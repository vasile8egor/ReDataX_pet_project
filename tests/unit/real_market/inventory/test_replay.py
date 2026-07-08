from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from revolut_app.real_market.inventory.models import (
    UnifiedMarketEvent,
)
from revolut_app.real_market.inventory.replay import (
    calculate_passive_maker_delta,
    replay_passive_market_maker_inventory,
)


def make_event(
    *,
    event_index: int,
    symbol: str,
    side: str,
    price: str,
    quantity: str,
):
    price_decimal = Decimal(price)
    quantity_decimal = Decimal(quantity)

    return UnifiedMarketEvent(
        trade_date=date(2025, 1, 6),
        event_index=event_index,
        symbol=symbol,
        aggregate_trade_id=event_index,
        event_timestamp=datetime(2025, 1, 6, tzinfo=timezone.utc),
        timestamp_us=(
            1736121600000000 + event_index
        ),
        price=price_decimal,
        base_quantity=quantity_decimal,
        quote_quantity=price_decimal*quantity_decimal,
        aggressor_side=side,
    )


def test_btcusdt_aggressor_buy():
    event = make_event(
        event_index=1,
        symbol='BTCUSDT',
        side='buy_base',
        price='100000',
        quantity='0.1',
    )

    delta = calculate_passive_maker_delta(
        event
    )

    assert delta.btc == Decimal('-0.1')
    assert delta.eth == Decimal('0')
    assert delta.usdt == Decimal('10000')


def test_btcusdt_aggressor_sell():
    event = make_event(
        event_index=1,
        symbol='BTCUSDT',
        side='sell_base',
        price='100000',
        quantity='0.1',
    )

    delta = calculate_passive_maker_delta(
        event
    )

    assert delta.btc == Decimal('0.1')
    assert delta.usdt == Decimal('-10000')


def test_ethbtc_aggressor_buy():
    event = make_event(
        event_index=1,
        symbol='ETHBTC',
        side='buy_base',
        price='0.035',
        quantity='10',
    )

    delta = calculate_passive_maker_delta(
        event
    )

    assert delta.eth == Decimal('-10')
    assert delta.btc == Decimal('0.35')
    assert delta.usdt == Decimal('0')


def test_replay_accumulates_inventory():
    events = [
        make_event(
            event_index=1,
            symbol='BTCUSDT',
            side='buy_base',
            price='100000',
            quantity='0.1',
        ),
        make_event(
            event_index=2,
            symbol='ETHBTC',
            side='buy_base',
            price='0.035',
            quantity='10',
        ),
    ]

    records = list(replay_passive_market_maker_inventory(events))

    final = records[-1]

    assert final.inventory_btc == Decimal('0.25')
    assert final.inventory_eth == Decimal('-10')
    assert final.inventory_usdt == Decimal('10000')


def test_rejects_non_contiguous_indices():
    events = [
        make_event(
            event_index=1,
            symbol='BTCUSDT',
            side='buy_base',
            price='100000',
            quantity='0.1',
        ),
        make_event(
            event_index=3,
            symbol='BTCUSDT',
            side='buy_base',
            price='100000',
            quantity='0.1',
        ),
    ]

    with pytest.raises(
        ValueError,
        match='contiguous',
    ):
        list(replay_passive_market_maker_inventory(events))
