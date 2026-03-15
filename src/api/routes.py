from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services import insight_service

router = APIRouter()


@router.get("/customers")
def list_customers(db: Session = Depends(get_db)):
    customers = insight_service.get_all_customers(db)
    return [
        {
            "id": c.id,
            "external_id": c.external_id,
            "name": c.name,
            "email": c.email,
            "total_outstanding": c.total_outstanding or 0.0,
            "available_credit": c.available_credit or 0.0,
        }
        for c in customers
    ]


@router.get("/customers/{customer_id}/outstanding")
def customer_outstanding(customer_id: int, db: Session = Depends(get_db)):
    result = insight_service.get_customer_outstanding(db, customer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result


@router.get("/invoices/overdue")
def overdue_invoices(db: Session = Depends(get_db)):
    return insight_service.get_overdue_invoices(db)


@router.get("/insights/receivables-summary")
def receivables_summary(db: Session = Depends(get_db)):
    return insight_service.get_receivables_summary(db)
