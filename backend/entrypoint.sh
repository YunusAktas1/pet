#!/usr/bin/env bash
set -euo pipefail

# wait for DB
python - <<'PY'
import os, time, sys
import psycopg2
dsn = os.environ["DATABASE_URL"].replace("+psycopg2","")
for i in range(60):
    try:
        psycopg2.connect(dsn).close()
        sys.exit(0)
    except Exception:
        time.sleep(1)
print("DB not ready", file=sys.stderr)
sys.exit(1)
PY

alembic upgrade head
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
