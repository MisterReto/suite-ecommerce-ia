"""Bounded private image delivery; temporary files belong to one response."""
from contextlib import contextmanager
import logging
import os
from pathlib import Path
import resource
import tempfile
import threading
import time

from starlette.responses import FileResponse

DOWNLOAD_SLOTS = threading.BoundedSemaphore(2)
PREVIEW_SLOTS = threading.BoundedSemaphore(1)
log = logging.getLogger("uvicorn.error")


def rss_bytes():
    try:
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return None


@contextmanager
def memory_operation(operation):
    """Process RSS, not exclusive operation allocation; never log IDs or credentials."""
    started, before = time.monotonic(), rss_bytes()
    log.info("image_memory operation=%s phase=start rss_bytes=%s", operation, before)
    try:
        yield
    finally:
        log.info("image_memory operation=%s phase=end rss_bytes=%s process_peak_kib=%s elapsed_ms=%d",
                 operation, rss_bytes(), resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 int((time.monotonic() - started) * 1000))


class TemporaryImageResponse(FileResponse):
    async def __call__(self, scope, receive, send):
        # pathsend may defer opening the file until after this call returns.
        scope = {**scope, "extensions": {k: v for k, v in scope.get("extensions", {}).items()
                                         if k != "http.response.pathsend"}}
        try:
            await super().__call__(scope, receive, send)
        finally:
            Path(self.path).unlink(missing_ok=True)


def temporary_image(writer, *, media_type="image/jpeg", download=False):
    fd, path = tempfile.mkstemp(prefix="rincon_image_", suffix=".jpg", dir="/tmp")
    os.close(fd)  # mkstemp creates a private 0600 file.
    try:
        writer(path)
        return TemporaryImageResponse(path, media_type=media_type,
            headers={"Cache-Control": "no-store", **(
                {"Content-Disposition": "attachment; filename=imagen-rincon"} if download else {})})
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def drive_image(drive_factory, file_id, *, media_type, download=False):
    def write(path):
        # Bound client construction and folder validation as well as the transfer.
        # Queued requests must not retain a Google SDK client while waiting here.
        with DOWNLOAD_SLOTS, memory_operation("catalog_download"):
            drive = drive_factory()
            try:
                drive.download_to(file_id, path)
            finally:
                close = getattr(drive, "close", None)
                if close:
                    close()
    return temporary_image(write, media_type=media_type, download=download)
