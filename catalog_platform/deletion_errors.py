"""Safe, actionable failures for the confirmed product-removal operation."""
import json

from googleapiclient.errors import HttpError


def google_failure(error):
    """Keep provider codes only, never its URL, message or credentials."""
    if not isinstance(error, HttpError):
        return None, "unknown"
    status = int(error.resp.status)
    try:
        reasons = json.loads(error.content).get("error", {}).get("errors", [])
        reason = reasons[0].get("reason", "unknown") if reasons else "unknown"
    except (ValueError, TypeError, AttributeError, IndexError, KeyError):
        reason = "unknown"
    known = {"insufficientFilePermissions", "insufficientPermissions", "forbidden",
             "storageQuotaExceeded", "userRateLimitExceeded", "rateLimitExceeded",
             "dailyLimitExceeded", "notFound", "authError", "backendError"}
    return status, reason if isinstance(reason, str) and reason in known else "unknown"


class DeletionError(Exception):
    def __init__(self, stage, message, *, status_code=503, cause_type="DriveCapabilityError",
                 provider_status=None, provider_reason="unknown"):
        super().__init__(message)
        self.stage, self.status_code = stage, status_code
        self.cause_type = cause_type
        self.provider_status, self.provider_reason = provider_status, provider_reason

    @classmethod
    def from_exception(cls, stage, error):
        status, reason = google_failure(error)
        code = 503
        if reason == "storageQuotaExceeded":
            message = "Google no pudo crear el respaldo por falta de espacio. Libera espacio en la cuenta de Drive y vuelve a intentarlo. El producto permanece en la app."
        elif reason in {"rateLimitExceeded", "userRateLimitExceeded", "dailyLimitExceeded"}:
            message = "Google alcanzó su límite de solicitudes. Inténtalo más tarde o revisa la cuota de Google. El producto permanece en la app."
        elif status == 403:
            code = 403
            target = "modificar inventario_completo" if stage == "sheet_delete" else "completar el respaldo o la eliminación en Drive"
            message = f"Google no permite a tu cuenta {target}. Revisa los permisos de Drive y de la hoja. El producto permanece en la app."
        elif status == 404:
            code = 409
            message = "Un archivo del producto o el inventario ya no está disponible para tu cuenta. Revisa su acceso en Drive; el producto permanece en la app."
        elif isinstance(error, ValueError):
            code = 409
            message = "No se pudo verificar el inventario o las imágenes del producto. Revisa duplicados y archivos fuera de la carpeta autorizada. El producto permanece en la app."
        else:
            message = "No se completó la eliminación en Drive. El producto permanece en la app; reintenta para terminar la operación."
        return cls(stage, message, status_code=code, cause_type=type(error).__name__,
                   provider_status=status, provider_reason=reason)
