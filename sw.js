const CACHE_NAME = 'piediabetico-v26-cache';
const OFFLINE_URL = './offline.html';

const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './offline.html',
  './styles.css?v=23',
  './app.js?v=23',
  './manifest.json',
  './icon.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
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

  // Si es navegación HTML, intentar red y hacer fallback a offline.html
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseToCache));
          }
          return networkResponse;
        })
        .catch(() => {
          return caches.match(event.request).then((cachedResp) => {
            return cachedResp || caches.match(OFFLINE_URL);
          });
        })
    );
    return;
  }
  
  // ESTRATEGIA NETWORK-FIRST PARA ASSETS:
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseToCache));
        }
        return networkResponse;
      })
      .catch(() => caches.match(event.request))
  );
});


// ═══════════════════════════════════════════════════════════════════════
// TAREA 5: RECEPCIÓN Y GESTIÓN DE WEB PUSH NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════════════
// NOTA TÉCNICA DE COMPATIBILIDAD CON APPLE / IOS:
// 1. En iOS / iPadOS, las Web Push Notifications requieren iOS 16.4 o superior.
// 2. La PWA DEBE estar obligatoriamente agregada a la Pantalla de Inicio (Home Screen)
//    y ejecutándose en modo 'standalone'.
// 3. El permiso solo puede ser solicitado mediante una acción explícita del usuario (gesture).
// ═══════════════════════════════════════════════════════════════════════

self.addEventListener('push', (event) => {
  let data = {
    title: 'piediabetico.lat — Alerta Clínica',
    body: 'Nueva actualización en tu ficha de seguimiento o consulta médica.',
    icon: './icon.svg',
    badge: './icon.svg',
    data: { url: './index.html' }
  };

  if (event.data) {
    try {
      data = Object.assign(data, event.data.json());
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || './icon.svg',
    badge: data.badge || './icon.svg',
    vibrate: [200, 100, 200],
    tag: data.tag || 'piediabetico-notification',
    renotify: true,
    data: data.data || { url: './index.html' },
    actions: [
      { action: 'open', title: 'Ver en la App' },
      { action: 'close', title: 'Descartar' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'close') return;

  const targetUrl = (event.notification.data && event.notification.data.url) || './index.html';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes('index.html') && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
