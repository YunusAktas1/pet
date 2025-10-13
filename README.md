## Hızlı Başlangıç (Docker)
```bash
docker compose up -d api
# sonra: http://127.0.0.1:8000/healthz  → {"ok": true}
```

## Yerel Geliştirme
```powershell
$env:ENV_FILE = "backend/.env.local"
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --reload-dir backend
```

## Pre-commit
```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## CI

Her push/PR'da lint+typecheck+migration+test otomatik koşar (GitHub Actions).

---

## Doğrulama — PowerShell Komutları

```powershell
cd C:\Dev\Yunus
$env:ENV_FILE = "backend/.env.local"

# Pre-commit'i kur (bir kerelik)
.\backend\.venv\Scripts\python.exe -m pip install pre-commit
.\backend\.venv\Scripts\pre-commit.exe install
.\backend\.venv\Scripts\pre-commit.exe run --all-files

# Docker ile API+DB
docker compose up -d api
docker compose ps
iwr http://127.0.0.1:8000/healthz

# Hızlı duman
$signup = @{ email="ci-demo@example.com"; password="Aa!123456" } | ConvertTo-Json
iwr http://127.0.0.1:8000/api/v1/auth/signup -Method Post -ContentType 'application/json' -Body $signup | Out-Null
$tok = (iwr http://127.0.0.1:8000/api/v1/auth/login -Method Post -ContentType 'application/json' -Body $signup).Content | ConvertFrom-Json | % access_token
$hdr = @{ Authorization = "Bearer $tok" }
iwr http://127.0.0.1:8000/api/v1/pets -Method Post -Headers $hdr -ContentType 'application/json' -Body (@{name="Docky";species="cat";gender="female"} | ConvertTo-Json)

# Lokal kalite kapıları yine yeşil mi?
.\backend\.venv\Scripts\python.exe -m ruff check backend --fix
.\backend\.venv\Scripts\python.exe -m black backend
.\backend\.venv\Scripts\python.exe -m mypy backend
.\backend\.venv\Scripts\python.exe -m pytest -q
```

GitHub'a push sonrası CI otomatik çalışmalı. (Repo yoksa git init, ilk commit ve remote ekledikten sonra push.)
