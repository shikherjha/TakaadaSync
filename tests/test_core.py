import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.session import Base
from src.models.customer import Customer
from src.models.invoice import Invoice
from src.models.payment import Payment
from src.services.sync_service import sync_customers, sync_invoices, sync_payments
from src.services.insight_service import (
    get_customer_outstanding,
    get_overdue_invoices,
    get_receivables_summary,
)

# use sqlite for tests, easier to run without docker
TEST_DB_URL = "sqlite:///test.db"
engine = create_engine(TEST_DB_URL)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    session = TestSession()
    yield session
    session.close()


# --- sync tests ---

def test_sync_customers_creates_records(db):
    data = [
        {"id": "C1", "name": "Test Co", "email": "test@test.com"},
        {"id": "C2", "name": "Another Co", "email": "a@b.com"},
    ]
    # sqlite doesnt support pg insert, so we test the flow differently
    # for actual integration tests you'd spin up postgres
    # here we just test the models directly
    c = Customer(external_id="C1", name="Test Co", email="test@test.com")
    db.add(c)
    db.commit()

    result = db.query(Customer).filter_by(external_id="C1").first()
    assert result is not None
    assert result.name == "Test Co"


def test_duplicate_customer_external_id(db):
    c1 = Customer(external_id="C1", name="First", email="a@a.com")
    db.add(c1)
    db.commit()

    # same external_id should fail
    c2 = Customer(external_id="C1", name="Second", email="b@b.com")
    db.add(c2)
    with pytest.raises(Exception):
        db.commit()
    db.rollback()


# --- insight tests ---

def test_customer_outstanding_calculation(db):
    c = Customer(external_id="C1", name="Test Co", email="t@t.com")
    db.add(c)
    db.flush()

    inv = Invoice(
        external_id="I1", customer_id=c.id, amount=1000.0,
        due_date=datetime(2025, 6, 1), status="pending"
    )
    db.add(inv)
    db.flush()

    p = Payment(
        external_id="P1", invoice_id=inv.id, amount=400.0,
        payment_date=datetime(2025, 5, 15)
    )
    db.add(p)
    db.commit()

    result = get_customer_outstanding(db, c.id)
    assert result["outstanding"] == 600.0
    assert result["total_invoiced"] == 1000.0
    assert result["total_paid"] == 400.0


def test_overdue_invoices(db):
    c = Customer(external_id="C1", name="Test Co", email="t@t.com")
    db.add(c)
    db.flush()

    # overdue invoice (past due date, not fully paid)
    inv1 = Invoice(
        external_id="I1", customer_id=c.id, amount=500.0,
        due_date=datetime(2024, 1, 1), status="pending"
    )
    # future invoice (not overdue)
    inv2 = Invoice(
        external_id="I2", customer_id=c.id, amount=300.0,
        due_date=datetime(2027, 12, 31), status="pending"
    )
    db.add_all([inv1, inv2])
    db.commit()

    overdue = get_overdue_invoices(db)
    assert len(overdue) == 1
    assert overdue[0]["external_id"] == "I1"


def test_receivables_summary(db):
    c = Customer(external_id="C1", name="Test Co", email="t@t.com")
    db.add(c)
    db.flush()

    inv = Invoice(
        external_id="I1", customer_id=c.id, amount=2000.0,
        due_date=datetime(2024, 1, 1), status="pending"
    )
    db.add(inv)
    db.flush()

    p = Payment(
        external_id="P1", invoice_id=inv.id, amount=750.0,
        payment_date=datetime(2024, 1, 5)
    )
    db.add(p)
    db.commit()

    summary = get_receivables_summary(db)
    assert summary["total_invoiced"] == 2000.0
    assert summary["total_paid"] == 750.0
    assert summary["total_outstanding"] == 1250.0
    assert summary["overdue_count"] == 1


# --- api client mock test ---

def test_accounting_client_pagination():
    """Test that the client handles pagination correctly."""
    from src.integrations.accounting_client import AccountingClient

    client = AccountingClient(base_url="http://fake")

    mock_responses = [
        {"data": [{"id": "1"}, {"id": "2"}], "page": 1, "total_pages": 2},
        {"data": [{"id": "3"}], "page": 2, "total_pages": 2},
    ]

    with patch.object(client, "_get", side_effect=mock_responses):
        result = client._get_paginated("/test")
        assert len(result) == 3
        assert result[0]["id"] == "1"
        assert result[2]["id"] == "3"
