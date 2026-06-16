from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Currency(str, Enum):
    GBP = 'GBP'
    EUR = 'EUR'
    USD = 'USD'


class TransactionType(str, Enum):
    card_payment = 'card_payment'
    internal_transfer = 'internal_transfer'
    bank_transfer_out = 'bank_transfer_out'
    bank_transfer_in = 'bank_transfer_in'
    salary = 'salary'
    cash_withdrawal = 'cash_withdrawal'
    fee = 'fee'
    refund = 'refund'


class TransactionEventRequest(BaseModel):
    event_id: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)
    transaction_id: str = Field(..., min_length=1)
    account_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: Currency
    transaction_type: TransactionType
    category: str | None = None
    merchant_name: str | None = None
    created_at: datetime


class TransactionIngestionResponse(BaseModel):
    status: Literal['accepted', 'duplicate']
    transaction_id: str
    risk_score: float
    risk_level: Literal['low', 'medium', 'high']
    is_duplicate: bool
