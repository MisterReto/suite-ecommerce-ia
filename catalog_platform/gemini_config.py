"""Gemini credentials belong to the server, never to a browser or job snapshot."""
import os


def server_key():
    return os.getenv("GEMINI_API_KEY", "").strip()


def apply_server_key(value, *, allowed=True):
    key = server_key() if allowed else ""
    if key:
        value.update(gemini_key=key, gemini_source="render")
    else:
        value.pop("gemini_key", None)
        value["gemini_source"] = "not_configured"
