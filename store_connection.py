"""Default to Drive-only: no WordPress/WooCommerce network traffic."""
import os


def drive_only() -> bool:
    # Fail closed, including missing or misspelled configuration.
    return os.getenv("SUITE_DRIVE_ONLY", "true").strip().lower() not in {"false", "0", "no", "off"}


def require_store_connection(error_type=RuntimeError):
    if drive_only():
        raise error_type("Modo solo Drive: conexión con WordPress y WooCommerce pausada.")
