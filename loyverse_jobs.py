"""Small, session-owned upload jobs. No tokens, payloads, or job IDs in logs."""
from copy import deepcopy
import logging
import secrets
from threading import RLock, Thread
import time

log = logging.getLogger("uvicorn.error")
STATE_LOCK = RLock()
ACTIVE_STATES = {'queued', 'running'}


def status(value, job_id=None):
    with STATE_LOCK:
        job = value.get('loyverse_job')
        if not job or (job_id and job['id'] != job_id):
            return None
        return deepcopy(job)


def update(value, job_id, **fields):
    with STATE_LOCK:
        job = value.get('loyverse_job')
        if job and job['id'] == job_id:
            job.update(deepcopy(fields), updated_at=time.time())


def launch(value, preview_id, total, target):
    with STATE_LOCK:
        previous = value.get('loyverse_job')
        if previous and previous['preview_id'] == preview_id:
            return deepcopy(previous)  # Network retries never start a second write.
        if previous and previous['state'] in ACTIVE_STATES:
            raise ValueError('Ya hay una subida en curso. Consulta su progreso antes de enviar otra.')
        job = {'id': secrets.token_urlsafe(24), 'preview_id': preview_id, 'state': 'queued',
               'total': total, 'done': 0, 'current': None, 'phase': 'Preparando subida',
               'created': [], 'completed': [], 'uncertain': None, 'error': None,
               'started_at': time.time(), 'updated_at': time.time()}
        value['loyverse_job'] = job
        job_id = job['id']

    def runner():
        started = time.monotonic()
        try:
            update(value, job_id, state='running')
            result = target(lambda **fields: update(value, job_id, **fields))
            update(value, job_id, **result, state='error' if result.get('error') else 'done',
                   phase='Subida detenida' if result.get('error') else 'Subida terminada')
        except Exception:
            current = status(value, job_id) or {}
            update(value, job_id, state='error', phase='Subida detenida',
                   uncertain=current.get('current') if current.get('phase') == 'Enviando a Loyverse' else None,
                   error='No se pudo confirmar la operación. Revisa el resultado antes de reintentar.')
        finally:
            final = status(value, job_id) or {}
            log.info('loyverse_upload state=%s confirmed=%d total=%d seconds=%.1f',
                     final.get('state'), final.get('done', 0), total, time.monotonic()-started)

    try:
        Thread(target=runner, name='loyverse-upload', daemon=True).start()
    except Exception:
        update(value, job_id, state='error', error='No se pudo iniciar la subida. Vuelve a comparar.')
        raise ValueError('No se pudo iniciar la subida.') from None
    return status(value, job_id)
