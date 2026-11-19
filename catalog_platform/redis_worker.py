"""Render supervisor: RQ processes, Redis readiness and SQL outbox reconciliation."""
# Supervisor de procesos RQ, heartbeat Redis y reconciliación SQL periódica.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path
from . import redis_broker
from .security import cipher


# Valida el número de procesos de imagen entre 1 y 8; aumentar este valor puede aumentar RAM
# y gasto.
def concurrency():
    try:
        value = int(os.getenv("IMAGE_WORKER_CONCURRENCY", "1"))
    except ValueError:
        raise RuntimeError("IMAGE_WORKER_CONCURRENCY debe ser un entero.") from None
    if not 1 <= value <= 8:
        raise RuntimeError("IMAGE_WORKER_CONCURRENCY debe estar entre 1 y 8.")
    return value


def supervise(pool, stopped, ready):
    next_beat = next_scan = 0.0
    idle_delay, failure_delay = 5, 5
    healthy = False
    while not stopped.is_set():
        if pool.poll() is not None:
            raise RuntimeError("El pool RQ terminó; Render debe reiniciar el worker.")
        stamp = time.monotonic()
        try:
            if stamp >= next_scan:
                queued = redis_broker.reconcile()
                idle_delay = 5 if queued else min(600, idle_delay * 2)
                next_scan = stamp + idle_delay
                healthy = True
            if healthy and stamp >= next_beat:
                redis_broker.connection().set(redis_broker.heartbeat_key(), "1", ex=90)
                next_beat = stamp + 30
                if ready is not None:
                    ready.set()
                failure_delay = 5
        except (SQLAlchemyError, RedisError):
            logging.warning("Mantenimiento pendiente; se reintentará.")
            healthy = False
            next_scan = next_beat = stamp + failure_delay
            failure_delay = min(60, failure_delay * 2)
            if ready is not None:
                ready.clear()
        stopped.wait(5)


def main(ready=None):
    from .render_config import configure_redirect
    configure_redirect()
    cipher()
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("Falta DATABASE_URL; no se inició el worker.")
    if os.getenv("GENERATION_QUEUE_BACKEND") != "rq" or not redis_broker.reachable():
        raise RuntimeError("Configura Redis y GENERATION_QUEUE_BACKEND=rq.")
    count = concurrency()
    from .initialize import initialize_empty_database
    initialize_empty_database()
    stopped = threading.Event()
    pool = subprocess.Popen(
        [str(Path(sys.executable).with_name("rq")), "worker-pool",
         "--config", "catalog_platform.rq_settings", "--serializer", "json",
         "--num-workers", str(count), "--logging-level", "WARNING"],
        start_new_session=True,
    )
    # Detiene el grupo de procesos y retira la señal de readiness al recibir una señal de
    # apagado.
    def shutdown(*_):
        stopped.set()
        if ready is not None:
            ready.clear()
        if pool.poll() is None:
            os.killpg(pool.pid, signal.SIGTERM)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    logging.basicConfig(level=logging.INFO)
    try:
        supervise(pool, stopped, ready)
    finally:
        shutdown()
        # Render's shutdown window depends on the plan. Free does not allow an
        # extended delay; SQL records uncertain in-flight work after interruption.
        pool.wait()


if __name__ == "__main__":
    main()
