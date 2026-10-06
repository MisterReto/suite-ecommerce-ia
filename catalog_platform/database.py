"""No implicit data migrations at web startup; production requires PostgreSQL."""

from contextlib import contextmanager
from functools import lru_cache
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def configured():
    return bool(os.getenv("DATABASE_URL"))


@lru_cache(maxsize=2)
def engine_for(url):
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    if not url.startswith("postgresql+psycopg://") and os.getenv("APP_ENV") != "test":
        raise RuntimeError(
            "El catálogo operativo requiere PostgreSQL. SQLite solo se permite en pruebas."
        )
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    else:
        options.update(
            pool_size=3,
            max_overflow=2,
            pool_timeout=15,
            connect_args={"connect_timeout": 10},
        )
    return create_engine(url, **options)


@contextmanager
def transaction():
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("Configura DATABASE_URL para activar el catálogo maestro.")
    with sessionmaker(bind=engine_for(url), expire_on_commit=False)() as db:
        with db.begin():
            yield db
        # Explicitly requested deliveries occur only after SQL committed. SQL is
        # the outbox: a Redis outage cannot erase an accepted job.
        ids = db.info.get("dispatch_ids", ())
        if ids:
            from .redis_broker import publish_committed

            publish_committed(ids)
