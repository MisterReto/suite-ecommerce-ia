"""Runtime bindings for the unchanged, accepted Colab product exporter."""
from copy import deepcopy
import html
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit, urlparse
from types import SimpleNamespace

import requests

CORE = Path(__file__).with_name("woocommerce_colab.py")
KINDS = {"simple": "Simple", "family": "Familia", "variant": "Variante"}
SHEET_DEFAULT = "1gnuDwcceWwN4ksNnyq3Hs_MQHTfnZQZjeLnph72aUrE"
IMAGES_DEFAULT = "1V4HgnTCRnwVGwrGD968eNdtvQDGGY7wt"
ALIASES = {
    "WOOCOMMERCE_URL": "WC_URL",
    "WOOCOMMERCE_CONSUMER_KEY": "WC_CONSUMER_KEY",
    "WOOCOMMERCE_CONSUMER_SECRET": "WC_CONSUMER_SECRET",
}


def secret(name):
    value = os.getenv(name) or os.getenv(ALIASES.get(name, ""))
    if not value:
        raise ValueError("Falta la variable de entorno: " + name)
    return value.strip()


def store_url():
    origin = secret("WOOCOMMERCE_URL").rstrip("/")
    parsed = urlsplit(origin)
    allowed = {name.strip().lower() for name in os.getenv(
        "WOOCOMMERCE_ALLOWED_HOSTS", "rincon.creandotusite.com").split(",") if name.strip()}
    if (parsed.scheme != "https" or parsed.hostname not in allowed or parsed.username
            or parsed.password or parsed.port or parsed.query or parsed.fragment or parsed.path):
        raise ValueError("WOOCOMMERCE_URL debe ser el origen HTTPS de la tienda autorizada.")
    return origin


def connection_status():
    missing = [name for name in ALIASES if not (os.getenv(name) or os.getenv(ALIASES[name]))]
    media_missing = [name for name in ("WP_USERNAME", "WP_APP_PASSWORD") if not os.getenv(name)]
    try:
        origin = store_url()
    except ValueError:
        origin = ""
        if not missing:
            missing.append("WOOCOMMERCE_URL")
    return {"configured": not missing, "images_configured": not media_missing,
            "missing": missing, "media_missing": media_missing, "store": origin}


def safe_error(exc):
    text = html.unescape(str(exc))
    for name in (*ALIASES, *ALIASES.values(), "WP_USERNAME", "WP_APP_PASSWORD"):
        value = os.getenv(name)
        if value:
            text = text.replace(value, "[redacted]")
    from app_security import public_error
    return public_error(ValueError(text))


class StoreSession(requests.Session):
    """Bind store-only HTTP, no redirects or write retries, and durable acknowledgments."""
    def __init__(self, origin, write=False, before=None, after=None):
        super().__init__()
        self.origin, self.write = origin, write
        self.before, self.after = before, after

    def request(self, method, url, **kwargs):
        if not url.startswith(self.origin + "/wp-json/"):
            raise ValueError("La petición no pertenece a la tienda configurada.")
        modifying = method.upper() not in {"GET", "HEAD", "OPTIONS"}
        if modifying and not self.write:
            raise ValueError("La vista previa no puede escribir en WooCommerce.")
        operation = {"method": method.upper(), "endpoint": url[len(self.origin):]}
        payload = kwargs.get("json") or {}
        if payload.get("sku"):
            operation["sku"] = payload["sku"]
        disposition = (kwargs.get("headers") or {}).get("Content-Disposition", "")
        if disposition:
            operation["filename"] = disposition.split('filename="', 1)[-1].rstrip('"')
        if self.before:
            self.before(operation, modifying)
        kwargs["allow_redirects"] = False
        response = super().request(method, url, **kwargs)
        if self.after:
            self.after(operation, modifying, response)
        if not response.ok and response.status_code != 406:
            try:
                detail = response.json()
            except ValueError:
                detail = None
            if isinstance(detail, dict) and isinstance(detail.get("message"), str):
                raise ValueError(f"WooCommerce: HTTP {response.status_code}. " + html.unescape(detail["message"]))
        return response


class BoundedSheets:
    """Keep the Colab row reader while bounding its existing A1 ranges by metadata."""
    def __init__(self, client, sheet_id):
        self.client, self.sheet_id = client, sheet_id
        metadata = client.spreadsheets().get(spreadsheetId=sheet_id,
            fields="sheets(properties(title,gridProperties(rowCount)))").execute()
        self.rows = {item["properties"]["title"]: item["properties"]["gridProperties"]["rowCount"]
                     for item in metadata.get("sheets", [])}

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, spreadsheetId, range, **kwargs):
        match = re.fullmatch(r"'([^']+)'!A1:([A-Z]+)", range)
        if spreadsheetId != self.sheet_id or not match or match[1] not in self.rows:
            raise ValueError("Pestaña de publicación no disponible.")
        count = self.rows[match[1]]
        if count > 10000:
            raise ValueError("La hoja supera el límite de lectura de publicación.")
        return self.client.spreadsheets().values().get(spreadsheetId=spreadsheetId,
            range=range + str(count), **kwargs)


def google_clients(value):
    from studio_api import runtime
    return runtime._get_sheets_service(value), runtime._get_drive_service(value)


def index_images(client, root):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", root):
        raise ValueError("Carpeta de imágenes inválida.")
    folder = client.files().get(fileId=root, supportsAllDrives=True,
        fields="id,name,mimeType,trashed").execute()
    if (folder.get("name") != "imagenes_generadas" or folder.get("trashed")
            or folder.get("mimeType") != "application/vnd.google-apps.folder"):
        raise ValueError("La carpeta de imágenes configurada debe ser imagenes_generadas.")
    from drive_service import DriveService
    return [item for item in DriveService(client, root).list(root,
        "mimeType contains 'image/'", fields="id,name,mimeType,size,parents,trashed", limit=20000)
        if root in item.get("parents", []) and not item.get("trashed")
        and item.get("mimeType", "").startswith("image/")
        and not any(char in item["name"] for char in ('\r', '\n', '"'))]


class Exporter:
    """Each execution gets private Colab globals; no request shares credentials/state."""
    def __init__(self, source=None, drive=None, write=False, before=None, after=None,
                 on_event=None, on_cache=None, media_cache=None):
        self.temp = tempfile.TemporaryDirectory(prefix="rincon-wc-")
        self.ns = {}
        exec(compile(CORE.read_text(encoding="utf8"), str(CORE), "exec"), self.ns)
        origin = store_url()
        session = StoreSession(origin, write, before, after)
        session.auth = (os.getenv("WOOCOMMERCE_CONSUMER_KEY") or os.getenv("WC_CONSUMER_KEY", ""),
                        os.getenv("WOOCOMMERCE_CONSUMER_SECRET") or os.getenv("WC_CONSUMER_SECRET", ""))
        session.headers.update(self.ns["HEADERS"])
        self.ns.update(URL=origin, WC_API=origin + "/wp-json/wc/v3", WP_API=origin + "/wp-json/wp/v2",
            secret=secret, wc_session=session, wp_session=None, drive_api=drive,
            requests=SimpleNamespace(Session=lambda: StoreSession(origin, write, before, after)),
            LOG_DIR=Path(self.temp.name), CACHE_PATH=Path(self.temp.name) / "media_cache.json",
            MEDIA_CACHE=deepcopy(media_cache or {}), MEDIA_SYNC={}, TERMINOS={}, REGISTRO=None,
            RUTA_REGISTRO=None, print=lambda *args, **kwargs: None,
            SIMPLES={}, PADRES={}, VARIANTES={}, COMPLETA={}, CSV_VARIANTES={}, ARCHIVOS=[])
        if source:
            self.ns.update(deepcopy(source))
        self.ns["MEDIA_CACHE"] = deepcopy(media_cache or {})
        self.events = []
        original_event = self.ns["registrar"]
        original_cache = self.ns["guardar_cache"]

        def record(action, **data):
            if "mensaje" in data:
                data["mensaje"] = safe_error(ValueError(data["mensaje"]))
            original_event(action, **data)
            event = {"action": action, **data}
            self.events.append(event)
            if on_event:
                on_event(event)

        def cache():
            original_cache()
            if on_cache:
                on_cache(deepcopy(self.ns["MEDIA_CACHE"]))

        self.ns["registrar"], self.ns["guardar_cache"] = record, cache
        original_product = self.ns["buscar_producto"]
        original_variation = self.ns["buscar_variacion"]

        def reject_trash(items, sku):
            item = next((item for item in items if item.get("sku") == sku), None)
            if item:
                raise ValueError(f"El SKU {sku} ya existe en la papelera de WooCommerce (ID {item['id']}). "
                    "Restaura ese producto en WordPress y revisa otra vez. Se detuvo la creación de ese SKU.")

        def find_product(sku):
            result = original_product(sku)
            if not result:
                reject_trash(self.ns["wc"]("GET", "products", params={"sku": sku, "status": "trash", "per_page": 100}), sku)
            return result

        def find_variation(parent_id, sku):
            result = original_variation(parent_id, sku)
            if not result:
                page = 1
                while True:
                    items = self.ns["wc"]("GET", f"products/{parent_id}/variations",
                        params={"status": "trash", "per_page": 100, "page": page})
                    reject_trash(items, sku)
                    if len(items) < 100:
                        break
                    page += 1
            return result

        self.ns["buscar_producto"], self.ns["buscar_variacion"] = find_product, find_variation

    def close(self):
        self.ns["wc_session"].close()
        if self.ns.get("wp_session"):
            self.ns["wp_session"].close()
        self.temp.cleanup()

    def load(self, value, include_images=True):
        sheets, drive = google_clients(value)
        sheet_id = os.getenv("WOOCOMMERCE_SHEET_ID") or os.getenv("GOOGLE_SHEET_ID") or SHEET_DEFAULT
        self.ns.update(sheets_api=BoundedSheets(sheets, sheet_id), SHEET_ID=sheet_id, drive_api=drive)
        reader = self.ns["leer_hoja"]
        definitions = [("SIMPLES", "Lista Simple", "N", "sku", "simple"),
            ("PADRES", "Lista Variable", "N", "sku", "variable"),
            ("VARIANTES", "Lista Variable", "N", "sku", "variation"),
            ("COMPLETA", "Lista completa", "U", "sku", None),
            ("CSV_VARIANTES", "CSV 2 Variaciones", "AS", "SKU", None)]
        read = {}
        for key, tab, columns, sku, kind in definitions:
            if tab not in read:
                read[tab] = reader(tab, columns)
            self.ns[key] = {row[sku]: row for row in read[tab] if row.get(sku)
                           and (kind is None or row.get("tipo", "").lower() == kind)}
        if include_images:
            self.ns["ARCHIVOS"] = index_images(drive, os.getenv("WOOCOMMERCE_IMAGES_FOLDER_ID", IMAGES_DEFAULT))
            for row in reader("Media Sync", "I"):
                fid, mid, media_url = row.get("drive_file_id"), row.get("wp_media_id"), row.get("wp_media_url", "")
                if fid and mid and str(mid).isdigit() and urlparse(media_url).netloc == urlparse(self.ns["URL"]).netloc:
                    self.ns["MEDIA_SYNC"][fid] = int(mid)
        return self

    def catalog(self):
        result = []
        for kind, key in (("simple", "SIMPLES"), ("family", "PADRES"), ("variant", "VARIANTES")):
            for sku, row in self.ns[key].items():
                result.append({"kind": kind, "sku": sku, "name": row.get("nombre_producto", ""),
                    "brand": row.get("Marca", ""), "category": row.get("categorias", ""),
                    "price": row.get("precio", ""), "parent_sku": self.ns["sku_padre"](row),
                    "variants": len(self.ns["hijos_familia"](sku)) if kind == "family" else 0})
        return result

    def preview(self, kind, sku, options):
        if kind not in KINDS:
            raise ValueError("Tipo de selección inválido.")
        try:
            parent, selected, all_children = self.ns["resolver"](KINDS[kind], sku)
        except KeyError:
            raise ValueError("El SKU no está en la hoja seleccionada.") from None
        self.ns["validar"](parent, selected, all_children, options["images"], options["stock"])
        rows = selected or [parent]
        return {"kind": kind, "sku": sku, "parent_sku": parent["sku"], "parent_name": parent.get("nombre_producto", ""),
            "items": [{"sku": row["sku"], "name": row.get("nombre_producto", ""),
                "brand": row.get("Marca", ""), "price": self.ns["precio"](row.get("precio")),
                "stock": row.get("Existencias", ""), "category": row.get("categorias", ""),
                "tags": row.get("etiquetas", "") if options["tags"] else "",
                "attribute": self.ns["atributo_variante"](row) if selected else None,
                "images": [{"id": f["id"], "name": f["name"]} for f in self.ns["fotos_sku"](row["sku"])]
                    if options["images"] else []} for row in rows], "new_status": "draft"}

    def snapshot(self, kind, sku):
        parent, selected, children = self.ns["resolver"](KINDS[kind], sku)
        skus = {parent["sku"], *(row["sku"] for row in children)}
        if not children:
            skus.add(sku)
        result = {key: {code: row for code, row in self.ns[key].items() if code in skus}
                  for key in ("SIMPLES", "PADRES", "VARIANTES", "COMPLETA", "CSV_VARIANTES")}
        result["ARCHIVOS"] = list({file["id"]: file for code in skus
            for file in self.ns["fotos_sku"](code)}.values())
        fids = {file["id"] for file in result["ARCHIVOS"]}
        result["MEDIA_SYNC"] = {fid: mid for fid, mid in self.ns["MEDIA_SYNC"].items() if fid in fids}
        return deepcopy(result)

    def execute(self, kind, sku, options):
        status = connection_status()
        if not status["configured"] or options["images"] and not status["images_configured"]:
            raise ValueError("Configura las credenciales de WooCommerce/WordPress antes de subir.")
        self.ns["ejecutar"](KINDS[kind], sku, imagenes=options["images"], stock=options["stock"],
            tags=options["tags"], permitir_publicada=options.get("allow_published_family", False))
        return self.events

    def preflight(self, kind, sku):
        """Read the store before review; the worker repeats the lookup before writes."""
        if connection_status()["configured"]:
            parent, selected, _ = self.ns["resolver"](KINDS[kind], sku)
            existing = self.ns["buscar_producto"](parent["sku"])
            if existing and kind == "variant":
                self.ns["buscar_variacion"](existing["id"], selected[0]["sku"])


def fingerprint(source, selection, options):
    return hashlib.sha256(json.dumps({"source": source, "selection": selection, "options": options},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
