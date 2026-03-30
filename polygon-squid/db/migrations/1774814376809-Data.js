module.exports = class Data1774814376809 {
    name = 'Data1774814376809'

    async up(db) {
        await db.query(`ALTER TABLE "transaction" ADD "block_id" character varying`)
        await db.query(`ALTER TABLE "log" ADD "block_id" character varying`)
        await db.query(`ALTER TABLE "trace" ADD "block_id" character varying`)
        await db.query(`CREATE INDEX "IDX_c0e1460f3c9eee975fee81002d" ON "transaction" ("block_id") `)
        await db.query(`CREATE INDEX "IDX_7d3f5ac68148194ee7ced3032e" ON "log" ("block_id") `)
        await db.query(`CREATE INDEX "IDX_40a63d9e29c3d0ddc3501292c6" ON "trace" ("block_id") `)
        await db.query(`ALTER TABLE "transaction" ADD CONSTRAINT "FK_c0e1460f3c9eee975fee81002dc" FOREIGN KEY ("block_id") REFERENCES "block"("id") ON DELETE NO ACTION ON UPDATE NO ACTION`)
        await db.query(`ALTER TABLE "log" ADD CONSTRAINT "FK_7d3f5ac68148194ee7ced3032e2" FOREIGN KEY ("block_id") REFERENCES "block"("id") ON DELETE NO ACTION ON UPDATE NO ACTION`)
        await db.query(`ALTER TABLE "trace" ADD CONSTRAINT "FK_40a63d9e29c3d0ddc3501292c6b" FOREIGN KEY ("block_id") REFERENCES "block"("id") ON DELETE NO ACTION ON UPDATE NO ACTION`)
    }

    async down(db) {
        await db.query(`ALTER TABLE "transaction" DROP COLUMN "block_id"`)
        await db.query(`ALTER TABLE "log" DROP COLUMN "block_id"`)
        await db.query(`ALTER TABLE "trace" DROP COLUMN "block_id"`)
        await db.query(`DROP INDEX "public"."IDX_c0e1460f3c9eee975fee81002d"`)
        await db.query(`DROP INDEX "public"."IDX_7d3f5ac68148194ee7ced3032e"`)
        await db.query(`DROP INDEX "public"."IDX_40a63d9e29c3d0ddc3501292c6"`)
        await db.query(`ALTER TABLE "transaction" DROP CONSTRAINT "FK_c0e1460f3c9eee975fee81002dc"`)
        await db.query(`ALTER TABLE "log" DROP CONSTRAINT "FK_7d3f5ac68148194ee7ced3032e2"`)
        await db.query(`ALTER TABLE "trace" DROP CONSTRAINT "FK_40a63d9e29c3d0ddc3501292c6b"`)
    }
}
