"""Text enrichment is a reviewable proposal; it never writes price or inventory."""

import json
from pathlib import Path
from sqlalchemy import select
from .database import transaction
from .models import Product, Category
from . import queue


def enrich(job, owner, value, drive):
    from studio_api import DESCRIPTION_RULES, clean_description, read_barcodes
    from gemini_gateway import GeminiClient, image_part, text_config, parse_json
    from creative_pipeline import TEXT_MODEL

    payload = dict(job["payload"])
    paths = []
    for index, fid in enumerate(payload["references"]):
        path = f"/tmp/{value['file_namespace']}_enrich_{index}.jpg"
        Path(path).write_bytes(drive.download(fid))
        paths.append(path)
    with transaction() as db:
        categories = list(
            db.scalars(
                select(Category.name).where(Category.tenant_id == job["tenant_id"])
            )
        )
        tags = list(
            dict.fromkeys(
                t
                for p in db.scalars(
                    select(Product).where(Product.tenant_id == job["tenant_id"], Product.status != "deleted")
                )
                for t in p.tags
            )
        )[:80]
    prompt = "Analiza únicamente los hechos legibles en las fotos del producto. Devuelve JSON con nombre, marca, gramaje, " "categoria, subcategoria, desc_corta, desc_larga, etiquetas (array). No inventes lo desconocido. " + DESCRIPTION_RULES + " Categorías existentes: " + json.dumps(
        categories, ensure_ascii=False
    ) + ". Etiquetas existentes (elige solo de estas si no está vacío): " + json.dumps(
        tags, ensure_ascii=False
    )
    payload["in_flight"] = {"operation": "text_enrichment"}
    queue.checkpoint(
        job["id"],
        owner,
        payload=payload,
        message="Leyendo las referencias; se guardará una propuesta para revisar.",
    )
    response = GeminiClient(value["gemini_key"]).models.generate_content(
        model=TEXT_MODEL,
        contents=[image_part(p) for p in paths] + [prompt],
        config=text_config(2500, model=TEXT_MODEL),
    )
    data = parse_json(response.text)
    codes = list(dict.fromkeys(code for path in paths for code in read_barcodes(path)))
    proposal = {
        "name": str(data.get("nombre", ""))[:180],
        "brand": str(data.get("marca", ""))[:120],
        "category": str(data.get("categoria", ""))[:160],
        "subcategory": str(data.get("subcategoria", ""))[:160],
        "short_description": clean_description(data.get("desc_corta", ""), short=True),
        "long_description": clean_description(data.get("desc_larga", ""))[:5000],
        "tags": [
            t
            for t in data.get("etiquetas", [])
            if isinstance(t, str) and (not tags or t in tags)
        ][:5],
        "barcode": codes[0] if len(codes) == 1 else "",
        "size": str(data.get("gramaje", ""))[:80],
    }
    payload.update(proposal=proposal, in_flight=None)
    queue.checkpoint(
        job["id"],
        owner,
        payload=payload,
        progress=100,
        message="Propuesta lista. Revisa y guarda desde el producto.",
    )
    return True
