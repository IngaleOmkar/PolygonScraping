-- ============================================================
-- POLYGON INDEXING SCHEMA — partitions cover analysis window
-- ============================================================
-- NOTE: Database 'polygon' is created automatically by Docker/PostgreSQL
-- This script runs within the 'polygon' database context

-- -----------------------------
-- BLOCKS (not partitioned — smaller table, random access)
-- -----------------------------
CREATE TABLE blocks (
    block_number      BIGINT PRIMARY KEY,
    block_hash        VARCHAR(66) NOT NULL,
    parent_hash       VARCHAR(66) NOT NULL,
    block_timestamp   TIMESTAMPTZ NOT NULL,
    gas_limit         BIGINT,
    gas_used          BIGINT,
    base_fee_per_gas  NUMERIC(38,0),
    ingested_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_blocks_timestamp ON blocks (block_timestamp);

-- -----------------------------
-- TRANSACTIONS
-- -----------------------------
CREATE TABLE transactions (
    block_number                BIGINT NOT NULL,
    transaction_hash            VARCHAR(66) NOT NULL,
    transaction_index           INT NOT NULL,
    from_address                VARCHAR(42) NOT NULL,
    to_address                  VARCHAR(42),
    value                       NUMERIC(78,0) NOT NULL,
    gas                         BIGINT NOT NULL,
    gas_price                   NUMERIC(38,0),
    max_fee_per_gas             NUMERIC(38,0),
    max_priority_fee_per_gas    NUMERIC(38,0),
    nonce                       BIGINT NOT NULL,
    transaction_type            SMALLINT,
    success                     BOOLEAN,
    ingested_at                 TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (block_number, transaction_hash)
) PARTITION BY RANGE (block_number);

CREATE UNIQUE INDEX uq_tx_hash_block ON transactions (transaction_hash, block_number);
CREATE INDEX idx_tx_from   ON transactions (from_address);
CREATE INDEX idx_tx_to     ON transactions (to_address);

-- Partitions in 10 M-block increments; DEFAULT catches anything outside
CREATE TABLE transactions_p0   PARTITION OF transactions FOR VALUES FROM (0)        TO (10000000);
CREATE TABLE transactions_p10  PARTITION OF transactions FOR VALUES FROM (10000000) TO (20000000);
CREATE TABLE transactions_p20  PARTITION OF transactions FOR VALUES FROM (20000000) TO (30000000);
CREATE TABLE transactions_p30  PARTITION OF transactions FOR VALUES FROM (30000000) TO (40000000);
CREATE TABLE transactions_p40  PARTITION OF transactions FOR VALUES FROM (40000000) TO (50000000);
CREATE TABLE transactions_p50  PARTITION OF transactions FOR VALUES FROM (50000000) TO (60000000);  -- ← analysis window lives here
CREATE TABLE transactions_p60  PARTITION OF transactions FOR VALUES FROM (60000000) TO (70000000);
CREATE TABLE transactions_def  PARTITION OF transactions DEFAULT;

-- -----------------------------
-- LOGS
-- -----------------------------
CREATE TABLE logs (
    block_number        BIGINT NOT NULL,
    transaction_hash    VARCHAR(66) NOT NULL,
    log_index           INT NOT NULL,
    address             VARCHAR(42) NOT NULL,
    topic0              VARCHAR(66),
    topic1              VARCHAR(66),
    topic2              VARCHAR(66),
    topic3              VARCHAR(66),
    data                TEXT NOT NULL,
    ingested_at         TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (block_number, transaction_hash, log_index)
) PARTITION BY RANGE (block_number);

CREATE INDEX idx_logs_address ON logs (address);
CREATE INDEX idx_logs_topic0  ON logs (topic0);

CREATE TABLE logs_p0   PARTITION OF logs FOR VALUES FROM (0)        TO (10000000);
CREATE TABLE logs_p10  PARTITION OF logs FOR VALUES FROM (10000000) TO (20000000);
CREATE TABLE logs_p20  PARTITION OF logs FOR VALUES FROM (20000000) TO (30000000);
CREATE TABLE logs_p30  PARTITION OF logs FOR VALUES FROM (30000000) TO (40000000);
CREATE TABLE logs_p40  PARTITION OF logs FOR VALUES FROM (40000000) TO (50000000);
CREATE TABLE logs_p50  PARTITION OF logs FOR VALUES FROM (50000000) TO (60000000);
CREATE TABLE logs_p60  PARTITION OF logs FOR VALUES FROM (60000000) TO (70000000);
CREATE TABLE logs_def  PARTITION OF logs DEFAULT;

-- -----------------------------
-- RECEIPTS
-- -----------------------------
CREATE TABLE receipts (
    block_number        BIGINT NOT NULL,
    transaction_hash    VARCHAR(66) NOT NULL,
    gas_used            BIGINT NOT NULL,
    effective_gas_price NUMERIC(38,0),
    contract_address    VARCHAR(42),
    status              SMALLINT NOT NULL,
    ingested_at         TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (block_number, transaction_hash)
) PARTITION BY RANGE (block_number);

CREATE TABLE receipts_p0   PARTITION OF receipts FOR VALUES FROM (0)        TO (10000000);
CREATE TABLE receipts_p10  PARTITION OF receipts FOR VALUES FROM (10000000) TO (20000000);
CREATE TABLE receipts_p20  PARTITION OF receipts FOR VALUES FROM (20000000) TO (30000000);
CREATE TABLE receipts_p30  PARTITION OF receipts FOR VALUES FROM (30000000) TO (40000000);
CREATE TABLE receipts_p40  PARTITION OF receipts FOR VALUES FROM (40000000) TO (50000000);
CREATE TABLE receipts_p50  PARTITION OF receipts FOR VALUES FROM (50000000) TO (60000000);
CREATE TABLE receipts_p60  PARTITION OF receipts FOR VALUES FROM (60000000) TO (70000000);
CREATE TABLE receipts_def  PARTITION OF receipts DEFAULT;

-- -----------------------------
-- ERC-20 TOKEN TRANSFERS
-- -----------------------------
CREATE TABLE token_transfers_erc20 (
    block_number        BIGINT NOT NULL,
    transaction_hash    VARCHAR(66) NOT NULL,
    log_index           INT NOT NULL,
    token_address       VARCHAR(42) NOT NULL,
    from_address        VARCHAR(42) NOT NULL,
    to_address          VARCHAR(42) NOT NULL,
    value               NUMERIC(78,0) NOT NULL,
    PRIMARY KEY (block_number, transaction_hash, log_index)
) PARTITION BY RANGE (block_number);

CREATE INDEX idx_erc20_from  ON token_transfers_erc20 (from_address);
CREATE INDEX idx_erc20_to    ON token_transfers_erc20 (to_address);
CREATE INDEX idx_erc20_token ON token_transfers_erc20 (token_address);

CREATE TABLE erc20_p0   PARTITION OF token_transfers_erc20 FOR VALUES FROM (0)        TO (10000000);
CREATE TABLE erc20_p10  PARTITION OF token_transfers_erc20 FOR VALUES FROM (10000000) TO (20000000);
CREATE TABLE erc20_p20  PARTITION OF token_transfers_erc20 FOR VALUES FROM (20000000) TO (30000000);
CREATE TABLE erc20_p30  PARTITION OF token_transfers_erc20 FOR VALUES FROM (30000000) TO (40000000);
CREATE TABLE erc20_p40  PARTITION OF token_transfers_erc20 FOR VALUES FROM (40000000) TO (50000000);
CREATE TABLE erc20_p50  PARTITION OF token_transfers_erc20 FOR VALUES FROM (50000000) TO (60000000);
CREATE TABLE erc20_p60  PARTITION OF token_transfers_erc20 FOR VALUES FROM (60000000) TO (70000000);
CREATE TABLE erc20_def  PARTITION OF token_transfers_erc20 DEFAULT;

-- -----------------------------
-- ERC-721 TOKEN TRANSFERS
-- -----------------------------
CREATE TABLE token_transfers_erc721 (
    block_number        BIGINT NOT NULL,
    transaction_hash    VARCHAR(66) NOT NULL,
    log_index           INT NOT NULL,
    token_address       VARCHAR(42) NOT NULL,
    from_address        VARCHAR(42) NOT NULL,
    to_address          VARCHAR(42) NOT NULL,
    token_id            NUMERIC(78,0) NOT NULL,
    PRIMARY KEY (block_number, transaction_hash, log_index)
) PARTITION BY RANGE (block_number);

CREATE INDEX idx_erc721_from  ON token_transfers_erc721 (from_address);
CREATE INDEX idx_erc721_to    ON token_transfers_erc721 (to_address);
CREATE INDEX idx_erc721_token ON token_transfers_erc721 (token_address);

CREATE TABLE erc721_p0   PARTITION OF token_transfers_erc721 FOR VALUES FROM (0)        TO (10000000);
CREATE TABLE erc721_p10  PARTITION OF token_transfers_erc721 FOR VALUES FROM (10000000) TO (20000000);
CREATE TABLE erc721_p20  PARTITION OF token_transfers_erc721 FOR VALUES FROM (20000000) TO (30000000);
CREATE TABLE erc721_p30  PARTITION OF token_transfers_erc721 FOR VALUES FROM (30000000) TO (40000000);
CREATE TABLE erc721_p40  PARTITION OF token_transfers_erc721 FOR VALUES FROM (40000000) TO (50000000);
CREATE TABLE erc721_p50  PARTITION OF token_transfers_erc721 FOR VALUES FROM (50000000) TO (60000000);
CREATE TABLE erc721_p60  PARTITION OF token_transfers_erc721 FOR VALUES FROM (60000000) TO (70000000);
CREATE TABLE erc721_def  PARTITION OF token_transfers_erc721 DEFAULT;

-- -----------------------------
-- TRACES (internal calls)
-- NOTE: PK uses transaction_hash to ensure uniqueness across txs in same block.
-- -----------------------------
CREATE TABLE traces (
    block_number        BIGINT NOT NULL,
    transaction_hash    VARCHAR(66) NOT NULL,   -- added to PK vs original design
    trace_address       TEXT NOT NULL,
    trace_type          VARCHAR(16),
    call_type           VARCHAR(16),
    from_address        VARCHAR(42),
    to_address          VARCHAR(42),
    value               NUMERIC(78,0),
    gas                 BIGINT,
    gas_used            BIGINT,
    error               TEXT,
    PRIMARY KEY (block_number, transaction_hash, trace_address)
) PARTITION BY RANGE (block_number);

CREATE TABLE traces_p0   PARTITION OF traces FOR VALUES FROM (0)        TO (10000000);
CREATE TABLE traces_p10  PARTITION OF traces FOR VALUES FROM (10000000) TO (20000000);
CREATE TABLE traces_p20  PARTITION OF traces FOR VALUES FROM (20000000) TO (30000000);
CREATE TABLE traces_p30  PARTITION OF traces FOR VALUES FROM (30000000) TO (40000000);
CREATE TABLE traces_p40  PARTITION OF traces FOR VALUES FROM (40000000) TO (50000000);
CREATE TABLE traces_p50  PARTITION OF traces FOR VALUES FROM (50000000) TO (60000000);
CREATE TABLE traces_p60  PARTITION OF traces FOR VALUES FROM (60000000) TO (70000000);
CREATE TABLE traces_def  PARTITION OF traces DEFAULT;

-- -----------------------------
-- ADDRESS INTERACTIONS (primary analysis dataset)
-- -----------------------------
CREATE TABLE address_interactions (
    block_number        BIGINT NOT NULL,
    transaction_hash    VARCHAR(66) NOT NULL,
    from_address        VARCHAR(42) NOT NULL,
    to_address          VARCHAR(42) NOT NULL,
    value               NUMERIC(78,0),
    interaction_type    SMALLINT,   -- 0=native tx, 1=erc20, 2=erc721
    PRIMARY KEY (block_number, transaction_hash, from_address, to_address)
) PARTITION BY RANGE (block_number);

CREATE INDEX idx_ai_from ON address_interactions (from_address);
CREATE INDEX idx_ai_to   ON address_interactions (to_address);

CREATE TABLE ai_p0   PARTITION OF address_interactions FOR VALUES FROM (0)        TO (10000000);
CREATE TABLE ai_p10  PARTITION OF address_interactions FOR VALUES FROM (10000000) TO (20000000);
CREATE TABLE ai_p20  PARTITION OF address_interactions FOR VALUES FROM (20000000) TO (30000000);
CREATE TABLE ai_p30  PARTITION OF address_interactions FOR VALUES FROM (30000000) TO (40000000);
CREATE TABLE ai_p40  PARTITION OF address_interactions FOR VALUES FROM (40000000) TO (50000000);
CREATE TABLE ai_p50  PARTITION OF address_interactions FOR VALUES FROM (50000000) TO (60000000);
CREATE TABLE ai_p60  PARTITION OF address_interactions FOR VALUES FROM (60000000) TO (70000000);
CREATE TABLE ai_def  PARTITION OF address_interactions DEFAULT;