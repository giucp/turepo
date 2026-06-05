// Tu Repo · Venezuela — service worker v3
// Sube el número de versión (CACHE) cada vez que cambies algo importante:
// eso obliga a borrar lo viejo y traer lo nuevo.
const CACHE = 'turepo-v3';

self.addEventListener('install', e => {
  self.skipWaiting(); // activa la versión nueva de inmediato
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(k => caches.delete(k)))) // borra TODO el caché viejo
      .then(() => self.clients.claim())
  );
});

// El HTML y los datos siempre desde la red (nunca cacheados),
// así nunca te quedas con una versión vieja de la app.
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
