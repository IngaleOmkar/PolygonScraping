import {Entity as Entity_, Column as Column_, PrimaryColumn as PrimaryColumn_, IntColumn as IntColumn_, Index as Index_, StringColumn as StringColumn_, DateTimeColumn as DateTimeColumn_, OneToMany as OneToMany_} from "@subsquid/typeorm-store"
import {Transaction} from "./transaction.model"
import {Log} from "./log.model"
import {Trace} from "./trace.model"
import {Erc20Transfer} from "./erc20Transfer.model"
import {Erc721Transfer} from "./erc721Transfer.model"

@Entity_()
export class Block {
    constructor(props?: Partial<Block>) {
        Object.assign(this, props)
    }

    @PrimaryColumn_()
    id!: string

    @Index_()
    @IntColumn_({nullable: false})
    height!: number

    @StringColumn_({nullable: false})
    hash!: string

    @Index_()
    @DateTimeColumn_({nullable: false})
    timestamp!: Date

    @OneToMany_(() => Transaction, e => e.block)
    transactions!: Transaction[]

    @OneToMany_(() => Log, e => e.block)
    logs!: Log[]

    @OneToMany_(() => Trace, e => e.block)
    traces!: Trace[]

    @OneToMany_(() => Erc20Transfer, e => e.block)
    erc20Transfers!: Erc20Transfer[]

    @OneToMany_(() => Erc721Transfer, e => e.block)
    erc721Transfers!: Erc721Transfer[]
}
