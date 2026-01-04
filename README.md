# PetMatch backend

## Quick start (Docker)
```bash
cd C:\Users\YUNUS\Documents\GitHub\pet
docker compose up -d --build
# run migrations inside api container
docker compose exec api alembic upgrade head
# health check
curl http://127.0.0.1:8000/healthz
```

## Local dev (venv)
```powershell
# set required secret for refresh token HMAC hashing
$env:REFRESH_TOKEN_HMAC_SECRET="dev-refresh-hmac-secret-change-me-32chars-minimum"
python -m venv backend/.venv
.ackend\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --reload-dir backend
```

## Verify OpenAPI
```bash
curl -s http://127.0.0.1:8000/openapi.json | Select-String -Pattern '"/api/v1/auth/refresh"'
```

## Auth flow (enveloped responses)
- `POST /api/v1/auth/signup` with `{ "email": "user@example.com", "password": "StrongPass!234" }`
- `POST /api/v1/auth/login` returns `{ "success": true, "data": { "access_token", "refresh_token", "token_type" }, "error": null }`
- `POST /api/v1/auth/refresh` with `{ "refresh_token": "..." }` rotates the refresh token (old one revoked) and returns new access/refresh tokens.
- `POST /api/v1/auth/logout` with `{ "refresh_token": "..." }` revokes that refresh token server-side.
- Access tokens are short-lived (default 30m); refresh tokens default to 14 days and are stored hashed in DB.

PowerShell smoke test:
```powershell
$signup = @{ email="ci-demo@example.com"; password="Aa!123456" } | ConvertTo-Json
Invoke-WebRequest http://127.0.0.1:8000/api/v1/auth/signup -Method Post -ContentType 'application/json' -Body $signup | Out-Null
$login = Invoke-WebRequest http://127.0.0.1:8000/api/v1/auth/login -Method Post -ContentType 'application/json' -Body $signup | ConvertFrom-Json
$refresh1 = $login.data.refresh_token
Invoke-WebRequest http://127.0.0.1:8000/api/v1/auth/refresh -Method Post -ContentType 'application/json' -Body (@{refresh_token=$refresh1} | ConvertTo-Json)
Invoke-WebRequest http://127.0.0.1:8000/api/v1/auth/logout -Method Post -ContentType 'application/json' -Body (@{refresh_token=$refresh1} | ConvertTo-Json)
# reuse should fail with 401
Invoke-WebRequest http://127.0.0.1:8000/api/v1/auth/refresh -Method Post -ContentType 'application/json' -Body (@{refresh_token=$refresh1} | ConvertTo-Json) -SkipHttpErrorCheck
```

## Inspect DB schema (refresh_token table)
```bash
docker compose exec db psql -U petuser -d petmatch -c "\d refresh_token"
```

## CORS
- Dev defaults allow:
  - http://localhost:3000
  - http://localhost:5173
- Override via `CORS_ORIGINS` in `.env` for other environments.

## Seed data (dev only)
```powershell
# ensure DB is reachable (docker compose up or local DB)
$env:REFRESH_TOKEN_HMAC_SECRET="dev-refresh-hmac-secret-change-me-32chars-minimum"
python -m backend.scripts.seed
```
- Idempotent: re-running keeps/updates demo users (`seed@example.com`, `seed2@example.com`), pets, photos, pair, messages, and sample matches.

## Pre-commit
```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Quality gates
```powershell
.ackend\.venv\Scripts\python.exe -m ruff check backend --fix
.ackend\.venv\Scripts\python.exe -m black backend
.ackend\.venv\Scripts\python.exe -m mypy backend
.ackend\.venv\Scripts\python.exe -m pytest -q
```
