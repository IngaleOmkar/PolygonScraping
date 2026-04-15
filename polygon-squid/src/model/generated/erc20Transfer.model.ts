import {Entity as Entity_, Column as Column_, PrimaryColumn as PrimaryColumn_, ManyToOne as ManyToOne_, Index as Index_, IntColumn as IntColumn_, StringColumn as StringColumn_, BigIntColumn as BigIntColumn_} from "@subsquid/typeorm-store"
import {Block} from "./block.model"

@Entity_()
export class Erc20Transfer {
    constructor(props?: Partial<Erc20Transfer>) {
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
    contractAddress!: string

    @Index_()
    @StringColumn_({nullable: false})
    from!: string

    @Index_()
    @StringColumn_({nullable: false})
    to!: string

    @BigIntColumn_({nullable: false})
    value!: bigint
}
