"""Real Gradio file routes plus isolated ownership checks; no external calls."""
import os
import secrets
import time
from pathlib import Path

os.environ.update(GOOGLE_CLIENT_ID="test", GOOGLE_CLIENT_SECRET="test", GOOGLE_REDIRECT_URI="https://suite.example/auth/callback", GRADIO_ANALYTICS_ENABLED="False", SUITE_SERVICE_ROLE="main")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from gradio.processing_utils import move_files_to_cache
from PIL import Image
import app_security
import service_entrypoint
import app


def test_real_gradio_preview_belongs_only_to_its_session(tmp_path):
    namespace = secrets.token_urlsafe(20)
    app.SESSIONS["owner"] = {"file_namespace": namespace, "expires_at": time.time()+600}
    app.SESSIONS["other"] = {"file_namespace": secrets.token_urlsafe(20), "expires_at": time.time()+600}
    source = Path("/tmp") / f"{namespace}_TEST_1_hd.jpg"
    Image.new("RGB", (16,16), "orange").save(source)
    data = move_files_to_cache(app.out_img1.postprocess(str(source)), app.out_img1, postprocess=True)
    try:
        with TestClient(service_entrypoint.fastapi_app, base_url="https://suite.example") as client:
            assert client.get(data["url"]).status_code == 401
            client.cookies.set("session_id", "owner")
            assert client.get(data["url"]).status_code == 200
            client.cookies.set("session_id", "other")
            assert client.get(data["url"]).status_code == 403
            assert client.get("/gradio_api/file=/etc/passwd").status_code == 403
            assert client.get("/gradio_api/file=https://example.com/private").status_code == 403
    finally:
        source.unlink(missing_ok=True)
        Path(data["path"]).unlink(missing_ok=True)
        app.SESSIONS.clear()


def test_real_upload_is_registered_and_cannot_be_read_by_another_session():
    import io
    image = io.BytesIO()
    Image.new("RGB", (16,16), "green").save(image, format="JPEG")
    app.SESSIONS.update({key:{"expires_at":time.time()+600} for key in ("owner","other")})
    path = None
    try:
        with TestClient(service_entrypoint.fastapi_app, base_url="https://suite.example") as client:
            client.cookies.set("session_id", "owner")
            response = client.post("/gradio_api/upload", files={"files":("input.jpg", image.getvalue(), "image/jpeg")}, headers={"origin":"https://suite.example"})
            assert response.status_code == 200
            path = response.json()[0]
            assert str(Path(path).resolve()) in app.SESSIONS["owner"]["gradio_uploads"]
            assert client.get("/gradio_api/file="+path).status_code == 200
            client.cookies.set("session_id", "other")
            assert client.get("/gradio_api/file="+path).status_code == 403
    finally:
        if path:
            Path(path).unlink(missing_ok=True)
        app.SESSIONS.clear()


def test_gradio_state_stream_cancel_and_file_input_are_scoped_to_owner():
    probe = FastAPI()
    @probe.get("/")
    def root():
        return {"ok":True}
    @probe.api_route("/gradio_api/{route:path}", methods=["GET","POST"])
    def api(route:str):
        return {"ok":True}
    sessions = {key:{"expires_at":time.time()+600} for key in ("owner","other")}
    probe.add_middleware(app_security.SecurityMiddleware, sessions=lambda:sessions)
    headers={"origin":"https://suite.example"}
    with TestClient(probe, base_url="https://suite.example") as client:
        client.cookies.set("session_id","owner")
        data={"session_hash":"private-state", "data":[]}
        assert client.post("/gradio_api/queue/join", json=data, headers=headers).status_code == 200
        assert client.get("/gradio_api/queue/data?session_hash=private-state").status_code == 200
        client.cookies.set("session_id","other")
        for route in ("queue/join", "run/check", "cancel", "reset"):
            assert client.post("/gradio_api/"+route, json=data, headers=headers).status_code == 403
        assert client.get("/gradio_api/queue/data?session_hash=private-state").status_code == 403
        assert client.get("/gradio_api/heartbeat/private-state").status_code == 403
        assert client.get("/gradio_api/call/check/event").status_code == 403
        assert client.post("/gradio_api/run/check", json={"session_hash":"own-state","data":[{"path":"/tmp/foreign.jpg"}]},headers=headers).status_code == 403
        client.cookies.delete("session_id")
        assert client.get("/").status_code == 200
        assert client.cookies.get("suite_ui")
        assert client.post("/gradio_api/queue/join",json={"session_hash":"anonymous-state","data":[]},headers=headers).status_code == 200
        assert client.get("/gradio_api/queue/data?session_hash=anonymous-state").status_code == 200
        client.cookies.clear()
        client.get("/")
        assert client.get("/gradio_api/queue/data?session_hash=anonymous-state").status_code == 403
