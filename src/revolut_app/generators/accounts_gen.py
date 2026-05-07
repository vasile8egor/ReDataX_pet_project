import random
import uuid
from datetime import datetime
from faker import Faker

from revolut_app.core.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD
)
from revolut_app.core.constants import (
    LOCATIONS,
    NUM_ACCOUNTS_STARTPACK,
    CURRENCIES,
    ACCOUNT_TYPES
)


class AccountGenerator:
    def __init__(self):
        self.fake = Faker(random.choice(LOCATIONS))

    def get_weighted_choice(self, choices_dict):
        items = list(choices_dict.keys())
        weights = list(choices_dict.values())
        return random.choices(items, weights=weights, k=1)[0]

    def generate_account_id(self):
        return uuid.uuid4().hex[:32]

    def generate_account_data(self):
        account_id = self.generate_account_id()
        currency = self.get_weighted_choice(CURRENCIES)
        acc_type = self.get_weighted_choice(ACCOUNT_TYPES)

        name = f"{self.fake.first_name()} {self.fake.last_name()}"

        return {
            "AccountId": account_id,
            "Currency": currency,
            "AccountType": acc_type,
            "AccountSubType": 'CurrentAccount' if acc_type == 'Personal' else acc_type,
            "Account": [
                {
                    "SchemeName": "UK.OBIE.IBAN",
                    "Identification": f"GB{random.randint(10, 99)}{account_id[:18].upper()}",
                    "Name": name
                },
                {
                    "SchemeName": "UK.OBIE.SortCodeAccountNumber",
                    "Identification": f"{random.randint(10, 99)}-{random.randint(10, 99)}-{random.randint(10, 99)}/{random.randint(10000000, 99999999)}",
                    "Name": name
                }
            ]
        }

    def generate_batch(self, num_accounts=NUM_ACCOUNTS_STARTPACK):
        """Генерирует финальный JSON в формате Revolut"""
        accounts = [self.generate_account_data() for _ in range(num_accounts)]

        return {
            "Data": {"Account": accounts},
            "Links": {"Self": "https://sandbox-oba-auth.revolut.com/accounts"},
            "Meta": {"TotalPages": 1}
        }


def save_to_json(accounts_data, filename="generated_accounts.json"):
    import json
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(accounts_data, f, indent=2, ensure_ascii=False)
    print(f"JSON saved in {filename}")


def main():
    accounts_data = generate_accounts_json_format(NUM_ACCOUNTS)

    save_to_json(
        accounts_data,
        f"accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )


if __name__ == "__main__":
    main()
