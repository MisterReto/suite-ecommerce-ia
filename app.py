# Runtime compartido de OAuth, sesiones, Drive/Sheets y funciones históricas; contiene partes del generador protegidas.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
# ==========================================
# IMPORTANTE: estas variables deben quedar ANTES de importar oauthlib,
# porque la librería las lee al momento de importarse.
# ==========================================
import os

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
os.environ.setdefault("OAUTHLIB_IGNORE_SCOPE_CHANGE", "1")

import io
import time
import html as html_lib
import re
import json
import secrets
import difflib
import traceback
import base64
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from PIL import Image, ImageOps
Image.MAX_IMAGE_PIXELS = 24_000_000

from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload

from google import genai
from gemini_gateway import GeminiClient, text_config
from product_generation import DESCRIPTION_RULES, clean_description, branded_image
from product_capture import ProductCapture, NEW_PARENT, EXISTING_PARENT
from pathlib import Path
from oauth_guard import issue_oauth, consume_oauth, email_allowed
from google.genai import types

def field_update(**values):
    """Structured field values used by catalog adapters, independent of the UI."""
    return values


# ==========================================
# 0. CONFIGURACIÓN INICIAL (variables de entorno / secretos)
# ==========================================
MODELO_TEXTO = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
MODELO_IMAGEN = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
MAX_INTENTOS_IMAGEN = max(1, min(3, int(os.getenv("GEMINI_IMAGE_ATTEMPTS", "1"))))
PUNTUACION_MINIMA_QA = 90

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


# Exige una variable de arranque y falla sin mostrar su valor secreto.
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
if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
    DRIVE_SCOPES=["openid","https://www.googleapis.com/auth/userinfo.email"]

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
NOMBRE_GOOGLE_SHEET = "inventario_completo"
NOMBRE_HOJA_INVENTARIO = "Gabo nueva"
NOMBRE_HOJA_VARIABLE = "Lista Variable"
# Se conserva únicamente para migrar automáticamente un inventario creado por
# una versión anterior de la app. El CSV no se elimina y queda como respaldo.
NOMBRE_CSV_LEGACY = "inventario_completo.csv"
NOMBRE_LOGO = "logo_rincon_asia.png"
NOMBRES_INVENTARIO_IMPORTABLE = (
    "inventario_completo.xlsx",
    "inventario_completo.xls",
    "inventario_completo.ods",
    "inventario_completo.csv",
)

COLUMNAS_INVENTARIO = [
    'sku_padre', 'tipo', 'sku', 'nombre_producto',
    'descripcion_corta', 'descripcion_larga', 'Existencias',
    'categoria', 'subcategoria', 'etiquetas', 'Web link imagen',
    'precio', 'Precio descuento', 'imagenes'
]

COLUMNAS_LISTA_VARIABLE = [
    'parent_sku', 'sku', 'stock_status', 'regular_price', 'images',
    'variante', 'categoria', 'subcategoria', 'name',
    'short_description', 'description', 'etiquetas'
]

CATEGORIAS_DEFECTO = ["Abarrotes", "Bebidas", "Cocina y Accesorios", "Dulces", "Snacks", "Ramen e Instantáneo", "Merch-store"]
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
    historial = [str(x)[:500] for x in (historial or [])][-8:]
    texto_libre = str(texto_libre or "")[:600]
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

    historial = historial[-8:]
    if not historial:
        return "", historial, "Primer intento (sin correcciones previas)."

    intento = len(historial)
    bloque = (
        "\n\n===== REGENERATION FEEDBACK =====\n"
        f"This is a RE-GENERATION. The previous output(s) were REJECTED by a human reviewer. "
        f"There are {intento} accumulated correction(s). You MUST fix every single one of them "
        f"while keeping everything that was already correct:\n"
    )
    for i, instruccion in enumerate(historial, start=1):
        bloque += f"{i}. {instruccion}\n"
    bloque += "===== END FEEDBACK =====\n"

    marcados = (errores_seleccionados or [])
    if texto_libre and texto_libre.strip():
        marcados = marcados + [texto_libre.strip()]

    if marcados:
        resumen = "🔧 Correcciones enviadas a la IA:\n" + "\n".join(
            f"  {i}. {t}" for i, t in enumerate(marcados, start=1)
        )
    else:
        resumen = f"🔧 Reintento arrastrando {intento} corrección(es) anterior(es)."

    return bloque, historial, resumen


# ==========================================
# 0.2 ALMACÉN DE SESIONES (en memoria del proceso)
# ==========================================
SESSIONS = {}


# Genera el identificador aleatorio que recibirá la cookie de sesión.
def _nueva_session_id():
    return secrets.token_urlsafe(32)


# Revoca la sesión SQL, retira su copia local y limpia solo temporales de esa sesión.
def _eliminar_sesion(session_id):
    from catalog_platform.web_sessions import revoke
    revoke(session_id)
    session = SESSIONS.pop(session_id, None)
    namespace = (session or {}).get("file_namespace", "")
    if re.fullmatch(r"[A-Za-z0-9_-]{20,80}", namespace):
        for path in Path("/tmp").glob(namespace + "_*"):
            if path.is_file():
                path.unlink(missing_ok=True)


# Actualiza el registro en memoria y persiste la sesión cuando el almacén durable está
# disponible.
def _guardar_sesion(clave_sesion, **kwargs):
    """Crea o actualiza una sesión y conserva su ID dentro del registro.

    El parámetro se llama ``clave_sesion`` para que ``session_id`` pueda formar
    parte de los datos guardados sin colisionar con el argumento posicional.
    """
    if not clave_sesion:
        return
    if clave_sesion not in SESSIONS:
        now = time.time()
        for key, session in list(SESSIONS.items()):
            if session.get("expires_at", now + 1) < now:
                _eliminar_sesion(key)
        if len(SESSIONS) >= 500:
            raise RuntimeError("Servicio ocupado. Vuelve a conectar Drive en unos minutos.")
        SESSIONS[clave_sesion] = {}
    from catalog_platform.web_sessions import save
    value = dict(SESSIONS[clave_sesion], **kwargs)
    value["session_id"] = clave_sesion
    value["expires_at"] = time.time() + 8 * 3600
    save(clave_sesion, value)
    SESSIONS[clave_sesion].update(value)


# Obtiene la sesión validada desde la cookie y retira sesiones caducadas.
def _obtener_sesion(request: FastAPIRequest):
    if request is None:
        return None
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in SESSIONS:
        return None
    session = SESSIONS[session_id]
    if session.get("expires_at", 0) <= time.time():
        _eliminar_sesion(session_id)
        return None
    return session


# Devuelve sesión o error de acceso para las funciones compatibles.
def _validar_sesion(request: FastAPIRequest, requiere_api_key=True):
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
fastapi_app = FastAPI(title="El Rincón de Asia · Suite e-commerce", docs_url=None, redoc_url=None, openapi_url=None)
fastapi_app.mount("/suite-static", StaticFiles(directory=STATIC_DIR), name="suite-static")


# Emite estado/PKCE y redirige a Google; el frontend actual llega aquí por /auth/start
# después de comprobar salud.
@fastapi_app.get("/login")
def login():
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=DRIVE_SCOPES, redirect_uri=GOOGLE_REDIRECT_URI, autogenerate_code_verifier=True)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    issue_oauth(state, flow.code_verifier)
    resp = RedirectResponse(auth_url)
    resp.set_cookie(
        "oauth_state", state,
        httponly=True, secure=True, samesite="lax",
        path="/", max_age=600
    )
    resp.set_cookie(
        "oauth_code_verifier", flow.code_verifier,
        httponly=True, secure=True, samesite="lax",
        path="/", max_age=600
    )
    return resp


# Consume estado una vez, intercambia el código, valida cuenta y crea cookie/sesión segura
# antes de volver al frontend.
@fastapi_app.get("/auth/callback")
def auth_callback(request: FastAPIRequest):
    """Intercambia el 'code' por el token.

    Claves para que NO truene en hostings con proxy (Render, HF Spaces...):
      - scopes=None  -> no se valida el orden/formato de los scopes que devuelve Google.
      - fetch_token(code=...) -> no se reconstruye la URL completa, así el esquema
        http/https del proxy deja de importar; state se valida primero.
      - Los errores no muestran tokens ni trazas internas.
    """
    try:
        params = dict(request.query_params)
        expected_state = request.cookies.get("oauth_state", "")
        if not expected_state or not secrets.compare_digest(expected_state, params.get("state", "")):
            return PlainTextResponse("Acceso Google caducado o inválido. Vuelve a conectar Drive.", status_code=400)

        if "error" in params or "code" not in params:
            return PlainTextResponse(
                "Google no completó el acceso. Vuelve a conectar Drive.", status_code=400
            )

        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=DRIVE_SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI,
            state=request.cookies.get("oauth_state"),
        )
        flow.code_verifier = consume_oauth(expected_state, params.get("state", ""))
        flow.fetch_token(code=params["code"])
        creds = flow.credentials

        info_usuario = build("oauth2", "v2", credentials=creds).userinfo().get().execute()
        email = info_usuario.get("email", "")
        if not email or info_usuario.get("verified_email") is not True or not email_allowed(email):
            return PlainTextResponse("Cuenta no autorizada", status_code=403)
        _eliminar_sesion(request.cookies.get("session_id"))

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
            max_age=8 * 3600,
        )
        resp.delete_cookie("oauth_state", path="/")
        resp.delete_cookie("oauth_code_verifier", path="/")
        return resp

    except Exception:
        return PlainTextResponse("No pude completar el acceso a Google. Vuelve a conectar Drive.", status_code=500)


# Revoca la sesión y elimina la cookie mediante una solicitud explícita.
@fastapi_app.post("/logout")
def logout(request: FastAPIRequest):
    session_id = request.cookies.get("session_id")
    _eliminar_sesion(session_id)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("session_id", path="/")
    return resp


# ==========================================
# 2. UTILIDADES DE GOOGLE DRIVE (por usuario)
# ==========================================
# Construye el cliente Drive con las credenciales del usuario autenticado.
def _get_drive_service(sesion):
    from google_credentials import dedicated_credentials
    from drive_service import DriveService
    dedicated=dedicated_credentials()
    if dedicated:
        return DriveService(build("drive","v3",credentials=dedicated,cache_discovery=False),os.environ["GOOGLE_DRIVE_FOLDER_ID"])
    creds = Credentials.from_authorized_user_info(sesion["creds"], DRIVE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        sesion["creds"] = json.loads(creds.to_json())
    from drive_service import DriveService
    return DriveService(build("drive", "v3", credentials=creds, cache_discovery=False))


# Construye el cliente Sheets con la misma conexión Google de la sesión.
def _get_sheets_service(sesion):
    """Cliente de Google Sheets usando las mismas credenciales de Drive."""
    from google_credentials import dedicated_credentials
    creds = dedicated_credentials() or Credentials.from_authorized_user_info(sesion["creds"], DRIVE_SCOPES)
    if creds.expired and getattr(creds,"refresh_token",None):
        creds.refresh(GoogleAuthRequest())
        sesion["creds"] = json.loads(creds.to_json())
    return build("sheets", "v4", credentials=creds)


# Resuelve o crea una carpeta en el flujo histórico de preparación; no usar como lectura de
# taxonomía.
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


# Busca un archivo existente por nombre, carpeta y tipo MIME.
def _buscar_archivo(service, nombre, parent_id, mime_type=None):
    query = f"name = '{nombre}' and '{parent_id}' in parents and trashed = false"
    if mime_type:
        query += f" and mimeType = '{mime_type}'"
    res = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    archivos = res.get('files', [])
    return archivos[0]['id'] if archivos else None


def _buscar_inventario_importable(service, parent_id):
    """Encuentra el XLSX/ODS/CSV entregado dentro de la carpeta del cliente."""
    permitidos = {nombre.casefold() for nombre in NOMBRES_INVENTARIO_IMPORTABLE}
    encontrados = []
    page_token = None
    while True:
        respuesta = service.files().list(
            q=f"'{parent_id}' in parents and trashed = false",
            spaces="drive",
            pageSize=1000,
            pageToken=page_token,
            fields="nextPageToken,files(id,name,mimeType,modifiedTime)",
        ).execute()
        for archivo in respuesta.get("files", []):
            if str(archivo.get("name", "")).casefold() in permitidos:
                encontrados.append(archivo)
        page_token = respuesta.get("nextPageToken")
        if not page_token:
            break
    if not encontrados:
        return None
    prioridad = {nombre.casefold(): posicion for posicion, nombre in enumerate(NOMBRES_INVENTARIO_IMPORTABLE)}
    encontrados.sort(key=lambda item: prioridad.get(str(item.get("name", "")).casefold(), 999))
    return encontrados[0]


def _convertir_inventario_importable(service, carpeta_raiz_id):
    """Convierte el archivo subido a una hoja nativa sin borrar el original."""
    origen = _buscar_inventario_importable(service, carpeta_raiz_id)
    if not origen:
        return None

    buffer = io.BytesIO()
    descarga = MediaIoBaseDownload(buffer, service.files().get_media(fileId=origen["id"]))
    terminado = False
    while not terminado:
        _, terminado = descarga.next_chunk()
    buffer.seek(0)

    mime_origen = origen.get("mimeType") or "application/octet-stream"
    media = MediaIoBaseUpload(buffer, mimetype=mime_origen, resumable=False)
    metadata = {
        "name": NOMBRE_GOOGLE_SHEET,
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [carpeta_raiz_id],
        "description": f"Convertido automáticamente desde {origen.get('name', 'archivo importado')}.",
    }
    creado = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,mimeType",
    ).execute()
    return creado.get("id")


def _validar_inventario_preparado(sheets_service, spreadsheet_id):
    """Verifica la tabla canónica antes de permitir que la carpeta quede activa."""
    respuesta = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{NOMBRE_HOJA_INVENTARIO}'!A:N",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    values = respuesta.get("values", [])
    encabezados = [str(value or "").strip() for value in (values[0] if values else [])]
    faltantes = [columna for columna in COLUMNAS_INVENTARIO if columna not in encabezados]
    if faltantes:
        raise ValueError(
            "El inventario no tiene la estructura esperada. Faltan: "
            + ", ".join(faltantes)
        )
    filas = sum(
        1 for row in values[1:]
        if any(str(value or "").strip() for value in row[:len(COLUMNAS_INVENTARIO)])
    )
    return filas


def _obtener_gid_inventario(sheets_service, spreadsheet_id):
    """Devuelve el sheetId de 'Gabo nueva'; crea o renombra la pestaña si hace falta."""
    libro = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    hojas = libro.get("sheets", [])

    for hoja in hojas:
        props = hoja.get("properties", {})
        if props.get("title") == NOMBRE_HOJA_INVENTARIO:
            return props["sheetId"]

    if len(hojas) == 1:
        gid = hojas[0]["properties"]["sheetId"]
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [{
                    "updateSheetProperties": {
                        "properties": {"sheetId": gid, "title": NOMBRE_HOJA_INVENTARIO},
                        "fields": "title",
                    }
                }]
            },
        ).execute()
        return gid

    respuesta = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": NOMBRE_HOJA_INVENTARIO}}}]},
    ).execute()
    return respuesta["replies"][0]["addSheet"]["properties"]["sheetId"]


def _aplicar_formato_base(sheets_service, spreadsheet_id, sheet_gid, agregar_reglas=False):
    """Replica la estructura visual principal de la pestaña 'Gabo nueva'."""
    requests = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_gid,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_gid,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(COLUMNAS_INVENTARIO),
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontFamily": "Arial", "bold": True},
                        "verticalAlignment": "BOTTOM",
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat(textFormat,verticalAlignment,wrapStrategy)",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_gid,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": 38},
                "fields": "pixelSize",
            }
        },
    ]

    # Anchos equivalentes a la hoja de referencia: A, B, C, D, E y F:N.
    for inicio, fin, pixeles in [
        (0, 1, 111),
        (1, 2, 100),
        (2, 3, 126),
        (3, 4, 313),
        (4, 5, 236),
        (5, 14, 100),
    ]:
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_gid,
                    "dimension": "COLUMNS",
                    "startIndex": inicio,
                    "endIndex": fin,
                },
                "properties": {"pixelSize": pixeles},
                "fields": "pixelSize",
            }
        })

    if agregar_reglas:
        naranja = {"red": 1.0, "green": 0.6, "blue": 0.0}
        verde = {"red": 0.7176471, "green": 0.88235295, "blue": 0.8039216}
        cyan = {"red": 0.0, "green": 1.0, "blue": 1.0}
        reglas = [
            # SKU diferente al SKU padre, igual que en la hoja de referencia.
            (2, 3, '=AND($C2<>"",$C2<>$A2)', cyan),
            (2, 3, '=COUNTIF($C$2:$C$1000,C2)>1', naranja),
            (3, 4, '=COUNTIF($D$2:$D$1000,D2)>1', naranja),
            (4, 5, '=COUNTIF($E$2:$E$1000,E2)>1', verde),
            (5, 6, '=COUNTIF($F$2:$F$1000,F2)>1', verde),
        ]
        for indice, (col_inicio, col_fin, formula, color) in enumerate(reglas):
            requests.append({
                "addConditionalFormatRule": {
                    "index": indice,
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_gid,
                            "startRowIndex": 1,
                            "endRowIndex": 1000,
                            "startColumnIndex": col_inicio,
                            "endColumnIndex": col_fin,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": formula}],
                            },
                            "format": {"backgroundColor": color},
                        },
                    },
                }
            })

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def _aplicar_formato_filas(sheets_service, spreadsheet_id, sheet_gid, inicio, fin):
    """Formatea únicamente las filas pobladas; inicio/fin son índices base cero."""
    if fin <= inicio:
        return
    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_gid,
                    "startRowIndex": inicio,
                    "endRowIndex": fin,
                    "startColumnIndex": 0,
                    "endColumnIndex": 14,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontFamily": "Arial"},
                        "verticalAlignment": "BOTTOM",
                    }
                },
                "fields": "userEnteredFormat(textFormat,verticalAlignment)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_gid,
                    "startRowIndex": inicio,
                    "endRowIndex": fin,
                    "startColumnIndex": 3,
                    "endColumnIndex": 6,
                },
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat.wrapStrategy",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_gid,
                    "startRowIndex": inicio,
                    "endRowIndex": fin,
                    "startColumnIndex": 6,
                    "endColumnIndex": 7,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "NUMBER", "pattern": "0"}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_gid,
                    "startRowIndex": inicio,
                    "endRowIndex": fin,
                    "startColumnIndex": 11,
                    "endColumnIndex": 13,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "CURRENCY", "pattern": '"$"#,##0.00'}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_gid,
                    "dimension": "ROWS",
                    "startIndex": inicio,
                    "endIndex": fin,
                },
                "properties": {"pixelSize": 21},
                "fields": "pixelSize",
            }
        },
    ]
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def _limpiar_valor_sheet(valor):
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return "" if valor is None else valor
    try:
        return valor.item()
    except Exception:
        return str(valor)


def _fila_formato_gabo(registro):
    """Convierte un diccionario/Series al orden exacto de 'Gabo nueva'."""
    obtener = registro.get
    tipo = _limpiar_valor_sheet(obtener('tipo', 'Simple')) or 'Simple'
    sku_padre = _limpiar_valor_sheet(obtener('sku_padre', '')) if tipo == 'Variable' else ''
    return [
        sku_padre,
        tipo,
        _limpiar_valor_sheet(obtener('sku', '')),
        _limpiar_valor_sheet(obtener('nombre_producto', '')),
        _limpiar_valor_sheet(obtener('descripcion_corta', '')),
        _limpiar_valor_sheet(obtener('descripcion_larga', '')),
        _limpiar_valor_sheet(obtener('Existencias', 1)) or 1,
        _limpiar_valor_sheet(obtener('categoria', '')),
        _limpiar_valor_sheet(obtener('subcategoria', '')),
        _limpiar_valor_sheet(obtener('etiquetas', '')),
        _limpiar_valor_sheet(obtener('Web link imagen', '')),
        _limpiar_valor_sheet(obtener('precio', 0)) or 0,
        _limpiar_valor_sheet(obtener('Precio descuento', 0)) or 0,
        _limpiar_valor_sheet(obtener('imagenes', '')),
    ]


def _obtener_o_crear_gid_lista_variable(sheets_service, spreadsheet_id):
    """Resuelve la pestaña canónica 'Lista Variable' sin duplicar variantes de mayúsculas."""
    libro = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    hojas = libro.get("sheets", [])

    for hoja in hojas:
        props = hoja.get("properties", {})
        if props.get("title") == NOMBRE_HOJA_VARIABLE:
            return props["sheetId"], False

    for hoja in hojas:
        props = hoja.get("properties", {})
        if str(props.get("title", "")).strip().casefold() == NOMBRE_HOJA_VARIABLE.casefold():
            gid = props["sheetId"]
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [{
                        "updateSheetProperties": {
                            "properties": {"sheetId": gid, "title": NOMBRE_HOJA_VARIABLE},
                            "fields": "title",
                        }
                    }]
                },
            ).execute()
            return gid, False

    respuesta = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": NOMBRE_HOJA_VARIABLE}}}]},
    ).execute()
    gid = respuesta["replies"][0]["addSheet"]["properties"]["sheetId"]
    return gid, True


def _variante_desde_nombre(nombre):
    """Fallback conservador para nuevas variantes; nunca modifica el nombre o descripciones."""
    texto = str(nombre or "").strip()
    patrones = [
        r'(\d+(?:[.,]\d+)?\s*(?:kg|mg|g|ml|l|oz|pz|piezas?|sobres?|sticks?))\b',
        r'(?:no\.?|#)\s*(\d+)\b',
    ]
    for patron in patrones:
        coincidencias = re.findall(patron, texto, flags=re.IGNORECASE)
        if coincidencias:
            valor = coincidencias[-1]
            if patron.startswith('(?:no'):
                return f"No. {valor}"
            return re.sub(r'\s+', '', valor)
    return ""


def _normalizar_fila_variable(fila):
    fila = list(fila[:len(COLUMNAS_LISTA_VARIABLE)])
    fila.extend([''] * (len(COLUMNAS_LISTA_VARIABLE) - len(fila)))
    return [_limpiar_valor_sheet(valor) for valor in fila]


def _fila_variable_desde_gabo(fila_gabo, variante=""):
    """Mapea campos por posición, sin resumir ni alterar nombres o descripciones."""
    fila = list(fila_gabo[:len(COLUMNAS_INVENTARIO)])
    fila.extend([''] * (len(COLUMNAS_INVENTARIO) - len(fila)))
    return [
        _limpiar_valor_sheet(fila[0]),   # sku_padre -> parent_sku
        _limpiar_valor_sheet(fila[2]),   # sku
        _limpiar_valor_sheet(fila[6]) or 1,
        _limpiar_valor_sheet(fila[11]) or 0,
        _limpiar_valor_sheet(fila[13]),
        _limpiar_valor_sheet(variante) or _variante_desde_nombre(fila[3]),
        _limpiar_valor_sheet(fila[7]),
        _limpiar_valor_sheet(fila[8]),
        _limpiar_valor_sheet(fila[3]),   # nombre exacto
        _limpiar_valor_sheet(fila[4]),   # descripción corta exacta
        _limpiar_valor_sheet(fila[5]),   # descripción larga exacta
        _limpiar_valor_sheet(fila[9]),   # etiquetas exactas
    ]


def _aplicar_formato_lista_variable(sheets_service, spreadsheet_id, sheet_gid,
                                    filas_pobladas, hoja_nueva=False):
    """Extiende el formato existente a la columna etiquetas y a filas recién añadidas."""
    fin_filas = max(2, filas_pobladas + 1)
    requests = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_gid,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_gid,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(COLUMNAS_LISTA_VARIABLE),
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontFamily": "Arial", "bold": True},
                        "verticalAlignment": "BOTTOM",
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat(textFormat,verticalAlignment,wrapStrategy)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_gid,
                    "startRowIndex": 1,
                    "endRowIndex": fin_filas,
                    "startColumnIndex": 8,
                    "endColumnIndex": 12,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontFamily": "Arial", "fontSize": 10},
                        "verticalAlignment": "BOTTOM",
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat(textFormat,verticalAlignment,wrapStrategy)",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_gid,
                    "dimension": "COLUMNS",
                    "startIndex": 11,
                    "endIndex": 12,
                },
                "properties": {"pixelSize": 220},
                "fields": "pixelSize",
            }
        },
    ]

    if hoja_nueva:
        for inicio, fin, pixeles in [
            (0, 2, 126), (2, 3, 90), (3, 4, 105), (4, 5, 260),
            (5, 6, 100), (6, 8, 145), (8, 9, 300), (9, 10, 280),
            (10, 11, 400),
        ]:
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_gid,
                        "dimension": "COLUMNS",
                        "startIndex": inicio,
                        "endIndex": fin,
                    },
                    "properties": {"pixelSize": pixeles},
                    "fields": "pixelSize",
                }
            })

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def _sincronizar_lista_variable(sheets_service, spreadsheet_id, registro_nuevo=None,
                                crear_desde_variables=False):
    """Sincroniza por SKU desde 'Gabo nueva'.

    La selección y el orden de una Lista Variable existente se conservan. Solo se
    reemplazan name, short_description, description y etiquetas con los valores
    literales del mismo SKU en Gabo nueva. Un registro recién guardado se añade
    únicamente cuando fue marcado como Variable.
    """
    sheet_gid, hoja_nueva = _obtener_o_crear_gid_lista_variable(
        sheets_service, spreadsheet_id
    )
    resultado_gabo = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{NOMBRE_HOJA_INVENTARIO}'!A:N",
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    valores_gabo = resultado_gabo.get('values', [])
    mapa_gabo = {}
    for fila in valores_gabo[1:]:
        completa = list(fila[:len(COLUMNAS_INVENTARIO)])
        completa.extend([''] * (len(COLUMNAS_INVENTARIO) - len(completa)))
        sku = str(completa[2] or '').strip()
        if sku:
            mapa_gabo[sku] = completa

    resultado_lista = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{NOMBRE_HOJA_VARIABLE}'!A:L",
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    valores_lista = resultado_lista.get('values', [])
    filas_lista = [_normalizar_fila_variable(fila) for fila in valores_lista[1:]]

    sincronizadas = 0
    skus_lista = set()
    for fila in filas_lista:
        sku = str(fila[1] or '').strip()
        if sku:
            skus_lista.add(sku)
        fuente = mapa_gabo.get(sku)
        if not fuente:
            continue
        fila[8:12] = [
            _limpiar_valor_sheet(fuente[3]),
            _limpiar_valor_sheet(fuente[4]),
            _limpiar_valor_sheet(fuente[5]),
            _limpiar_valor_sheet(fuente[9]),
        ]
        sincronizadas += 1

    nuevas = []
    if not filas_lista and (crear_desde_variables or hoja_nueva):
        for fuente in mapa_gabo.values():
            if str(fuente[1] or '').strip().casefold() == 'variable':
                nuevas.append(_fila_variable_desde_gabo(fuente))

    if registro_nuevo:
        sku_nuevo = str(registro_nuevo.get('sku', '') or '').strip()
        tipo_nuevo = str(registro_nuevo.get('tipo', '') or '').strip().casefold()
        if sku_nuevo and tipo_nuevo == 'variable' and sku_nuevo not in skus_lista:
            fuente = mapa_gabo.get(sku_nuevo) or _fila_formato_gabo(registro_nuevo)
            nuevas.append(_fila_variable_desde_gabo(
                fuente, variante=registro_nuevo.get('variante', '')
            ))

    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{NOMBRE_HOJA_VARIABLE}'!A1:L1",
        valueInputOption='RAW',
        body={'values': [COLUMNAS_LISTA_VARIABLE]},
    ).execute()

    if filas_lista:
        valores_exactos = [fila[8:12] for fila in filas_lista]
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{NOMBRE_HOJA_VARIABLE}'!I2:L{len(filas_lista) + 1}",
            valueInputOption='RAW',
            body={'values': valores_exactos},
        ).execute()

    for fila in nuevas:
        sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{NOMBRE_HOJA_VARIABLE}'!A:L",
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': [fila]},
        ).execute()

    total_filas = len(filas_lista) + len(nuevas)
    _aplicar_formato_lista_variable(
        sheets_service, spreadsheet_id, sheet_gid, total_filas,
        hoja_nueva=hoja_nueva,
    )
    return {
        'sincronizadas': sincronizadas,
        'nuevas': len(nuevas),
        'total': total_filas,
    }


def _crear_o_encontrar_inventario(service, sheets_service, carpeta_raiz_id):
    mime_sheet = 'application/vnd.google-apps.spreadsheet'
    spreadsheet_id = _buscar_archivo(
        service, NOMBRE_GOOGLE_SHEET, carpeta_raiz_id, mime_type=mime_sheet
    )
    creado = False
    if spreadsheet_id is None:
        # Una carpeta descargada y vuelta a subir contiene un XLSX, no una hoja
        # nativa. Lo convertimos una sola vez y conservamos el archivo original.
        spreadsheet_id = _convertir_inventario_importable(service, carpeta_raiz_id)

    if spreadsheet_id is None:
        creado = True
        metadata = {
            'name': NOMBRE_GOOGLE_SHEET,
            'mimeType': mime_sheet,
            'parents': [carpeta_raiz_id],
        }
        spreadsheet_id = service.files().create(body=metadata, fields='id').execute()['id']

    sheet_gid = _obtener_gid_inventario(sheets_service, spreadsheet_id)
    if creado:
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{NOMBRE_HOJA_INVENTARIO}'!A1:N1",
            valueInputOption='RAW',
            body={'values': [COLUMNAS_INVENTARIO]},
        ).execute()
    _aplicar_formato_base(
        sheets_service, spreadsheet_id, sheet_gid, agregar_reglas=creado
    )
    return spreadsheet_id, sheet_gid, creado


def _leer_csv_legacy(service, csv_id):
    if csv_id is None:
        return pd.DataFrame()
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
        return pd.DataFrame()


def _migrar_csv_legacy(service, sheets_service, carpeta_raiz_id, spreadsheet_id, sheet_gid):
    """Copia una vez el CSV anterior al nuevo Sheet; conserva el CSV como respaldo."""
    csv_id = _buscar_archivo(service, NOMBRE_CSV_LEGACY, carpeta_raiz_id, mime_type='text/csv')
    df_legacy = _leer_csv_legacy(service, csv_id)
    if df_legacy.empty:
        return 0
    filas = [_fila_formato_gabo(fila) for _, fila in df_legacy.iterrows()]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{NOMBRE_HOJA_INVENTARIO}'!A2:N{len(filas) + 1}",
        valueInputOption='RAW',
        body={'values': filas},
    ).execute()
    _aplicar_formato_filas(sheets_service, spreadsheet_id, sheet_gid, 1, len(filas) + 1)
    return len(filas)


# Prepara la estructura histórica Drive/Sheets; puede escribir, por eso la clasificación usa
# un lector separado.
def _preparar_estructura(service, sesion=None):
    """Asegura carpetas, imágenes y un Google Sheet nativo con formato Gabo nueva.

    Devuelve (carpeta_raiz_id, carpeta_imagenes_id, spreadsheet_id, logo_file_id_o_None).
    """
    if not sesion:
        raise RuntimeError("No hay una sesión de Google disponible.")
    carpeta_manual = sesion.get("carpeta_raiz_id_manual") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if os.getenv("DATABASE_URL") and carpeta_manual:
        # Preserve the operational Sheet during the SQL transition. Discovery
        # must not create or synchronize existing sheets on a read request.
        if hasattr(service, "root_id"):
            service.root_id = carpeta_manual
        images=_buscar_archivo(service,NOMBRE_SUBCARPETA_IMAGENES,carpeta_manual,"application/vnd.google-apps.folder")
        sheet=os.getenv("GOOGLE_SHEET_ID") or _buscar_archivo(service,NOMBRE_GOOGLE_SHEET,carpeta_manual,"application/vnd.google-apps.spreadsheet")
        if os.getenv("GOOGLE_SHEET_ID"):
            from drive_service import DriveService
            boundary = DriveService(service, carpeta_manual)
            if not boundary.owns(sheet) or boundary.metadata(sheet).get("mimeType") != "application/vnd.google-apps.spreadsheet":
                raise ValueError("GOOGLE_SHEET_ID no es una hoja nativa de la carpeta autorizada.")
        return carpeta_manual,images,sheet,_buscar_archivo(service,NOMBRE_LOGO,carpeta_manual)
    if carpeta_manual:
        carpeta_raiz_id = carpeta_manual
    else:
        carpeta_raiz_id = _buscar_o_crear_carpeta(service, NOMBRE_CARPETA_RAIZ)
    carpeta_imagenes_id = _buscar_o_crear_carpeta(
        service, NOMBRE_SUBCARPETA_IMAGENES, parent_id=carpeta_raiz_id
    )
    sheets_service = _get_sheets_service(sesion)
    spreadsheet_id, sheet_gid, creado = _crear_o_encontrar_inventario(
        service, sheets_service, carpeta_raiz_id
    )
    if creado:
        _migrar_csv_legacy(
            service, sheets_service, carpeta_raiz_id, spreadsheet_id, sheet_gid
        )
    if not sesion.get("lista_variable_verificada"):
        try:
            _sincronizar_lista_variable(
                sheets_service,
                spreadsheet_id,
                crear_desde_variables=creado,
            )
            sesion["lista_variable_verificada"] = True
        except Exception as e:
            # El inventario principal sigue disponible; el usuario verá el error
            # al guardar si la sincronización vuelve a fallar.
            print(f"⚠️ No se pudo sincronizar '{NOMBRE_HOJA_VARIABLE}': {type(e).__name__}")
    logo_id = _buscar_archivo(service, NOMBRE_LOGO, carpeta_raiz_id)
    return carpeta_raiz_id, carpeta_imagenes_id, spreadsheet_id, logo_id


# Extrae un ID de carpeta de una URL Drive o de un ID introducido por el usuario.
def _extraer_folder_id(texto):
    """Acepta una URL de carpeta de Drive o un ID puro y devuelve el ID."""
    if not texto:
        return None
    texto = texto.strip()
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', texto)
    if match:
        return match.group(1)
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', texto)
    if match:
        return match.group(1)
    return texto  # asumimos que ya nos pasaron el ID directamente


# Lee filas de la hoja canónica mediante Sheets y las devuelve como tabla por encabezados.
def _leer_google_sheet(sheets_service, spreadsheet_id):
    resultado = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{NOMBRE_HOJA_INVENTARIO}'!A:N",
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    valores = resultado.get('values', [])
    if len(valores) <= 1:
        return pd.DataFrame(columns=COLUMNAS_INVENTARIO)
    filas = []
    for fila in valores[1:]:
        completa = list(fila[:len(COLUMNAS_INVENTARIO)])
        completa.extend([''] * (len(COLUMNAS_INVENTARIO) - len(completa)))
        filas.append(completa)
    return pd.DataFrame(filas, columns=COLUMNAS_INVENTARIO)


# Añade una fila del guardado histórico respetando columnas y sincronización existente.
def _agregar_fila_google_sheet(sesion, spreadsheet_id, registro):
    sheets_service = _get_sheets_service(sesion)
    fila = _fila_formato_gabo(registro)
    respuesta = sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{NOMBRE_HOJA_INVENTARIO}'!A:N",
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body={'values': [fila]},
    ).execute()
    rango_actualizado = respuesta.get('updates', {}).get('updatedRange', '')
    match = re.search(r'![A-Z]+(\d+):[A-Z]+(\d+)$', rango_actualizado)
    if match:
        fila_uno = int(match.group(1))
        sheet_gid = _obtener_gid_inventario(sheets_service, spreadsheet_id)
        _aplicar_formato_filas(
            sheets_service, spreadsheet_id, sheet_gid, fila_uno - 1, fila_uno
        )
    _sincronizar_lista_variable(
        sheets_service,
        spreadsheet_id,
        registro_nuevo=registro,
    )
    return spreadsheet_id


# Obtiene el inventario compatible de la sesión; puede preparar estructura, no sirve para una
# lectura sin escrituras.
def _cargar_df(sesion):
    service = _get_drive_service(sesion)
    _, _, spreadsheet_id, _ = _preparar_estructura(service, sesion)
    sheets_service = _get_sheets_service(sesion)
    return service, spreadsheet_id, _leer_google_sheet(sheets_service, spreadsheet_id)


def _subir_imagen_drive(service, carpeta_imagenes_id, nombre_archivo, ruta_local):
    from drive_service import DriveService
    if os.getenv("STUDIO_IMAGE_JOBS") == "worker" and isinstance(service, DriveService):
        # Preserve the capture adapter and canonical ID, adding a backup only
        # for the explicitly enabled separated mode before any replacement.
        import hashlib
        digest = hashlib.sha256()
        with open(ruta_local, "rb") as stream:
            for chunk in iter(lambda: stream.read(512 * 1024), b""):
                digest.update(chunk)
        return service.save_approved(ruta_local, nombre_archivo, carpeta_imagenes_id,
                                     "capture-" + digest.hexdigest())["id"]
    media = MediaFileUpload(ruta_local, mimetype='image/jpeg', resumable=False)
    existente_id = _buscar_archivo(service, nombre_archivo, carpeta_imagenes_id)
    if existente_id:
        service.files().update(fileId=existente_id, media_body=media).execute()
        return existente_id
    metadata = {'name': nombre_archivo, 'parents': [carpeta_imagenes_id]}
    archivo = service.files().create(body=metadata, media_body=media, fields='id').execute()
    return archivo['id']


def _cargar_logo_marca(service, logo_id):
    # Each request owns its buffer; no shared /tmp file between sessions.
    if logo_id:
        try:
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, service.files().get_media(fileId=logo_id))
            listo = False
            while not listo:
                _, listo = downloader.next_chunk()
            buffer.seek(0)
            with Image.open(buffer) as logo:
                return logo.convert("RGBA")
        except Exception:
            pass  # The bundled official logo also works when Drive is unavailable.
    with Image.open(os.path.join(STATIC_DIR, "rincon-logo.png")) as logo:
        return logo.convert("RGBA")


# ==========================================
# 3. FUNCIONES DE APOYO (SKU, imágenes locales)
# ==========================================
def limpiar_texto_sku(texto):
    if not texto:
        return "XXX"
    texto = re.sub(r'[^a-zA-Z0-9]', '', str(texto))
    return texto.upper()


# Respaldo aceptado de diez caracteres: marca 3, nombre 3 y gramaje 4; se usa cuando no hay
# código válido.
def generar_sku_logica(nombre, marca, gramaje):
    """Genera un SKU de EXACTAMENTE 10 caracteres: Marca (3) + Nombre (3) + Gramaje (4).
    Si algún segmento es más corto, se rellena con 'X'; si es más largo, se recorta."""
    str_marca = limpiar_texto_sku(marca)[:3].ljust(3, 'X')
    str_nom = limpiar_texto_sku(nombre)[:3].ljust(3, 'X')
    str_gramaje = limpiar_texto_sku(gramaje)
    if not str_gramaje:
        str_gramaje = "00"
    str_gramaje = str_gramaje[:4].ljust(4, 'X')
    sku = f"{str_marca}{str_nom}{str_gramaje}"
    return sku[:10].ljust(10, 'X')


def comprimir_imagen(img_array, max_size=1024):
    img = Image.open(img_array) if isinstance(img_array, (str, os.PathLike)) else Image.fromarray(img_array)
    img = ImageOps.exif_transpose(img)
    img.thumbnail((max_size, max_size))
    return img


def estampar_logo(ruta_imagen, service, logo_id):
    logo = _cargar_logo_marca(service, logo_id)
    with Image.open(ruta_imagen) as image:
        final = branded_image(image, logo)
    final.save(ruta_imagen, format="JPEG", quality=95, optimize=True)


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
            if getattr(part, "thought", False):
                continue
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None) and str(getattr(inline, "mime_type", "")).startswith("image/"):
                data = inline.data
                return base64.b64decode(data, validate=True) if isinstance(data, str) else data
    return None


def _imagen_para_ia(path):
    """Small inline reference: avoids an extra Files API upload per call."""
    with open(path, "rb") as file:
        data = file.read()
    mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    return types.Part.from_bytes(data=data, mime_type=mime)


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
        client = GeminiClient(api_key=api_key)
        response = client.models.generate_content(
            model=MODELO_TEXTO,
            contents=prompt,
            config=text_config(1536, search=True, model=MODELO_TEXTO)
        )
        return _extraer_json(response.text)
    except Exception as e:
        print(f"⚠️ No se pudo estimar el precio automáticamente: {type(e).__name__}")
        return {"precio_min": 0, "precio_max": 0, "precio_sugerido": 0, "moneda": "MXN"}


def _obtener_vocabulario_etiquetas(df):
    """Junta todas las etiquetas ya usadas en el inventario (la columna guarda
    varias por celda, separadas por coma) en una lista única, sin repetidos."""
    if df is None or df.empty or 'etiquetas' not in df.columns:
        return []
    vistas = []
    for celda in df['etiquetas'].dropna().tolist():
        for etiqueta in str(celda).split(','):
            etiqueta = etiqueta.strip()
            if etiqueta and etiqueta.lower() not in [v.lower() for v in vistas]:
                vistas.append(etiqueta)
    return vistas


def _vocabulario_relevante(vocabulario, contexto, limite=80):
    palabras = set(re.findall(r"\w+", contexto.lower()))
    valores = list(dict.fromkeys(str(v).strip() for v in vocabulario if str(v).strip() and len(str(v)) <= 80))
    return sorted(valores, key=lambda v: (-len(palabras & set(re.findall(r"\w+", v.lower()))), v.lower()))[:limite]

def estimar_etiquetas_producto(nombre, marca, categoria, subcategoria, descripcion, vocabulario, api_key):
    """Si ya existen etiquetas en el catálogo, la IA SOLO puede elegir entre esas
    (nada de inventar nuevas). Si el catálogo todavía no tiene ninguna, la IA
    propone unas pocas para empezar a construir el vocabulario."""
    if not nombre:
        return []
    nombre, marca, categoria, subcategoria = [str(x or "")[:180] for x in (nombre, marca, categoria, subcategoria)]
    descripcion = str(descripcion or "")[:1000]
    vocabulario = _vocabulario_relevante(vocabulario, " ".join([nombre, marca, categoria, subcategoria, descripcion]))
    if vocabulario:
        instruccion = (
            f"Debes elegir ÚNICAMENTE etiquetas de esta lista que YA EXISTE en el catálogo, escogiendo "
            f"solo las que apliquen a este producto (puede ser ninguna, una, o varias): {vocabulario}. "
            f"NO inventes etiquetas que no estén en esa lista, y respeta la ortografía exacta con la que "
            f"aparecen ahí."
        )
    else:
        instruccion = (
            "Todavía no hay etiquetas en el catálogo. Sugiere entre 2 y 5 etiquetas cortas y reutilizables "
            "(en español; sin alegaciones dietéticas, de salud o certificaciones no verificadas) "
            "que describan bien este producto y sirvan para clasificar productos parecidos en el futuro."
        )
    prompt = (
        f"Producto: '{nombre}', marca '{marca}', categoría '{categoria}', subcategoría '{subcategoria}'. "
        f"Contexto adicional: '{descripcion}'. {instruccion} "
        f"Devuelve ÚNICAMENTE un JSON estricto, sin texto adicional ni markdown, con una sola clave "
        f"'etiquetas' (array de strings)."
    )
    try:
        client = GeminiClient(api_key=api_key)
        response = client.models.generate_content(model=MODELO_TEXTO, contents=prompt, config=text_config(768, model=MODELO_TEXTO))
        datos = _extraer_json(response.text)
        etiquetas = [e for e in (datos.get("etiquetas", []) or []) if isinstance(e, str)][:5]
        if vocabulario:
            vocab_lower = {v.lower(): v for v in vocabulario}
            etiquetas = [vocab_lower[e.lower()] for e in etiquetas if e.lower() in vocab_lower]
        return etiquetas
    except Exception as e:
        print(f"⚠️ No se pudieron estimar las etiquetas: {type(e).__name__}")
        return []


def recalcular_etiquetas_ui(nombre, marca, categoria, subcategoria, descripcion, request: FastAPIRequest):
    sesion, error = _validar_sesion(request)
    if error:
        return ""
    _, _, df = _cargar_df(sesion)
    vocabulario = _obtener_vocabulario_etiquetas(df)
    etiquetas = estimar_etiquetas_producto(nombre, marca, categoria, subcategoria, descripcion, vocabulario, sesion["gemini_key"])
    return ", ".join(etiquetas)


def buscar_variantes_por_imagen(imagen, nombre_actual, marca_actual, request: FastAPIRequest):
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
        buffer_imagen = io.BytesIO()
        img_pil.save(buffer_imagen, format="JPEG", quality=85)

        client = GeminiClient(api_key=api_key)
        archivo_ref = types.Part.from_bytes(data=buffer_imagen.getvalue(), mime_type="image/jpeg")

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
            f"Devuelve ÚNICAMENTE un JSON estricto, sin texto adicional ni markdown, con las claves:\n"
            f"'producto_identificado' (string), 'marca_identificada' (string),\n"
            f"'tiene_variantes' (booleano), 'variantes' (lista de objetos con 'gramaje', 'fuente', 'precio_aprox'),\n"
            f"'justificacion' (string breve)."
        )

        response = client.models.generate_content(
            model=MODELO_TEXTO,
            contents=[archivo_ref, prompt],
            config=text_config(1536, search=True, model=MODELO_TEXTO)
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

        reporte = f"### 🔍 Producto identificado: {producto} ({marca})\n\n"
        if variantes:
            reporte += "| Gramaje/Tamaño | Fuente | Precio aprox. |\n|---|---|---|\n"
            for v in variantes:
                reporte += f"| {v.get('gramaje','-')} | {v.get('fuente','-')} | {v.get('precio_aprox','-')} |\n"
        else:
            reporte += "_No se encontraron otras presentaciones a la venta actualmente._\n"
        reporte += f"\n**Justificación de la IA:** {justificacion}"

        return recomendacion, reporte, tipo_recomendado
    except Exception as e:
        return f"❌ Error en la búsqueda visual: {type(e).__name__}", "", "Simple"


def investigar_prompts(producto, marca, desc, api_key):
    from creative_pipeline import brief, fallback_brief
    product = {"name": producto, "brand": marca, "description": desc}
    try:
        return brief(GeminiClient(api_key), product)
    except Exception:
        return fallback_brief(product)


def _rutas_referencia(ruta_base):
    """Acepta una foto (versiones anteriores) o frontal+reverso (versión actual)."""
    if isinstance(ruta_base, (list, tuple)):
        return [ruta for ruta in ruta_base if ruta and os.path.exists(ruta)]
    return [ruta_base] if ruta_base and os.path.exists(ruta_base) else []


def _configuracion_imagen_cuadrada():
    """Fuerza 1:1 en la API; conserva compatibilidad con SDKs antiguos."""
    try:
        return types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="1:1"),
        )
    except (AttributeError, TypeError):
        return types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])


def _contrato_visual(slot):
    from creative_pipeline import FIDELITY
    scenes = {
        "1_hd": "Pure white seamless catalog backdrop, full product centered.",
        "2_uso": "Visible adults must actively consume or correctly use this product. Allow natural hands and interaction; preserve recognizable packaging.",
        "3_comercial": "Artistically decorate the hero product with original illustration, expressive colors, movement and depth; keep the real package unchanged.",
    }
    return FIDELITY + scenes.get(slot, "Keep product recognizable.")


def _validacion_local_imagen(ruta_imagen):
    try:
        with Image.open(ruta_imagen) as img:
            img.verify()
        with Image.open(ruta_imagen) as img:
            ancho, alto = img.size
            extrema = img.convert("RGB").getextrema()
            transparent = "A" in img.getbands() and img.getchannel("A").getextrema()[1] == 0
        errores = []
        if transparent or max(high - low for low, high in extrema) < 8:
            errores.append("The output is blank or nearly uniform; the product is missing.")
        if ancho != alto:
            errores.append(f"Output is {ancho}x{alto}; it must be exactly square 1:1.")
        if min(ancho, alto) < 1024:
            errores.append(f"Output is only {ancho}x{alto}; minimum accepted size is 1024x1024.")
        return errores
    except Exception as e:
        return [f"The generated file is not a valid readable image: {type(e).__name__}"]


def _validar_con_vision(client, archivos_referencia, ruta_generada, slot):
    """Un segundo pase de visión actúa como control de calidad antes de subir a Drive."""
    try:
        candidato = _imagen_para_ia(ruta_generada)
        prompt_qa = (
            "You are a strict e-commerce image quality inspector. The first attached image(s) are the real product "
            "references; the last attached image is the generated candidate. Compare only facts visible in those "
            "images. Reject the candidate if any product/package identity detail changed: object count, silhouette, "
            "geometry, material, color, closure, logo, character, artwork, label, readable wording, flavor, weight, "
            "number, certification mark or text layout. Reject invented or missing package elements, extra packages, "
            "product crop/occlusion, blur, or a non-square canvas. Tiny unreadable source text may remain unreadable, "
            "but it may not become invented legible text. Lifestyle requires adults actively using/consuming the product; natural hands, contact and opened food are allowed. Commercial allows original artistic decoration. Scene elements may be "
            "around the product without obscuring its identity; do not reject people or original decorative illustration. "
            f"Image type: {slot}. Return ONLY strict JSON with keys: "
            "'aprobada' (boolean), 'puntuacion' (integer 0-100), 'errores' (array of concise English correction "
            "instructions), and 'resumen' (short Spanish explanation for the user). Approve only if score is at least "
            f"{PUNTUACION_MINIMA_QA} and there are no identity or format errors."
        )
        respuesta = client.models.generate_content(
            model=MODELO_TEXTO,
            contents=archivos_referencia + [candidato, prompt_qa],
        )
        datos = _extraer_json(respuesta.text)
        puntuacion = int(datos.get("puntuacion", 0) or 0)
        errores = [str(x).strip() for x in (datos.get("errores", []) or []) if str(x).strip()]
        aprobada = datos.get("aprobada") is True and puntuacion >= PUNTUACION_MINIMA_QA and not errores
        return {
            "aprobada": aprobada,
            "puntuacion": puntuacion,
            "errores": errores,
            "resumen": str(datos.get("resumen", "")).strip(),
        }
    except Exception as e:
        return {
            "aprobada": False,
            "qa_unavailable": True,
            "puntuacion": 0,
            "technical_error": True,
            "errores": [f"The automatic visual comparison failed and the image cannot be approved: {type(e).__name__}"],
            "resumen": "No se pudo completar el control automático de fidelidad.",
        }


def generar_foto_individual(prompt, ruta_base, ruta_salida_local, api_key, service, logo_id,
                            slot, correccion=""):
    """Genera, compara contra la referencia y reintenta antes de guardar una imagen."""
    rutas_ref = _rutas_referencia(ruta_base)
    if not rutas_ref:
        return None

    try:
        client = GeminiClient(api_key=api_key)
        archivos_ref = [_imagen_para_ia(ruta) for ruta in rutas_ref]
        contrato = _contrato_visual(slot)
        errores_automaticos = []
        ultimo_qa = {"puntuacion": 0, "errores": [], "resumen": ""}

        for intento in range(1, MAX_INTENTOS_IMAGEN + 1):
            bloque_reintento = ""
            if errores_automaticos:
                bloque_reintento = (
                    "\n\nTHE PREVIOUS CANDIDATE WAS AUTOMATICALLY REJECTED. Fix every issue below without "
                    "changing anything else:\n- " + "\n- ".join(errores_automaticos)
                )
            prompt_seguro = f"{prompt}{contrato}{correccion}{bloque_reintento}"
            response = client.models.generate_content(
                model=MODELO_IMAGEN,
                contents=archivos_ref + [prompt_seguro],
                config=_configuracion_imagen_cuadrada(),
            )
            datos_imagen = _extraer_imagen_bytes(response)
            if not datos_imagen:
                errores_automaticos = ["The model returned no usable image. Generate a complete JPEG image."]
                ultimo_qa = {
                    "puntuacion": 0,
                    "errores": errores_automaticos,
                    "resumen": "La IA no devolvió una imagen utilizable.",
                }
                continue

            ruta_candidata = f"{ruta_salida_local}.intento_{intento}.jpg"
            with open(ruta_candidata, "wb") as f:
                f.write(datos_imagen)

            errores_locales = _validacion_local_imagen(ruta_candidata)
            if errores_locales:
                ultimo_qa = {
                    "aprobada": False,
                    "puntuacion": 0,
                    "errores": errores_locales,
                    "resumen": "La imagen no cumple el formato cuadrado o la resolución mínima.",
                }
            else:
                ultimo_qa = _validar_con_vision(client, archivos_ref, ruta_candidata, slot)
            if ultimo_qa.get("qa_unavailable"):
                os.remove(ruta_candidata)
                return {"ruta": None, "intentos": intento, "resumen": "Falló la revisión de IA; no se gastaron más generaciones. Reintenta esta imagen."}

            if ultimo_qa.get("aprobada"):
                # El modelo puede devolver PNG aunque el nombre final sea .jpg.
                # Re-encodeamos para que extensión, MIME y bytes siempre coincidan.
                with Image.open(ruta_candidata) as img_aprobada:
                    img_aprobada.convert("RGB").save(
                        ruta_salida_local, format="JPEG", quality=95, optimize=True
                    )
                try:
                    os.remove(ruta_candidata)
                except OSError:
                    pass
                try:
                    estampar_logo(ruta_salida_local, service, logo_id)
                except Exception:
                    Path(ruta_salida_local).unlink(missing_ok=True)
                    return {"ruta": None, "intentos": intento,
                            "resumen": "No se pudo aplicar la marca de agua. La imagen no se guardó."}
                return {
                    "ruta": ruta_salida_local,
                    "puntuacion": ultimo_qa.get("puntuacion", 0),
                    "intentos": intento,
                    "resumen": ultimo_qa.get("resumen", ""),
                }

            if ultimo_qa.get("technical_error"):
                Path(ruta_candidata).unlink(missing_ok=True)
                break
            errores_automaticos = ultimo_qa.get("errores") or [
                "Recreate the image with exact product fidelity and strict 1:1 format."
            ]
            try:
                os.remove(ruta_candidata)
            except OSError:
                pass

        print(f"❌ Imagen rechazada por QA tras {MAX_INTENTOS_IMAGEN} intentos: [detalles omitidos]")
        return {
            "ruta": None,
            "puntuacion": ultimo_qa.get("puntuacion", 0),
            "intentos": intento,
            "resumen": ultimo_qa.get("resumen", "No superó el control de calidad."),
            "errores": ultimo_qa.get("errores", []),
        }
    except Exception as e:
        return {"ruta": None, "intentos": 0, "resumen": f"Falló el servicio de imágenes ({type(e).__name__}). Revisa cuota, permisos del modelo y conexión."}


def modulo_extraer_textos(imagen_1, imagen_2, descripcion_breve, request: FastAPIRequest):
    sesion, error = _validar_sesion(request)
    if error:
        return [error, "", "", "", "", 0, "Simple", field_update(visible=False), "", "", "", "", "", None]
    if imagen_1 is None:
        return ["❌ Sube al menos la foto principal.", "", "", "", "", 0, "Simple",
                field_update(visible=False), "", "", "", "", "", None]

    sesion["capture_revision"] = secrets.token_urlsafe(18)
    sesion.pop("product_images", None)

    api_key = sesion["gemini_key"]
    client = GeminiClient(api_key=api_key)
    service, spreadsheet_id, df_actual = _cargar_df(sesion)

    lista_cats = df_actual['categoria'].dropna().unique().tolist() if 'categoria' in df_actual else []
    lista_cats = lista_cats if lista_cats else CATEGORIAS_DEFECTO
    lista_subcats = df_actual['subcategoria'].dropna().unique().tolist() if 'subcategoria' in df_actual else []
    lista_subcats = lista_subcats if lista_subcats else SUBCATEGORIAS_DEFECTO

    token_sesion = re.sub(r'[^a-zA-Z0-9_-]', '', sesion.setdefault("file_namespace", secrets.token_urlsafe(24)))[:64]
    archivos_ia = []
    img_1_pil = comprimir_imagen(imagen_1).convert("RGB")
    ruta_temp_1 = f"/tmp/{token_sesion}_temp_in_1.jpg"
    img_1_pil.save(ruta_temp_1, format="JPEG", quality=85)
    archivos_ia.append(_imagen_para_ia(ruta_temp_1))

    ruta_base_frontal = f"/tmp/{token_sesion}_base_gen_frontal.jpg"
    img_1_pil.save(ruta_base_frontal, format="JPEG", quality=95)
    rutas_base_memoria = [ruta_base_frontal]

    if imagen_2 is not None:
        img_2_pil = comprimir_imagen(imagen_2).convert("RGB")
        ruta_temp_2 = f"/tmp/{token_sesion}_temp_in_2.jpg"
        img_2_pil.save(ruta_temp_2, format="JPEG", quality=85)
        archivos_ia.append(_imagen_para_ia(ruta_temp_2))
        ruta_base_reverso = f"/tmp/{token_sesion}_base_gen_reverso.jpg"
        img_2_pil.save(ruta_base_reverso, format="JPEG", quality=95)
        rutas_base_memoria.append(ruta_base_reverso)

    vocabulario_etiquetas = _vocabulario_relevante(_obtener_vocabulario_etiquetas(df_actual), str(descripcion_breve or ""))
    prompt_datos = (
        f"Analiza el producto de las imágenes. Contexto extra: '{str(descripcion_breve or '')[:1000]}'. "
        f"Actúa como un experto en SEO para e-commerce. Devuelve un JSON estricto con:\n"
        f"1. 'nombre': El nombre del producto claro y comercial.\n"
        f"2. 'marca': La marca del producto.\n"
        f"3. 'gramaje': La unidad de medida y cantidad EXACTA. Puede ser G, KG, ML, L, OZ o PZ. "
        f"Ejemplo: '500G', '12OZ', '1L', '10PZ'.\n"
        f"4. 'categoria': Clasifícalo ESTRICTAMENTE usando SOLO una de las siguientes Categorías: "
        f"{lista_cats}. NO inventes ninguna.\n"
        f"5. 'subcategoria': Clasifícalo ESTRICTAMENTE usando SOLO una de las siguientes Subcategorías: "
        f"{lista_subcats}. NO inventes ninguna.\n"
        f"6-7. Descripciones: {DESCRIPTION_RULES}\n"
        f"8. 'etiquetas': hasta 5 strings. Si hay vocabulario, elige exclusivamente de: {vocabulario_etiquetas}. "
        "Sin vocabulario, propone etiquetas reutilizables sin alegaciones dietéticas o de salud no verificadas."
    )

    try:
        res_datos = client.models.generate_content(model=MODELO_TEXTO, contents=archivos_ia + [prompt_datos], config=text_config(1536, model=MODELO_TEXTO))
        datos = _extraer_json(res_datos.text)
    except Exception as e:
        return [f"❌ Error leyendo imagen: {type(e).__name__}", "", "", "", "", 0, "Simple",
                field_update(visible=False), "", "", "", "", "", None]

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
    etiquetas_sugeridas = [e for e in datos.get("etiquetas", []) if isinstance(e, str)][:5]
    if vocabulario_etiquetas:
        etiquetas_sugeridas = [e for e in etiquetas_sugeridas if e in vocabulario_etiquetas]
    etiquetas_str = ", ".join(etiquetas_sugeridas)

    return [
        "✅ Textos, precio y etiquetas sugeridas. Verifica SKU, Categorías, Precio y Etiquetas.",
        sku_gen, nombre, marca, gramaje, precio_sugerido, "Simple",
        field_update(visible=False), cat_final, subcat_final,
        clean_description(datos.get("desc_corta", ""), short=True), clean_description(datos.get("desc_larga", "")),
        etiquetas_str,
        rutas_base_memoria
    ]


# ==========================================
# 5. GENERACIÓN DE FOTOS Y GUARDADO (hacia el Drive del usuario)
# ==========================================
PROMPT_HD = (
    "Create a faithful e-commerce catalog photograph of the exact reference product. Preserve the reference "
    "view and product pixels as closely as possible. Use a pure white #FFFFFF seamless background, neutral "
    "color rendering, crisp edges and even studio lighting. Do not retouch or recreate package artwork."
)


def _rehacer_generico(slot, prompt, ruta_base, sku, errores, feedback, historial, sesion):
    """Núcleo compartido: arma la corrección, genera un borrador y devuelve
    (ruta_imagen, historial_actualizado, mensaje)."""
    correccion, historial_nuevo, resumen = _construir_correccion(errores, feedback, historial)

    service = _get_drive_service(sesion)
    _, _, _, logo_id = _preparar_estructura(service, sesion)
    revision = sesion.get("capture_revision")

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", str(sku)):
        return field_update(), historial_nuevo, "❌ SKU inválido: usa letras, números, guion o guion bajo."
    nombre_archivo = f"{sku}_{slot}.jpg"
    token_sesion = re.sub(r'[^a-zA-Z0-9_-]', '', sesion.setdefault("file_namespace", secrets.token_urlsafe(24)))[:64]
    rutas = _rutas_referencia(ruta_base)
    if not rutas or any(not Path(r).name.startswith(token_sesion + "_") or Path(r).parent != Path("/tmp") for r in rutas):
        return field_update(), historial_nuevo, "❌ Referencia de imagen inválida para esta sesión."
    ruta_local = f"/tmp/{token_sesion}_{sku}_{slot}_{secrets.token_urlsafe(12)}.jpg"

    resultado = generar_foto_individual(
        prompt, ruta_base, ruta_local, sesion["gemini_key"], service, logo_id,
        slot=slot, correccion=correccion
    )
    if not resultado:
        return field_update(), historial_nuevo, "❌ La IA no devolvió imagen. Intenta de nuevo o ajusta el feedback."
    if not resultado.get("ruta"):
        detalle = resultado.get("resumen") or "No conservó fielmente el producto."
        return (
            field_update(),
            historial_nuevo,
            f"⚠️ La imagen NO se guardó: fue rechazada automáticamente después de "
            f"{resultado.get('intentos', MAX_INTENTOS_IMAGEN)} intentos. {detalle}",
        )

    ruta_aprobada = resultado["ruta"]
    captura.stage_image(sesion, str(sku), slot, ruta_aprobada, revision)
    mensaje = (
        f"✅ {nombre_archivo} aprobada ({resultado.get('puntuacion', 0)}/100) "
        f"después de {resultado.get('intentos', 1)} intento(s). Vista previa: se subirá a Drive al pulsar Guardar.\n{resumen}"
    )
    return ruta_aprobada, historial_nuevo, mensaje


def rehacer_hd(ruta_base, sku, errores, feedback, historial, request: FastAPIRequest):
    sesion, error = _validar_sesion(request)
    if error:
        return None, historial, error
    if not ruta_base:
        return None, historial, "❌ Extrae los textos primero (necesito la foto base)."
    return _rehacer_generico("1_hd", PROMPT_HD, ruta_base, sku, errores, feedback, historial, sesion)


def rehacer_life(ruta_base, sku, nombre, marca, desc, errores, feedback, historial, request: FastAPIRequest):
    sesion, error = _validar_sesion(request)
    if error:
        return None, historial, error
    if not ruta_base:
        return None, historial, "❌ Extrae los textos primero (necesito la foto base)."
    prompts = investigar_prompts(nombre, marca, desc, sesion["gemini_key"])
    return _rehacer_generico("2_uso", prompts['lifestyle'], ruta_base, sku, errores, feedback, historial, sesion)


def rehacer_comercial(ruta_base, sku, nombre, marca, desc, errores, feedback, historial, request: FastAPIRequest):
    sesion, error = _validar_sesion(request)
    if error:
        return None, historial, error
    if not ruta_base:
        return None, historial, "❌ Extrae los textos primero (necesito la foto base)."
    prompts = investigar_prompts(nombre, marca, desc, sesion["gemini_key"])
    return _rehacer_generico("3_comercial", prompts['comercial'], ruta_base, sku, errores, feedback, historial, sesion)


def modulo_generar_todo(ruta_base, sku, nombre, marca, desc, request: FastAPIRequest):
    """Primera pasada: sin correcciones y reseteando el historial de feedback."""
    sesion, error = _validar_sesion(request)
    if error:
        yield error, None, None, None, [], [], []
        return
    if not ruta_base:
        yield "❌ Extrae los textos primero", None, None, None, [], [], []
        return

    outputs = [field_update(), field_update(), field_update()]
    messages = []
    yield "📸 Preparando las tres imágenes…", *outputs, [], [], []
    # One prompt request for both scenes instead of repeating it per photo.
    prompts = investigar_prompts(nombre, marca, desc, sesion["gemini_key"])
    for index, (slot, prompt) in enumerate([
        ("1_hd", PROMPT_HD), ("2_uso", prompts["lifestyle"]), ("3_comercial", prompts["comercial"])
    ]):
        yield "\n".join(messages + [f"📸 Generando imagen {index + 1}/3…"]), *outputs, [], [], []
        try:
            output, _, message = _rehacer_generico(slot, prompt, ruta_base, sku, [], "", [], sesion)
        except Exception as exc:
            output, message = field_update(), f"❌ Imagen {index + 1}: {type(exc).__name__}. Reintenta solo esta imagen."
        outputs[index] = output
        messages.append(message)
    yield "\n".join(messages), *outputs, [], [], []


# Guarda la ficha confirmada con su tipo, padre y campos en el inventario histórico.
def guardar_producto_sheet(sku, tipo, sku_padre, nombre, marca, gramaje, atributo_nombre,
                           atributo_valor, precio, cat, subcat, etiquetas,
                           desc_corta, desc_larga, request: FastAPIRequest):
    sesion, error = _validar_sesion(request, requiere_api_key=False)
    if error:
        return error
    if not sku:
        return "❌ Error: No hay datos para guardar."
    if tipo == "Variable":
        padre = str(sku_padre or "").strip()
        valor_atributo = str(atributo_valor or gramaje or "").strip()
        if not padre or padre.casefold() == "no detectado":
            return (
                "❌ Una variación necesita el SKU de un producto padre que ya exista "
                "como tipo variable en Lista completa."
            )
        if not valor_atributo:
            return "❌ Captura el valor de la variación (por ejemplo: 360ml, Fresa o 5 piezas)."
    try:
        _, spreadsheet_id, _ = _cargar_df(sesion)
        lista_imagenes_str = f"{sku}_1_hd.jpg,{sku}_2_uso.jpg,{sku}_3_comercial.jpg"
        nueva_fila = {
            'sku_padre': sku_padre if tipo == "Variable" else "",
            'tipo': tipo,
            'sku': sku,
            'variante': gramaje,
            'atributo_nombre': atributo_nombre or "Tamaño",
            'atributo_valor': atributo_valor or gramaje,
            'nombre_producto': nombre,
            'descripcion_corta': desc_corta,
            'descripcion_larga': desc_larga,
            'Existencias': 1,
            'categoria': cat,
            'subcategoria': subcat,
            'etiquetas': etiquetas,
            'Web link imagen': "",
            'precio': precio or 0,
            'Precio descuento': 0,
            'imagenes': lista_imagenes_str,
        }
        _agregar_fila_google_sheet(sesion, spreadsheet_id, nueva_fila)
        url_sheet = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
        return (
            f"💾 ¡Guardado en Google Sheets! El producto {sku} está en la pestaña "
            f"'{NOMBRE_HOJA_INVENTARIO}'.\n{url_sheet}"
        )
    except Exception as e:
        return f"❌ Error al guardar en Google Sheets: {e}"


def detectar_padre(nombre_actual, marca_actual, request: FastAPIRequest):
    """Busca en TU inventario ya guardado (no en internet) un producto existente
    parecido a este, para detectar de cuál SKU es variante. Si primero filtramos
    por la misma marca, la comparación de nombres es más precisa (dos productos de
    marcas distintas con nombres parecidos ya no se confunden entre sí)."""
    if not nombre_actual:
        return ""
    sesion, error = _validar_sesion(request, requiere_api_key=False)
    if error:
        return "No detectado"
    try:
        _, _, df = _cargar_df(sesion)
        if df.empty or 'nombre_producto' not in df.columns:
            return "No detectado"

        candidatos = df
        if 'tipo' in candidatos.columns:
            candidatos = candidatos[
                candidatos['tipo'].astype(str).str.strip().str.casefold() == 'variable'
            ]
        if candidatos.empty:
            return "No detectado"

        if marca_actual and 'marca' in candidatos.columns:
            mismos_marca = candidatos[
                candidatos['marca'].astype(str).str.strip().str.lower()
                == str(marca_actual).strip().lower()
            ]
            if not mismos_marca.empty:
                candidatos = mismos_marca

        nombres_existentes = candidatos['nombre_producto'].dropna().tolist()
        similares = difflib.get_close_matches(nombre_actual, nombres_existentes, n=1, cutoff=0.35)
        if similares:
            nombre_padre = similares[0]
            return candidatos[candidatos['nombre_producto'] == nombre_padre].iloc[0]['sku']
        return "No detectado"
    except Exception:
        return "No detectado"


def cambio_tipo_ui(tipo_seleccionado, nombre_actual, marca_actual, request: FastAPIRequest):
    if tipo_seleccionado == "Variable":
        padre_detectado = detectar_padre(nombre_actual, marca_actual, request)
        return field_update(visible=True, value=padre_detectado)
    return field_update(visible=False, value="")


def aplicar_recomendacion_tipo(tipo_recomendado, nombre_actual, marca_actual, request: FastAPIRequest):
    """Se dispara directo desde el botón 'Aplicar recomendación' de la pestaña Lens.
    A diferencia de antes, esto YA busca el SKU padre de inmediato en vez de esperar
    a que el cambio de valor de in_tipo dispare otro evento por su cuenta."""
    if tipo_recomendado == "Variable":
        padre_detectado = detectar_padre(nombre_actual, marca_actual, request)
        return field_update(value="Variable"), field_update(visible=True, value=padre_detectado)
    return field_update(value="Simple"), field_update(visible=False, value="")


def recalcular_sku_ui(nombre, marca, gramaje):
    return generar_sku_logica(nombre, marca, gramaje)


def recalcular_precio_ui(nombre, marca, gramaje, categoria, request: FastAPIRequest):
    sesion, error = _validar_sesion(request)
    if error:
        return 0
    datos_precio = estimar_precio_producto(nombre, marca, gramaje, categoria, sesion["gemini_key"])
    return datos_precio.get("precio_sugerido", 0)


def obtener_categorias(request: FastAPIRequest):
    sesion, error = _validar_sesion(request, requiere_api_key=False)
    if error:
        return CATEGORIAS_DEFECTO
    try:
        _, _, df = _cargar_df(sesion)
        cats = df['categoria'].dropna().unique().tolist()
        return cats if cats else CATEGORIAS_DEFECTO
    except Exception:
        return CATEGORIAS_DEFECTO


def obtener_subcategorias(request: FastAPIRequest):
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
def _estado_login_html(request: FastAPIRequest):
    sesion = _obtener_sesion(request)
    if sesion:
        email = html_lib.escape(str(sesion.get("email", "tu cuenta")))
        tiene_key = "✅ propia del cliente" if sesion.get("gemini_key") else "❌ falta configurarla"
        carpeta_nombre = (
            sesion.get("carpeta_raiz_nombre_manual") or "Carpeta del cliente"
            if sesion.get("carpeta_raiz_id_manual")
            else "Proyecto_IA (automática)"
        )
        carpeta_txt = html_lib.escape(str(carpeta_nombre))
        return (
            f"<div style='padding:12px;border-radius:8px;background:#eafaf1;'>"
            f"✅ Conectado a Google Drive como <b>{email}</b> &nbsp;|&nbsp; "
            f"API Key de Gemini: {tiene_key} &nbsp;|&nbsp; Carpeta: {carpeta_txt} "
            f"&nbsp;·&nbsp; <a href='/logout'>Cerrar sesión</a>"
            f"</div>"
        )
    return (
        "<div style='padding:12px;border-radius:8px;background:#fdecea;'>"
        "❌ No estás conectado. "
        "<a href='/login'><b>🔐 Conectar con Google Drive</b></a>"
        "</div>"
    )


def cargar_estado_inicial(request: FastAPIRequest):
    html = _estado_login_html(request)
    cats, subcats = CATEGORIAS_DEFECTO, SUBCATEGORIAS_DEFECTO
    session = _obtener_sesion(request)
    if session:
        try:
            _, _, df = _cargar_df(session)
            cats = df["categoria"].dropna().unique().tolist() or cats
            subcats = df["subcategoria"].dropna().unique().tolist() or subcats
        except Exception:
            pass
    return html, field_update(choices=cats), field_update(choices=subcats)


# Guarda la clave Gemini en la sesión/configuración compatible sin imprimirla.
def guardar_api_key(api_key_input, request: FastAPIRequest):
    sesion = _obtener_sesion(request)
    if not sesion:
        return (
            "❌ Primero conéctate con Google Drive.",
            _estado_login_html(request),
            field_update(value=""),
        )
    clave = str(api_key_input or "").strip()
    if not clave:
        return (
            "❌ Ingresa una clave válida.",
            _estado_login_html(request),
            field_update(value=""),
        )
    _guardar_sesion(request.cookies.get("session_id"), gemini_key=clave)
    return (
        "✅ Clave guardada solo en esta sesión. El consumo se cobrará al proyecto de Google del cliente.",
        _estado_login_html(request),
        field_update(value=""),
    )


def refrescar_categorias(request: FastAPIRequest):
    return field_update(choices=obtener_categorias(request)), field_update(choices=obtener_subcategorias(request))


def guardar_carpeta_personalizada(texto_carpeta, request: FastAPIRequest):
    sesion = _obtener_sesion(request)
    if not sesion:
        return "❌ Primero conéctate con Google Drive.", _estado_login_html(request)

    folder_id = _extraer_folder_id(texto_carpeta)
    session_id = request.cookies.get("session_id")

    if not folder_id:
        _guardar_sesion(
            session_id,
            carpeta_raiz_id_manual=None,
            carpeta_raiz_nombre_manual=None,
        )
        return (
            "↩️ Se usará la carpeta automática 'Proyecto_IA' en la raíz de tu Drive.",
            _estado_login_html(request),
        )

    anterior_id = sesion.get("carpeta_raiz_id_manual")
    anterior_nombre = sesion.get("carpeta_raiz_nombre_manual")
    try:
        service = _get_drive_service(sesion)
        info = service.files().get(fileId=folder_id, fields="id,name,mimeType").execute()
        if info.get("mimeType") != "application/vnd.google-apps.folder":
            return (
                f"❌ Ese enlace/ID no es una carpeta (tipo: {info.get('mimeType')}).",
                _estado_login_html(request),
            )

        mime_sheet = "application/vnd.google-apps.spreadsheet"
        hoja_nativa = _buscar_archivo(
            service, NOMBRE_GOOGLE_SHEET, folder_id, mime_type=mime_sheet
        )
        archivo_importable = _buscar_inventario_importable(service, folder_id)
        if not hoja_nativa and not archivo_importable:
            return (
                "❌ La carpeta no contiene una hoja nativa 'inventario_completo' ni "
                "inventario_completo.xlsx/.xls/.ods/.csv. No se cambió tu configuración.",
                _estado_login_html(request),
            )

        _guardar_sesion(
            session_id,
            carpeta_raiz_id_manual=folder_id,
            carpeta_raiz_nombre_manual=info.get("name") or "Carpeta del cliente",
        )
        _, carpeta_imagenes_id, spreadsheet_id, _ = _preparar_estructura(service, sesion)
        filas = _validar_inventario_preparado(
            _get_sheets_service(sesion), spreadsheet_id
        )
        return (
            f"✅ Carpeta validada: '{info.get('name')}'. Inventario: {filas} productos. "
            f"Imágenes: carpeta lista ({carpeta_imagenes_id}).",
            _estado_login_html(request),
        )
    except Exception as e:
        _guardar_sesion(
            session_id,
            carpeta_raiz_id_manual=anterior_id,
            carpeta_raiz_nombre_manual=anterior_nombre,
        )
        return (
            "❌ No pude validar esa carpeta y conservé la configuración anterior. "
            f"Detalle: {e}",
            _estado_login_html(request),
        )


def limpiar_feedback():
    """Después de mandar el feedback, limpia los checkboxes y el texto libre
    (el historial se conserva en el State)."""
    return field_update(value=[]), field_update(value="")


# ==========================================
# 6. INTERFAZ GRÁFICA
# ==========================================
captura = ProductCapture(globals())
