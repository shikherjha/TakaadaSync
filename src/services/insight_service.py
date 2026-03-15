from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.models.customer import Customer
from src.models.invoice import Invoice
from src.models.payment import Payment


def get_all_customers(db: Session):
    return db.query(Customer).all()


def get_customer_outstanding(db: Session, customer_id: int):
    """Return denormalized balance + risk level for a customer."""
    customer = db.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        return None

    # get overdue info for risk calculation
    now = datetime.utcnow()
    overdue_invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments))
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.due_date < now,
            Invoice.status != "paid",
        )
        .all()
    )

    overdue_count = 0
    max_days_overdue = 0
    for inv in overdue_invoices:
        paid = sum(p.amount for p in inv.payments)
        if inv.amount - paid > 0:
            overdue_count += 1
            due = inv.due_date.replace(tzinfo=None) if inv.due_date.tzinfo else inv.due_date
            days = (now - due).days
            max_days_overdue = max(max_days_overdue, days)

    risk = _calculate_risk(overdue_count, max_days_overdue)

    return {
        "customer_id": customer.id,
        "name": customer.name,
        "total_outstanding": customer.total_outstanding or 0.0,
        "available_credit": customer.available_credit or 0.0,
        "risk_level": risk,
        "overdue_invoice_count": overdue_count,
    }


def _calculate_risk(overdue_count, max_days_overdue):
    """Simple heuristic risk bucketing."""
    if overdue_count == 0:
        return "low"
    if overdue_count >= 3 or max_days_overdue > 30:
        return "high"
    return "medium"


def get_overdue_invoices(db: Session):
    """Find invoices past due with outstanding balance.
    Uses joinedload to avoid N+1 on payments.
    """
    now = datetime.utcnow()

    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments), joinedload(Invoice.customer))
        .filter(Invoice.due_date < now, Invoice.status != "paid")
        .all()
    )

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
    """High-level summary with aging buckets."""
    total_invoiced = db.query(
        func.coalesce(func.sum(Invoice.amount), 0)
    ).scalar()

    total_paid = db.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    total_outstanding = float(total_invoiced) - float(total_paid)

    # aging buckets
    now = datetime.utcnow()
    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.payments))
        .filter(Invoice.status != "paid")
        .all()
    )

    buckets = {
        "current": 0.0,
        "1_to_30_days": 0.0,
        "31_to_60_days": 0.0,
        "61_to_90_days": 0.0,
        "90_plus_days": 0.0,
    }

    overdue_count = 0
    overdue_amount = 0.0

    for inv in invoices:
        paid = sum(p.amount for p in inv.payments)
        remaining = inv.amount - paid
        if remaining <= 0:
            continue

        due = inv.due_date.replace(tzinfo=None) if inv.due_date.tzinfo else inv.due_date
        days_past = (now - due).days

        if days_past <= 0:
            buckets["current"] += remaining
        elif days_past <= 30:
            buckets["1_to_30_days"] += remaining
            overdue_count += 1
            overdue_amount += remaining
        elif days_past <= 60:
            buckets["31_to_60_days"] += remaining
            overdue_count += 1
            overdue_amount += remaining
        elif days_past <= 90:
            buckets["61_to_90_days"] += remaining
            overdue_count += 1
            overdue_amount += remaining
        else:
            buckets["90_plus_days"] += remaining
            overdue_count += 1
            overdue_amount += remaining

    # round bucket values
    for key in buckets:
        buckets[key] = round(buckets[key], 2)

    total_customers = db.query(Customer).count()
    total_invoices = db.query(Invoice).count()

    return {
        "total_customers": total_customers,
        "total_invoices": total_invoices,
        "total_invoiced": round(float(total_invoiced), 2),
        "total_paid": round(float(total_paid), 2),
        "total_outstanding": round(total_outstanding, 2),
        "overdue_count": overdue_count,
        "overdue_amount": round(overdue_amount, 2),
        "aging": buckets,
    }
