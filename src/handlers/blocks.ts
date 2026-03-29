import type { BlockRow } from '../types.js'

function toBigInt(value: any): bigint {
	if (value === null || value === undefined) return BigInt(0)
	if (typeof value === 'bigint') return value
	if (typeof value === 'number') return BigInt(value)
	if (typeof value === 'string') {
		// hex or decimal
		if (value.startsWith('0x')) return BigInt(value)
		try { return BigInt(value) } catch { return BigInt(Number(value)) }
	}
	return BigInt(0)
}

function toTimestamp(dateLike: any): Date {
	if (!dateLike) return new Date(0)
	// Subquery often returns seconds as string/number or ISO
	if (typeof dateLike === 'string') {
		if (/^\d+$/.test(dateLike)) {
			// seconds or ms
			return new Date(dateLike.length === 10 ? Number(dateLike) * 1000 : Number(dateLike))
		}
		const d = new Date(dateLike)
		if (!isNaN(d.getTime())) return d
	}
	if (typeof dateLike === 'number') return new Date(dateLike > 1e12 ? dateLike : dateLike * 1000)
	return new Date(0)
}

export function handleBlock(b: any): BlockRow {
	// Defensive mapping from Subquery/Subquid block/header shape to BlockRow
	const header = b.header ?? b.block ?? b

	return {
		block_number: toBigInt(header.number ?? header.blockNumber ?? b.number),
		block_hash: header.hash ?? header.blockHash ?? b.hash ?? '' ,
		parent_hash: header.parentHash ?? header.parent_hash ?? '' ,
		nonce: header.nonce ?? header.nonceHex ?? '0x0',
		sha3_uncles: header.sha3Uncles ?? header.unclesHash ?? '0x' + '0'.repeat(64),
		logs_bloom: header.logsBloom ?? header.logs_bloom ?? '0x' + '0'.repeat(512),
		transactions_root: header.transactionsRoot ?? header.transactions_root ?? '0x' + '0'.repeat(64),
		state_root: header.stateRoot ?? header.state_root ?? '0x' + '0'.repeat(64),
		receipts_root: header.receiptsRoot ?? header.receipts_root ?? '0x' + '0'.repeat(64),
		miner: header.miner ?? header.author ?? header.coinbase ?? '0x' + '0'.repeat(40),
		proposer: header.proposer ?? null,
		difficulty: header.difficulty ? toBigInt(header.difficulty) : null,
		total_difficulty: header.totalDifficulty ? toBigInt(header.totalDifficulty) : null,
		size: toBigInt(header.size ?? 0),
		extra_data: header.extraData ?? header.extra_data ?? '',
		gas_limit: toBigInt(header.gasLimit ?? header.gas_limit ?? 0),
		gas_used: toBigInt(header.gasUsed ?? header.gas_used ?? 0),
		base_fee_per_gas: header.baseFeePerGas ? toBigInt(header.baseFeePerGas) : null,
		block_timestamp: toTimestamp(header.timestamp ?? header.time ?? header.block_timestamp ?? b.timestamp),
	}
}

export default handleBlock

