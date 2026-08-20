"""Cliente de WordPress Media con keep-alive y payloads pequeños."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse, unquote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class WordPressMediaError(RuntimeError):
    pass


class WordPressMediaClient:
    def __init__(self):
        self.base_url = os.getenv("WP_URL", os.getenv("WC_URL", "https://rincon.creandotusite.com")).rstrip("/")
        self.username = os.getenv("WP_USERNAME", "").strip()
        self.app_password = os.getenv("WP_APP_PASSWORD", "").strip()
        self.write_enabled = os.getenv("WP_MEDIA_WRITE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.timeout = max(10, int(os.getenv("WP_TIMEOUT", "60")))
        self.session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=1,
            status=2,
            backoff_factor=0.35,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

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
        headers = {
            "Authorization": self._auth(),
            "Accept": "application/json",
            "Content-Type": content_type,
            "User-Agent": "RinconDeAsia-SuiteEcommerceIA/1.0",
            "Connection": "keep-alive",
        }
        if extra_headers:
            headers.update(extra_headers)
        try:
            response = self.session.request(
                method.upper(),
                url,
                params=params,
                data=body,
                headers=headers,
                timeout=(10, self.timeout),
            )
            if response.status_code >= 400:
                raise WordPressMediaError(
                    f"WordPress HTTP {response.status_code}: {response.text[:600]}"
                )
            return response.json() if response.content else None
        except requests.RequestException as exc:
            raise WordPressMediaError(f"No se pudo conectar con WordPress: {exc}") from exc

    def health(self) -> dict[str, Any]:
        rows = self._request(
            "GET", "users/me",
            params={"context": "edit", "_fields": "id,name"},
        )
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
        rows = self._request(
            "GET", "media",
            params={
                "search": stem,
                "per_page": 20,
                "context": "edit",
                "_fields": "id,source_url",
            },
        ) or []
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
            params={"_fields": "id,source_url"},
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
            updated = self._request(
                "POST",
                f"media/{media_id}",
                params={"_fields": "id,source_url"},
                body=json.dumps(metadata).encode("utf-8"),
                require_write=True,
            )
            if updated:
                uploaded = updated
        return uploaded
