// Caché PWA de la carcasa pública; no guarda sesión, datos privados ni operaciones de API.
// Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
/* UI shell only. Private photos, credentials, API responses and writes stay online. */
const CACHE = 'rincon-shell-20261006-v3';
const PUBLIC = ['/', '/logo.png', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PUBLIC)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('rincon-shell-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  const shell = url.pathname === '/' && request.mode === 'navigate';
  const asset = (url.pathname.startsWith('/_next/static/') || PUBLIC.includes(url.pathname) && url.pathname !== '/') && !url.search;
  if (!shell && !asset) return;
  if (shell) {
    event.respondWith(fetch(request).then(response => {
      if (response.ok) event.waitUntil(caches.open(CACHE).then(cache => cache.put('/', response.clone())));
      return response;
    }).catch(() => caches.match('/').then(response => response || Response.error())));
  } else {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => {
      if (response.ok && response.type === 'basic') event.waitUntil(caches.open(CACHE).then(cache => cache.put(request, response.clone())));
      return response;
    })));
  }
});
