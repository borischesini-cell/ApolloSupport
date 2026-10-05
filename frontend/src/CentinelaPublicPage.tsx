import { useEffect, useMemo, useState } from 'react';
import { Download, Monitor, ArrowLeft, RefreshCw, Shield, CheckCircle2, AlertCircle } from 'lucide-react';
import { API_URL } from './api';

type DownloadInfo = {
  filename: string;
  url: string;
  size_bytes: number;
  size_mb: number;
};

type PublicInfo = {
  version?: string;
  url?: string;
  published?: boolean;
  downloads?: Record<string, DownloadInfo>;
  error?: string;
};

function detectArch(): 'x64' | 'x86' {
  const ua = navigator.userAgent || '';
  // Win64; x64 / WOW64 → máquina de 64 bits
  if (/Win64|x64|WOW64|amd64/i.test(ua)) return 'x64';
  if (typeof navigator !== 'undefined' && (navigator as any).userAgentData?.platform) {
    const p = String((navigator as any).userAgentData.platform);
    if (/Win/i.test(p)) return 'x64';
  }
  return 'x86';
}

function absUrl(pathOrUrl: string) {
  if (!pathOrUrl) return '';
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  // API_URL es .../api → raíz del host
  const origin = API_URL.replace(/\/api\/?$/, '');
  return `${origin}${pathOrUrl.startsWith('/') ? '' : '/'}${pathOrUrl}`;
}

export default function CentinelaPublicPage({ onBack }: { onBack: () => void }) {
  const [info, setInfo] = useState<PublicInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const arch = useMemo(() => detectArch(), []);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/public/centinela?t=${Date.now()}`);
      if (!res.ok) throw new Error('No se pudo consultar la versión publicada');
      const data = await res.json();
      setInfo(data);
    } catch (e: any) {
      setError(e?.message || 'Error de red');
      setInfo(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const downloads = info?.downloads || {};
  const recommended =
    downloads[arch] || downloads.combined || downloads.x64 || downloads.x86 || null;
  const version = info?.version || '—';

  const startDownload = (d: DownloadInfo) => {
    const url = absUrl(d.url);
    window.location.href = url;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-brand-500/15 via-slate-950 to-slate-950 pointer-events-none" />
      <div className="absolute -top-24 -right-24 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-xl">
        <button
          type="button"
          onClick={onBack}
          className="mb-4 inline-flex items-center gap-2 text-xs font-bold text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft size={14} /> Volver al login
        </button>

        <div className="bg-slate-900/80 border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl backdrop-blur">
          <div className="flex items-start gap-4 mb-6">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-500 to-orange-600 flex items-center justify-center shadow-lg shadow-brand-500/30 shrink-0">
              <Monitor size={28} className="text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight">Apollo Centinela</h1>
              <p className="text-sm text-slate-400 mt-1">
                Instalación y actualización del agente de soporte remoto. No requiere login.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 mb-5">
            <span className="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full bg-sky-500/15 text-sky-300 border border-sky-500/30">
              Versión {loading ? '…' : version}
            </span>
            <span className="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full bg-slate-500/20 text-slate-300 border border-slate-500/30">
              Tu PC: {arch === 'x64' ? 'Windows 64-bit' : 'Windows 32-bit'}
            </span>
            <button
              type="button"
              onClick={load}
              className="ml-auto inline-flex items-center gap-1.5 text-[10px] font-bold text-slate-400 hover:text-white"
              title="Actualizar info"
            >
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Actualizar
            </button>
          </div>

          {error && (
            <div className="mb-4 flex items-start gap-2 text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-xl px-3 py-2">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!loading && info && !info.published && (
            <div className="mb-4 flex items-start gap-2 text-sm text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-xl px-3 py-2">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>Todavía no hay instaladores publicados en el servidor (carpeta updates/).</span>
            </div>
          )}

          {recommended && (
            <button
              type="button"
              onClick={() => startDownload(recommended)}
              className="w-full flex items-center justify-center gap-3 bg-gradient-to-r from-brand-500 to-orange-600 hover:from-brand-600 hover:to-orange-700 text-white font-extrabold py-4 rounded-2xl shadow-[0_0_24px_rgba(245,158,11,0.35)] transition-all mb-4"
            >
              <Download size={20} />
              Descargar recomendado ({recommended.size_mb} MB)
            </button>
          )}

          <div className="space-y-2 mb-6">
            {(['x64', 'x86', 'combined'] as const).map((key) => {
              const d = downloads[key];
              if (!d) return null;
              const label =
                key === 'x64' ? 'Windows 64-bit' :
                key === 'x86' ? 'Windows 32-bit' :
                'Instalador unificado';
              const isRec = recommended?.filename === d.filename && key === (downloads[arch] ? arch : 'combined');
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => startDownload(d)}
                  className={`w-full flex items-center justify-between gap-3 px-4 py-3 rounded-xl border text-left transition-all ${
                    isRec
                      ? 'bg-brand-500/10 border-brand-500/40 hover:bg-brand-500/20'
                      : 'bg-slate-950/60 border-white/10 hover:border-white/20'
                  }`}
                >
                  <div>
                    <div className="text-sm font-bold flex items-center gap-2">
                      {label}
                      {isRec && (
                        <span className="text-[9px] uppercase font-black text-brand-400">Recomendado</span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono">{d.filename}</div>
                  </div>
                  <div className="text-xs font-bold text-slate-300 flex items-center gap-2">
                    {d.size_mb} MB
                    <Download size={14} className="text-brand-400" />
                  </div>
                </button>
              );
            })}
          </div>

          <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-slate-400">
              <Shield size={14} /> Cómo instalar / actualizar
            </div>
            <ol className="space-y-2 text-sm text-slate-300 list-decimal list-inside">
              <li>Descargá e instalá (si Windows pide permiso, tocá <strong>Sí</strong>).</li>
              <li>Al terminar se abre solo ApolloSoporte con el ID y el PIN. No hace falta nada más.</li>
              <li>Si SmartScreen avisa: <strong>Más información → Ejecutar de todas formas</strong>.</li>
            </ol>
            <div className="flex items-start gap-2 text-[11px] text-emerald-400/90 pt-1">
              <CheckCircle2 size={14} className="mt-0.5 shrink-0" />
              <span>
                Actualización: el mismo instalador reemplaza la versión anterior y deja el icono
                y la ventana listos. Si ya tenés Centinela abierto, usá «Actualizar ahora» y aceptá el UAC.
              </span>
            </div>
          </div>
        </div>

        <p className="text-center text-[10px] text-slate-600 mt-4 font-bold tracking-wide">
          Master IS · Apollo Support · {API_URL.includes('localhost') ? 'LOCAL' : 'PRODUCCIÓN'}
        </p>
      </div>
    </div>
  );
}
