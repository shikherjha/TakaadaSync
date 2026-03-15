import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/takaada")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL", "http://localhost:8001")
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))
