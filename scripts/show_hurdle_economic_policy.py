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
    print(
        'Decision stride:',
        f'''{configuration['decision_stride_seconds']} seconds''',
    )

    for symbol, target in payload['targets'].items():
        print()
        print('=' * 110)
        print(symbol)
        print('status:', target['status'])

        selected = target.get('selected_final_candidate')
        if selected is None:
            print('selected final candidate: no_action')
            continue

        policy = selected['policy_spec']
        model = selected['model_spec']
        print(
            'selected:',
            f'''H={selected['horizon_seconds']}s,''',
            f'''model={model['preset']},''',
            f'''budget={policy['notional_budget_fraction']:.1%},''',
            f'''margin={policy['min_expected_net_margin_bps']:.2f} bps,''',
            f'''pBE={policy['min_break_even_probability']:.2f},''',
            f'''multiplier={policy['prediction_multiplier']:.2f}''',
        )

        final = target['final_test']
        aggregate = final['aggregate']
        for name in (
            'no_action',
            'probability_budget',
            'direct_economic',
            'hurdle_economic',
            'oracle_upper_bound',
        ):
            row = aggregate[name]
            print(
                f'''{name:22s} '''
                f'''net={row['net_value_per_million_usdt']:+.4f} '''
                f'''USDT/$1M, '''
                f'''notional={row['acted_notional_fraction']:.2%}, '''
                f'''capture={row['capture_rate']:.2%}, '''
                f'''B/C={row['benefit_cost_ratio']:.3f}'''
            )

        print(
            'oracle capture:',
            f'''{final['oracle_capture_fraction']:.2%}''',
        )
        for comparison, values in final['bootstrap'].items():
            print(
                f'''{comparison:28s} '''
                f'''mean={values['mean']:+.4f}, '''
                f'''CI=[{values['ci_025']:+.4f}, '''
                f'''{values['ci_975']:+.4f}], '''
                f'''positive_days='''
                f'''{values['positive_day_fraction']:.2%}'''
            )


if __name__ == '__main__':
    main()
