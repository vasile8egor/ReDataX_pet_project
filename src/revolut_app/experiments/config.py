from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExperimentConfig():
    experiment_id = 'cashback_card_payments_v1',
    start_date = datetime.now(),
    treatment_share = 0.5,
    target_segment = 'low_active',
    affected_tx_type = 'card_payment',
    card_payment_uplift = 0.1,
    cashback_rate = 0.02,
    randomization = ''
