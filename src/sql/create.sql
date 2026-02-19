-- ============================================================
-- Polygon Blockchain Data Indexing Schema
-- Target: PostgreSQL
-- Description: Normalized schema for blocks, transactions,
--              receipts, logs, token transfers (ERC-20 & ERC-721),
--              and internal calls/traces from the Polygon network.
-- ============================================================

-- Create the database
CREATE DATABASE polygon;

-- Connect to the database (psql meta-command)
\c polygon;

-- ============================================================
-- 1. BLOCKS
-- ============================================================
CREATE TABLE blocks (
    block_number        BIGINT          NOT NULL,
    block_hash          CHAR(66)        NOT NULL,       -- 0x-prefixed, 32-byte hex
    parent_hash         CHAR(66)        NOT NULL,
    nonce               VARCHAR(18)     NOT NULL,       -- 0x-prefixed 8-byte hex
    sha3_uncles         CHAR(66)        NOT NULL,
    logs_bloom          VARCHAR(514)    NOT NULL,       -- 0x + 256-byte hex
    transactions_root   CHAR(66)        NOT NULL,
    state_root          CHAR(66)        NOT NULL,
    receipts_root       CHAR(66)        NOT NULL,
    miner               CHAR(42)        NOT NULL,       -- 0x-prefixed, 20-byte address
    difficulty          NUMERIC(38,0)   NOT NULL DEFAULT 0,
    total_difficulty    NUMERIC(38,0)   NOT NULL DEFAULT 0,
    size                BIGINT          NOT NULL,
    extra_data          TEXT            NOT NULL DEFAULT '0x',
    gas_limit           BIGINT          NOT NULL,
    gas_used            BIGINT          NOT NULL,
    base_fee_per_gas    NUMERIC(38,0)   NULL,           -- post EIP-1559 (nullable for pre-1559 blocks)
    block_timestamp     TIMESTAMP       NOT NULL,       -- derived from UNIX epoch

    CONSTRAINT pk_blocks PRIMARY KEY (block_number),
    CONSTRAINT uq_blocks_hash UNIQUE (block_hash)
);

CREATE INDEX idx_blocks_timestamp ON blocks (block_timestamp);
CREATE INDEX idx_blocks_miner ON blocks (miner);

-- ============================================================
-- 2. TRANSACTIONS
-- ============================================================
CREATE TABLE transactions (
    transaction_hash            CHAR(66)        NOT NULL,   -- 0x-prefixed, 32-byte hex
    block_number                BIGINT          NOT NULL,
    transaction_index           INT             NOT NULL,
    from_address                CHAR(42)        NOT NULL,
    to_address                  CHAR(42)        NULL,       -- NULL for contract creation txns
    value                       NUMERIC(78,0)   NOT NULL DEFAULT 0,  -- wei (uint256)
    gas                         BIGINT          NOT NULL,   -- gas limit set by sender
    gas_price                   NUMERIC(38,0)   NOT NULL DEFAULT 0,
    max_fee_per_gas             NUMERIC(38,0)   NULL,       -- EIP-1559 (type 2 txns)
    max_priority_fee_per_gas    NUMERIC(38,0)   NULL,       -- EIP-1559 (type 2 txns)
    input                       TEXT            NOT NULL DEFAULT '0x',
    nonce                       BIGINT          NOT NULL,
    transaction_type            SMALLINT        NOT NULL DEFAULT 0,  -- 0=legacy, 1=access-list, 2=EIP-1559

    CONSTRAINT pk_transactions PRIMARY KEY (transaction_hash),
    CONSTRAINT fk_transactions_block FOREIGN KEY (block_number)
        REFERENCES blocks (block_number)
);

CREATE INDEX idx_transactions_block_number ON transactions (block_number);
CREATE INDEX idx_transactions_from ON transactions (from_address);
CREATE INDEX idx_transactions_to ON transactions (to_address);
CREATE INDEX idx_transactions_block_index ON transactions (block_number, transaction_index);

-- ============================================================
-- 3. RECEIPTS
--    1:1 with transactions; separated for normalization.
-- ============================================================
CREATE TABLE receipts (
    transaction_hash    CHAR(66)        NOT NULL,
    block_number        BIGINT          NOT NULL,
    transaction_index   INT             NOT NULL,
    cumulative_gas_used BIGINT          NOT NULL,
    gas_used            BIGINT          NOT NULL,
    effective_gas_price NUMERIC(38,0)   NOT NULL DEFAULT 0,
    contract_address    CHAR(42)        NULL,       -- non-NULL only for contract creation txns
    status              SMALLINT        NOT NULL,   -- 1 = success, 0 = failure
    root                CHAR(66)        NULL,       -- pre-Byzantium state root (legacy)
    logs_bloom          VARCHAR(514)    NOT NULL,

    CONSTRAINT pk_receipts PRIMARY KEY (transaction_hash),
    CONSTRAINT fk_receipts_transaction FOREIGN KEY (transaction_hash)
        REFERENCES transactions (transaction_hash),
    CONSTRAINT fk_receipts_block FOREIGN KEY (block_number)
        REFERENCES blocks (block_number)
);

CREATE INDEX idx_receipts_block_number ON receipts (block_number);
CREATE INDEX idx_receipts_contract ON receipts (contract_address) WHERE contract_address IS NOT NULL;
CREATE INDEX idx_receipts_status ON receipts (status);

-- ============================================================
-- 4. LOGS (Event Logs)
--    One transaction can emit many logs.
-- ============================================================
CREATE TABLE logs (
    block_number        BIGINT          NOT NULL,
    transaction_hash    CHAR(66)        NOT NULL,
    transaction_index   INT             NOT NULL,
    log_index           BIGINT          NOT NULL,
    address             CHAR(42)        NOT NULL,   -- contract that emitted the event
    data                TEXT            NOT NULL DEFAULT '0x',
    topic0              CHAR(66)        NULL,       -- event signature hash
    topic1              CHAR(66)        NULL,       -- indexed param 1
    topic2              CHAR(66)        NULL,       -- indexed param 2
    topic3              CHAR(66)        NULL,       -- indexed param 3
    removed             BOOLEAN         NOT NULL DEFAULT FALSE,

    CONSTRAINT pk_logs PRIMARY KEY (block_number, log_index),
    CONSTRAINT fk_logs_transaction FOREIGN KEY (transaction_hash)
        REFERENCES transactions (transaction_hash),
    CONSTRAINT fk_logs_block FOREIGN KEY (block_number)
        REFERENCES blocks (block_number)
);

CREATE INDEX idx_logs_transaction_hash ON logs (transaction_hash);
CREATE INDEX idx_logs_address ON logs (address);
CREATE INDEX idx_logs_topic0 ON logs (topic0) WHERE topic0 IS NOT NULL;
CREATE INDEX idx_logs_address_topic0 ON logs (address, topic0);

-- ============================================================
-- 5. TOKEN TRANSFERS — ERC-20
--    Decoded from Transfer(address,address,uint256) logs.
-- ============================================================
CREATE TABLE token_transfers_erc20 (
    block_number        BIGINT          NOT NULL,
    transaction_hash    CHAR(66)        NOT NULL,
    log_index           BIGINT          NOT NULL,
    token_address       CHAR(42)        NOT NULL,   -- ERC-20 contract address
    from_address        CHAR(42)        NOT NULL,
    to_address          CHAR(42)        NOT NULL,
    value               NUMERIC(78,0)   NOT NULL DEFAULT 0,  -- token amount in smallest unit

    CONSTRAINT pk_erc20_transfers PRIMARY KEY (block_number, log_index),
    CONSTRAINT fk_erc20_transaction FOREIGN KEY (transaction_hash)
        REFERENCES transactions (transaction_hash),
    CONSTRAINT fk_erc20_block FOREIGN KEY (block_number)
        REFERENCES blocks (block_number),
    CONSTRAINT fk_erc20_log FOREIGN KEY (block_number, log_index)
        REFERENCES logs (block_number, log_index)
);

CREATE INDEX idx_erc20_token ON token_transfers_erc20 (token_address);
CREATE INDEX idx_erc20_from ON token_transfers_erc20 (from_address);
CREATE INDEX idx_erc20_to ON token_transfers_erc20 (to_address);
CREATE INDEX idx_erc20_block ON token_transfers_erc20 (block_number);

-- ============================================================
-- 6. TOKEN TRANSFERS — ERC-721 (NFTs)
--    Decoded from Transfer(address,address,uint256) logs
--    where the third indexed param is the tokenId.
-- ============================================================
CREATE TABLE token_transfers_erc721 (
    block_number        BIGINT          NOT NULL,
    transaction_hash    CHAR(66)        NOT NULL,
    log_index           BIGINT          NOT NULL,
    token_address       CHAR(42)        NOT NULL,   -- ERC-721 contract address
    from_address        CHAR(42)        NOT NULL,
    to_address          CHAR(42)        NOT NULL,
    token_id            NUMERIC(78,0)   NOT NULL,   -- uint256 NFT token ID

    CONSTRAINT pk_erc721_transfers PRIMARY KEY (block_number, log_index),
    CONSTRAINT fk_erc721_transaction FOREIGN KEY (transaction_hash)
        REFERENCES transactions (transaction_hash),
    CONSTRAINT fk_erc721_block FOREIGN KEY (block_number)
        REFERENCES blocks (block_number),
    CONSTRAINT fk_erc721_log FOREIGN KEY (block_number, log_index)
        REFERENCES logs (block_number, log_index)
);

CREATE INDEX idx_erc721_token ON token_transfers_erc721 (token_address);
CREATE INDEX idx_erc721_from ON token_transfers_erc721 (from_address);
CREATE INDEX idx_erc721_to ON token_transfers_erc721 (to_address);
CREATE INDEX idx_erc721_token_id ON token_transfers_erc721 (token_address, token_id);
CREATE INDEX idx_erc721_block ON token_transfers_erc721 (block_number);

-- ============================================================
-- 7. TRACES (Internal Calls)
--    Captures internal message calls, contract creations,
--    and self-destructs via debug_traceBlock / trace_block.
-- ============================================================
CREATE TABLE traces (
    block_number        BIGINT          NOT NULL,
    transaction_hash    CHAR(66)        NULL,       -- NULL for block-level rewards
    transaction_index   INT             NULL,
    trace_address       TEXT            NOT NULL DEFAULT '',  -- e.g. '0,1,2' for nested calls
    trace_type          VARCHAR(16)     NOT NULL,   -- 'call', 'create', 'suicide', 'reward'
    call_type           VARCHAR(16)     NULL,       -- 'call', 'callcode', 'delegatecall', 'staticcall'
    from_address        CHAR(42)        NULL,
    to_address          CHAR(42)        NULL,
    value               NUMERIC(78,0)   NOT NULL DEFAULT 0,
    gas                 BIGINT          NULL,
    gas_used            BIGINT          NULL,
    input               TEXT            NULL,
    output              TEXT            NULL,
    error               TEXT            NULL,       -- non-NULL if the internal call reverted
    subtraces           INT             NOT NULL DEFAULT 0,

    CONSTRAINT pk_traces PRIMARY KEY (block_number, transaction_index, trace_address),
    CONSTRAINT fk_traces_block FOREIGN KEY (block_number)
        REFERENCES blocks (block_number)
);

CREATE INDEX idx_traces_transaction_hash ON traces (transaction_hash);
CREATE INDEX idx_traces_from ON traces (from_address);
CREATE INDEX idx_traces_to ON traces (to_address);
CREATE INDEX idx_traces_type ON traces (trace_type);
CREATE INDEX idx_traces_block ON traces (block_number);
CREATE INDEX idx_traces_call_type ON traces (call_type) WHERE call_type IS NOT NULL;

-- ============================================================
-- NOTES FOR PRODUCTION / LARGE-SCALE ANALYTICS
-- ============================================================
-- 1. PARTITIONING: For billions of rows, partition the larger
--    tables (transactions, receipts, logs, token_transfers_*,
--    traces) by block_number ranges using PostgreSQL declarative
--    partitioning (PARTITION BY RANGE (block_number)).
--
-- 2. FOREIGN KEYS: The foreign key constraints above ensure
--    referential integrity. For maximum bulk-insert throughput,
--    consider deferring or dropping FKs during initial backfill
--    and re-adding them afterwards.
--
-- 3. ADDRESSES: All addresses and hashes are stored as
--    lowercased 0x-prefixed hex strings. Enforce this in
--    your ingestion pipeline for consistent querying.
--
-- 4. NUMERIC PRECISION: Ethereum uint256 values can be up to
--    78 decimal digits. NUMERIC(78,0) accommodates the full
--    range without overflow.
-- ============================================================
