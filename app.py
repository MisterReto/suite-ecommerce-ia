# ==========================================
# IMPORTANTE: estas variables deben quedar ANTES de importar oauthlib,
# porque la librería las lee al momento de importarse.
# ==========================================
import os

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
os.environ.setdefault("OAUTHLIB_IGNORE_SCOPE_CHANGE", "1")

import io
import re
import json
import secrets
import difflib
import traceback

import pandas as pd
import gradio as gr
from PIL import Image

from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.responses import RedirectResponse, PlainTextResponse

from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload

from google import genai
from google.genai import types

# ==========================================
# 0. CONFIGURACIÓN INICIAL (variables de entorno / secretos)
# ==========================================
MODELO_TEXTO = "gemini-2.5-flash"
MODELO_IMAGEN = "gemini-2.5-flash-image"


def _env_requerida(nombre):
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(
            f"❌ Falta configurar la variable de entorno '{nombre}'. "
            f"Ve GUIA_DESPLIEGUE.md para configurarla como 'Secret' en tu hosting."
        )
    return valor


GOOGLE_CLIENT_ID = _env_requerida("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _env_requerida("GOOGLE_CLIENT_SECRET")
# Debe ser EXACTAMENTE la misma URI registrada en Google Cloud Console.
# Ej: https://suite-ecommerce-ia.onrender.com/auth/callback  (https, sin slash final)
GOOGLE_REDIRECT_URI = _env_requerida("GOOGLE_REDIRECT_URI")

DRIVE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive",
]

CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [GOOGLE_REDIRECT_URI],
    }
}

NOMBRE_CARPETA_RAIZ = "Proyecto_IA"
NOMBRE_SUBCARPETA_IMAGENES = "imagenes_generadas"
NOMBRE_CSV = "inventario_completo.csv"
NOMBRE_LOGO = "logo_rincon_asia.png"

COLUMNAS_CSV = [
    'sku', 'tipo', 'sku_padre', 'nombre_producto', 'marca',
    'gramaje', 'precio', 'categoria', 'subcategoria', 'descripcion_corta',
    'descripcion_larga', 'imagenes'
]

CATEGORIAS_DEFECTO = ["Alimentos", "Bebidas", "K-Pop", "Cosméticos"]
SUBCATEGORIAS_DEFECTO = ["Snacks", "Ramen", "Refrescos", "Cuidado Facial"]

# ==========================================
# 0.1 CATÁLOGO DE ERRORES DE LA IA (feedback para re-generar)
# ==========================================
# Cada error visible en español se traduce a una instrucción correctiva en inglés,
# que es el idioma en el que el modelo de imagen obedece mejor.
ERRORES_IA = {
    "📦 Inventó un empaque que no es el del producto":
        "CRITICAL FIX: In the previous attempt you INVENTED or ALTERED the packaging. "
        "You MUST copy the packaging from the reference image pixel-faithfully: same shape, "
        "same proportions, same artwork, same layout. Do not redesign anything.",

    "🏷️ Agregó un logo o marca que no existe":
        "CRITICAL FIX: In the previous attempt you ADDED a logo, badge, seal or brand mark that "
        "does not exist on the real product. Remove ALL invented logos, watermarks and emblems. "
        "Only the marks physically present in the reference image may appear.",

    "🔤 Inventó texto en el empaque":
        "CRITICAL FIX: In the previous attempt you INVENTED text, letters or characters on the "
        "packaging. Reproduce ONLY the exact text visible in the reference image. If a text area "
        "is unreadable, keep it visually blurred rather than inventing words.",

    "📐 Dimensionó mal el producto (escala/proporciones)":
        "CRITICAL FIX: In the previous attempt the product SCALE and PROPORTIONS were wrong. "
        "Respect the real-world size of the product relative to the scene and keep the exact "
        "aspect ratio of the package (do not stretch, squash, or make it oversized/tiny).",

    "🎨 Cambió los colores del producto":
        "CRITICAL FIX: In the previous attempt the product COLORS were altered. Match the exact "
        "hues, saturation and finish of the reference packaging.",

    "🧬 Deformó o duplicó el producto":
        "CRITICAL FIX: In the previous attempt the product was DEFORMED, warped or DUPLICATED. "
        "Render exactly ONE clean, undistorted, correctly built product.",

    "⬜ El fondo no quedó blanco puro":
        "CRITICAL FIX: In the previous attempt the background was not pure white. Use a perfectly "
        "clean pure white (#FFFFFF) seamless background with no gradients, props or shadows on the backdrop.",

    "⬛ La imagen no quedó cuadrada 1:1":
        "CRITICAL FIX: In the previous attempt the output was NOT square. Generate the image natively "
        "in a STRICT 1:1 SQUARE aspect ratio, with the product fully inside the frame.",

    "🖼️ La escena no corresponde al producto":
        "CRITICAL FIX: In the previous attempt the scene/context did not match the product category. "
        "Build a scene that is coherent and believable for this specific product.",

    "🔍 Se ve borrosa o de baja calidad":
        "CRITICAL FIX: In the previous attempt the result was blurry or low quality. Deliver razor-sharp "
        "focus on the packaging, high micro-detail, clean professional studio-grade lighting.",

    "✂️ Recortó o tapó parte del producto":
        "CRITICAL FIX: In the previous attempt the product was cropped or occluded. The complete product "
        "must be fully visible, centered, and unobstructed.",
}

ETIQUETAS_ERRORES = list(ERRORES_IA.keys())


def _construir_correccion(errores_seleccionados, texto_libre, historial):
    """Arma el bloque de retroalimentación que se le manda al modelo explicándole
    POR QUÉ estamos rehaciendo la imagen y qué debe corregir.

    Devuelve (bloque_prompt, historial_actualizado, resumen_legible).
    """
    historial = list(historial or [])
    nuevas = []

    for etiqueta in (errores_seleccionados or []):
        instruccion = ERRORES_IA.get(etiqueta)
        if instruccion:
            nuevas.append(instruccion)

    if texto_libre and texto_libre.strip():
        nuevas.append(
            "CRITICAL FIX (reported by the human reviewer, obey literally): "
            f"{texto_libre.strip()}"
        )

    # El historial acumula las correcciones de los intentos anteriores para que el
    # modelo no vuelva a cometer el mismo error que ya le señalamos antes.
    for instruccion in nuevas:
        if instruccion not in historial:
            historial.append(instruccion)

    if not historial:
        return "", historial, "Primer intento (sin correcciones previas)."

    intento = len(historial)
    bloque = (
        "

===== REGENERATION FEEDBACK =====
"
        f"This is a RE-GENERATION. The previous output(s) were REJECTED by a human reviewer. "
        f"There are {intento} accumulated correction(s). You MUST fix every single one of them "
        f"while keeping everything that was already correct:
"
    )
    for i, instruccion in enumerate(historial, start=1):
        bloque += f"{i}. {instruccion}
"
    bloque += "===== END FEEDBACK =====
"

    marcados = (errores_seleccionados or [])
    if texto_libre and texto_libre.strip():
        marcados = marcados + [texto_libre.strip()]

    if marcados:
        resumen = "🔧 Correcciones enviadas a la IA:
" + "
".join(
            f"  {i}. {t}" for i, t in enumerate(marcados, start=1)
        )
    else:
        resumen = f"🔧 Reintento arrastrando {intento} corrección(es) anterior(es)."

    return bloque, historial, resumen


# ==========================================
# 0.2 ALMACÉN DE SESIONES (en memoria del proceso)
# ==========================================
SESSIONS = {}


def _nueva_session_id():
    return secrets.token_urlsafe(32)


def _guardar_sesion(session_id, **kwargs):
    if not session_id:
        return
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {}
    SESSIONS[session_id].update(kwargs)


def _obtener_sesion(request: gr.Request):
    if request is None:
        return None
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in SESSIONS:
        return None
    return SESSIONS[session_id]


def _validar_sesion(request: gr.Request, requiere_api_key=True):
    """Devuelve (sesion, mensaje_error). Si mensaje_error no es None, hay que abortar."""
    sesion = _obtener_sesion(request)
    if not sesion:
        return None, "❌ Primero conéctate con Google Drive (pestaña ⚙️ Configuración)."
    if requiere_api_key and not sesion.get("gemini_key"):
        return None, "❌ Primero guarda tu API Key de Gemini (pestaña ⚙️ Configuración)."
    return sesion, None


# ==========================================
# 1. RUTAS DE AUTENTICACIÓN (FastAPI + OAuth de Google)
# ==========================================
fastapi_app = FastAPI()


@fastapi_app.get("/login")
def login():
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=DRIVE_SCOPES, redirect_uri=GOOGLE_REDIRECT_URI)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    resp = RedirectResponse(auth_url)
    resp.set_cookie("oauth_state", state, httponly=True, secure=True, samesite="lax", path="/", max_age=600)
    return resp


@fastapi_app.get("/auth/callback")
def auth_callback(request: FastAPIRequest):
    """Intercambia el 'code' por el token.

    Claves para que NO truene en hostings con proxy (Render, HF Spaces...):
      - scopes=None  -> no se valida el orden/formato de los scopes que devuelve Google.
      - fetch_token(code=...) -> no se reconstruye la URL completa, así el esquema
        http/https del proxy deja de importar y no exige validar el state cookie.
      - El traceback se muestra en pantalla en vez de un "Internal Server Error" mudo.
    """
    try:
        params = dict(request.query_params)

        if "error" in params or "code" not in params:
            return PlainTextResponse(
                f"Google devolvió una respuesta inesperada: {params}", status_code=400
            )

        flow = Flow.from_client_config(
            CLIENT_CONFIG, scopes=None, redirect_uri=GOOGLE_REDIRECT_URI
        )
        flow.fetch_token(code=params["code"])
        creds = flow.credentials

        try:
            info_usuario = build("oauth2", "v2", credentials=creds).userinfo().get().execute()
            email = info_usuario.get("email", "Usuario de Drive")
        except Exception:
            email = "Usuario de Drive"

        session_id = _nueva_session_id()
        _guardar_sesion(
            session_id,
            creds=json.loads(creds.to_json()),
            email=email,
            gemini_key=None,
        )

        resp = RedirectResponse(url="/")
        resp.set_cookie(
            "session_id", session_id,
            httponly=True, secure=True, samesite="lax", path="/",
            max_age=60 * 60 * 24 * 30,
        )
        resp.delete_cookie("oauth_state", path="/")
        return resp

    except Exception:
        return PlainTextResponse(traceback.format_exc(), status_code=500)


@fastapi_app.get("/logout")
def logout(request: FastAPIRequest):
    session_id = request.cookies.get("session_id")
    if session_id in SESSIONS:
        del SESSIONS[session_id]
    resp = RedirectResponse(url="/")
    resp.delete_cookie("session_id", path="/")
    return resp


# ==========================================
# 2. UTILIDADES DE GOOGLE DRIVE (por usuario)
# ==========================================
def _get_drive_service(sesion):
    creds = Credentials.from_authorized_user_info(sesion["creds"], DRIVE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        sesion["creds"] = json.loads(creds.to_json())
    return build("drive", "v3", credentials=creds)


def _buscar_o_crear_carpeta(service, nombre, parent_id=None):
    query = f"name = '{nombre}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    query += f" and '{parent_id}' in parents" if parent_id else " and 'root' in parents"
    res = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    archivos = res.get('files', [])
    if archivos:
        return archivos[0]['id']
    metadata = {'name': nombre, 'mimeType': 'application/vnd.google-apps.folder'}
    if parent_id:
        metadata['parents'] = [parent_id]
    carpeta = service.files().create(body=metadata, fields='id').execute()
    return carpeta['id']


def _buscar_archivo(service, nombre, parent_id):
    query = f"name = '{nombre}' and '{parent_id}' in parents and trashed = false"
    res = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    archivos = res.get('files', [])
    return archivos[0]['id'] if archivos else None


def _preparar_estructura(service):
    """Asegura que exista Proyecto_IA/imagenes_generadas en el Drive del usuario.
    Devuelve (carpeta_raiz_id, carpeta_imagenes_id, csv_file_id_o_None, logo_file_id_o_None)"""
    carpeta_raiz_id = _buscar_o_crear_carpeta(service, NOMBRE_CARPETA_RAIZ)
    carpeta_imagenes_id = _buscar_o_crear_carpeta(service, NOMBRE_SUBCARPETA_IMAGENES, parent_id=carpeta_raiz_id)
    csv_id = _buscar_archivo(service, NOMBRE_CSV, carpeta_raiz_id)
    logo_id = _buscar_archivo(service, NOMBRE_LOGO, carpeta_raiz_id)
    return carpeta_raiz_id, carpeta_imagenes_id, csv_id, logo_id


def _leer_csv_drive(service, csv_id):
    if csv_id is None:
        return pd.DataFrame(columns=COLUMNAS_CSV)
    peticion = service.files().get_media(fileId=csv_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, peticion)
    listo = False
    while not listo:
        _, listo = downloader.next_chunk()
    buffer.seek(0)
    try:
        return pd.read_csv(buffer)
    except Exception:
        return pd.DataFrame(columns=COLUMNAS_CSV)


def _guardar_csv_drive(service, carpeta_raiz_id, csv_id, df):
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    media = MediaIoBaseUpload(buffer, mimetype='text/csv', resumable=False)
    if csv_id:
        service.files().update(fileId=csv_id, media_body=media).execute()
        return csv_id
    metadata = {'name': NOMBRE_CSV, 'parents': [carpeta_raiz_id]}
    archivo = service.files().create(body=metadata, media_body=media, fields='id').execute()
    return archivo['id']


def _cargar_df(sesion):
    service = _get_drive_service(sesion)
    _, _, csv_id, _ = _preparar_estructura(service)
    return service, csv_id, _leer_csv_drive(service, csv_id)


def _subir_imagen_drive(service, carpeta_imagenes_id, nombre_archivo, ruta_local):
    media = MediaFileUpload(ruta_local, mimetype='image/jpeg', resumable=False)
    existente_id = _buscar_archivo(service, nombre_archivo, carpeta_imagenes_id)
    if existente_id:
        service.files().update(fileId=existente_id, media_body=media).execute()
        return existente_id
    metadata = {'name': nombre_archivo, 'parents': [carpeta_imagenes_id]}
    archivo = service.files().create(body=metadata, media_body=media, fields='id').execute()
    return archivo['id']


def _descargar_logo_temporal(service, logo_id):
    if logo_id is None:
        return None
    peticion = service.files().get_media(fileId=logo_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, peticion)
    listo = False
    while not listo:
        _, listo = downloader.next_chunk()
    ruta_logo_temp = "/tmp/logo_temp.png"
    with open(ruta_logo_temp, "wb") as f:
        f.write(buffer.getvalue())
    return ruta_logo_temp


# ==========================================
# 3. FUNCIONES DE APOYO (SKU, imágenes locales)
# ==========================================
def limpiar_texto_sku(texto):
    if not texto:
        return "XXX"
    texto = re.sub(r'[^a-zA-Z0-9]', '', str(texto))
    return texto.upper()


def generar_sku_logica(nombre, marca, gramaje):
    """Genera SKU: Marca (3) + Nombre (3) + Unidad/Gramaje. Máximo 10 caracteres."""
    str_marca = limpiar_texto_sku(marca)[:3].ljust(3, 'X')
    str_nom = limpiar_texto_sku(nombre)[:3].ljust(3, 'X')
    str_gramaje = limpiar_texto_sku(gramaje)
    if not str_gramaje:
        str_gramaje = "00"
    sku = f"{str_marca}{str_nom}{str_gramaje}"
    return sku[:10]


def comprimir_imagen(img_array, max_size=1024):
    img = Image.fromarray(img_array)
    img.thumbnail((max_size, max_size))
    return img


def estampar_logo(ruta_imagen, service, logo_id):
    try:
        ruta_logo_temp = _descargar_logo_temporal(service, logo_id)
        if not ruta_logo_temp:
            return
        img_base = Image.open(ruta_imagen).convert("RGBA")
        logo_original = Image.open(ruta_logo_temp).convert("RGBA")

        # 1. Centro (Marca de agua tenue)
        ancho_centro = int(img_base.width * 0.5)
        prop_centro = ancho_centro / float(logo_original.width)
        alto_centro = int((float(logo_original.height) * float(prop_centro)))
        logo_centro = logo_original.resize((ancho_centro, alto_centro), Image.Resampling.LANCZOS)
        alpha_centro = logo_centro.split()[3]
        alpha_centro = alpha_centro.point(lambda p: p * 0.15)
        logo_centro.putalpha(alpha_centro)
        pos_x_centro = (img_base.width - logo_centro.width) // 2
        pos_y_centro = (img_base.height - logo_centro.height) // 2
        img_base.paste(logo_centro, (pos_x_centro, pos_y_centro), logo_centro)

        # 2. Esquina
        ancho_esquina = int(img_base.width * 0.20)
        prop_esquina = ancho_esquina / float(logo_original.width)
        alto_esquina = int((float(logo_original.height) * float(prop_esquina)))
        logo_esquina = logo_original.resize((ancho_esquina, alto_esquina), Image.Resampling.LANCZOS)
        margen = 20
        pos_x_esquina = img_base.width - logo_esquina.width - margen
        pos_y_esquina = img_base.height - logo_esquina.height - margen
        img_base.paste(logo_esquina, (pos_x_esquina, pos_y_esquina), logo_esquina)

        img_final = img_base.convert("RGB")
        img_final.save(ruta_imagen, quality=95)
    except Exception as e:
        print(f"Error con el logo: {e}")


# ==========================================
# 4. INTELIGENCIA ARTIFICIAL (Textos, Precio, Lens, Imágenes)
# ==========================================
def _extraer_json(texto_raw):
    texto_limpio = (texto_raw or "").replace('```json', '').replace('```', '').strip()
    match = re.search(r'\{.*\}', texto_limpio, re.DOTALL)
    if match:
        texto_limpio = match.group(0)
    return json.loads(texto_limpio)


def _extraer_imagen_bytes(response):
    """Saca los bytes de la imagen de la respuesta del modelo.
    (response.parts no existe: hay que recorrer candidates -> content -> parts)"""
    for candidato in (getattr(response, "candidates", None) or []):
        contenido = getattr(candidato, "content", None)
        for part in (getattr(contenido, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return inline.data
    return None


def estimar_precio_producto(nombre, marca, gramaje, categoria, api_key):
    """Usa Gemini + Búsqueda de Google (con la API key del usuario) para investigar
    el precio real de mercado del producto y sugerir un precio de venta."""
    if not nombre:
        return {"precio_min": 0, "precio_max": 0, "precio_sugerido": 0, "moneda": "MXN"}
    prompt = (
        f"Actúa como un analista de pricing para e-commerce en México. "
        f"Busca en internet (tiendas online, Amazon, Mercado Libre, tiendas asiáticas, supermercados) "
        f"el precio de venta al público del producto '{nombre}' de la marca '{marca}', "
        f"presentación '{gramaje}', categoría '{categoria}'. "
        f"Devuelve ÚNICAMENTE un JSON estricto, sin texto adicional ni markdown, con las claves: "
        f"'precio_min' (número en MXN), 'precio_max' (número en MXN), "
        f"'precio_sugerido' (número en MXN, con margen razonable de reventa), 'moneda' ('MXN')."
    )
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODELO_TEXTO,
            contents=prompt,
            config=types.GenerateContentConfig(tools=[{"google_search": {}}])
        )
        return _extraer_json(response.text)
    except Exception as e:
        print(f"⚠️ No se pudo estimar el precio automáticamente: {e}")
        return {"precio_min": 0, "precio_max": 0, "precio_sugerido": 0, "moneda": "MXN"}


def buscar_variantes_por_imagen(imagen, nombre_actual, marca_actual, request: gr.Request):
    """Búsqueda tipo Google Lens: sube la foto del producto y usa Gemini (visión +
    Búsqueda de Google) para detectar si el MISMO producto existe en otros
    gramajes/tamaños en el mercado."""
    sesion, error = _validar_sesion(request)
    if error:
        return error, "", "Simple"
    if imagen is None:
        return "📷 Sube o importa una foto del producto para poder buscar.", "", "Simple"

    api_key = sesion["gemini_key"]
    try:
        img_pil = comprimir_imagen(imagen).convert("RGB")
        ruta_temp = "/tmp/temp_lens.jpg"
        img_pil.save(ruta_temp, format="JPEG", quality=85)

        client = genai.Client(api_key=api_key)
        archivo_ref = client.files.upload(file=ruta_temp)

        contexto = ""
        if nombre_actual:
            contexto = (
                f"Nombre de referencia (ya analizado previamente): '{nombre_actual}'. "
                f"Marca de referencia: '{marca_actual}'. "
            )

        prompt = (
            f"Actúa como Google Lens combinado con Google Shopping. Observa cuidadosamente la imagen "
            f"del producto adjunta e identifica exactamente de qué producto y marca se trata. {contexto}"
            f"Después, busca en internet si ese MISMO producto existe en OTRAS presentaciones, tamaños "
            f"o gramajes distintos al de la foto (ej: el mismo snack en 30g, 100g y 500g). "
            f"NO busques marcas ni productos distintos, solo variantes de tamaño/gramaje del mismo producto. "
            f"Devuelve ÚNICAMENTE un JSON estricto, sin texto adicional ni markdown, con las claves:
"
            f"'producto_identificado' (string), 'marca_identificada' (string),
"
            f"'tiene_variantes' (booleano), 'variantes' (lista de objetos con 'gramaje', 'fuente', 'precio_aprox'),
"
            f"'justificacion' (string breve)."
        )

        response = client.models.generate_content(
            model=MODELO_TEXTO,
            contents=[archivo_ref, prompt],
            config=types.GenerateContentConfig(tools=[{"google_search": {}}])
        )
        datos = _extraer_json(response.text)

        producto = datos.get("producto_identificado", "Producto no identificado")
        marca = datos.get("marca_identificada", "")
        tiene_variantes = bool(datos.get("tiene_variantes", False))
        variantes = datos.get("variantes", []) or []
        justificacion = datos.get("justificacion", "")

        tipo_recomendado = "Variable" if (tiene_variantes and len(variantes) > 0) else "Simple"
        if tipo_recomendado == "Variable":
            recomendacion = (
                f"✅ Se encontraron {len(variantes)} presentación(es) adicional(es). "
                f"Recomendado: marcar como VARIABLE."
            )
        else:
            recomendacion = "ℹ️ No se encontraron otras presentaciones del mismo producto. Recomendado: dejar como SIMPLE."

        reporte = f"### 🔍 Producto identificado: {producto} ({marca})

"
        if variantes:
            reporte += "| Gramaje/Tamaño | Fuente | Precio aprox. |
|---|---|---|
"
            for v in variantes:
                reporte += f"| {v.get('gramaje','-')} | {v.get('fuente','-')} | {v.get('precio_aprox','-')} |
"
        else:
            reporte += "_No se encontraron otras presentaciones a la venta actualmente._
"
        reporte += f"
**Justificación de la IA:** {justificacion}"

        return recomendacion, reporte, tipo_recomendado
    except Exception as e:
        return f"❌ Error en la búsqueda visual: {e}", "", "Simple"


def investigar_prompts(producto, marca, desc, api_key):
    prompt = (
        f"Actúa como un director de arte publicitario. Producto: '{producto}', Marca: '{marca}', Contexto: '{desc}'. "
        f"Devuelve un JSON estricto con dos claves: 'lifestyle' y 'comercial'. "
        f"REGLA 1: Si es comida/bebida, describe escenas con ingredientes volando y consumo feliz. "
        f"REGLA 2: Si NO es comida, describe un estudio estilizado, neón, pop-art. "
        f"CRÍTICO: All prompt instructions MUST be exclusively in English. The physical product packaging "
        f"MUST be clearly visible and centered. DO NOT invent packaging. DO NOT ask for text or logos. "
        f"MENTION THAT THE IMAGE MUST BE 1:1 SQUARE."
    )
    try:
        client = genai.Client(api_key=api_key)
        res = client.models.generate_content(model=MODELO_TEXTO, contents=prompt)
        return _extraer_json(res.text)
    except Exception:
        return {
            "lifestyle": (
                f"Warm lifestyle photography of the exact packaging of {producto}, highly detailed scene, "
                f"authentic interaction, natural lighting, 1:1 square aspect ratio."
            ),
            "comercial": (
                f"Dynamic epic commercial photography highlighting the exact packaging of {producto} by {marca}, "
                f"highly stylized studio lighting, 1:1 square aspect ratio."
            ),
        }


def generar_foto_individual(prompt, ruta_base, ruta_salida_local, api_key, service, logo_id, correccion=""):
    """Genera una imagen. Si 'correccion' viene con contenido, se le explica al modelo
    exactamente por qué se está rehaciendo la imagen y qué debe arreglar."""
    try:
        client = genai.Client(api_key=api_key)
        archivo_ref = client.files.upload(file=ruta_base)
        prompt_seguro = (
            f"{prompt} "
            f"CRITICAL INSTRUCTIONS: "
            f"1. YOU MUST USE THE EXACT PRODUCT PACKAGING FROM THE REFERENCE IMAGE. DO NOT invent, alter, "
            f"or hallucinate boxes, text, or shapes. The physical product is untouchable. "
            f"2. ABSOLUTELY NO LOGOS, NO WATERMARKS, NO EXTRA TEXT anywhere. "
            f"3. Respect the real proportions and scale of the product. "
            f"4. Generate the final output natively in a STRICTLY SQUARE 1:1 ASPECT RATIO."
            f"{correccion}"
        )
        response = client.models.generate_content(
            model=MODELO_IMAGEN,
            contents=[archivo_ref, prompt_seguro]
        )
        datos_imagen = _extraer_imagen_bytes(response)
        if not datos_imagen:
            print("❌ El modelo no devolvió imagen.")
            return None
        with open(ruta_salida_local, "wb") as f:
            f.write(datos_imagen)
        if logo_id:
            estampar_logo(ruta_salida_local, service, logo_id)
        return ruta_salida_local
    except Exception as e:
        print(f"❌ Error al generar imagen: {e}")
        return None


def modulo_extraer_textos(imagen_1, imagen_2, descripcion_breve, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return [error, "", "", "", "", 0, "Simple", gr.update(visible=False), "", "", "", "", None]
    if imagen_1 is None:
        return ["❌ Sube al menos la foto principal.", "", "", "", "", 0, "Simple",
                gr.update(visible=False), "", "", "", "", None]

    api_key = sesion["gemini_key"]
    client = genai.Client(api_key=api_key)
    service, csv_id, df_actual = _cargar_df(sesion)

    lista_cats = df_actual['categoria'].dropna().unique().tolist() if 'categoria' in df_actual else []
    lista_cats = lista_cats if lista_cats else CATEGORIAS_DEFECTO
    lista_subcats = df_actual['subcategoria'].dropna().unique().tolist() if 'subcategoria' in df_actual else []
    lista_subcats = lista_subcats if lista_subcats else SUBCATEGORIAS_DEFECTO

    archivos_ia = []
    img_1_pil = comprimir_imagen(imagen_1).convert("RGB")
    ruta_temp_1 = "/tmp/temp_in_1.jpg"
    img_1_pil.save(ruta_temp_1, format="JPEG", quality=85)
    archivos_ia.append(client.files.upload(file=ruta_temp_1))

    ruta_base_memoria = "/tmp/base_gen.jpg"
    img_1_pil.save(ruta_base_memoria, format="JPEG")

    if imagen_2 is not None:
        img_2_pil = comprimir_imagen(imagen_2).convert("RGB")
        ruta_temp_2 = "/tmp/temp_in_2.jpg"
        img_2_pil.save(ruta_temp_2, format="JPEG", quality=85)
        archivos_ia.append(client.files.upload(file=ruta_temp_2))

    prompt_datos = (
        f"Analiza el producto de las imágenes. Contexto extra: '{descripcion_breve}'. "
        f"Actúa como un experto en SEO para e-commerce. Devuelve un JSON estricto con:
"
        f"1. 'nombre': El nombre del producto claro y comercial.
"
        f"2. 'marca': La marca del producto.
"
        f"3. 'gramaje': La unidad de medida y cantidad EXACTA. Puede ser G, KG, ML, L, OZ o PZ. "
        f"Ejemplo: '500G', '12OZ', '1L', '10PZ'.
"
        f"4. 'categoria': Clasifícalo ESTRICTAMENTE usando SOLO una de las siguientes Categorías: "
        f"{lista_cats}. NO inventes ninguna.
"
        f"5. 'subcategoria': Clasifícalo ESTRICTAMENTE usando SOLO una de las siguientes Subcategorías: "
        f"{lista_subcats}. NO inventes ninguna.
"
        f"6. 'desc_corta': Optimizado para SEO (Máximo 150 caracteres).
"
        f"7. 'desc_larga': Optimizado para SEO con beneficios/ingredientes en formato de viñetas (-).
"
    )

    try:
        res_datos = client.models.generate_content(model=MODELO_TEXTO, contents=archivos_ia + [prompt_datos])
        datos = _extraer_json(res_datos.text)
    except Exception as e:
        return [f"❌ Error leyendo imagen: {e}", "", "", "", "", 0, "Simple",
                gr.update(visible=False), "", "", "", "", None]

    nombre = datos.get("nombre", "Producto Desconocido")
    marca = datos.get("marca", "Genérica")
    gramaje = datos.get("gramaje", "00G")

    cat_final = datos.get("categoria", "")
    if cat_final not in lista_cats:
        cat_final = lista_cats[0]
    subcat_final = datos.get("subcategoria", "")
    if subcat_final not in lista_subcats:
        subcat_final = lista_subcats[0]

    sku_gen = generar_sku_logica(nombre, marca, gramaje)
    datos_precio = estimar_precio_producto(nombre, marca, gramaje, cat_final, api_key)
    precio_sugerido = datos_precio.get("precio_sugerido", 0)

    return [
        "✅ Textos y precio sugerido extraídos. Verifica SKU, Categorías y Precio.",
        sku_gen, nombre, marca, gramaje, precio_sugerido, "Simple",
        gr.update(visible=False), cat_final, subcat_final,
        datos.get("desc_corta", ""), datos.get("desc_larga", ""),
        ruta_base_memoria
    ]


# ==========================================
# 5. GENERACIÓN DE FOTOS Y GUARDADO (hacia el Drive del usuario)
# ==========================================
PROMPT_HD = (
    "Create a clean e-commerce studio shot of this exact product packaging. Isolated on a pure white "
    "background. Crisp details, bright and even studio lighting. MUST BE 1:1 SQUARE ASPECT RATIO."
)


def _rehacer_generico(slot, prompt, ruta_base, sku, errores, feedback, historial, sesion):
    """Núcleo compartido: arma la corrección, genera, sube a Drive y devuelve
    (ruta_imagen, historial_actualizado, mensaje)."""
    correccion, historial_nuevo, resumen = _construir_correccion(errores, feedback, historial)

    service = _get_drive_service(sesion)
    _, carpeta_imagenes_id, _, logo_id = _preparar_estructura(service)

    nombre_archivo = f"{sku}_{slot}.jpg"
    ruta_local = f"/tmp/{nombre_archivo}"

    resultado = generar_foto_individual(
        prompt, ruta_base, ruta_local, sesion["gemini_key"], service, logo_id, correccion=correccion
    )
    if not resultado:
        return None, historial_nuevo, "❌ La IA no devolvió imagen. Intenta de nuevo o ajusta el feedback."

    _subir_imagen_drive(service, carpeta_imagenes_id, nombre_archivo, resultado)
    mensaje = f"✅ {nombre_archivo} regenerada y guardada en Drive.
{resumen}"
    return resultado, historial_nuevo, mensaje


def rehacer_hd(ruta_base, sku, errores, feedback, historial, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return None, historial, error
    if not ruta_base:
        return None, historial, "❌ Extrae los textos primero (necesito la foto base)."
    return _rehacer_generico("1_hd", PROMPT_HD, ruta_base, sku, errores, feedback, historial, sesion)


def rehacer_life(ruta_base, sku, nombre, marca, desc, errores, feedback, historial, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return None, historial, error
    if not ruta_base:
        return None, historial, "❌ Extrae los textos primero (necesito la foto base)."
    prompts = investigar_prompts(nombre, marca, desc, sesion["gemini_key"])
    return _rehacer_generico("2_uso", prompts['lifestyle'], ruta_base, sku, errores, feedback, historial, sesion)


def rehacer_comercial(ruta_base, sku, nombre, marca, desc, errores, feedback, historial, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return None, historial, error
    if not ruta_base:
        return None, historial, "❌ Extrae los textos primero (necesito la foto base)."
    prompts = investigar_prompts(nombre, marca, desc, sesion["gemini_key"])
    return _rehacer_generico("3_comercial", prompts['comercial'], ruta_base, sku, errores, feedback, historial, sesion)


def modulo_generar_todo(ruta_base, sku, nombre, marca, desc, request: gr.Request):
    """Primera pasada: sin correcciones y reseteando el historial de feedback."""
    sesion, error = _validar_sesion(request)
    if error:
        yield error, None, None, None, [], [], []
        return
    if not ruta_base:
        yield "❌ Extrae los textos primero", None, None, None, [], [], []
        return

    yield "📸 Generando fondo blanco...", None, None, None, [], [], []
    out_1, _, _ = rehacer_hd(ruta_base, sku, [], "", [], request)

    yield "📸 Generando estilo de vida...", out_1, None, None, [], [], []
    out_2, _, _ = rehacer_life(ruta_base, sku, nombre, marca, desc, [], "", [], request)

    yield "📸 Generando comercial épica...", out_1, out_2, None, [], [], []
    out_3, _, _ = rehacer_comercial(ruta_base, sku, nombre, marca, desc, [], "", [], request)

    yield (
        "✅ ¡Set fotográfico completo, guardado en tu Google Drive! "
        "Si algo salió mal, usa el panel 🔧 de cada imagen para decirle a la IA qué corregir.",
        out_1, out_2, out_3, [], [], []
    )


def guardar_excel_final(sku, tipo, sku_padre, nombre, marca, gramaje, precio, cat, subcat,
                        desc_corta, desc_larga, request: gr.Request):
    sesion, error = _validar_sesion(request, requiere_api_key=False)
    if error:
        return error
    if not sku:
        return "❌ Error: No hay datos para guardar."
    try:
        service, csv_id, df = _cargar_df(sesion)
        carpeta_raiz_id, _, _, _ = _preparar_estructura(service)
        lista_imagenes_str = f"{sku}_1_hd.jpg, {sku}_2_uso.jpg, {sku}_3_comercial.jpg"
        nueva_fila = {
            'sku': sku, 'tipo': tipo,
            'sku_padre': sku_padre if tipo == "Variable" else "",
            'nombre_producto': nombre, 'marca': marca, 'gramaje': gramaje,
            'precio': precio, 'categoria': cat, 'subcategoria': subcat,
            'descripcion_corta': desc_corta, 'descripcion_larga': desc_larga,
            'imagenes': lista_imagenes_str
        }
        df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
        _guardar_csv_drive(service, carpeta_raiz_id, csv_id, df)
        return f"💾 ¡Guardado en tu Google Drive! El producto {sku} está en tu inventario maestro."
    except Exception as e:
        return f"❌ Error al guardar en Drive: {e}"


def detectar_padre(nombre_actual, request: gr.Request):
    if not nombre_actual:
        return ""
    sesion, error = _validar_sesion(request, requiere_api_key=False)
    if error:
        return "No detectado"
    try:
        _, _, df = _cargar_df(sesion)
        nombres_existentes = df['nombre_producto'].dropna().tolist()
        similares = difflib.get_close_matches(nombre_actual, nombres_existentes, n=1, cutoff=0.4)
        if similares:
            nombre_padre = similares[0]
            return df[df['nombre_producto'] == nombre_padre].iloc[0]['sku']
        return "No detectado"
    except Exception:
        return "No detectado"


def cambio_tipo_ui(tipo_seleccionado, nombre_actual, request: gr.Request):
    if tipo_seleccionado == "Variable":
        padre_detectado = detectar_padre(nombre_actual, request)
        return gr.update(visible=True, value=padre_detectado)
    return gr.update(visible=False, value="")


def recalcular_sku_ui(nombre, marca, gramaje):
    return generar_sku_logica(nombre, marca, gramaje)


def recalcular_precio_ui(nombre, marca, gramaje, categoria, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return 0
    datos_precio = estimar_precio_producto(nombre, marca, gramaje, categoria, sesion["gemini_key"])
    return datos_precio.get("precio_sugerido", 0)


def obtener_categorias(request: gr.Request):
    sesion, error = _validar_sesion(request, requiere_api_key=False)
    if error:
        return CATEGORIAS_DEFECTO
    try:
        _, _, df = _cargar_df(sesion)
        cats = df['categoria'].dropna().unique().tolist()
        return cats if cats else CATEGORIAS_DEFECTO
    except Exception:
        return CATEGORIAS_DEFECTO


def obtener_subcategorias(request: gr.Request):
    sesion, error = _validar_sesion(request, requiere_api_key=False)
    if error:
        return SUBCATEGORIAS_DEFECTO
    try:
        _, _, df = _cargar_df(sesion)
        subcats = df['subcategoria'].dropna().unique().tolist()
        return subcats if subcats else SUBCATEGORIAS_DEFECTO
    except Exception:
        return SUBCATEGORIAS_DEFECTO


# ==========================================
# 5.1 ESTADO DE LOGIN / CONFIGURACIÓN
# ==========================================
def _estado_login_html(request: gr.Request):
    sesion = _obtener_sesion(request)
    if sesion:
        email = sesion.get("email", "tu cuenta")
        tiene_key = "✅ guardada" if sesion.get("gemini_key") else "❌ falta guardarla abajo"
        return (
            f"<div style='padding:12px;border-radius:8px;background:#eafaf1;'>"
            f"✅ Conectado a Google Drive como <b>{email}</b> &nbsp;|&nbsp; "
            f"API Key de Gemini: {tiene_key} &nbsp;·&nbsp; <a href='/logout'>Cerrar sesión</a>"
            f"</div>"
        )
    return (
        "<div style='padding:12px;border-radius:8px;background:#fdecea;'>"
        "❌ No estás conectado. "
        "<a href='/login'><b>🔐 Conectar con Google Drive</b></a>"
        "</div>"
    )


def cargar_estado_inicial(request: gr.Request):
    html = _estado_login_html(request)
    cats = obtener_categorias(request)
    subcats = obtener_subcategorias(request)
    return html, gr.update(choices=cats), gr.update(choices=subcats)


def guardar_api_key(api_key_input, request: gr.Request):
    sesion = _obtener_sesion(request)
    if not sesion:
        return "❌ Primero conéctate con Google Drive.", _estado_login_html(request)
    if not api_key_input or not api_key_input.strip():
        return "❌ Ingresa una API key válida.", _estado_login_html(request)
    _guardar_sesion(request.cookies.get("session_id"), gemini_key=api_key_input.strip())
    return "✅ API Key guardada para tu sesión.", _estado_login_html(request)


def refrescar_categorias(request: gr.Request):
    return gr.update(choices=obtener_categorias(request)), gr.update(choices=obtener_subcategorias(request))


def limpiar_feedback():
    """Después de mandar el feedback, limpia los checkboxes y el texto libre
    (el historial se conserva en el State)."""
    return gr.update(value=[]), gr.update(value="")


# ==========================================
# 6. INTERFAZ GRÁFICA
# ==========================================
css_camara = """
video { transform: none !important; }
"""

with gr.Blocks(theme=gr.themes.Soft(), css=css_camara) as demo:
    memoria_ruta_base = gr.State(None)
    # Historial de correcciones por cada slot de imagen
    hist_1 = gr.State([])
    hist_2 = gr.State([])
    hist_3 = gr.State([])

    gr.Markdown("# 🛒 Suite Ecommerce (SEO, Precios, IA y Variantes)")
    estado_login = gr.HTML()

    with gr.Tabs():
        # ==================================
        # PESTAÑA 0: CONFIGURACIÓN
        # ==================================
        with gr.Tab("⚙️ Configuración"):
            gr.Markdown(
                "### 1. Conecta tu Google Drive
"
                "Usa el enlace de arriba (o el de abajo) para iniciar sesión con Google. "
                "Todo lo que generes se guardará en la carpeta `Proyecto_IA` de **tu propio Drive**.

"
                "### 2. Guarda tu API Key de Gemini
"
                "Se usa solo durante tu sesión; no se comparte con otros usuarios ni se guarda en el código."
            )
            gr.HTML("<a href='/login'><b>🔐 Conectar / Reconectar con Google Drive</b></a>")
            in_api_key = gr.Textbox(label="Tu API Key de Gemini (Google AI Studio)", type="password")
            btn_guardar_key = gr.Button("💾 Guardar API Key", variant="primary")
            estado_config = gr.Textbox(label="Estado", interactive=False)
            btn_refrescar_cats = gr.Button("🔄 Actualizar categorías desde mi Drive", size="sm")

        # ==================================
        # PESTAÑA 1: INGRESO Y EDICIÓN
        # ==================================
        with gr.Tab("1. Ingreso y Edición de Productos"):
            estado = gr.Textbox(label="Consola de Sistema", interactive=False, lines=4)

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 1. Imágenes y Análisis")
                    img1 = gr.Image(label="Foto Frontal", type="numpy", sources=["upload", "webcam", "clipboard"])
                    img2 = gr.Image(label="Foto Reverso (Opcional)", type="numpy", sources=["upload", "webcam", "clipboard"])
                    desc_input = gr.Textbox(label="Apuntes Extra", placeholder="Ej. Galletas coreanas edición limitada")
                    btn_extraer = gr.Button("🔍 Analizar Producto (SEO + Info + Precio)", variant="primary")

                with gr.Column(scale=1):
                    gr.Markdown("### 2. Clasificación, Textos y Precio")
                    with gr.Group():
                        in_nombre = gr.Textbox(label="Nombre Comercial")
                        in_marca = gr.Textbox(label="Marca")
                        in_gramaje = gr.Textbox(label="Medida (Ej. 120G, 1L, 10PZ, 5OZ)")

                    with gr.Row():
                        in_precio = gr.Number(label="💲 Precio Sugerido (MXN)", precision=2)
                        btn_act_precio = gr.Button("🔄 Recalcular Precio", size="sm")

                    with gr.Row():
                        in_sku = gr.Textbox(label="SKU (Max 10 caracteres)", interactive=True)
                        btn_act_sku = gr.Button("🔄 Recalcular SKU", size="sm")

                    with gr.Group():
                        in_tipo = gr.Radio(["Simple", "Variable"], label="Tipo de Producto", value="Simple")
                        in_sku_padre = gr.Textbox(label="SKU Padre Detectado", visible=False, interactive=True)

                    with gr.Group():
                        in_cat = gr.Dropdown(choices=CATEGORIAS_DEFECTO, label="Categoría (Estricta)")
                        in_subcat = gr.Dropdown(choices=SUBCATEGORIAS_DEFECTO, label="Subcategoría (Estricta)")

                    in_desc_corta = gr.Textbox(label="Desc. Corta (SEO - max 150 carácteres)", lines=2)
                    in_desc_larga = gr.Textbox(label="Desc. Larga (SEO - Viñetas y Beneficios)", lines=5)

                with gr.Column(scale=2):
                    gr.Markdown("### 3. Estudio Fotográfico IA (Formato Cuadrado)")
                    btn_generar_fotos = gr.Button("✨ Generar Set de 3 Fotos Comerciales", variant="primary")
                    gr.Markdown(
                        "_¿Salió mal una foto? Abre su panel **🔧 ¿Qué salió mal?**, marca el error "
                        "(empaque inventado, logo que no existe, mala escala...) y dale Rehacer. "
                        "La IA recibe esa retroalimentación y las correcciones se van acumulando en cada intento._"
                    )

                    with gr.Row():
                        # ---------- Slot 1: Fondo blanco ----------
                        with gr.Column():
                            out_img1 = gr.Image(label="Fondo Blanco")
                            with gr.Accordion("🔧 ¿Qué salió mal? (Fondo Blanco)", open=False):
                                err_1 = gr.CheckboxGroup(choices=ETIQUETAS_ERRORES, label="Errores detectados")
                                fb_1 = gr.Textbox(
                                    label="Otra corrección (texto libre)",
                                    placeholder="Ej. la tapa es roja, no azul",
                                    lines=2,
                                )
                                btn_limpiar_hist_1 = gr.Button("🧹 Olvidar correcciones previas", size="sm")
                            btn_rehacer_1 = gr.Button("🔄 Rehacer HD con feedback")

                        # ---------- Slot 2: Lifestyle ----------
                        with gr.Column():
                            out_img2 = gr.Image(label="Lifestyle")
                            with gr.Accordion("🔧 ¿Qué salió mal? (Lifestyle)", open=False):
                                err_2 = gr.CheckboxGroup(choices=ETIQUETAS_ERRORES, label="Errores detectados")
                                fb_2 = gr.Textbox(
                                    label="Otra corrección (texto libre)",
                                    placeholder="Ej. la mano tapa el nombre del producto",
                                    lines=2,
                                )
                                btn_limpiar_hist_2 = gr.Button("🧹 Olvidar correcciones previas", size="sm")
                            btn_rehacer_2 = gr.Button("🔄 Rehacer Life con feedback")

                        # ---------- Slot 3: Comercial ----------
                        with gr.Column():
                            out_img3 = gr.Image(label="Comercial")
                            with gr.Accordion("🔧 ¿Qué salió mal? (Comercial)", open=False):
                                err_3 = gr.CheckboxGroup(choices=ETIQUETAS_ERRORES, label="Errores detectados")
                                fb_3 = gr.Textbox(
                                    label="Otra corrección (texto libre)",
                                    placeholder="Ej. inventó un sello de 'premium quality'",
                                    lines=2,
                                )
                                btn_limpiar_hist_3 = gr.Button("🧹 Olvidar correcciones previas", size="sm")
                            btn_rehacer_3 = gr.Button("🔄 Rehacer Com con feedback")

            gr.Markdown("---")
            btn_guardar = gr.Button(
                "💾 APROBAR Y GUARDAR EN MI INVENTARIO (Google Drive)", variant="primary", size="lg"
            )

        # ==================================
        # PESTAÑA 2: VARIANTES DE PRESENTACIÓN (GOOGLE LENS IA)
        # ==================================
        with gr.Tab("2. Variantes de Presentación (Google Lens IA)"):
            gr.Markdown(
                "### 🔎 Busca con IA si el producto existe en otros gramajes/tamaños
"
                "Sube o reutiliza la foto del producto para que la IA lo identifique visualmente "
                "(como Google Lens) y busque en internet si existen otras presentaciones o gramajes "
                "del MISMO producto. Así sabrás si conviene marcarlo como **Variable** en la Pestaña 1 "
                "en vez de **Simple**."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    img_lens = gr.Image(label="Foto del producto a investigar", type="numpy",
                                        sources=["upload", "webcam", "clipboard"])
                    btn_usar_foto_tab1 = gr.Button("📋 Usar foto de la Pestaña 1", size="sm")
                    btn_buscar_lens = gr.Button("🔍 Buscar Variantes con Google Lens (IA)", variant="primary")
                with gr.Column(scale=2):
                    recomendacion_tipo_box = gr.Textbox(label="Recomendación", interactive=False)
                    reporte_variantes = gr.Markdown(label="Reporte de Variantes Encontradas")
                    state_tipo_recomendado = gr.State("Simple")
                    btn_aplicar_recomendacion = gr.Button("✅ Aplicar recomendación de Tipo en la Pestaña 1")

    # ==========================================
    # 7. CONEXIONES
    # ==========================================
    demo.load(cargar_estado_inicial, inputs=None, outputs=[estado_login, in_cat, in_subcat])

    btn_guardar_key.click(guardar_api_key, inputs=[in_api_key], outputs=[estado_config, estado_login])
    btn_refrescar_cats.click(refrescar_categorias, inputs=None, outputs=[in_cat, in_subcat])

    entradas_textos = [img1, img2, desc_input]
    salidas_textos = [estado, in_sku, in_nombre, in_marca, in_gramaje, in_precio, in_tipo,
                      in_sku_padre, in_cat, in_subcat, in_desc_corta, in_desc_larga, memoria_ruta_base]
    btn_extraer.click(modulo_extraer_textos, inputs=entradas_textos, outputs=salidas_textos)

    btn_act_sku.click(recalcular_sku_ui, inputs=[in_nombre, in_marca, in_gramaje], outputs=[in_sku])
    btn_act_precio.click(recalcular_precio_ui, inputs=[in_nombre, in_marca, in_gramaje, in_cat], outputs=[in_precio])
    in_tipo.change(cambio_tipo_ui, inputs=[in_tipo, in_nombre], outputs=[in_sku_padre])

    # Primera pasada: resetea los 3 historiales de feedback
    btn_generar_fotos.click(
        modulo_generar_todo,
        inputs=[memoria_ruta_base, in_sku, in_nombre, in_marca, in_desc_corta],
        outputs=[estado, out_img1, out_img2, out_img3, hist_1, hist_2, hist_3]
    )

    # Re-generaciones con retroalimentación
    btn_rehacer_1.click(
        rehacer_hd,
        inputs=[memoria_ruta_base, in_sku, err_1, fb_1, hist_1],
        outputs=[out_img1, hist_1, estado]
    ).then(limpiar_feedback, inputs=None, outputs=[err_1, fb_1])

    btn_rehacer_2.click(
        rehacer_life,
        inputs=[memoria_ruta_base, in_sku, in_nombre, in_marca, in_desc_corta, err_2, fb_2, hist_2],
        outputs=[out_img2, hist_2, estado]
    ).then(limpiar_feedback, inputs=None, outputs=[err_2, fb_2])

    btn_rehacer_3.click(
        rehacer_comercial,
        inputs=[memoria_ruta_base, in_sku, in_nombre, in_marca, in_desc_corta, err_3, fb_3, hist_3],
        outputs=[out_img3, hist_3, estado]
    ).then(limpiar_feedback, inputs=None, outputs=[err_3, fb_3])

    btn_limpiar_hist_1.click(lambda: ([], "🧹 Historial de correcciones (Fondo Blanco) reiniciado."),
                             inputs=None, outputs=[hist_1, estado])
    btn_limpiar_hist_2.click(lambda: ([], "🧹 Historial de correcciones (Lifestyle) reiniciado."),
                             inputs=None, outputs=[hist_2, estado])
    btn_limpiar_hist_3.click(lambda: ([], "🧹 Historial de correcciones (Comercial) reiniciado."),
                             inputs=None, outputs=[hist_3, estado])

    btn_guardar.click(
        guardar_excel_final,
        inputs=[in_sku, in_tipo, in_sku_padre, in_nombre, in_marca, in_gramaje, in_precio,
                in_cat, in_subcat, in_desc_corta, in_desc_larga],
        outputs=[estado]
    )

    btn_usar_foto_tab1.click(lambda x: x, inputs=[img1], outputs=[img_lens])
    btn_buscar_lens.click(
        buscar_variantes_por_imagen,
        inputs=[img_lens, in_nombre, in_marca],
        outputs=[recomendacion_tipo_box, reporte_variantes, state_tipo_recomendado]
    )
    btn_aplicar_recomendacion.click(
        lambda t: gr.update(value=t),
        inputs=[state_tipo_recomendado],
        outputs=[in_tipo]
    )

# ==========================================
# 8. MONTAJE FINAL (FastAPI + Gradio)
# ==========================================
gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
