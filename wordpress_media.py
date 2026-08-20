"""Cliente mínimo de WordPress Media usando Application Passwords."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, unquote
from urllib.request import Request, urlopen


class WordPressMediaError(RuntimeError):
    pass


class WordPressMediaClient:
    def __init__(self):
        self.base_url = os.getenv("WP_URL", os.getenv("WC_URL", "https://rincon.creandotusite.com")).rstrip("/")
        self.username = os.getenv("WP_USERNAME", "").strip()
        self.app_password = os.getenv("WP_APP_PASSWORD", "").strip()
        self.write_enabled = os.getenv("WP_MEDIA_WRITE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.timeout = max(5, int(os.getenv("WP_TIMEOUT", "30")))

    @property
    def configured(self) -> bool:
        return bool(self.username and self.app_password and self.base_url)

    def _auth(self) -> str:
        if not self.configured:
            raise WordPressMediaError("Faltan WP_URL, WP_USERNAME o WP_APP_PASSWORD en Render.")
        raw = f"{self.username}:{self.app_password}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _request(self, method: str, endpoint: str, *, params: dict[str, Any] | None = None,
                 body: bytes | None = None, content_type: str = "application/json",
                 extra_headers: dict[str, str] | None = None, require_write: bool = False) -> Any:
        if require_write and not self.write_enabled:
            raise WordPressMediaError("Subida de medios deshabilitada. Define WP_MEDIA_WRITE_ENABLED=true después de validar el preview.")
        url = f"{self.base_url}/wp-json/wp/v2/{endpoint.lstrip('/')}"
        if params:
            url += "?" + urlencode(params, doseq=True)
        headers = {
            "Authorization": self._auth(),
            "Accept": "application/json",
            "Content-Type": content_type,
            "User-Agent": "RinconDeAsia-SuiteEcommerceIA/1.0",
        }
        if extra_headers:
            headers.update(extra_headers)
        req = Request(url, data=body, method=method.upper(), headers=headers)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                data = response.read().decode("utf-8")
                return json.loads(data) if data else None
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise WordPressMediaError(f"WordPress HTTP {exc.code}: {detail[:600]}") from exc
        except URLError as exc:
            raise WordPressMediaError(f"No se pudo conectar con WordPress: {exc.reason}") from exc

    def health(self) -> dict[str, Any]:
        rows = self._request("GET", "users/me", params={"context": "edit"})
        return {
            "ok": True,
            "url": self.base_url,
            "configured": self.configured,
            "write_enabled": self.write_enabled,
            "user_id": rows.get("id") if isinstance(rows, dict) else None,
            "name": rows.get("name") if isinstance(rows, dict) else None,
        }

    @staticmethod
    def _source_filename(media: dict[str, Any]) -> str:
        source = str(media.get("source_url") or "")
        try:
            return unquote(PurePosixPath(urlparse(source).path).name)
        except Exception:
            return ""

    def find_media_by_filename(self, filename: str) -> dict[str, Any] | None:
        stem = PurePosixPath(filename).stem
        rows = self._request("GET", "media", params={"search": stem, "per_page": 100, "context": "edit"}) or []
        target = filename.casefold()
        for row in rows:
            if self._source_filename(row).casefold() == target:
                return row
        return None

    def upload_media(self, filename: str, data: bytes, *, mime_type: str | None = None,
                     alt_text: str = "", title: str = "") -> dict[str, Any]:
        if not filename:
            raise ValueError("Filename vacío.")
        mime_type = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        uploaded = self._request(
            "POST",
            "media",
            body=data,
            content_type=mime_type,
            extra_headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            require_write=True,
        )
        media_id = int(uploaded["id"])
        metadata = {}
        if alt_text:
            metadata["alt_text"] = alt_text
        if title:
            metadata["title"] = title
        if metadata:
            uploaded = self._request(
                "POST",
                f"media/{media_id}",
                body=json.dumps(metadata).encode("utf-8"),
                require_write=True,
            )
        return uploaded
