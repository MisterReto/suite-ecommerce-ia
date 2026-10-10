"""Native inventario_completo operations; precise writes, historic headers intact."""

import re


def column_name(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


class SheetsService:
    def __init__(self, client, spreadsheet_id=None, tab="Lista completa"):
        self.client, self.spreadsheet_id, self.tab = client, spreadsheet_id, tab

    def spreadsheets(self):
        # Compatibility boundary for proven capture/inventory modules.
        return self.client.spreadsheets()

    def _id(self):
        if not self.spreadsheet_id:
            raise ValueError("Selecciona inventario_completo por ID.")
        return self.spreadsheet_id

    def _tab(self):
        return "'" + self.tab.replace("'", "''") + "'"

    def metadata(self):
        return self.spreadsheets().get(spreadsheetId=self._id(),
            fields="spreadsheetId,properties(title),sheets(properties)").execute()

    def read_range(self, cells):
        # Require bounded A1, never accidentally read the whole workbook.
        if not re.fullmatch(r"[A-Z]+[1-9][0-9]*(?::[A-Z]+[1-9][0-9]*)?", cells):
            raise ValueError("Usa un rango A1 acotado, por ejemplo A1:AN100.")
        return self.spreadsheets().values().get(spreadsheetId=self._id(),
            range=self._tab() + "!" + cells, valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [])

    def columns(self, required=("sku",)):
        rows = self.read_range("A1:AZ1")
        headers = rows[0] if rows else []
        columns = {}
        for index, header in enumerate(headers, 1):
            name = str(header or "").strip()
            if not name:
                continue  # Preserve unnamed columns and their positions.
            if name in columns:
                raise ValueError("Encabezado duplicado: " + name)
            columns[name] = index
        missing = set(required) - set(columns)
        if missing:
            raise ValueError("Faltan columnas: " + ", ".join(sorted(missing)))
        return columns

    def find_sku(self, sku, max_rows=5000):
        if not sku or not 2 <= max_rows <= 10000:
            raise ValueError("SKU o límite de lectura inválido.")
        columns = self.columns()
        tabs = self.metadata().get("sheets", [])
        properties = next((tab["properties"] for tab in tabs
                           if tab.get("properties", {}).get("title") == self.tab), None)
        if not properties:
            raise ValueError("La pestaña no existe; no se realizó ninguna escritura.")
        row_count = properties.get("gridProperties", {}).get("rowCount", 0)
        if not row_count or row_count > max_rows:
            raise ValueError("El límite no cubre la pestaña completa; amplía la lectura antes de escribir.")
        max_rows = row_count
        letter = column_name(columns["sku"])
        matches = []
        for start in range(2, max_rows + 1, 500):
            rows = self.read_range(f"{letter}{start}:{letter}{min(start + 499, max_rows)}")
            matches.extend(start + offset for offset, row in enumerate(rows)
                           if row and str(row[0]).strip().casefold() == sku.strip().casefold())
        if len(matches) > 1:
            raise ValueError("SKU duplicado; no se realizó ninguna escritura.")
        return matches[0] if matches else None

    def update_cell(self, sku, column, value, expected=None):
        columns = self.columns(("sku", column))
        row = self.find_sku(sku)
        if row is None:
            raise ValueError("SKU no encontrado; no se realizó ninguna escritura.")
        sku_cell = self.read_range(column_name(columns["sku"]) + str(row))
        if not sku_cell or str(sku_cell[0][0]).strip().casefold() != sku.strip().casefold():
            raise ValueError("La fila cambió; vuelve a buscar el SKU antes de guardar.")
        cell = column_name(columns[column]) + str(row)
        prior = self.read_range(cell)
        previous = prior[0][0] if prior and prior[0] else ""
        if expected is not None and previous != expected:
            raise ValueError("La celda cambió; vuelve a leer antes de guardar.")
        self.spreadsheets().values().update(spreadsheetId=self._id(),
            range=self._tab() + "!" + cell, valueInputOption="RAW",
            body={"values": [[value]]}).execute()
        result = self.read_range(cell)
        if not result or not result[0] or str(result[0][0]) != str(value):
            raise ValueError("No se pudo confirmar la celda. Revisa antes de reintentar.")
        return {"range": self._tab() + "!" + cell, "before": previous, "after": result[0][0]}
