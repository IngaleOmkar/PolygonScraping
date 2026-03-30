import {EvmBatchProcessor} from '@subsquid/evm-processor'
import {lookupArchive} from '@subsquid/archive-registry'

export const processor = new EvmBatchProcessor()
    .setDataSource({
        // Use the high-speed gateway for Polygon
        archive: lookupArchive('polygon', {type: 'EVM'}),
        // Important: Use a reliable RPC (Alchemy/QuickNode) for Traces
        chain: process.env.RPC_POLYGON_HTTP || 'https://polygon-rpc.com'
    })
    .setFinalityConfirmation(200)
    .setBlockRange({ from: 47_000_000, to: 54_000_000 })
    .addLog({
        // Capture all ERC20/ERC721 Transfers for clustering
        topic0: ['0xddf252ad1be2c89b69c2b068fc378daf8d8d9a7ef30e63f76eb2d3dbe75bfd92'] 
    })
    .addTransaction({
        // Captures standard EOA to EOA/Contract calls
    })
    .setFields({
        transaction: {
            from: true,
            to: true,
            value: true,
            gasUsed: true,
            hash: true
        },
        log: {
            address: true,
            data: true,
            topics: true
        },
        trace: {
            callFrom: true,
            callTo: true,
            callValue: true,
            callSighash: true,
            type: true
        }
    })
    .addTrace({
        type: ['call', 'create', 'suicide']
    })