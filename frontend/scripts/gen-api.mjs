// Generates src/api/schema.d.ts from the server's OpenAPI (`sibylle openapi`).
// `--check` fails instead of writing when the committed file is out of date.
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';

import openapiTS, { astToString } from 'openapi-typescript';

const check = process.argv.includes('--check');
const target = new URL('../src/api/schema.d.ts', import.meta.url);

const spec = execFileSync('uv', ['run', '--directory', '../backend', 'sibylle', 'openapi'], {
  encoding: 'utf8',
  maxBuffer: 64 * 1024 * 1024,
});
const ast = await openapiTS(JSON.parse(spec));
const output =
  "// Généré par `npm run gen:api` depuis l'OpenAPI du serveur. Ne pas modifier à la main.\n\n" +
  astToString(ast);

if (check) {
  let current = '';
  try {
    current = readFileSync(target, 'utf8');
  } catch {
    // missing file: out of date
  }
  if (current !== output) {
    console.error('src/api/schema.d.ts est en retard sur le serveur : lance `npm run gen:api`.');
    process.exit(1);
  }
  console.log('src/api/schema.d.ts est à jour.');
} else {
  writeFileSync(target, output);
  console.log('src/api/schema.d.ts régénéré.');
}
