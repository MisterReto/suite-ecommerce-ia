"""Transactional PostgreSQL and post-commit delivery; no implicit data migrations."""

from contextlib import contextmanager
from functools import lru_cache
import os
from sqlalchemy import create_engine, event, exc
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
    engine = create_engine(url, **options)

    @event.listens_for(engine, "connect")
    def mark_process(connection, record):
        record.info["pid"] = os.getpid()

    @event.listens_for(engine, "checkout")
    def require_own_connection(connection, record, proxy):
        # RQ forks jobs. A child must open its own socket, leaving the parent's
        # connection and psycopg prepared statements untouched.
        if record.info.get("pid") != os.getpid():
            record.dbapi_connection = proxy.dbapi_connection = None
            raise exc.DisconnectionError("Conexión SQL heredada; abrir una propia.")

    return engine


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
            from .worker_wakeup import notify
            notify()
            from .redis_broker import publish_committed

            publish_committed(ids)
