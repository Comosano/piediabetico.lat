const CACHE_NAME = 'piediabetico-v19-cache';
const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './styles.css?v=17',
  './app.js?v=17',
  './manifest.json'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Ignorar POST y APIs externas de IA
  if (event.request.method !== 'GET' || event.request.url.includes('/agentes/') || event.request.url.includes('/analizar-foto') || event.request.url.includes('api.evidencemd.ai')) {
    return;
  }
  
  // ESTRATEGIA NETWORK-FIRST: Siempre busca la versión más nueva en el servidor
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => caches.match(event.request))
  );
});
