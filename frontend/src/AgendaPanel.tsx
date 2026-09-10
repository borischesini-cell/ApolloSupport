import { useEffect, useMemo, useState } from 'react';
import {
  Video, Film, CalendarClock, Plus, Copy, Mail, Phone, Monitor,
  X, RefreshCw, ExternalLink, Play, Download, Trash2,
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
  type ScheduledMeeting,
  type ScheduledRecording,
} from './api';

type ClientLite = {
  id: number;
  razon_social: string;
  email?: string | null;
  telefono?: string | null;
  devices?: Array<{ id: number; device_name: string; assist_id?: string | null }>;
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
  onNotify?: (msg: string) => void;
};

type SubTab = 'meetings' | 'recordings' | 'library';

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

export default function AgendaPanel({ darkMode, clients, users, currentUserId, onNotify }: Props) {
  const [sub, setSub] = useState<SubTab>('meetings');
  const [meetings, setMeetings] = useState<ScheduledMeeting[]>([]);
  const [recordings, setRecordings] = useState<ScheduledRecording[]>([]);
  const [library, setLibrary] = useState<ScheduledRecording[]>([]);
  const [loading, setLoading] = useState(false);
  const [showMeetingForm, setShowMeetingForm] = useState(false);
  const [showRecordingForm, setShowRecordingForm] = useState(false);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [videoBlobUrl, setVideoBlobUrl] = useState<string | null>(null);

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
  });

  const selectedClientDevices = useMemo(() => {
    const c = clients.find(x => String(x.id) === rForm.client_id);
    return c?.devices || [];
  }, [clients, rForm.client_id]);

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
    try {
      await createAgendaRecording({
        client_id: Number(rForm.client_id),
        device_id: Number(rForm.device_id),
        technician_id: Number(rForm.technician_id),
        scheduled_at: localInputToIso(rForm.scheduled_at),
        duration_minutes: Number(rForm.duration_minutes) || 30,
        notes: rForm.notes || undefined,
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
                  <select
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                    value={mForm.client_id}
                    onChange={e => setMForm({ ...mForm, client_id: e.target.value })}
                  >
                    <option value="">Seleccionar…</option>
                    {clients.map(c => (
                      <option key={c.id} value={c.id}>{c.razon_social}</option>
                    ))}
                  </select>
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
              <div className="flex justify-between items-center">
                <h3 className="font-bold text-sm">Nueva grabación remota</h3>
                <button onClick={() => setShowRecordingForm(false)}><X size={16} /></button>
              </div>
              <div className="grid sm:grid-cols-2 gap-3">
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">Cliente</span>
                  <select
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                    value={rForm.client_id}
                    onChange={e => setRForm({ ...rForm, client_id: e.target.value, device_id: '' })}
                  >
                    <option value="">Seleccionar…</option>
                    {clients.map(c => (
                      <option key={c.id} value={c.id}>{c.razon_social}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs space-y-1">
                  <span className="text-slate-400 font-bold">PC / Device</span>
                  <select
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2"
                    value={rForm.device_id}
                    onChange={e => setRForm({ ...rForm, device_id: e.target.value })}
                  >
                    <option value="">Seleccionar…</option>
                    {selectedClientDevices.map(d => (
                      <option key={d.id} value={d.id}>{d.device_name} {d.assist_id ? `(${d.assist_id})` : ''}</option>
                    ))}
                  </select>
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
              <button
                onClick={handleCreateRecording}
                className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-bold"
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

