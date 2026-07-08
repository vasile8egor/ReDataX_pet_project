from __future__ import annotations

from typing import Iterable, Iterator

from revolut_app.real_market.inventory.models import (
    InventoryDelta,
    InventoryReplayRecord,
    InventoryState,
    UnifiedMarketEvent,
)


SUPPORTED_SYMBOLS = {
    'BTCUSDT',
    'ETHUSDT',
    'ETHBTC',
}


def calculate_passive_maker_delta(
    event: UnifiedMarketEvent,
):
    if event.symbol not in SUPPORTED_SYMBOLS:
        raise ValueError(
            f'Unsupported symbol: {event.symbol}'
        )

    if event.aggressor_side not in {'buy_base', 'sell_base'}:
        raise ValueError(
            'Unsupported aggressor side: '
            f'{event.aggressor_side}'
        )

    if event.price <= 0:
        raise ValueError(
            'price must be positive'
        )

    if event.base_quantity <= 0:
        raise ValueError(
            'base_quantity must be positive'
        )

    quote_quantity = (
        event.price * event.base_quantity
    )

    if event.aggressor_side == 'buy_base':
        base_delta = -event.base_quantity
        quote_delta = quote_quantity
    else:
        base_delta = event.base_quantity
        quote_delta = -quote_quantity

    if event.symbol == 'BTCUSDT':
        return InventoryDelta(
            btc=base_delta,
            usdt=quote_delta,
        )

    if event.symbol == 'ETHUSDT':
        return InventoryDelta(
            eth=base_delta,
            usdt=quote_delta,
        )

    if event.symbol == 'ETHBTC':
        return InventoryDelta(
            eth=base_delta,
            btc=quote_delta,
        )

    raise AssertionError(
        'Unreachable symbol branch'
    )


def replay_passive_market_maker_inventory(
    events: Iterable[UnifiedMarketEvent],
    initial_state: InventoryState | None = None,
):
    state = initial_state or InventoryState()

    previous_event_index: int | None = None
    previous_timestamp_us: int | None = None

    for event in events:
        if previous_event_index is not None:
            if event.event_index != previous_event_index + 1:
                raise ValueError(
                    'event_index must be contiguous: '
                    f'previous={previous_event_index}, '
                    f'current={event.event_index}'
                )

        if previous_timestamp_us is not None:
            if event.timestamp_us < previous_timestamp_us:
                raise ValueError(
                    'timestamps must be non-decreasing'
                )

        delta = calculate_passive_maker_delta(
            event
        )

        state = state.apply(delta)

        yield InventoryReplayRecord(
            trade_date=event.trade_date,
            event_index=event.event_index,
            symbol=event.symbol,
            aggregate_trade_id=event.aggregate_trade_id,
            event_timestamp=event.event_timestamp,
            timestamp_us=event.timestamp_us,
            price=event.price,
            base_quantity=event.base_quantity,
            quote_quantity=event.quote_quantity,
            aggressor_side=event.aggressor_side,
            delta_btc=delta.btc,
            delta_eth=delta.eth,
            delta_usdt=delta.usdt,
            inventory_btc=state.btc,
            inventory_eth=state.eth,
            inventory_usdt=state.usdt,
        )

        previous_event_index = event.event_index
        previous_timestamp_us = event.timestamp_us
