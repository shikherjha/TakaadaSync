from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.customer import Customer
from src.models.invoice import Invoice
from src.models.payment import Payment


def get_all_customers(db: Session):
    return db.query(Customer).all()


def get_customer_outstanding(db: Session, customer_id: int):
    """Calculate outstanding balance for a customer.
    outstanding = total invoiced - total paid
    """
    customer = db.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        return None

    total_invoiced = (
        db.query(func.coalesce(func.sum(Invoice.amount), 0))
        .filter(Invoice.customer_id == customer_id)
        .scalar()
    )

    total_paid = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(Invoice.customer_id == customer_id)
        .scalar()
    )

    return {
        "customer_id": customer.id,
        "name": customer.name,
        "total_invoiced": round(float(total_invoiced), 2),
        "total_paid": round(float(total_paid), 2),
        "outstanding": round(float(total_invoiced) - float(total_paid), 2),
    }


def get_overdue_invoices(db: Session):
    """Find invoices where due_date < now and there's still an outstanding amount."""
    now = datetime.utcnow()

    invoices = db.query(Invoice).filter(
        Invoice.due_date < now,
        Invoice.status != "paid"
    ).all()

    overdue = []
    for inv in invoices:
        paid = sum(p.amount for p in inv.payments)
        remaining = inv.amount - paid
        if remaining > 0:
            due = inv.due_date.replace(tzinfo=None) if inv.due_date.tzinfo else inv.due_date
            overdue.append({
                "invoice_id": inv.id,
                "external_id": inv.external_id,
                "customer_id": inv.customer_id,
                "customer_name": inv.customer.name,
                "amount": inv.amount,
                "paid": round(paid, 2),
                "outstanding": round(remaining, 2),
                "due_date": inv.due_date.isoformat(),
                "days_overdue": (now - due).days,
            })

    return overdue


def get_receivables_summary(db: Session):
    """High-level summary of the whole receivables situation."""
    total_invoiced = db.query(
        func.coalesce(func.sum(Invoice.amount), 0)
    ).scalar()

    total_paid = db.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    total_outstanding = float(total_invoiced) - float(total_paid)

    now = datetime.utcnow()
    overdue_invoices = get_overdue_invoices(db)
    overdue_amount = sum(inv["outstanding"] for inv in overdue_invoices)

    total_customers = db.query(Customer).count()
    total_invoices = db.query(Invoice).count()

    return {
        "total_customers": total_customers,
        "total_invoices": total_invoices,
        "total_invoiced": round(float(total_invoiced), 2),
        "total_paid": round(float(total_paid), 2),
        "total_outstanding": round(total_outstanding, 2),
        "overdue_count": len(overdue_invoices),
        "overdue_amount": round(overdue_amount, 2),
    }
