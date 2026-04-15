import {TypeormDatabase} from '@subsquid/typeorm-store'
import {Block, Transaction, Log, Trace, Erc20Transfer, Erc721Transfer} from './model'
import {processor} from './processor'

// keccak256("Transfer(address,address,uint256)")
// Shared by both ERC-20 and ERC-721 — they have the same event signature.
const TRANSFER_TOPIC0 = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'

/**
 * Topics are 32-byte hex strings. Addresses occupy the last 20 bytes.
 * We strip the leading 12 zero-bytes (24 hex chars) and restore the 0x prefix.
 */
function decodeAddress(topic: string): string {
    return '0x' + topic.slice(26).toLowerCase()
}

processor.run(new TypeormDatabase({supportHotBlocks: true}), async (ctx) => {
    const blocks: Block[] = []
    const transactions: Transaction[] = []
    const logs: Log[] = []
    const traces: Trace[] = []
    const erc20Transfers: Erc20Transfer[] = []
    const erc721Transfers: Erc721Transfer[] = []

    for (let block of ctx.blocks) {

        // 1. Block
        const blockEntity = new Block({
            id: block.header.height.toString(),
            height: block.header.height,
            hash: block.header.hash,
            timestamp: new Date(block.header.timestamp),
        })
        blocks.push(blockEntity)

        // 2. Transactions
        for (let tx of block.transactions) {
            transactions.push(new Transaction({
                id: tx.hash,
                block: blockEntity,
                blockNumber: block.header.height,
                hash: tx.hash,
                from: tx.from,
                to: tx.to,
                value: tx.value,
                gasUsed: tx.gasUsed,
            }))
        }

        // 3. Raw Logs + decoded ERC-20 / ERC-721 Transfers
        for (let log of block.logs) {

            // Always store the raw log
            logs.push(new Log({
                id: log.id,
                block: blockEntity,
                blockNumber: block.header.height,
                transactionHash: log.transaction?.hash,
                address: log.address,
                topic0: log.topics[0],
                data: log.data,
            }))

            // Only attempt decoding when the topic matches and we have enough topics
            if (log.topics[0] !== TRANSFER_TOPIC0) continue

            const txHash = log.transaction?.hash
            const transferId = `${txHash ?? 'unknown'}-${log.id}`

            if (log.topics.length === 3) {
                // -------------------------------------------------------
                // ERC-20: Transfer(address indexed from, address indexed to, uint256 value)
                // topics[1] = from, topics[2] = to, data = value (uint256, not indexed)
                // -------------------------------------------------------
                const from = decodeAddress(log.topics[1])
                const to   = decodeAddress(log.topics[2])

                // data is a 32-byte big-endian hex uint256, e.g. "0x000...0de0b6b3a7640000"
                // Guard against empty or malformed data
                if (!log.data || log.data === '0x') continue

                const value = BigInt(log.data)

                erc20Transfers.push(new Erc20Transfer({
                    id: transferId,
                    block: blockEntity,
                    blockNumber: block.header.height,
                    transactionHash: txHash,
                    contractAddress: log.address,
                    from,
                    to,
                    value,
                }))

            } else if (log.topics.length === 4) {
                // -------------------------------------------------------
                // ERC-721: Transfer(address indexed from, address indexed to, uint256 indexed tokenId)
                // topics[1] = from, topics[2] = to, topics[3] = tokenId (indexed, so in topics not data)
                // -------------------------------------------------------
                const from    = decodeAddress(log.topics[1])
                const to      = decodeAddress(log.topics[2])
                const tokenId = BigInt(log.topics[3])

                erc721Transfers.push(new Erc721Transfer({
                    id: transferId,
                    block: blockEntity,
                    blockNumber: block.header.height,
                    transactionHash: txHash,
                    contractAddress: log.address,
                    from,
                    to,
                    tokenId,
                }))
            }
            // logs.length === 2 or anything else: malformed event, skip silently
        }

        // 4. Traces
        for (let trc of block.traces) {
            const traceId = `${block.header.height}-${trc.transactionIndex}-${trc.traceAddress.join('-')}`

            if (trc.type === 'call') {
                const callTrc = trc as any
                if (callTrc.action?.from) {
                    traces.push(new Trace({
                        id: traceId,
                        block: blockEntity,
                        blockNumber: block.header.height,
                        transactionHash: trc.transaction?.hash,
                        from: callTrc.action.from,
                        to: callTrc.action.to,
                        type: trc.type,
                        value: callTrc.action.value ?? 0n,
                    }))
                }
            } else if (trc.type === 'create') {
                const createTrc = trc as any
                if (createTrc.action?.from) {
                    traces.push(new Trace({
                        id: traceId,
                        block: blockEntity,
                        blockNumber: block.header.height,
                        transactionHash: trc.transaction?.hash,
                        from: createTrc.action.from,
                        to: createTrc.result?.address,
                        type: trc.type,
                        value: createTrc.action.value ?? 0n,
                    }))
                }
            }
        }
    }

    // 5. Batch save — blocks first due to FK dependencies
    await ctx.store.upsert(blocks)
    await ctx.store.upsert(transactions)
    await ctx.store.upsert(logs)
    await ctx.store.upsert(traces)
    await ctx.store.upsert(erc20Transfers)
    await ctx.store.upsert(erc721Transfers)
})