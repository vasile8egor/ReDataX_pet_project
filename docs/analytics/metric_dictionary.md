# Research metric dictionary

## Economic value

### `net_value_per_million_usdt`

Scenario-adjusted protected value after action cost, normalized by total
notional:

```text
net protected value / total notional × 1,000,000
```

It is not realized bank PnL.

### `gross_value_per_million_usdt`

Potential protected adverse-selection exposure before action cost.

### `benefit_cost_ratio`

```text
gross protected value / action cost
```

Values above 1 indicate positive economics under the selected scenario.

### `break_even_action_cost_bps`

Maximum action cost at which the selected intervention set remains
break-even.

### `oracle_capture_fraction`

```text
model net value / oracle net value
```

The oracle uses realized future markout and is not deployable.

## Capital usage

### `acted_notional_fraction`

Share of total notional affected by the policy.

### `acted_event_fraction`

Share of decision observations receiving a full or partial action.

### `mean_action_fraction_on_acted_events`

Average fractional hedge or proportional action among affected events.

## Risk capture

### `capture_rate`

Share of observed positive markout exposure captured by selected actions.

### `risk_concentration`

```text
capture rate / acted notional fraction
```

Values above 1 indicate concentration of observed exposure in the affected
notional.

## Statistical reporting

### `mean_delta`

Equal-weighted mean of daily policy differences.

### `ci_lower`, `ci_upper`

Day-cluster bootstrap confidence interval for `mean_delta`.

### `positive_day_fraction`

Fraction of test days on which the candidate exceeded the baseline.

## Important estimand distinction

`aggregate_net_value_per_million_usdt` is calculated from pooled sums and
therefore notional-weights the days.

`mean_daily_uplift_per_million_usdt` gives each day equal weight. Its
bootstrap confidence interval must not be attached to the aggregate metric.
