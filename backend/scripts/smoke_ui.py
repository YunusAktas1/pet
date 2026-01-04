
from __future__ import annotations

import os
import time

import httpx

DEFAULT_BASE = os.getenv("SMOKE_BASE_URL", "http://localhost:8000")
EMAIL_1 = os.getenv("SEED_EMAIL_1", "seed@example.com")
EMAIL_2 = os.getenv("SEED_EMAIL_2", "seed2@example.com")
PASSWORD = os.getenv("SEED_PASSWORD", "SeedPass123!")


def _redact(token: str | None) -> str:
    if not token:
        return ""
    return token[:6] + "..."


def _auth_header(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    base = DEFAULT_BASE.rstrip("/")
    client = httpx.Client(base_url=base, timeout=10)
    steps: list[str] = []
    try:
        r = client.get("/healthz")
        r.raise_for_status()
        steps.append("healthz PASS")

        creds = {"email": EMAIL_1, "password": PASSWORD}
        login = client.post("/api/v1/auth/login", json=creds)
        login.raise_for_status()
        tokens = login.json().get("data", login.json())
        access = tokens.get("access_token")
        refresh = tokens.get("refresh_token")
        steps.append(f"login PASS access={_redact(access)} refresh={_redact(refresh)}")

        refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        if refresh_resp.status_code == 429:
            retry_after = int(refresh_resp.headers.get("Retry-After", "1"))
            time.sleep(retry_after + 1)
            refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        if refresh_resp.status_code == 429:
            steps.append("refresh rate_limited (accepted)")
            new_refresh = refresh
        else:
            refresh_resp.raise_for_status()
            refresh_data = refresh_resp.json().get("data", refresh_resp.json())
            new_refresh = refresh_data.get("refresh_token")
            access = refresh_data.get("access_token", access)
            steps.append(f"refresh PASS new_refresh={_redact(new_refresh)}")

        logout = client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh or refresh})
        logout.raise_for_status()
        steps.append("logout PASS")

        reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        if reuse.status_code != 401:
            raise SystemExit(f"reuse expected 401, got {reuse.status_code}")
        steps.append("refresh reuse 401 PASS")

        access_header = _auth_header(access)

        def check_list(path: str):
            resp = client.get(path, headers=access_header)
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, dict) or "items" not in payload:
                raise SystemExit(f"unexpected shape for {path}: {payload}")
            steps.append(f"list {path} PASS")
            if payload.get("items"):
                return payload["items"][0]
            return None

        first_pet = check_list("/api/v1/pets?limit=1")
        check_list("/api/v1/matches?limit=1")
        check_list("/api/v1/pairs?limit=1")
        check_list("/api/v1/messages?pair_id=1&limit=1")

        if first_pet:
            photos = first_pet.get("photos") or []
            photo_url = first_pet.get("primary_photo_url") or (photos[0].get("url") if photos else None)
            if photo_url:
                media_resp = client.get(photo_url)
                media_resp.raise_for_status()
                steps.append(f"media {photo_url} PASS")
            else:
                steps.append("media skip (no photo)")
        else:
            steps.append("pet list empty")

        print("\n".join(steps))
    finally:
        client.close()


if __name__ == "__main__":
    main()
