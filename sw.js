// La Cosa · Barinas — service worker mínimo
// Su sola presencia hace que Android instale la app "de verdad"
// (ícono limpio, sin el sello de Chrome, a pantalla completa).
const CACHE = 'lacosa-v1';

// Al instalar, guarda la página principal para que abra aunque haya internet lento.
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(['./', './index.html']).catch(()=>{}))
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

// Estrategia "red primero": siempre intenta traer lo más nuevo;
// si no hay internet, usa lo guardado. Así nunca se queda con datos viejos.
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request)
      .then(resp => {
        const copia = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, copia)).catch(()=>{});
        return resp;
      })
      .catch(() => caches.match(e.request).then(r => r || caches.match('./index.html')))
  );
});
