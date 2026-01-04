
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

from sqlmodel import Session, select

# --- make project root importable even if CWD is different ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.config import settings  # type: ignore
from backend.core.db import engine  # type: ignore
from backend.core.security import hash_password  # type: ignore
from backend.models.message import Message  # type: ignore
from backend.models.match import Match, MatchDecision  # type: ignore
from backend.models.pair import Pair  # type: ignore
from backend.models.pet import Gender, Pet  # type: ignore
from backend.models.photo import Photo  # type: ignore
from backend.models.user import User  # type: ignore

SEED_PASSWORD = os.getenv("SEED_PASSWORD", "SeedPass123!")
SEED_EMAIL_1 = os.getenv("SEED_EMAIL_1", "seed@example.com")
SEED_EMAIL_2 = os.getenv("SEED_EMAIL_2", "seed2@example.com")


def get_or_create_user(session: Session, email: str, password: str) -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        print(f"[seed] user exists: {email}")
        return user
    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    print(f"[seed] created user: {email}")
    return user


def get_or_create_pet(session: Session, owner_id: int, name: str, species: str, gender: Gender = Gender.unknown) -> Pet:
    pet = session.exec(
        select(Pet).where(Pet.owner_id == owner_id, Pet.name == name)
    ).first()
    if pet:
        print(f"[seed] pet exists: {name}")
        return pet
    pet = Pet(owner_id=owner_id, name=name, species=species, gender=gender)
    session.add(pet)
    session.commit()
    session.refresh(pet)
    print(f"[seed] created pet: {name}")
    return pet


def ensure_photo(
    session: Session,
    pet: Pet,
    *,
    filename: str,
    url: str,
    mime: str = "image/jpeg",
    size: int = 1024,
    primary: bool = False,
) -> Photo:
    existing = session.exec(select(Photo).where(Photo.filename == filename)).first()
    if existing:
        return existing
    photo = Photo(
        pet_id=pet.id,
        filename=filename,
        mime_type=mime,
        size_bytes=size,
        url=url,
        is_primary=primary,
    )
    session.add(photo)
    session.commit()
    session.refresh(photo)
    return photo


def ensure_pair(session: Session, user_a: User, user_b: User) -> Pair:
    low, high = (user_a.id, user_b.id) if user_a.id < user_b.id else (user_b.id, user_a.id)
    pair = session.exec(
        select(Pair).where(Pair.user_low_id == low, Pair.user_high_id == high)
    ).first()
    if pair:
        print("[seed] pair exists")
        return pair
    pair = Pair(user_low_id=low, user_high_id=high)
    session.add(pair)
    session.commit()
    session.refresh(pair)
    print("[seed] created pair")
    return pair


def ensure_messages(session: Session, pair: Pair, senders: list[int], bodies: Iterable[str]) -> None:
    existing = list(session.exec(select(Message).where(Message.pair_id == pair.id)).all())
    existing_count = len(existing)
    bodies_list = list(bodies)
    to_create = max(0, len(bodies_list) - existing_count)
    for idx in range(to_create):
        sender = senders[idx % len(senders)]
        msg = Message(pair_id=pair.id, sender_user_id=sender, body=bodies_list[idx])
        session.add(msg)
    if to_create:
        session.commit()
        print(f"[seed] added {to_create} messages")
    else:
        print("[seed] messages already present")


def ensure_matches(session: Session, owner_id: int, target_pets: list[Pet]) -> None:
    decisions = [MatchDecision.liked, MatchDecision.passed, MatchDecision.undecided]
    created = 0
    for idx, pet in enumerate(target_pets):
        decision = decisions[idx % len(decisions)]
        existing = session.exec(
            select(Match).where(Match.owner_user_id == owner_id, Match.target_pet_id == pet.id)
        ).first()
        if existing:
            existing.decision = decision
            session.add(existing)
        else:
            session.add(Match(owner_user_id=owner_id, target_pet_id=pet.id, decision=decision))
            created += 1
    if target_pets:
        session.commit()
    print(f"[seed] matches ensured: {len(target_pets)} (created {created})")


def run() -> None:
    env_file = os.environ.get("ENV_FILE", "backend/.env")
    print(f"[seed] ENV_FILE={env_file} (override with ENV_FILE if needed)")

    with Session(engine) as session:
        demo_user = get_or_create_user(session, SEED_EMAIL_1, SEED_PASSWORD)
        other_user = get_or_create_user(session, SEED_EMAIL_2, SEED_PASSWORD)

        pet_a = get_or_create_pet(session, demo_user.id, "Mia", "cat", Gender.female)
        pet_b = get_or_create_pet(session, demo_user.id, "Rex", "dog", Gender.male)
        pet_c = get_or_create_pet(session, other_user.id, "Luna", "cat", Gender.female)

        ensure_photo(session, pet_a, filename="seed_mia_1.jpg", url="/media/seed_mia_1.jpg", primary=True)
        ensure_photo(session, pet_a, filename="seed_mia_2.jpg", url="/media/seed_mia_2.jpg")
        ensure_photo(session, pet_b, filename="seed_rex_1.jpg", url="/media/seed_rex_1.jpg", primary=True)

        pair = ensure_pair(session, demo_user, other_user)
        ensure_messages(session, pair, [demo_user.id, other_user.id], [
            "Hey there!",
            "Nice to meet you",
            "Want to schedule a playdate?",
            "Sure, sounds great",
            "See you soon!",
        ])

        ensure_matches(session, demo_user.id, [pet_c, pet_b, pet_a])

    print("[seed] complete")
    print("[seed] DEMO CREDENTIALS")
    print(f"[seed] email_1={SEED_EMAIL_1} password={SEED_PASSWORD}")
    print(f"[seed] email_2={SEED_EMAIL_2} password={SEED_PASSWORD}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
