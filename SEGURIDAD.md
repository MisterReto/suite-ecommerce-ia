# Seguridad de Suite e-commerce

Controles aplicados a ambos servicios públicos. Referencia solicitada:
https://www.fortinet.com/lat/resources/cyberglossary/types-of-cyber-attacks

| Riesgo | Control implementado | Alcance |
| --- | --- | --- |
| CSRF y login falsificado | Origen exacto en escrituras; OAuth state comparado en tiempo constante; cookies Secure/HttpOnly/SameSite | Las excepciones internas requieren firma HMAC y ticket de un uso |
| Secuestro/repetición de sesiones | Sesiones con caducidad y cupo; tickets de 120 s; HMAC con tiempo y nonce | No hay credenciales en enlaces o HTML; el worker recibe solo token Google temporal |
| XSS e inyección de HTML | Escape de celdas/atributos/enlaces; descripciones saneadas con Bleach; CSP y nosniff | HTML básico permitido; CSP conserva unsafe-inline por páginas existentes; únicamente la portada Gradio del principal admite unsafe-eval para compilar sus plantillas HTML. El segundo servicio y las demás rutas no lo admiten |
| Manipulación de URL, SSRF, MITM | HTTPS, verificación TLS, rechazo de destinos privados literales/localhost y credenciales en URL; redirects desactivados en clientes de tienda; allowlist de herramientas | URLs de tienda configuradas en servidor; no incluye protección completa contra DNS rebinding ni compromiso del DNS/proveedor |
| DoS y fuerza bruta | 600 solicitudes/min por dirección observada; 30 accesos de autenticación/5 min; cuerpos limitados; máximo 3 operaciones pesadas; 2 hilos de subida | Límites locales por proceso; no sustituyen mitigación DDoS de red/WAF |
| Archivos maliciosos | Upload requiere sesión; descargas/subidas de imágenes limitadas a 12 MB; validación del contenido con Pillow; rechazo de SVG y ejecutables; nosniff | WordPress recibe solo imágenes válidas de hasta 24 megapíxeles; no ejecuta archivos subidos. No sustituye antivirus del cliente |
| Fugas de información | Sin logs HTTP de URLs; no se registran cuerpos en middleware; errores de lote genéricos/redactados; respuestas de sesión sin caché | Logs de proveedores y código legado deben mantener secretos fuera de mensajes |
| Dependencias/suministro | Auditoría pip-audit en CI, actualización de pip, pruebas antes del despliegue | La auditoría detecta vulnerabilidades conocidas, no garantiza ausencia de fallos |
| Inyección SQL/comandos | Persistencia mediante APIs de Sheets y payloads JSON; no ejecuta SQL ni shell derivados de celdas | No protege instalaciones WordPress externas vulnerables |

Además se mantiene el aislamiento del segundo servicio, publicación explícita,
verificación posterior de los productos y portadas FULL sin precio/stock propio.
No se cambia contenido, estilos, plugins ni caché de WordPress desde estas defensas.

## Medidas fuera del código de la Suite

Phishing/spear phishing, whaling, ransomware, ataques internos, contraseñas robadas,
DNS comprometido y DDoS volumétrico no se resuelven únicamente con middleware.
El propietario debe mantener MFA en Google/Render/GitHub/WordPress, permisos mínimos,
actualizaciones de WordPress/plugins, copias recuperables y protección de red/WAF.
No se ha configurado ni contratado un WAF, antivirus ni un servicio DDoS.

Mantén `SYNC_SERVICE_SHARED_KEY` aleatoria (al menos 32 bytes), rota claves si se
filtran y no las incluyas en repositorios, CSV o capturas. El segundo servicio no
necesita secretos OAuth ni claves de generación de IA. Las pruebas de seguridad
usan datos ficticios y no realizan ataques contra la tienda del cliente.
