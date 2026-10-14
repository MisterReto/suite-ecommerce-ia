// Retire the old shell cache. Pages, scripts and API requests use the network.
self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith('rincon-shell-')).map(key => caches.delete(key))
  )).then(() => self.clients.claim()));
});
