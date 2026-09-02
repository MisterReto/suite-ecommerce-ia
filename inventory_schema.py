"""Adaptadores para el esquema canónico de inventario de El Rincón de Asia."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

MASTER_SHEET = "Lista completa"
SIMPLE_SHEET = "Lista Simple"
VARIABLE_SHEET = "Lista Variable"

MASTER_COLUMNS = (
    "sku_padre", "tipo", "sku", "nombre_producto", "Marca",
    "descripcion_corta", "descripcion_larga", "Existencias", "categorias",
    "etiquetas", "Web link imagen", "precio", "Precio descuento", "imagenes",
)


def split_category_path(value: Any) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""
    parent, sep, child = text.partition(">")
    return parent.strip(), child.strip() if sep else ""


def join_category_path(parent: Any, child: Any) -> str:
    parent = str(parent or "").strip()
    child = str(child or "").strip()
    if parent and child:
        return f"{parent} > {child}"
    return parent or child


def normalize_product_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Devuelve nombres canónicos sin alterar el contenido comercial del producto."""
    out = {key: row.get(key, "") for key in MASTER_COLUMNS}
    out["sku"] = str(out["sku"] or "").strip()
    out["sku_padre"] = str(out["sku_padre"] or "").strip()
    out["Marca"] = str(out["Marca"] or row.get("marca", "") or "").strip()

    raw_kind = str(out["tipo"] or "simple").strip().casefold()
    aliases = {
        "simple": "simple",
        "variable": "variable",
        "variation": "variation",
        "variación": "variation",
        "variacion": "variation",
        "variante": "variation",
    }
    kind = aliases.get(raw_kind, "variation" if out["sku_padre"] else "simple")
    # Compatibilidad con capturas antiguas: la interfaz llamaba "Variable" a
    # las filas hijas. Un SKU padre informado convierte ese registro en variación.
    if kind == "variable" and out["sku_padre"]:
        kind = "variation"
    out["tipo"] = kind
    if kind != "variation":
        out["sku_padre"] = ""

    if not out["categorias"]:
        out["categorias"] = join_category_path(row.get("categoria"), row.get("subcategoria"))

    try:
        out["Existencias"] = int(float(out["Existencias"] or 0))
    except (TypeError, ValueError):
        out["Existencias"] = 0
    try:
        out["precio"] = float(out["precio"] or 0)
    except (TypeError, ValueError):
        out["precio"] = 0.0
    try:
        out["Precio descuento"] = float(out["Precio descuento"] or 0)
    except (TypeError, ValueError):
        out["Precio descuento"] = 0.0
    return out


@dataclass(frozen=True)
class ProductKindIndex:
    simple_skus: frozenset[str]
    variable_skus: frozenset[str]

    @classmethod
    def from_rows(cls, simple_rows, variable_rows) -> "ProductKindIndex":
        def collect(rows):
            return frozenset(
                str(r.get("sku", "") or "").strip()
                for r in rows
                if str(r.get("sku", "") or "").strip()
            )
        return cls(collect(simple_rows), collect(variable_rows))

    def kind_for(self, sku: str, fallback: str = "Simple") -> str:
        sku = str(sku or "").strip()
        if sku in self.variable_skus:
            return "Variable"
        if sku in self.simple_skus:
            return "Simple"
        return "Variable" if str(fallback).strip().casefold() == "variable" else "Simple"
