"""Original functions from the accepted Loyverse Colab, supplied 2026-10-16.

No Colab authentication, UI or top-level side effects. Runtime globals are bound
per execution by loyverse_export.py. Function bodies remain unchanged.
"""
import io
import re
from decimal import Decimal
from PIL import Image, ImageOps
from googleapiclient.http import MediaIoBaseDownload

def api(method, endpoint, payload=None, params=None):
    r = session.request(
        method,
        API + "/" + endpoint.lstrip("/"),
        json=payload,
        params=params,
        timeout=90
    )
    if not r.ok:
        raise RuntimeError(
            f"{method} {endpoint}: HTTP {r.status_code}: "
            f"{r.text[:500]}"
        )
    return r.json() if r.content else {}

def listar(endpoint, clave):
    acumulado = []
    cursor = None
    vistos = set()

    while True:
        params = {"limit": 250}
        if cursor:
            params["cursor"] = cursor

        respuesta = api("GET", endpoint, params=params)
        acumulado.extend(respuesta.get(clave, []))

        cursor = respuesta.get("cursor")
        if not cursor:
            break
        if cursor in vistos:
            raise RuntimeError("Paginación repetida en Loyverse")
        vistos.add(cursor)

    return acumulado

def leer(nombre, columnas="AZ"):
    datos = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{nombre}'!A1:{columnas}"
    ).execute().get("values", [])

    if not datos:
        return []

    headers = [str(x).strip() for x in datos[0]]
    rows = []

    for values in datos[1:]:
        fila = list(values)
        fila += [""] * (len(headers) - len(fila))
        rows.append(dict(zip(headers, fila)))

    return rows

def parent_sku(v):
    return (
        v.get("sku_padre")
        or CSV_V.get(v["sku"], {}).get("Superior")
        or ""
    ).strip()

def hijos(parent):
    return [
        v for v in VARIANTES.values()
        if parent_sku(v) == parent
    ]

def indexar_item(item):
    referencia = item.get("reference_id")
    if referencia:
        REF_INDEX[referencia] = item

    for v in item.get("variants", []):
        sku = v.get("sku")
        if sku:
            SKU_INDEX[sku] = v

def variante_existente(sku):
    if sku in SKU_INDEX:
        return SKU_INDEX[sku]

    resultado = api(
        "GET", "variants",
        params={"sku": sku, "limit": 250}
    )

    for v in resultado.get("variants", []):
        if v.get("sku") == sku:
            SKU_INDEX[sku] = v
            return v

    return None

def padre_existente(padre):
    sku = padre["sku"]
    if sku in REF_INDEX:
        return REF_INDEX[sku]

    nombre = padre.get("nombre_producto", "").casefold()

    for item in ITEMS:
        if item.get("item_name", "").casefold() == nombre:
            raise ValueError(
                "Existe un artículo con el mismo nombre, "
                "pero sin referencia de SKU padre. "
                "Revisarlo manualmente para evitar duplicados."
            )

    return None

def precio(fila):
    raw = str(fila.get("precio", "")).replace(",", "")
    raw = re.sub(r"[^\d.]", "", raw)

    if not raw:
        raise ValueError(f"Sin precio: {fila['sku']}")

    valor = Decimal(raw)
    if valor <= 0:
        raise ValueError(f"Precio inválido: {fila['sku']}")

    return float(valor)

def descripcion(fila):
    partes = []

    marca = fila.get("Marca", "").strip()
    corta = fila.get("descripcion_corta", "").strip()
    larga = fila.get("descripcion_larga", "").strip()

    if marca:
        partes.append("Marca: " + marca)
    if corta:
        partes.append(corta)
    if larga:
        partes.append(larga)

    resultado = "\n\n".join(partes)

    if len(resultado) > 32768:
        raise ValueError("Descripción demasiado larga")

    return resultado

def categoria_id(fila, crear=False):
    nombre = fila.get("categorias", "").strip()

    if not nombre:
        return None

    # Loyverse utiliza una categoría plana.
    # Conservar la ruta completa evita perder contexto.
    if len(nombre) > 64:
        raise ValueError(
            f"Categoría demasiado larga: {nombre}"
        )

    for c in CATEGORIES:
        if c["name"].casefold() == nombre.casefold():
            return c["id"]

    if not crear:
        print("Categoría no existente, se omite:", nombre)
        return None

    nuevo = api("POST", "categories", {
        "name": nombre
    })
    CATEGORIES.append(nuevo)
    return nuevo["id"]

def barcode(fila):
    sku = fila["sku"]
    dato = (
        EXTRA.get(sku, {}).get("codigo_barras")
        or CSV_V.get(
            sku, {}
        ).get("GTIN, UPC, EAN, or ISBN")
        or ""
    )
    return str(dato).strip()

def datos_variante(fila, atributo=None):
    sku = fila["sku"]

    if not sku or len(sku) > 40:
        raise ValueError(f"SKU no válido: {sku}")

    resultado = {
        "sku": sku,
        "default_pricing_type": "FIXED",
        "default_price": precio(fila)
    }

    codigo = barcode(fila)
    if codigo:
        resultado["barcode"] = codigo

    if atributo:
        resultado["option1_value"] = atributo

    return resultado

def atributo(v):
    sku = v["sku"]
    meta = CSV_V.get(sku, {})
    extra = EXTRA.get(sku, {})
    meta_padre = CSV_V.get(parent_sku(v), {})

    nombre = (
        meta.get("Nombre del atributo 1")
        or extra.get("atributo_nombre")
        or meta_padre.get("Nombre del atributo 1")
        or ""
    ).strip()

    valor = (
        meta.get("Valor(es) del atributo 1")
        or extra.get("atributo_valor")
        or ""
    ).strip()

    if not nombre or not valor:
        raise ValueError(f"Atributo incompleto: {sku}")

    if len(nombre) > 64 or len(valor) > 20:
        raise ValueError(f"Atributo demasiado largo: {sku}")

    return nombre, valor

def cargar_indice_imagenes():
    global IMAGE_FILES

    if IMAGE_FILES is not None:
        return

    IMAGE_FILES = []
    pendientes = [FOLDER_ID]
    visitadas = set()

    while pendientes:
        folder = pendientes.pop()

        if folder in visitadas:
            continue
        visitadas.add(folder)

        token = None
        while True:
            res = drive_api.files().list(
                q=f"'{folder}' in parents and trashed = false",
                fields=(
                    "nextPageToken,"
                    "files(id,name,mimeType,size)"
                ),
                pageSize=1000,
                pageToken=token
            ).execute()

            for f in res.get("files", []):
                if f["mimeType"] == (
                    "application/vnd.google-apps.folder"
                ):
                    pendientes.append(f["id"])
                elif f.get("mimeType", "").startswith("image/"):
                    IMAGE_FILES.append(f)

            token = res.get("nextPageToken")
            if not token:
                break

    print("Imágenes indexadas:", len(IMAGE_FILES))

def imagen_principal(sku):
    cargar_indice_imagenes()

    patron = re.compile(
        rf"^{re.escape(sku)}_(\d+)(?=[._])",
        re.I
    )

    candidatos = []

    for f in IMAGE_FILES:
        nombre = f["name"]
        match = patron.match(nombre)

        if not match:
            continue

        if not re.search(r"\.(png|jpe?g|webp)$", nombre, re.I):
            continue

        numero = int(match.group(1))
        hd = "_hd." in nombre.lower()

        candidatos.append((
            numero,
            0 if hd else 1,
            nombre,
            f
        ))

    candidatos.sort(key=lambda x: x[:3])
    return candidatos[0][3] if candidatos else None

def subir_imagen(item_id, archivo):
    # Una imagen principal por artículo en Loyverse.
    file_id = archivo["id"]
    tamaño = int(archivo.get("size") or 0)

    if tamaño > 25 * 1024 * 1024:
        raise ValueError("Imagen original demasiado grande")

    stream = io.BytesIO()
    request = drive_api.files().get_media(fileId=file_id)
    loader = MediaIoBaseDownload(stream, request)

    done = False
    while not done:
        _, done = loader.next_chunk()

    stream.seek(0)

    # Convertir a PNG cuadrado para Loyverse.
    with Image.open(stream) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((800, 800))

        fondo = Image.new(
            "RGB", (800, 800), "white"
        )

        if img.mode in ("RGBA", "LA"):
            capa = img.convert("RGBA")
            fondo.paste(
                capa,
                ((800 - capa.width) // 2,
                 (800 - capa.height) // 2),
                capa
            )
        else:
            img = img.convert("RGB")
            fondo.paste(
                img,
                ((800 - img.width) // 2,
                 (800 - img.height) // 2)
            )

        salida = io.BytesIO()
        fondo.save(salida, format="PNG", optimize=True)

    stream.close()

    r = session.post(
        f"{API}/items/{item_id}/image",
        data=salida.getvalue(),
        headers={"Content-Type": "image/png"},
        timeout=120
    )
    salida.close()

    if r.status_code != 201:
        raise RuntimeError(
            f"Error imagen HTTP {r.status_code}: "
            f"{r.text[:300]}"
        )

def validar_nombre(padre):
    nombre = padre.get("nombre_producto", "").strip()
    if not (1 <= len(nombre) <= 64):
        raise ValueError(
            f"Nombre debe tener 1-64 caracteres: "
            f"{padre['sku']}"
        )
    return nombre

def construir_simple(fila, crear_categoria=False):
    payload = {
        "item_name": validar_nombre(fila),
        "description": descripcion(fila),
        "reference_id": fila["sku"],
        "variants": [datos_variante(fila)]
    }

    cat = categoria_id(fila, crear_categoria)
    if cat:
        payload["category_id"] = cat

    return payload

def construir_familia(
    padre, elegidos, crear_categoria=False
):
    nombres = set()
    combinaciones = set()
    valores = []

    for v in elegidos:
        n, valor = atributo(v)
        nombres.add(n.casefold())

        if valor.casefold() in combinaciones:
            raise ValueError(
                f"Atributo repetido en familia: {valor}"
            )

        combinaciones.add(valor.casefold())
        valores.append((v, n, valor))

    if len(nombres) != 1:
        raise ValueError(
            "La familia contiene atributos incompatibles"
        )

    payload = {
        "item_name": validar_nombre(padre),
        "description": descripcion(padre),
        "reference_id": padre["sku"],
        "option1_name": valores[0][1],
        "variants": [
            datos_variante(v, valor)
            for v, _, valor in valores
        ]
    }

    cat = categoria_id(padre, crear_categoria)
    if cat:
        payload["category_id"] = cat

    return payload

def resolver(modo, sku):
    if modo == "Simple":
        return SIMPLES[sku], [], []

    if modo == "Familia":
        padre = PADRES[sku]
        todos = hijos(sku)
        if not todos:
            raise ValueError("Familia sin variantes")
        return padre, todos, todos

    v = VARIANTES[sku]
    parent = parent_sku(v)

    if parent not in PADRES:
        raise ValueError(
            f"No se encontró el SKU padre: {parent}"
        )

    return PADRES[parent], [v], hijos(parent)

def crear_seleccion(
    modo, sku, incluir_imagen,
    crear_categoria, registrar
):
    padre, elegidos, todos = resolver(modo, sku)

    if not elegidos:
        existente = variante_existente(sku)

        if existente:
            registrar("omitido", sku, "SKU existente")
            return

        if padre_existente(padre):
            registrar("omitido", sku, "Artículo existente")
            return

        payload = construir_simple(
            padre, crear_categoria
        )

        creado = api("POST", "items", payload)
        indexar_item(creado)

        registrar("creado", sku, "Artículo simple creado")

        if incluir_imagen:
            subir_imagen_si_existe(
                creado["id"], sku, registrar
            )

        return

    # Prevalidación de atributos y precios
    nombres = set()
    valores = set()

    for v in elegidos:
        nombre, valor = atributo(v)
        nombres.add(nombre.casefold())

        if valor.casefold() in valores:
            raise ValueError(
                f"Variante duplicada en {padre['sku']}"
            )

        valores.add(valor.casefold())
        datos_variante(v, valor)

    if len(nombres) != 1:
        raise ValueError("Atributos de familia incompatibles")

    existente = padre_existente(padre)

    # No crear una familia duplicada si alguna
    # variante pertenece ya a otro artículo.
    for v in elegidos:
        remoto = variante_existente(v["sku"])

        if remoto and (
            not existente
            or remoto.get("item_id") != existente.get("id")
        ):
            raise ValueError(
                f"SKU {v['sku']} ya pertenece "
                "a otro artículo de Loyverse."
            )

    if not existente:
        payload = construir_familia(
            padre, elegidos, crear_categoria
        )

        creado = api("POST", "items", payload)
        indexar_item(creado)

        registrar(
            "creado", padre["sku"],
            f"Familia con {len(elegidos)} variante(s)"
        )

        if incluir_imagen:
            imagen_sku = padre["sku"]

            if not imagen_principal(imagen_sku):
                imagen_sku = elegidos[0]["sku"]

            subir_imagen_si_existe(
                creado["id"], imagen_sku, registrar
            )

        return

    # Padre existente: añadir exclusivamente
    # variantes faltantes sin cambiar las anteriores.
    detalle = api("GET", f"items/{existente['id']}")
    nombre_opcion = detalle.get("option1_name", "")

    for v in elegidos:
        nombre, valor = atributo(v)

        if nombre_opcion.casefold() != nombre.casefold():
            raise ValueError(
                f"Atributo incompatible en familia "
                f"{padre['sku']}"
            )

    for v in elegidos:
        if variante_existente(v["sku"]):
            registrar("omitido", v["sku"], "Variante existente")
            continue

        _, valor = atributo(v)
        payload = datos_variante(v, valor)
        payload["item_id"] = existente["id"]

        nueva = api("POST", "variants", payload)
        SKU_INDEX[v["sku"]] = nueva

        registrar(
            "creado", v["sku"],
            "Variante añadida a familia existente"
        )

def subir_imagen_si_existe(item_id, sku, registrar):
    try:
        imagen = imagen_principal(sku)

        if not imagen:
            registrar(
                "sin_imagen", sku,
                "No se encontró imagen principal"
            )
            return

        subir_imagen(item_id, imagen)
        registrar("imagen", sku, imagen["name"])

    except Exception as e:
        registrar(
            "error_imagen", sku, str(e)
        )
        print("Error de imagen:", str(e))
