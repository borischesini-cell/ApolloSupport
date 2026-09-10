import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, RefreshCw, Search } from 'lucide-react';
import { getIaBillingMonth } from './api';

type BillingRow = {
  gescom_serial?: string;
  gescom_user?: string;
  nomfa?: string;
  raso?: string;
  total_request?: number;
  total_tokens?: number;
  client_usd?: number;
  provider_usd?: number;
  credit_usd?: number;
  bill_usd?: number;
  by_type?: Record<string, { client_usd?: number; total_request?: number; total_tokens?: number }>;
  centinela?: {
    client_id?: number;
    codigo?: string;
    cclifac?: string;
    razon_social?: string;
    nombre_fantasia?: string;
    activo?: boolean;
  } | null;
};

function monthStartISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function money(n?: number) {
  const v = Number(n ?? 0);
  return `u$s ${v.toFixed(2)}`;
}

export default function IaBillingPanel() {
  const [desde, setDesde] = useState(monthStartISO);
  const [hasta, setHasta] = useState(todayISO);
  const [serial, setSerial] = useState('');
  const [q, setQ] = useState('');
  const [onlyBillable, setOnlyBillable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getIaBillingMonth(desde, hasta, serial.trim() || undefined);
      if (data?.result === 'error') {
        setError(data.message || 'Error al consultar billing IA');
        setPayload(null);
      } else {
        setPayload(data);
      }
    } catch (e: any) {
      setError(e?.message || 'Error de red');
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, [desde, hasta, serial]);

  useEffect(() => {
    load();
  }, []);

  const rows: BillingRow[] = useMemo(() => {
    const list: BillingRow[] = Array.isArray(payload?.resultado) ? payload.resultado : [];
    const term = q.trim().toLowerCase();
    return list.filter((r) => {
      if (onlyBillable && !(Number(r.bill_usd) > 0)) return false;
      if (!term) return true;
      const hay = [
        r.gescom_serial,
        r.gescom_user,
        r.nomfa,
        r.raso,
        r.centinela?.codigo,
        r.centinela?.cclifac,
        r.centinela?.razon_social,
        r.centinela?.nombre_fantasia,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return hay.includes(term);
    });
  }, [payload, q, onlyBillable]);

  const totals = payload?.totals || {};

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-black text-white flex items-center gap-2">
            <Activity className="text-brand-500" size={26} /> Consumo ApolloIA
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Tokens y exceso sobre crédito mensual por serial, con vínculo Centinela (CCOD / CCLIFAC).
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2 shadow-lg transition-all self-start"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Actualizar
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3 bg-slate-900/60 border border-white/5 rounded-2xl p-4">
        <label className="text-xs text-slate-400 font-bold uppercase tracking-wide">
          Desde
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="mt-1 w-full bg-slate-950 border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
        </label>
        <label className="text-xs text-slate-400 font-bold uppercase tracking-wide">
          Hasta
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="mt-1 w-full bg-slate-950 border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
        </label>
        <label className="text-xs text-slate-400 font-bold uppercase tracking-wide xl:col-span-2">
          Serial (opcional)
          <input
            value={serial}
            onChange={(e) => setSerial(e.target.value)}
            placeholder="Filtrar un serial GesCom"
            className="mt-1 w-full bg-slate-950 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          />
        </label>
        <label className="text-xs text-slate-400 font-bold uppercase tracking-wide flex items-end pb-2 gap-2 cursor-pointer">
          <input type="checkbox" checked={onlyBillable} onChange={(e) => setOnlyBillable(e.target.checked)} className="rounded" />
          Solo con exceso
        </label>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 text-red-300 px-4 py-3 text-sm">
          {error}
          <div className="text-red-400/80 text-xs mt-1">
            Verificá IA_API_URL / IA_API_KEY / IA_SERIAL_GESCOM en el backend Centinela.
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label="Seriales" value={String(totals.serials ?? rows.length)} />
        <Stat label="A facturar" value={String(totals.billable_serials ?? rows.filter((r) => Number(r.bill_usd) > 0).length)} />
        <Stat label="Consumo cliente" value={money(totals.client_usd)} />
        <Stat label="Exceso (bill)" value={money(totals.bill_usd)} accent />
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar serial, user, CCLIFAC, razón social..."
          className="w-full bg-slate-900/70 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white"
        />
      </div>

      <div className="overflow-auto rounded-2xl border border-white/5 bg-slate-900/40">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wider text-slate-500 border-b border-white/5">
            <tr>
              <th className="px-3 py-3">User</th>
              <th className="px-3 py-3">Serial</th>
              <th className="px-3 py-3">Cliente</th>
              <th className="px-3 py-3">CCLIFAC</th>
              <th className="px-3 py-3 text-right">Req</th>
              <th className="px-3 py-3 text-right">Chat</th>
              <th className="px-3 py-3 text-right">Invoice</th>
              <th className="px-3 py-3 text-right">Total</th>
              <th className="px-3 py-3 text-right">Exceso</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-slate-500">
                  Consultando API IA...
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-slate-500">
                  Sin consumo en el rango.
                </td>
              </tr>
            )}
            {!loading &&
              rows.map((r) => {
                const chat = Number(r.by_type?.chat?.client_usd ?? 0);
                const inv = Number(r.by_type?.invoice?.client_usd ?? 0);
                const name =
                  r.centinela?.nombre_fantasia ||
                  r.centinela?.razon_social ||
                  r.nomfa ||
                  r.raso ||
                  '—';
                return (
                  <tr key={r.gescom_serial || Math.random()} className="border-b border-white/5 hover:bg-white/[0.03]">
                    <td className="px-3 py-2.5 font-mono text-slate-300">{r.gescom_user || (r.gescom_serial || '').slice(0, 4)}</td>
                    <td className="px-3 py-2.5 font-mono text-xs text-slate-400">{r.gescom_serial}</td>
                    <td className="px-3 py-2.5 text-white">
                      <div className="font-medium">{name}</div>
                      <div className="text-[11px] text-slate-500">
                        {r.centinela?.codigo ? `CCOD ${r.centinela.codigo}` : 'sin match Centinela'}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-slate-300">{r.centinela?.cclifac || '—'}</td>
                    <td className="px-3 py-2.5 text-right text-slate-300">{r.total_request ?? 0}</td>
                    <td className="px-3 py-2.5 text-right text-slate-300">{money(chat)}</td>
                    <td className="px-3 py-2.5 text-right text-slate-300">{money(inv)}</td>
                    <td className="px-3 py-2.5 text-right text-white font-semibold">{money(r.client_usd)}</td>
                    <td className={`px-3 py-2.5 text-right font-bold ${Number(r.bill_usd) > 0 ? 'text-amber-400' : 'text-slate-500'}`}>
                      {money(r.bill_usd)}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {payload?.bill_art && (
        <p className="text-xs text-slate-500">
          Artículo LisArtC configurado: <span className="text-slate-300 font-mono">{payload.bill_art}</span>
          {payload?.credit_usd != null && <> · Crédito mensual: {money(payload.credit_usd)}</>}
          {payload?.model && <> · Modelo: {payload.model}</>}
        </p>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-2xl border border-white/5 bg-slate-900/50 px-4 py-3">
      <div className="text-[10px] uppercase tracking-widest text-slate-500 font-black">{label}</div>
      <div className={`text-xl font-black mt-1 ${accent ? 'text-amber-400' : 'text-white'}`}>{value}</div>
    </div>
  );
}
