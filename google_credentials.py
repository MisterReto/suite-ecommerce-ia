"""Optional dedicated account, shared-folder access only; no JSON files in git."""

import json
import os
from google.oauth2 import service_account


def dedicated_credentials():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        return None
    if not os.getenv("GOOGLE_DRIVE_FOLDER_ID"):
        raise RuntimeError("La cuenta dedicada requiere GOOGLE_DRIVE_FOLDER_ID.")
    try:
        info = json.loads(raw)
    except ValueError:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON tiene formato inválido."
        ) from None
    return service_account.Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )
