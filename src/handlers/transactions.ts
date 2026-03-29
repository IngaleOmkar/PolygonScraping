import type { TransactionRow, ReceiptRow } from '../types.js'

function toBigInt(value: any): bigint {
	if (value === null || value === undefined) return BigInt(0)
	if (typeof value === 'bigint') return value
	if (typeof value === 'number') return BigInt(value)
	if (typeof value === 'string') {
		if (value.startsWith('0x')) return BigInt(value)
		try { return BigInt(value) } catch { return BigInt(Number(value)) }
	}
	return BigInt(0)
}

export function handleTransaction(tx: any, receipt?: any): { txRow: TransactionRow, receiptRow?: ReceiptRow } {
	const tr: TransactionRow = {
		transaction_hash: tx.hash ?? tx.transactionHash ?? '',
		block_number: toBigInt(tx.blockNumber ?? tx.block_number ?? tx.block?.number),
		transaction_index: (tx.transactionIndex ?? tx.index ?? tx.txIndex ?? 0) as number,
		from_address: tx.from ?? tx.fromAddress ?? tx.sender ?? '0x' + '0'.repeat(40),
		to_address: tx.to ?? tx.toAddress ?? null,
		value: toBigInt(tx.value ?? tx.valueHex ?? 0),
		gas: toBigInt(tx.gas ?? tx.gasLimit ?? 0),
		gas_price: toBigInt(tx.gasPrice ?? tx.gas_price ?? tx.effectiveGasPrice ?? 0),
		max_fee_per_gas: tx.maxFeePerGas ? toBigInt(tx.maxFeePerGas) : null,
		max_priority_fee_per_gas: tx.maxPriorityFeePerGas ? toBigInt(tx.maxPriorityFeePerGas) : null,
		input: tx.input ?? tx.data ?? '',
		nonce: toBigInt(tx.nonce ?? 0),
		transaction_type: Number(tx.type ?? tx.transactionType ?? 0),
	}

	let receiptRow: ReceiptRow | undefined
	if (receipt) {
		receiptRow = {
			transaction_hash: receipt.transactionHash ?? tr.transaction_hash,
			block_number: toBigInt(receipt.blockNumber ?? receipt.block_number ?? tr.block_number),
			transaction_index: receipt.transactionIndex ?? tr.transaction_index,
			cumulative_gas_used: toBigInt(receipt.cumulativeGasUsed ?? receipt.cumulative_gas_used ?? 0),
			gas_used: toBigInt(receipt.gasUsed ?? receipt.gas_used ?? 0),
			effective_gas_price: receipt.effectiveGasPrice ? toBigInt(receipt.effectiveGasPrice) : null,
			contract_address: receipt.contractAddress ?? receipt.contract_address ?? null,
			status: Number(receipt.status ?? 0),
			root: receipt.root ?? null,
			logs_bloom: receipt.logsBloom ?? receipt.logs_bloom ?? '',
		}
	}

	return { txRow: tr, receiptRow }
}

export default handleTransaction

