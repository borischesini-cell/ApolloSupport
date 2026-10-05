import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import PwaUpdateBanner from './PwaUpdateBanner.tsx'
import {
  ensureFreshPortalBundle,
  registerPortalServiceWorker,
  reloadForNewBundle,
  type UpdateInfo,
} from './pwa'

function Root() {
  const [pendingUpdate, setPendingUpdate] = useState<UpdateInfo | null>(null);

  useEffect(() => {
    registerPortalServiceWorker((info) => {
      setPendingUpdate((prev) => prev ?? info);
    });
  }, []);

  return (
    <>
      <App />
      <PwaUpdateBanner
        update={pendingUpdate}
        onDismiss={() => setPendingUpdate(null)}
      />
    </>
  );
}

async function bootstrap() {
  const needsReload = await ensureFreshPortalBundle();
  if (needsReload) {
    reloadForNewBundle();
    return;
  }

  createRoot(document.getElementById('root')!).render(
    <Root />
  );
}

void bootstrap();
