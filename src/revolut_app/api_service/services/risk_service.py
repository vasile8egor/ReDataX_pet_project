from datetime import datetime
from revolut_app.api_service.schemas.transactions import (
    TransactionEventRequest
)


class RiskService:

    def score(self, event: TransactionEventRequest):

        score = 0.05

        if event.amount >= 1000:
            score += 0.3

        if event.transaction_type == 'cash_withdrawal':
            score += 0.2

        if event.category in {'electronics', 'crypto', 'gambling'}:
            score += 0.1

        if self._is_night_transaction(event.created_at):
            score += 0.1

        score = min(score, 1.0)
        risk_level = self._risk_level(score)

        return round(score, 4), risk_level

    @staticmethod
    def _is_night_transaction(created_at: datetime):
        return True if created_at.hour < 5 else False

    @staticmethod
    def _risk_level(score: float):
        if score < 0.3:
            return 'low'
        elif score < 0.7:
            return 'medium'
        else:
            return 'high'
