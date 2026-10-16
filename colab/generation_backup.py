"""Colab I/O adapter; all creative instructions come from the frozen app modules.

This module never imports the API, opens a database or publishes to WooCommerce.
It can be tested with a synthetic client without spending Gemini credits.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
import threading
import unicodedata
import uuid

import pandas as pd
from PIL import Image, ImageOps
import requests

import creative_pipeline as creative
from gemini_gateway import GeminiClient, image_part
from product_generation import branded_image


def cell(row, *names):
    for name in names:
        value = row.get(name, "")
        if value is not None and str(value).strip() and str(value).casefold() != "nan":
            return str(value).strip()
    return ""


def header(value):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def valid_image(path):
    try:
        with Image.open(path) as picture:
            width, height = picture.size
            picture.verify()
        return width == height and min(width, height) >= 1024
    except (OSError, ValueError):
        return False


class ColabGenerator:
    def __init__(self, base, *, csv_path=None, output=None, logo=None, api_key=None, client=None):
        import app_generation_contract as contract
        self.contract = contract
        self.base = Path(base).expanduser().resolve()
        self.csv_path = Path(csv_path).expanduser().resolve() if csv_path else self.base / "inventario_completo.csv"
        self.output = Path(output).expanduser().resolve() if output else self.base / "imagenes_generadas"
        self.logo = Path(logo).expanduser().resolve() if logo else self.base / "logo_rincon_asia.png"
        if not self.logo.is_file():
            self.logo = Path(contract.__file__).parent / "rincon-logo.png"
        self.work = self.base / "colab_respaldo_generacion"
        self.work.mkdir(parents=True, exist_ok=True)
        self.state_path = self.work / "estado.json"
        self.lock = threading.RLock()
        self.busy = threading.Lock()
        self.stop_event = threading.Event()
        self.client = client
        self._key = api_key
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"items": {}, "plans": {}}
        self.styles = None

    def _client(self):
        if self.client is None:
            if not self._key:
                try:
                    from google.colab import userdata
                    self._key = userdata.get("GEMINI_API_KEY")
                except Exception:
                    pass
            if not self._key:
                from getpass import getpass
                self._key = getpass("Gemini API key (no se guarda en el notebook): ").strip()
            if not self._key:
                raise ValueError("Configura GEMINI_API_KEY en Secrets de Colab.")
            self.client = GeminiClient(self._key)
        return self.client

    def _persist(self):
        # Caller holds the instance lock. A partial JSON file never replaces state.
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2))
        temporary.replace(self.state_path)

    def inventory(self):
        last_error = None
        for encoding in ("utf-8-sig", "latin-1"):
            for separator in (",", ";"):
                try:
                    frame = pd.read_csv(self.csv_path, dtype=str, keep_default_na=False, sep=separator, encoding=encoding)
                    if len(frame.columns) < 2:
                        continue
                    frame.columns = [header(name) for name in frame.columns]
                    if frame.columns.duplicated().any():
                        raise ValueError("Hay encabezados duplicados en el CSV.")
                    if not {"sku", "nombre_producto"}.issubset(frame.columns):
                        continue
                    return frame.to_dict("records")
                except (ValueError, UnicodeError) as exc:
                    last_error = exc
        raise ValueError("No se pudo leer inventario_completo.csv; requiere sku y nombre_producto.") from last_error

    def _product(self, row):
        sku = cell(row, "sku")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", sku):
            raise ValueError("SKU inválido: usa 1–80 letras, números, guiones o guiones bajos.")
        name = cell(row, "nombre_producto", "name")
        if not name:
            raise ValueError("Falta nombre_producto.")
        category = cell(row, "categorias", "categoria", "category")
        parts = [part.strip() for part in category.split(">", 1)]
        return {"sku": sku, "name": name, "brand": cell(row, "marca", "brand"),
                "size": cell(row, "presentacion", "gramaje", "size", "atributo_valor"),
                "category": parts[0], "subcategory": parts[1] if len(parts) == 2 else cell(row, "subcategoria"),
                "short_description": cell(row, "descripcion_corta", "short_description"),
                "description": cell(row, "descripcion_larga", "description", "long_description")}

    def _record(self, sku, slot):
        return self.state["items"].get(sku + ":" + slot, {})

    def audit(self, rows=None, slots=None):
        rows = self.inventory() if rows is None else rows
        slots = list(creative.SLOTS if slots is None else slots)
        if not slots or any(slot not in creative.SLOTS for slot in slots):
            raise ValueError("Selecciona 1_hd, 2_uso o 3_comercial.")
        counts = {}
        for row in rows:
            sku = cell(row, "sku")
            counts[sku] = counts.get(sku, 0) + 1
        results = []
        for row in rows:
            sku = cell(row, "sku")
            try:
                product = self._product(row)
                if counts[sku] != 1:
                    raise ValueError("SKU duplicado en el CSV; corrige sus filas antes de generar.")
                pending, staged, uncertain = [], [], []
                for slot in slots:
                    entry = self._record(sku, slot)
                    if entry.get("status") in {"processing", "uncertain"}:
                        uncertain.append(slot)
                    elif entry.get("status") == "candidate" and valid_image(entry.get("image", "")):
                        staged.append(slot)
                    elif not valid_image(self.output / f"{sku}_{slot}.jpg"):
                        pending.append(slot)
                results.append({"sku": sku, "nombre_producto": product["name"], "imagenes_faltantes": ",".join(pending),
                                "por_revisar": ",".join(staged), "resultado_incierto": ",".join(uncertain), "advertencia": ""})
            except ValueError as exc:
                results.append({"sku": sku, "advertencia": str(exc)})
        frame = pd.DataFrame(results)
        frame.to_csv(self.work / "faltantes.csv", index=False, encoding="utf-8-sig")
        return frame

    def _references(self, row, sku, temporary):
        local = cell(row, "referencias_locales", "referencia_local")
        paths = []
        for name in re.split(r"[;|\n]+", local):
            if name.strip():
                path = Path(name.strip()).expanduser()
                paths.append(str(path if path.is_absolute() else self.base / path))
        urls = re.findall(r"https?://[^\s;|]+", cell(row, "web_link_imagen", "url_imagen", "image_url"))
        for index, url in enumerate(urls[:6 - len(paths)]):
            destination = temporary / f"{sku}_{index}.jpg"
            with requests.get(url.rstrip(","), stream=True, timeout=(15, 90), headers={"User-Agent": "Mozilla/5.0"}) as response:
                response.raise_for_status()
                size = 0
                with destination.open("wb") as target:
                    for chunk in response.iter_content(256 * 1024):
                        size += len(chunk)
                        if size > 10 * 1024 * 1024:
                            raise ValueError("La referencia supera 10 MB.")
                        target.write(chunk)
            paths.append(str(destination))
        if not paths or len(paths) > 6:
            raise ValueError("Se requieren de 1 a 6 fotos originales: Web link imagen o referencias_locales.")
        for path in paths:
            if Path(path).stat().st_size > 10 * 1024 * 1024:
                raise ValueError("La referencia supera 10 MB.")
            with Image.open(path) as picture:
                picture.verify()
        return paths

    def _styles(self):
        if self.styles is not None:
            return self.styles
        candidates = [p for p in self.output.glob("*") if p.is_file() and re.search(r"_3(?:_comercial)?\.(png|jpe?g)$", p.name, re.I)]
        candidates.sort(key=lambda p: (0 if re.search(r"_3\.png$", p.name, re.I) else 1, -p.stat().st_mtime_ns))
        directory = self.work / "estilos"
        directory.mkdir(exist_ok=True)
        self.styles = []
        for path in candidates:
            if len(self.styles) == 2:
                break
            if path.stat().st_size > 12_000_000:
                continue
            try:
                with Image.open(path) as source:
                    image = ImageOps.exif_transpose(source).convert("RGB")
                    image.thumbnail((900, 900))
                    key = hashlib.sha256((path.name + str(path.stat().st_mtime_ns)).encode()).hexdigest()[:24]
                    target = directory / (key + ".jpg")
                    if not target.exists():
                        image.save(target, "JPEG", quality=82, optimize=True)
                self.styles.append(str(target))
            except (OSError, ValueError):
                continue
        return self.styles

    def _plan(self, product):
        styles = self._styles()
        key = creative.plan_key(product, styles)
        with self.lock:
            if key in self.state["plans"]:
                return self.state["plans"][key], styles
        try:
            plan = creative.brief(self._client(), product, styles)
        except Exception:
            plan = creative.fallback_brief(product, "La investigación no estuvo disponible. Se usará una escena original.")
        with self.lock:
            self.state["plans"][key] = plan
            self._persist()
        return plan, styles

    def _generate(self, product, paths, slot, plan, styles, *, feedback=(), automatic_review=False):
        sku = product["sku"]
        key = sku + ":" + slot
        with self.lock:
            previous = dict(self._record(sku, slot))
            if previous.get("status") in {"processing", "uncertain"}:
                raise ValueError("Resultado anterior incierto. Revísalo y autoriza un reintento explícito.")
            history = list(dict.fromkeys(previous.get("history", []) + list(feedback)))[-8:]
            if feedback and not Path(previous.get("raw") or "__missing_raw__").is_file():
                raise ValueError("Falta el raw anterior; genera primero una vista previa para corregirla.")
            token = uuid.uuid4().hex
            destination = self.work / "candidatos" / sku / token
            destination.mkdir(parents=True)
            raw, final = destination / f"{sku}_{slot}_raw.jpg", destination / f"{sku}_{slot}.jpg"
            self.state["items"][key] = {**previous, "status": "processing", "history": history}
            self._persist()  # Durable checkpoint before the one paid image request.
        prompt = self.contract.PROMPT_HD if slot == "1_hd" else plan["lifestyle" if slot == "2_uso" else "comercial"]
        try:
            picture = creative.generate(self._client(), paths, prompt, slot,
                previous=previous.get("raw") if feedback else None, corrections=history, styles=styles)
            picture.save(raw, "JPEG", quality=95, optimize=True)
            qa = self.contract._validar_con_vision(self._client(), [image_part(p) for p in paths], str(raw), slot) if automatic_review else None
            with Image.open(self.logo) as logo:
                branded_image(picture, logo).save(final, "JPEG", quality=94, optimize=True)
            with self.lock:
                revisions = previous.get("versions", []) + ([{k: previous[k] for k in ("raw", "image", "history") if k in previous}] if previous.get("raw") else [])
                self.state["items"][key] = {"sku": sku, "slot": slot, "name": product["name"], "status": "candidate",
                    "raw": str(raw), "image": str(final), "history": history, "qa": qa, "versions": revisions}
                self._persist()
            return {"sku": sku, "slot": slot, "status": "candidate"}
        except Exception as exc:
            with self.lock:
                self.state["items"][key] = {**previous, "sku": sku, "slot": slot, "status": "uncertain", "history": history,
                                          "error_type": type(exc).__name__}
                self._persist()
            raise RuntimeError(f"{sku} · {slot}: {type(exc).__name__}. Se conservó la imagen anterior. Revisa cuota/permisos y autoriza el reintento si procede.") from None

    def batch(self, *, slots=None, skus=(), limit=0, workers=2, automatic_review=False, confirm=False):
        if not confirm:
            raise ValueError("Primero revisa la auditoría y confirma la generación.")
        if not self.busy.acquire(blocking=False):
            raise ValueError("Ya hay un lote activo.")
        self.stop_event.clear()
        try:
            slots = list(creative.SLOTS if slots is None else slots)
            rows = self.inventory()
            report = self.audit(rows, slots)
            valid = {row["sku"]: row for row in report.to_dict("records") if not row.get("advertencia")}
            selected = [row for row in rows if cell(row, "sku") in valid and (not skus or cell(row, "sku") in skus)]
            if limit > 0:
                selected = selected[:limit]
            self._styles()  # Freeze the customer's style references once for the entire batch.
            def process(row):
                sku = cell(row, "sku")
                pending = [slot for slot in slots if slot in valid[sku].get("imagenes_faltantes", "").split(",")]
                if self.stop_event.is_set() or not pending:
                    return []
                results = []
                try:
                    product = self._product(row)
                    with tempfile.TemporaryDirectory(prefix="rincon_colab_") as temporary:
                        paths = self._references(row, sku, Path(temporary))
                        plan, styles = self._plan(product) if any(s != "1_hd" for s in pending) else ({}, [])
                        for slot in pending:
                            if self.stop_event.is_set():
                                break
                            try:
                                result = self._generate(product, paths, slot, plan, styles, automatic_review=automatic_review)
                            except Exception as exc:
                                result = {"sku": sku, "slot": slot, "status": "warning", "message": str(exc)}
                            print(f"{sku} · {slot}: {result['status']}")
                            results.append(result)
                except Exception as exc:
                    results.append({"sku": sku, "status": "warning", "message": f"No se pudo preparar el producto ({type(exc).__name__}). Revisa sus referencias y datos."})
                return results
            results = []
            with ThreadPoolExecutor(max_workers=max(1, min(4, int(workers)))) as pool:
                futures = [pool.submit(process, row) for row in selected]
                try:
                    for future in as_completed(futures):
                        results.extend(future.result())
                except KeyboardInterrupt:
                    self.stop_event.set()
                    for future in futures:
                        future.cancel()
                    print("Detenido: las llamadas ya iniciadas terminan y guardan su candidato; no se inician otras.")
            self.audit(rows, slots)
            return pd.DataFrame(results)
        finally:
            self.busy.release()

    def correct(self, sku, slot, feedback, *, errors=(), automatic_review=False, confirm=False):
        if not confirm or slot not in creative.SLOTS:
            raise ValueError("Confirma la corrección y selecciona un slot válido.")
        corrections = [self.contract.ERRORES_IA[name] for name in errors]
        if feedback.strip():
            corrections.append(feedback.strip())
        if not corrections:
            raise ValueError("Indica qué se debe corregir.")
        rows = [row for row in self.inventory() if cell(row, "sku") == sku]
        if len(rows) != 1:
            raise ValueError("El SKU debe existir una sola vez en el CSV.")
        product = self._product(rows[0])
        with tempfile.TemporaryDirectory(prefix="rincon_correct_") as temporary:
            paths = self._references(rows[0], sku, Path(temporary))
            plan, styles = self._plan(product) if slot != "1_hd" else ({}, [])
            return self._generate(product, paths, slot, plan, styles, feedback=corrections, automatic_review=automatic_review)

    def allow_retry(self, sku, slot, *, confirm=False):
        if not confirm:
            raise ValueError("Revisa el resultado incierto antes de confirmar otro intento.")
        with self.lock:
            entry = self._record(sku, slot)
            if entry.get("status") not in {"processing", "uncertain"}:
                raise ValueError("Ese slot no tiene un resultado incierto.")
            entry["status"] = "retry_authorized"
            self._persist()

    def regenerate(self, sku, slot, *, automatic_review=False, confirm=False):
        if not confirm or slot not in creative.SLOTS:
            raise ValueError("Confirma la regeneración y selecciona un slot válido.")
        rows = [row for row in self.inventory() if cell(row, "sku") == sku]
        if len(rows) != 1:
            raise ValueError("El SKU debe existir una sola vez en el CSV.")
        with tempfile.TemporaryDirectory(prefix="rincon_regenerate_") as temporary:
            product = self._product(rows[0])
            paths = self._references(rows[0], sku, Path(temporary))
            plan, styles = self._plan(product) if slot != "1_hd" else ({}, [])
            return self._generate(product, paths, slot, plan, styles, automatic_review=automatic_review)

    def gallery(self, sku=""):
        from IPython.display import HTML, Image as DisplayImage, display
        for entry in list(self.state["items"].values()):
            if entry.get("image") and (not sku or entry.get("sku") == sku):
                label = html.escape(f"{entry.get('sku')} · {entry.get('slot')} · {entry.get('status')}")
                display(HTML(f"<h4>{label}</h4>"))
                display(DisplayImage(filename=entry["image"], width=360))
                if entry.get("qa"):
                    display(HTML("<p>QA: " + html.escape(json.dumps(entry["qa"], ensure_ascii=False)) + "</p>"))

    def approve(self, *, skus=(), slots=None, confirm=False):
        if not confirm or not skus:
            raise ValueError("Revisa la galería, indica los SKU aprobados y confirma el guardado.")
        saved = []
        self.output.mkdir(parents=True, exist_ok=True)
        with self.lock:
            for entry in self.state["items"].values():
                if entry.get("sku") not in skus or entry.get("slot") not in (slots or creative.SLOTS) or entry.get("status") != "candidate":
                    continue
                if not valid_image(entry["image"]) or not valid_image(entry["raw"]):
                    raise ValueError("El candidato o su raw ya no es válido; no se reemplazó el canónico.")
                for source, filename in ((entry["image"], f"{entry['sku']}_{entry['slot']}.jpg"),
                                         (entry["raw"], f"{entry['sku']}_{entry['slot']}_raw.jpg")):
                    target = self.output / filename
                    if target.exists():
                        backup = self.work / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
                        backup.mkdir(parents=True)
                        shutil.copy2(target, backup / filename)
                    temporary = self.output / ("." + uuid.uuid4().hex + ".tmp")
                    shutil.copy2(source, temporary)
                    temporary.replace(target)
                entry["status"] = "approved"
                saved.append(str(self.output / f"{entry['sku']}_{entry['slot']}.jpg"))
                self._persist()
        return saved
