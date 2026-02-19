"""
Core indexing pipeline — fetches, parses, and persists Polygon chain data.

Pipeline per batch
------------------
1. Fan out *N* blocks across healthy RPC endpoints in parallel
   (each worker fetches one block + all its receipts from a single endpoint).
2. Gather results; retry failures on different endpoints.
3. Reconcile — verify parent-hash chain and receipt completeness.
4. Parse receipts → logs; decode Transfer events → ERC-20 / ERC-721 rows.
5. Atomically commit everything + checkpoint to PostgreSQL.
6. Repeat — or sleep-poll when at the chain tip.

The ``traces`` table is **not** populated because most public endpoints
block ``trace_*`` / ``debug_*`` methods.  Traces can be back-filled
later if a trace-capable endpoint becomes available.
"""

import signal
import time
import logging

from config import Config
from endpoint_pool import EndpointPool, BlockResult
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
    Orchestrates the block-by-block indexing loop using a pool of
    RPC endpoints for parallel fetching.

    * Fully idempotent — safe to kill and restart at any time.
    * Checkpoint is updated inside the same DB transaction as the data,
      so you never get partial batches.
    * Reconciles data from multiple endpoints before committing.
    * Logs throughput statistics and per-endpoint health after every batch.
    """

    def __init__(self, pool: EndpointPool, db: Database, cfg: Config):
        self.pool = pool
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
            "▶ Indexer started  |  start=%d  batch=%d  workers=%d  endpoints=%d",
            current,
            self.cfg.block_batch_size,
            self.cfg.parallel_workers,
            len(self.cfg.all_endpoints),
        )
        self._t0 = time.monotonic()

        while not self._shutdown.requested:
            # Find out how far the chain has progressed
            chain_tip = self.pool.get_latest_block_number()

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
        block_numbers = list(range(from_block, to_block + 1))

        # ── 1. Fetch all blocks in parallel across endpoints ─────────────
        block_results = self.pool.fetch_blocks_parallel(block_numbers)

        # ── 2. Reconcile data from multiple endpoints ────────────────────
        self._reconcile(block_results)

        # ── 3. Parse blocks, receipts, logs, token transfers ─────────────
        blocks: list[tuple] = []
        transactions: list[tuple] = []
        receipts: list[tuple] = []
        logs: list[tuple] = []
        erc20_xfers: list[tuple] = []
        erc721_xfers: list[tuple] = []

        for result in block_results:
            # Block + embedded transactions
            blk, txs = parse_block_with_transactions(result.raw_block)
            blocks.append(blk)
            transactions.extend(txs)

            # Receipts + logs for this block
            for raw_receipt in result.raw_receipts:
                rcpt, log_list = parse_receipt_with_logs(raw_receipt)
                receipts.append(rcpt)
                for log_tuple in log_list:
                    logs.append(log_tuple)
                    xfer = decode_transfer_from_log(log_tuple)
                    if xfer:
                        kind, transfer = xfer
                        if kind == "erc20":
                            erc20_xfers.append(transfer)
                        else:
                            erc721_xfers.append(transfer)

        # ── 4. Atomic commit to PostgreSQL ───────────────────────────────
        self.db.commit_batch(
            last_block=to_block,
            blocks=blocks,
            transactions=transactions,
            receipts=receipts,
            logs=logs,
            erc20_transfers=erc20_xfers,
            erc721_transfers=erc721_xfers,
        )

        # ── 5. Stats ────────────────────────────────────────────────────
        n_blocks = to_block - from_block + 1
        self._blocks_done += n_blocks
        elapsed = time.monotonic() - t_start
        total_elapsed = time.monotonic() - self._t0
        bps = self._blocks_done / total_elapsed if total_elapsed > 0 else 0

        # Per-endpoint breakdown for this batch
        ep_summary = {}
        for r in block_results:
            ep_summary.setdefault(r.endpoint, []).append(r.latency)

        ep_str = "  ".join(
            f"{url.split('//')[1][:30]}={len(lats)}blk/{sum(lats):.1f}s"
            for url, lats in ep_summary.items()
        )

        logger.info(
            "✔ %d–%d  |  %d blk  %d tx  %d rcpt  %d log  "
            "%d erc20  %d erc721  | %.1fs  (%.1f blk/s avg)\n"
            "    endpoints: %s",
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
            ep_str,
        )

    # ---- reconciliation --------------------------------------------------

    @staticmethod
    def _reconcile(results: list[BlockResult]) -> None:
        """
        Verify data integrity across blocks fetched from different endpoints.

        Checks:
        1. Parent-hash chain — block N+1's parentHash must match block N's hash.
           Raises on mismatch (indicates reorg or endpoint serving stale data).
        2. Receipt completeness — every transaction must have a receipt.
           Raises on mismatch (should not happen after _fetch_one_block's
           own check, but acts as a safety net).

        Raises
        ------
        RuntimeError
            If any integrity check fails — the batch must NOT be committed.
        """
        for i in range(1, len(results)):
            prev_hash = results[i - 1].raw_block.get("hash", "").lower()
            curr_parent = results[i].raw_block.get("parentHash", "").lower()
            if prev_hash and curr_parent and prev_hash != curr_parent:
                raise RuntimeError(
                    f"Parent-hash chain break at block {results[i].block_number}: "
                    f"expected parent={prev_hash[:18]}… got={curr_parent[:18]}… "
                    f"(prev from {results[i - 1].endpoint}, "
                    f"curr from {results[i].endpoint}). "
                    f"Possible chain reorg — batch will be retried."
                )

        for result in results:
            expected = len([
                tx for tx in result.raw_block.get("transactions", [])
                if isinstance(tx, dict)
            ])
            actual = len(result.raw_receipts)
            if expected != actual:
                raise RuntimeError(
                    f"Block {result.block_number}: expected {expected} receipts, "
                    f"got {actual} (endpoint {result.endpoint}). "
                    f"Batch will be retried."
                )
