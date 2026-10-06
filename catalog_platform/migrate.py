"""Initial additive schema only. Never drops or rewrites existing Sheets/SQL data."""

import os
from .database import engine_for
from .models import Base


def main():
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("Falta DATABASE_URL; no se creó ningún objeto.")
    Base.metadata.create_all(engine_for(url))
    print("Esquema inicial aditivo preparado; no se borraron datos.")


if __name__ == "__main__":
    main()
