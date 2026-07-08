# Deployment

Deployment is development-oriented and containerized.

## Local Stack

The repository uses Docker Compose for services such as API, Airflow, PostgreSQL, ClickHouse, MinIO, and Metabase.

## Deployment Checklist

- configure environment variables;
- start dependent services;
- run migrations or bootstrap tasks;
- validate health endpoints;
- run a small ingestion smoke test;
- run a short experiment smoke test;
- verify analytics access.

## Production Note

This project is a research and educational platform. Treat production deployment as a separate hardening project.

