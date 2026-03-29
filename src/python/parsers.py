"""
Transform raw JSON-RPC responses into database-ready tuples.

Each ``parse_*`` function matches the column order of its target table in
``create.sql`` so tuples can be passed straight to ``execute_values``.
"""

from datetime import datetime, timezone
from typing import Any

# keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)


# ---- hex helpers ---------------------------------------------------------

def hex_to_int(val: str | None, default: int = 0) -> int:
    """Safely convert a 0x-hex string to int."""
    if val is None or val in ("", "0x"):
        return default
    return int(val, 16)


def hex_to_timestamp(val: str) -> datetime:
    """Convert a hex UNIX epoch to a timezone-aware UTC datetime."""
    return datetime.fromtimestamp(int(val, 16), tz=timezone.utc)


def norm_addr(addr: str | None) -> str | None:
    """Lower-case an address, or pass through None."""
    return addr.lower() if addr else None


def topic_to_address(topic: str) -> str:
    """Extract the rightmost 20 bytes of a 32-byte hex topic as an address."""
    return "0x" + topic[-40:].lower()


# ---- block + transactions ------------------------------------------------

def parse_block_with_transactions(
    raw: dict[str, Any],
) -> tuple[tuple, list[tuple]]:
    """
    Parse one ``eth_getBlockByNumber(n, true)`` response.

    Returns
    -------
    (block_tuple, [transaction_tuple, …])

    Tuple field order matches the INSERT in ``database.py``.
    """
    block = (
        hex_to_int(raw["number"]),                                          # block_number
        raw["hash"].lower(),                                                # block_hash
        raw["parentHash"].lower(),                                          # parent_hash
        raw.get("nonce", "0x0"),                                            # nonce
        raw["sha3Uncles"].lower(),                                          # sha3_uncles
        raw["logsBloom"],                                                   # logs_bloom
        raw["transactionsRoot"].lower(),                                    # transactions_root
        raw["stateRoot"].lower(),                                           # state_root
        raw["receiptsRoot"].lower(),                                        # receipts_root
        raw["miner"].lower(),                                               # miner
        None,                                                               # proposer (TODO: recover from Bor extraData via ecrecover)
        hex_to_int(raw.get("difficulty")),                                  # difficulty
        hex_to_int(raw.get("totalDifficulty")),                             # total_difficulty
        hex_to_int(raw.get("size")),                                        # size
        raw.get("extraData", "0x"),                                         # extra_data
        hex_to_int(raw["gasLimit"]),                                        # gas_limit
        hex_to_int(raw["gasUsed"]),                                         # gas_used
        hex_to_int(raw.get("baseFeePerGas")) if raw.get("baseFeePerGas") else None,  # base_fee_per_gas
        hex_to_timestamp(raw["timestamp"]),                                 # block_timestamp
    )

    txs: list[tuple] = []
    for tx in raw.get("transactions", []):
        # If the block was fetched with full=False, txs are bare hashes — skip.
        if isinstance(tx, str):
            continue
        txs.append((
            tx["hash"].lower(),                                             # transaction_hash
            hex_to_int(tx["blockNumber"]),                                  # block_number
            hex_to_int(tx["transactionIndex"]),                             # transaction_index
            tx["from"].lower(),                                             # from_address
            norm_addr(tx.get("to")),                                        # to_address (NULL → create)
            hex_to_int(tx.get("value")),                                    # value (wei)
            hex_to_int(tx.get("gas")),                                      # gas limit
            hex_to_int(tx.get("gasPrice")),                                 # gas_price
            hex_to_int(tx.get("maxFeePerGas")) if tx.get("maxFeePerGas") else None,
            hex_to_int(tx.get("maxPriorityFeePerGas")) if tx.get("maxPriorityFeePerGas") else None,
            tx.get("input", "0x"),                                          # input (calldata)
            hex_to_int(tx.get("nonce")),                                    # sender nonce
            hex_to_int(tx.get("type")),                                     # transaction_type
        ))

    return block, txs


# ---- receipt + logs ------------------------------------------------------

def parse_receipt_with_logs(
    raw: dict[str, Any],
) -> tuple[tuple, list[tuple]]:
    """
    Parse one ``eth_getTransactionReceipt`` response.

    Returns
    -------
    (receipt_tuple, [log_tuple, …])
    """
    receipt = (
        raw["transactionHash"].lower(),                                     # transaction_hash
        hex_to_int(raw["blockNumber"]),                                     # block_number
        hex_to_int(raw["transactionIndex"]),                                # transaction_index
        hex_to_int(raw["cumulativeGasUsed"]),                               # cumulative_gas_used
        hex_to_int(raw["gasUsed"]),                                         # gas_used
        hex_to_int(raw.get("effectiveGasPrice")),                           # effective_gas_price
        norm_addr(raw.get("contractAddress")),                              # contract_address
        hex_to_int(raw.get("status")),                                      # status (1=ok, 0=fail)
        raw.get("root"),                                                    # root (pre-Byzantium)
        raw.get("logsBloom", ""),                                           # logs_bloom
    )

    logs: list[tuple] = []
    for entry in raw.get("logs", []):
        topics = entry.get("topics", [])
        logs.append((
            hex_to_int(entry["blockNumber"]),                               # block_number
            entry["transactionHash"].lower(),                               # transaction_hash
            hex_to_int(entry["transactionIndex"]),                          # transaction_index
            hex_to_int(entry["logIndex"]),                                  # log_index
            entry["address"].lower(),                                       # address (emitter)
            entry.get("data", "0x"),                                        # data
            topics[0].lower() if len(topics) > 0 else None,                # topic0
            topics[1].lower() if len(topics) > 1 else None,                # topic1
            topics[2].lower() if len(topics) > 2 else None,                # topic2
            topics[3].lower() if len(topics) > 3 else None,                # topic3
            entry.get("removed", False),                                    # removed
        ))

    return receipt, logs


# ---- token transfer decoding --------------------------------------------

def decode_transfer_from_log(log_tuple: tuple) -> tuple[str, tuple] | None:
    """
    Attempt to decode an ERC-20 or ERC-721 *Transfer* event from a log tuple.

    ERC-20  Transfer(address indexed from, address indexed to, uint256 value)
        → 3 topics (sig + from + to), value in ``data``

    ERC-721 Transfer(address indexed from, address indexed to, uint256 indexed tokenId)
        → 4 topics (sig + from + to + tokenId), ``data`` is empty

    Returns
    -------
    ("erc20",  tuple)  — if it looks like an ERC-20 transfer
    ("erc721", tuple)  — if it looks like an ERC-721 transfer
    None               — if the log is not a Transfer event
    """
    (
        block_number, tx_hash, _tx_idx, log_index,
        address, data, topic0, topic1, topic2, topic3, _removed,
    ) = log_tuple

    if topic0 != TRANSFER_TOPIC:
        return None

    # Both standards need at least from and to as indexed params
    if topic1 is None or topic2 is None:
        return None

    from_addr = topic_to_address(topic1)
    to_addr = topic_to_address(topic2)

    if topic3 is not None:
        # ERC-721: tokenId is the third indexed parameter
        try:
            token_id = int(topic3, 16)
        except (ValueError, TypeError):
            return None
        return ("erc721", (
            block_number, tx_hash, log_index,
            address, from_addr, to_addr, token_id,
        ))
    else:
        # ERC-20: value lives in the data field
        try:
            value = int(data, 16) if data and data != "0x" else 0
        except (ValueError, TypeError):
            return None
        return ("erc20", (
            block_number, tx_hash, log_index,
            address, from_addr, to_addr, value,
        ))
