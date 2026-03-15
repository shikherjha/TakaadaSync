import requests
import time
import logging

from src.config import EXTERNAL_API_URL

logger = logging.getLogger(__name__)


class AccountingClient:
    def __init__(self, base_url=None):
        self.base_url = base_url or EXTERNAL_API_URL
        self.session = requests.Session()

    def _get(self, endpoint, params=None, retries=3):
        """Make a GET request with basic retry logic."""
        url = f"{self.base_url}{endpoint}"
        for attempt in range(retries):
            try:
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                logger.warning(f"Request to {url} failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # simple exponential backoff
                else:
                    raise

    def _get_paginated(self, endpoint):
        """Fetch all pages from a paginated endpoint."""
        all_data = []
        page = 1
        while True:
            result = self._get(endpoint, params={"page": page})
            data = result.get("data", [])
            if not data:
                break
            all_data.extend(data)
            total_pages = result.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
        return all_data

    def get_customers(self):
        return self._get_paginated("/customers")

    def get_invoices(self):
        return self._get_paginated("/invoices")

    def get_payments(self):
        return self._get_paginated("/payments")
