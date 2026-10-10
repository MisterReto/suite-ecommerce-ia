"""Explicit initialization of a new empty staging DB; never migrate existing data."""
# Inicialización optativa únicamente de una base vacía; no migra un esquema existente incompleto.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

import os
from sqlalchemy import inspect, text
from .database import engine_for
from .models import Base


# Con autorización del flag, crea tablas solo si la base está vacía; exige migración
# explícita si existe un esquema incompleto.
def initialize_empty_database():
    if os.getenv("INITIALIZE_EMPTY_DATABASE", "false").lower() != "true":
        return False
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("Falta DATABASE_URL; no se inicializó la base vacía.")
    with engine_for(url).begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(726463190063)"))
        inspection = inspect(connection)
        existing = set(inspection.get_table_names())
        if not existing:
            Base.metadata.create_all(connection)
            return True
        if existing != set(Base.metadata.tables):
            raise RuntimeError("La base no está vacía ni tiene el esquema completo. Requiere revisión y migración manual.")
        for name, table in Base.metadata.tables.items():
            columns = {column["name"] for column in inspection.get_columns(name)}
            if not set(table.columns.keys()) <= columns:
                raise RuntimeError("El esquema existente está incompleto. No se aplicó ningún cambio automático.")
    return False
