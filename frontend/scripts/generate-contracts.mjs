import { readFile, writeFile } from 'node:fs/promises'
import { compile } from 'json-schema-to-typescript'

const schema = JSON.parse(await readFile(new URL('../src/shared/contracts.schema.json', import.meta.url), 'utf8'))
const output = await compile(schema, 'PlatformContracts', {
  bannerComment: '/* Generated from backend/app/shared/schemas.py. Controller-owned; do not hand edit. */',
  additionalProperties: false,
  unreachableDefinitions: true,
})
await writeFile(new URL('../src/shared/contracts.ts', import.meta.url), output)
console.log('Generated src/shared/contracts.ts')
