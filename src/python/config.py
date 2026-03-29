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


# Default public RPC endpoints for Polygon mainnet.
# Override with a comma-separated PUBLIC_ENDPOINTS env var.
_DEFAULT_PUBLIC_ENDPOINTS: list[str] = [
    "https://polygon-mainnet.gateway.tatum.io/",
    "https://1rpc.io/matic",
    "https://polygon-bor.publicnode.com",
    "https://api.blockeden.xyz/polygon/67nCBdZQSH9z3YqDDjdm",
    "https://polygon.drpc.org/",
    "https://polygon-public.nodies.app",
    "https://polygon.api.onfinality.io/public",
    "https://poly.api.pocket.network/",
    "https://rpc-mainnet.matic.quiknode.pro",
    "https://polygon-mainnet.rpcfast.com?api_key=xbhWBI1Wkguk8SNMu1bvvLurPGLXmgwYeC4S6g2H7WdwFigZSmPWVZRxrskEQwIf",
    "https://polygon.rpc.subquery.network/public",
    "https://polygon.gateway.tenderly.co",
    "https://137.rpc.thirdweb.com/",
]


class Config:
    """Read-only configuration populated from environment variables."""

    # ---- Primary (private) RPC node -------------------------------------
    rpc_endpoint: str = os.getenv("RPC_ENDPOINT", "http://130.60.144.43:8546")

    # ---- Public RPC endpoints -------------------------------------------
    public_endpoints: list[str] = (
        os.getenv("PUBLIC_ENDPOINTS", "").split(",")
        if os.getenv("PUBLIC_ENDPOINTS")
        else _DEFAULT_PUBLIC_ENDPOINTS
    )

    @property
    def all_endpoints(self) -> list[str]:
        """Private endpoint first, then all public endpoints."""
        return [self.rpc_endpoint] + self.public_endpoints

    # ---- PostgreSQL -----------------------------------------------------
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5433"))
    db_name: str = os.getenv("DB_NAME", "polygon")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "pass")

    # ---- Parallel fetching ----------------------------------------------
    block_batch_size: int = int(os.getenv("BLOCK_BATCH_SIZE", "10"))
    parallel_workers: int = int(os.getenv("PARALLEL_WORKERS", "10"))
    pool_rpc_timeout: int = int(os.getenv("POOL_RPC_TIMEOUT", "30"))
    receipt_batch_size: int = int(os.getenv("RECEIPT_BATCH_SIZE", "20"))
    endpoint_cooldown: float = float(os.getenv("ENDPOINT_COOLDOWN_S", "60"))

    # ---- Indexer tuning -------------------------------------------------
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
