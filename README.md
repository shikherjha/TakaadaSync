# Takaada Integration Service

A backend service that integrates with an external accounting system, syncs financial data locally, and exposes API endpoints for receivables insights.

## Key Engineering Highlights

- **Robust Background Processing**: Uses **Celery + Redis** instead of basic cron jobs, providing proper task queueing, automatic retries with exponential backoff on API failures, and concurrency control.
- **API Rate Limiting**: A custom **Redis-based sliding window** rate limiter protects the externally facing insight endpoints from abuse.
- **Complete Containerization**: The entire ecosystem (Postgres, Redis, API, Celery Worker, Celery Beat scheduler, and Mock API) is fully containerized and orchestrated via **Docker Compose** for true one-click local deployment.
- **N+1 Query Prevention**: All ORM queries use `joinedload` to eager-load relationships in a single SQL hit instead of lazy-loading per row.
- **Denormalized Balances (Zero Read Latency)**: Customer outstanding and credit amounts are pre-calculated during the background sync and stored directly on the customer row, making API reads essentially O(1).
- **FinTech Business Logic**: 
  - **Aging Report**: Standard accounting aging buckets (Current, 1-30, 31-60, 61-90, 90+ days) are computed accurately.
  - **Credit/Overpayment Handling**: If a customer overpays, outstanding floors to $0 and the excess is explicitly exposed as `available_credit`.
  - **Risk Classification**: Simple heuristic risk levels (low/medium/high) automatically assign based on overdue count and days past due.
- **Idempotent Synchronization**: PostgreSQL `ON CONFLICT DO UPDATE` ensures that re-running or retrying failed syncs never creates duplicate records.
- **True Network Integration**: The mock external API runs in a completely isolated container with its own memory space. The worker makes actual HTTP requests over the Docker network, accurately simulating a real third-party integration.

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
    Worker->>DB: Recalculate customer balances
```

### 3. Insight Request Flow
```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB

    Client->>API: GET /customers/{id}/outstanding
    API->>DB: Read denormalized balance + overdue invoices
    DB-->>API: data
    API->>API: Calculate risk level
    API-->>Client: JSON response
```

The system follows an **eventual consistency** model, there's a window of up to 5 minutes where the local DB may lag behind the external system. This was a deliberate trade-off for simplicity, since we can't assume the external API supports webhooks.

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
        decimal total_outstanding
        decimal available_credit
    }

    INVOICES {
        int id
        string external_id
        int customer_id
        decimal amount
        date due_date
        string status
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
| `GET /customers` | List all customers with outstanding balance and credit |
| `GET /customers/{id}/outstanding` | Detailed balance, risk level, overdue count |
| `GET /invoices/overdue` | All overdue invoices with days overdue |
| `GET /insights/receivables-summary` | Receivables overview with aging buckets |

### Insight Calculations

- **Outstanding balance** = `sum(invoice.amount) - sum(payments.amount)` per customer, pre-calculated during sync
- **Available credit** = if customer overpaid, the excess stored as credit (outstanding floors to 0)
- **Risk level**: `low` (0 overdue), `medium` (1-2 overdue, <30 days), `high` (3+ overdue or >30 days past due)
- **Aging buckets**: `current`, `1_to_30_days`, `31_to_60_days`, `61_to_90_days`, `90_plus_days`
- **Overdue invoice** = `due_date < now AND outstanding > 0 AND status != 'paid'`

## Setup & Running

### Prerequisites
- Docker & Docker Compose

### Quick Start

```bash
# Clone and run
git clone https://github.com/shikherjha/TakaadaSync
cd TakaadaSync

# Start everything
docker-compose up --build
```

This spins up:
- PostgreSQL on `:5432`
- Redis on `:6379`
- Mock Accounting API on `:8001`
- FastAPI service on `:8080`
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

### Why denormalize customer balances?
Since we only write during sync (every 5 minutes) but read on every API request, pre-computing `total_outstanding` and `available_credit` during sync and storing them on the customer row avoids expensive `SUM()` aggregations on the read path. This is a standard read-heavy optimization.

### Why idempotent upserts?
Using PostgreSQL's `ON CONFLICT DO UPDATE` on `external_id` means we can safely re-run syncs without worrying about duplicates. If a sync fails halfway through, the next run picks up where things left off.

### Why separate internal IDs?
External IDs (like `CUST-001`) are kept as-is but we use auto-incrementing internal IDs for foreign keys. This decouples our schema from the external system's ID format.

### Why Redis for rate limiting?
Redis is already in the stack for Celery, so using it for a sliding window rate limiter avoids adding another dependency. Simple and works well enough for this scale.

### N+1 query problem
SQLAlchemy's lazy-loading would fire a separate query for every invoice's payments when iterating. Using `joinedload` on the overdue and summary queries fetches invoices and payments in a single SQL join, reducing database round-trips from O(N) to O(1).

## Project Structure

```
├── src/
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Environment config
│   ├── api/
│   │   └── routes.py           # API endpoint handlers
│   ├── services/
│   │   ├── insight_service.py  # Financial calculations, risk, aging
│   │   └── sync_service.py     # Upsert logic + balance recalculation
│   ├── models/
│   │   ├── customer.py         # Includes denormalized balance columns
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

- **Webhooks**: Replace polling with event-driven sync if the external system supports it, massively reduces latency and unnecessary API calls
- **Caching**: Add Redis TTL caching (1-2 min) on insight endpoints to avoid recomputing on every request
- **Monitoring**: Integrate Flower for Celery dashboard, Prometheus for sync success/failure metrics, Sentry for error tracking
- **Auth**: Add JWT authentication on insight endpoints, API key rotation for external API access
- **Scalability**: Horizontal Celery workers for parallel syncing, PostgreSQL read replicas for heavy read loads
- **Input validation**: More thorough Pydantic schemas for API responses
- **Incremental sync**: Track `last_synced_at` and only fetch records modified since, reduces payload and DB writes
