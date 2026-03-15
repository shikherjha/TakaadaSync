from fastapi import FastAPI, Query
from datetime import datetime, timedelta
import random

app = FastAPI(title="Mock Accounting API")

# some hardcoded data that feels like a real small business
CUSTOMERS = [
    {"id": "CUST-001", "name": "Acme Corp", "email": "billing@acme.com"},
    {"id": "CUST-002", "name": "Globex Industries", "email": "accounts@globex.io"},
    {"id": "CUST-003", "name": "Initech LLC", "email": "pay@initech.com"},
    {"id": "CUST-004", "name": "Umbrella Corp", "email": "finance@umbrella.co"},
    {"id": "CUST-005", "name": "Stark Enterprises", "email": "ap@stark.com"},
]

INVOICES = [
    {"id": "INV-001", "customer_id": "CUST-001", "amount": 15000.00, "due_date": "2025-01-15T00:00:00", "status": "pending"},
    {"id": "INV-002", "customer_id": "CUST-001", "amount": 8500.50, "due_date": "2025-02-28T00:00:00", "status": "pending"},
    {"id": "INV-003", "customer_id": "CUST-002", "amount": 22000.00, "due_date": "2025-03-10T00:00:00", "status": "pending"},
    {"id": "INV-004", "customer_id": "CUST-002", "amount": 4750.00, "due_date": "2026-06-01T00:00:00", "status": "pending"},
    {"id": "INV-005", "customer_id": "CUST-003", "amount": 12300.00, "due_date": "2025-04-20T00:00:00", "status": "pending"},
    {"id": "INV-006", "customer_id": "CUST-003", "amount": 6800.00, "due_date": "2026-07-15T00:00:00", "status": "pending"},
    {"id": "INV-007", "customer_id": "CUST-004", "amount": 31000.00, "due_date": "2025-05-01T00:00:00", "status": "paid"},
    {"id": "INV-008", "customer_id": "CUST-004", "amount": 9200.00, "due_date": "2025-08-30T00:00:00", "status": "pending"},
    {"id": "INV-009", "customer_id": "CUST-005", "amount": 17500.00, "due_date": "2025-06-15T00:00:00", "status": "pending"},
    {"id": "INV-010", "customer_id": "CUST-005", "amount": 5500.00, "due_date": "2026-09-01T00:00:00", "status": "pending"},
]

PAYMENTS = [
    {"id": "PAY-001", "invoice_id": "INV-001", "amount": 15000.00, "payment_date": "2025-01-12T00:00:00"},
    {"id": "PAY-002", "invoice_id": "INV-002", "amount": 4000.00, "payment_date": "2025-02-20T00:00:00"},
    {"id": "PAY-003", "invoice_id": "INV-003", "amount": 22000.00, "payment_date": "2025-03-08T00:00:00"},
    {"id": "PAY-004", "invoice_id": "INV-005", "amount": 6000.00, "payment_date": "2025-04-10T00:00:00"},
    {"id": "PAY-005", "invoice_id": "INV-007", "amount": 31000.00, "payment_date": "2025-04-28T00:00:00"},
    {"id": "PAY-006", "invoice_id": "INV-009", "amount": 10000.00, "payment_date": "2025-06-10T00:00:00"},
]


def paginate(items, page, per_page=5):
    start = (page - 1) * per_page
    end = start + per_page
    total_pages = (len(items) + per_page - 1) // per_page
    return {
        "data": items[start:end],
        "page": page,
        "per_page": per_page,
        "total": len(items),
        "total_pages": total_pages,
    }


@app.get("/customers")
def get_customers(page: int = Query(1, ge=1)):
    return paginate(CUSTOMERS, page)


@app.get("/invoices")
def get_invoices(page: int = Query(1, ge=1)):
    return paginate(INVOICES, page)


@app.get("/payments")
def get_payments(page: int = Query(1, ge=1)):
    return paginate(PAYMENTS, page)
