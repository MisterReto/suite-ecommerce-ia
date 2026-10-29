"""Real file/ASGI/concurrency tests; no network or paid image generation."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
from pathlib import Path
import stat
import threading
import time
from types import SimpleNamespace

import pytest
from PIL import Image

from catalog_platform.image_delivery import drive_image, temporary_image
from product_capture import ProductCapture
from test_catalog_platform import setup, create, reference


def deliver(response, failure=None, headers=()):
    messages = []
    async def send(message):
        if failure and message["type"] == "http.response.body":
            raise failure
        messages.append(message)
    async def receive():
        return {"type": "http.disconnect"}
    asyncio.run(response({"type": "http", "method": "GET", "headers": headers,
        "asgi": {"spec_version": "2.4"},
        "extensions": {"http.response.pathsend": {}}}, receive, send))
    return messages


@pytest.mark.parametrize("failure", [None, OSError("disconnected"), asyncio.CancelledError()])
def test_temporary_response_removes_private_file_even_when_send_fails(failure):
    payload = b"x" * 200000
    response = temporary_image(lambda path: Path(path).write_bytes(payload), download=True)
    path = Path(response.path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == "attachment; filename=imagen-rincon"
    if failure:
        with pytest.raises(type(failure)):
            deliver(response, failure)
    else:
        messages = deliver(response)
        assert b"".join(m.get("body", b"") for m in messages) == payload
        assert max(len(m.get("body", b"")) for m in messages) <= 65536
    assert not path.exists()


def test_asgi_disconnect_cleans_up():
    response = temporary_image(lambda p: Path(p).write_bytes(b"x" * 200000))
    async def send(message):
        await asyncio.sleep(0)
    async def receive():
        return {"type": "http.disconnect"}
    asyncio.run(response({"type": "http", "method": "GET", "headers": [],
                          "asgi": {"spec_version": "2.0"}}, receive, send))
    assert not Path(response.path).exists()


def test_failed_download_removes_partial_file():
    paths = []
    def write(path):
        paths.append(Path(path))
        Path(path).write_bytes(b"partial")
        raise ValueError("forbidden")
    with pytest.raises(ValueError):
        temporary_image(write)
    assert paths and not paths[0].exists()


def test_ranges_cleanup_and_distinct_paths():
    a = temporary_image(lambda p: Path(p).write_bytes(b"abcdef"))
    b = temporary_image(lambda p: Path(p).write_bytes(b"ghijkl"))
    assert a.path != b.path
    messages = deliver(a, headers=[(b"range", b"bytes=1-3")])
    assert messages[0]["status"] == 206
    assert b"".join(m.get("body", b"") for m in messages) == b"bcd"
    deliver(b)
    assert not Path(a.path).exists() and not Path(b.path).exists()


def test_concurrent_downloads_are_bounded_and_not_buffered():
    lock = threading.Lock()
    counts = {"active": 0, "peak": 0}
    def write(file_id, path):
        with lock:
            counts["active"] += 1
            counts["peak"] = max(counts["peak"], counts["active"])
        try:
            time.sleep(.02)
            Path(path).write_bytes(file_id.encode())
        finally:
            with lock:
                counts["active"] -= 1
    drive = SimpleNamespace(download_to=write)
    def fetch(i):
        response = drive_image(lambda: drive, str(i), media_type="image/jpeg")
        messages = deliver(response)
        return b"".join(m.get("body", b"") for m in messages)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(fetch, range(8))) == [str(i).encode() for i in range(8)]
    assert counts["peak"] == 2 and counts["active"] == 0


@pytest.mark.parametrize("fmt,orientation", [("JPEG", 1), ("JPEG", 6), ("PNG", 1)])
def test_preview_uses_bounded_disk_download_preserving_orientation(monkeypatch, fmt, orientation):
    import product_capture
    raw = io.BytesIO()
    with Image.new("RGB", (2400, 1600), "red") as source:
        exif = Image.Exif(); exif[274] = orientation
        source.save(raw, fmt, exif=exif)
    class Download:
        def __init__(self, stream, request, chunksize):
            assert chunksize == 512 * 1024
            assert not isinstance(stream, io.BytesIO)
            self.stream = stream
        def next_chunk(self):
            self.stream.write(raw.getvalue())
            return None, True
    monkeypatch.setattr(product_capture, "MediaIoBaseDownload", Download)
    capture = ProductCapture({"_buscar_archivo": lambda *a: "image"})
    service = SimpleNamespace(files=lambda: SimpleNamespace(get_media=lambda **kw: None))
    with capture._drive_picture(service, "authorized-folder", "image.jpg") as result:
        assert result.mode == "RGB"
        assert result.size == ((800, 1200) if orientation == 6 else (1200, 800))
        assert result.getpixel((0, 0))[0] > 240


def test_drive_download_retains_ownership_check(tmp_path):
    from drive_service import DriveService
    drive = DriveService(None, "authorized")
    drive.owns = lambda _: False
    with pytest.raises(ValueError):
        drive_image(lambda: drive, "foreign", media_type="image/jpeg")


def test_client_lifecycle_is_bounded_before_construction():
    lock = threading.Lock()
    counts = {"active": 0, "peak": 0, "created": 0, "closed": 0}
    class Client:
        def __init__(self):
            with lock:
                counts["active"] += 1
                counts["created"] += 1
                counts["peak"] = max(counts["peak"], counts["active"])
            time.sleep(.01)  # Represents discovery/folder validation, before media I/O.
        def download_to(self, key, path):
            time.sleep(.01)
            Path(path).write_bytes(key.encode())
        def close(self):
            with lock:
                counts["active"] -= 1
                counts["closed"] += 1
    def fetch(i):
        response = drive_image(Client, str(i), media_type="image/jpeg")
        return b"".join(m.get("body", b"") for m in deliver(response))
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert list(pool.map(fetch, range(24))) == [str(i).encode() for i in range(24)]
    assert counts == {"active": 0, "peak": 2, "created": 24, "closed": 24}


def test_failed_media_download_closes_client_and_unlinks_partial_file():
    from unittest.mock import Mock
    paths = []
    def fail(key, path):
        paths.append(Path(path))
        Path(path).write_bytes(b"partial")
        raise ValueError("not authorized")
    client = SimpleNamespace(download_to=fail, close=Mock())
    with pytest.raises(ValueError, match="not authorized"):
        drive_image(lambda: client, "foreign", media_type="image/jpeg")
    client.close.assert_called_once()
    assert len(paths) == 1 and not paths[0].exists()


def test_failed_drive_folder_validation_closes_the_owned_client():
    from unittest.mock import Mock
    from drive_service import DriveService
    sdk = SimpleNamespace(close=Mock())
    value = {"email": "editor@example.test"}
    runtime = SimpleNamespace(_get_drive_service=Mock(return_value=DriveService(sdk)),
                              _preparar_estructura=Mock(side_effect=ValueError("wrong root")))
    with pytest.raises(ValueError, match="wrong root"):
        DriveService.for_session(runtime, value)
    sdk.close.assert_called_once()


@pytest.mark.parametrize("email,role", [("admin@example.test", "admin"),
                                      ("editor@example.test", "editor")])
def test_authorized_accounts_download_exact_bytes_with_session_doubles(setup, monkeypatch, email, role):
    """Simulated sessions only; does not claim live OAuth/Drive verification."""
    import json
    client, value, drive = setup
    monkeypatch.setenv("APP_ROLE_MAP", json.dumps({email: role}))
    value["email"] = email
    product = create(client)
    item = reference(client, product)
    response = client.get(f"/api/platform/images/{item['id']}?download=true")
    assert response.status_code == 200, response.text
    assert response.content == drive.files[item["drive_file_id"]]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith("attachment;")
    value["platform_tenant"] = "another-tenant"
    value["carpeta_raiz_id_manual"] = "another-tenant"
    assert client.get(f"/api/platform/images/{item['id']}").status_code == 404


def test_match_endpoint_closes_image_and_deletes_response_file(setup, monkeypatch):
    import studio_api
    client, _, _ = setup
    monkeypatch.setattr(studio_api.runtime.captura, "snapshot", lambda v:
                        (None, "sheet", [{"sku": "SKU", "imagenes": "SKU.jpg"}]))
    monkeypatch.setattr(studio_api.runtime, "_preparar_estructura", lambda *a:
                        ("root", "images", "sheet", None))
    image = Image.new("RGB", (120, 80), "red")
    monkeypatch.setattr(studio_api.runtime.captura, "_drive_picture", lambda *a: image)
    before = set(Path("/tmp").glob("rincon_image_*"))
    response = client.get("/api/matches/SKU/image")
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.content)) as preview:
        assert preview.size == (120, 80) and preview.format == "JPEG"
    with pytest.raises(ValueError):
        image.getpixel((0, 0))
    assert set(Path("/tmp").glob("rincon_image_*")) == before
