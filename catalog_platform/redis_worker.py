"""Render supervisor: RQ processes, SQL heartbeat and outbox reconciliation."""
# Supervisor de procesos RQ, heartbeat SQL y reconciliación periódica.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

import logging
import os
import signal
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from . import queue, redis_broker
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


# Inicia el pool RQ, actualiza heartbeat y reconcilia SQL cada cinco segundos; un pool
# terminado provoca el reinicio del servicio.
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
    owner = "rq-supervisor-" + str(uuid.uuid4())
    logging.basicConfig(level=logging.INFO)
    try:
        while not stopped.is_set():
            if pool.poll() is not None:
                raise RuntimeError("El pool RQ terminó; Render debe reiniciar el worker.")
            queue.heartbeat(owner)
            redis_broker.reconcile()
            if ready is not None:
                ready.set()
            stopped.wait(5)
    finally:
        shutdown()
        # Render's shutdown window depends on the plan. Free does not allow an
        # extended delay; SQL records uncertain in-flight work after interruption.
        pool.wait()


if __name__ == "__main__":
    main()
