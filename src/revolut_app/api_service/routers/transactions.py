from fastapi import APIRouter, HTTPException, status

from revolut_app.api_service.services.transactions_service import (
    TransactionService
)
from revolut_app.api_service.schemas.transactions import (
    TransactionIngestionResponse,
    TransactionEventRequest
)

router = APIRouter(prefix='/events/transactions', tags=['transactions'])

transaction_service = TransactionService()


@router.post(
    '',
    response_model=TransactionIngestionResponse,
    status_code=status.HTTP_201_CREATED
)
def ingest_transaction(event: TransactionEventRequest):
    response = transaction_service.ingest(event)

    if response.is_duplicate:
        return response
    return response


@router.get('/{transaction_id}')
def get_transaction(transaction_id):
    event = transaction_service.get_by_transaction_id(transaction_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Transaction event not found'
        )
    return event
