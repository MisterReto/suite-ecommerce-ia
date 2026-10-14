"""Run the repository's isolated regression groups without operational databases."""

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
GROUPS = [
    ("inventario", ["pytest", "test_stability.py", "test_generation_content.py", "test_catalog_capture.py", "test_bulk_security.py", "test_gemini_costs.py", "test_capture_workflow.py", "-q", "-p", "no:cacheprovider"]),
    ("plataforma", ["pytest", "test_studio_api.py", "test_creative_pipeline.py", "test_generation_contract.py", "test_catalog_platform.py", "test_catalog_controls.py", "test_frontend_separation.py", "test_functional_parity.py", "test_web_sessions.py", "test_native_tools.py", "test_integration_removal.py", "-q", "-p", "no:cacheprovider"]),
    ("recuperacion", ["pytest", "test_catalog_platform.py", "test_catalog_controls.py", "test_stabilization.py", "test_free_render.py", "test_functional_parity.py", "test_web_sessions.py", "-q", "-p", "no:cacheprovider"]),
    ("sheets-drive", ["pytest", "test_sheet_catalog_sync.py", "-q", "-p", "no:cacheprovider"]),
]


def main():
    if os.name == "nt":
        Path("/tmp").mkdir(exist_ok=True)
    environment = os.environ.copy()
    for key in (
        "DATABASE_URL", "REDIS_URL", "TEST_DATABASE_URL", "TEST_REDIS_URL",
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "GOOGLE_REDIRECT_BASE",
        "GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_DRIVE_FOLDER_ID", "GOOGLE_SHEET_ID",
        "CREDENTIAL_ENCRYPTION_KEY", "APP_PUBLIC_ORIGIN", "APP_ALLOWED_EMAILS", "APP_ROLE_MAP",
        "APP_DEFAULT_ROLE", "RENDER_EXTERNAL_URL", "SYNC_SERVICE_URL", "SYNC_SERVICE_SHARED_KEY",
        "AI_API_KEY", "WC_ALLOWED_EMAILS", "WC_URL", "WC_CONSUMER_KEY", "WC_CONSUMER_SECRET",
        "WOOCOMMERCE_URL", "WOOCOMMERCE_CONSUMER_KEY", "WOOCOMMERCE_CONSUMER_SECRET",
        "WORDPRESS_URL", "WP_URL", "WP_USERNAME", "WP_APP_PASSWORD", "LOYVERSE_ACCESS_TOKEN",
    ):
        environment.pop(key, None)
    environment.update(INITIALIZE_EMPTY_DATABASE="false", GRADIO_ANALYTICS_ENABLED="False", WC_WRITE_ENABLED="false", WP_MEDIA_WRITE_ENABLED="false", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    failed = []
    for name, arguments in GROUPS:
        print(f"Ejecutando {name}...", flush=True)
        result = subprocess.run([sys.executable, "-m", *arguments], cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
        log = ROOT / f"validacion-{name}.log"
        log.write_text(result.stdout, encoding="utf-8")
        summary = [line for line in result.stdout.splitlines() if " passed" in line or line.startswith("Ran ") or line.startswith("OK") or "FAILED" in line or "ERROR" in line]
        print(f"{name}: salida {result.returncode}; " + " | ".join(summary[-5:]), flush=True)
        if result.returncode:
            failed.append(name)
            print("\n".join(result.stdout.splitlines()[-35:]), flush=True)
        print(f"Log: {log.name}", flush=True)
    print("Grupos fallidos: " + (", ".join(failed) if failed else "ninguno"), flush=True)
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())
