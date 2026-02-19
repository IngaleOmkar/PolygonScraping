"""
Rate-limited JSON-RPC client with batch support and automatic retries.

Design goals
------------
* Minimise round-trips with **batch JSON-RPC** (many calls → one HTTP POST).
* Be gentle with the university node via configurable inter-request delay.
* Survive transient failures with exponential back-off retries.
"""

import time
import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# ---- exceptions ---------------------------------------------------------

class RpcError(Exception):
    """The JSON-RPC endpoint returned an error object."""

    def __init__(self, error_data: dict):
        self.code = error_data.get("code", -1)
        self.message = error_data.get("message", "Unknown RPC error")
        super().__init__(f"RPC Error {self.code}: {self.message}")


# ---- client -------------------------------------------------------------

class RpcClient:
    """
    Thin wrapper around ``requests.Session`` for Ethereum JSON-RPC.

    Features
    --------
    * HTTP keep-alive & connection pooling.
    * Automatic retries with exponential back-off on 429 / 5xx.
    * ``batch_call`` to pack N JSON-RPC requests in a single HTTP POST.
    * ``batch_call_chunked`` to split large batches into node-friendly chunks.
    * Configurable delay between HTTP requests.
    """

    def __init__(
        self,
        endpoint: str,
        request_delay: float = 0.1,
        timeout: int = 120,
        max_retries: int = 6,
        backoff_factor: float = 2.0,
    ):
        self.endpoint = endpoint
        self.request_delay = request_delay
        self.timeout = timeout
        self._id = 0

        # Persistent session with retry strategy
        self.session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=1, pool_maxsize=2)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({"Content-Type": "application/json"})

    # ---- internal helpers ------------------------------------------------

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _throttle(self) -> None:
        if self.request_delay > 0:
            time.sleep(self.request_delay)

    # ---- public API ------------------------------------------------------

    def call(self, method: str, params: list | None = None) -> Any:
        """Single JSON-RPC call.  Returns the *result* field."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": self._next_id(),
        }
        self._throttle()
        resp = self.session.post(self.endpoint, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise RpcError(body["error"])
        return body.get("result")

    def batch_call(self, calls: list[tuple[str, list]]) -> list[Any]:
        """
        Send *calls* ``[(method, params), …]`` as **one** JSON-RPC batch.

        Returns results in the same order.  Individual failures become ``None``.
        """
        if not calls:
            return []

        payload = [
            {"jsonrpc": "2.0", "method": m, "params": p or [], "id": self._next_id()}
            for m, p in calls
        ]
        self._throttle()
        resp = self.session.post(self.endpoint, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()

        # Responses may arrive out-of-order; re-sort by id.
        id_map = {r["id"]: r for r in body}
        ordered = [id_map.get(item["id"]) for item in payload]

        outputs: list[Any] = []
        for r in ordered:
            if r is None or "error" in (r or {}):
                if r and "error" in r:
                    logger.debug("Batch item error: %s", r["error"])
                outputs.append(None)
            else:
                outputs.append(r.get("result"))
        return outputs

    def batch_call_chunked(
        self,
        calls: list[tuple[str, list]],
        chunk_size: int = 50,
    ) -> list[Any]:
        """Split *calls* into chunks of *chunk_size* and fire sequentially."""
        results: list[Any] = []
        for i in range(0, len(calls), chunk_size):
            chunk = calls[i : i + chunk_size]
            results.extend(self.batch_call(chunk))
        return results

    # ---- convenience wrappers --------------------------------------------

    def get_latest_block_number(self) -> int:
        return int(self.call("eth_blockNumber"), 16)

    def get_client_version(self) -> str:
        return self.call("web3_clientVersion")

    def get_chain_id(self) -> int:
        return int(self.call("eth_chainId"), 16)
