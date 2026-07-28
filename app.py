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

MODELO_TEXTO = "gemini-2.5-flash"
MODELO_IMAGEN = "gemini-2.5-flash-image"


def _env_requerida(nombre):
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(f"Falta configurar la variable de entorno '{nombre}'. Configurala como Secret en tu hosting.")
    return valor


GOOGLE_CLIENT_ID = _env_requerida("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _env_requerida("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = _env_requerida("GOOGLE_REDIRECT_URI")

DRIVE_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/drive"]

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

COLUMNAS_CSV = ['sku', 'tipo', 'sku_padre', 'nombre_producto', 'marca', 'gramaje', 'precio', 'categoria', 'subcategoria', 'descripcion_corta', 'descripcion_larga', 'imagenes']

CATEGORIAS_DEFECTO = ["Alimentos", "Bebidas", "K-Pop", "Cosmeticos"]
SUBCATEGORIAS_DEFECTO = ["Snacks", "Ramen", "Refrescos", "Cuidado Facial"]

ERRORES_IA = {
    "Invento un empaque que no es el del producto": "CRITICAL FIX: In the previous attempt you INVENTED or ALTERED the packaging. You MUST copy the packaging from the reference image faithfully: same shape, same proportions, same artwork, same layout. Do not redesign anything.",
    "Agrego un logo o marca que no existe": "CRITICAL FIX: In the previous attempt you ADDED a logo, badge, seal or brand mark that does not exist on the real product. Remove ALL invented logos, watermarks and emblems. Only the marks physically present in the reference image may appear.",
    "Invento texto en el empaque": "CRITICAL FIX: In the previous attempt you INVENTED text, letters or characters on the packaging. Reproduce ONLY the exact text visible in the reference image. If a text area is unreadable, keep it visually blurred instead of inventing words.",
    "Dimensiono mal el producto (escala/proporciones)": "CRITICAL FIX: In the previous attempt the product SCALE and PROPORTIONS were wrong. Respect the real-world size of the product relative to the scene and keep the exact aspect ratio of the package. Do not stretch, squash, or make it oversized or tiny.",
    "Cambio los colores del producto": "CRITICAL FIX: In the previous attempt the product COLORS were altered. Match the exact hues, saturation and finish of the reference packaging.",
    "Deformo o duplico el producto": "CRITICAL FIX: In the previous attempt the product was DEFORMED, warped or DUPLICATED. Render exactly ONE clean, undistorted, correctly built product.",
    "El fondo no quedo blanco puro": "CRITICAL FIX: In the previous attempt the background was not pure white. Use a perfectly clean pure white FFFFFF seamless background with no gradients, props or shadows on the backdrop.",
    "La imagen no quedo cuadrada 1:1": "CRITICAL FIX: In the previous attempt the output was NOT square. Generate the image natively in a STRICT 1:1 SQUARE aspect ratio, with the product fully inside the frame.",
    "La escena no corresponde al producto": "CRITICAL FIX: In the previous attempt the scene and context did not match the product category. Build a scene that is coherent and believable for this specific product.",
    "Se ve borrosa o de baja calidad": "CRITICAL FIX: In the previous attempt the result was blurry or low quality. Deliver razor-sharp focus on the packaging, high micro-detail, clean professional studio-grade lighting.",
    "Recorto o tapo parte del producto": "CRITICAL FIX: In the previous attempt the product was cropped or occluded. The complete product must be fully visible, centered, and unobstructed.",
}

ETIQUETAS_ERRORES = list(ERRORES_IA.keys())


def _construir_correccion(errores_seleccionados, texto_libre, historial):
    historial = list(historial or [])
    nuevas = []
    for etiqueta in (errores_seleccionados or []):
        instruccion = ERRORES_IA.get(etiqueta)
        if instruccion:
            nuevas.append(instruccion)
    if texto_libre and texto_libre.strip():
        nuevas.append("CRITICAL FIX (reported by the human reviewer, obey literally): " + texto_libre.strip())
    for instruccion in nuevas:
        if instruccion not in historial:
            historial.append(instruccion)
    if not historial:
        return "", historial, "Primer intento (sin correcciones previas)."
    total = len(historial)
    partes = []
    partes.append("")
    partes.append("===== REGENERATION FEEDBACK =====")
    partes.append("This is a RE-GENERATION. The previous output was REJECTED by a human reviewer. There are " + str(total) + " accumulated correction(s). You MUST fix every single one of them while keeping everything that was already correct:")
    for i, instruccion in enumerate(historial, start=1):
        partes.append(str(i) + ". " + instruccion)
    partes.append("===== END FEEDBACK =====")
    bloque = "
".join(partes)
    marcados = list(errores_seleccionados or [])
    if texto_libre and texto_libre.strip():
        marcados.append(texto_libre.strip())
    if marcados:
        resumen = "Correcciones enviadas a la IA:
" + "
".join("  " + str(i) + ". " + t for i, t in enumerate(marcados, start=1))
    else:
        resumen = "Reintento arrastrando " + str(total) + " correccion(es) anterior(es)."
    return bloque, historial, resumen


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
    sesion = _obtener_sesion(request)
    if not sesion:
        return None, "Primero conectate con Google Drive (pestana Configuracion)."
    if requiere_api_key and not sesion.get("gemini_key"):
        return None, "Primero guarda tu API Key de Gemini (pestana Configuracion)."
    return sesion, None


fastapi_app = FastAPI()


@fastapi_app.get("/login")
def login():
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=DRIVE_SCOPES, redirect_uri=GOOGLE_REDIRECT_URI)
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    resp = RedirectResponse(auth_url)
    resp.set_cookie("oauth_state", state, httponly=True, secure=True, samesite="lax", path="/", max_age=600)
    return resp


@fastapi_app.get("/auth/callback")
def auth_callback(request: FastAPIRequest):
    try:
        params = dict(request.query_params)
        if "error" in params or "code" not in params:
            return PlainTextResponse("Google devolvio una respuesta inesperada: " + str(params), status_code=400)
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=None, redirect_uri=GOOGLE_REDIRECT_URI)
        flow.fetch_token(code=params["code"])
        creds = flow.credentials
        try:
            info_usuario = build("oauth2", "v2", credentials=creds).userinfo().get().execute()
            email = info_usuario.get("email", "Usuario de Drive")
        except Exception:
            email = "Usuario de Drive"
        session_id = _nueva_session_id()
        _guardar_sesion(session_id, creds=json.loads(creds.to_json()), email=email, gemini_key=None)
        resp = RedirectResponse(url="/")
        resp.set_cookie("session_id", session_id, httponly=True, secure=True, samesite="lax", path="/", max_age=60 * 60 * 24 * 30)
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


def _get_drive_service(sesion):
    creds = Credentials.from_authorized_user_info(sesion["creds"], DRIVE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        sesion["creds"] = json.loads(creds.to_json())
    return build("drive", "v3", credentials=creds)


def _buscar_o_crear_carpeta(service, nombre, parent_id=None):
    query = "name = '" + nombre + "' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query = query + " and '" + parent_id + "' in parents"
    else:
        query = query + " and 'root' in parents"
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
    query = "name = '" + nombre + "' and '" + parent_id + "' in parents and trashed = false"
    res = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    archivos = res.get('files', [])
    return archivos[0]['id'] if archivos else None


def _preparar_estructura(service):
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


def limpiar_texto_sku(texto):
    if not texto:
        return "XXX"
    texto = re.sub(r'[^a-zA-Z0-9]', '', str(texto))
    return texto.upper()


def generar_sku_logica(nombre, marca, gramaje):
    str_marca = limpiar_texto_sku(marca)[:3].ljust(3, 'X')
    str_nom = limpiar_texto_sku(nombre)[:3].ljust(3, 'X')
    str_gramaje = limpiar_texto_sku(gramaje)
    if not str_gramaje:
        str_gramaje = "00"
    sku = str_marca + str_nom + str_gramaje
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
        ancho_centro = int(img_base.width * 0.5)
        prop_centro = ancho_centro / float(logo_original.width)
        alto_centro = int(float(logo_original.height) * float(prop_centro))
        logo_centro = logo_original.resize((ancho_centro, alto_centro), Image.Resampling.LANCZOS)
        alpha_centro = logo_centro.split()[3]
        alpha_centro = alpha_centro.point(lambda p: p * 0.15)
        logo_centro.putalpha(alpha_centro)
        pos_x_centro = (img_base.width - logo_centro.width) // 2
        pos_y_centro = (img_base.height - logo_centro.height) // 2
        img_base.paste(logo_centro, (pos_x_centro, pos_y_centro), logo_centro)
        ancho_esquina = int(img_base.width * 0.20)
        prop_esquina = ancho_esquina / float(logo_original.width)
        alto_esquina = int(float(logo_original.height) * float(prop_esquina))
        logo_esquina = logo_original.resize((ancho_esquina, alto_esquina), Image.Resampling.LANCZOS)
        margen = 20
        pos_x_esquina = img_base.width - logo_esquina.width - margen
        pos_y_esquina = img_base.height - logo_esquina.height - margen
        img_base.paste(logo_esquina, (pos_x_esquina, pos_y_esquina), logo_esquina)
        img_final = img_base.convert("RGB")
        img_final.save(ruta_imagen, quality=95)
    except Exception as e:
        print("Error con el logo: " + str(e))


def _extraer_json(texto_raw):
    texto_limpio = (texto_raw or "").replace("```json", "").replace("```", "").strip()
    match = re.search(r'\{.*\}', texto_limpio, re.DOTALL)
    if match:
        texto_limpio = match.group(0)
    return json.loads(texto_limpio)


def _extraer_imagen_bytes(response):
    for candidato in (getattr(response, "candidates", None) or []):
        contenido = getattr(candidato, "content", None)
        for part in (getattr(contenido, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return inline.data
    return None


def estimar_precio_producto(nombre, marca, gramaje, categoria, api_key):
    if not nombre:
        return {"precio_min": 0, "precio_max": 0, "precio_sugerido": 0, "moneda": "MXN"}
    prompt = "Actua como un analista de pricing para e-commerce en Mexico. Busca en internet (tiendas online, Amazon, Mercado Libre, tiendas asiaticas, supermercados) el precio de venta al publico del producto '" + str(nombre) + "' de la marca '" + str(marca) + "', presentacion '" + str(gramaje) + "', categoria '" + str(categoria) + "'. Devuelve UNICAMENTE un JSON estricto, sin texto adicional ni markdown, con las claves: 'precio_min' (numero en MXN), 'precio_max' (numero en MXN), 'precio_sugerido' (numero en MXN, con margen razonable de reventa), 'moneda' ('MXN')."
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=MODELO_TEXTO, contents=prompt, config=types.GenerateContentConfig(tools=[{"google_search": {}}]))
        return _extraer_json(response.text)
    except Exception as e:
        print("No se pudo estimar el precio automaticamente: " + str(e))
        return {"precio_min": 0, "precio_max": 0, "precio_sugerido": 0, "moneda": "MXN"}


def buscar_variantes_por_imagen(imagen, nombre_actual, marca_actual, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return error, "", "Simple"
    if imagen is None:
        return "Sube o importa una foto del producto para poder buscar.", "", "Simple"
    api_key = sesion["gemini_key"]
    try:
        img_pil = comprimir_imagen(imagen).convert("RGB")
        ruta_temp = "/tmp/temp_lens.jpg"
        img_pil.save(ruta_temp, format="JPEG", quality=85)
        client = genai.Client(api_key=api_key)
        archivo_ref = client.files.upload(file=ruta_temp)
        contexto = ""
        if nombre_actual:
            contexto = "Nombre de referencia (ya analizado previamente): '" + str(nombre_actual) + "'. Marca de referencia: '" + str(marca_actual) + "'. "
        prompt = "Actua como Google Lens combinado con Google Shopping. Observa cuidadosamente la imagen del producto adjunta e identifica exactamente de que producto y marca se trata. " + contexto + "Despues, busca en internet si ese MISMO producto existe en OTRAS presentaciones, tamanos o gramajes distintos al de la foto (ej: el mismo snack en 30g, 100g y 500g). NO busques marcas ni productos distintos, solo variantes de tamano o gramaje del mismo producto. Devuelve UNICAMENTE un JSON estricto, sin texto adicional ni markdown, con las claves: 'producto_identificado' (string), 'marca_identificada' (string), 'tiene_variantes' (booleano), 'variantes' (lista de objetos con 'gramaje', 'fuente', 'precio_aprox'), 'justificacion' (string breve)."
        response = client.models.generate_content(model=MODELO_TEXTO, contents=[archivo_ref, prompt], config=types.GenerateContentConfig(tools=[{"google_search": {}}]))
        datos = _extraer_json(response.text)
        producto = datos.get("producto_identificado", "Producto no identificado")
        marca = datos.get("marca_identificada", "")
        tiene_variantes = bool(datos.get("tiene_variantes", False))
        variantes = datos.get("variantes", []) or []
        justificacion = datos.get("justificacion", "")
        tipo_recomendado = "Variable" if (tiene_variantes and len(variantes) > 0) else "Simple"
        if tipo_recomendado == "Variable":
            recomendacion = "Se encontraron " + str(len(variantes)) + " presentacion(es) adicional(es). Recomendado: marcar como VARIABLE."
        else:
            recomendacion = "No se encontraron otras presentaciones del mismo producto. Recomendado: dejar como SIMPLE."
        reporte = "### Producto identificado: " + str(producto) + " (" + str(marca) + ")

"
        if variantes:
            reporte = reporte + "| Gramaje/Tamano | Fuente | Precio aprox. |
|---|---|---|
"
            for v in variantes:
                reporte = reporte + "| " + str(v.get('gramaje', '-')) + " | " + str(v.get('fuente', '-')) + " | " + str(v.get('precio_aprox', '-')) + " |
"
        else:
            reporte = reporte + "_No se encontraron otras presentaciones a la venta actualmente._
"
        reporte = reporte + "
**Justificacion de la IA:** " + str(justificacion)
        return recomendacion, reporte, tipo_recomendado
    except Exception as e:
        return "Error en la busqueda visual: " + str(e), "", "Simple"


def investigar_prompts(producto, marca, desc, api_key):
    prompt = "Actua como un director de arte publicitario. Producto: '" + str(producto) + "', Marca: '" + str(marca) + "', Contexto: '" + str(desc) + "'. Devuelve un JSON estricto con dos claves: 'lifestyle' y 'comercial'. REGLA 1: Si es comida o bebida, describe escenas con ingredientes volando y consumo feliz. REGLA 2: Si NO es comida, describe un estudio estilizado, neon, pop-art. CRITICO: All prompt instructions MUST be exclusively in English. The physical product packaging MUST be clearly visible and centered. DO NOT invent packaging. DO NOT ask for text or logos. MENTION THAT THE IMAGE MUST BE 1:1 SQUARE."
    try:
        client = genai.Client(api_key=api_key)
        res = client.models.generate_content(model=MODELO_TEXTO, contents=prompt)
        return _extraer_json(res.text)
    except Exception:
        fallback_life = "Warm lifestyle photography of the exact packaging of " + str(producto) + ", highly detailed scene, authentic interaction, natural lighting, 1:1 square aspect ratio."
        fallback_com = "Dynamic epic commercial photography highlighting the exact packaging of " + str(producto) + " by " + str(marca) + ", highly stylized studio lighting, 1:1 square aspect ratio."
        return {"lifestyle": fallback_life, "comercial": fallback_com}


def generar_foto_individual(prompt, ruta_base, ruta_salida_local, api_key, service, logo_id, correccion=""):
    try:
        client = genai.Client(api_key=api_key)
        archivo_ref = client.files.upload(file=ruta_base)
        reglas = " CRITICAL INSTRUCTIONS: 1. YOU MUST USE THE EXACT PRODUCT PACKAGING FROM THE REFERENCE IMAGE. DO NOT invent, alter, or hallucinate boxes, text, or shapes. The physical product is untouchable. 2. ABSOLUTELY NO LOGOS, NO WATERMARKS, NO EXTRA TEXT anywhere. 3. Respect the real proportions and scale of the product. 4. Generate the final output natively in a STRICTLY SQUARE 1:1 ASPECT RATIO."
        prompt_seguro = str(prompt) + reglas + str(correccion)
        response = client.models.generate_content(model=MODELO_IMAGEN, contents=[archivo_ref, prompt_seguro])
        datos_imagen = _extraer_imagen_bytes(response)
        if not datos_imagen:
            print("El modelo no devolvio imagen.")
            return None
        with open(ruta_salida_local, "wb") as f:
            f.write(datos_imagen)
        if logo_id:
            estampar_logo(ruta_salida_local, service, logo_id)
        return ruta_salida_local
    except Exception as e:
        print("Error al generar imagen: " + str(e))
        return None


def modulo_extraer_textos(imagen_1, imagen_2, descripcion_breve, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return [error, "", "", "", "", 0, "Simple", gr.update(visible=False), "", "", "", "", None]
    if imagen_1 is None:
        return ["Sube al menos la foto principal.", "", "", "", "", 0, "Simple", gr.update(visible=False), "", "", "", "", None]
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
    prompt_datos = "Analiza el producto de las imagenes. Contexto extra: '" + str(descripcion_breve) + "'. Actua como un experto en SEO para e-commerce. Devuelve un JSON estricto con: 1. 'nombre': El nombre del producto claro y comercial. 2. 'marca': La marca del producto. 3. 'gramaje': La unidad de medida y cantidad EXACTA. Puede ser G, KG, ML, L, OZ o PZ. Ejemplo: '500G', '12OZ', '1L', '10PZ'. 4. 'categoria': Clasificalo ESTRICTAMENTE usando SOLO una de las siguientes Categorias: " + str(lista_cats) + ". NO inventes ninguna. 5. 'subcategoria': Clasificalo ESTRICTAMENTE usando SOLO una de las siguientes Subcategorias: " + str(lista_subcats) + ". NO inventes ninguna. 6. 'desc_corta': Optimizado para SEO, maximo 150 caracteres. 7. 'desc_larga': Optimizado para SEO con beneficios e ingredientes en formato de vinetas con guiones."
    try:
        res_datos = client.models.generate_content(model=MODELO_TEXTO, contents=archivos_ia + [prompt_datos])
        datos = _extraer_json(res_datos.text)
    except Exception as e:
        return ["Error leyendo imagen: " + str(e), "", "", "", "", 0, "Simple", gr.update(visible=False), "", "", "", "", None]
    nombre = datos.get("nombre", "Producto Desconocido")
    marca = datos.get("marca", "Generica")
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
    return ["Textos y precio sugerido extraidos. Verifica SKU, Categorias y Precio.", sku_gen, nombre, marca, gramaje, precio_sugerido, "Simple", gr.update(visible=False), cat_final, subcat_final, datos.get("desc_corta", ""), datos.get("desc_larga", ""), ruta_base_memoria]


PROMPT_HD = "Create a clean e-commerce studio shot of this exact product packaging. Isolated on a pure white background. Crisp details, bright and even studio lighting. MUST BE 1:1 SQUARE ASPECT RATIO."


def _rehacer_generico(slot, prompt, ruta_base, sku, errores, feedback, historial, sesion):
    correccion, historial_nuevo, resumen = _construir_correccion(errores, feedback, historial)
    service = _get_drive_service(sesion)
    _, carpeta_imagenes_id, _, logo_id = _preparar_estructura(service)
    nombre_archivo = str(sku) + "_" + slot + ".jpg"
    ruta_local = "/tmp/" + nombre_archivo
    resultado = generar_foto_individual(prompt, ruta_base, ruta_local, sesion["gemini_key"], service, logo_id, correccion=correccion)
    if not resultado:
        return None, historial_nuevo, "La IA no devolvio imagen. Intenta de nuevo o ajusta el feedback."
    _subir_imagen_drive(service, carpeta_imagenes_id, nombre_archivo, resultado)
    mensaje = nombre_archivo + " regenerada y guardada en Drive.
" + resumen
    return resultado, historial_nuevo, mensaje


def rehacer_hd(ruta_base, sku, errores, feedback, historial, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return None, historial, error
    if not ruta_base:
        return None, historial, "Extrae los textos primero (necesito la foto base)."
    return _rehacer_generico("1_hd", PROMPT_HD, ruta_base, sku, errores, feedback, historial, sesion)


def rehacer_life(ruta_base, sku, nombre, marca, desc, errores, feedback, historial, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return None, historial, error
    if not ruta_base:
        return None, historial, "Extrae los textos primero (necesito la foto base)."
    prompts = investigar_prompts(nombre, marca, desc, sesion["gemini_key"])
    return _rehacer_generico("2_uso", prompts['lifestyle'], ruta_base, sku, errores, feedback, historial, sesion)


def rehacer_comercial(ruta_base, sku, nombre, marca, desc, errores, feedback, historial, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        return None, historial, error
    if not ruta_base:
        return None, historial, "Extrae los textos primero (necesito la foto base)."
    prompts = investigar_prompts(nombre, marca, desc, sesion["gemini_key"])
    return _rehacer_generico("3_comercial", prompts['comercial'], ruta_base, sku, errores, feedback, historial, sesion)


def modulo_generar_todo(ruta_base, sku, nombre, marca, desc, request: gr.Request):
    sesion, error = _validar_sesion(request)
    if error:
        yield error, None, None, None, [], [], []
        return
    if not ruta_base:
        yield "Extrae los textos primero", None, None, None, [], [], []
        return
    yield "Generando fondo blanco...", None, None, None, [], [], []
    out_1, _, _ = rehacer_hd(ruta_base, sku, [], "", [], request)
    yield "Generando estilo de vida...", out_1, None, None, [], [], []
    out_2, _, _ = rehacer_life(ruta_base, sku, nombre, marca, desc, [], "", [], request)
    yield "Generando comercial epica...", out_1, out_2, None, [], [], []
    out_3, _, _ = rehacer_comercial(ruta_base, sku, nombre, marca, desc, [], "", [], request)
    yield "Set fotografico completo, guardado en tu Google Drive. Si algo salio mal, usa el panel de correcciones de cada imagen.", out_1, out_2, out_3, [], [], []


def guardar_excel_final(sku, tipo, sku_padre, nombre, marca, gramaje, precio, cat, subcat, desc_corta, desc_larga, request: gr.Request):
    sesion, error = _validar_sesion(request, requiere_api_key=False)
    if error:
        return error
    if not sku:
        return "Error: No hay datos para guardar."
    try:
        service, csv_id, df = _cargar_df(sesion)
        carpeta_raiz_id, _, _, _ = _preparar_estructura(service)
        lista_imagenes_str = str(sku) + "_1_hd.jpg, " + str(sku) + "_2_uso.jpg, " + str(sku) + "_3_comercial.jpg"
        nueva_fila = {
            'sku': sku,
            'tipo': tipo,
            'sku_padre': sku_padre if tipo == "Variable" else "",
            'nombre_producto': nombre,
            'marca': marca,
            'gramaje': gramaje,
            'precio': precio,
            'categoria': cat,
            'subcategoria': subcat,
            'descripcion_corta': desc_corta,
            'descripcion_larga': desc_larga,
            'imagenes': lista_imagenes_str,
        }
        df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
        _guardar_csv_drive(service, carpeta_raiz_id, csv_id, df)
        return "Guardado en tu Google Drive. El producto " + str(sku) + " esta en tu inventario maestro."
    except Exception as e:
        return "Error al guardar en Drive: " + str(e)


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


def _estado_login_html(request: gr.Request):
    sesion = _obtener_sesion(request)
    if sesion:
        email = sesion.get("email", "tu cuenta")
        tiene_key = "guardada" if sesion.get("gemini_key") else "falta guardarla abajo"
        return "<div style='padding:12px;border-radius:8px;background:#eafaf1;'>Conectado a Google Drive como <b>" + str(email) + "</b> | API Key de Gemini: " + tiene_key + " &middot; <a href='/logout'>Cerrar sesion</a></div>"
    return "<div style='padding:12px;border-radius:8px;background:#fdecea;'>No estas conectado. <a href='/login'><b>Conectar con Google Drive</b></a></div>"


def cargar_estado_inicial(request: gr.Request):
    html = _estado_login_html(request)
    cats = obtener_categorias(request)
    subcats = obtener_subcategorias(request)
    return html, gr.update(choices=cats), gr.update(choices=subcats)


def guardar_api_key(api_key_input, request: gr.Request):
    sesion = _obtener_sesion(request)
    if not sesion:
        return "Primero conectate con Google Drive.", _estado_login_html(request)
    if not api_key_input or not api_key_input.strip():
        return "Ingresa una API key valida.", _estado_login_html(request)
    _guardar_sesion(request.cookies.get("session_id"), gemini_key=api_key_input.strip())
    return "API Key guardada para tu sesion.", _estado_login_html(request)


def refrescar_categorias(request: gr.Request):
    return gr.update(choices=obtener_categorias(request)), gr.update(choices=obtener_subcategorias(request))


def limpiar_feedback():
    return gr.update(value=[]), gr.update(value="")


css_camara = "video { transform: none !important; }"

with gr.Blocks(theme=gr.themes.Soft(), css=css_camara) as demo:
    memoria_ruta_base = gr.State(None)
    hist_1 = gr.State([])
    hist_2 = gr.State([])
    hist_3 = gr.State([])

    gr.Markdown("# Suite Ecommerce (SEO, Precios, IA y Variantes)")
    estado_login = gr.HTML()

    with gr.Tabs():
        with gr.Tab("Configuracion"):
            gr.Markdown("### 1. Conecta tu Google Drive")
            gr.Markdown("Inicia sesion con Google. Todo lo que generes se guardara en la carpeta Proyecto_IA de tu propio Drive.")
            gr.Markdown("### 2. Guarda tu API Key de Gemini")
            gr.Markdown("Se usa solo durante tu sesion; no se comparte con otros usuarios ni se guarda en el codigo.")
            gr.HTML("<a href='/login'><b>Conectar / Reconectar con Google Drive</b></a>")
            in_api_key = gr.Textbox(label="Tu API Key de Gemini (Google AI Studio)", type="password")
            btn_guardar_key = gr.Button("Guardar API Key", variant="primary")
            estado_config = gr.Textbox(label="Estado", interactive=False)
            btn_refrescar_cats = gr.Button("Actualizar categorias desde mi Drive", size="sm")

        with gr.Tab("1. Ingreso y Edicion de Productos"):
            estado = gr.Textbox(label="Consola de Sistema", interactive=False, lines=4)

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 1. Imagenes y Analisis")
                    img1 = gr.Image(label="Foto Frontal", type="numpy", sources=["upload", "webcam", "clipboard"])
                    img2 = gr.Image(label="Foto Reverso (Opcional)", type="numpy", sources=["upload", "webcam", "clipboard"])
                    desc_input = gr.Textbox(label="Apuntes Extra", placeholder="Ej. Galletas coreanas edicion limitada")
                    btn_extraer = gr.Button("Analizar Producto (SEO + Info + Precio)", variant="primary")

                with gr.Column(scale=1):
                    gr.Markdown("### 2. Clasificacion, Textos y Precio")
                    with gr.Group():
                        in_nombre = gr.Textbox(label="Nombre Comercial")
                        in_marca = gr.Textbox(label="Marca")
                        in_gramaje = gr.Textbox(label="Medida (Ej. 120G, 1L, 10PZ, 5OZ)")
                    with gr.Row():
                        in_precio = gr.Number(label="Precio Sugerido (MXN)", precision=2)
                        btn_act_precio = gr.Button("Recalcular Precio", size="sm")
                    with gr.Row():
                        in_sku = gr.Textbox(label="SKU (Max 10 caracteres)", interactive=True)
                        btn_act_sku = gr.Button("Recalcular SKU", size="sm")
                    with gr.Group():
                        in_tipo = gr.Radio(["Simple", "Variable"], label="Tipo de Producto", value="Simple")
                        in_sku_padre = gr.Textbox(label="SKU Padre Detectado", visible=False, interactive=True)
                    with gr.Group():
                        in_cat = gr.Dropdown(choices=CATEGORIAS_DEFECTO, label="Categoria (Estricta)")
                        in_subcat = gr.Dropdown(choices=SUBCATEGORIAS_DEFECTO, label="Subcategoria (Estricta)")
                    in_desc_corta = gr.Textbox(label="Desc. Corta (SEO - max 150 caracteres)", lines=2)
                    in_desc_larga = gr.Textbox(label="Desc. Larga (SEO - Vinetas y Beneficios)", lines=5)

                with gr.Column(scale=2):
                    gr.Markdown("### 3. Estudio Fotografico IA (Formato Cuadrado)")
                    btn_generar_fotos = gr.Button("Generar Set de 3 Fotos Comerciales", variant="primary")
                    gr.Markdown("_Si salio mal una foto, abre su panel de correcciones, marca el error (empaque inventado, logo que no existe, mala escala...) y dale Rehacer. La IA recibe esa retroalimentacion y las correcciones se acumulan en cada intento._")

                    with gr.Row():
                        with gr.Column():
                            out_img1 = gr.Image(label="Fondo Blanco")
                            with gr.Accordion("Que salio mal? (Fondo Blanco)", open=False):
                                err_1 = gr.CheckboxGroup(choices=ETIQUETAS_ERRORES, label="Errores detectados")
                                fb_1 = gr.Textbox(label="Otra correccion (texto libre)", placeholder="Ej. la tapa es roja, no azul", lines=2)
                                btn_limpiar_hist_1 = gr.Button("Olvidar correcciones previas", size="sm")
                            btn_rehacer_1 = gr.Button("Rehacer HD con feedback")

                        with gr.Column():
                            out_img2 = gr.Image(label="Lifestyle")
                            with gr.Accordion("Que salio mal? (Lifestyle)", open=False):
                                err_2 = gr.CheckboxGroup(choices=ETIQUETAS_ERRORES, label="Errores detectados")
                                fb_2 = gr.Textbox(label="Otra correccion (texto libre)", placeholder="Ej. la mano tapa el nombre del producto", lines=2)
                                btn_limpiar_hist_2 = gr.Button("Olvidar correcciones previas", size="sm")
                            btn_rehacer_2 = gr.Button("Rehacer Life con feedback")

                        with gr.Column():
                            out_img3 = gr.Image(label="Comercial")
                            with gr.Accordion("Que salio mal? (Comercial)", open=False):
                                err_3 = gr.CheckboxGroup(choices=ETIQUETAS_ERRORES, label="Errores detectados")
                                fb_3 = gr.Textbox(label="Otra correccion (texto libre)", placeholder="Ej. invento un sello de premium quality", lines=2)
                                btn_limpiar_hist_3 = gr.Button("Olvidar correcciones previas", size="sm")
                            btn_rehacer_3 = gr.Button("Rehacer Com con feedback")

            gr.Markdown("---")
            btn_guardar = gr.Button("APROBAR Y GUARDAR EN MI INVENTARIO (Google Drive)", variant="primary", size="lg")

        with gr.Tab("2. Variantes de Presentacion (Google Lens IA)"):
            gr.Markdown("### Busca con IA si el producto existe en otros gramajes o tamanos")
            gr.Markdown("Sube o reutiliza la foto del producto para que la IA lo identifique visualmente (como Google Lens) y busque en internet si existen otras presentaciones del MISMO producto. Asi sabras si conviene marcarlo como Variable en la Pestana 1 en vez de Simple.")
            with gr.Row():
                with gr.Column(scale=1):
                    img_lens = gr.Image(label="Foto del producto a investigar", type="numpy", sources=["upload", "webcam", "clipboard"])
                    btn_usar_foto_tab1 = gr.Button("Usar foto de la Pestana 1", size="sm")
                    btn_buscar_lens = gr.Button("Buscar Variantes con Google Lens (IA)", variant="primary")
                with gr.Column(scale=2):
                    recomendacion_tipo_box = gr.Textbox(label="Recomendacion", interactive=False)
                    reporte_variantes = gr.Markdown()
                    state_tipo_recomendado = gr.State("Simple")
                    btn_aplicar_recomendacion = gr.Button("Aplicar recomendacion de Tipo en la Pestana 1")

    demo.load(cargar_estado_inicial, inputs=None, outputs=[estado_login, in_cat, in_subcat])

    btn_guardar_key.click(guardar_api_key, inputs=[in_api_key], outputs=[estado_config, estado_login])
    btn_refrescar_cats.click(refrescar_categorias, inputs=None, outputs=[in_cat, in_subcat])

    entradas_textos = [img1, img2, desc_input]
    salidas_textos = [estado, in_sku, in_nombre, in_marca, in_gramaje, in_precio, in_tipo, in_sku_padre, in_cat, in_subcat, in_desc_corta, in_desc_larga, memoria_ruta_base]
    btn_extraer.click(modulo_extraer_textos, inputs=entradas_textos, outputs=salidas_textos)

    btn_act_sku.click(recalcular_sku_ui, inputs=[in_nombre, in_marca, in_gramaje], outputs=[in_sku])
    btn_act_precio.click(recalcular_precio_ui, inputs=[in_nombre, in_marca, in_gramaje, in_cat], outputs=[in_precio])
    in_tipo.change(cambio_tipo_ui, inputs=[in_tipo, in_nombre], outputs=[in_sku_padre])

    btn_generar_fotos.click(modulo_generar_todo, inputs=[memoria_ruta_base, in_sku, in_nombre, in_marca, in_desc_corta], outputs=[estado, out_img1, out_img2, out_img3, hist_1, hist_2, hist_3])

    btn_rehacer_1.click(rehacer_hd, inputs=[memoria_ruta_base, in_sku, err_1, fb_1, hist_1], outputs=[out_img1, hist_1, estado]).then(limpiar_feedback, inputs=None, outputs=[err_1, fb_1])
    btn_rehacer_2.click(rehacer_life, inputs=[memoria_ruta_base, in_sku, in_nombre, in_marca, in_desc_corta, err_2, fb_2, hist_2], outputs=[out_img2, hist_2, estado]).then(limpiar_feedback, inputs=None, outputs=[err_2, fb_2])
    btn_rehacer_3.click(rehacer_comercial, inputs=[memoria_ruta_base, in_sku, in_nombre, in_marca, in_desc_corta, err_3, fb_3, hist_3], outputs=[out_img3, hist_3, estado]).then(limpiar_feedback, inputs=None, outputs=[err_3, fb_3])

    btn_limpiar_hist_1.click(lambda: ([], "Historial de correcciones (Fondo Blanco) reiniciado."), inputs=None, outputs=[hist_1, estado])
    btn_limpiar_hist_2.click(lambda: ([], "Historial de correcciones (Lifestyle) reiniciado."), inputs=None, outputs=[hist_2, estado])
    btn_limpiar_hist_3.click(lambda: ([], "Historial de correcciones (Comercial) reiniciado."), inputs=None, outputs=[hist_3, estado])

    btn_guardar.click(guardar_excel_final, inputs=[in_sku, in_tipo, in_sku_padre, in_nombre, in_marca, in_gramaje, in_precio, in_cat, in_subcat, in_desc_corta, in_desc_larga], outputs=[estado])

    btn_usar_foto_tab1.click(lambda x: x, inputs=[img1], outputs=[img_lens])
    btn_buscar_lens.click(buscar_variantes_por_imagen, inputs=[img_lens, in_nombre, in_marca], outputs=[recomendacion_tipo_box, reporte_variantes, state_tipo_recomendado])
    btn_aplicar_recomendacion.click(lambda t: gr.update(value=t), inputs=[state_tipo_recomendado], outputs=[in_tipo])

gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
