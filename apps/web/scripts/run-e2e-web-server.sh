#!/usr/bin/env bash
set -euo pipefail

backup_dir="$(mktemp -d /tmp/stockmassive-e2e-metadata.XXXXXX)"

restore_metadata() {
  cp "$backup_dir/next-env.d.ts" next-env.d.ts
  cp "$backup_dir/tsconfig.json" tsconfig.json
  find "$backup_dir" -maxdepth 1 -type f -delete
  rmdir "$backup_dir"
}

cp next-env.d.ts "$backup_dir/next-env.d.ts"
cp tsconfig.json "$backup_dir/tsconfig.json"
trap restore_metadata EXIT

pnpm build
restore_metadata
trap - EXIT

cp -R .next-e2e/static .next-e2e/standalone/apps/web/.next-e2e/static
cp -R public .next-e2e/standalone/apps/web/public
exec node .next-e2e/standalone/apps/web/server.js
