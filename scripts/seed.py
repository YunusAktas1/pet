from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlmodel import Session, select

# --- make project root importable even if CWD is different ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Now we can import our app packages
from backend.core.db import engine  # type: ignore
from backend.core.security import hash_password  # type: ignore
from backend.models.user import User  # type: ignore
from backend.models.pet import Pet  # type: ignore


def run() -> None:
    # Info: which ENV file is effective (Settings will default to backend/.env)
    env_file = os.environ.get("ENV_FILE", "backend/.env")
    print(
        "[seed] ENV_FILE={env_file}  (set ENV_FILE to backend/.env.local for host, or backend/.env.docker for compose)"
    )

    created_users = 0
    created_pets = 0

    with Session(engine) as session:
        # idempotent upsert-ish seed for a demo user
        email = "seed@example.com"
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            user = User(
                email=email,
                password_hash=hash_password("SeedPass123!"),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            created_users += 1
            print(f"[seed] created user: {user.email}")
        else:
            print(f"[seed] user already exists: {user.email}")

        # Add a couple of demo pets for that user if they don't exist
        def ensure_pet(name: str, species: str) -> None:
            nonlocal created_pets
            existing = session.exec(
                select(Pet).where(Pet.owner_id == user.id, Pet.name == name)
            ).first()
            if not existing:
                pet = Pet(owner_id=user.id, name=name, species=species)
                session.add(pet)
                session.commit()
                created_pets += 1
                print(f"[seed] created pet: {name} ({species})")
            else:
                print(f"[seed] pet already exists: {name}")

        ensure_pet("Mia", "cat")
        ensure_pet("Rex", "dog")

    print(f"[seed] done. users_created={created_users}, pets_created={created_pets}")


if __name__ == "__main__":
    run()
