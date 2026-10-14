"""Check PostgreSQL TLS and catalog schema using a read-only transaction."""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog_platform.database import engine_for
from catalog_platform.models import Base


def main():
    load_dotenv(ROOT / ".env", override=False)
    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("Falta DATABASE_URL en .env o en el entorno. No se abrió una conexión.")
        return 1
    engine = None
    try:
        parsed = make_url(url)
        if not parsed.drivername.startswith("postgres") or not (parsed.host or "").endswith(".neon.tech"):
            print("DATABASE_URL debe apuntar a PostgreSQL de Neon. No se abrió una conexión.")
            return 1
        engine = engine_for(url)
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text("SET LOCAL statement_timeout = '15s'"))
                connection.execute(text("SELECT 1"))
                encrypted = connection.connection.driver_connection.pgconn.ssl_in_use
                if not encrypted:
                    print("ERROR: PostgreSQL no confirmó TLS. Revisa sslmode en DATABASE_URL.")
                    return 1
                inspection = inspect(connection)
                tables = set(inspection.get_table_names())
                missing_tables = sorted(set(Base.metadata.tables) - tables)
                missing_columns = {}
                for name, table in Base.metadata.tables.items():
                    if name in tables:
                        existing = {column["name"] for column in inspection.get_columns(name)}
                        missing = sorted(set(table.columns.keys()) - existing)
                        if missing:
                            missing_columns[name] = missing
                print("Conexión Neon: correcta. TLS: confirmado. Transacción: solo lectura.")
                print(f"Tablas esperadas presentes: {len(set(Base.metadata.tables) & tables)}/{len(Base.metadata.tables)}")
                if missing_tables or missing_columns:
                    print("Tablas faltantes: " + (", ".join(missing_tables) or "ninguna"))
                    for name, columns in missing_columns.items():
                        print(f"Columnas faltantes en {name}: {', '.join(columns)}")
                    return 1
                print("Esquema: todas las tablas y columnas esperadas están presentes.")
                print("Esta revisión no demuestra igualdad de datos con Render ni prueba Redis/worker.")
        return 0
    except Exception as error:
        print(f"Falló la comprobación ({type(error).__name__}). Revisa conexión, TLS y permisos sin compartir secretos.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
