"""Derive the staging OAuth callback from Render's public frontend origin."""

import os
import re


def configure_redirect():
    if os.getenv("GOOGLE_REDIRECT_URI"):
        return
    base = os.getenv("GOOGLE_REDIRECT_BASE", "").rstrip("/")
    if not base:
        return
    if not re.fullmatch(r"https://[a-z0-9][a-z0-9-]*\.onrender\.com", base):
        raise RuntimeError("GOOGLE_REDIRECT_BASE debe ser el origen HTTPS público del frontend de Render.")
    os.environ["GOOGLE_REDIRECT_URI"] = base + "/auth/callback"
