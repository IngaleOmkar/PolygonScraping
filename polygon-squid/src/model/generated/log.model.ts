import {Entity as Entity_, Column as Column_, PrimaryColumn as PrimaryColumn_, ManyToOne as ManyToOne_, Index as Index_, IntColumn as IntColumn_, StringColumn as StringColumn_} from "@subsquid/typeorm-store"
import {Block} from "./block.model"

@Entity_()
export class Log {
    constructor(props?: Partial<Log>) {
        Object.assign(this, props)
    }

    @PrimaryColumn_()
    id!: string

    @Index_()
    @ManyToOne_(() => Block, {nullable: true})
    block!: Block

    @Index_()
    @IntColumn_({nullable: false})
    blockNumber!: number

    @Index_()
    @StringColumn_({nullable: true})
    transactionHash!: string | undefined | null

    @Index_()
    @StringColumn_({nullable: false})
    address!: string

    @Index_()
    @StringColumn_({nullable: true})
    topic0!: string | undefined | null

    @StringColumn_({nullable: true})
    data!: string | undefined | null
}
