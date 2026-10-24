# Behoosh (بهوش)

Personal health, finance and meeting assistant, in Persian. AI agents use it over MCP.

| Module | Prefix | Scopes |
|---|---|---|
| Auth | `/v1/auth` | — |
| Health: meals, sleep, workouts, body, prayer, mood, screen time, habits, temperament | `/v1` | `health:read`, `health:write` |
| Finance: double-entry ledger, bank SMS parser, budgets, loans | `/v1/finance` | `finance:read`, `finance:write` |
| Live meeting: speech-to-text plus AI agents | `/v1/live` | `meeting:read`, `meeting:write` |

The user ID always comes from the token, never from the request.

## Layout

```
app/
  api/            FastAPI app (main.py), auth, finance, live, dashboard routes
    health/       health routes: logs.py, temperament.py, insights.py
  core/           settings (env vars), password/token hashing, rate limiter
  db/             SQLAlchemy models, session, migrate.py, seed, set_password
  mcp/            MCP servers (health :8001, finance :8002) + shared HTTP client
  services/       finance ledger, SMS parser, Jalali dates, ASR, live meeting
dashboard/        static HTML pages with css/ and js/
migrations/       SQL files, applied in name order by app.db.migrate
deploy/           Dockerfile, compose files, nginx, env examples
tests/            pytest suite
```

## Running locally

```bash
cp deploy/env/api.env.example .env      # set DATABASE_URL, API_TOKEN
make up                                 # db + api (migrations run on start) + mcp
docker compose -f deploy/docker-compose.yml exec api \
  python -m app.db.set_password --email me@example.com --password 'secret123'
```

## Migrations

Migrations are plain SQL files in `migrations/`, applied in filename order. Each one is
recorded in the `schema_migrations` table, so it runs only once. The files are idempotent,
so running this against a database that was migrated by hand is safe: it just records them.

```bash
python -m app.db.migrate            # apply pending migrations
python -m app.db.migrate --status
```

To add a migration, create the next numbered file, for example `010_something.sql`.
Don't edit a file that has already been applied.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                   # unit tests only
TEST_DATABASE_URL=postgresql+psycopg://user@localhost:5432/behoosh_test pytest
ruff check app tests
```

The API tests need an empty Postgres database. The suite drops and recreates its schemas.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://behoosh:behoosh@db:5432/behoosh` | |
| `API_TOKEN` | empty | Legacy fixed token (health scopes only). Placeholders such as `CHANGE_ME` are rejected. |
| `AUTH_LEGACY_TOKEN` | `true` | Set to `false` once agents use their own tokens. |
| `CORS_ORIGINS` | `*` | Comma-separated dashboard origins. |
| `ALLOW_REGISTRATION` | `false` | Opens `POST /v1/auth/register`. |
| `SESSION_TTL_DAYS` | `30` | Lifetime of dashboard login tokens. `0` means no expiry. |
| `AUTH_RATE_LIMIT` / `AUTH_RATE_WINDOW_S` | `10` / `300` | Login and register attempts per IP and per email. |
| `SEED_DISPLAY_NAME` | `کاربر` | Name of the first user created by `app.db.seed`. |
| `BEHOOSH_API` | `http://api:8000` | Address the MCP servers use to reach the API. |
| `MCP_ALLOW_FALLBACK` | `false` | Lets MCP fall back to the env token when a request has no token. |
| `SINA_ASR_URL`, `SINA_ASR_KEY` | | Speech-to-text service for live meetings. |
| `AMP_URL`, `BEHOOSH_MCP_URL` | | Agent bridge for live meetings. |

Deployment steps (in Persian) are in [deploy/README.md](deploy/README.md).
