import numpy as np
import random
from datetime import date, datetime
from faker import Faker
from revolut_app.core.constants import (
    ACTIVITY_DISTRIBUTION,
    LOCATIONS,
    ITERATIONS_QUANTITY
)


TRANSACTION_TYPES = {
    "card_payment": 0.45,
    "internal_transfer": 0.20,
    "bank_transfer_out": 0.12,
    "bank_transfer_in": 0.10,
    "salary": 0.05,
    "cash_withdrawal": 0.04,
    "fee": 0.02,
    "refund": 0.02,
}

CARD_CATEGORIES = [
    "groceries",
    "transport",
    "restaurants",
    "online",
    "subscriptions",
    "entertainment",
    "health",
]


class MetropolisTransactionGenerator:
    def __init__(self, temperature=0.35, base_lambda=65):
        self.temperature = temperature
        self.base_lambda = base_lambda
        self.fake = Faker(random.choice(LOCATIONS))
        self.contact_book: dict[str, list[str]] = {}

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

    def build_contact_book(
        self,
        account_ids: list[str],
        contacts_per_account: int = 5
    ) -> None:
        account_ids = [str(account_id) for account_id in account_ids]

        for account_id in account_ids:
            candidates = [
                candidate
                for candidate in account_ids
                if candidate != account_id
            ]
            if not candidates:
                self.contact_book[account_id] = []
                continue

            sample_size = min(contacts_per_account, len(candidates))
            self.contact_book[account_id] = random.sample(
                candidates,
                sample_size
            )

    def choose_internal_target(
        self,
        source_account_id: str,
        account_ids: list[str]
    ) -> str | None:
        source_account_id = str(source_account_id)
        candidates = [
            str(candidate)
            for candidate in account_ids
            if str(candidate) != source_account_id
        ]
        if not candidates:
            return None

        contacts = [
            contact
            for contact in self.contact_book.get(source_account_id, [])
            if contact in candidates
        ]

        if contacts and random.random() < 0.8:
            return random.choice(contacts)

        return random.choice(candidates)

    def generate_amount(self, transaction_type: str) -> float:
        params = {
            "card_payment": {"mean": 35, "sigma": 0.75},
            "internal_transfer": {"mean": 120, "sigma": 0.90},
            "bank_transfer_out": {"mean": 250, "sigma": 1.10},
            "bank_transfer_in": {"mean": 300, "sigma": 1.00},
            "salary": {"mean": 2500, "sigma": 0.25},
            "cash_withdrawal": {"mean": 80, "sigma": 0.45},
            "fee": {"mean": 7, "sigma": 0.20},
            "refund": {"mean": 25, "sigma": 0.70},
        }

        cfg = params[transaction_type]
        return float(
            round(
                np.random.lognormal(
                    mean=np.log(cfg["mean"]),
                    sigma=cfg["sigma"],
                ),
                2,
            )
        )

    def generate_for_account(
        self,
        account_id: str,
        all_account_ids: list[str] | date,
        target_date: date | None = None,
    ):
        if target_date is None:
            target_date = all_account_ids
            all_account_ids = [str(account_id)]

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
            transaction_type = random.choices(
                list(TRANSACTION_TYPES.keys()),
                weights=list(TRANSACTION_TYPES.values())
            )[0]

            yield self.generate_transaction_by_type(
                transaction_type=transaction_type,
                account_id=str(account_id),
                all_account_ids=list(all_account_ids),
                target_date=target_date,
                tx_time=tx_time,
                index=i,
            )

    def generate_transaction_by_type(
        self,
        transaction_type: str,
        account_id: str,
        all_account_ids: list[str],
        target_date,
        tx_time: datetime,
        index: int,
    ) -> dict:
        source_account_id = account_id
        target_account_id = None
        external_counterparty_id = None
        counterparty_type = None
        direction = "outgoing"
        merchant_name = None
        category = None

        if transaction_type == "internal_transfer":
            target_account_id = self.choose_internal_target(
                account_id,
                all_account_ids
            )
            counterparty_type = "internal_account"
        elif transaction_type == "card_payment":
            external_counterparty_id = f"merchant_{self.fake.uuid4()}"
            counterparty_type = "merchant"
            merchant_name = self.fake.company()
            category = random.choice(CARD_CATEGORIES)
        elif transaction_type == "bank_transfer_out":
            external_counterparty_id = f"external_bank_{self.fake.uuid4()}"
            counterparty_type = "external_bank_account"
        elif transaction_type == "bank_transfer_in":
            source_account_id = None
            target_account_id = account_id
            external_counterparty_id = f"external_bank_{self.fake.uuid4()}"
            counterparty_type = "external_bank_account"
            direction = "incoming"
        elif transaction_type == "salary":
            source_account_id = None
            target_account_id = account_id
            external_counterparty_id = f"employer_{self.fake.uuid4()}"
            counterparty_type = "employer"
            direction = "incoming"
            category = "salary"
            merchant_name = self.fake.company()
        elif transaction_type == "cash_withdrawal":
            external_counterparty_id = f"atm_{self.fake.uuid4()}"
            counterparty_type = "atm"
            category = "cash"
        elif transaction_type == "fee":
            external_counterparty_id = "bank_fee_account"
            counterparty_type = "bank"
            category = "fee"
        elif transaction_type == "refund":
            source_account_id = None
            target_account_id = account_id
            external_counterparty_id = f"merchant_{self.fake.uuid4()}"
            counterparty_type = "merchant"
            direction = "incoming"
            category = "refund"
        else:
            raise ValueError(f"Unsupported transaction type: {transaction_type}")

        return {
            "transaction_id": (
                f"{account_id}_{target_date.strftime('%Y%m%d')}_"
                f"{index + 1:06d}"
            ),
            "account_id": str(account_id),
            "source_account_id": source_account_id,
            "target_account_id": target_account_id,
            "external_counterparty_id": external_counterparty_id,
            "counterparty_type": counterparty_type,
            "amount": self.generate_amount(transaction_type),
            "currency": "GBP",
            "direction": direction,
            "transaction_type": transaction_type,
            "status": "completed",
            "created_at": tx_time.isoformat(),
            "merchant_name": merchant_name,
            "category": category,
        }

    def generate_all(self, account_ids: list[str], target_date):
        account_ids = [str(account_id) for account_id in account_ids]
        if not self.contact_book:
            self.build_contact_book(account_ids)

        all_transactions = []
        for acc_id in account_ids:
            all_transactions.extend(
                list(
                    self.generate_for_account(
                        account_id=acc_id,
                        all_account_ids=account_ids,
                        target_date=target_date,
                    )
                )
            )
        return all_transactions
