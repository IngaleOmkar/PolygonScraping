#!/usr/bin/env python3
"""
Polygon Blockchain Data Indexer — entry point.

Usage
-----
    # 1. Verify RPC + DB connectivity
    python main.py --check

    # 2. Start / resume indexing (picks up from the last checkpoint)
    python main.py

    # 3. Index a specific block range and stop
    python main.py --start 55000000 --end 55001000

    # 4. Override start even if a checkpoint exists
    python main.py --start 60000000

Prerequisites
-------------
* PostgreSQL running with the ``polygon`` database created
  (execute ``src/sql/create.sql`` first).
* Dependencies installed: ``pip install -r requirements.txt``
* ``.env`` file in the project root with the required variables.

Notes
-----
* The ``traces`` table is **not** populated — the RPC endpoint blocks
  ``trace_*`` / ``debug_*`` (HTTP 403).  Use a trace-capable node later
  if you need internal calls.
"""

import argparse
import logging
import sys

from config import Config
from rpc_client import RpcClient
from endpoint_pool import EndpointPool
from database import Database
from indexer import Indexer


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Polygon Blockchain Data Indexer",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Verify RPC and DB connectivity, then exit",
    )
    p.add_argument(
        "--start",
        type=int,
        default=None,
        help="Override the starting block number",
    )
    p.add_argument(
        "--end",
        type=int,
        default=None,
        help="Stop after reaching this block (inclusive)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = Config()

    # ---- Logging --------------------------------------------------------
    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger("main")

    # ---- Initialise components ------------------------------------------
    pool = EndpointPool(
        endpoints=cfg.all_endpoints,
        max_workers=cfg.parallel_workers,
        timeout=cfg.pool_rpc_timeout,
        cooldown=cfg.endpoint_cooldown,
        receipt_batch_size=cfg.receipt_batch_size,
    )
    db = Database(cfg.dsn)
    db.init_checkpoint_table()

    # ---- Connectivity-check mode ----------------------------------------
    if args.check:
        try:
            ver = pool.get_client_version()
            chain = pool.get_chain_id()
            tip = pool.get_latest_block_number()
            log.info("✅ RPC OK — %s  chain=%d  tip=%d", ver, chain, tip)
        except Exception as exc:
            log.error("❌ RPC FAILED — %s", exc)
            sys.exit(1)

        log.info("✅ DB  OK — %s:%s/%s", cfg.db_host, cfg.db_port, cfg.db_name)
        log.info("✅ Endpoints: %d configured", len(cfg.all_endpoints))
        for ep in cfg.all_endpoints:
            log.info("    • %s", ep)
        return

    # ---- Determine start block ------------------------------------------
    start = args.start
    if start is None:
        cp = db.get_checkpoint()
        if cp is not None:
            start = cp + 1
            log.info("📌 Resuming from checkpoint → block %d", start)
        elif cfg.start_block.lower() == "latest":
            start = pool.get_latest_block_number()
            log.info("📌 No checkpoint — starting from chain tip %d", start)
        else:
            start = int(cfg.start_block)
            log.info("📌 No checkpoint — starting from configured block %d", start)

    # ---- Run the indexer ------------------------------------------------
    indexer = Indexer(pool, db, cfg)
    try:
        indexer.run(start, args.end)
    finally:
        pool.shutdown()
        db.close()
        log.info("🔌 Pool shut down, database connection closed.")


if __name__ == "__main__":
    main()
