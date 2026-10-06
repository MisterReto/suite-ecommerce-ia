"""Render supervisor: RQ processes, SQL heartbeat and outbox reconciliation."""

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


def concurrency():
    try:
        value = int(os.getenv("IMAGE_WORKER_CONCURRENCY", "1"))
    except ValueError:
        raise RuntimeError("IMAGE_WORKER_CONCURRENCY debe ser un entero.") from None
    if not 1 <= value <= 8:
        raise RuntimeError("IMAGE_WORKER_CONCURRENCY debe estar entre 1 y 8.")
    return value


def main():
    cipher()
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("Falta DATABASE_URL; no se inició el worker.")
    if os.getenv("GENERATION_QUEUE_BACKEND") != "rq" or not redis_broker.reachable():
        raise RuntimeError("Configura Redis y GENERATION_QUEUE_BACKEND=rq.")
    count = concurrency()
    stopped = threading.Event()
    pool = subprocess.Popen(
        [str(Path(sys.executable).with_name("rq")), "worker-pool",
         "--config", "catalog_platform.rq_settings", "--serializer", "json",
         "--num-workers", str(count), "--logging-level", "WARNING"],
        start_new_session=True,
    )
    def shutdown(*_):
        stopped.set()
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
            stopped.wait(5)
    finally:
        shutdown()
        # Render gives the current job up to 300s. A second termination is left
        # to its process manager; SQL then records any uncertain in-flight work.
        pool.wait()


if __name__ == "__main__":
    main()
