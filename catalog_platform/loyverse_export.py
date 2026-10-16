"""Isolated bindings around the 23 unchanged functions supplied from Colab."""
from copy import deepcopy
import hashlib
import io
import json
import re
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import requests
from PIL import Image
from googleapiclient.http import MediaIoBaseDownload

API = "https://api.loyverse.com/v1.0"
SHEET_ID = "1gnuDwcceWwN4ksNnyq3Hs_MQHTfnZQZjeLnph72aUrE"
FOLDER_ID = "1V4HgnTCRnwVGwrGD968eNdtvQDGGY7wt"
KINDS = {"simple": "Simple", "family": "Familia", "variant": "Variante"}
CORE = Path(__file__).with_name("loyverse_colab.py")
MAX_IMAGE = 25 * 1024 * 1024


class ProviderError(ValueError):
    def __init__(self, status):
        self.status = status
        labels = {401: "Token inválido o vencido", 402: "Revisa la suscripción de la cuenta",
                  403: "El token no tiene los permisos requeridos", 429: "Límite de solicitudes alcanzado"}
        super().__init__(f"Loyverse: HTTP {status}. " + labels.get(status, "La operación no pudo completarse"))


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()


class LoyverseSession(requests.Session):
    """No redirects, deletes, stock writes or updates to existing variants/items."""
    def __init__(self, token, *, write=False, store_id=None, stores=(), before=None, after=None):
        super().__init__()
        self.headers.update({"Authorization": "Bearer " + token.strip(),
            "Accept": "application/json", "Content-Type": "application/json"})
        self.write, self.store_id, self.stores = write, store_id, list(stores)
        self.before, self.after, self.last_request = before, after, 0.0

    def request(self, method, url, **kwargs):
        method = method.upper()
        if not url.startswith(API + "/") or urlsplit(url).query or ".." in url:
            raise ValueError("Destino Loyverse inválido.")
        endpoint = url[len(API) + 1:].strip("/")
        image = bool(re.fullmatch(r"items/[A-Za-z0-9_-]+/image", endpoint))
        if method not in {"GET", "POST"} or not (endpoint in {"merchant", "stores", "items", "variants", "categories"}
                or re.fullmatch(r"items/[A-Za-z0-9_-]+", endpoint) or image):
            raise ValueError("Esta integración solo consulta y crea catálogo.")
        modifying = method == "POST"
        if modifying and (not self.write or not (endpoint in {"items", "variants", "categories"} or image)):
            raise ValueError("La lectura y la vista previa no pueden publicar.")
        payload = deepcopy(kwargs.get("json") or {})
        if modifying and not image:
            if any(key in payload for key in ("id", "variant_id", "in_stock", "stock", "inventory")):
                raise ValueError("No se permite modificar artículos, precios o existencias existentes.")
            variants = payload.get("variants", []) if endpoint == "items" else [payload] if endpoint == "variants" else []
            for variant in variants:
                if any(key in variant for key in ("id", "variant_id", "in_stock", "stock", "inventory", "stores")):
                    raise ValueError("Solo se crean variantes nuevas.")
                if not self.store_id or self.store_id not in self.stores:
                    raise ValueError("Selecciona una sucursal válida antes de publicar.")
                variant["stores"] = [{"store_id": store, "available_for_sale": store == self.store_id}
                                     for store in self.stores]
            kwargs["json"] = payload
        if method == "GET" and endpoint in {"items", "variants"}:
            kwargs["params"] = {**(kwargs.get("params") or {}), "show_deleted": "true"}
        op = {"method": method, "endpoint": endpoint}
        if payload.get("reference_id") or payload.get("sku"):
            op["sku"] = payload.get("reference_id") or payload["sku"]
        if endpoint == "items" and modifying:
            op["skus"] = [v["sku"] for v in payload.get("variants", [])]
        if payload.get("name"):
            op["category"] = payload["name"]
        for attempt in range(3 if not modifying else 1):
            if self.before:
                self.before(op, modifying)
            delay = 1.05 - (time.monotonic() - self.last_request)
            if delay > 0:
                time.sleep(delay)
            self.last_request = time.monotonic()
            try:
                response = super().request(method, url, allow_redirects=False, **kwargs)
            except requests.RequestException:
                # Raw provider/client errors can contain headers or response bodies.
                if not modifying and attempt < 2:
                    time.sleep(attempt + 1)
                    continue
                raise ValueError("Loyverse no respondió. Consulta el resultado antes de reintentar.") from None
            if self.after:
                self.after(op, modifying, response)
            if response.status_code in {429, 500, 502, 503, 504} and not modifying and attempt < 2:
                time.sleep(min(5, attempt + 1))
                continue
            if not 200 <= response.status_code < 300:
                raise ProviderError(response.status_code)
            return response


class LimitedBuffer(io.BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_IMAGE:
            raise ValueError("La imagen supera el límite de 25 MB.")
        return super().write(data)


class ImageDrive:
    """Revalidate a snapshotted image before downloading it in a later worker."""
    def __init__(self, client, files):
        self.client, self.allowed = client, {f["id"]: f for f in files}

    def files(self): return self

    def get_media(self, fileId):
        original = self.allowed.get(fileId)
        if not original:
            raise ValueError("Imagen fuera de la selección revisada.")
        info = self.client.files().get(fileId=fileId, supportsAllDrives=True,
            fields="id,name,mimeType,size,parents,trashed").execute()
        if (info.get("trashed") or FOLDER_ID not in info.get("parents", [])
                or info.get("name") != original["name"] or not info.get("mimeType", "").startswith("image/")
                or int(info.get("size") or 0) > MAX_IMAGE):
            raise ValueError("La imagen cambió de nombre, carpeta o disponibilidad desde la revisión.")
        return self.client.files().get_media(fileId=fileId)


def safe_open(stream):
    image = Image.open(stream)
    if image.width * image.height > 25_000_000:
        image.close()
        raise ValueError("La imagen supera el límite de dimensiones.")
    return image


def google_clients(value):
    from studio_api import runtime
    return runtime._get_sheets_service(value), runtime._get_drive_service(value)


class BoundedSheets:
    def __init__(self, client):
        self.client = client
        metadata = client.spreadsheets().get(spreadsheetId=SHEET_ID,
            fields="sheets(properties(title,gridProperties(rowCount)))").execute()
        self.rows = {s["properties"]["title"]: s["properties"]["gridProperties"]["rowCount"]
                     for s in metadata.get("sheets", [])}

    def spreadsheets(self): return self
    def values(self): return self

    def get(self, spreadsheetId, range):
        match = re.fullmatch(r"'([^']+)'!A1:([A-Z]+)", range)
        if spreadsheetId != SHEET_ID or not match or not 1 <= self.rows.get(match[1], 0) <= 10000:
            raise ValueError("Hoja de publicación no disponible o demasiado grande.")
        return self.client.spreadsheets().values().get(spreadsheetId=SHEET_ID,
            range=range + str(self.rows[match[1]]))


def index_images(client):
    """Only final, numbered files directly inside the supplied generated-image folder."""
    from drive_service import DriveService
    info = client.files().get(fileId=FOLDER_ID, supportsAllDrives=True,
        fields="id,name,mimeType,trashed").execute()
    if info.get("trashed") or info.get("name") != "imagenes_generadas" or info.get("mimeType") != "application/vnd.google-apps.folder":
        raise ValueError("La fuente de imágenes debe ser la carpeta imagenes_generadas indicada.")
    rows = DriveService(client, FOLDER_ID).list(FOLDER_ID, "mimeType contains 'image/'",
        fields="id,name,mimeType,size,parents,trashed", limit=20000)
    return [f for f in rows if not f.get("trashed") and FOLDER_ID in f.get("parents", [])
            and re.fullmatch(r"[A-Za-z0-9_-]+_\d+(?:_(?:hd|uso|comercial))?\.(?:jpe?g|png|webp)", f["name"], re.I)]


def keyed(rows, key, kind=None):
    result = {}
    for row in rows:
        if not row.get(key) or kind and row.get("tipo") != kind:
            continue
        sku = str(row[key]).strip()
        if sku in result:
            raise ValueError("SKU duplicado en Google Sheets: " + sku)
        result[sku] = {**row, key: sku}
    return result


class Exporter:
    def __init__(self, token, source=None, drive=None, **session_options):
        self.ns = {}
        exec(compile(CORE.read_text(encoding="utf8"), str(CORE), "exec"), self.ns)
        self.session = LoyverseSession(token, **session_options)
        self.ns.update(API=API, SHEET_ID=SHEET_ID, FOLDER_ID=FOLDER_ID, session=self.session,
            ITEMS=[], CATEGORIES=[], REF_INDEX={}, SKU_INDEX={}, IMAGE_FILES=[], drive_api=drive,
            SIMPLES={}, PADRES={}, VARIANTES={}, EXTRA={}, CSV_V={})
        # Preserve Colab image processing while bounding actual download size/pixels.
        self.ns["io"] = SimpleNamespace(BytesIO=LimitedBuffer)
        self.ns["Image"] = SimpleNamespace(open=safe_open, new=Image.new)
        if source:
            self.ns.update(deepcopy(source))

    def close(self): self.session.close()

    def bind_drive(self, drive):
        self.ns["drive_api"] = ImageDrive(drive, self.ns["IMAGE_FILES"])

    def identity(self):
        merchant = self.ns["api"]("GET", "merchant/")
        stores = self.ns["listar"]("stores", "stores")
        if not isinstance(merchant.get("id"), str) or not merchant["id"]:
            raise ValueError("Loyverse no devolvió la identidad de la cuenta.")
        stores = [{"id": s["id"], "name": s["name"]} for s in stores if not s.get("deleted_at")]
        if not stores:
            raise ValueError("La cuenta no tiene sucursales disponibles.")
        return {"merchant_id": merchant["id"], "merchant_name": merchant.get("business_name") or "Cuenta Loyverse", "stores": stores}

    def remote(self):
        self.ns["ITEMS"] = self.ns["listar"]("items", "items")
        self.ns["CATEGORIES"] = [c for c in self.ns["listar"]("categories", "categories") if not c.get("deleted_at")]
        self.ns["REF_INDEX"], self.ns["SKU_INDEX"] = {}, {}
        self.duplicate_refs = set()
        for item in self.ns["ITEMS"]:
            reference = item.get("reference_id")
            if reference and reference in self.ns["REF_INDEX"]:
                self.duplicate_refs.add(reference)
            self.ns["indexar_item"](item)
        return self

    def load(self, value, images=False):
        sheets, drive = google_clients(value)
        self.ns.update(sheets=BoundedSheets(sheets), drive_api=drive)
        simple, variable, extra, variants = [self.ns["leer"](name, columns) for name, columns in (
            ("Lista Simple", "N"), ("Lista Variable", "N"), ("Lista completa", "U"), ("CSV 2 Variaciones", "AS"))]
        self.ns.update(SIMPLES=keyed(simple, "sku", "simple"), PADRES=keyed(variable, "sku", "variable"),
            VARIANTES=keyed(variable, "sku", "variation"), EXTRA=keyed(extra, "sku"), CSV_V=keyed(variants, "SKU"),
            IMAGE_FILES=index_images(drive) if images else [])
        return self

    def resolve(self, selection):
        return self.ns["resolver"](KINDS[selection["kind"]], selection["sku"])

    def snapshot(self, selection):
        parent, chosen, all_children = self.resolve(selection)
        skus = {parent["sku"], *[v["sku"] for v in all_children]}
        return {key: {sku: deepcopy(row) for sku, row in self.ns[key].items() if sku in skus}
                for key in ("SIMPLES", "PADRES", "VARIANTES", "EXTRA", "CSV_V")} | {
            "IMAGE_FILES": [deepcopy(f) for sku in skus if (f := self.ns["imagen_principal"](sku))]}

    def review(self, selection, options):
        parent, chosen, _ = self.resolve(selection)
        if parent["sku"] in getattr(self, "duplicate_refs", set()):
            raise ValueError("Hay más de un artículo con este SKU padre de referencia. Revísalo en Loyverse.")
        if chosen:
            self.ns["construir_familia"](parent, chosen, False)
        else:
            self.ns["construir_simple"](parent, False)
        existing = self.ns["padre_existente"](parent)
        if existing and existing.get("deleted_at"):
            raise ValueError("El artículo está eliminado en Loyverse. Revísalo manualmente.")
        if existing and chosen:
            if existing.get("option2_name") or existing.get("option3_name"):
                raise ValueError("La familia existente tiene más de un atributo de variación.")
            expected = self.ns["atributo"](chosen[0])[0]
            if (existing.get("option1_name") or "").casefold() != expected.casefold():
                raise ValueError("El atributo de la familia existente es incompatible.")
        result = []
        for row in chosen or [parent]:
            remote = self.ns["variante_existente"](row["sku"])
            if remote and remote.get("deleted_at"):
                raise ValueError("El SKU está eliminado en Loyverse: " + row["sku"])
            if remote and chosen and (not existing or remote.get("item_id") != existing["id"]):
                raise ValueError("El SKU pertenece a otra familia: " + row["sku"])
            image = self.ns["imagen_principal"](parent["sku"]) or self.ns["imagen_principal"](row["sku"])
            if image and int(image.get("size") or 0) > MAX_IMAGE:
                raise ValueError("Imagen original demasiado grande: " + image["name"])
            result.append({"sku": row["sku"], "name": row.get("nombre_producto", ""),
                "price": self.ns["precio"](row), "barcode": self.ns["barcode"](row),
                "description": self.ns["descripcion"](parent), "category": parent.get("categorias", ""),
                "brand": parent.get("Marca", ""), "attribute": self.ns["atributo"](row) if chosen else None,
                "action": "existing" if remote or not chosen and existing else "create",
                "image_name": image["name"] if image and options["images"] and not existing else None})
        return {**selection, "parent_sku": parent["sku"], "parent_name": parent.get("nombre_producto", ""),
            "items": result, "shared_catalog": True}

    def catalog(self):
        result = []
        for kind, key in (("simple", "SIMPLES"), ("family", "PADRES"), ("variant", "VARIANTES")):
            for sku, row in self.ns[key].items():
                skus = [v["sku"] for v in self.ns["hijos"](sku)] if kind == "family" else [sku]
                present = sum(s in self.ns["SKU_INDEX"] for s in skus)
                state = "existing" if skus and present == len(skus) else "partial" if present else "missing"
                if kind == "family" and sku in self.ns["REF_INDEX"] and not present:
                    state = "partial"
                result.append({"sku": sku, "kind": kind, "name": row.get("nombre_producto", ""),
                    "category": row.get("categorias", ""), "brand": row.get("Marca", ""),
                    "price": row.get("precio", ""), "variants": len(skus) if kind == "family" else 0,
                    "parent_sku": self.ns["parent_sku"](row) if kind == "variant" else "", "comparison": state})
        return result

    def remote_rows(self, store_id):
        categories = {c["id"]: c["name"] for c in self.ns["CATEGORIES"]}
        return [{"sku": variant.get("sku", ""), "name": item.get("item_name", ""),
            "category": categories.get(item.get("category_id"), ""),
            "price": next((s.get("price") if s.get("price") is not None else variant.get("default_price") for s in variant.get("stores", [])
                           if s["store_id"] == store_id), variant.get("default_price")),
            "available": next((s.get("available_for_sale", True) for s in variant.get("stores", [])
                               if s["store_id"] == store_id), True),
            "parent_sku": item.get("reference_id", ""),
            "deleted": bool(item.get("deleted_at") or variant.get("deleted_at"))}
            for item in self.ns["ITEMS"] for variant in item.get("variants", [])]

    def execute(self, selection, options, event):
        self.ns["crear_seleccion"](KINDS[selection["kind"]], selection["sku"],
            options["images"], options["create_categories"], event)


def preview_bytes(drive, file):
    stream = LimitedBuffer()
    loader = MediaIoBaseDownload(stream, ImageDrive(drive, [file]).get_media(fileId=file["id"]), chunksize=1024 * 1024)
    done = False
    while not done:
        _, done = loader.next_chunk()
    stream.seek(0)
    with safe_open(stream) as image:
        from PIL import ImageOps
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((800, 800))
        output = io.BytesIO()
        image.save(output, "JPEG", quality=85)
    stream.close()
    return output.getvalue()


def bounded_entries(selection, source, size=50):
    """Split large families into small snapshots consumed by the unchanged resolver."""
    if selection["kind"] != "family" or len(source["VARIANTES"]) <= size:
        return [{"selection": selection, "source": source, "part": 0}]
    skus = list(source["VARIANTES"])
    result = []
    for index in range(0, len(skus), size):
        snapshot = deepcopy(source)
        snapshot["VARIANTES"] = {sku: snapshot["VARIANTES"][sku] for sku in skus[index:index + size]}
        result.append({"selection": selection, "source": snapshot, "part": len(result)})
    return result
