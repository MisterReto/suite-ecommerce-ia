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
        and publishable_image(item["name"])]


def publishable_image(name):
    """Only final numbered gallery files; references, raw files and backups stay private."""
    return bool(re.fullmatch(r"[A-Za-z0-9_-]+_\d+(?:_(?:hd|uso|comercial))?\.(?:jpg|jpeg|png|webp)", name, re.I))


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
        # Filter persisted job snapshots too, before the unchanged Colab selector
        # applies its slot priority. Old queued sources can contain raw originals.
        self.ns["ARCHIVOS"] = [file for file in self.ns["ARCHIVOS"] if publishable_image(file.get("name", ""))]
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
                raise ValueError(f"El SKU {sku} ya existe en la papelera de WooCommerce. "
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
        original_attributes = self.ns["atributos_padre"]

        def one_variation_axis(children):
            attrs = original_attributes(children)
            if len(attrs) > 1:
                raise ValueError("La familia debe usar un solo atributo de variación. "
                    "Revisa el nombre del atributo en sus variantes antes de subir.")
            return attrs

        self.ns["atributos_padre"] = one_variation_axis
        original_base = self.ns["datos_base"]

        def base_with_one_axis(row, kind, stock, tags):
            payload = original_base(row, kind, stock, tags)
            if kind == "variable":
                # Brand is descriptive metadata, never a second variation axis.
                payload.pop("attributes", None)
                if row.get("Marca", "").strip():
                    payload.setdefault("meta_data", []).append({"key": "_rincon_marca", "value": row["Marca"].strip()})
            return payload

        self.ns["datos_base"] = base_with_one_axis

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
                    if options["images"] else []} for row in rows], "new_status": options.get("status", "draft")}

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
        parent, selected, children = self.ns["resolver"](KINDS[kind], sku)
        existing = self.ns["buscar_producto"](parent["sku"])
        if existing and existing.get("type") not in {None, "simple" if kind == "simple" else "variable"}:
            raise ValueError("El SKU existente tiene otro tipo de producto en WooCommerce. Revisa la familia antes de continuar.")
        allow = options.get("allow_published_family", False)
        # A retry that only finds acknowledged variants performs no new writes.
        if existing and existing.get("status") == "publish" and selected and not allow:
            allow = all(self.ns["buscar_variacion"](existing["id"], row["sku"]) for row in selected)
        if options.get("status") == "publish" and existing and existing.get("status") not in {"draft", "publish"}:
            raise ValueError("Solo se pueden publicar productos nuevos o borradores. Revisa el estado en WooCommerce.")
        if existing and selected and any(not self.ns["buscar_variacion"](existing["id"], row["sku"]) for row in selected):
            if existing.get("status") == "publish" and not allow:
                raise ValueError("La familia ya está publicada. Autoriza añadir variantes a familias publicadas para continuar.")
            axis = self.ns["atributos_padre"](children)[0]
            remote_axes = [attr for attr in existing.get("attributes", []) if attr.get("variation")]
            if any(attr.get("name", "").casefold() != axis["name"].casefold() for attr in remote_axes):
                raise ValueError("La familia de WooCommerce usa otro atributo de variación. Revisa su atributo antes de añadir variantes.")
            old = remote_axes[0] if remote_axes else {}
            axis["options"] = list(dict.fromkeys([*old.get("options", []), *axis["options"]]))
            if old.get("id"):
                axis["id"] = old["id"]
            payload = {"attributes": [axis]}
            if parent.get("Marca", "").strip():
                payload["meta_data"] = [{"key":"_rincon_marca", "value":parent["Marca"].strip()}]
            if len(existing.get("attributes", [])) != 1 or not set(axis["options"]).issubset(old.get("options", [])):
                updated = self.ns["wc"]("PUT", f"products/{existing['id']}", data=payload)
                confirmed = [a for a in updated.get("attributes", []) if a.get("variation")]
                if (len(updated.get("attributes", [])) != 1 or len(confirmed) != 1
                        or confirmed[0].get("name", "").casefold() != axis["name"].casefold()
                        or not set(axis["options"]).issubset(confirmed[0].get("options", []))):
                    raise ValueError("WooCommerce no confirmó las opciones del atributo del padre. Revisa la familia antes de reintentar.")
                self.ns["registrar"]("atributo_padre_actualizado", sku=parent["sku"])
        self.ns["ejecutar"](KINDS[kind], sku, imagenes=options["images"], stock=options["stock"],
            tags=options["tags"], permitir_publicada=allow)
        if options.get("status") == "publish":
            # Keep the unchanged Colab creation logic. Publish only after every
            # selected variation has finished successfully; failures leave a draft.
            product = self.ns["buscar_producto"](parent["sku"])
            if not product:
                raise ValueError("No se encontró el producto creado para confirmar su publicación.")
            if product.get("status") != "publish" or product.get("catalog_visibility") == "hidden":
                result = self.ns["wc"]("PUT", f"products/{product['id']}",
                    data={"status": "publish", "catalog_visibility": "visible"})
                if result.get("status") != "publish" or result.get("catalog_visibility") != "visible":
                    raise ValueError("WooCommerce no confirmó la publicación. Revisa el producto antes de reintentar.")
                self.ns["registrar"]("producto_publicado", sku=parent["sku"], id=result["id"])
        return self.events

    def preflight(self, kind, sku, options=None, *, review_only=False):
        """Read the store before review; the worker repeats the lookup before writes."""
        warnings = []
        if connection_status()["configured"]:
            parent, selected, _ = self.ns["resolver"](KINDS[kind], sku)
            existing = self.ns["buscar_producto"](parent["sku"])
            if existing and existing.get("type") not in {None, "simple" if kind == "simple" else "variable"}:
                raise ValueError("El SKU existente tiene otro tipo de producto en WooCommerce. Revisa la familia antes de continuar.")
            if options and options.get("status") == "publish" and existing and existing.get("status") not in {"draft", "publish"}:
                raise ValueError("Solo se pueden publicar productos nuevos o borradores. Revisa el estado en WooCommerce.")
            if options and existing and existing.get("status") == "publish" and selected and not options.get("allow_published_family"):
                if any(not self.ns["buscar_variacion"](existing["id"], row["sku"]) for row in selected):
                    message = "La familia ya está publicada. Autoriza añadir variantes a familias publicadas para continuar."
                    if not review_only:
                        raise ValueError(message)
                    warnings.append(message)
            if existing and kind == "variant":
                self.ns["buscar_variacion"](existing["id"], selected[0]["sku"])
        return warnings


def fingerprint(source, selection, options):
    return hashlib.sha256(json.dumps({"source": source, "selection": selection, "options": options},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
