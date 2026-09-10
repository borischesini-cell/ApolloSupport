/* Versión inyectada en build por vite (placeholders __APOLLO_*__) */
const APP_VERSION = '__APOLLO_VERSION__';
const APP_BUILD = '__APOLLO_BUILD__';
const CACHE_PREFIX = 'apollo-support';
const CACHE_NAME = `${CACHE_PREFIX}-v${APP_VERSION}`;

const OFFLINE_ASSETS = [
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
  '/favicon.svg',
];

const VERSION_URL = '/version.txt';
const VERSION_CHECK_MS = 5 * 60 * 1000;

/** Rutas que nunca deben usar cache-first (app + API siempre frescos). */
function isNetworkOnly(pathname) {
  if (pathname.startsWith('/api/')) return true;
  if (pathname.startsWith('/assets/')) return true;
  if (pathname === '/index.html' || pathname === '/') return true;
  if (pathname === VERSION_URL) return true;
  if (/^\/sw(-v[\d.]+)?\.js$/i.test(pathname)) return true;
  return false;
}

function isStaticAsset(pathname) {
  return (
    pathname === '/manifest.json'
    || pathname === '/favicon.svg'
    || pathname.startsWith('/icon-')
  );
}

async function fetchServerVersion() {
  const res = await fetch(`${VERSION_URL}?t=${Date.now()}`, {
    cache: 'no-store',
    headers: { Accept: 'text/plain' },
  });
  if (!res.ok) return null;
  const text = await res.text();
  const m = text.match(/^version=(.+)$/m);
  return m ? m[1].trim() : null;
}

async function notifyClientsUpdate(serverVersion) {
  const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  for (const client of clients) {
    client.postMessage({
      type: 'APOLLO_UPDATE_AVAILABLE',
      localVersion: APP_VERSION,
      serverVersion,
      build: APP_BUILD,
    });
  }
}

async function checkForPortalUpdate() {
  try {
    const serverVersion = await fetchServerVersion();
    if (serverVersion && serverVersion !== APP_VERSION) {
      await notifyClientsUpdate(serverVersion);
      return true;
    }
  } catch {
    /* sin red */
  }
  return false;
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(OFFLINE_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((n) => n.startsWith(CACHE_PREFIX) && n !== CACHE_NAME)
          .map((n) => caches.delete(n)),
      ))
      .then(() => self.clients.claim())
      .then(() => checkForPortalUpdate()),
  );
});

self.addEventListener('message', (event) => {
  const data = event.data;
  if (!data || typeof data !== 'object') return;

  if (data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (data.type === 'CHECK_UPDATE') {
    event.waitUntil(checkForPortalUpdate());
  }
});

let versionCheckTimer = null;
function scheduleVersionChecks() {
  if (versionCheckTimer) clearInterval(versionCheckTimer);
  versionCheckTimer = setInterval(() => {
    checkForPortalUpdate();
  }, VERSION_CHECK_MS);
}
scheduleVersionChecks();

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (isNetworkOnly(url.pathname) || event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' }).catch(() => {
        if (event.request.mode === 'navigate') {
          return caches.match('/index.html').then((r) => r || new Response(
            '<!DOCTYPE html><html><body style="font-family:sans-serif;padding:2rem;background:#0f172a;color:#fff"><h1>Sin conexión</h1><p>Reintente cuando tenga internet.</p></body></html>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } },
          ));
        }
        return Response.error();
      }),
    );
    return;
  }

  if (isStaticAsset(url.pathname)) {
    event.respondWith(staleWhileRevalidate(event.request));
    return;
  }

  event.respondWith(fetch(event.request, { cache: 'no-store' }));
});

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  const networkPromise = fetch(request)
    .then((res) => {
      if (res && res.status === 200) {
        cache.put(request, res.clone());
      }
      return res;
    })
    .catch(() => null);

  if (cached) {
    void networkPromise;
    return cached;
  }
  const res = await networkPromise;
  return res || Response.error();
}

self.addEventListener('push', (event) => {
  let payload = {
    title: 'Soporte ApolloGesCom',
    body: 'Nueva alerta recibida desde un Centinela',
    url: '/',
  };

  if (event.data) {
    try {
      payload = { ...payload, ...event.data.json() };
    } catch {
      payload.body = event.data.text();
    }
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      vibrate: [200, 100, 200],
      data: { url: payload.url || '/' },
      actions: [
        { action: 'open', title: 'Ver Detalles' },
        { action: 'close', title: 'Cerrar' },
      ],
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.action === 'close') return;

  const urlToOpen = new URL(event.notification.data?.url || '/', self.location.origin).href;
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url === urlToOpen && 'focus' in client) {
          return client.focus();
        }
      }
      const sameOrigin = windowClients.find((c) => c.url.startsWith(self.location.origin));
      if (sameOrigin && 'focus' in sameOrigin) {
        sameOrigin.postMessage({ type: 'APOLLO_NAVIGATE', url: urlToOpen });
        return sameOrigin.focus();
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    }),
  );
});
