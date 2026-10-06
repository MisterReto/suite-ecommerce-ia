"""The separate UI origin does not bypass API Host or request-origin checks."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app_security import SecurityMiddleware


def client(monkeypatch, public="https://ui.example.com"):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://api.example.com")
    monkeypatch.setenv("APP_PUBLIC_ORIGIN", public)
    app = FastAPI()

    @app.post("/api/probe")
    def probe():
        return {"ok": True}

    app.add_middleware(SecurityMiddleware)
    return TestClient(app, base_url="https://api.example.com")


def test_configured_frontend_can_post_and_another_origin_cannot(monkeypatch):
    with client(monkeypatch) as api:
        assert api.post("/api/probe", headers={"Origin": "https://ui.example.com"}).status_code == 200
        assert api.post("/api/probe", headers={"Origin": "https://other.example.com"}).status_code == 403
        assert api.post("/api/probe", headers={"X-Forwarded-Host": "ui.example.com"}).status_code == 403
        assert api.post("/api/probe", headers={"Origin": "https://ui.example.com", "Host": "other.example.com"}).status_code == 400


def test_bad_public_origin_fails_closed(monkeypatch):
    with client(monkeypatch, "https://ui.example.com/unsafe") as api:
        assert api.post("/api/probe", headers={"Origin": "https://ui.example.com"}).status_code == 503


def test_compatible_deployment_keeps_same_origin(monkeypatch):
    with client(monkeypatch, "") as api:
        assert api.post("/api/probe", headers={"Origin": "https://api.example.com"}).status_code == 200
