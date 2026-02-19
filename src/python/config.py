"""
Configuration loader — reads .env from the project root.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .env lives at the project root, three levels above this file:
#   src/python/config.py  →  src/python  →  src  →  project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")


class Config:
    """Read-only configuration populated from environment variables."""

    # ---- RPC node -------------------------------------------------------
    rpc_endpoint: str = os.getenv("RPC_ENDPOINT", "http://130.60.144.43:8546")

    # ---- PostgreSQL -----------------------------------------------------
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5433"))
    db_name: str = os.getenv("DB_NAME", "polygon")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "pass")

    # ---- Indexer tuning -------------------------------------------------
    block_batch_size: int = int(os.getenv("BLOCK_BATCH_SIZE", "5"))
    rpc_batch_size: int = int(os.getenv("RPC_BATCH_SIZE", "50"))
    request_delay: float = int(os.getenv("REQUEST_DELAY_MS", "100")) / 1000.0
    poll_interval: float = float(os.getenv("POLL_INTERVAL_S", "2"))
    start_block: str = os.getenv("START_BLOCK", "latest")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def dsn(self) -> str:
        """libpq-style connection string for psycopg2."""
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname={self.db_name} user={self.db_user} "
            f"password={self.db_password}"
        )
