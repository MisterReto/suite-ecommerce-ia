"""Initial additive schema only. Never drops or rewrites existing Sheets/SQL data."""

import os
from sqlalchemy import inspect, text
from .database import engine_for
from .models import Base


def main():
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("Falta DATABASE_URL; no se creó ningún objeto.")
    Base.metadata.create_all(engine_for(url))
    engine = engine_for(url)
    if "batch_id" not in {c["name"] for c in inspect(engine).get_columns("rincon_generation_jobs")}:
        # Compatibility for a previously activated platform schema. Nullable,
        # additive only; the old worker can ignore it during rollback.
        with engine.begin() as db:
            db.execute(text("ALTER TABLE rincon_generation_jobs ADD COLUMN batch_id VARCHAR(36) REFERENCES rincon_generation_batches(id)"))
    print("Esquema inicial aditivo preparado; no se borraron datos.")


if __name__ == "__main__":
    main()
