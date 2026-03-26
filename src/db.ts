import pg from 'pg'
import { config } from './config.js'
import type {
  BlockRow, TransactionRow, ReceiptRow, LogRow,
  Erc20TransferRow, Erc721TransferRow, TraceRow
} from './types.js'

const { Pool } = pg

export const pool = new Pool({ connectionString: config.databaseUrl })

// ─── FK helpers ───────────────────────────────────────────────────────────────

export async function dropForeignKeys(): Promise<void> {
  console.log('Dropping foreign key constraints for bulk insert...')
  await pool.query(`
    ALTER TABLE transactions   DROP CONSTRAINT IF EXISTS fk_transactions_block;
    ALTER TABLE receipts       DROP CONSTRAINT IF EXISTS fk_receipts_transaction;
    ALTER TABLE receipts       DROP CONSTRAINT IF EXISTS fk_receipts_block;
    ALTER TABLE logs           DROP CONSTRAINT IF EXISTS fk_logs_transaction;
    ALTER TABLE logs           DROP CONSTRAINT IF EXISTS fk_logs_block;
    ALTER TABLE token_transfers_erc20  DROP CONSTRAINT IF EXISTS fk_erc20_transaction;
    ALTER TABLE token_transfers_erc20  DROP CONSTRAINT IF EXISTS fk_erc20_block;
    ALTER TABLE token_transfers_erc20  DROP CONSTRAINT IF EXISTS fk_erc20_log;
    ALTER TABLE token_transfers_erc721 DROP CONSTRAINT IF EXISTS fk_erc721_transaction;
    ALTER TABLE token_transfers_erc721 DROP CONSTRAINT IF EXISTS fk_erc721_block;
    ALTER TABLE token_transfers_erc721 DROP CONSTRAINT IF EXISTS fk_erc721_log;
    ALTER TABLE traces         DROP CONSTRAINT IF EXISTS fk_traces_block;
  `)
  console.log('Foreign keys dropped.')
}

export async function restoreForeignKeys(): Promise<void> {
  console.log('Restoring foreign key constraints...')
  await pool.query(`
    ALTER TABLE transactions ADD CONSTRAINT fk_transactions_block
      FOREIGN KEY (block_number) REFERENCES blocks (block_number);
    ALTER TABLE receipts ADD CONSTRAINT fk_receipts_transaction
      FOREIGN KEY (transaction_hash) REFERENCES transactions (transaction_hash);
    ALTER TABLE receipts ADD CONSTRAINT fk_receipts_block
      FOREIGN KEY (block_number) REFERENCES blocks (block_number);
    ALTER TABLE logs ADD CONSTRAINT fk_logs_transaction
      FOREIGN KEY (transaction_hash) REFERENCES transactions (transaction_hash);
    ALTER TABLE logs ADD CONSTRAINT fk_logs_block
      FOREIGN KEY (block_number) REFERENCES blocks (block_number);
    ALTER TABLE token_transfers_erc20 ADD CONSTRAINT fk_erc20_transaction
      FOREIGN KEY (transaction_hash) REFERENCES transactions (transaction_hash);
    ALTER TABLE token_transfers_erc20 ADD CONSTRAINT fk_erc20_block
      FOREIGN KEY (block_number) REFERENCES blocks (block_number);
    ALTER TABLE token_transfers_erc20 ADD CONSTRAINT fk_erc20_log
      FOREIGN KEY (block_number, log_index) REFERENCES logs (block_number, log_index);
    ALTER TABLE token_transfers_erc721 ADD CONSTRAINT fk_erc721_transaction
      FOREIGN KEY (transaction_hash) REFERENCES transactions (transaction_hash);
    ALTER TABLE token_transfers_erc721 ADD CONSTRAINT fk_erc721_block
      FOREIGN KEY (block_number) REFERENCES blocks (block_number);
    ALTER TABLE token_transfers_erc721 ADD CONSTRAINT fk_erc721_log
      FOREIGN KEY (block_number, log_index) REFERENCES logs (block_number, log_index);
    ALTER TABLE traces ADD CONSTRAINT fk_traces_block
      FOREIGN KEY (block_number) REFERENCES blocks (block_number);
  `)
  console.log('Foreign keys restored.')
}

// ─── Generic bulk insert using unnest ─────────────────────────────────────────
// Sends one query per table per batch — much faster than row-by-row inserts

export async function insertBlocks(rows: BlockRow[]): Promise<void> {
  if (!rows.length) return
  await pool.query(`
    INSERT INTO blocks (
      block_number, block_hash, parent_hash, nonce, sha3_uncles, logs_bloom,
      transactions_root, state_root, receipts_root, miner, proposer,
      difficulty, total_difficulty, size, extra_data, gas_limit, gas_used,
      base_fee_per_gas, block_timestamp
    )
    SELECT * FROM unnest(
      $1::bigint[], $2::char(66)[], $3::char(66)[], $4::varchar[], $5::char(66)[],
      $6::varchar[], $7::char(66)[], $8::char(66)[], $9::char(66)[], $10::char(42)[],
      $11::char(42)[], $12::numeric[], $13::numeric[], $14::bigint[], $15::text[],
      $16::bigint[], $17::bigint[], $18::numeric[], $19::timestamptz[]
    )
    ON CONFLICT DO NOTHING
  `, [
    rows.map(r => r.block_number),
    rows.map(r => r.block_hash),
    rows.map(r => r.parent_hash),
    rows.map(r => r.nonce),
    rows.map(r => r.sha3_uncles),
    rows.map(r => r.logs_bloom),
    rows.map(r => r.transactions_root),
    rows.map(r => r.state_root),
    rows.map(r => r.receipts_root),
    rows.map(r => r.miner),
    rows.map(r => r.proposer),
    rows.map(r => r.difficulty?.toString() ?? null),
    rows.map(r => r.total_difficulty?.toString() ?? null),
    rows.map(r => r.size),
    rows.map(r => r.extra_data),
    rows.map(r => r.gas_limit),
    rows.map(r => r.gas_used),
    rows.map(r => r.base_fee_per_gas?.toString() ?? null),
    rows.map(r => r.block_timestamp),
  ])
}

export async function insertTransactions(rows: TransactionRow[]): Promise<void> {
  if (!rows.length) return
  await pool.query(`
    INSERT INTO transactions (
      transaction_hash, block_number, transaction_index, from_address, to_address,
      value, gas, gas_price, max_fee_per_gas, max_priority_fee_per_gas,
      input, nonce, transaction_type
    )
    SELECT * FROM unnest(
      $1::char(66)[], $2::bigint[], $3::int[], $4::char(42)[], $5::char(42)[],
      $6::numeric[], $7::bigint[], $8::numeric[], $9::numeric[], $10::numeric[],
      $11::text[], $12::bigint[], $13::smallint[]
    )
    ON CONFLICT DO NOTHING
  `, [
    rows.map(r => r.transaction_hash),
    rows.map(r => r.block_number),
    rows.map(r => r.transaction_index),
    rows.map(r => r.from_address),
    rows.map(r => r.to_address),
    rows.map(r => r.value.toString()),
    rows.map(r => r.gas),
    rows.map(r => r.gas_price.toString()),
    rows.map(r => r.max_fee_per_gas?.toString() ?? null),
    rows.map(r => r.max_priority_fee_per_gas?.toString() ?? null),
    rows.map(r => r.input),
    rows.map(r => r.nonce),
    rows.map(r => r.transaction_type),
  ])
}

export async function insertReceipts(rows: ReceiptRow[]): Promise<void> {
  if (!rows.length) return
  await pool.query(`
    INSERT INTO receipts (
      transaction_hash, block_number, transaction_index, cumulative_gas_used,
      gas_used, effective_gas_price, contract_address, status, root, logs_bloom
    )
    SELECT * FROM unnest(
      $1::char(66)[], $2::bigint[], $3::int[], $4::bigint[],
      $5::bigint[], $6::numeric[], $7::char(42)[], $8::smallint[],
      $9::char(66)[], $10::varchar[]
    )
    ON CONFLICT DO NOTHING
  `, [
    rows.map(r => r.transaction_hash),
    rows.map(r => r.block_number),
    rows.map(r => r.transaction_index),
    rows.map(r => r.cumulative_gas_used),
    rows.map(r => r.gas_used),
    rows.map(r => r.effective_gas_price?.toString() ?? null),
    rows.map(r => r.contract_address),
    rows.map(r => r.status),
    rows.map(r => r.root),
    rows.map(r => r.logs_bloom),
  ])
}

export async function insertLogs(rows: LogRow[]): Promise<void> {
  if (!rows.length) return
  await pool.query(`
    INSERT INTO logs (
      block_number, transaction_hash, transaction_index, log_index,
      address, data, topic0, topic1, topic2, topic3, removed
    )
    SELECT * FROM unnest(
      $1::bigint[], $2::char(66)[], $3::int[], $4::bigint[],
      $5::char(42)[], $6::text[], $7::char(66)[], $8::char(66)[],
      $9::char(66)[], $10::char(66)[], $11::boolean[]
    )
    ON CONFLICT DO NOTHING
  `, [
    rows.map(r => r.block_number),
    rows.map(r => r.transaction_hash),
    rows.map(r => r.transaction_index),
    rows.map(r => r.log_index),
    rows.map(r => r.address),
    rows.map(r => r.data),
    rows.map(r => r.topic0),
    rows.map(r => r.topic1),
    rows.map(r => r.topic2),
    rows.map(r => r.topic3),
    rows.map(r => r.removed),
  ])
}

export async function insertErc20Transfers(rows: Erc20TransferRow[]): Promise<void> {
  if (!rows.length) return
  await pool.query(`
    INSERT INTO token_transfers_erc20 (
      block_number, transaction_hash, log_index,
      token_address, from_address, to_address, value
    )
    SELECT * FROM unnest(
      $1::bigint[], $2::char(66)[], $3::bigint[],
      $4::char(42)[], $5::char(42)[], $6::char(42)[], $7::numeric[]
    )
    ON CONFLICT DO NOTHING
  `, [
    rows.map(r => r.block_number),
    rows.map(r => r.transaction_hash),
    rows.map(r => r.log_index),
    rows.map(r => r.token_address),
    rows.map(r => r.from_address),
    rows.map(r => r.to_address),
    rows.map(r => r.value.toString()),
  ])
}

export async function insertErc721Transfers(rows: Erc721TransferRow[]): Promise<void> {
  if (!rows.length) return
  await pool.query(`
    INSERT INTO token_transfers_erc721 (
      block_number, transaction_hash, log_index,
      token_address, from_address, to_address, token_id
    )
    SELECT * FROM unnest(
      $1::bigint[], $2::char(66)[], $3::bigint[],
      $4::char(42)[], $5::char(42)[], $6::char(42)[], $7::numeric[]
    )
    ON CONFLICT DO NOTHING
  `, [
    rows.map(r => r.block_number),
    rows.map(r => r.transaction_hash),
    rows.map(r => r.log_index),
    rows.map(r => r.token_address),
    rows.map(r => r.from_address),
    rows.map(r => r.to_address),
    rows.map(r => r.token_id.toString()),
  ])
}

export async function insertTraces(rows: TraceRow[]): Promise<void> {
  if (!rows.length) return
  await pool.query(`
    INSERT INTO traces (
      block_number, transaction_hash, transaction_index, trace_address,
      trace_type, call_type, from_address, to_address, value,
      gas, gas_used, input, output, error, subtraces
    )
    SELECT * FROM unnest(
      $1::bigint[], $2::char(66)[], $3::int[], $4::text[],
      $5::varchar[], $6::varchar[], $7::char(42)[], $8::char(42)[], $9::numeric[],
      $10::bigint[], $11::bigint[], $12::text[], $13::text[], $14::text[], $15::int[]
    )
    ON CONFLICT DO NOTHING
  `, [
    rows.map(r => r.block_number),
    rows.map(r => r.transaction_hash),
    rows.map(r => r.transaction_index),
    rows.map(r => r.trace_address),
    rows.map(r => r.trace_type),
    rows.map(r => r.call_type),
    rows.map(r => r.from_address),
    rows.map(r => r.to_address),
    rows.map(r => r.value.toString()),
    rows.map(r => r.gas),
    rows.map(r => r.gas_used),
    rows.map(r => r.input),
    rows.map(r => r.output),
    rows.map(r => r.error),
    rows.map(r => r.subtraces),
  ])
}