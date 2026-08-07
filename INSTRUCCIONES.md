# Actualización del tutorial

Reemplaza en la raíz del repositorio los archivos de este paquete, conservando
la carpeta `static` con sus dos archivos.

Estructura esperada:

```text
app.py
Dockerfile
requirements.txt
static/
  tutorial.js
  tutorial.css
```

El tutorial no registra usuarios, no usa `localStorage` y no se abre por sí
solo. Únicamente inicia al presionar el botón grande **VER TUTORIAL GUIADO**.

Después del despliegue:

1. Comprueba que `/static/tutorial.js` y `/static/tutorial.css` abran en el
   dominio de la app.
2. Haz una recarga completa del navegador (`Ctrl` + `F5`) para evitar archivos
   anteriores en caché.
3. Presiona **VER TUTORIAL GUIADO** y recorre los pasos con Siguiente y Atrás.

El `Dockerfile` incluye ahora `COPY static ./static`; esa línea es necesaria
para que Render publique el JavaScript y el CSS.
