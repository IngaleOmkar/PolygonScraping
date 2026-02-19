"""
Multi-endpoint RPC pool with health tracking and parallel block fetching.

Distributes block-fetching work across multiple Polygon RPC endpoints,
tracks per-endpoint health (success rate, latency), and automatically
rotates failing endpoints to the back of the queue with cooldown.

Architecture
------------
* One ``RpcClient`` per endpoint, each with its own ``requests.Session``.
* A ``ThreadPoolExecutor`` fans out block-level work in parallel.
* Each worker fetches **one complete block** (header + txs + receipts)
  from a single endpoint — no cross-endpoint consistency issues.
* Failures are retried on a *different* endpoint (up to ``MAX_RETRIES``).
* Endpoints that fail repeatedly get a progressive cooldown and are
  moved to the back of the selection order.
"""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from rpc_client import RpcClient, RpcError

logger = logging.getLogger(__name__)


# ---- data structures ------------------------------------------------------


@dataclass
class EndpointHealth:
    """Per-endpoint health metrics (guarded by the pool's lock)."""

    url: str
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    total_latency: float = 0.0
    cooldown_until: float = 0.0

    @property
    def avg_latency(self) -> float:
        return self.total_latency / max(self.successes, 1)

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return self.successes / max(total, 1)


@dataclass
class BlockResult:
    """Complete data for one block: header, transactions, and receipts."""

    block_number: int
    raw_block: dict[str, Any]
    raw_receipts: list[dict[str, Any]]
    endpoint: str
    latency: float = 0.0


# ---- pool -----------------------------------------------------------------


class EndpointPool:
    """
    Manages multiple RPC endpoints with health-aware round-robin selection
    and parallel block fetching via ``ThreadPoolExecutor``.

    Parameters
    ----------
    endpoints : list[str]
        URLs of JSON-RPC endpoints (private + public).
    max_workers : int
        Number of parallel threads for block fetching (default 10).
    timeout : int
        Per-request HTTP timeout in seconds (default 30).
    cooldown : float
        Base cooldown in seconds for a failing endpoint (default 60).
        Scales linearly with consecutive failures, capped at 5 min.
    receipt_batch_size : int
        Max number of receipt calls per batch-RPC POST (default 20).
        Public endpoints often reject batches > 20–50.
    """

    MAX_RETRIES = 4

    def __init__(
        self,
        endpoints: list[str],
        max_workers: int = 10,
        timeout: int = 30,
        cooldown: float = 60.0,
        receipt_batch_size: int = 20,
    ):
        if not endpoints:
            raise ValueError("At least one endpoint is required")

        self._lock = threading.Lock()
        self._cooldown_base = cooldown
        self._receipt_batch_size = receipt_batch_size

        # One lightweight RpcClient per endpoint (no delay, fast retries)
        self._clients: dict[str, RpcClient] = {}
        self._health: dict[str, EndpointHealth] = {}
        self._order: list[str] = []

        for url in dict.fromkeys(endpoints):  # deduplicate, preserve order
            self._clients[url] = RpcClient(
                url,
                request_delay=0.0,
                timeout=timeout,
                max_retries=2,
                backoff_factor=0.5,
            )
            self._health[url] = EndpointHealth(url=url)
            self._order.append(url)

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="rpc-pool",
        )
        logger.info(
            "Endpoint pool: %d endpoints, %d workers, timeout=%ds",
            len(self._order),
            max_workers,
            timeout,
        )

    # ---- endpoint selection (caller must hold _lock) ----------------------

    def _get_healthy(self, n: int) -> list[str]:
        """Return up to *n* healthy (not on cooldown) endpoints."""
        now = time.monotonic()
        healthy = [
            url for url in self._order
            if self._health[url].cooldown_until <= now
        ]
        if not healthy:
            logger.warning("All endpoints on cooldown — resetting all cooldowns")
            for h in self._health.values():
                h.cooldown_until = 0.0
                h.consecutive_failures = 0
            healthy = list(self._order)
        return healthy[:n]

    def _pick_one(self, exclude: set[str] | None = None) -> str:
        """Pick the best available endpoint, excluding given URLs."""
        now = time.monotonic()
        exclude = exclude or set()
        for url in self._order:
            if url not in exclude and self._health[url].cooldown_until <= now:
                return url
        # Everything excluded or on cooldown — pick first not excluded
        for url in self._order:
            if url not in exclude:
                return url
        return self._order[0]

    # ---- health bookkeeping -----------------------------------------------

    def _report_success(self, url: str, latency: float) -> None:
        with self._lock:
            h = self._health[url]
            h.successes += 1
            h.total_latency += latency
            h.consecutive_failures = 0

    def _report_failure(self, url: str) -> None:
        with self._lock:
            h = self._health[url]
            h.failures += 1
            h.consecutive_failures += 1
            cooldown = min(
                self._cooldown_base * h.consecutive_failures, 300.0
            )
            h.cooldown_until = time.monotonic() + cooldown
            # Move to back of priority order
            if url in self._order:
                self._order.remove(url)
                self._order.append(url)
            logger.warning(
                "Endpoint %s failed (consecutive=%d) — cooldown %.0fs",
                url,
                h.consecutive_failures,
                cooldown,
            )

    # ---- parallel block fetching ------------------------------------------

    def fetch_blocks_parallel(
        self,
        block_numbers: list[int],
    ) -> list[BlockResult]:
        """
        Fetch complete block data (header + txs + receipts) for every block
        in *block_numbers*, distributing work across healthy endpoints.

        Each block is fetched entirely from a single endpoint.
        Failed blocks are retried on *different* endpoints — we track which
        endpoints each block has already been attempted on.

        Returns
        -------
        list[BlockResult]
            Results sorted by block number.

        Raises
        ------
        RuntimeError
            If any block still fails after ``MAX_RETRIES`` rounds.
        """
        results: dict[int, BlockResult] = {}
        pending = set(block_numbers)
        # Track which endpoints have been tried per block to avoid re-use
        attempted: dict[int, set[str]] = {b: set() for b in block_numbers}

        for attempt in range(self.MAX_RETRIES):
            if not pending:
                break

            # Assign each pending block to a healthy endpoint, skipping
            # any endpoint that already failed for that specific block.
            with self._lock:
                healthy = self._get_healthy(len(self._order))

            assignments: list[tuple[int, str]] = []
            for block_num in sorted(pending):
                # Filter out endpoints already attempted for this block
                candidates = [
                    url for url in healthy if url not in attempted[block_num]
                ]
                if not candidates:
                    # All healthy endpoints exhausted for this block;
                    # fall back to any healthy endpoint (retry anyway).
                    candidates = healthy
                # Round-robin across remaining candidates
                idx = block_num % len(candidates)
                chosen = candidates[idx]
                assignments.append((block_num, chosen))
                attempted[block_num].add(chosen)

            # Fan out
            futures: dict = {}
            for block_num, endpoint in assignments:
                future = self._executor.submit(
                    self._fetch_one_block, endpoint, block_num,
                )
                futures[future] = (block_num, endpoint)

            # Collect
            failed: set[int] = set()
            for future in as_completed(futures):
                block_num, endpoint = futures[future]
                try:
                    result = future.result()
                    self._report_success(endpoint, result.latency)
                    results[block_num] = result
                except Exception as exc:
                    logger.warning(
                        "Block %d failed on %s (attempt %d/%d): %s",
                        block_num,
                        endpoint,
                        attempt + 1,
                        self.MAX_RETRIES,
                        exc,
                    )
                    self._report_failure(endpoint)
                    failed.add(block_num)

            pending = failed

        if pending:
            raise RuntimeError(
                f"Failed to fetch blocks after {self.MAX_RETRIES} attempts: "
                f"{sorted(pending)}"
            )

        return sorted(results.values(), key=lambda r: r.block_number)

    def _fetch_one_block(self, endpoint: str, block_num: int) -> BlockResult:
        """
        Fetch one complete block (header + transactions + all receipts)
        from a single endpoint.
        """
        client = self._clients[endpoint]
        t0 = time.monotonic()

        # 1. Block with full transaction objects
        raw_block = client.call("eth_getBlockByNumber", [hex(block_num), True])
        if raw_block is None:
            raise RpcError(
                {"code": -1, "message": f"Block {block_num} returned null"}
            )

        # 2. Batch-fetch all receipts for this block's transactions
        txs = raw_block.get("transactions", [])
        tx_hashes = [tx["hash"] for tx in txs if isinstance(tx, dict)]

        raw_receipts: list[dict] = []
        if tx_hashes:
            receipt_calls = [
                ("eth_getTransactionReceipt", [h]) for h in tx_hashes
            ]
            fetched = client.batch_call_chunked(
                receipt_calls, chunk_size=self._receipt_batch_size,
            )
            raw_receipts = [r for r in fetched if r is not None]

            # Receipt completeness check — if any are missing, raise so
            # the pool retries this block on a different endpoint.
            if len(raw_receipts) != len(tx_hashes):
                missing = len(tx_hashes) - len(raw_receipts)
                raise RpcError({
                    "code": -1,
                    "message": (
                        f"Block {block_num}: {missing}/{len(tx_hashes)} "
                        f"receipts missing from {endpoint}"
                    ),
                })

        latency = time.monotonic() - t0
        return BlockResult(
            block_number=block_num,
            raw_block=raw_block,
            raw_receipts=raw_receipts,
            endpoint=endpoint,
            latency=latency,
        )

    # ---- chain-tip & utility queries --------------------------------------

    def get_latest_block_number(self) -> int:
        """
        Query the chain tip from several endpoints and return the **highest**
        reported value (guards against stale nodes).
        """
        with self._lock:
            endpoints = self._get_healthy(min(3, len(self._order)))

        tips: list[int] = []
        for url in endpoints:
            try:
                tip = self._clients[url].get_latest_block_number()
                self._report_success(url, 0.0)
                tips.append(tip)
            except Exception:
                self._report_failure(url)

        if not tips:
            raise RuntimeError("All endpoints failed to report chain tip")
        return max(tips)

    def get_client_version(self) -> str:
        """For connectivity checks — try first healthy endpoint."""
        with self._lock:
            endpoints = self._get_healthy(3)
        for url in endpoints:
            try:
                return self._clients[url].get_client_version()
            except Exception:
                self._report_failure(url)
        raise RuntimeError("All endpoints failed get_client_version")

    def get_chain_id(self) -> int:
        """For connectivity checks — try first healthy endpoint."""
        with self._lock:
            endpoints = self._get_healthy(3)
        for url in endpoints:
            try:
                return self._clients[url].get_chain_id()
            except Exception:
                self._report_failure(url)
        raise RuntimeError("All endpoints failed get_chain_id")

    # ---- diagnostics -------------------------------------------------------

    def health_summary(self) -> list[dict]:
        """Return per-endpoint health stats (safe to call from any thread)."""
        now = time.monotonic()
        with self._lock:
            return [
                {
                    "url": h.url,
                    "successes": h.successes,
                    "failures": h.failures,
                    "avg_latency_s": round(h.avg_latency, 3),
                    "success_rate": round(h.success_rate, 3),
                    "on_cooldown": h.cooldown_until > now,
                }
                for h in self._health.values()
            ]

    def shutdown(self) -> None:
        """Shut down the thread pool executor."""
        self._executor.shutdown(wait=True)
