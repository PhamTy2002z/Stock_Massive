# Backend deployment

The backend currently deploys to the local Docker Compose service named
`stockmassive-api-1`. The service listens on `http://127.0.0.1:8000`; the
repository does not define a remote deployment environment or public backend
URL.

## Deploy the backend

Create a PostgreSQL backup before a deployment that includes a migration. Then
rebuild and replace only the API container:

```bash
REALTIME_INGESTION_ENABLED=false \
  docker compose up -d --build --no-deps api
```

The API entrypoint runs `alembic upgrade head` before Uvicorn starts. A local
migration failure stops the container instead of serving an older schema.

The realtime ingestion runtime remains disabled until the controlled S1 probe
passes during an open-market window. Enabling it also requires PostgreSQL,
Redis, `DNSE_API_KEY`, and `DNSE_API_SECRET`.

## Verify the deployment

Verify the container, schema, and HTTP contract after every deploy:

```bash
docker compose ps
docker compose exec -T api alembic current
curl --fail http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/realtime/health
```

When realtime ingestion is disabled and has never recorded a health state, the
realtime health endpoint returns `404` with `Realtime health is not recorded`.
This response does not indicate a failed API deployment.

## Environment variables

The deployment forwards these realtime settings without storing their values
in the repository:

- `REALTIME_INGESTION_ENABLED`
- `DNSE_API_KEY`
- `DNSE_API_SECRET`
- `DNSE_BOARD_IDS`
- `REALTIME_QUEUE_SIZE`
- `REALTIME_WORKER_COUNT`
- `REALTIME_SHUTDOWN_TIMEOUT_SECONDS`

Use `.env` for local values. Git ignores that file and its timestamped backup
variants.

## Roll back

Stop the API and downgrade while the current source still contains the
migration. Then switch to a checkout of the previous source revision before
rebuilding; rebuilding from the current checkout would run the entrypoint and
upgrade the schema again:

```bash
docker compose stop api
docker compose run --rm --entrypoint alembic api downgrade b7f4e9c21a08
# Check out the verified pre-deployment revision, preferably in a temporary
# worktree, and run the rebuild from that checkout.
docker compose up -d --build --no-deps api
```

If a downgrade cannot preserve the required data, restore the verified
pre-deployment custom-format dump with PostgreSQL 16 `pg_restore` (for example,
the binary inside the `postgres:16-alpine` database container). The host's older
`pg_restore` may not understand the archive format. Restoring a dump replaces
database state, so resolve the exact target and stop writers before running it.

## Latest deployment evidence

On August 24, 2026, the local API image was rebuilt from commit `f52e69a` and
migrated to Alembic head `c8f2a6d31e04`. The deployment kept realtime ingestion
disabled. The root health check returned `200`, the container remained healthy
with a zero failing streak, and the realtime health endpoint returned its
expected disabled-state `404`.

The verified backup is
`.backups/stockmassive-pre-deploy-f52e69a-20260824T2204.dump`. Its SHA-256
digest is
`b395697f313060874fad3027cde3325f84b70db687b14fefe05f6d7df5202a75`.

## Next steps

Run the controlled S1 probe during an open-market window. Record quote quantity
scale, throughput, subscription limits, ordering, and reconnect gaps before
setting `REALTIME_INGESTION_ENABLED=true`.
