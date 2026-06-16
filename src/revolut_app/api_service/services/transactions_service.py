from revolut_app.api_service.repositories.transaction_event_repository import (
    TransactionEventRepository
)
from revolut_app.api_service.schemas.transactions import (
    TransactionEventRequest,
    TransactionIngestionResponse
)
from .risk_service import (
    RiskService
)


class TransactionService:
    def __init__(
        self,
        repository: TransactionEventRepository | None = None,
        risk_service: RiskService | None = None,
    ):
        self.repository = repository or TransactionEventRepository()
        self.risk_service = risk_service or RiskService()

    def ingest(
            self,
            event: TransactionEventRequest
    ) -> TransactionIngestionResponse:
        existing_event = self.repository.find_by_idempotency_key(
            event.idempotency_key
        )

        if existing_event:
            return TransactionIngestionResponse(
                status='duplicate',
                transaction_id=existing_event['transaction_id'],
                risk_score=existing_event['risk_score'],
                risk_level=existing_event['risk_level'],
                is_duplicate=True
            )

        risk_score, risk_level = self.risk_service.score(event)

        payload = event.model_dump(mode='json')
        payload['risk'] = {
            'risk_score': risk_score,
            'risk_level': risk_level,
        }
        payload['source'] = 'api'

        self.repository.insert_event(
            event_id=event.event_id,
            idempotency_key=event.idempotency_key,
            transaction_id=event.transaction_id,
            account_id=event.account_id,
            payload=payload,
            risk_score=risk_score,
            risk_level=risk_level,
        )

        return TransactionIngestionResponse(
            status='accepted',
            transaction_id=event.transaction_id,
            risk_score=risk_score,
            risk_level=risk_level,
            is_duplicate=False
        )

    def get_by_transaction_id(self, transaction_id):
        return self.repository.find_by_transaction_id(transaction_id)
