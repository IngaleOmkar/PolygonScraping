import {EvmBatchProcessor} from '@subsquid/evm-processor'
import {lookupArchive} from '@subsquid/archive-registry'

export const processor = new EvmBatchProcessor()
    .setDataSource({
        archive: lookupArchive('polygon', {type: 'EVM'}),
        chain: process.env.RPC_POLYGON_HTTP || 'https://polygon-rpc.com'
    })
    .setFinalityConfirmation(200)
    .setBlockRange({ from: 47_000_000, to: 54_000_000 })
    .addLog({
        // Correct keccak256 of Transfer(address,address,uint256)
        topic0: ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef']
    })
    .addTransaction({})
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