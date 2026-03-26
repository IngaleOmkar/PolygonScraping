export interface BlockRow {
  block_number: bigint
  block_hash: string
  parent_hash: string
  nonce: string
  sha3_uncles: string
  logs_bloom: string
  transactions_root: string
  state_root: string
  receipts_root: string
  miner: string
  proposer: string | null
  difficulty: bigint | null
  total_difficulty: bigint | null
  size: bigint
  extra_data: string
  gas_limit: bigint
  gas_used: bigint
  base_fee_per_gas: bigint | null
  block_timestamp: Date
}

export interface TransactionRow {
  transaction_hash: string
  block_number: bigint
  transaction_index: number
  from_address: string
  to_address: string | null
  value: bigint
  gas: bigint
  gas_price: bigint
  max_fee_per_gas: bigint | null
  max_priority_fee_per_gas: bigint | null
  input: string
  nonce: bigint
  transaction_type: number
}

export interface ReceiptRow {
  transaction_hash: string
  block_number: bigint
  transaction_index: number
  cumulative_gas_used: bigint
  gas_used: bigint
  effective_gas_price: bigint | null
  contract_address: string | null
  status: number
  root: string | null
  logs_bloom: string
}

export interface LogRow {
  block_number: bigint
  transaction_hash: string
  transaction_index: number
  log_index: bigint
  address: string
  data: string
  topic0: string | null
  topic1: string | null
  topic2: string | null
  topic3: string | null
  removed: boolean
}

export interface Erc20TransferRow {
  block_number: bigint
  transaction_hash: string
  log_index: bigint
  token_address: string
  from_address: string
  to_address: string
  value: bigint
}

export interface Erc721TransferRow {
  block_number: bigint
  transaction_hash: string
  log_index: bigint
  token_address: string
  from_address: string
  to_address: string
  token_id: bigint
}

export interface TraceRow {
  block_number: bigint
  transaction_hash: string | null
  transaction_index: number | null
  trace_address: string
  trace_type: string
  call_type: string | null
  from_address: string | null
  to_address: string | null
  value: bigint
  gas: bigint | null
  gas_used: bigint | null
  input: string | null
  output: string | null
  error: string | null
  subtraces: number
}