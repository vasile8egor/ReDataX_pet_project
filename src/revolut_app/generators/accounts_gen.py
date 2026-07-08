import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from faker import Faker

from revolut_app.core.constants import (
    ACCOUNT_TYPES,
    CURRENCIES,
    CUSTOMER_CATEGORIES,
    DOMAINS,
    LOCATIONS,
    MAX_AGE_CLIENT,
    MIN_AGE_CLIENT,
    NUM_ACCOUNTS_STARTPACK,
    SCORING_CONFIG,
)


class AccountGenerator:
    def __init__(self):
        self.fake = Faker(random.choice(LOCATIONS))

    def get_daily_count(self, target_date):
        is_weekend = target_date.weekday() >= 5
        return np.random.poisson(5 if is_weekend else 10)

    def _weighted_choice(self, choices: Dict[str, float]):
        return random.choices(
            list(choices.keys()),
            weights=list(choices.values()),
            k=1
        )[0]

    def _registration_timestamp(self, target_date):
        return datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            random.randint(0, 23),
            random.randint(0, 59),
            random.randint(0, 59)
        )

    def generate_account(
        self,
        target_date: Optional[Any] = None
    ):
        target_date = target_date or datetime.utcnow().date()
        registration_time = self._registration_timestamp(target_date)

        channel = random.choices(
            list(CUSTOMER_CATEGORIES.keys()),
            weights=[cfg['prob'] for cfg in CUSTOMER_CATEGORIES.values()],
            k=1
        )[0]
        category = CUSTOMER_CATEGORIES[channel]

        first_name = self.fake.first_name()
        last_name = self.fake.last_name()
        full_name = f'{first_name} {last_name}'
        account_id = uuid.uuid4().hex
        account_type = self._weighted_choice(ACCOUNT_TYPES)
        currency = self._weighted_choice(CURRENCIES)
        churn_risk = category['churn_risk']
        lifetime_value = category['lifetime_value']
        initial_deposit = round(
            np.random.lognormal(
                mean=np.log(category['avg_initial_deposit']),
                sigma=0.5
            ),
            2
        )

        return {
            'AccountId': account_id,
            'Currency': currency,
            'AccountType': account_type,
            'AccountSubType': (
                'CurrentAccount'
                if account_type == 'Personal'
                else account_type
            ),
            'Account': [
                {
                    'SchemeName': 'UK.OBIE.IBAN',
                    'Identification': (
                        f'GB{random.randint(10, 99)}'
                        f'{account_id[:18].upper()}'
                    ),
                    'Name': full_name,
                },
                {
                    'SchemeName': 'UK.OBIE.SortCodeAccountNumber',
                    'Identification': (
                        f'{random.randint(10, 99)}-'
                        f'{random.randint(10, 99)}-'
                        f'{random.randint(10, 99)}/'
                        f'{random.randint(10000000, 99999999)}'
                    ),
                    'Name': full_name,
                },
            ],
            'Customer': {
                'FirstName': first_name,
                'LastName': last_name,
                'Email': (
                    f'{first_name.lower()}.'
                    f'{last_name.lower()}@{random.choice(DOMAINS)}'
                ),
                'Phone': f'44{random.randint(100000000, 999999999)}',
                'DateOfBirth': self.fake.date_of_birth(
                    minimum_age=MIN_AGE_CLIENT,
                    maximum_age=MAX_AGE_CLIENT
                ).isoformat(),
            },
            'Acquisition': {
                'Channel': channel,
                'ChannelName': category['name'],
                'RegistrationDatetime': registration_time.isoformat(),
                'InitialDeposit': initial_deposit,
            },
            'Scoring': {
                'ChurnRisk': churn_risk,
                'ChurnRiskScore': SCORING_CONFIG['churn_risk'][churn_risk],
                'LifetimeValue': lifetime_value,
                'LifetimeValueAmount': (
                    SCORING_CONFIG['lifetime_value'][lifetime_value]
                ),
            },
            'UpdatedAt': datetime.utcnow().isoformat(),
        }

    def generate_batch(
        self,
        num_accounts: int = NUM_ACCOUNTS_STARTPACK,
        target_date: Optional[Any] = None
    ):
        return [
            self.generate_account(target_date)
            for _ in range(num_accounts)
        ]

    def generate_daily_batch(self, target_date):
        return self.generate_batch(
            num_accounts=self.get_daily_count(target_date),
            target_date=target_date
        )
