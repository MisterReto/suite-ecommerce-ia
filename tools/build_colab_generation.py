"""Build the self-contained Colab backup from an immutable app commit.

Usage: python tools/build_colab_generation.py original.ipynb output.ipynb
The source notebook is never committed: outputs and private account data stay out.
"""
import ast
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "4e04b738a5f228ed3a56c50c4d891625f76c9e48"


def source_at(path):
    return subprocess.check_output(["git", "show", SOURCE_COMMIT + ":" + path], cwd=ROOT)


def extract(source, names):
    wanted = []
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            wanted.append(ast.get_source_segment(source, node))
        elif isinstance(node, ast.Assign) and any(isinstance(n, ast.Name) and n.id in names for n in node.targets):
            wanted.append(ast.get_source_segment(source, node))
    return "\n\n".join(wanted) + "\n"


def build(original_path, destination):
    original = json.loads(Path(original_path).read_text())
    app = source_at("app.py").decode()
    files = {name: source_at(name) for name in ("creative_pipeline.py", "gemini_gateway.py", "product_generation.py")}
    files["app_generation_contract.py"] = ("import os, re, json\nfrom google.genai import types\n\n" + extract(app, {
        "PROMPT_HD", "PUNTUACION_MINIMA_QA", "MODELO_TEXTO", "ERRORES_IA", "_imagen_para_ia", "_extraer_json", "_validar_con_vision"})).encode()
    files["accepted_studio_functions.py.txt"] = extract(source_at("studio_api.py").decode(), {"creative_plan", "make_image"}).encode()
    files["rincon-logo.png"] = source_at("static/rincon-logo.png")
    files["generation_contract.json"] = source_at("tests/fixtures/generation_contract.json")
    files["generation_backup.py"] = (ROOT / "colab/generation_backup.py").read_bytes()
    manifest = {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}
    payload = base64.b64encode(zlib.compress(json.dumps({name: base64.b64encode(raw).decode() for name, raw in files.items()}).encode(), 9)).decode()
    cells = []

    def md(text, id):
        cells.append({"cell_type": "markdown", "metadata": {"id": id}, "source": text.splitlines(True)})

    def code(text, id, form=False):
        text = "\n".join(line[:line.index("#@param")] + line[line.index("#@param"):].replace("'", '"') if "#@param" in line else line for line in text.split("\n"))
        cells.append({"cell_type": "code", "execution_count": None, "outputs": [],
                      "metadata": {"id": id, **({"cellView": "form"} if form else {})}, "source": text.splitlines(True)})

    md("""# Rincón de Asia · Generación respaldada de la app
**Producto limpio · Lifestyle con personas · Comercial artístico**

Esta edición contiene dentro del notebook el motor de la app desplegada en `4e04b73`.
No descarga una rama cambiante: verifica cada módulo con SHA-256 antes de usarlo.
Conserva modelo, prompts, referencias originales, hasta dos ejemplos de estilo,
formato cuadrado ≥1024 px, marca determinista y corrección sobre el raw sin marca.

**Recorrido:** 1. Preparar → 2. Configurar y auditar → 3. Generar candidatos →
4. Revisar/corregir → 5. Aprobar y guardar.

Configura `GEMINI_API_KEY` en Secrets de Colab (icono de llave). No pegues claves en el código.
La auditoría no llama a Gemini. Las casillas de generación, corrección y guardado empiezan desactivadas.
CSV: `sku`, `nombre_producto`, `Web link imagen`; opcionales `Marca`, `categorias`,
`subcategoria`, `descripcion_corta`, `descripcion_larga`, `presentacion` y `referencias_locales`.
Lee el SKU como texto para conservar ceros iniciales. Para varias fotos locales, separa las rutas con `;`.

[App](https://rincon-frontend.onrender.com/) · [Versión del código](https://github.com/MisterReto/suite-ecommerce-ia/tree/4e04b738a5f228ed3a56c50c4d891625f76c9e48)

La celda histórica de compresión de 134 PNG se conserva al final como herramienta opcional.
""", "rda-intro")
    md("## 1 · Preparar el entorno", "rda-setup-title")
    code("""#@title Montar Drive e instalar las versiones de la app
from google.colab import drive
drive.mount('/content/drive')
import subprocess, sys
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'google-genai==2.28.0', 'pandas==2.2.3', 'pillow==12.3.0',
    'requests==2.34.2', 'bleach==6.4.0'])
print('Entorno preparado. Continúa con la restauración del motor.')
""", "jYBQZ8VQHcrl", True)
    code("#@title Restaurar y verificar el motor congelado (sin llamadas de IA)\n"
         "import base64, hashlib, json, os, sys, tempfile, zlib\nfrom pathlib import Path\n"
         f"SOURCE_COMMIT = {SOURCE_COMMIT!r}\nMANIFEST = {manifest!r}\n"
         f"BUNDLE = {payload!r}\n"
         "RUNTIME_DIR = Path(tempfile.gettempdir()) / ('rincon_motor_' + SOURCE_COMMIT[:7])\n"
         "RUNTIME_DIR.mkdir(parents=True, exist_ok=True)\n"
         "for name, encoded in json.loads(zlib.decompress(base64.b64decode(BUNDLE))).items():\n"
         "    raw = base64.b64decode(encoded)\n"
         "    assert hashlib.sha256(raw).hexdigest() == MANIFEST[name], 'Motor alterado: ' + name\n"
         "    assert Path(name).name == name, 'Nombre de módulo inválido'\n"
         "    (RUNTIME_DIR / name).write_bytes(raw)\n"
         "os.environ['GEMINI_IMAGE_MODEL'] = 'gemini-3.1-flash-image'\n"
         "os.environ['GEMINI_TEXT_MODEL'] = 'gemini-2.5-flash'\n"
         "sys.path.insert(0, str(RUNTIME_DIR))\n"
         "for module in ('creative_pipeline', 'gemini_gateway', 'product_generation', 'app_generation_contract', 'generation_backup'):\n"
         "    sys.modules.pop(module, None)\n"
         "from generation_backup import ColabGenerator\n"
         "print('Motor verificado:', SOURCE_COMMIT[:7], '·', len(MANIFEST), 'archivos íntegros.')\n",
         "rda-frozen-engine", True)
    md("## 2 · Configurar y auditar\nLa carpeta predeterminada conserva la ubicación del Colab anterior. Cámbiala si tu carpeta de Drive tiene otro nombre.", "rda-config-title")
    code("""#@title Rutas, tipos de imagen y auditoría gratuita
CARPETA_BASE = '/content/drive/MyDrive/Proyecto_IA' #@param {type:'string'}
CSV_INVENTARIO = '' #@param {type:'string'}
CARPETA_IMAGENES = '' #@param {type:'string'}
LOGO = '' #@param {type:'string'}
TIPOS = '1_hd,2_uso,3_comercial' #@param {type:'string'}
SOLO_SKUS = '' #@param {type:'string'}
MAX_PRODUCTOS = 0 #@param {type:'integer'}
PRODUCTOS_EN_PARALELO = 2 #@param {type:'slider',min:1,max:4,step:1}
REVISION_AUTOMATICA = False #@param {type:'boolean'}

motor = ColabGenerator(CARPETA_BASE, csv_path=CSV_INVENTARIO or None,
    output=CARPETA_IMAGENES or None, logo=LOGO or None)
slots = [s.strip() for s in TIPOS.split(',') if s.strip()]
skus = [s.strip() for s in SOLO_SKUS.split(',') if s.strip()]
auditoria = motor.audit(slots=slots)
display(auditoria)
print('La auditoría no genera imágenes. Candidatos, estado e historial:', motor.work)
print('Las fotos aprobadas se guardarán en:', motor.output)
""", "rda-config", True)
    md("## 3 · Generar candidatos\nCada imagen se solicita una vez. Si una llamada falla o se interrumpe, queda señalada para revisión, sin repetir el gasto automáticamente. Los demás productos continúan. Las imágenes válidas existentes y los candidatos pendientes de revisión se conservan.", "rda-run-title")
    code("""#@title Generar las imágenes faltantes seleccionadas
CONFIRMAR_GENERACION = False #@param {type:'boolean'}
if CONFIRMAR_GENERACION:
    resultado = motor.batch(slots=slots, skus=skus, limit=MAX_PRODUCTOS,
        workers=PRODUCTOS_EN_PARALELO, automatic_review=REVISION_AUTOMATICA, confirm=True)
    display(resultado)
else:
    print('Revisa la auditoría y activa CONFIRMAR_GENERACION cuando quieras iniciar el lote.')
""", "-vY-eouWVDOt", True)
    md("## 4 · Revisar y corregir\nLifestyle exige personas adultas usando o consumiendo el producto. Comercial conserva el empaque y aplica un entorno artístico. La imagen limpia mantiene el producto centrado sobre blanco. Revisa identidad, texto, proporciones y uso antes de aprobar. Detén un lote con el botón de interrupción de Colab; las llamadas ya iniciadas pueden terminar.", "rda-review-title")
    code("""#@title Ver la galería de candidatos
SKU_GALERIA = '' #@param {type:'string'}
motor.gallery(SKU_GALERIA)
""", "rda-gallery", True)
    code("""#@title Corregir, regenerar o autorizar un reintento
SKU_EDITAR = '' #@param {type:'string'}
TIPO_EDITAR = '2_uso' #@param ['1_hd','2_uso','3_comercial']
ACCION = 'Corregir' #@param ['Corregir','Regenerar','Autorizar reintento']
CORRECCION = '' #@param {type:'string'}
CONFIRMAR_EDICION = False #@param {type:'boolean'}
if CONFIRMAR_EDICION:
    if ACCION == 'Corregir':
        display(motor.correct(SKU_EDITAR, TIPO_EDITAR, CORRECCION,
            automatic_review=REVISION_AUTOMATICA, confirm=True))
    elif ACCION == 'Regenerar':
        display(motor.regenerate(SKU_EDITAR, TIPO_EDITAR,
            automatic_review=REVISION_AUTOMATICA, confirm=True))
    else:
        motor.allow_retry(SKU_EDITAR, TIPO_EDITAR, confirm=True)
        print('Reintento autorizado. Ejecuta el lote o la corrección cuando quieras solicitarlo.')
    motor.gallery(SKU_EDITAR)
else:
    print('La corrección usa las fotos originales, el raw anterior y hasta 8 indicaciones acumuladas.')
""", "rda-correct", True)
    md("## 5 · Aprobar y guardar\nSelecciona los SKU y tipos que ya revisaste. Solo los candidatos aprobados se copian a `imagenes_generadas` con nombres `SKU_1_hd.jpg`, `SKU_2_uso.jpg` y `SKU_3_comercial.jpg`, junto con su raw. Un canónico anterior se respalda antes de reemplazarlo. El CSV y las existencias no se modifican.", "rda-save-title")
    code("""#@title Guardar únicamente los candidatos revisados
SKUS_APROBADOS = '' #@param {type:'string'}
TIPOS_APROBADOS = '1_hd,2_uso,3_comercial' #@param {type:'string'}
CONFIRMAR_GUARDADO = False #@param {type:'boolean'}
if CONFIRMAR_GUARDADO:
    aprobados = [s.strip() for s in SKUS_APROBADOS.split(',') if s.strip()]
    tipos_aprobados = [s.strip() for s in TIPOS_APROBADOS.split(',') if s.strip()]
    display(motor.approve(skus=aprobados, slots=tipos_aprobados, confirm=True))
    display(motor.audit(slots=slots))
else:
    print('Primero revisa la galería y escribe los SKU aprobados.')
""", "rda-save", True)
    md("## Herramienta histórica opcional · compresión PNG\nSe conserva el código original de las 134 imágenes. Ejecútalo solo si necesitas ese proceso y después de revisar sus rutas. No interviene en la generación nueva.", "rda-legacy-title")
    compression = "".join(original["cells"][1]["source"])
    code("#@title Ejecutar la compresión histórica (opcional)\nEJECUTAR_COMPRESION_HISTORICA = False #@param {type:'boolean'}\n"
         + "COMPRESION_ORIGINAL = " + repr(compression) + "\n"
         + "if EJECUTAR_COMPRESION_HISTORICA:\n    get_ipython().run_cell(COMPRESION_ORIGINAL)\nelse:\n    print('Compresión histórica conservada y desactivada.')\n",
         "2TLApgi7qMS4", True)
    metadata = {key: value for key, value in original.get("metadata", {}).items() if key in {"kernelspec", "language_info", "colab"}}
    notebook = {"nbformat": 4, "nbformat_minor": 0, "metadata": metadata, "cells": cells}
    notebook["metadata"]["rincon_backup"] = {"source_commit": SOURCE_COMMIT, "manifest": manifest,
        "notes": "App modules embedded byte-for-byte; Colab I/O and approval are an explicit adapter."}
    notebook["metadata"].setdefault("colab", {})["name"] = "Proyecto_IA_m9 — motor de generación respaldado.ipynb"
    Path(destination).write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"output": str(destination), "cells": len(cells), "source_commit": SOURCE_COMMIT,
                      "embedded_files": list(manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    build(*sys.argv[1:3])
