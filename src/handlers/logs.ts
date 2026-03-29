import type { LogRow, Erc20TransferRow, Erc721TransferRow } from '../types.js'

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

const ERC20_TRANSFER_SIG = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'

export function handleLog(l: any): { logRow: LogRow, erc20?: Erc20TransferRow, erc721?: Erc721TransferRow } {
	const topics: (string | null)[] = Array.isArray(l.topics) ? l.topics : (l.topics ?? [])

	const logRow: LogRow = {
		block_number: toBigInt(l.blockNumber ?? l.block_number ?? l.block?.number),
		transaction_hash: l.transactionHash ?? l.transaction_hash ?? '',
		transaction_index: l.transactionIndex ?? l.transaction_index ?? 0,
		log_index: toBigInt(l.logIndex ?? l.log_index ?? 0),
		address: l.address ?? l.contractAddress ?? '',
		data: l.data ?? l.rawData ?? '',
		topic0: topics[0] ?? null,
		topic1: topics[1] ?? null,
		topic2: topics[2] ?? null,
		topic3: topics[3] ?? null,
		removed: Boolean(l.removed ?? false),
	}

	// Try to decode ERC20/721 Transfer events (topic0 == transfer signature)
	let erc20: Erc20TransferRow | undefined
	let erc721: Erc721TransferRow | undefined

	if (topics[0] && topics[0].toLowerCase() === ERC20_TRANSFER_SIG) {
		// indexed: from (topic1), to (topic2); value in data
		const from = topics[1] ? '0x' + topics[1].slice(-40) : ''
		const to = topics[2] ? '0x' + topics[2].slice(-40) : ''
		const value = l.data ? toBigInt(l.data) : BigInt(0)
		erc20 = {
			block_number: logRow.block_number,
			transaction_hash: logRow.transaction_hash,
			log_index: logRow.log_index,
			token_address: logRow.address,
			from_address: from,
			to_address: to,
			value,
		}
	}

	// ERC721 Transfer has same signature but tokenId in topics[3] or data
	if (topics[0] && topics[0].toLowerCase() === ERC20_TRANSFER_SIG && (topics[3] || l.data)) {
		// If topics[3] exists it's tokenId (indexed)
		const tokenId = topics[3] ? toBigInt(topics[3]) : (l.data ? toBigInt(l.data) : BigInt(0))
		const from = topics[1] ? '0x' + topics[1].slice(-40) : ''
		const to = topics[2] ? '0x' + topics[2].slice(-40) : ''
		erc721 = {
			block_number: logRow.block_number,
			transaction_hash: logRow.transaction_hash,
			log_index: logRow.log_index,
			token_address: logRow.address,
			from_address: from,
			to_address: to,
			token_id: tokenId,
		}
	}

	return { logRow, erc20, erc721 }
}

export default handleLog

