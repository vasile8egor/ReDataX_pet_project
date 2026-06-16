from fastapi import FastAPI

from revolut_app.api_service.routers import health, transactions

app = FastAPI(
    title='ReDataX Transaction Ingestion API',
    description=(
        'FastAPI service for transaction ingestion, idempotency, risk scoring.'
    ),
    version='0.1.0',
)

app.include_router(health.router)
app.include_router(transactions.router)
