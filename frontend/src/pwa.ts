import { APP_VERSION, APP_BUILD, APP_VERSION_STORAGE_KEY } from './version';

const SW_URL = `/sw-v${APP_VERSION}.js`;
const VERSION_URL = '/version.txt';

export type UpdateInfo = {
  serverVersion: string;
  localVersion: string;
  build?: string;
};

/** Desregistra SW viejos (otra versión o sw.js legacy). */
export async function migrateStaleServiceWorkers(): Promise<void> {
  if (!('serviceWorker' in navigator)) return;

  const regs = await navigator.serviceWorker.getRegistrations();
  await Promise.all(
    regs.map(async (reg) => {
      const scriptUrl = reg.active?.scriptURL || reg.installing?.scriptURL || reg.waiting?.scriptURL || '';
      const isCurrent = scriptUrl.includes(SW_URL);
      if (!isCurrent) {
        await reg.unregister();
      }
    }),
  );
}

/** Compara version.txt del servidor con el bundle actual. */
export async function fetchServerPortalVersion(): Promise<string | null> {
  try {
    const res = await fetch(`${VERSION_URL}?t=${Date.now()}`, {
      cache: 'no-store',
      headers: { Accept: 'text/plain' },
    });
    if (!res.ok) return null;
    const text = await res.text();
    const m = text.match(/^version=(.+)$/m);
    return m ? m[1].trim() : null;
  } catch {
    return null;
  }
}

export function isNewerVersion(server: string, local: string): boolean {
  const parse = (v: string) => v.split('.').map((n) => parseInt(n, 10) || 0);
  const a = parse(server);
  const b = parse(local);
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    if ((a[i] || 0) > (b[i] || 0)) return true;
    if ((a[i] || 0) < (b[i] || 0)) return false;
  }
  return false;
}

/**
 * Si el HTML/JS en caché del navegador es de un deploy anterior, limpia caches
 * y recarga una sola vez (sin bucle).
 */
export async function ensureFreshPortalBundle(): Promise<boolean> {
  const prevKey = localStorage.getItem('apollo_portal_deploy_id');
  if (prevKey === APP_VERSION_STORAGE_KEY) {
    const server = await fetchServerPortalVersion();
    if (server && isNewerVersion(server, APP_VERSION)) {
      return true;
    }
    return false;
  }

  localStorage.setItem('apollo_portal_deploy_id', APP_VERSION_STORAGE_KEY);

  if (prevKey === null) return false;

  if ('caches' in window) {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith('apollo-support')).map((k) => caches.delete(k)));
  }
  await migrateStaleServiceWorkers();
  return true;
}

export async function registerPortalServiceWorker(
  onUpdateAvailable?: (info: UpdateInfo) => void,
): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator) || !import.meta.env.PROD) return null;

  await migrateStaleServiceWorkers();

  const reg = await navigator.serviceWorker.register(SW_URL, { scope: '/' });
  console.info(`[Apollo] SW registrado: ${SW_URL}`);

  const notify = (serverVersion: string) => {
    onUpdateAvailable?.({ serverVersion, localVersion: APP_VERSION, build: APP_BUILD });
  };

  const checkServer = async () => {
    const server = await fetchServerPortalVersion();
    if (server && (server !== APP_VERSION || isNewerVersion(server, APP_VERSION))) {
      notify(server);
    }
  };

  navigator.serviceWorker.addEventListener('message', (ev) => {
    const d = ev.data;
    if (d?.type === 'APOLLO_UPDATE_AVAILABLE' && d.serverVersion) {
      notify(d.serverVersion);
    }
    if (d?.type === 'APOLLO_NAVIGATE' && d.url) {
      window.location.href = d.url;
    }
  });

  if (reg.waiting) {
    const server = await fetchServerPortalVersion();
    if (server) notify(server);
  }

  reg.addEventListener('updatefound', () => {
    const worker = reg.installing;
    if (!worker) return;
    worker.addEventListener('statechange', () => {
      if (worker.state === 'installed' && navigator.serviceWorker.controller) {
        void checkServer();
      }
    });
  });

  let reloading = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloading) return;
    reloading = true;
    window.location.reload();
  });

  const pingUpdateCheck = () => {
    reg.update().catch(() => {});
    reg.active?.postMessage({ type: 'CHECK_UPDATE' });
    void checkServer();
  };

  pingUpdateCheck();
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') pingUpdateCheck();
  });
  window.setInterval(pingUpdateCheck, 5 * 60 * 1000);

  return reg;
}

/** Activa SW en espera y recarga cuando tome control. */
export async function applyPortalUpdate(): Promise<void> {
  const reg = await navigator.serviceWorker.getRegistration('/');
  if (reg?.waiting) {
    reg.waiting.postMessage({ type: 'SKIP_WAITING' });
    return;
  }
  window.location.reload();
}

/** Recarga forzada cuando el bundle local está detrás del servidor. */
export function reloadForNewBundle(): void {
  const clearCaches =
    typeof caches !== 'undefined'
      ? caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      : Promise.resolve();
  void clearCaches.finally(() => {
    globalThis.location.reload();
  });
}
