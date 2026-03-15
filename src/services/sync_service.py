import logging
from datetime import datetime
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.models.customer import Customer
from src.models.invoice import Invoice
from src.models.payment import Payment

logger = logging.getLogger(__name__)


def sync_customers(db, customers_data):
    """Upsert customers from external API data."""
    for c in customers_data:
        stmt = pg_insert(Customer).values(
            external_id=c["id"],
            name=c["name"],
            email=c.get("email", ""),
        ).on_conflict_do_update(
            index_elements=["external_id"],
            set_={"name": c["name"], "email": c.get("email", "")},
        )
        db.execute(stmt)
    db.commit()
    logger.info(f"Synced {len(customers_data)} customers")


def sync_invoices(db, invoices_data):
    """Upsert invoices. We need to resolve customer_id from external customer ref."""
    for inv in invoices_data:
        # look up internal customer id
        customer = db.query(Customer).filter_by(external_id=inv["customer_id"]).first()
        if not customer:
            logger.warning(f"Customer {inv['customer_id']} not found, skipping invoice {inv['id']}")
            continue

        due_date = datetime.fromisoformat(inv["due_date"])

        stmt = pg_insert(Invoice).values(
            external_id=inv["id"],
            customer_id=customer.id,
            amount=float(inv["amount"]),
            due_date=due_date,
            status=inv.get("status", "pending"),
        ).on_conflict_do_update(
            index_elements=["external_id"],
            set_={
                "amount": float(inv["amount"]),
                "due_date": due_date,
                "status": inv.get("status", "pending"),
            },
        )
        db.execute(stmt)
    db.commit()
    logger.info(f"Synced {len(invoices_data)} invoices")


def sync_payments(db, payments_data):
    """Upsert payments. Resolve invoice_id from external reference."""
    for p in payments_data:
        invoice = db.query(Invoice).filter_by(external_id=p["invoice_id"]).first()
        if not invoice:
            logger.warning(f"Invoice {p['invoice_id']} not found, skipping payment {p['id']}")
            continue

        payment_date = datetime.fromisoformat(p["payment_date"])

        stmt = pg_insert(Payment).values(
            external_id=p["id"],
            invoice_id=invoice.id,
            amount=float(p["amount"]),
            payment_date=payment_date,
        ).on_conflict_do_update(
            index_elements=["external_id"],
            set_={
                "amount": float(p["amount"]),
                "payment_date": payment_date,
            },
        )
        db.execute(stmt)
    db.commit()
    logger.info(f"Synced {len(payments_data)} payments")
