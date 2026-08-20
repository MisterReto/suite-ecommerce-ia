"""Arranque único: Suite IA + sincronización individual WooCommerce.

Carga app.py mediante ai_app para usar `Lista completa` como fuente canónica y
luego monta las rutas individuales existentes de product_web. No incluye el
sistema de lotes.
"""
import sys

import ai_app

# Todos los módulos históricos que hagan `import app` reciben el runtime
# canónico preparado por ai_app, sin modificar app.py en disco.
sys.modules["app"] = ai_app.legacy

import product_web

fastapi_app = product_web.fastapi_app
