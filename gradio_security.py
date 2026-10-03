"""Bind Gradio state, event streams and cached files to their browser/session."""
import json
from pathlib import Path
import re
import secrets
from threading import Lock
import time
from urllib.parse import unquote


class GradioGuard:
    def __init__(self):
        self.owners = {}
        self.lock = Lock()

    def viewer(self, request, session):
        if session:
            return ("account", request.cookies.get("session_id")), None
        cookie = request.cookies.get("suite_ui", "")
        if re.fullmatch(r"[A-Za-z0-9_-]{43}", cookie):
            return ("browser", cookie), None
        cookie = secrets.token_urlsafe(32)
        return ("browser", cookie), cookie

    def bind(self, token, owner, *, create=False):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", token):
            return False
        with self.lock:
            now = time.monotonic()
            for key, value in list(self.owners.items()):
                if value[1] < now:
                    del self.owners[key]
            current = self.owners.get(token)
            if current:
                return current[0] == owner
            if not create or len(self.owners) >= 4096:
                return False
            self.owners[token] = (owner, now + 8 * 3600)
            return True

    def permits(self, request, session, owner, body=b""):
        path = request.url.path
        if not path.startswith("/gradio_api/"):
            return True
        route = path[len("/gradio_api/"):]
        # The browser UI uses queue/run. Unused direct API and mutable streaming
        # endpoints otherwise expose event identifiers without ownership checks.
        if route.startswith(("call/", "stream/")):
            return False
        if route == "queue/data":
            return self.bind(request.query_params.get("session_hash"), owner)
        if route.startswith("heartbeat/"):
            return self.bind(route.split("/", 1)[1], owner, create=True)
        if request.method == "POST" and (route == "queue/join" or route.startswith(("run/", "api/")) or route in {"cancel", "reset"}):
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    return False
                if not self.inputs_permitted(data, session):
                    return False
                return self.bind(data.get("session_hash"), owner, create=route not in {"cancel", "reset"})
            except (ValueError, TypeError):
                return False
        return True

    @classmethod
    def inputs_permitted(cls, value, session):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and not cls.file_permitted("file=" + value["path"], session):
                return False
            return all(cls.inputs_permitted(v, session) for v in value.values())
        if isinstance(value, list):
            return all(cls.inputs_permitted(v, session) for v in value)
        return True

    @staticmethod
    def file_permitted(path, session):
        if not session:
            return False
        try:
            target = Path(unquote(path.split("file=", 1)[1])).resolve()
            if str(target) in session.get("gradio_uploads", set()):
                return True
            namespace = session.get("file_namespace", "")
            return bool(namespace and target.name.startswith(namespace + "_") and target.is_relative_to(Path("/tmp")))
        except (ValueError, OSError):
            return False

    @staticmethod
    def register_uploads(session, raw):
        try:
            files = json.loads(raw)
            if isinstance(files, list) and all(isinstance(p, str) for p in files):
                owned = session.setdefault("gradio_uploads", set())
                for path in files:
                    if len(owned) < 128:
                        owned.add(str(Path(path).resolve()))
        except (ValueError, OSError):
            pass
