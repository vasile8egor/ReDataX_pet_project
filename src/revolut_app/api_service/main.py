from fastapi import FastAPI

from revolut_app.api_service.routers import fx, health, transactions

app = FastAPI(
    title='ReDataX Transaction Ingestion API',
    description=(
        'FastAPI service for transaction ingestion, idempotency, risk scoring.'
    ),
    version='0.2.0',
)

app.include_router(health.router)
app.include_router(transactions.router)
app.include_router(fx.router)
