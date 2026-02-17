"""
PostgreSQL persistence layer — bulk inserts and checkpoint management.

Every batch of blocks is committed **atomically**: either all rows plus the
checkpoint update succeed, or the whole batch is rolled back and can be retried.
"""

import logging

import psycopg2
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)

# ---- SQL templates (ON CONFLICT makes every insert idempotent) -----------

_BLOCKS_SQL = """
INSERT INTO blocks (
    block_number, block_hash, parent_hash, nonce, sha3_uncles,
    logs_bloom, transactions_root, state_root, receipts_root,
    miner, difficulty, total_difficulty, size, extra_data,
    gas_limit, gas_used, base_fee_per_gas, block_timestamp
) VALUES %s
ON CONFLICT (block_number) DO NOTHING
"""

_TXS_SQL = """
INSERT INTO transactions (
    transaction_hash, block_number, transaction_index,
    from_address, to_address, value, gas, gas_price,
    max_fee_per_gas, max_priority_fee_per_gas,
    input, nonce, transaction_type
) VALUES %s
ON CONFLICT (transaction_hash) DO NOTHING
"""

_RECEIPTS_SQL = """
INSERT INTO receipts (
    transaction_hash, block_number, transaction_index,
    cumulative_gas_used, gas_used, effective_gas_price,
    contract_address, status, root, logs_bloom
) VALUES %s
ON CONFLICT (transaction_hash) DO NOTHING
"""

_LOGS_SQL = """
INSERT INTO logs (
    block_number, transaction_hash, transaction_index,
    log_index, address, data,
    topic0, topic1, topic2, topic3, removed
) VALUES %s
ON CONFLICT (block_number, log_index) DO NOTHING
"""

_ERC20_SQL = """
INSERT INTO token_transfers_erc20 (
    block_number, transaction_hash, log_index,
    token_address, from_address, to_address, value
) VALUES %s
ON CONFLICT (block_number, log_index) DO NOTHING
"""

_ERC721_SQL = """
INSERT INTO token_transfers_erc721 (
    block_number, transaction_hash, log_index,
    token_address, from_address, to_address, token_id
) VALUES %s
ON CONFLICT (block_number, log_index) DO NOTHING
"""

_CHECKPOINT_UPSERT = """
INSERT INTO indexer_checkpoints (key, block_number, updated_at)
VALUES (%s, %s, NOW())
ON CONFLICT (key) DO UPDATE
    SET block_number = EXCLUDED.block_number,
        updated_at   = NOW()
"""


class Database:
    """
    Single-connection wrapper with automatic reconnection.

    A connection pool is overkill here — the indexer is single-threaded and
    pipelines one batch at a time.  Keeping one persistent connection avoids
    pool overhead while still being safe (reconnect on failure).
    """

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._conn: psycopg2.extensions.connection | None = None
        self._connect()

    # ---- connection management -------------------------------------------

    def _connect(self) -> None:
        logger.info("Connecting to PostgreSQL …")
        self._conn = psycopg2.connect(self._dsn)
        self._conn.autocommit = False
        logger.info("Connected.")

    def _ensure(self) -> psycopg2.extensions.connection:
        if self._conn is None or self._conn.closed:
            self._connect()
        return self._conn  # type: ignore[return-value]

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()

    # ---- schema helpers --------------------------------------------------

    def init_checkpoint_table(self) -> None:
        """Create the checkpoint bookkeeping table if it doesn't exist."""
        conn = self._ensure()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS indexer_checkpoints (
                    key          VARCHAR(64) PRIMARY KEY,
                    block_number BIGINT NOT NULL,
                    updated_at   TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()

    def get_checkpoint(self, key: str = "main") -> int | None:
        """Return the last committed block number, or *None* if no checkpoint."""
        conn = self._ensure()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT block_number FROM indexer_checkpoints WHERE key = %s",
                (key,),
            )
            row = cur.fetchone()
        conn.commit()  # close the implicit txn
        return row[0] if row else None

    # ---- atomic batch commit ---------------------------------------------

    def commit_batch(
        self,
        last_block: int,
        blocks: list[tuple],
        transactions: list[tuple],
        receipts: list[tuple],
        logs: list[tuple],
        erc20_transfers: list[tuple],
        erc721_transfers: list[tuple],
        checkpoint_key: str = "main",
    ) -> None:
        """
        Insert **all** rows and update the checkpoint in a single transaction.

        If any step fails the whole batch is rolled back so it can be retried
        without leaving partial data.
        """
        conn = self._ensure()
        try:
            with conn.cursor() as cur:
                if blocks:
                    execute_values(cur, _BLOCKS_SQL, blocks, page_size=500)
                if transactions:
                    execute_values(cur, _TXS_SQL, transactions, page_size=500)
                if receipts:
                    execute_values(cur, _RECEIPTS_SQL, receipts, page_size=500)
                if logs:
                    execute_values(cur, _LOGS_SQL, logs, page_size=1000)
                if erc20_transfers:
                    execute_values(cur, _ERC20_SQL, erc20_transfers, page_size=1000)
                if erc721_transfers:
                    execute_values(cur, _ERC721_SQL, erc721_transfers, page_size=1000)
                cur.execute(_CHECKPOINT_UPSERT, (checkpoint_key, last_block))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
