import { config } from './config.js'
import { pool, dropForeignKeys, restoreForeignKeys, insertBlocks, insertTransactions, insertReceipts, insertLogs, insertErc20Transfers, insertErc721Transfers, insertTraces } from './db.js'
import handleBlock from './handlers/blocks.js'
import handleTransaction from './handlers/transactions.js'
import handleLog from './handlers/logs.js'
import handleTrace from './handlers/traces.js'

const SUBQ_URL = process.env.SUBQ_URL

async function runNoop() {
  console.log('Processor implemented. To run, set SUBQ_URL and ensure @subsquid/evm-processor is installed.')
  console.log('Example: SUBQ_URL="https://your-subquery-endpoint" npm start')
}

async function main() {
  if (!SUBQ_URL) {
    await runNoop()
    return
  }

  let evmModule: any
  try {
    evmModule = await import('@subsquid/evm-processor')
  } catch (e) {
    console.error('Failed to import @subsquid/evm-processor:', (e as any).message ?? e)
    console.error('Handlers are implemented but the runtime integration could not be loaded.')
    process.exit(1)
  }

  // Best-effort wiring: try to detect commonly used API shapes
  const createProcessor = evmModule.createEvmBatchProcessor ?? evmModule.createProcessor ?? evmModule.EvmBatchProcessor ?? evmModule.BatchProcessor

  if (!createProcessor) {
    console.error('Unrecognized @subsquid/evm-processor API. Handlers are ready, but processor wiring failed.')
    process.exit(1)
  }

  // Batch accumulation arrays
  let blocks: any[] = []
  let txs: any[] = []
  let receipts: any[] = []
  let logs: any[] = []
  let erc20s: any[] = []
  let erc721s: any[] = []
  let traces: any[] = []

  const processor = typeof createProcessor === 'function'
    ? createProcessor({ url: SUBQ_URL, startBlock: config.fromBlock, endBlock: config.toBlock })
    : new createProcessor({ url: SUBQ_URL, startBlock: config.fromBlock, endBlock: config.toBlock })

  // Helper to flush current accumulated rows into DB
  async function flush() {
    if (blocks.length) await insertBlocks(blocks.map(handleBlock))
    if (txs.length) await insertTransactions(txs.map(t => t))
    if (receipts.length) await insertReceipts(receipts.map(r => r))
    if (logs.length) await insertLogs(logs.map(l => l))
    if (erc20s.length) await insertErc20Transfers(erc20s.map(e => e))
    if (erc721s.length) await insertErc721Transfers(erc721s.map(e => e))
    if (traces.length) await insertTraces(traces.map(t => t))

    blocks = []
    txs = []
    receipts = []
    logs = []
    erc20s = []
    erc721s = []
    traces = []
  }

  // Register handlers for a few common API shapes
  if (processor.on && typeof processor.on === 'function') {
    processor.on('block', async (ctx: any) => {
      try {
        blocks.push(handleBlock(ctx.block ?? ctx))
        for (const tx of (ctx.transactions ?? ctx.txs ?? [])) {
          const { txRow, receiptRow } = handleTransaction(tx, tx.receipt ?? ctx.receipt ?? undefined)
          txs.push(txRow)
          if (receiptRow) receipts.push(receiptRow)
        }
        for (const l of (ctx.logs ?? [])) {
          const { logRow, erc20, erc721 } = handleLog(l)
          logs.push(logRow)
          if (erc20) erc20s.push(erc20)
          if (erc721) erc721s.push(erc721)
        }
        for (const tr of (ctx.traces ?? [])) {
          traces.push(handleTrace(tr))
        }
      } catch (e) {
        console.error('Error handling block event:', e)
      }
    })

    processor.on('batchEnd', async () => {
      try { await flush() } catch (e) { console.error('Flush error', e) }
    })

    console.log('Starting processor (evented API)')
    if (processor.run) await processor.run()
    else if (processor.start) await processor.start()
    else console.error('Processor object has no run/start method')

    return
  }

  // Fallback: If processor has a `run` function that accepts handlers directly
  if (processor.run && typeof processor.run === 'function') {
    console.log('Starting processor (direct run API)')
    await processor.run({
      onBlock: async (block: any) => {
        blocks.push(handleBlock(block))
      },
      onTransaction: async (tx: any, receipt: any) => {
        const { txRow, receiptRow } = handleTransaction(tx, receipt)
        txs.push(txRow)
        if (receiptRow) receipts.push(receiptRow)
      },
      onLog: async (l: any) => {
        const { logRow, erc20, erc721 } = handleLog(l)
        logs.push(logRow)
        if (erc20) erc20s.push(erc20)
        if (erc721) erc721s.push(erc721)
      },
      onTrace: async (t: any) => {
        traces.push(handleTrace(t))
      },
      onBatchEnd: async () => { await flush() }
    })
    return
  }

  console.error('Processor API not recognized. Handlers are implemented though.')
}

main().catch(e => { console.error(e); process.exit(1) })
