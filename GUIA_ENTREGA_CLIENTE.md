# Entrega de la Suite al cliente

Esta versión está preparada para que cada cliente trabaje con su propia cuenta de Google Drive y su propio proyecto de Gemini. Las credenciales de Google OAuth y WooCommerce pertenecen al despliegue de la aplicación; el inventario, las imágenes y el consumo de Gemini pertenecen al cliente conectado.

## Carpeta que recibe el cliente

La carpeta puede llamarse como el cliente prefiera, pero debe contener:

```text
Carpeta del cliente/
├── inventario_completo
│   └── Hoja nativa de Google con la pestaña "Lista completa"
├── imagenes_generadas/
└── logo_rincon_asia.png        # opcional
```

También se admite una carpeta descargada y vuelta a subir:

```text
Carpeta del cliente/
├── inventario_completo.xlsx   # también .xls, .ods o .csv
├── imagenes_generadas/
└── logo_rincon_asia.png
```

Cuando no existe una hoja nativa, la aplicación convierte una sola vez el archivo importable a una hoja llamada `inventario_completo` y conserva el archivo original como respaldo. El XLSX es la opción recomendada porque conserva todas las pestañas y fórmulas; un CSV solo contiene una pestaña.

## Pasos que realiza el cliente

1. Subir la carpeta completa a su Drive o aceptar la carpeta compartida.
2. Abrir la Suite y pulsar **Conectar con Google Drive**.
3. Copiar el enlace de la carpeta y pegarlo en **Ajustes → Selecciona y valida la carpeta**.
4. Pulsar **Validar y usar esta carpeta**. La app comprueba los encabezados de `Lista completa`, cuenta los productos y resuelve `imagenes_generadas` dentro de la misma carpeta.
5. Entrar a [Google AI Studio](https://aistudio.google.com/apikey), crear un proyecto/clave propios y activar la facturación cuando necesite el nivel de pago.
6. Pegar la clave en **Ajustes → Clave de Gemini**.
7. Actualizar categorías desde Drive y probar primero con un producto.

La clave se conserva únicamente en memoria durante la sesión del servidor. No se escribe en GitHub, Google Drive ni Google Sheets. Si Render reinicia la instancia, el cliente deberá pegarla de nuevo.

## Configuración que conserva el responsable de la aplicación

Estas variables siguen siendo secretos del servicio de Render:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `WC_BASE_URL`, `WC_CONSUMER_KEY`, `WC_CONSUMER_SECRET`
- credenciales de WordPress necesarias para medios
- interruptores de escritura de WooCommerce/WordPress

El cliente no necesita modificar esas variables para usar su carpeta y su clave de Gemini. Para conectar una tienda WooCommerce diferente sí se requiere otro despliegue o reemplazar los secretos de WooCommerce.

El consentimiento OAuth debe estar publicado para usuarios externos o el correo del cliente debe estar registrado como usuario de prueba en Google Cloud.

## Aislamiento entre clientes

- La hoja se busca dentro de la carpeta seleccionada para la sesión.
- `imagenes_generadas` se resuelve dentro de esa misma carpeta.
- Se eliminó el ID fijo de imágenes del proyecto original.
- Los cachés de imágenes incluyen el ID de sesión y el ID de carpeta.
- La clave de Gemini nunca se comparte entre sesiones.
- El modo ligero ya no contiene IDs predeterminados del inventario original.

## Modelos

- Texto: `GEMINI_TEXT_MODEL` (predeterminado `gemini-2.5-flash`).
- Imagen: `GEMINI_IMAGE_MODEL` (predeterminado `gemini-3.1-flash-image`).

Ambos se pueden cambiar desde variables de entorno sin editar código.
