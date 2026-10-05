import { useEffect, useMemo, useState } from 'react';
import { searchClients } from './api';

export type ClientOption = {
  id: number | string;
  codigo?: string | null;
  razon_social?: string | null;
  nombre_fantasia?: string | null;
  cclifac?: string | null;
};

export function gescom7(code?: string | null): string {
  const raw = String(code || '').trim();
  if (!raw) return '';
  if (/^\d+$/.test(raw)) return raw.padStart(7, '0');
  return raw;
}

function digitsLoose(value?: string | null): string {
  return String(value || '').replace(/\D/g, '').replace(/^0+/, '') || '';
}

export function clientMatchesQuery(c: ClientOption, query: string): boolean {
  const parts = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!parts.length) return true;
  const fac = gescom7(c.cclifac);
  const cod = String(c.codigo || '').trim();
  const hay = [c.razon_social, c.nombre_fantasia, c.codigo, c.cclifac, fac]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  const facDigits = digitsLoose(c.cclifac);
  const codDigits = digitsLoose(c.codigo);
  return parts.every((part) => {
    if (hay.includes(part)) return true;
    const pDigits = digitsLoose(part);
    if (pDigits && (facDigits === pDigits || facDigits.endsWith(pDigits) || codDigits === pDigits || codDigits.endsWith(pDigits))) {
      return true;
    }
    return false;
  });
}

function labelOf(c: ClientOption): string {
  const lic = String(c.codigo || '').trim();
  const fac = gescom7(c.cclifac);
  const codes = [lic, fac].filter(Boolean).join(' · ');
  return `${codes ? `${codes} — ` : ''}${c.razon_social || 'Sin nombre'}`;
}

type Props = {
  clients: ClientOption[];
  valueId: string;
  onChange: (id: string, client?: ClientOption | null) => void;
  placeholder?: string;
  optionalLabel?: string;
  darkMode?: boolean;
};

export default function ClientSearchSelect({
  clients,
  valueId,
  onChange,
  placeholder = 'Buscar por nombre, código o GesCom (7 dígitos)…',
  optionalLabel,
  darkMode = true,
}: Props) {
  const selected = clients.find((c) => String(c.id) === String(valueId));
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [remoteHits, setRemoteHits] = useState<ClientOption[]>([]);
  const display = open ? query : (selected ? labelOf(selected) : query);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setRemoteHits([]);
      return;
    }
    let cancelled = false;
    const t = window.setTimeout(async () => {
      try {
        const rows = await searchClients(q, 80);
        if (!cancelled && Array.isArray(rows)) setRemoteHits(rows);
      } catch {
        if (!cancelled) setRemoteHits([]);
      }
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [query]);

  const merged = useMemo(() => {
    const byId = new Map<string, ClientOption>();
    for (const c of [...remoteHits, ...clients]) {
      if (c && c.id != null) byId.set(String(c.id), c);
    }
    return Array.from(byId.values());
  }, [clients, remoteHits]);

  const matched = useMemo(
    () => merged.filter((c) => clientMatchesQuery(c, query)),
    [merged, query],
  );
  const qParts = query.trim().split(/\s+/).filter(Boolean);
  const visible = qParts.length ? matched.slice(0, 150) : matched.slice(0, 40);

  return (
    <div className="relative">
      <input
        type="text"
        value={display}
        onChange={(e) => {
          setQuery(e.target.value);
          onChange('', null);
          setOpen(true);
        }}
        onFocus={() => {
          setQuery(selected ? '' : query);
          setOpen(true);
        }}
        placeholder={placeholder}
        autoComplete="off"
        className={`w-full p-2.5 rounded-xl border outline-none text-sm ${
          darkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-slate-50 border-slate-200'
        }`}
      />
      {selected && (
        <span className="absolute right-3 top-2.5 text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded-full">
          ✓ {gescom7(selected.cclifac) || selected.codigo || selected.id}
        </span>
      )}
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className={`absolute left-0 right-0 mt-1 max-h-56 overflow-y-auto rounded-xl border shadow-2xl z-20 divide-y ${
            darkMode ? 'bg-slate-800 border-white/10 divide-white/5' : 'bg-white border-slate-200 divide-slate-100'
          }`}>
            {optionalLabel && (
              <button
                type="button"
                className="w-full text-left p-3 text-xs font-semibold text-slate-400 hover:bg-violet-600 hover:text-white"
                onClick={() => {
                  onChange('', null);
                  setQuery('');
                  setOpen(false);
                }}
              >
                {optionalLabel}
              </button>
            )}
            {visible.map((c) => {
              const fac = gescom7(c.cclifac);
              return (
                <button
                  type="button"
                  key={String(c.id)}
                  className="w-full text-left p-3 text-xs font-semibold flex items-center justify-between gap-2 hover:bg-indigo-600 hover:text-white"
                  onClick={() => {
                    onChange(String(c.id), c);
                    setQuery(labelOf(c));
                    setOpen(false);
                  }}
                >
                  <span className="truncate">{c.razon_social}</span>
                  <span className="flex items-center gap-1 shrink-0">
                    {c.codigo ? (
                      <span className="text-[10px] bg-white/10 px-2 py-0.5 rounded font-bold" title="Código licencia / GesActi">
                        {c.codigo}
                      </span>
                    ) : null}
                    {fac ? (
                      <span className="text-[10px] bg-sky-500/15 text-sky-300 px-2 py-0.5 rounded font-mono font-bold" title="Código GesCom (CCLIFAC)">
                        {fac}
                      </span>
                    ) : (
                      <span className="text-[10px] text-slate-500">sin GesCom</span>
                    )}
                  </span>
                </button>
              );
            })}
            {matched.length === 0 && (
              <p className="p-4 text-xs text-slate-500 italic text-center">
                No se encontró. Probá nombre, código corto o GesCom de 7 dígitos (ej. 0001307).
              </p>
            )}
            {matched.length > visible.length && (
              <p className="p-2 text-[10px] text-slate-500 text-center">
                Escribí más para acotar · {matched.length} coincidencias
              </p>
            )}
            {!qParts.length && clients.length > visible.length && (
              <p className="p-2 text-[10px] text-slate-500 text-center">
                Escribí nombre o GesCom — hay {clients.length} clientes
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
