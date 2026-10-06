"""Create a restrictive PostgreSQL dump. No destructive restore/migration commands."""

import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone


def main():
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Se requiere DATABASE_URL PostgreSQL.")
    root = Path(os.getenv("BACKUP_DIRECTORY", "/tmp/rincon-backups"))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / (
        "rincon-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".dump"
    )
    result = subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", "--file", str(path)],
        env={**os.environ, "PGDATABASE": url},
        capture_output=True,
    )
    if result.returncode:
        path.unlink(missing_ok=True)
        raise RuntimeError("No se completó el backup; no se ejecutó ninguna migración.")
    path.chmod(0o600)
    print("Backup PostgreSQL creado:", str(path))


if __name__ == "__main__":
    main()
