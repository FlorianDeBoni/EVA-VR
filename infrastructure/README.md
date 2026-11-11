# Infrastructure

Local services for development (Langfuse v3: web, worker, Postgres, ClickHouse, Redis, MinIO).

## Setup

```bash
cp infrastructure/.env.infrastructure.template infrastructure/.env.infrastructure   # then adjust the values
task dev:langfuse     # start, UI at http://localhost:3000
task docker:stop      # stop, keep data
task docker:delete    # stop and remove the volumes (data is lost)
```

All settings live in `.env.infrastructure` (git-ignored). The compose file at
`langfuse/docker-compose.yml` has no hard-coded values: a missing variable makes
`docker compose` fail with an explicit message. The defaults in the template are for
local development only, change every secret before exposing anything.
