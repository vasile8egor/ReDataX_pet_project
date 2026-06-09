import numpy as np
import random
from datetime import datetime
from faker import Faker
from revolut_app.core.constants import (
    ACTIVITY_DISTRIBUTION,
    LOCATIONS,
    ITERATIONS_QUANTITY
)


class MetropolisTransactionGenerator:
    def __init__(self, temperature=0.35, base_lambda=65):
        self.temperature = temperature
        self.base_lambda = base_lambda
        self.fake = Faker(random.choice(LOCATIONS))

        target = np.array(ACTIVITY_DISTRIBUTION)
        self.target_intensity = target / target.sum()
        self.current_intensity = self.target_intensity.copy()

    def run_mcmc(self, iterations=ITERATIONS_QUANTITY):
        for _ in range(iterations):
            proposed = self.current_intensity + np.random.normal(0, 0.04, 24)
            proposed = np.clip(proposed, 0.01, 1.0)
            proposed /= proposed.sum()

            current_energy = np.sum(
                (self.current_intensity - self.target_intensity) ** 2)
            proposed_energy = np.sum((proposed - self.target_intensity) ** 2)

            if proposed_energy < current_energy or \
               random.random() < np.exp(-(proposed_energy - current_energy) / self.temperature):
                self.current_intensity = proposed
        return self.current_intensity

    def generate_for_account(self, account_id, target_date):
        daily_n = max(10, int(np.random.poisson(self.base_lambda)))
        hours = np.random.choice(24, size=daily_n, p=self.current_intensity)

        for i, hour in enumerate(hours):
            tx_time = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                random.randint(0, 59),
                random.randint(0, 59)
            )
            tx_type = random.choices(
                ['Debit', 'Credit'],
                weights=[0.73, 0.27]
            )[0]

            yield {
                'transaction_id': f"{account_id}_{target_date.strftime('%Y%m%d')}_{i+1:06d}",
                'account_id': str(account_id),
                'amount': float(round(np.random.lognormal(mean=np.log(55), sigma=0.85), 2)),
                'currency': 'GBP',
                'created_at': tx_time.isoformat()
            }

            # yield {
            #     'transaction_id': f"{account_id}_{target_date.strftime('%Y%m%d')}_{i+1:06d}",
            #     'account_id': account_id,
            #     'booking_datetime': tx_time,
            #     'value_datetime': tx_time,
            #     'amount': round(np.random.lognormal(mean=np.log(55), sigma=0.85), 2),
            #     'currency': 'GBP',
            #     'credit_debit_indicator': tx_type,
            #     'status': 'Completed',
            #     'transaction_information': f"Synthetic {tx_type} transaction",
            #     'merchant_name': self.fake.company() if tx_type == 'Debit' else None,
            #     'load_ts': datetime.now()
            # }
    def generate_all(self, account_ids: list, target_date):
        all_transactions = []
        for acc_id in account_ids:
            all_transactions.extend(list(self.generate_for_account(acc_id, target_date)))
        return all_transactions
