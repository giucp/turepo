// Tu Repo · Venezuela — service worker v4
// Acelera la apertura cacheando el cascaron de la app y las librerias/fuentes.
// IMPORTANTE: los DATOS nunca se cachean (las llamadas a *.supabase.co pasan
// directo a la red), asi que siempre se ven en vivo. Solo se cachea el "cascaron".
//
// Para forzar que todos bajen una version limpia, sube el numero de VERSION:
// eso renombra los caches y el 'activate' borra los viejos.
const VERSION = 'v4';
const SHELL  = 'turepo-shell-'  + VERSION;   // index.html / navegacion
const VENDOR = 'turepo-vendor-' + VERSION;   // supabase-js + fuentes (inmutables)

// Origenes de terceros que son inmutables por version -> se pueden cachear sin riesgo.
const VENDOR_HOSTS = ['cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', e => {
  self.skipWaiting(); // activa la version nueva de inmediato
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== SHELL && k !== VENDOR).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;

  let url;
  try { url = new URL(req.url); } catch (_) { return; }

  // 1) HTML del propio sitio (incluida la navegacion del TWA): stale-while-revalidate.
  //    Sirve el cascaron cacheado al instante y trae el fresco para la proxima vez.
  if (req.mode === 'navigate' ||
      (url.origin === self.location.origin && (url.pathname === '/' || url.pathname.endsWith('.html')))) {
    e.respondWith(staleWhileRevalidate(e, req, SHELL));
    return;
  }

  // 2) Librerias y fuentes inmutables: cache-first (se bajan una sola vez).
  if (VENDOR_HOSTS.includes(url.hostname)) {
    e.respondWith(cacheFirst(e, req, VENDOR));
    return;
  }

  // 3) Todo lo demas (API de Supabase, iconos, og.jpg, manifest...) pasa directo
  //    a la red sin tocar. Los datos siempre en vivo.
});

async function staleWhileRevalidate(e, req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  const fromNet = fetch(req)
    .then(res => { if (res && res.ok) cache.put(req, res.clone()); return res; })
    .catch(() => cached);
  if (cached) { e.waitUntil(fromNet); return cached; }   // sirve lo cacheado, revalida atras
  return fromNet;                                         // primera vez: va a la red
}

async function cacheFirst(e, req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if (cached) return cached;
  const res = await fetch(req);
  // res.ok cubre respuestas normales; type 'opaque' cubre las fuentes cross-origin sin CORS.
  if (res && (res.ok || res.type === 'opaque')) e.waitUntil(cache.put(req, res.clone()));
  return res;
}
