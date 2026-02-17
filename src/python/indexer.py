"""
Core indexing pipeline — fetches, parses, and persists Polygon chain data.

Pipeline per batch
------------------
1. Fetch *N* blocks with full transaction objects  (batch JSON-RPC)
2. Fetch all transaction receipts for those blocks (batch JSON-RPC, chunked)
3. Parse receipts → logs; decode Transfer events → ERC-20 / ERC-721 rows
4. Atomically commit everything + checkpoint to PostgreSQL
5. Repeat — or sleep-poll when at the chain tip

The ``traces`` table is **not** populated because the RPC endpoint blocks
``trace_*`` and ``debug_*`` methods (HTTP 403).  Traces can be back-filled
later if a trace-capable endpoint becomes available.
"""

import signal
import time
import logging

from config import Config
from rpc_client import RpcClient
from database import Database
from parsers import (
    parse_block_with_transactions,
    parse_receipt_with_logs,
    decode_transfer_from_log,
)

logger = logging.getLogger(__name__)


# ---- graceful shutdown ---------------------------------------------------

class _Shutdown:
    """Catch SIGINT / SIGTERM so the current batch can finish cleanly."""

    _stop = False

    def __init__(self):
        signal.signal(signal.SIGINT, self._handler)
        signal.signal(signal.SIGTERM, self._handler)

    def _handler(self, _sig, _frame):
        if not self._stop:
            logger.info("⏹  Shutdown requested — finishing current batch …")
        self._stop = True

    @property
    def requested(self) -> bool:
        return self._stop


# ---- indexer -------------------------------------------------------------

class Indexer:
    """
    Orchestrates the block-by-block indexing loop.

    * Fully idempotent — safe to kill and restart at any time.
    * Checkpoint is updated inside the same DB transaction as the data,
      so you never get partial batches.
    * Logs throughput statistics after every batch.
    """

    def __init__(self, rpc: RpcClient, db: Database, cfg: Config):
        self.rpc = rpc
        self.db = db
        self.cfg = cfg
        self._shutdown = _Shutdown()
        self._blocks_done = 0
        self._t0 = time.monotonic()

    # ---- public entry point ----------------------------------------------

    def run(self, start_block: int, end_block: int | None = None) -> None:
        """
        Index blocks from *start_block* forward.

        * If *end_block* is given, stops after it (bounded back-fill).
        * Otherwise runs forever, polling for new blocks at the tip.
        * Handles ``SIGINT`` / ``SIGTERM`` for clean shutdown.
        """
        current = start_block

        logger.info(
            "▶ Indexer started  |  start=%d  batch=%d  rpc_chunk=%d  delay=%dms",
            current,
            self.cfg.block_batch_size,
            self.cfg.rpc_batch_size,
            int(self.cfg.request_delay * 1000),
        )
        self._t0 = time.monotonic()

        while not self._shutdown.requested:
            # Find out how far the chain has progressed
            chain_tip = self.rpc.get_latest_block_number()

            if current > chain_tip:
                logger.info("💤 At chain tip (%d) — polling …", chain_tip)
                time.sleep(self.cfg.poll_interval)
                continue

            # Determine the end of this batch
            batch_end = min(
                current + self.cfg.block_batch_size - 1,
                chain_tip,
            )
            if end_block is not None:
                batch_end = min(batch_end, end_block)

            # Process the batch (with retry on transient failure)
            try:
                self._process_batch(current, batch_end)
            except Exception:
                logger.exception(
                    "❌ Batch %d–%d failed — will retry in 5 s",
                    current,
                    batch_end,
                )
                time.sleep(5)
                continue

            current = batch_end + 1

            if end_block is not None and current > end_block:
                logger.info("🏁 Reached end block %d.", end_block)
                break

        logger.info(
            "■ Indexer stopped.  Total blocks indexed this session: %d",
            self._blocks_done,
        )

    # ---- batch processing ------------------------------------------------

    def _process_batch(self, from_block: int, to_block: int) -> None:
        t_start = time.monotonic()

        # ── 1. Fetch blocks (with full tx objects) ──────────────────────
        block_calls = [
            ("eth_getBlockByNumber", [hex(n), True])
            for n in range(from_block, to_block + 1)
        ]
        raw_blocks = self.rpc.batch_call_chunked(
            block_calls, self.cfg.rpc_batch_size
        )

        # ── 2. Parse blocks & collect tx hashes ─────────────────────────
        blocks: list[tuple] = []
        transactions: list[tuple] = []
        tx_hashes: list[str] = []

        for raw in raw_blocks:
            if raw is None:
                continue
            blk, txs = parse_block_with_transactions(raw)
            blocks.append(blk)
            transactions.extend(txs)
            tx_hashes.extend(tx[0] for tx in txs)  # field 0 = transaction_hash

        # ── 3. Fetch all receipts ────────────────────────────────────────
        if tx_hashes:
            receipt_calls = [
                ("eth_getTransactionReceipt", [h]) for h in tx_hashes
            ]
            raw_receipts = self.rpc.batch_call_chunked(
                receipt_calls, self.cfg.rpc_batch_size
            )
        else:
            raw_receipts = []

        # ── 4. Parse receipts, logs, and token transfers ─────────────────
        receipts: list[tuple] = []
        logs: list[tuple] = []
        erc20_xfers: list[tuple] = []
        erc721_xfers: list[tuple] = []

        for raw in raw_receipts:
            if raw is None:
                continue
            rcpt, log_list = parse_receipt_with_logs(raw)
            receipts.append(rcpt)
            for log_tuple in log_list:
                logs.append(log_tuple)
                result = decode_transfer_from_log(log_tuple)
                if result:
                    kind, transfer = result
                    if kind == "erc20":
                        erc20_xfers.append(transfer)
                    else:
                        erc721_xfers.append(transfer)

        # ── 5. Atomic commit to PostgreSQL ───────────────────────────────
        self.db.commit_batch(
            last_block=to_block,
            blocks=blocks,
            transactions=transactions,
            receipts=receipts,
            logs=logs,
            erc20_transfers=erc20_xfers,
            erc721_transfers=erc721_xfers,
        )

        # ── 6. Stats ────────────────────────────────────────────────────
        n_blocks = to_block - from_block + 1
        self._blocks_done += n_blocks
        elapsed = time.monotonic() - t_start
        total_elapsed = time.monotonic() - self._t0
        bps = self._blocks_done / total_elapsed if total_elapsed > 0 else 0

        logger.info(
            "✔ %d–%d  |  %d blk  %d tx  %d rcpt  %d log  "
            "%d erc20  %d erc721  | %.1fs  (%.1f blk/s avg)",
            from_block,
            to_block,
            len(blocks),
            len(transactions),
            len(receipts),
            len(logs),
            len(erc20_xfers),
            len(erc721_xfers),
            elapsed,
            bps,
        )
