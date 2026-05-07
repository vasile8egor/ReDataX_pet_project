import random
import uuid
import numpy as np
from datetime import datetime, timedelta
from faker import Faker
from revolut_app.core.constants import (
    LOCATIONS,
    CUSTOMER_CATEGORIES,
    CURRENCIES,
    ACCOUNT_TYPES,
    DOMAINS,
    MIN_AGE_CLIENT,
    MAX_AGE_CLIENT,
    INITIAL_MERCHANTS,
    SCORING_CONFIG
)


class NewAccountGenerator:
    def __init__(self):
        self.fake = Faker(random.choice(LOCATIONS))

    def get_daily_count(self, target_date):
        is_weekend = target_date.weekday() >= 5
        return np.random.poisson(5 if is_weekend else 10)

    def generate_new_client(self, target_date):
        channel = random.choices(
            list(CUSTOMER_CATEGORIES.keys()),
            weights=[v['prob'] for v in CUSTOMER_CATEGORIES.values()]
        )[0]

        category = CUSTOMER_CATEGORIES[channel]
        reg_time = datetime(
            target_date.year, target_date.month, target_date.day,
            random.randint(0, 23), random.randint(0, 59), random.randint(0, 59)
        )

        first_name = self.fake.first_name()
        last_name = self.fake.last_name()

        acc_type = random.choices(
            list(ACCOUNT_TYPES.keys()),
            weights=list(ACCOUNT_TYPES.values())
        )[0]

        account_id = uuid.uuid4().hex
        initial_deposit = round(np.random.lognormal(
            mean=np.log(category['avg_initial_deposit']), sigma=0.5), 2)

        risk_cat = category['churn_risk']
        ltv_cat = category['lifetime_value']

        account_data = {
            'account_id': account_id,
            'first_name': first_name,
            'last_name': last_name,
            'email': f"{first_name.lower()}.{last_name.lower()}@{random.choice(DOMAINS)}",
            'phone': f"44{random.randint(100000000, 999999999)}",
            'date_of_birth': self.fake.date_of_birth(minimum_age=MIN_AGE_CLIENT, maximum_age=MAX_AGE_CLIENT),
            'currency': random.choices(list(CURRENCIES.keys()), weights=list(CURRENCIES.values()))[0],
            'account_type': acc_type,
            'account_sub_type': 'CurrentAccount' if acc_type == 'Personal' else acc_type,
            'acquisition_channel': channel,
            'acquisition_channel_name': category['name'],
            'initial_deposit': initial_deposit,
            'registration_datetime': reg_time,
            'updated_at': datetime.now(),
            'churn_risk': risk_cat,
            'churn_risk_score': SCORING_CONFIG['churn_risk'][risk_cat],
            'lifetime_value': ltv_cat,
            'ltv_amount': SCORING_CONFIG['lifetime_value'][ltv_cat],
        }

        merchant = random.choice(INITIAL_MERCHANTS)
        tx_time = reg_time + timedelta(minutes=random.randint(1, 60))

        transaction_data = {
            'transaction_id': f"{account_id}_{reg_time.strftime('%Y%m%d')}_INIT",
            'account_id': account_id,
            'booking_datetime': tx_time,
            'value_datetime': tx_time,
            'amount': float(initial_deposit),
            'currency': 'GBP',
            'credit_debit_indicator': 'Credit',
            'status': 'Completed',
            'transaction_information': f"{merchant} - New registration via {category['name']}",
            'merchant_name': merchant,
            'load_ts': datetime.now()
        }

        return account_data, transaction_data
