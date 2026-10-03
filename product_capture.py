"""Gradio capture workflow, scoped to the connected customer's inventory."""
import hashlib
import io
from pathlib import Path
import re
import secrets
import textwrap
import time

import gradio as gr
from googleapiclient.http import MediaIoBaseDownload
from PIL import Image, ImageDraw, ImageFont, ImageOps

from catalog_capture import (barcode, family_name, next_parent_sku,
                             prepare_capture_updates, review_product, text)
from inventory_schema import MASTER_COLUMNS, is_variable_parent
from product_generation import branded_image

NEW_PARENT = "Crear nuevo padre"
EXISTING_PARENT = "Usar padre existente"


def read_barcodes(image):
    import zxingcpp
    if image is None:
        return []
    if isinstance(image, (str, Path)):
        with Image.open(image) as source:
            picture = ImageOps.exif_transpose(source).convert("RGB")
    else:
        picture = Image.fromarray(image).convert("RGB")
    picture.thumbnail((2400, 2400))
    formats = (zxingcpp.BarcodeFormat.EAN13, zxingcpp.BarcodeFormat.EAN8, zxingcpp.BarcodeFormat.UPCA, zxingcpp.BarcodeFormat.ITF)
    found = []
    for result in zxingcpp.read_barcodes(picture, formats=formats):
        try:
            code = barcode(result.text)
        except ValueError:
            continue
        if code and code not in found:
            found.append(code)
    return found


def compose_family_cover(pictures, title):
    """Faithful family cover: photos only; no invented flavors or package art."""
    if not pictures:
        raise ValueError("Necesito una foto real para preparar la portada.")
    canvas = Image.new("RGB", (1200, 1200), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=36)
    lines = textwrap.wrap(text(title)[:120], width=45)[:2]
    for index, line in enumerate(lines):
        box = draw.textbbox((0, 0), line, font=font)
        draw.text(((1200 - (box[2] - box[0])) // 2, 40 + index * 46), line, fill="#222222", font=font)
    pictures = pictures[:4]
    columns = 1 if len(pictures) == 1 else 2
    row_count = (len(pictures) + columns - 1) // columns
    width, height = 1080 // columns, 980 // row_count
    for index, picture in enumerate(pictures):
        image = ImageOps.contain(ImageOps.exif_transpose(picture).convert("RGB"), (width - 40, height - 40))
        x = 60 + index % columns * width + (width - image.width) // 2
        y = 150 + index // columns * height + (height - image.height) // 2
        canvas.paste(image, (x, y))
    return canvas


class ProductCapture:
    def __init__(self, backend):
        # globals() stays live when ai_app installs the canonical Sheet adapters.
        self.backend = backend

    def session(self, request):
        session, error = self.backend["_validar_sesion"](request, requiere_api_key=False)
        if error:
            raise ValueError(error)
        return session

    def snapshot(self, session):
        cached = session.get("capture_snapshot")
        if cached and time.monotonic() - cached[0] < 20:
            return cached[1]
        service, sheet, frame = self.backend["_cargar_df"](session)
        snapshot = (service, sheet, frame.to_dict("records"))
        session["capture_snapshot"] = (time.monotonic(), snapshot)
        return snapshot

    def check(self, sku, name, brand, size, code, parent, attribute, value, request: gr.Request):
        try:
            session = self.session(request)
            _, _, rows = self.snapshot(session)
            code = barcode(code)
            if not any(text(v) for v in (sku, name, code)):
                return "Analiza el producto o captura su código para verificar coincidencias."
            candidate = {"sku": sku, "nombre_producto": name, "Marca": brand, "gramaje": size,
                         "codigo_barras": code, "sku_padre": parent,
                         "atributo_nombre": attribute, "atributo_valor": value}
            result = review_product(rows, candidate)
            message = result["message"]
            if parent:
                options = [f"{text(r.get('atributo_valor')) or text(r.get('nombre_producto'))} ({text(r.get('sku'))})" for r in rows if text(r.get("sku_padre")) == parent]
                if options:
                    message += "\nOpciones ya registradas: " + "; ".join(options[:8])
            if code and result["status"] != "duplicate":
                message += "\nCódigo válido, sin coincidencia de código registrada. Los productos antiguos pueden no tener código; revisa también nombre y presentación."
            return message
        except Exception as error:
            return f"⚠️ No pude verificar: {error}"

    def scan(self, photo, current_code, request: gr.Request):
        try:
            self.session(request)
            codes = read_barcodes(photo)
            if len(codes) != 1:
                message = "No se leyó un código. Acerca la cámara, evita reflejos o escríbelo manualmente." if not codes else "Hay varios códigos en la foto. Encuadra solo el del producto o escríbelo manualmente."
                return current_code, message
            return codes[0], "✅ Código leído localmente. Pulsa Verificar producto para compararlo con tu inventario."
        except Exception:
            return current_code, "⚠️ No pude leer la foto; captura el código manualmente."

    def detect_from_product(self, front, back, current_code, request: gr.Request):
        try:
            session = self.session(request)
            codes = list(dict.fromkeys(read_barcodes(back) + read_barcodes(front)))
            previous = session.get("auto_barcode", "")
            result = codes[0] if len(codes) == 1 else (current_code if not codes and current_code != previous else "")
            session["auto_barcode"] = codes[0] if len(codes) == 1 else ""
            return result
        except Exception:
            return ""

    def load_parents(self, kind, mode, name, brand, sku, selected, request: gr.Request):
        visible = kind == "Variable"
        try:
            session = self.session(request)
            _, _, rows = self.snapshot(session)
            result = review_product(rows, {"sku": sku, "nombre_producto": name, "Marca": brand})
            parents = result["parents"]
            choices = [(f"{text(r.get('nombre_producto'))} · {text(r.get('Marca'))} · {text(r.get('sku'))}", text(r.get("sku"))) for r in parents]
            if not parents:
                mode = NEW_PARENT
            available = {value for _, value in choices}
            selected = selected if selected in available else (result["suggested"] or None)
            parent = next((r for r in parents if text(r.get("sku")) == selected), {})
            parent_sku = selected or ""
            title = text(parent.get("nombre_producto"))
            attribute = text(parent.get("atributo_nombre")) or "Tamaño"
            if mode == NEW_PARENT:
                parent_sku = next_parent_sku(name, brand, rows) if name else ""
                title = family_name(name)
            return (gr.update(choices=choices, value=selected, visible=visible and mode == EXISTING_PARENT),
                    gr.update(visible=visible, value=parent_sku, interactive=mode == NEW_PARENT),
                    gr.update(visible=visible), gr.update(value=title, interactive=mode == NEW_PARENT),
                    gr.update(value=attribute), gr.update(value=mode))
        except Exception:
            return (gr.update(choices=[], value=None, visible=visible), gr.update(visible=visible, value=""),
                    gr.update(visible=visible), gr.update(value=family_name(name)), gr.update(), gr.update())

    def select_parent(self, selected, request: gr.Request):
        try:
            _, _, rows = self.snapshot(self.session(request))
            parent = next(r for r in rows if text(r.get("sku")) == selected and is_variable_parent(r))
            return selected, text(parent.get("nombre_producto")), text(parent.get("atributo_nombre")) or "Tamaño"
        except Exception:
            return "", "", gr.update()

    def _namespace(self, session):
        return re.sub(r"[^a-zA-Z0-9_-]", "", session.setdefault("file_namespace", secrets.token_urlsafe(24)))[:64]

    def _references(self, session, reference):
        prefix = self._namespace(session) + "_"
        paths = self.backend["_rutas_referencia"](reference)
        if not paths or any(Path(path).parent != Path("/tmp") or not Path(path).name.startswith(prefix) for path in paths):
            raise ValueError("Analiza primero la foto del producto para preparar su portada.")
        return paths

    def stage_image(self, session, sku, slot, path, revision):
        if revision != session.get("capture_revision"):
            raise ValueError("La foto base cambió. Genera las imágenes del producto actual.")
        if slot not in {"1_hd", "2_uso", "3_comercial"} or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", sku):
            raise ValueError("Imagen de producto inválida.")
        picture = Path(path)
        if picture.parent != Path("/tmp") or not picture.name.startswith(self._namespace(session) + "_") or not picture.is_file():
            raise ValueError("La imagen no pertenece a esta sesión.")
        draft = session.get("product_images")
        if not draft or draft["sku"] != sku or draft["revision"] != revision:
            draft = {"sku": sku, "revision": revision, "files": {}}
            session["product_images"] = draft
        draft["files"][slot] = str(picture)

    def draft_images(self, session, sku):
        draft = session.get("product_images", {})
        if draft.get("sku") != sku or draft.get("revision") != session.get("capture_revision"):
            return []
        images = []
        for slot in ("1_hd", "2_uso", "3_comercial"):
            path = draft.get("files", {}).get(slot)
            if path:
                picture = Path(path)
                if picture.parent != Path("/tmp") or not picture.name.startswith(self._namespace(session) + "_") or not picture.is_file():
                    raise ValueError("Una vista previa ya no está disponible. Vuelve a generarla.")
                images.append((f"{sku}_{slot}.jpg", path))
        return images

    def _drive_picture(self, service, folder, name):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,140}", name):
            return None
        image_id = self.backend["_buscar_archivo"](service, name, folder)
        if not image_id:
            return None
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, service.files().get_media(fileId=image_id))
        done = False
        while not done:
            _, done = downloader.next_chunk()
            if buffer.tell() > 12 * 1024 * 1024:
                return None
        buffer.seek(0)
        with Image.open(buffer) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1200, 1200))
            return image

    def cover(self, kind, mode, parent, title, sku, reference, request: gr.Request):
        if kind != "Variable":
            return None, "", None
        try:
            session = self.session(request)
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", text(parent)) or parent == sku:
                raise ValueError("Elige un padre existente o crea un padre con SKU distinto al de la variación.")
            if not text(title):
                raise ValueError("Captura el nombre de la familia para la portada.")
            paths = self._references(session, reference)
            key = hashlib.sha256(repr((parent, title, sku, mode, session.get("capture_revision"), [(p, Path(p).stat().st_mtime_ns) for p in paths])).encode()).hexdigest()
            covers = session.setdefault("family_covers", {})
            for token, info in covers.items():
                if info["key"] == key and Path(info["path"]).is_file():
                    return info["path"], info["message"], token
            service, _, rows = self.snapshot(session)
            _, folder, _, logo_id = self.backend["_preparar_estructura"](service, session)
            pictures = []
            with Image.open(paths[0]) as source:
                pictures.append(ImageOps.exif_transpose(source).convert("RGB"))
            # Include siblings whose catalog HD photo actually exists in this Drive.
            included = {text(sku)}
            for row in rows:
                if len(pictures) == 4:
                    break
                child_sku = text(row.get("sku"))
                if text(row.get("sku_padre")) != parent or child_sku in included or is_variable_parent(row):
                    continue
                names = [n.strip() for n in text(row.get("imagenes")).split(",") if n.strip()]
                if not names:
                    names = [f"{child_sku}_1_hd.jpg", f"{child_sku}_1.png"]
                for name in names[:1]:
                    try:
                        picture = self._drive_picture(service, folder, name)
                    except Exception:
                        picture = None
                    if picture is not None:
                        pictures.append(picture)
                        included.add(child_sku)
                        break
            image = compose_family_cover(pictures, title)
            image = branded_image(image, self.backend["_cargar_logo_marca"](service, logo_id))
            token = secrets.token_urlsafe(18)
            path = f"/tmp/{self._namespace(session)}_{parent}_portada_{token}.jpg"
            image.save(path, format="JPEG", quality=95, optimize=True)
            message = f"✅ Portada del padre preparada con {len(pictures)} foto(s) reales y marca de agua. Se guardará al guardar la variación."
            if len(pictures) == 1:
                message += " Aún no hay fotos de otras variaciones disponibles; puedes actualizarla después."
            while len(covers) >= 8:
                old = covers.pop(next(iter(covers)))
                Path(old["path"]).unlink(missing_ok=True)
            covers[token] = {"key": key, "path": path, "parent": parent, "title": title,
                             "sku": sku, "mode": mode, "message": message,
                             "revision": session.get("capture_revision")}
            return path, message, token
        except ValueError as error:
            return None, f"⚠️ {error}", None
        except Exception:
            return None, "⚠️ No pude preparar la portada. Revisa la conexión y pulsa Actualizar portada.", None

    def regenerate_cover(self, kind, mode, parent, title, sku, reference, request: gr.Request):
        try:
            session = self.session(request)
            for info in session.get("family_covers", {}).values():
                if info["parent"] == parent:
                    info["key"] = ""  # Keep previews on disk; invalidate only the cache key.
        except ValueError:
            pass
        return self.cover(kind, mode, parent, title, sku, reference, request)

    def save(self, sku, kind, parent, name, brand, size, attribute, value, price,
             category, subcategory, tags, short, long, code, mode, title, cover_token,
             request: gr.Request):
        try:
            session = self.session(request)
            if not text(name):
                raise ValueError("Captura el nombre del producto.")
            session.pop("capture_snapshot", None)
            service, sheet, rows = self.snapshot(session)
            images = self.draft_images(session, text(sku))
            record = {"sku": text(sku), "tipo": "variation" if kind == "Variable" else "simple",
                      "sku_padre": text(parent) if kind == "Variable" else "", "nombre_producto": text(name),
                      "Marca": text(brand), "gramaje": text(size), "atributo_nombre": text(attribute),
                      "atributo_valor": text(value) or text(size), "precio": price or 0, "Existencias": 0,
                      "categorias": f"{category} > {subcategory}" if category and subcategory else text(category or subcategory),
                      "etiquetas": tags, "descripcion_corta": short, "descripcion_larga": long,
                      "codigo_barras": barcode(code),
                      "imagenes": ",".join(name for name, _ in images)}
            info = None
            if kind == "Variable":
                info = session.get("family_covers", {}).get(cover_token)
                if not info or (info["parent"], info["title"], info["sku"], info["mode"]) != (parent, title, sku, mode) or info.get("revision") != session.get("capture_revision") or not Path(info["path"]).is_file():
                    raise ValueError("Prepara o actualiza la portada del padre antes de guardar la variación.")
                record["_parent_cover"] = f"{parent}_portada_{cover_token}.jpg"
                if mode == NEW_PARENT:
                    record["_new_parent"] = {"sku": parent, "tipo": "variable", "sku_padre": "",
                        "nombre_producto": title, "Marca": brand, "categorias": record["categorias"], "etiquetas": tags,
                        "descripcion_corta": f"{title}. Selecciona una variación para consultar su presentación.",
                        "descripcion_larga": f"Familia de productos {title}. Selecciona una opción para consultar sus características, precio y disponibilidad."}
            # Validate before uploading; the adapter repeats validation on a fresh
            # Sheet snapshot under a lock before one atomic parent+child write.
            values = [list(MASTER_COLUMNS) + ["", "", "", "", "atributo_nombre", "atributo_valor", "codigo_barras"]]
            values += [[r.get(k, "") for k in MASTER_COLUMNS] + ["", "", "", "", r.get("atributo_nombre", ""), r.get("atributo_valor", ""), r.get("codigo_barras", "")] for r in rows]
            prepare_capture_updates(values, record)
            if images or info:
                _, folder, _, _ = self.backend["_preparar_estructura"](service, session)
                for filename, path in images:
                    self.backend["_subir_imagen_drive"](service, folder, filename, path)
            if info:
                self.backend["_subir_imagen_drive"](service, folder, record["_parent_cover"], info["path"])
            self.backend["_agregar_fila_google_sheet"](session, sheet, record)
            session.pop("capture_snapshot", None)
            detail = f" {len(images)} imagen(es) guardadas en Drive."
            if kind == "Variable":
                detail += f" Padre {parent} y portada vinculados."
            return f"💾 {sku} guardado en Lista completa.{detail}\nhttps://docs.google.com/spreadsheets/d/{sheet}/edit"
        except ValueError as error:
            return f"⛔ {error}"
        except Exception:
            return "❌ No pude completar el guardado. Revisa Drive y vuelve a verificar antes de reintentar."
