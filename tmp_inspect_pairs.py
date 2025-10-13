from sqlalchemy import text
from backend.core.db import engine

with engine.connect() as c:
    print("=== match rows ===")
    for row in c.execute(text('select id, owner_user_id, target_pet_id, decision, created_at from "match" order by id')):
        print(dict(row._mapping))
    print("\n=== pair rows ===")
    for row in c.execute(text('select * from pair order by id')):
        print(dict(row._mapping))