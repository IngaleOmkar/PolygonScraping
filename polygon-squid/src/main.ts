import {TypeormDatabase} from '@subsquid/typeorm-store'
import {Block, Transaction, Log, Trace} from './model'
import {processor} from './processor'

processor.run(new TypeormDatabase({supportHotBlocks: true}), async (ctx) => {
    const blocks: Block[] = []
    const transactions: Transaction[] = []
    const logs: Log[] = []
    const traces: Trace[] = []

    for (let block of ctx.blocks) {
        // 1. Initialize the Block Entity
        const blockEntity = new Block({
            id: block.header.height.toString(),
            height: block.header.height,
            hash: block.header.hash,
            timestamp: new Date(block.header.timestamp),
        })
        blocks.push(blockEntity)

        // 2. Map Transactions
        for (let tx of block.transactions) {
            transactions.push(new Transaction({
                id: tx.hash,
                block: blockEntity, // Relation link
                blockNumber: block.header.height,
                hash: tx.hash,
                from: tx.from,
                to: tx.to,
                value: tx.value,
                gasUsed: tx.gasUsed,
            }))
        }

        // 3. Map Logs (Events)
        for (let log of block.logs) {
            logs.push(new Log({
                id: log.id,
                block: blockEntity, // Relation link
                blockNumber: block.header.height,
                transactionHash: log.transaction?.hash,
                address: log.address,
                topic0: log.topics[0],
                data: log.data,
            }))
        }

        // 4. Map Traces (Internal Calls)
        for (let trc of block.traces) {
            const traceId = `${block.header.height}-${trc.transactionIndex}-${trc.traceAddress.join('-')}`

            if (trc.type === 'call') {
                const callTrc = trc as any
                if (callTrc.action?.from) {
                    traces.push(new Trace({
                        id: traceId,
                        block: blockEntity, // Relation link
                        blockNumber: block.header.height,
                        transactionHash: trc.transaction?.hash,
                        from: callTrc.action.from,
                        to: callTrc.action.to,
                        type: trc.type,
                        value: callTrc.action.value ?? 0n,
                    }))
                }
            } 
            else if (trc.type === 'create') {
                const createTrc = trc as any
                if (createTrc.action?.from) {
                    traces.push(new Trace({
                        id: traceId,
                        block: blockEntity, // Relation link
                        blockNumber: block.header.height,
                        transactionHash: trc.transaction?.hash,
                        from: createTrc.action.from,
                        to: createTrc.result?.address, // New contract address
                        type: trc.type,
                        value: createTrc.action.value ?? 0n,
                    }))
                }
            }
        }
    }

    // 5. Batch Save to Database
    // Order matters here: Blocks must be saved first because of Foreign Key relations
    await ctx.store.upsert(blocks)
    await ctx.store.upsert(transactions)
    await ctx.store.upsert(logs)
    await ctx.store.upsert(traces)
})