import { useState } from 'react';
import { RefreshCw, X } from 'lucide-react';
import type { UpdateInfo } from './pwa';
import { applyPortalUpdate, reloadForNewBundle, isNewerVersion } from './pwa';

type Props = {
  update: UpdateInfo | null;
  onDismiss: () => void;
};

export default function PwaUpdateBanner({ update, onDismiss }: Props) {
  const [applying, setApplying] = useState(false);

  if (!update) return null;

  const needsFullReload = isNewerVersion(update.serverVersion, update.localVersion);

  const handleApply = async () => {
    setApplying(true);
    try {
      if (needsFullReload) {
        reloadForNewBundle();
      } else {
        await applyPortalUpdate();
      }
    } finally {
      setApplying(false);
    }
  };

  return (
    <div
      role="status"
      className="fixed bottom-4 left-4 right-4 z-[10000] mx-auto max-w-lg animate-in slide-in-from-bottom-4 fade-in md:left-auto md:right-6"
    >
      <div className="flex items-start gap-3 rounded-2xl border border-amber-500/40 bg-slate-900/95 p-4 shadow-2xl backdrop-blur-md">
        <RefreshCw size={20} className="mt-0.5 shrink-0 text-amber-400" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-white">Nueva versión del portal</p>
          <p className="mt-0.5 text-xs text-slate-400">
            v{update.localVersion} → v{update.serverVersion}
            {update.build ? ` (${update.build})` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={handleApply}
          disabled={applying}
          className="shrink-0 rounded-xl bg-amber-500 px-3 py-2 text-xs font-black uppercase text-slate-900 hover:bg-amber-400 disabled:opacity-60"
        >
          {applying ? '…' : 'Actualizar'}
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-lg p-1.5 text-slate-500 hover:bg-white/10 hover:text-white"
          aria-label="Cerrar"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
