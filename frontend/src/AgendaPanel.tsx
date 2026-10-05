import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Video, Film, CalendarClock, Plus, Copy, Mail, Phone, Monitor,
  X, RefreshCw, ExternalLink, Play, Download, Trash2, Search,
} from 'lucide-react';
import {
  getAuthHeaders,
  listAgendaMeetings,
  createAgendaMeeting,
  cancelAgendaMeeting,
  shareAgendaMeeting,
  notifyAgendaMeeting,
  listAgendaRecordings,
  listAgendaRecordingLibrary,
  createAgendaRecording,
  cancelAgendaRecording,
  agendaRecordingDownloadUrl,
  fetchWindowsSessionsPolled,
  type ScheduledMeeting,
  type ScheduledRecording,
  type WindowsSessionInfo,
} from './api';
import { clientMatchesQuery, gescom7 } from './ClientSearchSelect';

type DeviceLite = {
  id: number;
  device_name: string;
  assist_id?: string | null;
  is_online?: boolean;
  last_seen?: string | null;
};

type ClientLite = {
  id: number;
  codigo?: string | null;
  razon_social: string;
  nombre_fantasia?: string | null;
  cclifac?: string | null;
  email?: string | null;
  telefono?: string | null;
  devices?: DeviceLite[];
};

type UserLite = {
  id: number;
  nombre?: string;
  full_name?: string;
  email?: string;
};

type Props = {
  darkMode?: boolean;
  clients: ClientLite[];
  users: UserLite[];
  currentUserId?: number | null;
  /** Device IDs currently connected via Centinela telemetry */
  onlineDeviceIds?: number[];
  onNotify?: (msg: string) => void;
};

type SubTab = 'meetings' | 'recordings' | 'library';

function clientCentinelaInfo(client: ClientLite, onlineSet: Set<number>) {
  const devices = client.devices || [];
  const online = devices.filter(d => onlineSet.has(d.id) || d.is_online).length;
  return {
    total: devices.length,
    online,
    hasCentinela: devices.length > 0,
  };
}

function ClientSearchSelect({
  clients,
  value,
  onChange,
  onlineSet,
  showCentinelaStatus = false,
  onlyWithCentinela = false,
}: {
  clients: ClientLite[];
  value: string;
  onChange: (clientId: string) => void;
  onlineSet: Set<number>;
  showCentinelaStatus?: boolean;
  onlyWithCentinela?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const wrapRef = useRef<HTMLDivElement>(null);

  const selected = clients.find(c => String(c.id) === value);

  useEffect(() => {
    if (selected) {
      setQuery(selected.razon_social);
    } else if (!value) {
      setQuery('');
    }
  }, [value, selected?.id, selected?.razon_social]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    let list = clients;
    if (onlyWithCentinela) {
      list = list.filter(c => (c.devices?.length || 0) > 0);
    }
    if (term) {
      list = list.filter(c => clientMatchesQuery(c, term));
    }
    // Prefer clients with Centinela / online first
    list = [...list].sort((a, b) => {
      const ia = clientCentinelaInfo(a, onlineSet);
      const ib = clientCentinelaInfo(b, onlineSet);
      if (ia.online !== ib.online) return ib.online - ia.online;
      if (ia.total !== ib.total) return ib.total - ia.total;
      return (a.razon_social || '').localeCompare(b.razon_social || '', 'es');
    });
    return term ? list.slice(0, 150) : list.slice(0, 40);
  }, [clients, query, onlineSet, onlyWithCentinela]);

  const statusBadgeFor = (c: ClientLite) => {
    const info = clientCentinelaInfo(c, onlineSet);
    if (!info.hasCentinela) {
      return (
        <span className="text-[9px] font-black uppercase tracking-wide px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/25">
          Sin Centinela
        </span>
      );
    }
    if (info.online > 0) {
      return (
        <span className="text-[9px] font-black uppercase tracking-wide px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/25">
          {info.online}/{info.total} en línea
        </span>
      );
    }
    return (
      <span className="text-[9px] font-black uppercase tracking-wide px-1.5 py-0.5 rounded bg-slate-500/20 text-slate-400 border border-slate-500/30">
        {info.total} PC · off
      </span>
    );
  };

  return (
    <div className="relative" ref={wrapRef}>
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
        <input
          className="w-full bg-slate-950 border border-white/10 rounded-xl pl-9 pr-8 py-2 text-xs"
          placeholder="Buscar cliente por nombre o código…"
          value={query}
          onFocus={() => setOpen(true)}
          onChange={e => {
            setQuery(e.target.value);
            setOpen(true);
            if (value) onChange('');
          }}
        />
        {(query || value) && (
          <button
            type="button"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
            onClick={() => {
              setQuery('');
              onChange('');
              setOpen(true);
            }}
            title="Limpiar"
          >
            <X size={14} />
          </button>
        )}
      </div>
      {selected && showCentinelaStatus && (
        <div className="mt-1.5 flex items-center gap-2">{statusBadgeFor(selected)}</div>
      )}
      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-56 overflow-y-auto rounded-xl border border-white/10 bg-slate-950 shadow-2xl">
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-[11px] text-slate-500 italic">
              {onlyWithCentinela ? 'Ningún cliente con Centinela coincide' : 'Sin coincidencias'}
            </div>
          ) : (
            filtered.map(c => (
              <button
                key={c.id}
                type="button"
                className={`w-full text-left px-3 py-2 text-xs hover:bg-brand-500/20 border-b border-white/5 last:border-0 ${
                  String(c.id) === value ? 'bg-brand-500/15 text-brand-300' : 'text-slate-200'
                }`}
                onClick={() => {
                  onChange(String(c.id));
                  setQuery(c.razon_social);
                  setOpen(false);
                }}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <span className="font-bold truncate block">{c.razon_social}</span>
                    {(c.codigo || c.cclifac) ? (
                      <span className="text-[10px] text-slate-500 font-mono">
                        {[c.codigo, gescom7(c.cclifac)].filter(Boolean).join(' · ')}
                      </span>
                    ) : null}
                  </div>
                  {showCentinelaStatus && statusBadgeFor(c)}
                </div>
              </button>
            ))
          )}
          {filtered.length >= 40 && (
            <div className="px-3 py-1.5 text-[10px] text-slate-500">Escribí más para acotar…</div>
          )}
        </div>
      )}
    </div>
  );
}


function fmtDate(iso?: string | null) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    scheduled: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    live: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    running: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    completed: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
    failed: 'bg-red-500/15 text-red-300 border-red-500/30',
    cancelled: 'bg-slate-700/40 text-slate-500 border-slate-600/40',
  };
  return map[status] || map.scheduled;
}

function toLocalInputValue(d: Date) {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localInputToIso(local: string) {
  const d = new Date(local);
  return d.toISOString();
}

export default function AgendaPanel({ darkMode, clients, users, currentUserId, onlineDeviceIds = [], onNotify }: Props) {
  const [sub, setSub] = useState<SubTab>('meetings');
  const [meetings, setMeetings] = useState<ScheduledMeeting[]>([]);
  const [recordings, setRecordings] = useState<ScheduledRecording[]>([]);
  const [library, setLibrary] = useState<ScheduledRecording[]>([]);
  const [loading, setLoading] = useState(false);
  const [showMeetingForm, setShowMeetingForm] = useState(false);
  const [showRecordingForm, setShowRecordingForm] = useState(false);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [videoBlobUrl, setVideoBlobUrl] = useState<string | null>(null);
  const [onlyWithCentinela, setOnlyWithCentinela] = useState(true);

  const onlineSet = useMemo(() => new Set(onlineDeviceIds), [onlineDeviceIds]);

  const [mForm, setMForm] = useState({
    client_id: '',
    title: 'Soporte Apollo',
    agenda: '',
    starts_at: toLocalInputValue(new Date(Date.now() + 60 * 60 * 1000)),
    duration_minutes: 30,
    notify_minutes_before: 15,
  });

  const [rForm, setRForm] = useState({
    client_id: '',
    device_id: '',
    technician_id: String(currentUserId || ''),
    scheduled_at: toLocalInputValue(new Date(Date.now() + 60 * 60 * 1000)),
    duration_minutes: 30,
    notes: '',
    windows_session_id: '',
  });

  const [winSessions, setWinSessions] = useState<WindowsSessionInfo[]>([]);
  const [winSessionsLoading, setWinSessionsLoading] = useState(false);

  const selectedClientDevices = useMemo(() => {
    const c = clients.find(x => String(x.id) === rForm.client_id);
    return c?.devices || [];
  }, [clients, rForm.client_id]);

  const selectedRecordingClient = useMemo(
    () => clients.find(x => String(x.id) === rForm.client_id),
    [clients, rForm.client_id]
  );

  const selectedDeviceOnline = useMemo(() => {
    if (!rForm.device_id) return false;
    const id = Number(rForm.device_id);
    const d = selectedClientDevices.find(x => x.id === id);
    return onlineSet.has(id) || !!d?.is_online;
  }, [rForm.device_id, selectedClientDevices, onlineSet]);

  useEffect(() => {
    let cancelled = false;
    const deviceId = Number(rForm.device_id);
    if (!rForm.device_id || !deviceId) {
      setWinSessions([]);
      setRForm(f => (f.windows_session_id ? { ...f, windows_session_id: '' } : f));
      return;
    }
    if (!selectedDeviceOnline) {
      setWinSessions([]);
      return;
    }
    (async () => {
      setWinSessionsLoading(true);
      try {
        const sessions = await fetchWindowsSessionsPolled(deviceId);
        if (cancelled) return;
        setWinSessions(sessions);
        const current = sessions.find(s => s.current) || sessions[0];
        if (current) {
          setRForm(f => ({ ...f, windows_session_id: String(current.id) }));
        }
      } catch {
        if (!cancelled) setWinSessions([]);
      } finally {
        if (!cancelled) setWinSessionsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [rForm.device_id, selectedDeviceOnline]);

  const windowsSessionLabel = (s: WindowsSessionInfo) => {
    const user = s.username || 'sin usuario';
    const name = s.name || `Sesión ${s.id}`;
    const state = s.state ? ` · ${s.state}` : '';
    const cur = s.current ? ' · actual' : '';
    return `${user} @ ${name} (ID ${s.id})${state}${cur}`;
  };

  const load = async () => {
    setLoading(true);
    try {
      if (sub === 'meetings') {
        setMeetings(await listAgendaMeetings());
      } else if (sub === 'recordings') {
        setRecordings(await listAgendaRecordings());
      } else {
        setLibrary(await listAgendaRecordingLibrary());
      }
    } catch (e: any) {
      onNotify?.(e?.message || 'Error al cargar agenda');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [sub]);

  useEffect(() => {
    if (currentUserId && !rForm.technician_id) {
      setRForm(f => ({ ...f, technician_id: String(currentUserId) }));
    }
  }, [currentUserId]);

  useEffect(() => {
    return () => {
      if (videoBlobUrl) URL.revokeObjectURL(videoBlobUrl);
    };
  }, [videoBlobUrl]);

  const copyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      onNotify?.('Copiado al portapapeles');
    } catch {
      onNotify?.('No se pudo copiar');
    }
  };

  const handleCreateMeeting = async () => {
    if (!mForm.client_id || !mForm.title || !mForm.starts_at) {
      onNotify?.('Completá cliente, título y fecha');
      return;
    }
    try {
      const client = clients.find(c => String(c.id) === mForm.client_id);
      await createAgendaMeeting({
        client_id: Number(mForm.client_id),
        title: mForm.title,
        agenda: mForm.agenda || undefined,
        starts_at: localInputToIso(mForm.starts_at),
        duration_minutes: Number(mForm.duration_minutes) || 30,
        notify_minutes_before: Number(mForm.notify_minutes_before) || 15,
        client_email: client?.email || undefined,
        client_phone: client?.telefono || undefined,
      });
      setShowMeetingForm(false);
      onNotify?.('Reunión creada');
      load();
    } catch (e: any) {
      onNotify?.(e?.message || 'Error al crear reunión');
    }
  };

  const handleCreateRecording = async () => {
    if (!rForm.client_id || !rForm.device_id || !rForm.technician_id || !rForm.scheduled_at) {
      onNotify?.('Completá cliente, PC, técnico y fecha');
      return;
    }
    if (!selectedClientDevices.length) {
      onNotify?.('Ese cliente no tiene Centinela registrado; no se puede grabar');
      return;
    }
    if (selectedDeviceOnline && winSessions.length > 0 && !rForm.windows_session_id) {
      onNotify?.('Elegí qué sesión de Windows grabar');
      return;
    }
    if (!selectedDeviceOnline) {
      const ok = window.confirm(
        'Esa PC está desconectada ahora. ¿Programar igual? (la grabación fallará si Centinela no está online a la hora acordada)'
      );
      if (!ok) return;
    }
    const sid = rForm.windows_session_id ? Number(rForm.windows_session_id) : undefined;
    const sess = winSessions.find(s => s.id === sid);
    try {
      await createAgendaRecording({
        client_id: Number(rForm.client_id),
        device_id: Number(rForm.device_id),
        technician_id: Number(rForm.technician_id),
        scheduled_at: localInputToIso(rForm.scheduled_at),
        duration_minutes: Number(rForm.duration_minutes) || 30,
        notes: rForm.notes || undefined,
        windows_session_id: sid,
        windows_session_label: sess ? windowsSessionLabel(sess) : undefined,
      });
      setShowRecordingForm(false);
      onNotify?.('Grabación programada');
      load();
    } catch (e: any) {
      onNotify?.(e?.message || 'Error al programar');
    }
  };

  const handleShare = async (id: number, mode: 'copy' | 'mail' | 'wa' | 'notify') => {
    try {
      if (mode === 'notify') {
        const res = await notifyAgendaMeeting(id);
        onNotify?.(
          `Aviso enviado${res.email_sent ? ' (mail)' : ''}${res.agent_notified ? ' (agente)' : ''}`
        );
        if (res.wa_url) window.open(res.wa_url, '_blank');
        return;
      }
      const share = await shareAgendaMeeting(id);
      if (mode === 'copy') await copyText(share.join_url);
      if (mode === 'mail' && share.mailto) window.location.href = share.mailto;
      if (mode === 'wa' && share.wa_url) window.open(share.wa_url, '_blank');
      if (mode === 'mail' && !share.mailto) onNotify?.('El cliente no tiene email');
      if (mode === 'wa' && !share.wa_url) onNotify?.('El cliente no tiene teléfono');
    } catch (e: any) {
      onNotify?.(e?.message || 'Error al compartir');
    }
  };

  const playRecording = async (id: number) => {
    try {
      if (videoBlobUrl) URL.revokeObjectURL(videoBlobUrl);
      const response = await fetch(agendaRecordingDownloadUrl(id), { headers: getAuthHeaders() });
      if (!response.ok) throw new Error('No se pudo descargar el video');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setVideoBlobUrl(url);
      setPlayingId(id);
    } catch (e: any) {
      onNotify?.(e?.message || 'Error al reproducir');
    }
  };

  const card = darkMode
    ? 'bg-slate-900/60 border-white/10'
    : 'bg-white border-slate-200';

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight">Agenda</h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-2">
            Videoconferencias Jitsi, grabaciones programadas y biblioteca de videos.
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold border border-white/10 bg-slate-800/50 hover:bg-slate-700 text-slate-300"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Actualizar
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {([
          ['meetings', 'Reuniones', Video],
          ['recordings', 'Grabaciones', CalendarClock],
          ['library', 'Biblioteca', Film],
        ] as const).map(([id, label, Icon]) => (
          <button
            key={id}
            onClick={() => setSub(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold border transition-all ${
              sub === id
                ? 'bg-brand-500 text-white border-brand-500 shadow-lg shadow-brand-500/20'
                : 'bg-slate-800/40 text-slate-400 border-white/10 hover:text-white'
            }`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* REUNIONES */}
      {sub === 'meetings' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setShowMeetingForm(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold"
            >
              <Plus size={14} /> Nueva reunión
            </button>
          </div>

          {showMeetingForm && (
            <div className={`p-5 rounded-2xl border ${card} space-y-3`}>
              <div className="flex justify-between items-center">
                <h3 className="font-bold text-sm">Programar videoconferencia</h3>
                <button onClick={() => setShowMeetingForm(false)}><X size={16} /></button>
              </div>
              <div className="grid sm:grid-cols-2 gap-3">
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">Cliente</span>
                  <ClientSearchSelect
                    clients={clients}
                    value={mForm.client_id}
                    onChange={id => setMForm({ ...mForm, client_id: id })}
                    onlineSet={onlineSet}
                    showCentinelaStatus
                  />
                </label>
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">Título</span>
                  <input
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                    value={mForm.title}
                    onChange={e => setMForm({ ...mForm, title: e.target.value })}
                  />
                </label>
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">Fecha y hora</span>
                  <input
                    type="datetime-local"
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                    value={mForm.starts_at}
                    onChange={e => setMForm({ ...mForm, starts_at: e.target.value })}
                  />
                </label>
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">Duración (min) / Alerta (min antes)</span>
                  <div className="flex gap-2">
                    <input
                      type="number"
                      className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                      value={mForm.duration_minutes}
                      onChange={e => setMForm({ ...mForm, duration_minutes: Number(e.target.value) })}
                    />
                    <input
                      type="number"
                      className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                      value={mForm.notify_minutes_before}
                      onChange={e => setMForm({ ...mForm, notify_minutes_before: Number(e.target.value) })}
                    />
                  </div>
                </label>
                <label className="text-xs space-y-1 sm:col-span-2">
                  <span className="text-slate-400 font-bold">Agenda / notas</span>
                  <textarea
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 min-h-[70px]"
                    value={mForm.agenda}
                    onChange={e => setMForm({ ...mForm, agenda: e.target.value })}
                  />
                </label>
              </div>
              <button
                onClick={handleCreateMeeting}
                className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-bold"
              >
                Crear sala Jitsi
              </button>
            </div>
          )}

          <div className="space-y-3">
            {meetings.length === 0 && !loading && (
              <p className="text-sm text-slate-500 italic text-center py-8">No hay reuniones agendadas.</p>
            )}
            {meetings.map(m => (
              <div key={m.id} className={`p-4 rounded-2xl border ${card}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-extrabold text-sm">{m.title}</h3>
                      <span className={`text-[9px] uppercase font-black px-2 py-0.5 rounded-full border ${statusBadge(m.status)}`}>
                        {m.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">{m.client_name} · {fmtDate(m.starts_at)} · {m.duration_minutes} min</p>
                    {m.agenda && <p className="text-[11px] text-slate-500">{m.agenda}</p>}
                    <a href={m.join_url} target="_blank" rel="noreferrer" className="text-[11px] text-sky-400 hover:underline break-all flex items-center gap-1">
                      <ExternalLink size={12} /> {m.join_url}
                    </a>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <button title="Copiar URL" onClick={() => handleShare(m.id, 'copy')} className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white"><Copy size={14} /></button>
                    <button title="Enviar por mail" onClick={() => handleShare(m.id, 'mail')} className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white"><Mail size={14} /></button>
                    <button title="WhatsApp" onClick={() => handleShare(m.id, 'wa')} className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500 hover:text-white"><Phone size={14} /></button>
                    <button title="Avisar mail + agente" onClick={() => handleShare(m.id, 'notify')} className="p-2 rounded-lg bg-sky-500/20 text-sky-400 hover:bg-sky-500 hover:text-white"><Monitor size={14} /></button>
                    {m.status !== 'cancelled' && m.status !== 'completed' && (
                      <button
                        title="Cancelar"
                        onClick={async () => {
                          if (!confirm('¿Cancelar reunión?')) return;
                          await cancelAgendaMeeting(m.id);
                          load();
                        }}
                        className="p-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* GRABACIONES PROGRAMADAS */}
      {sub === 'recordings' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setShowRecordingForm(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold"
            >
              <Plus size={14} /> Programar grabación
            </button>
          </div>

          {showRecordingForm && (
            <div className={`p-5 rounded-2xl border ${card} space-y-3`}>
              <div className="flex justify-between items-center gap-3 flex-wrap">
                <h3 className="font-bold text-sm">Nueva grabación remota</h3>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1.5 text-[10px] text-slate-400 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={onlyWithCentinela}
                      onChange={e => setOnlyWithCentinela(e.target.checked)}
                      className="rounded border-white/20"
                    />
                    Solo con Centinela
                  </label>
                  <button onClick={() => setShowRecordingForm(false)}><X size={16} /></button>
                </div>
              </div>
              <div className="grid sm:grid-cols-2 gap-3">
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">Cliente</span>
                  <ClientSearchSelect
                    clients={clients}
                    value={rForm.client_id}
                    onChange={id => setRForm({ ...rForm, client_id: id, device_id: '', windows_session_id: '' })}
                    onlineSet={onlineSet}
                    showCentinelaStatus
                    onlyWithCentinela={onlyWithCentinela}
                  />
                </label>
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">PC / Device</span>
                  <select
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                    value={rForm.device_id}
                    onChange={e => setRForm({ ...rForm, device_id: e.target.value, windows_session_id: '' })}
                    disabled={!rForm.client_id || selectedClientDevices.length === 0}
                  >
                    <option value="">
                      {!rForm.client_id
                        ? 'Elegí un cliente…'
                        : selectedClientDevices.length === 0
                          ? 'Sin PCs con Centinela'
                          : 'Seleccionar…'}
                    </option>
                    {selectedClientDevices.map(d => {
                      const online = onlineSet.has(d.id) || !!d.is_online;
                      return (
                        <option key={d.id} value={d.id}>
                          {online ? '● ' : '○ '}
                          {d.device_name}
                          {d.assist_id ? ` (${d.assist_id})` : ''}
                          {online ? ' — en línea' : ' — desconectado'}
                        </option>
                      );
                    })}
                  </select>
                  {rForm.device_id && (
                    <span className={`text-[10px] font-bold ${selectedDeviceOnline ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {selectedDeviceOnline
                        ? 'Centinela en línea ahora'
                        : 'Centinela desconectado ahora (podés programar igual)'}
                    </span>
                  )}
                </label>
                <label className="text-xs space-y-1 sm:col-span-2">
                  <span className="text-slate-400 font-bold flex items-center justify-between gap-2">
                    <span>Sesión Windows a grabar</span>
                    {rForm.device_id && selectedDeviceOnline && (
                      <button
                        type="button"
                        className="text-[10px] text-sky-400 hover:text-sky-300 font-bold"
                        onClick={async () => {
                          setWinSessionsLoading(true);
                          try {
                            const sessions = await fetchWindowsSessionsPolled(Number(rForm.device_id));
                            setWinSessions(sessions);
                            if (!rForm.windows_session_id && sessions[0]) {
                              setRForm(f => ({ ...f, windows_session_id: String(sessions[0].id) }));
                            }
                          } finally {
                            setWinSessionsLoading(false);
                          }
                        }}
                      >
                        {winSessionsLoading ? 'Consultando…' : 'Actualizar sesiones'}
                      </button>
                    )}
                  </span>
                  <select
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                    value={rForm.windows_session_id}
                    onChange={e => setRForm({ ...rForm, windows_session_id: e.target.value })}
                    disabled={!rForm.device_id || winSessionsLoading || (!winSessions.length && selectedDeviceOnline)}
                  >
                    {!rForm.device_id && <option value="">Elegí una PC primero…</option>}
                    {rForm.device_id && !selectedDeviceOnline && (
                      <option value="">PC offline — no se pueden listar sesiones ahora</option>
                    )}
                    {rForm.device_id && selectedDeviceOnline && winSessionsLoading && (
                      <option value="">Consultando sesiones en el servidor…</option>
                    )}
                    {rForm.device_id && selectedDeviceOnline && !winSessionsLoading && winSessions.length === 0 && (
                      <option value="">Sin sesiones reportadas (¿Centinela en Session 0?)</option>
                    )}
                    {winSessions.map(s => (
                      <option key={s.id} value={s.id}>
                        {windowsSessionLabel(s)}
                      </option>
                    ))}
                  </select>
                  <span className="text-[10px] text-slate-500">
                    En Terminal Server / RDS elegí el usuario cuyo escritorio querés grabar. Al iniciar, Centinela cambia a esa sesión.
                  </span>
                </label>
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">Técnico</span>
                  <select
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                    value={rForm.technician_id}
                    onChange={e => setRForm({ ...rForm, technician_id: e.target.value })}
                  >
                    <option value="">Seleccionar…</option>
                    {users.map(u => (
                      <option key={u.id} value={u.id}>{u.full_name || u.nombre || u.email}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">Fecha / duración (min)</span>
                  <div className="flex gap-2">
                    <input
                      type="datetime-local"
                      className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                      value={rForm.scheduled_at}
                      onChange={e => setRForm({ ...rForm, scheduled_at: e.target.value })}
                    />
                    <input
                      type="number"
                      className="w-24 bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                      value={rForm.duration_minutes}
                      onChange={e => setRForm({ ...rForm, duration_minutes: Number(e.target.value) })}
                    />
                  </div>
                </label>
                <label className="text-xs space-y-1 sm:col-span-2">
                  <span className="text-slate-400 font-bold">Notas</span>
                  <input
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                    value={rForm.notes}
                    onChange={e => setRForm({ ...rForm, notes: e.target.value })}
                    placeholder="Motivo / qué observar…"
                  />
                </label>
              </div>
              {selectedRecordingClient && selectedClientDevices.length === 0 && (
                <p className="text-[11px] text-red-400 font-semibold">
                  Este cliente no tiene Centinela registrado. No se puede programar una grabación remota.
                </p>
              )}
              <button
                onClick={handleCreateRecording}
                disabled={!rForm.client_id || selectedClientDevices.length === 0}
                className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold"
              >
                Guardar
              </button>
            </div>
          )}

          <div className="space-y-3">
            {recordings.length === 0 && !loading && (
              <p className="text-sm text-slate-500 italic text-center py-8">No hay grabaciones programadas.</p>
            )}
            {recordings.map(r => (
              <div key={r.id} className={`p-4 rounded-2xl border ${card}`}>
                <div className="flex flex-wrap justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-extrabold text-sm">{r.device_name || `Device #${r.device_id}`}</h3>
                      <span className={`text-[9px] uppercase font-black px-2 py-0.5 rounded-full border ${statusBadge(r.status)}`}>
                        {r.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      {r.client_name} · {fmtDate(r.scheduled_at)} · {r.duration_minutes} min · {r.technician_name}
                    </p>
                    {r.windows_session_label && (
                      <p className="text-[11px] text-sky-400/90 mt-1 font-semibold">
                        Sesión: {r.windows_session_label}
                      </p>
                    )}
                    {r.notes && <p className="text-[11px] text-slate-500 mt-1">{r.notes}</p>}
                    {r.error_message && <p className="text-[11px] text-red-400 mt-1">{r.error_message}</p>}
                  </div>
                  {r.status === 'scheduled' && (
                    <button
                      onClick={async () => {
                        if (!confirm('¿Cancelar grabación?')) return;
                        try {
                          await cancelAgendaRecording(r.id);
                          load();
                        } catch (e: any) {
                          onNotify?.(e?.message);
                        }
                      }}
                      className="p-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white h-fit"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* BIBLIOTECA */}
      {sub === 'library' && (
        <div className="space-y-4">
          {playingId && videoBlobUrl && (
            <div className={`p-4 rounded-2xl border ${card} space-y-3`}>
              <div className="flex justify-between items-center">
                <h3 className="font-bold text-sm">Reproduciendo #{playingId}</h3>
                <button
                  onClick={() => {
                    setPlayingId(null);
                    if (videoBlobUrl) URL.revokeObjectURL(videoBlobUrl);
                    setVideoBlobUrl(null);
                  }}
                >
                  <X size={16} />
                </button>
              </div>
              <video src={videoBlobUrl} controls className="w-full max-h-[480px] rounded-xl bg-black" />
            </div>
          )}

          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-3">Fecha / Hora</th>
                  <th className="px-4 py-3">Cliente</th>
                  <th className="px-4 py-3">PC</th>
                  <th className="px-4 py-3">Técnico</th>
                  <th className="px-4 py-3">Duración</th>
                  <th className="px-4 py-3">Estado</th>
                  <th className="px-4 py-3">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {library.length === 0 && !loading && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-slate-500 italic">
                      Sin videos todavía.
                    </td>
                  </tr>
                )}
                {library.map(r => (
                  <tr key={r.id} className="border-t border-white/5 hover:bg-white/5">
                    <td className="px-4 py-3 font-mono">{fmtDate(r.started_at || r.scheduled_at)}</td>
                    <td className="px-4 py-3 font-bold">{r.client_name || '—'}</td>
                    <td className="px-4 py-3">
                      {r.device_name}
                      {r.assist_id ? <span className="text-slate-500 ml-1">({r.assist_id})</span> : null}
                    </td>
                    <td className="px-4 py-3">{r.technician_name || '—'}</td>
                    <td className="px-4 py-3">
                      {r.duration_seconds != null
                        ? `${Math.round(r.duration_seconds / 60)} min`
                        : `${r.duration_minutes} min`}
                      {r.file_size ? (
                        <span className="text-slate-500 ml-1">
                          ({(r.file_size / (1024 * 1024)).toFixed(1)} MB)
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-[9px] uppercase font-black px-2 py-0.5 rounded-full border ${statusBadge(r.status)}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        {r.has_video && (
                          <>
                            <button
                              title="Reproducir"
                              onClick={() => playRecording(r.id)}
                              className="p-2 rounded-lg bg-brand-500/20 text-brand-400 hover:bg-brand-500 hover:text-white"
                            >
                              <Play size={14} />
                            </button>
                            <a
                              title="Descargar"
                              href={agendaRecordingDownloadUrl(r.id)}
                              onClick={async (e) => {
                                e.preventDefault();
                                const response = await fetch(agendaRecordingDownloadUrl(r.id), { headers: getAuthHeaders() });
                                const blob = await response.blob();
                                const url = URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = url;
                                a.download = `grabacion_${r.id}.mp4`;
                                a.click();
                                URL.revokeObjectURL(url);
                              }}
                              className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white"
                            >
                              <Download size={14} />
                            </a>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

