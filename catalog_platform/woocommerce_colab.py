"""Functions copied unchanged from the accepted Colab uploader, cell C_Z7cZqlZvFL.

Runtime bindings, authentication and job checkpoints live in woocommerce_export.py.
"""
import re, io, os, json, mimetypes, requests
from decimal import Decimal, InvalidOperation
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, unquote
from googleapiclient.http import MediaIoBaseDownload

HEADERS = {"Accept": "application/json", "User-Agent": "RinconDeAsia-CatalogExporter/1.0"}

def wordpress_session():
    global wp_session
    if wp_session is None:
        wp_session = requests.Session()
        wp_session.auth = (
            secret("WP_USERNAME"),
            secret("WP_APP_PASSWORD")
        )
        wp_session.headers.update(HEADERS)
    return wp_session

def comprobar_respuesta(r, contexto):
    if r.status_code == 406:
        raise RuntimeError(
            f"{contexto}: HTTP 406. "
            "ModSecurity bloqueó la petición."
        )
    if not r.ok:
        raise RuntimeError(
            f"{contexto}: HTTP {r.status_code}: "
            f"{r.text[:450]}"
        )
    try:
        return r.json()
    except ValueError:
        raise RuntimeError(
            f"{contexto}: el servidor no devolvió JSON."
        )

def wc(method, endpoint, data=None, params=None):
    r = wc_session.request(
        method,
        f"{WC_API}/{endpoint.lstrip('/')}",
        json=data,
        params=params,
        timeout=120
    )
    return comprobar_respuesta(r, endpoint)

def leer_hoja(nombre, columnas="AZ"):
    resultado = sheets_api.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{nombre}'!A1:{columnas}",
        valueRenderOption="FORMATTED_VALUE"
    ).execute()

    values = resultado.get("values", [])
    if not values:
        return []

    headers = [str(v).strip() for v in values[0]]
    rows = []

    for values_row in values[1:]:
        values_row = list(values_row)
        values_row += [""] * (
            len(headers) - len(values_row)
        )
        rows.append(dict(zip(headers, values_row)))

    return rows

def sku_padre(variante):
    return (
        variante.get("sku_padre")
        or CSV_VARIANTES.get(
            variante.get("sku", ""), {}
        ).get("Superior")
        or ""
    ).strip()

def hijos_familia(sku):
    return [
        p for p in VARIANTES.values()
        if sku_padre(p) == sku
    ]

def fotos_sku(sku):
    patron = re.compile(
        rf"^{re.escape(sku)}_(\d+)(?=[._])",
        re.IGNORECASE
    )

    elegidas = {}

    for f in ARCHIVOS:
        nombre = f["name"]
        if not re.search(r"\.(jpg|jpeg|png|webp)$",
                         nombre, re.I):
            continue

        match = patron.match(nombre)
        if not match:
            continue

        numero = int(match.group(1))
        n = nombre.lower()

        if "_hd." in n:
            prioridad = 0
        elif re.search(r"_\d+\.(png|jpg|jpeg|webp)$", n):
            prioridad = 1
        elif "_uso." in n:
            prioridad = 2
        elif "_comercial." in n:
            prioridad = 3
        else:
            prioridad = 4

        anterior = elegidas.get(numero)
        if anterior is None or prioridad < anterior[0]:
            elegidas[numero] = (prioridad, f)

    return [elegidas[k][1] for k in sorted(elegidas)]

def guardar_cache():
    temporal = CACHE_PATH.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(MEDIA_CACHE, indent=2),
        encoding="utf-8"
    )
    os.replace(temporal, CACHE_PATH)

def media_valida(mid, filename):
    wp = wordpress_session()
    r = wp.get(f"{WP_API}/media/{mid}", timeout=60)

    if r.status_code == 404:
        return False

    info = comprobar_respuesta(r, "Verificar imagen")
    remoto = unquote(
        Path(urlparse(
            info.get("source_url", "")
        ).path).name
    )

    return remoto.casefold() == filename.casefold()

def subir_imagen(file):
    fid = file["id"]
    nombre = file["name"]
    clave = f"{URL}|{fid}"

    posibles = [
        MEDIA_CACHE.get(clave),
        MEDIA_SYNC.get(fid)
    ]

    for mid in posibles:
        if mid and media_valida(int(mid), nombre):
            MEDIA_CACHE[clave] = int(mid)
            guardar_cache()
            return int(mid)

    tamano = int(file.get("size") or 0)
    if tamano > 20 * 1024 * 1024:
        raise ValueError(
            f"{nombre} excede 20 MB. "
            "Optimiza la imagen antes de subirla."
        )

    stream = io.BytesIO()
    request = drive_api.files().get_media(fileId=fid)
    downloader = MediaIoBaseDownload(stream, request)
    done = False

    while not done:
        _, done = downloader.next_chunk()

    contenido = stream.getvalue()
    stream.close()

    mime = (
        file.get("mimeType")
        or mimetypes.guess_type(nombre)[0]
        or "image/jpeg"
    )

    wp = wordpress_session()
    r = wp.post(
        f"{WP_API}/media",
        data=contenido,
        headers={
            "Content-Type": mime,
            "Content-Disposition":
                f'attachment; filename="{nombre}"'
        },
        timeout=180
    )

    info = comprobar_respuesta(
        r, f"Subir imagen {nombre}"
    )

    mid = int(info["id"])
    MEDIA_CACHE[clave] = mid
    guardar_cache()

    print("Imagen subida:", nombre, "ID:", mid)
    return mid

def imagenes_woocommerce(sku):
    return [
        {"id": subir_imagen(f)}
        for f in fotos_sku(sku)
    ]

def precio(valor):
    raw = str(valor or "").replace(",", "")
    raw = re.sub(r"[^\d.]", "", raw)

    if not raw:
        return ""

    try:
        n = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"Precio inválido: {valor}")

    if n <= 0:
        return ""

    return str(n.quantize(Decimal("0.01")))

def incluir_precio(payload, fila):
    normal = precio(fila.get("precio"))
    oferta = precio(fila.get("Precio descuento"))

    if not normal:
        raise ValueError(
            f"SKU {fila['sku']} sin precio válido"
        )

    payload["regular_price"] = normal

    if oferta and Decimal(oferta) < Decimal(normal):
        payload["sale_price"] = oferta

def incluir_stock(payload, fila, habilitado):
    if not habilitado:
        return

    valor = str(
        fila.get("Existencias", "")
    ).strip()

    if not valor:
        return

    try:
        cantidad = int(Decimal(valor.replace(",", "")))
    except Exception:
        raise ValueError(
            f"Stock inválido: {fila['sku']}"
        )

    if cantidad < 0:
        raise ValueError("Stock negativo")

    payload["manage_stock"] = True
    payload["stock_quantity"] = cantidad

def atributo_variante(v):
    sku = v["sku"]
    csv = CSV_VARIANTES.get(sku, {})
    extra = COMPLETA.get(sku, {})
    csv_padre = CSV_VARIANTES.get(
        sku_padre(v), {}
    )

    nombre = (
        csv.get("Nombre del atributo 1")
        or extra.get("atributo_nombre")
        or csv_padre.get("Nombre del atributo 1")
        or ""
    ).strip()

    valor = (
        csv.get("Valor(es) del atributo 1")
        or extra.get("atributo_valor")
        or ""
    ).strip()

    return nombre, valor

def atributos_padre(hijos):
    grupos = {}
    combinaciones = set()

    for v in hijos:
        nombre, valor = atributo_variante(v)

        if not nombre or not valor:
            raise ValueError(
                f"Falta atributo en SKU {v['sku']}"
            )

        combinacion = (
            nombre.casefold(), valor.casefold()
        )

        if combinacion in combinaciones:
            raise ValueError(
                f"Hay dos variantes con el mismo "
                f"atributo y valor: {nombre}={valor}"
            )

        combinaciones.add(combinacion)
        grupos.setdefault(nombre, [])

        if valor not in grupos[nombre]:
            grupos[nombre].append(valor)

    return [
        {
            "name": name,
            "visible": True,
            "variation": True,
            "options": options
        }
        for name, options in grupos.items()
    ]

def atributo_para_hijo(padre_wc, v):
    nombre, valor = atributo_variante(v)

    for attr in padre_wc.get("attributes", []):
        if (
            attr.get("name", "").casefold()
            == nombre.casefold()
            and attr.get("variation")
        ):
            opciones = [
                str(x).casefold()
                for x in attr.get("options", [])
            ]

            if valor.casefold() not in opciones:
                break

            resultado = {"option": valor}

            if attr.get("id"):
                resultado["id"] = attr["id"]
            else:
                resultado["name"] = attr["name"]

            return resultado

    raise ValueError(
        f"El padre {padre_wc['sku']} no permite "
        f"{nombre}={valor}. No se modificó el padre."
    )

def termino(endpoint, nombre, parent=None):
    clave = (endpoint, nombre.casefold(), parent)
    if clave in TERMINOS:
        return TERMINOS[clave]

    items = wc(
        "GET", endpoint,
        params={"search": nombre, "per_page": 100}
    )

    for item in items:
        if item["name"].casefold() != nombre.casefold():
            continue
        if parent is not None and item.get("parent") != parent:
            continue

        TERMINOS[clave] = item["id"]
        return item["id"]

    payload = {"name": nombre}
    if parent is not None:
        payload["parent"] = parent

    nuevo = wc("POST", endpoint, data=payload)
    TERMINOS[clave] = nuevo["id"]
    return nuevo["id"]

def categorias(texto):
    partes = [
        x.strip() for x in texto.split(">")
        if x.strip()
    ]

    parent = 0
    for name in partes:
        parent = termino(
            "products/categories", name, parent
        )

    return [{"id": parent}] if parent else []

def etiquetas(texto):
    nombres = list(dict.fromkeys(
        x.strip() for x in texto.split(",")
        if x.strip()
    ))

    return [
        {"id": termino("products/tags", n)}
        for n in nombres
    ]

def datos_base(fila, tipo, stock, tags):
    payload = {
        "name": fila.get("nombre_producto", ""),
        "sku": fila["sku"],
        "type": tipo,
        "status": "draft",
        "catalog_visibility": "hidden",
        "description": fila.get("descripcion_larga", ""),
        "short_description": fila.get(
            "descripcion_corta", ""
        ),
        "categories": categorias(
            fila.get("categorias", "")
        )
    }

    if tags:
        payload["tags"] = etiquetas(
            fila.get("etiquetas", "")
        )

    marca = fila.get("Marca", "").strip()

    if marca:
        payload["attributes"] = [{
            "name": "Marca",
            "visible": True,
            "variation": False,
            "options": [marca]
        }]

    codigo = COMPLETA.get(
        fila["sku"], {}
    ).get("codigo_barras", "").strip()

    if codigo:
        payload["meta_data"] = [{
            "key": "_rincon_codigo_barras",
            "value": codigo
        }]

    if tipo == "simple":
        incluir_precio(payload, fila)
        incluir_stock(payload, fila, stock)

    return payload

def buscar_producto(sku):
    items = wc(
        "GET", "products",
        params={"sku": sku, "per_page": 100}
    )

    return next(
        (x for x in items if x.get("sku") == sku),
        None
    )

def buscar_variacion(parent_id, sku):
    page = 1

    while True:
        items = wc(
            "GET",
            f"products/{parent_id}/variations",
            params={"page": page, "per_page": 100}
        )

        for item in items:
            if item.get("sku") == sku:
                return item

        if len(items) < 100:
            return None

        page += 1

def resolver(modo, sku):
    if modo == "Simple":
        return SIMPLES[sku], [], []

    if modo == "Familia":
        padre = PADRES[sku]
        todos = hijos_familia(sku)
        return padre, todos, todos

    hijo = VARIANTES[sku]
    parent_sku = sku_padre(hijo)

    if parent_sku not in PADRES:
        raise ValueError(
            f"No existe familia para {sku}: {parent_sku}"
        )

    padre = PADRES[parent_sku]
    todos = hijos_familia(parent_sku)

    return padre, [hijo], todos

def validar(padre, seleccionados, todos,
            incluir_imagenes, incluir_inventario):

    if seleccionados:
        if not todos:
            raise ValueError("Familia sin variantes")

        atributos_padre(todos)

    for p in (seleccionados or [padre]):
        temporal = {}
        incluir_precio(temporal, p)
        incluir_stock(temporal, p, incluir_inventario)

        if incluir_imagenes and not fotos_sku(p["sku"]):
            raise ValueError(
                f"Sin imágenes verificadas para "
                f"{p['sku']}. Desmarca imágenes "
                "si deseas crearlo sin fotografías."
            )

def registrar(accion, **datos):
    if REGISTRO is None:
        return

    REGISTRO["eventos"].append({
        "fecha": datetime.now().isoformat(),
        "accion": accion,
        **datos
    })

    RUTA_REGISTRO.write_text(
        json.dumps(
            REGISTRO, ensure_ascii=False, indent=2
        ),
        encoding="utf-8"
    )

def ejecutar(modo, sku, imagenes=True,
             stock=False, tags=False,
             permitir_publicada=False):

    global REGISTRO, RUTA_REGISTRO

    padre, elegidos, todos = resolver(modo, sku)
    validar(padre, elegidos, todos, imagenes, stock)

    # Validar el padre ANTES de modificar nada.
    padre_wc = buscar_producto(padre["sku"])

    if elegidos and padre_wc:
        if padre_wc.get("type") != "variable":
            raise ValueError(
                "El padre existente no es variable."
            )

        if (
            padre_wc.get("status") == "publish"
            and not permitir_publicada
        ):
            raise ValueError(
                "La familia ya está publicada. "
                "Añadir una variante podría hacerla "
                "visible inmediatamente. Activa la "
                "autorización específica si lo deseas."
            )

        for v in elegidos:
            atributo_para_hijo(padre_wc, v)

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    RUTA_REGISTRO = LOG_DIR / f"carga_{timestamp}.json"
    REGISTRO = {
        "tienda": URL,
        "modo": modo,
        "seleccion": sku,
        "eventos": []
    }

    registrar("inicio", sku=sku)

    try:
        # ---------- PRODUCTO SIMPLE ----------
        if not elegidos:
            if padre_wc:
                registrar(
                    "omitido_existente",
                    sku=sku, id=padre_wc["id"]
                )
                print("Ya existe:", sku)
                return

            payload = datos_base(
                padre, "simple", stock, tags
            )

            if imagenes:
                payload["images"] = imagenes_woocommerce(
                    sku
                )

            creado = wc(
                "POST", "products", data=payload
            )

            registrar(
                "producto_creado",
                sku=sku, id=creado["id"]
            )

            print("Producto creado:", sku)
            print("ID:", creado["id"])
            print("Estado:", creado["status"])
            return

        # ---------- PRODUCTO VARIABLE ----------
        if not padre_wc:
            payload = datos_base(
                padre, "variable", False, tags
            )

            attrs = atributos_padre(todos)
            payload["attributes"] = (
                attrs + payload.get("attributes", [])
            )

            if imagenes:
                fotos = fotos_sku(padre["sku"])

                if not fotos:
                    fotos = fotos_sku(elegidos[0]["sku"])

                payload["images"] = [
                    {"id": subir_imagen(f)}
                    for f in fotos
                ]

            padre_wc = wc(
                "POST", "products", data=payload
            )

            registrar(
                "familia_creada",
                sku=padre["sku"],
                id=padre_wc["id"]
            )

            print("Familia creada:", padre["sku"])
        else:
            registrar(
                "familia_existente",
                sku=padre["sku"],
                id=padre_wc["id"]
            )

        parent_id = padre_wc["id"]

        # ---------- VARIANTES ----------
        for v in elegidos:
            codigo = v["sku"]

            existente = buscar_variacion(
                parent_id, codigo
            )

            if existente:
                print("Variante existente:", codigo)
                registrar(
                    "variante_omitida",
                    sku=codigo, id=existente["id"]
                )
                continue

            atributo = atributo_para_hijo(padre_wc, v)

            payload = {
                "sku": codigo,
                "description": v.get(
                    "descripcion_larga", ""
                ),
                "attributes": [atributo]
            }

            incluir_precio(payload, v)
            incluir_stock(payload, v, stock)

            if imagenes:
                fotos = fotos_sku(codigo)
                payload["image"] = {
                    "id": subir_imagen(fotos[0])
                }

            creada = wc(
                "POST",
                f"products/{parent_id}/variations",
                data=payload
            )

            registrar(
                "variante_creada",
                sku=codigo,
                id=creada["id"],
                parent_id=parent_id
            )

            print("Variante creada:", codigo)

        print("\nOperación completada.")

    except Exception as e:
        registrar("error", mensaje=str(e))
        raise

    finally:
        registrar("fin")
        print("Registro:", RUTA_REGISTRO)
