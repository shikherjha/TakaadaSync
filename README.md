# Takaada Integration Service

A backend service that integrates with an external accounting system, syncs financial data locally, and exposes API endpoints for receivables insights.

## Architecture Diagrams

### 1. High-Level Architecture
```mermaid
graph LR
    A[External Accounting API] -->|Polling every 5 min| B[Celery Worker]
    C[Celery Beat] -->|Schedules task| B
    D[Redis] --- B
    D --- C
    B -->|Upserts| E[(PostgreSQL)]
    F[FastAPI] -->|Reads| E
    G[Client] -->|HTTP| F
```

### 2. Data Synchronization Flow
```mermaid
sequenceDiagram
    participant Beat
    participant Worker
    participant ExternalAPI
    participant DB

    Beat->>Worker: Trigger sync job
    Worker->>ExternalAPI: GET /customers
    ExternalAPI-->>Worker: customer data
    Worker->>DB: Upsert customers

    Worker->>ExternalAPI: GET /invoices
    ExternalAPI-->>Worker: invoice data
    Worker->>DB: Upsert invoices

    Worker->>ExternalAPI: GET /payments
    ExternalAPI-->>Worker: payment data
    Worker->>DB: Upsert payments
```

### 3. Insight Request Flow
```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB

    Client->>API: GET /customers/{id}/outstanding
    API->>DB: Query invoices + payments
    DB-->>API: data
    API->>API: Calculate outstanding
    API-->>Client: JSON response
```

The system follows an **eventual consistency** model — there's a window of up to 5 minutes where the local DB may lag behind the external system. This was a deliberate trade-off for simplicity, since we can't assume the external API supports webhooks.

## Database Schema

```mermaid
erDiagram
    CUSTOMERS ||--o{ INVOICES : has
    INVOICES ||--o{ PAYMENTS : receives

    CUSTOMERS {
        int id
        string external_id
        string name
        string email
    }

    INVOICES {
        int id
        string external_id
        int customer_id
        decimal amount
        date due_date
    }

    PAYMENTS {
        int id
        string external_id
        int invoice_id
        decimal amount
        date payment_date
    }
```

**Relationships:** Customer → many Invoices → many Payments

## API Endpoints

| Endpoint | Description |
|--------|-------------|
| `GET /health` | Health check |
| `GET /customers` | List all synced customers |
| `GET /customers/{id}/outstanding` | Outstanding balance for a specific customer |
| `GET /invoices/overdue` | All overdue invoices with days overdue |
| `GET /insights/receivables-summary` | High-level receivables overview |

### Insight Calculations

- **Outstanding balance** = `sum(invoice.amount) - sum(payments.amount)` for a customer
- **Overdue invoice** = `due_date < now AND outstanding > 0 AND status != 'paid'`
- **Receivables summary** = aggregated totals across all customers

## Setup & Running

### Prerequisites
- Docker & Docker Compose

### Quick Start

```bash
# Clone and run
git clone <repo-url>
cd takaada-integration

# Start everything
docker-compose up --build
```

This spins up:
- PostgreSQL on `:5432`
- Redis on `:6379`
- Mock Accounting API on `:8001`
- FastAPI service on `:8000`
- Celery Worker + Beat (background)

The API auto-runs Alembic migrations on startup, so tables are created automatically.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/takaada` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for Celery broker + rate limiting |
| `EXTERNAL_API_URL` | `http://localhost:8001` | Mock accounting API URL |
| `SYNC_INTERVAL_SECONDS` | `300` | How often to poll (seconds) |

### Running Tests

```bash
# Install deps
pip install -r requirements.txt

# Run tests (uses SQLite, no Docker needed)
PYTHONPATH=. pytest tests/ -v
```

## Design Decisions

### Why polling instead of webhooks?
The external API doesn't expose webhook endpoints, so polling is the pragmatic choice. 5-minute intervals keep things fresh without hammering the API. If webhooks become available, swapping out Celery Beat for a webhook receiver would be straightforward.

### Why idempotent upserts?
Using PostgreSQL's `ON CONFLICT DO UPDATE` on `external_id` means we can safely re-run syncs without worrying about duplicates. If a sync fails halfway through, the next run picks up where things left off.

### Why separate internal IDs?
External IDs (like `CUST-001`) are kept as-is but we use auto-incrementing internal IDs for foreign keys. This decouples our schema from the external system's ID format.

### Why Redis for rate limiting?
Redis is already in the stack for Celery, so using it for a sliding window rate limiter avoids adding another dependency. Simple and works well enough for this scale.

## Project Structure

```
├── src/
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Environment config
│   ├── api/
│   │   └── routes.py           # API endpoint handlers
│   ├── services/
│   │   ├── insight_service.py  # Financial calculations
│   │   └── sync_service.py     # Upsert logic
│   ├── models/
│   │   ├── customer.py
│   │   ├── invoice.py
│   │   └── payment.py
│   ├── integrations/
│   │   └── accounting_client.py # External API client
│   ├── tasks/
│   │   ├── celery_app.py       # Celery configuration
│   │   └── sync_tasks.py       # Scheduled sync task
│   ├── db/
│   │   └── session.py          # DB engine & session
│   └── utils/
│       └── rate_limiter.py     # Redis rate limiter
├── mock_accounting_api/
│   └── main.py                 # Fake external API
├── alembic/                    # Database migrations
├── tests/
│   └── test_core.py
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Future Improvements

- **Webhooks**: Replace polling with event-driven sync if the external system supports it — massively reduces latency and unnecessary API calls
- **Caching**: Add Redis TTL caching (1-2 min) on insight endpoints to avoid recomputing on every request
- **Monitoring**: Integrate Flower for Celery dashboard, Prometheus for sync success/failure metrics, Sentry for error tracking
- **Auth**: Add JWT authentication on insight endpoints, API key rotation for external API access
- **Scalability**: Horizontal Celery workers for parallel syncing, PostgreSQL read replicas for heavy read loads
- **Input validation**: More thorough Pydantic schemas for API responses
- **Incremental sync**: Track `last_synced_at` and only fetch records modified since — reduces payload and DB writes
