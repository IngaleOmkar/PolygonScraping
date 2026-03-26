import dotenv from 'dotenv'
dotenv.config()

function required(name: string): string {
  const val = process.env[name]
  if (!val) throw new Error(`Missing env var: ${name}`)
  return val
}

export const config = {
  databaseUrl: required('DATABASE_URL'),
  fromBlock: parseInt(process.env.FROM_BLOCK ?? '50000000', 10),
  toBlock: process.env.TO_BLOCK ? parseInt(process.env.TO_BLOCK, 10) : undefined,
}