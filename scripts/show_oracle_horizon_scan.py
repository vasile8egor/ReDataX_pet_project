#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('result')
    arguments = parser.parse_args()

    payload = json.loads(
        Path(arguments.result).read_text(encoding='utf-8')
    )
    configuration = payload['configuration']

    print(
        'Break-even markout:',
        f'''{configuration['break_even_markout_bps']:.4f} bps''',
    )
    print()

    for symbol, target in payload['targets'].items():
        print('=' * 100)
        print(symbol)
        recommendation = target['recommendations']
        print('status:', recommendation['status'])

        rows = target['candidate_ranking'][:15]
        for index, row in enumerate(rows, start=1):
            print(
                f'''{index:2d}. '''
                f'''H={row['horizon_seconds']:4d}s '''
                f'''budget={row['notional_budget_fraction']:.1%} | '''
                f'''mean={row['mean_daily_net_value_per_million_usdt']:+.4f} '''
                f'''robust={row['robust_score']:+.4f} '''
                f'''CI=[{row['bootstrap_ci_lower']:+.4f}, '''
                f'''{row['bootstrap_ci_upper']:+.4f}] '''
                f'''positive_days={row['positive_day_fraction']:.2%} '''
                f'''P(BE)={row['above_break_even_event_fraction']:.4%} '''
                f'''strict={row['strictly_feasible']}'''
            )


if __name__ == '__main__':
    main()
