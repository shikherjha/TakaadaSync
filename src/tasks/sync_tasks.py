import logging

from src.tasks.celery_app import celery_app
from src.integrations.accounting_client import AccountingClient
from src.services.sync_service import sync_customers, sync_invoices, sync_payments
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def sync_all_data(self):
    """Main sync task. Fetches everything from the external API and upserts locally."""
    client = AccountingClient()
    db = SessionLocal()

    try:
        logger.info("Starting data sync...")

        # customers first since invoices reference them
        customers = client.get_customers()
        sync_customers(db, customers)

        invoices = client.get_invoices()
        sync_invoices(db, invoices)

        payments = client.get_payments()
        sync_payments(db, payments)

        logger.info("Sync completed successfully")
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()
