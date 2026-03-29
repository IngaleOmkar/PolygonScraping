import type { TraceRow } from '../types.js'

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

function traceAddressToString(addr: any): string {
	if (Array.isArray(addr)) return addr.join('.')
	if (typeof addr === 'string') return addr
	return ''
}

export function handleTrace(t: any): TraceRow {
	// t shape: { blockNumber, transactionHash, transactionPosition, traceAddress, type, action, result, error, subtraces }
	const trace_address = traceAddressToString(t.traceAddress ?? t.trace_address ?? t.trace_address_raw ?? t.address)

	const action = t.action ?? t.action ?? {}
	const result = t.result ?? {}

	return {
		block_number: toBigInt(t.blockNumber ?? t.block_number ?? t.block?.number),
		transaction_hash: t.transactionHash ?? t.transaction_hash ?? null,
		transaction_index: t.transactionPosition ?? t.transactionIndex ?? t.transaction_index ?? null,
		trace_address,
		trace_type: String(t.type ?? t.traceType ?? t.trace_type ?? ''),
		call_type: action.callType ?? action.call_type ?? null,
		from_address: action.from ?? action.fromAddress ?? null,
		to_address: action.to ?? action.toAddress ?? null,
		value: toBigInt(action.value ?? action.amount ?? 0),
		gas: action.gas ? toBigInt(action.gas) : null,
		gas_used: result.gasUsed ? toBigInt(result.gasUsed) : (t.gasUsed ? toBigInt(t.gasUsed) : null),
		input: action.input ?? action.data ?? null,
		output: result.output ?? null,
		error: t.error ?? null,
		subtraces: Number(t.subtraces ?? t.subtracesCount ?? 0),
	}
}

export default handleTrace

