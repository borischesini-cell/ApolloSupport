import { useState, useEffect, useRef, useCallback } from 'react';
import { Ticket, Users, Settings, Bell, Search, Moon, Sun, Monitor, MessageSquare, X, LogOut, ArrowUpRight, Sparkles, FileText, Clipboard, Plus, Folder, Trash2, Menu, DollarSign, CheckCircle2, AlertCircle, Activity, UserPlus, Shield, Phone, MapPin, Mail, Lock, Key, Camera, Edit2, Maximize2, Minimize, Terminal, Smartphone, Power, Clock, CalendarDays, Unlock, RefreshCw, Video, CreditCard, Paperclip } from 'lucide-react';
import {
  API_URL, getTickets, getClients, createTicket, updateTicket, assignTicket, updateTicketStatus, createClient, updateClient,
  toggleClientStatus, getActiveCentinelas, forceCentinelaUpdate, releaseCentinelaSession, forceCentinelaRefresh,
  fetchAiAnalysis, getCentinelaFrame, fetchWindowsSessions,
  getCentinelaAlerts, runCentinelaCommand, sendCentinelaControl, getAreas,
  addIntervention, uploadFile, deleteCentinelaDevice, getCentinelaClipboard, pasteFilesToCentinela, getWebRtcIceServers,
  syncSaldosFromErp, updateCentinelaDeviceNotes, importTeamviewerCsv, getPendingCentinelas, assignCentinelaLicense,
  getUsers, createUser, updateUser, toggleUserStatus, updateUserStatus, logoutUser,
  getClientBalance, getClientExtracto, viewVoucherPdf, getClientLicFacturadas, getClientCbus,
  getActivationRequests, resolveActivationRequest, getPendingExtensions, approveExtension,
  getEstadosCuentaCorriente, createEstadoCuentaCorriente, updateEstadoCuentaCorriente,
  deleteEstadoCuentaCorriente, syncEstadosCuentaCorrienteFromErp,
  useViewerWebSocket, type ConnectionQuality, useHqViewerWebSocket,
  REMOTE_STREAM_WORKABLE_FPS, REMOTE_STREAM_COMFORTABLE_FPS, connectionQualityFromFps,
  getCentinelaLogs, clearCentinelaLogs, toggleAndroidDevice,
  getResellers, createReseller, updateReseller, deleteReseller,
} from './api';
import Login from './Login';
import CentinelaPublicPage from './CentinelaPublicPage';
import AgendaPanel from './AgendaPanel';
import ClientSearchSelect from './ClientSearchSelect';
import { APP_VERSION, APP_BUILD, APP_VERSION_TAG, APP_VERSION_LABEL } from './version';

const triggerPushNotification = (title: string, body: string, url: string = '/') => {
  if ('Notification' in window && Notification.permission === 'granted') {
    if (navigator.serviceWorker && navigator.serviceWorker.ready) {
      navigator.serviceWorker.ready.then(reg => {
        reg.showNotification(title, {
          body,
          icon: '/icon-192.png',
          badge: '/icon-192.png',
          vibrate: [200, 100, 200],
          data: { url }
        } as any);
      });
    } else {
      new Notification(title, {
        body,
        icon: '/icon-192.png'
      });
    }
  }
};

const stripRtf = (rtf: string): string => {
  if (!rtf) return "";
  let text = rtf;
  // Remove control words and parameters
  text = text.replace(/\\rtf1|\\ansi|\\ansicpg\d+|\\deff\d+|\\deflang\d+/g, "");
  // Remove font tables and color tables
  text = text.replace(/{\\fonttbl.*?}/g, "");
  // Remove stylesheet and colortbl
  text = text.replace(/{\\colortbl.*?}/g, "");
  text = text.replace(/{\\\*\\generator.*?}/g, "");
  // Remove standard RTF formatting tags
  text = text.replace(/\\par/g, "\n");
  text = text.replace(/\\tab/g, "    ");
  text = text.replace(/\\b\s|\\b0/g, "");
  text = text.replace(/\\i\s|\\i0/g, "");
  text = text.replace(/\\cf\d+/g, "");
  text = text.replace(/\\f\d+|\\fs\d+/g, "");
  // Decode hex characters e.g. \'f3 to characters
  text = text.replace(/\\\'([0-9a-f]{2})/gi, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
  // Strip any remaining curly braces
  text = text.replace(/{|}/g, "");
  return text.trim();
};

const ACTIVIDADES = [
  { key: 'Atención al Cliente', label: 'Atención al Cliente' },
  { key: 'Desarrollo', label: 'Desarrollo' },
  { key: 'Finanzas', label: 'Finanzas' },
  { key: 'Caja', label: 'Caja' },
] as const;

const userActivities = (u: any): string[] => {
  if (u?.departamento) {
    const names: string[] = [];
    for (const part of String(u.departamento).replace(/,/g, '/').split('/')) {
      const name = part.trim();
      if (name && !names.includes(name)) names.push(name);
    }
    if (names.length) return names;
  }
  const fromAreas: string[] = [];
  for (const area of u?.areas || []) {
    if (area?.nombre && !fromAreas.includes(area.nombre)) fromAreas.push(area.nombre);
  }
  return fromAreas;
};

const userInActivity = (u: any, name: string) =>
  userActivities(u).some((n) => n.toLowerCase() === name.toLowerCase());

const userInDesarrollo = (u: any) =>
  userInActivity(u, 'Desarrollo')
  || /desarroll|program/i.test(`${u?.rol || ''} ${userActivities(u).join(' ')} ${u?.departamento || ''}`);

const attachmentHref = (url?: string | null) => {
  if (!url) return '#';
  if (/^https?:\/\//i.test(url)) return url;
  const origin = API_URL.replace(/\/api\/?$/, '');
  return url.startsWith('/') ? `${origin}${url}` : `${origin}/api/temp/uploads/${url}`;
};

const attachmentDisplayName = (url?: string | null, fallback?: string) => {
  if (fallback) return fallback;
  if (!url) return 'archivo';
  const raw = decodeURIComponent(url.split('/').pop() || 'archivo');
  return raw.replace(/^\d+(\.\d+)?_/, '');
};

const adjuntoTipoFromFile = (file: File) => {
  if (file.type.startsWith('image/')) return 'imagen';
  if (file.type.startsWith('audio/')) return 'audio';
  if (file.type.startsWith('video/')) return 'video';
  return 'documento';
};

const activityBadgeClass = (name: string) => {
  if (/desarroll|program/i.test(name)) return 'border-violet-500/30 text-violet-400 bg-violet-500/5';
  if (/atenci/i.test(name)) return 'border-sky-500/30 text-sky-400 bg-sky-500/5';
  if (/caja/i.test(name)) return 'border-emerald-500/30 text-emerald-400 bg-emerald-500/5';
  return 'border-teal-500/30 text-teal-400 bg-teal-500/5';
};

const formatFechaLocal = (raw?: string | null) => {
  if (!raw) return null;
  const iso = String(raw).slice(0, 10);
  const parts = iso.split('-');
  if (parts.length === 3 && parts[0].length === 4) {
    return `${Number(parts[2])}/${Number(parts[1])}/${parts[0]}`;
  }
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return String(raw);
  return d.toLocaleDateString('es-AR');
};

const renderLastErpUpdate = (lastErpUpdateStr: string | null, telemetry: any) => {
  const rawVal = telemetry?.last_erp_update || lastErpUpdateStr;
  if (!rawVal) return null;
  
  try {
    const data = typeof rawVal === 'string' && rawVal.startsWith('{') ? JSON.parse(rawVal) : rawVal;
    if (data && data.status === 'success' && data.latest_record) {
      const rec = data.latest_record;
      const dateKeys = Object.keys(rec).filter(k => k.toLowerCase().includes('fecha') || k.toLowerCase().includes('date') || k.toLowerCase().includes('fec'));
      const dateVal = dateKeys.length > 0 ? rec[dateKeys[0]] : null;
      
      const hourKeys = Object.keys(rec).filter(k => k.toLowerCase().includes('hora') || k.toLowerCase().includes('time') || k.toLowerCase().includes('hor'));
      const hourVal = hourKeys.length > 0 ? rec[hourKeys[0]] : null;
      
      const verKeys = Object.keys(rec).filter(k => k.toLowerCase().includes('ver') || k.toLowerCase().includes('act') || k.toLowerCase().includes('det') || k.toLowerCase().includes('obs'));
      const verVal = verKeys.length > 0 ? rec[verKeys[0]] : null;

      if (dateVal) {
        let cleanDate = String(dateVal).trim();
        if (cleanDate.includes('-')) {
          const parts = cleanDate.split('T')[0].split('-');
          if (parts.length === 3) {
            cleanDate = `${parts[2]}/${parts[1]}/${parts[0]}`;
          }
        }
        
        return (
          <div className="mt-1.5 text-[9px] font-extrabold text-indigo-400 flex items-center gap-1.5 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 rounded-xl w-fit" title={`Ruta DBF: ${data.path || ''}`}>
            🔄 ERP Act.: <span className="text-white">{cleanDate}</span> {hourVal ? <span className="text-indigo-300 font-medium">({hourVal})</span> : null} {verVal ? <span className="text-indigo-300 font-medium">| {verVal}</span> : null}
          </div>
        );
      }
    }
  } catch (e) {
    return (
      <div className="mt-1.5 text-[9px] font-semibold text-slate-400 bg-slate-500/5 border border-slate-500/10 px-2.5 py-1 rounded-xl w-fit">
        🔄 ERP Act.: {String(rawVal)}
      </div>
    );
  }
  return null;
};

const parseInlineStyles = (text: string) => {
  let parts: any[] = [text];
  
  if (text.includes('**')) {
    const boldRegex = /\*\*(.*?)\*\*/g;
    let match;
    let lastIndex = 0;
    const newParts = [];
    
    while ((match = boldRegex.exec(text)) !== null) {
      const before = text.substring(lastIndex, match.index);
      if (before) newParts.push(before);
      newParts.push(<strong key={match.index} className="font-extrabold text-white">{match[1]}</strong>);
      lastIndex = boldRegex.lastIndex;
    }
    const after = text.substring(lastIndex);
    if (after) newParts.push(after);
    parts = newParts;
  }
  
  return parts.map((part, i) => {
    if (typeof part !== 'string') return part;
    if (part.includes('`')) {
      const codeRegex = /`(.*?)`/g;
      let match;
      let lastIndex = 0;
      const codeParts = [];
      while ((match = codeRegex.exec(part)) !== null) {
        const before = part.substring(lastIndex, match.index);
        if (before) codeParts.push(before);
        codeParts.push(<code key={match.index} className="px-1.5 py-0.5 rounded bg-black/40 text-rose-400 font-mono text-xs">{match[1]}</code>);
        lastIndex = codeRegex.lastIndex;
      }
      const after = part.substring(lastIndex);
      if (after) codeParts.push(after);
      return <span key={i}>{codeParts}</span>;
    }
    return <span key={i}>{part}</span>;
  });
};

const renderAiAnalysisText = (text: string) => {
  if (!text) return null;
  const lines = text.split('\n');
  return (
    <div className="space-y-3.5 text-sm leading-relaxed text-slate-300">
      {lines.map((line, idx) => {
        let cleanLine = line.trim();
        if (cleanLine.startsWith('###')) {
          return <h3 key={idx} className="text-lg font-black text-white mt-5 mb-2 border-b border-white/5 pb-1 flex items-center gap-2">{cleanLine.replace('###', '').trim()}</h3>;
        }
        if (cleanLine.startsWith('####')) {
          return <h4 key={idx} className="text-base font-extrabold text-indigo-400 mt-4 mb-1.5">{cleanLine.replace('####', '').trim()}</h4>;
        }
        if (cleanLine.startsWith('*') || cleanLine.startsWith('-')) {
          const itemText = cleanLine.substring(1).trim();
          return (
            <div key={idx} className="flex items-start gap-2 pl-3 py-0.5">
              <span className="text-indigo-500 mt-1.5 text-xs">●</span>
              <span className="flex-1">{parseInlineStyles(itemText)}</span>
            </div>
          );
        }
        if (cleanLine.startsWith('>')) {
          let alertContent = cleanLine.substring(1).trim();
          let alertType = 'note';
          if (alertContent.includes('[!WARNING]') || alertContent.includes('[!CAUTION]')) {
            alertType = 'warning';
            alertContent = alertContent.replace(/\[!(WARNING|CAUTION)\]/g, '').trim();
          } else if (alertContent.includes('[!NOTE]') || alertContent.includes('[!TIP]') || alertContent.includes('[!IMPORTANT]')) {
            alertType = 'note';
            alertContent = alertContent.replace(/\[!(NOTE|TIP|IMPORTANT)\]/g, '').trim();
          }
          const bgClass = alertType === 'warning' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-blue-500/10 border-blue-500/20 text-blue-400';
          return (
            <div key={idx} className={`p-4 rounded-2xl border text-xs font-semibold my-4 leading-relaxed ${bgClass}`}>
              {alertContent}
            </div>
          );
        }
        if (cleanLine === '') return <div key={idx} className="h-2" />;
        
        return <p key={idx} className="pl-1 text-slate-300">{parseInlineStyles(cleanLine)}</p>;
      })}
    </div>
  );
};

type StreamPreset = 'auto' | 'max' | 'balanced' | 'speed';

const STREAM_QUALITY_TIERS = [
  { max_width: 1024, webp_still: 54, webp_motion: 36 },
  { max_width: 1280, webp_still: 64, webp_motion: 44 },
  { max_width: 1920, webp_still: 80, webp_motion: 54 },
  { max_width: 0, webp_still: 90, webp_motion: 74 },
] as const;

function streamTierForManualPreset(p: Exclude<StreamPreset, 'auto'>): number {
  switch (p) {
    case 'speed': return 0;
    case 'balanced': return 2;
    case 'max': return 3;
  }
}

type ToastKind = 'success' | 'error' | 'info' | 'warning';

const TOAST_META: Record<ToastKind, { bar: string; border: string; ring: string; title: string }> = {
  success: { bar: 'bg-emerald-600', border: 'border-emerald-500', ring: 'ring-emerald-500/10', title: 'Listo' },
  error: { bar: 'bg-red-600', border: 'border-red-500', ring: 'ring-red-500/10', title: 'Error' },
  info: { bar: 'bg-indigo-600', border: 'border-indigo-500', ring: 'ring-indigo-500/10', title: 'Aviso' },
  warning: { bar: 'bg-amber-600', border: 'border-amber-500', ring: 'ring-amber-500/10', title: 'Atención' },
};

function formatAssistId(id: string | number | null | undefined): string {
  const s = String(id ?? '').trim();
  if (!s) return '';
  if (/^\d{6}$/.test(s)) return `${s.slice(0, 3)} ${s.slice(3)}`;
  return s;
}

/** ID que dicta ApolloSoporte (assist_id). No confundir con id interno de DB ni RustDesk. */
function deviceAssistLabel(dev: any): string {
  return formatAssistId(dev?.assist_id || '');
}

function parseUserAgentShort(ua: string): string {
  if (!ua?.trim()) return '';
  let browser = 'Navegador';
  if (/Edg\//i.test(ua)) browser = 'Edge';
  else if (/Chrome\//i.test(ua)) browser = 'Chrome';
  else if (/Firefox\//i.test(ua)) browser = 'Firefox';
  else if (/Safari\//i.test(ua) && !/Chrome/i.test(ua)) browser = 'Safari';
  let os = '';
  if (/Windows NT 10/i.test(ua)) os = 'Windows 10/11';
  else if (/Windows NT 6\.3/i.test(ua)) os = 'Windows 8.1';
  else if (/Windows/i.test(ua)) os = 'Windows';
  else if (/Android/i.test(ua)) os = 'Android';
  else if (/iPhone|iPad/i.test(ua)) os = 'iOS';
  else if (/Mac OS X/i.test(ua)) os = 'macOS';
  else if (/Linux/i.test(ua)) os = 'Linux';
  const ver = ua.match(/Chrome\/([\d.]+)/i)?.[1] || ua.match(/Firefox\/([\d.]+)/i)?.[1];
  const browserLabel = ver ? `${browser} ${ver.split('.')[0]}` : browser;
  return os ? `${browserLabel} · ${os}` : browserLabel;
}

function isLikelyUserAgent(text: string): boolean {
  return /Mozilla\/5\.0/i.test(text || '');
}

function androidDevicePrimaryLabel(dev: any): string {
  const user = (dev.usuario_asignado || '').trim();
  if (user) return user;
  const modelo = (dev.modelo || '').trim();
  if (dev.app === 'TCK' && isLikelyUserAgent(modelo)) return parseUserAgentShort(modelo);
  if (modelo && modelo.length <= 48 && !isLikelyUserAgent(modelo)) return modelo;
  const imei = (dev.imei_serial || '').trim();
  if (imei) return `HW ${imei}`;
  const aid = (dev.android_id || '').trim();
  if (aid) return `ID ${aid.length > 20 ? `${aid.slice(0, 20)}…` : aid}`;
  return dev.app_nombre || dev.app || 'Dispositivo';
}

function androidDeviceIdentityLines(dev: any): { label: string; value: string; mono?: boolean }[] {
  const lines: { label: string; value: string; mono?: boolean }[] = [];
  if (dev.id != null) lines.push({ label: 'Registro', value: `#${dev.id}`, mono: true });
  const serial = (dev.serial_gescom || '').trim();
  if (serial) lines.push({ label: 'Serial GesCom', value: serial, mono: true });
  const aid = (dev.android_id || '').trim();
  if (aid) lines.push({ label: 'Android / Nodo ID', value: aid, mono: true });
  const imei = (dev.imei_serial || '').trim();
  if (imei) lines.push({ label: 'IMEI / Serial HW', value: imei, mono: true });
  const tel = (dev.telefono || '').trim();
  if (tel) lines.push({ label: 'Teléfono', value: tel });
  const google = (dev.cuenta_google || '').trim();
  if (google) lines.push({ label: 'Cuenta Google', value: google });
  const user = (dev.usuario_asignado || '').trim();
  if (user) lines.push({ label: 'Usuario / Vendedor', value: user });
  const modelo = (dev.modelo || '').trim();
  if (modelo && (dev.app === 'TCK' || isLikelyUserAgent(modelo))) {
    lines.push({ label: 'User-Agent', value: modelo, mono: true });
  } else if (modelo) {
    lines.push({ label: 'Modelo / SO', value: modelo });
  }
  return lines;
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'));
  const [showCentinelaPublic, setShowCentinelaPublic] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      return (
        params.get('centinela') === '1' ||
        params.get('page') === 'centinela' ||
        window.location.hash.replace(/^#/, '') === 'centinela'
      );
    } catch {
      return false;
    }
  });
  const [userProfile, setUserProfile] = useState<any>(null);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, []);

  const [darkMode, setDarkMode] = useState(true);
  const [activeTab, setActiveTab] = useState('tickets');
  
  // === ESTADOS PARA BITÁCORA DE LOGS (TELEMETRÍA) ===
  const [telemetryLogs, setTelemetryLogs] = useState<any[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsAutoRefresh, setLogsAutoRefresh] = useState(true);
  const [logsFilterDevice, setLogsFilterDevice] = useState<string>('all');
  const [logsFilterLevel, setLogsFilterLevel] = useState<string>('all');
  const [logsFilterSource, setLogsFilterSource] = useState<string>('all');
  const [logsSearchTerm, setLogsSearchTerm] = useState('');

  // === ESTADOS PARA LOGS EN SOPORTE EN VIVO (STANDALONE) ===
  const [isDeviceLogsOpen, setIsDeviceLogsOpen] = useState(false);
  const [deviceLogs, setDeviceLogs] = useState<any[]>([]);
  const [deviceLogsLoading, setDeviceLogsLoading] = useState(false);

  const [globalSearchTerm, setGlobalSearchTerm] = useState('');
  const [licenses, setLicenses] = useState<any[]>([]);
  const [showLicenseModal, setShowLicenseModal] = useState(false);
  const [deviceNotesModal, setDeviceNotesModal] = useState<{ deviceId: number; name: string; notes: string } | null>(null);
  const [licClientId, setLicClientId] = useState<string>("");
  const [licMaxDevices, setLicMaxDevices] = useState<number>(5);
  const [licDurationDays, setLicDurationDays] = useState<number>(365);
  const [pendingDevices, setPendingDevices] = useState<any[]>([]);
  const [assignModal, setAssignModal] = useState<any | null>(null);
  const [assignClientId, setAssignClientId] = useState<string>("");

  const [tickets, setTickets] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [centinelas, setCentinelas] = useState<any>({});
  const centinelasRef = useRef(centinelas);
  centinelasRef.current = centinelas;
  const [loading, setLoading] = useState(true);

  // Estados Modal Crear
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newClientId, setNewClientId] = useState("");
  const [newSubject, setNewSubject] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPriority, setNewPriority] = useState("media");
  const [newOrigen, setNewOrigen] = useState<"cliente" | "interno">("cliente");
  const [newAssigneeId, setNewAssigneeId] = useState("");
  const [newPedidoFiles, setNewPedidoFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isEditingTicket, setIsEditingTicket] = useState(false);
  const [editSubject, setEditSubject] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editPriority, setEditPriority] = useState("media");
  const [editOrigen, setEditOrigen] = useState<"cliente" | "interno">("cliente");
  const [editClientId, setEditClientId] = useState("");
  const [isSavingTicketEdit, setIsSavingTicketEdit] = useState(false);

  // Estados Clientes
  const [isClientModalOpen, setIsClientModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<any>(null);
  
  // Integración ERP: Extracto de cuenta corriente
  const [showExtractoModal, setShowExtractoModal] = useState<{
    isOpen: boolean;
    client: any;
    data: any[];
    loading: boolean;
    desde: string;
    hasta: string;
  }>({
    isOpen: false,
    client: null,
    data: [],
    loading: false,
    desde: new Date(Date.now() - 150 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    hasta: new Date().toISOString().split('T')[0]
  });

  const handleOpenExtracto = async (client: any, customDesde?: string, customHasta?: string) => {
    const desdeVal = customDesde || showExtractoModal.desde;
    const hastaVal = customHasta || showExtractoModal.hasta;
    
    setShowExtractoModal(prev => ({
      ...prev,
      isOpen: true,
      client,
      data: [],
      loading: true,
      desde: desdeVal,
      hasta: hastaVal
    }));
    
    try {
      const desdeIso = new Date(desdeVal).toISOString();
      const hastaIso = new Date(hastaVal).toISOString();
      const res = await getClientExtracto(client.id, desdeIso, hastaIso);
      setShowExtractoModal(prev => ({
        ...prev,
        data: res.extracto || [],
        loading: false
      }));
    } catch (err: any) {
      alert(err.message || "Error consultando el extracto en el ERP.");
      setShowExtractoModal(prev => ({ ...prev, loading: false }));
    }
  };
  const [clientSearchTerm, setClientSearchTerm] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const [clientActiveTab, setClientActiveTab] = useState('basic');

  // === ESTADOS PARA LICENCIAS ERP (MYSQL) ===
  const [erpLicenses, setErpLicenses] = useState<any[]>([]);
  const [isErpLicensesLoading, setIsErpLicensesLoading] = useState(false);
  const [selectedErpSerial, setSelectedErpSerial] = useState<string | null>(null);
  const [erpTerminals, setErpTerminals] = useState<any[]>([]);
  const [isErpTerminalsLoading, setIsErpTerminalsLoading] = useState(false);
  const [erpTemplates, setErpTemplates] = useState<any[]>([]);
  const [showBannerConfigModal, setShowBannerConfigModal] = useState(false);
  const [bannerForm, setBannerForm] = useState({
    serial: '',
    client_codes: [] as string[],
    m_down: false,
    m_newdate: '',
    m_tipmsg: 1,
    m_showmode: '01',
    m_text: ''
  });
  const [showNewSerialForm, setShowNewSerialForm] = useState(false);
  const [licensePanelSummary, setLicensePanelSummary] = useState<Record<string, any>>({});
  const [selectedClientCodes, setSelectedClientCodes] = useState<string[]>([]);
  const [cartelFilter, setCartelFilter] = useState<string>('all'); // all | con | sin | tipmsg number
  const [estadoCtaFilter, setEstadoCtaFilter] = useState<string>('all'); // all | sin | codigo
  const [showAvisoPreview, setShowAvisoPreview] = useState(false);
  const [showAvisosCatalog, setShowAvisosCatalog] = useState(false);
  const [avisoEdit, setAvisoEdit] = useState({ m_num: 0, m_des: '', m_text: '' });
  const [estadosCta, setEstadosCta] = useState<any[]>([]);
  const [showEstadosCtaModal, setShowEstadosCtaModal] = useState(false);
  const [estadoCtaEdit, setEstadoCtaEdit] = useState<{ id?: number; codigo: string; descripcion: string; activo: boolean }>({
    codigo: '', descripcion: '', activo: true,
  });
  const [estadosCtaLoading, setEstadosCtaLoading] = useState(false);
  const [newSerialForm, setNewSerialForm] = useState({
    l_number: '',
    l_date: '',
    l_peri2016: 30,
    l_raso: '',
    l_nomfa: '',
    l_cuit: '',
    l_tele: '',
    l_locali: ''
  });
  const [erpModules, setErpModules] = useState<any[]>([]);
  const [serialAllModules, setSerialAllModules] = useState(false);
  const [serialModuleNums, setSerialModuleNums] = useState<string[]>([]);
  const [showReportsModal, setShowReportsModal] = useState(false);
  const [reportsSerial, setReportsSerial] = useState('');
  const [reportsFrom, setReportsFrom] = useState('');
  const [reportsTo, setReportsTo] = useState('');
  const [erpReports, setErpReports] = useState<any[]>([]);
  const [erpReportsLoading, setErpReportsLoading] = useState(false);
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);
  const [reportNodes, setReportNodes] = useState<any>(null);
  const [reportSystem, setReportSystem] = useState<any[]>([]);
  const [reportDetailTab, setReportDetailTab] = useState<'nodes' | 'system' | null>(null);

  // === ESTADOS PARA DISPOSITIVOS MÓVILES ANDROID (misi_licand) ===
  const [androidSummary, setAndroidSummary] = useState<any[]>([]);
  const [androidSummaryLoading, setAndroidSummaryLoading] = useState(false);
  const [androidSelectedClient, setAndroidSelectedClient] = useState<any | null>(null);
  const [androidClientDevices, setAndroidClientDevices] = useState<any[]>([]);
  const [androidClientDevicesLoading, setAndroidClientDevicesLoading] = useState(false);
  const [androidSearchTerm, setAndroidSearchTerm] = useState('');
  const [androidFilterApp, setAndroidFilterApp] = useState('all');
  const [androidFilterHabilitado, setAndroidFilterHabilitado] = useState('all');
  const [androidDeviceDetailModal, setAndroidDeviceDetailModal] = useState<any | null>(null);
  const [androidToggleConfirm, setAndroidToggleConfirm] = useState<{ dev: any; habilitado: boolean } | null>(null);
  const [androidToggleBusy, setAndroidToggleBusy] = useState(false);

  const [toast, setToast] = useState<{ message: string; kind: ToastKind } | null>(null);
  const toastTimerRef = useRef<number | null>(null);
  const showToast = useCallback((message: string, kind: ToastKind = 'info', autoHideMs = 4500) => {
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    setToast({ message, kind });
    if (autoHideMs > 0) {
      toastTimerRef.current = window.setTimeout(() => setToast(null), autoHideMs);
    }
  }, []);
  const setShowNotification = useCallback((message: string | null) => {
    if (message === null) setToast(null);
    else showToast(message, 'success');
  }, [showToast]);

  // Lic Facturadas (LisArtC)
  const [licFactModal, setLicFactModal] = useState<{
    isOpen: boolean;
    client: any;
    items: any[];
    loading: boolean;
  }>({ isOpen: false, client: null, items: [], loading: false });

  const [cbuModal, setCbuModal] = useState<{
    isOpen: boolean;
    client: any;
    items: any[];
    loading: boolean;
  }>({ isOpen: false, client: null, items: [], loading: false });

  // Activaciones pendientes / Extensiones OnLine
  const [actiRequests, setActiRequests] = useState<any[]>([]);
  const [actiRequestsLoading, setActiRequestsLoading] = useState(false);
  const [actiShowAll, setActiShowAll] = useState(false);
  const [extensiones, setExtensiones] = useState<any[]>([]);
  const [extensionesLoading, setExtensionesLoading] = useState(false);
  const [extShowAll, setExtShowAll] = useState(false);

  const loadAndroidSummary = async () => {
    setAndroidSummaryLoading(true);
    try {
      const token = localStorage.getItem('token');
      const resp = await fetch(`${API_URL}/android-devices/summary`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (resp.ok) {
        const data = await resp.json();
        setAndroidSummary(data);
      }
    } catch (e) {
      console.error('Error cargando resumen de dispositivos Android:', e);
    } finally {
      setAndroidSummaryLoading(false);
    }
  };

  const loadAndroidClientDevices = async (clientCode: string) => {
    setAndroidClientDevicesLoading(true);
    try {
      const token = localStorage.getItem('token');
      const resp = await fetch(`${API_URL}/android-devices/client/${clientCode}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (resp.ok) {
        const data = await resp.json();
        setAndroidClientDevices(data);
      }
    } catch (e) {
      console.error('Error cargando dispositivos del cliente:', e);
    } finally {
      setAndroidClientDevicesLoading(false);
    }
  };

  const handleToggleAndroidDevice = (dev: any, habilitado: boolean) => {
    setAndroidToggleConfirm({ dev, habilitado });
  };

  const executeAndroidDeviceToggle = async () => {
    if (!androidToggleConfirm || androidToggleBusy) return;
    const { dev, habilitado } = androidToggleConfirm;
    setAndroidToggleBusy(true);
    try {
      await toggleAndroidDevice(dev.id, habilitado);
      setAndroidDeviceDetailModal((prev: any) => prev && prev.id === dev.id ? { ...prev, habilitado } : prev);
      setAndroidClientDevices(prev => prev.map(d => d.id === dev.id ? { ...d, habilitado } : d));
      loadAndroidSummary();
      setAndroidToggleConfirm(null);
      showToast(
        habilitado ? 'Dispositivo activado correctamente.' : 'Dispositivo desactivado.',
        'success'
      );
    } catch (e: any) {
      showToast(e.message || 'No se pudo cambiar el estado del dispositivo.', 'error', 8000);
    } finally {
      setAndroidToggleBusy(false);
    }
  };

  const handleOpenCbus = async (client: any) => {
    if (!client?.cclifac && !client?.codigo) {
      showToast('Este cliente no tiene código ERP para buscar CBU.', 'warning');
      return;
    }
    setCbuModal({ isOpen: true, client, items: [], loading: true });
    try {
      const res = await getClientCbus(client.id);
      setCbuModal(prev => ({ ...prev, items: res.items || [], loading: false }));
    } catch (e: any) {
      setCbuModal(prev => ({ ...prev, loading: false }));
      alert(e.message || 'Error al consultar CBU');
    }
  };

  const handleOpenLicFacturadas = async (client: any) => {
    if (!client?.cclifac) {
      showToast('Este cliente no posee código de facturación (CCLIFAC) del ERP.', 'warning');
      return;
    }
    setLicFactModal({ isOpen: true, client, items: [], loading: true });
    try {
      const res = await getClientLicFacturadas(client.id);
      setLicFactModal(prev => ({ ...prev, items: res.items || [], loading: false }));
    } catch (e: any) {
      setLicFactModal(prev => ({ ...prev, loading: false }));
      alert(e.message || 'Error al consultar licencias facturadas');
    }
  };

  const loadActiRequests = async (showAll = actiShowAll) => {
    setActiRequestsLoading(true);
    try {
      const data = await getActivationRequests(!showAll);
      setActiRequests(Array.isArray(data) ? data : []);
    } catch (e: any) {
      console.error(e);
      alert(e.message || 'Error cargando activaciones pendientes');
    } finally {
      setActiRequestsLoading(false);
    }
  };

  const handleResolveActiRequest = async (req: any, state: string) => {
    let message: string | undefined;
    let new_date: string | undefined;
    if (state === '3') {
      const msg = window.prompt('Mensaje a mostrar al cliente:', req.r_message || '');
      if (msg === null) return;
      message = msg;
    }
    if (state === '4') {
      const d = window.prompt('Nueva fecha de expiración (YYYY-MM-DD):', new Date().toISOString().slice(0, 10));
      if (!d) return;
      new_date = d;
    }
    const labels: Record<string, string> = {
      '0': 'dejar pendiente',
      '1': 'activar',
      '2': 'denegar',
      '3': 'activar con mensaje',
      '4': 'activar con nueva fecha',
    };
    if (!window.confirm(`¿Confirma ${labels[state] || state} para serial ${req.r_number}?`)) return;
    try {
      await resolveActivationRequest(req.KeyID, { state, message, new_date });
      setShowNotification(`Solicitud ${req.KeyID}: ${labels[state] || state}`);
      setTimeout(() => setShowNotification(null), 3000);
      loadActiRequests();
    } catch (e: any) {
      alert(e.message || 'Error al resolver solicitud');
    }
  };

  const loadExtensiones = async (showAll = extShowAll) => {
    setExtensionesLoading(true);
    try {
      const data = await getPendingExtensions(!showAll);
      setExtensiones(Array.isArray(data) ? data : []);
    } catch (e: any) {
      console.error(e);
      alert(e.message || 'Error cargando extensiones');
    } finally {
      setExtensionesLoading(false);
    }
  };

  const handleApproveExtension = async (ext: any) => {
    const suggested = ext.suggested_newdate || '';
    const d = window.prompt('Nueva fecha de vencimiento (YYYY-MM-DD):', suggested);
    if (d === null) return;
    if (!window.confirm(`¿Generar extensión para ${ext.e_number} hasta ${d || suggested}?`)) return;
    try {
      await approveExtension(ext.KeyID, d || undefined);
      setShowNotification(`Extensión generada: ${ext.e_number}`);
      setTimeout(() => setShowNotification(null), 3000);
      loadExtensiones();
    } catch (e: any) {
      alert(e.message || 'Error al generar extensión');
    }
  };

  useEffect(() => {
    if (activeTab === 'android_devices') {
      loadAndroidSummary();
    }
    if (activeTab === 'acti_pending') {
      loadActiRequests();
    }
    if (activeTab === 'extensiones') {
      loadExtensiones();
    }
    if (activeTab === 'clients') {
      loadLicensePanelSummary();
      loadErpTemplates();
      loadErpModules();
      loadEstadosCta(false);
    }
  }, [activeTab]);

  const loadLicensePanelSummary = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/summary`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setLicensePanelSummary(data || {});
      }
    } catch (e) {
      console.error("Error loading license panel summary:", e);
    }
  };

  const loadErpTemplates = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/templates`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setErpTemplates(data);
      }
    } catch (e) {
      console.error("Error loading ERP templates:", e);
    }
  };

  const loadErpModules = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/modules`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setErpModules(data);
        return data;
      }
    } catch (e) {
      console.error("Error loading ERP modules:", e);
    }
    return [] as any[];
  };

  const suggestNextGesactiCode = async (version: string) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/clients/next-code?version=${encodeURIComponent(version || 'E')}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        if (data.codigo) setClientForm(prev => ({ ...prev, codigo: data.codigo, version_apollo: version }));
      }
    } catch (e) {
      console.error("Error suggesting client code:", e);
    }
  };

  const applySerialPreset = (preset: string) => {
    if (preset === 'TODOS') {
      setSerialAllModules(true);
      return;
    }
    setSerialAllModules(false);
    const key = ({
      E: 'm_erp', C: 'm_commerce', S: 'm_single', L: 'm_little', R: 'm_clock', P: 'm_pharmakos'
    } as Record<string, string>)[preset];
    if (!key) return;
    setSerialModuleNums(erpModules.filter((m: any) => m[key] && m.m_exe !== 'GESACTI').map((m: any) => m.m_num));
  };

  const handleGenerateGesactiSerial = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/generate-serial`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          client_code: /^\d+$/.test((clientForm.codigo || '').trim())
            ? (clientForm.codigo || '').trim().padStart(4, '0')
            : (clientForm.codigo || '').trim().toUpperCase(),
          expiry_date: newSerialForm.l_date,
          module_nums: serialModuleNums,
          all_modules: serialAllModules,
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'No se pudo generar el serial');
      setNewSerialForm(prev => ({ ...prev, l_number: data.l_number }));
      try { await navigator.clipboard.writeText(data.l_number); } catch (_) { /* ignore */ }
      setShowNotification(`Serial GesActi: ${data.l_number} (copiado al portapapeles)`);
      setTimeout(() => setShowNotification(null), 5000);
    } catch (e: any) {
      alert(e.message || 'Error al generar serial');
    }
  };

  const previewAvisoText = () => {
    const custom = (bannerForm.m_text || '').trim();
    if (custom) return custom;
    const tpl = erpTemplates.find((t: any) => Number(t.m_num ?? t.id) === Number(bannerForm.m_tipmsg));
    return ((tpl?.m_text || tpl?.text || '') as string).replace(/CRLF/g, '\n') || '(sin texto de cartel)';
  };

  const saveAvisoTemplate = async () => {
    if (!avisoEdit.m_num || !avisoEdit.m_des) {
      alert("Indicá número y nombre del cartel.");
      return;
    }
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/templates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(avisoEdit)
      });
      if (!response.ok) throw new Error('No se pudo guardar el cartel');
      await loadErpTemplates();
      setShowNotification("Cartel de aviso guardado en misi_messages.");
      setTimeout(() => setShowNotification(null), 3000);
      setAvisoEdit({ m_num: 0, m_des: '', m_text: '' });
    } catch (e: any) {
      alert(e.message || "Error al guardar cartel");
    }
  };

  const openReportsForSerial = (serial: string) => {
    const to = new Date();
    const from = new Date();
    from.setDate(from.getDate() - 90);
    const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    setReportsSerial(serial);
    setReportsFrom(fmt(from));
    setReportsTo(fmt(to));
    setErpReports([]);
    setSelectedReportId(null);
    setReportNodes(null);
    setReportSystem([]);
    setReportDetailTab(null);
    setShowReportsModal(true);
  };

  const loadErpReports = async () => {
    if (!reportsSerial) return;
    setErpReportsLoading(true);
    setSelectedReportId(null);
    setReportNodes(null);
    setReportSystem([]);
    setReportDetailTab(null);
    try {
      const token = localStorage.getItem('token');
      const q = new URLSearchParams();
      if (reportsFrom) q.set('date_from', reportsFrom);
      if (reportsTo) q.set('date_to', reportsTo);
      const response = await fetch(`${API_URL}/erp-licenses/reports/${encodeURIComponent(reportsSerial)}?${q}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) setErpReports(await response.json());
      else alert('No se pudieron cargar los reportes.');
    } catch (e) {
      alert('Error de comunicación al cargar reportes.');
    } finally {
      setErpReportsLoading(false);
    }
  };

  const loadReportNodes = async (reportId: number) => {
    setSelectedReportId(reportId);
    setReportDetailTab('nodes');
    setReportSystem([]);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/reports/${reportId}/nodes`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) setReportNodes(await response.json());
      else alert('No hay nodos para este reporte.');
    } catch (e) {
      alert('Error al cargar nodos del reporte.');
    }
  };

  const loadReportSystem = async (reportId: number) => {
    setSelectedReportId(reportId);
    setReportDetailTab('system');
    setReportNodes(null);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/reports/${reportId}/system`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) setReportSystem(await response.json());
      else alert('No hay datos System para este reporte.');
    } catch (e) {
      alert('Error al cargar System del reporte.');
    }
  };

  const loadErpLicenses = async (clientCode: string) => {
    setIsErpLicensesLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/client/${clientCode}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setErpLicenses(data);
        if (data.length > 0) {
          setSelectedErpSerial(data[0].l_number);
          loadErpTerminals(data[0].l_number);
        } else {
          setSelectedErpSerial(null);
          setErpTerminals([]);
        }
      }
    } catch (e) {
      console.error("Error loading ERP licenses:", e);
    } finally {
      setIsErpLicensesLoading(false);
    }
  };

  const loadErpTerminals = async (serial: string) => {
    setIsErpTerminalsLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/terminals/${serial}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setErpTerminals(data);
      }
    } catch (e) {
      console.error("Error loading ERP terminals:", e);
    } finally {
      setIsErpTerminalsLoading(false);
    }
  };

  const handleToggleErpLicense = async (serial: string, currentDesact: boolean) => {
    const action = currentDesact ? "activar" : "desactivar";
    if (!window.confirm(`¿Está seguro de que desea ${action} la licencia ${serial}?`)) return;
    
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/toggle/${serial}`, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ l_desact: !currentDesact })
      });
      if (response.ok) {
        setShowNotification(`Licencia ${serial} ha sido ${currentDesact ? 'activada' : 'desactivada'}.`);
        setTimeout(() => setShowNotification(null), 3000);
        loadErpLicenses(clientForm.codigo);
      } else {
        alert("Error al cambiar estado de la licencia.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const handleSaveBannerConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem('token');
      const isBulk = (bannerForm.client_codes || []).length > 0;
      const url = isBulk ? `${API_URL}/erp-licenses/management/bulk` : `${API_URL}/erp-licenses/management`;
      const response = await fetch(url, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(bannerForm)
      });
      if (response.ok) {
        const res = await response.json().catch(() => ({}));
        const extra = isBulk && res.aplicadas != null ? ` (${res.aplicadas} licencias)` : '';
        setShowNotification(`Configuración de cartel/bloqueo guardada${extra}.`);
        setTimeout(() => setShowNotification(null), 3000);
        setShowBannerConfigModal(false);
        setBannerForm(prev => ({ ...prev, client_codes: [] }));
        if (clientForm.codigo) loadErpLicenses(clientForm.codigo);
        loadLicensePanelSummary();
      } else {
        alert("Error al guardar la configuración.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const SHOWMODE_SECONDS: Record<string, number> = {
    '02': 5, '03': 15, '04': 30, '05': 180, '06': 60, '07': 120, '08': 240, '09': 300,
  };

  const formatShowmodeLabel = (code?: string | null) => {
    const c = String(code || '').trim().padStart(2, '0');
    if (!c || c === '00') return '';
    if (c === '01') return 'OK';
    const sec = SHOWMODE_SECONDS[c];
    return sec ? `${sec}s` : c;
  };

  const parseShowmodeInput = (raw: string): string | null => {
    const t = String(raw || '').trim().toLowerCase();
    if (!t || t === 'keep' || t === 'mantener' || t === 'm') return 'keep';
    if (t === '15' || t === '03') return '03';
    if (t === '30' || t === '04') return '04';
    if (t === '180' || t === '05') return '05';
    if (t === '01' || t === 'ok' || t === 'aceptar') return '01';
    if (/^\d{2}$/.test(t) && SHOWMODE_SECONDS[t] !== undefined) return t;
    return null;
  };

  const applyBulkCartelToMarked = async (m_tipmsg: number, m_text: string = '') => {
    if (selectedClientCodes.length === 0) {
      alert('Marcá al menos un cliente.');
      return;
    }
    const tpl = erpTemplates.find((t: any) => Number(t.m_num ?? t.id) === Number(m_tipmsg));
    const label = m_tipmsg <= 1
      ? 'quitar el cartel (sin aviso)'
      : `poner cartel ${m_tipmsg}${tpl ? ` — ${tpl.m_des || tpl.label}` : ''}`;

    // Demora: por defecto mantener 15/30/180 actuales para no pisarlos en cambios masivos
    let m_showmode: string = 'keep';
    if (m_tipmsg > 1) {
      const actuales = Array.from(new Set(
        selectedClientCodes.flatMap(code => {
          const s = licensePanelSummary[code] || {};
          return Array.isArray(s.showmodes) && s.showmodes.length ? s.showmodes : (s.m_showmode ? [s.m_showmode] : []);
        }).map((x: any) => formatShowmodeLabel(String(x))).filter(Boolean)
      ));
      const hint = actuales.length ? `\nDemoras actuales en marcados: ${actuales.join(', ')}` : '';
      const ans = window.prompt(
        `${label}\n\nDemora del cartel (Enter = MANTENER actual; no pisa 15/30/180):${hint}\n\nEscribí: keep | 15 | 30 | 180`,
        'keep'
      );
      if (ans === null) return;
      const parsed = parseShowmodeInput(ans);
      if (!parsed) {
        alert('Demora inválida. Usá keep, 15, 30 o 180.');
        return;
      }
      m_showmode = parsed;
    }

    if (!window.confirm(`¿${label} en las licencias activas de ${selectedClientCodes.length} cliente(s) marcado(s)?\nDemora: ${m_showmode === 'keep' ? 'mantener actual' : formatShowmodeLabel(m_showmode)}`)) return;
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/management/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          client_codes: selectedClientCodes,
          m_down: false,
          m_newdate: '',
          m_tipmsg,
          m_showmode,
          m_text: m_text || (m_tipmsg > 1 ? ((tpl?.m_text || tpl?.text || '') as string).replace(/CRLF/g, '\n') : ''),
        })
      });
      const res = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(res.detail || 'Error al aplicar carteles');
      setShowNotification(`Cartel aplicado a ${res.aplicadas ?? selectedClientCodes.length} licencia(s).`);
      setTimeout(() => setShowNotification(null), 3500);
      loadLicensePanelSummary();
    } catch (e: any) {
      alert(e.message || 'Error de comunicación.');
    }
  };

  const clientMatchesCartelFilter = (code4: string) => {
    if (cartelFilter === 'all') return true;
    const licSum = licensePanelSummary[code4] || {};
    if (cartelFilter === 'con') return !!licSum.cartel;
    if (cartelFilter === 'sin') return !licSum.cartel;
    const tip = Number(cartelFilter);
    if (!Number.isFinite(tip)) return true;
    const tips: number[] = Array.isArray(licSum.tipmsgs) && licSum.tipmsgs.length
      ? licSum.tipmsgs.map(Number)
      : [Number(licSum.m_tipmsg || 1)];
    return tips.includes(tip);
  };

  const normalizeEstadoCodigo = (cod?: string | null) => {
    const c = String(cod || '').trim().toUpperCase();
    if (!c) return '';
    if (/^\d+$/.test(c) && c.length < 5) return c.padStart(5, '0');
    return c;
  };

  const clientMatchesEstadoFilter = (c: any) => {
    if (estadoCtaFilter === 'all') return true;
    const cod = normalizeEstadoCodigo(c.clasificacion_codigo);
    if (estadoCtaFilter === 'sin') return !cod;
    return cod === estadoCtaFilter;
  };

  const loadEstadosCta = async (soloActivos = false) => {
    setEstadosCtaLoading(true);
    try {
      const data = await getEstadosCuentaCorriente(soloActivos);
      setEstadosCta(Array.isArray(data) ? data : []);
    } catch (e: any) {
      console.error(e);
    } finally {
      setEstadosCtaLoading(false);
    }
  };

  const handleSyncEstadosCtaErp = async () => {
    try {
      const res = await syncEstadosCuentaCorrienteFromErp();
      setShowNotification(`Estados ERP: +${res.inserted || 0} / upd ${res.updated || 0}`);
      setTimeout(() => setShowNotification(null), 3500);
      await loadEstadosCta(false);
      const refreshed = await getClients();
      setClients(refreshed);
    } catch (e: any) {
      alert(e.message || 'Error sincronizando estados');
    }
  };

  const handleSaveEstadoCta = async () => {
    try {
      if (estadoCtaEdit.id) {
        await updateEstadoCuentaCorriente(estadoCtaEdit.id, {
          descripcion: estadoCtaEdit.descripcion,
          activo: estadoCtaEdit.activo,
        });
      } else {
        if (!estadoCtaEdit.codigo.trim()) {
          alert('Indique el código del estado.');
          return;
        }
        await createEstadoCuentaCorriente({
          codigo: estadoCtaEdit.codigo,
          descripcion: estadoCtaEdit.descripcion,
          activo: estadoCtaEdit.activo,
        });
      }
      setEstadoCtaEdit({ codigo: '', descripcion: '', activo: true });
      await loadEstadosCta(false);
      setShowNotification('Estado de cuenta corriente guardado.');
      setTimeout(() => setShowNotification(null), 2500);
    } catch (e: any) {
      alert(e.message || 'Error al guardar');
    }
  };

  const handleDeleteEstadoCta = async (row: any) => {
    if (!window.confirm(`¿Eliminar / desactivar estado ${row.codigo}?`)) return;
    try {
      const res = await deleteEstadoCuentaCorriente(row.id);
      setShowNotification(res.message || `Estado ${row.codigo}: ${res.status}`);
      setTimeout(() => setShowNotification(null), 3000);
      await loadEstadosCta(false);
    } catch (e: any) {
      alert(e.message || 'Error al eliminar');
    }
  };

  const handleExtendErpLicense = async (serial: string, days: number, currentExpDate: string) => {
    const newDays = prompt("Ingrese los días permitidos para renovar (auto-extensión):", String(days));
    if (newDays === null) return;
    
    const parsedDays = parseInt(newDays);
    if (isNaN(parsedDays)) {
      alert("Por favor ingrese un número válido.");
      return;
    }

    const changeDate = window.confirm("¿Desea modificar también la fecha de vencimiento?");
    let newExpiryDate = null;
    if (changeDate) {
      const inputDate = prompt("Ingrese la nueva fecha de vencimiento (YYYY-MM-DD):", currentExpDate);
      if (inputDate) {
        newExpiryDate = inputDate;
      }
    }

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/extension/${serial}`, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ days: parsedDays, expiry_date: newExpiryDate })
      });
      if (response.ok) {
        setShowNotification("Licencia extendida/actualizada correctamente.");
        setTimeout(() => setShowNotification(null), 3000);
        loadErpLicenses(clientForm.codigo);
      } else {
        alert("Error al extender la licencia.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const handleDeactivateErpNode = async (terminal: any) => {
    if (!window.confirm(`¿Seguro que desea desactivar el nodo PC "${terminal.t_id}" para el usuario "${terminal.t_user}"? Esta acción impedirá que este equipo use la licencia.`)) return;

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/deactivate-node`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          serial: terminal.t_number,
          t_id_enc: terminal.t_id_enc,
          t_user_enc: terminal.t_user_enc,
          t_path_enc: terminal.t_path_enc
        })
      });
      if (response.ok) {
        setShowNotification(`El nodo "${terminal.t_id}" ha sido desactivado de forma permanente.`);
        setTimeout(() => setShowNotification(null), 3000);
        loadErpTerminals(terminal.t_number);
      } else {
        alert("Error al desactivar el nodo.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const handleCreateNewErpSerial = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/new-serial`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newSerialForm)
      });
      if (response.ok) {
        setShowNotification(`Serial ${newSerialForm.l_number} registrado con éxito.`);
        setTimeout(() => setShowNotification(null), 3000);
        setShowNewSerialForm(false);
        loadErpLicenses(clientForm.codigo);
      } else {
        const errData = await response.json();
        alert(errData.detail || "Error al crear el nuevo serial.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const [clientForm, setClientForm] = useState({
    codigo: '',
    razon_social: '',
    nombre_fantasia: '',
    identificador_fiscal: '',
    cparte: '',
    version_apollo: 'E',
    telefono: '',
    email: '',
    localidad: '',
    fecha_vencimiento: '',
    modulos: 'Base, Facturación',
    apikey_apollo: '',
    remote_password: '',
    saldo: 0.0,
    vendedor_codigo: '',
    vendedor_nombre: '',
    clasificacion_codigo: '',
    clasificacion_nombre: '',
    extracto: '',
    cclifac: '',
    fecha_ultimo_pago: '',
    activo: true,
    reseller_id: null as number | null,
  });

  useEffect(() => {
    if (clientActiveTab === 'erp_licensing' && clientForm.codigo) {
      loadErpLicenses(clientForm.codigo);
      loadErpTemplates();
    }
  }, [clientActiveTab, clientForm.codigo]);

  // Estados Modal Detalle + IA
  const [selectedTicket, setSelectedTicket] = useState<any>(null);
  const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [newMessage, setNewMessage] = useState("");

  // Alertas Proactivas
  const [activeAlerts, setActiveAlerts] = useState<any>({});
  const [nativeConnectionState, setNativeConnectionState] = useState<'idle' | 'connecting' | 'success' | 'error'>('idle');


  // Estados Centinela (Live View Multi-Sesión)
  const standaloneIdInit = new URLSearchParams(window.location.search).get('remote_device_id');
  const [activeSessions, setActiveSessions] = useState<any[]>(
    standaloneIdInit ? [{ id: parseInt(standaloneIdInit), device_name: "Cargando Terminal...", is_online: true }] : []
  );
  const [sessionFrames, setSessionFrames] = useState<Record<string, string>>({});
  const sessionFramesRef = useRef(sessionFrames);
  sessionFramesRef.current = sessionFrames;

  // ─── CALIDAD DE CONEXIÓN EN TIEMPO REAL ─────────────────────────────────
  // Mide FPS real y latencia de entrega de frames para mostrar al técnico
  const frameTimestampsRef = useRef<number[]>([]); // últimos timestamps de frames recibidos
  const [connectionFps, setConnectionFps] = useState<number>(0);
  const [connectionQuality, setConnectionQuality] = useState<ConnectionQuality>('disconnected');
  // wsViewerConnected: true cuando el WebSocket de video está activo (deshabilita el HTTP polling)
  const [wsViewerConnected, setWsViewerConnected] = useState<boolean>(false);
  // ───────────────────────────────────────────────────────────────────────────

  const [sessionCmds, setSessionCmds] = useState<Record<string, any>>({});
  const [sessionFiles, setSessionFiles] = useState<Record<string, any>>({});
  const [sessionChats, setSessionChats] = useState<Record<string, any[]>>({});
  const [chatVisibility, setChatVisibility] = useState<Record<string, boolean>>({});
  const [remoteClipboard, setRemoteClipboard] = useState<string>("");
  const lastRemoteClipFilesRef = useRef('');
  const [isDraggingFiles, setIsDraggingFiles] = useState(false);
  const [isControlEnabled, setIsControlEnabled] = useState<boolean>(true);
  const [isCapsLockActive, setIsCapsLockActive] = useState<boolean>(false);
  const [focusedSessionId, setFocusedSessionId] = useState<number | null>(null);
  type WinSession = { id: number; name: string; username: string; state: string; current: boolean };
  const [winSessions, setWinSessions] = useState<WinSession[]>([]);
  const [winSessionsByDevice, setWinSessionsByDevice] = useState<Record<number, WinSession[]>>({});
  const [sessionPickerDeviceId, setSessionPickerDeviceId] = useState<number | null>(null);
  const [sessionSwitchingDeviceId, setSessionSwitchingDeviceId] = useState<number | null>(null);
  const [loginDeviceId, setLoginDeviceId] = useState<number | null>(null);
  const [showSessionPicker, setShowSessionPicker] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [loginCreds, setLoginCreds] = useState({ username: localStorage.getItem('last_remote_username') || '', password: '', domain: localStorage.getItem('last_remote_domain') || '.' });
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [sessionSwitching, setSessionSwitching] = useState(false);
  const sessionSwitchingRef = useRef(false);
  sessionSwitchingRef.current = sessionSwitching;
  const [sessionSwitchError, setSessionSwitchError] = useState('');
  const pendingSwitchWindowsSessionRef = useRef<number | null>(null);

  // ─── MULTI-MONITOR ──────────────────────────────────────────────────────────
  // activeMonitor: monitor que el agente está capturando actualmente (1-based)
  // monitorCount: cantidad de monitores detectados en el PC remoto (viene de telemetría)
  const [activeMonitor, setActiveMonitor] = useState<number>(1);
  const [monitorCount, setMonitorCount] = useState<number>(1);

  // Cambiar monitor remotamente enviando set_monitor al agente
  const switchMonitor = async (sessionId: number, monitorIndex: number) => {
    setActiveMonitor(monitorIndex);
    await sendCentinelaControl(sessionId, { type: 'set_monitor', index: monitorIndex });
  };
  // ────────────────────────────────────────────────────────────────────────────

  // ─── FULLSCREEN REAL DEL VISOR REMOTO ───────────────────────────────────────
  // Cubre todo el monitor con SOLO la imagen remota + barra flotante auto-oculta
  const [isViewerFullscreen, setIsViewerFullscreen] = useState<boolean>(false);
  const [toolbarVisible, setToolbarVisible] = useState<boolean>(true);
  const toolbarTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const enterViewerFullscreen = async () => {
    setIsViewerFullscreen(true);
    setToolbarVisible(true);
    resetToolbarTimer();
    try {
      await document.documentElement.requestFullscreen();
      if ('keyboard' in navigator && (navigator as any).keyboard && (navigator as any).keyboard.lock) {
        await (navigator as any).keyboard.lock(['Escape']);
      }
    } catch (e) {
      console.warn("Fullscreen error", e);
    }
  };

  const exitViewerFullscreen = () => {
    setIsViewerFullscreen(false);
    if (toolbarTimerRef.current) clearTimeout(toolbarTimerRef.current);
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    }
    if ('keyboard' in navigator && (navigator as any).keyboard && (navigator as any).keyboard.unlock) {
      (navigator as any).keyboard.unlock();
    }
  };

  const resetToolbarTimer = () => {
    if (toolbarTimerRef.current) clearTimeout(toolbarTimerRef.current);
    setToolbarVisible(true);
    toolbarTimerRef.current = setTimeout(() => {
      setToolbarVisible(false);
    }, 3000); // Ocultar barra 3s después de la última acción del mouse
  };

  // Se eliminó el listener de Escape para permitir enviar ESC a la PC remota

  // Sincronizar si el usuario sale del fullscreen nativo del browser (F11 o barra del browser)
  useEffect(() => {
    const handleFsChange = () => {
      if (!document.fullscreenElement && isViewerFullscreen) {
        setIsViewerFullscreen(false);
      }
      // Forzar frame fresco en el agente tras cualquier cambio de fullscreen
      // (el viewport cambia de tamaño y el último frame queda "congelado")
      const _sid = new URLSearchParams(window.location.search).get('remote_device_id');
      const targetId = _sid ? parseInt(_sid) : focusedSessionId;
      if (targetId) {
        setTimeout(() => {
          sendCentinelaControl(targetId, { type: 'refresh_frame' });
        }, 200); // 200ms para que el browser termine la transición
      }

    };
    document.addEventListener('fullscreenchange', handleFsChange);
    return () => document.removeEventListener('fullscreenchange', handleFsChange);
  }, [isViewerFullscreen, focusedSessionId]);



  // ─── WEBSOCKET DE VIDEO (reemplaza HTTP polling para standalone) ───────────
  // Para el modo standalone (ventana de soporte individual), usamos WS push.
  // El hook maneja reconexión automática, ping y calidad en tiempo real.
  const standaloneDeviceId = standaloneIdInit ? parseInt(standaloneIdInit) : null;

  // ── LIVE VIDEO REF ─────────────────────────────────────────────────────────
  // Bypass React state para video en vivo: en lugar de setSessionFrames()
  // (que dispara un re-render completo en cada frame a 25 FPS), actualizamos
  // img.src directamente via DOM ref — 0ms de overhead React por frame.
  //
  // latestLiveFrameRef: guarda el último src para que si React re-renderiza
  //   por OTRA razón (ej: cambio de FPS indicator), el img no quede en blanco.
  //
  // ROLLBACK: cambiar applyFrame para que solo llame setSessionFrames(prev=>(...)
  //   y eliminar ref={setLiveImgRef} de los img tags.
  const liveCanvasRef       = useRef<HTMLCanvasElement | null>(null);
  const latestLiveFrameRef = useRef<string>('');   // último base64 para re-renders de React
  const rafIdRef         = useRef<number | null>(null);
  const hqStreamOnCanvasRef = useRef(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const webrtcVideoRef = useRef<HTMLVideoElement | null>(null);
  const webrtcPcRef = useRef<RTCPeerConnection | null>(null);
  const webrtcPendingIceRef = useRef<RTCIceCandidateInit[]>([]);
  const [webrtcState, setWebrtcState] = useState<'off' | 'connecting' | 'open' | 'failed'>('off');
  const hqBufferRef = useRef<Uint8Array>(new Uint8Array(0));
  const hqPendingChunksRef = useRef<ArrayBuffer[]>([]);
  const hqPendingWarnedRef = useRef(false);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const mseReadyRef = useRef(false);
  const mseAppendQueueRef = useRef<ArrayBuffer[]>([]);
  const logFrontendRef = useRef<(msg: string, level?: string) => void>(() => {});
  const feedHqChunkImplRef = useRef<(chunk: ArrayBuffer) => void>(() => {});
  const sendViewerCommandRef = useRef<(cmd: Record<string, unknown>) => void>(() => {});

  // Callback ref compartido
  const setLiveCanvasRef = (el: HTMLCanvasElement | null) => {
    liveCanvasRef.current = el;
  };

  const frameQueueRef = useRef<{src: string, delta?: import('./api').DeltaMeta}[]>([]);
  const isProcessingQueueRef = useRef(false);
  const remoteCanvasBaseReadyRef = useRef(false);

  const processFrameQueue = () => {
    if (isProcessingQueueRef.current || frameQueueRef.current.length === 0) return;
    isProcessingQueueRef.current = true;

    const frame = frameQueueRef.current.shift();
    if (!frame) {
      isProcessingQueueRef.current = false;
      return;
    }

    const img = new window.Image();
    img.src = frame.src;
    img.decode().then(() => {
      requestAnimationFrame(() => {
        const canvas = liveCanvasRef.current;
        if (canvas) {
          const ctx = canvas.getContext('2d', { alpha: false });
          if (ctx) {
            if (frame.delta) {
              if (!remoteCanvasBaseReadyRef.current) {
                isProcessingQueueRef.current = false;
                processFrameQueue();
                return;
              }
              const { x, y, w, h, fw, fh } = frame.delta;
              const fullW = fw || img.width;
              const fullH = fh || img.height;
              if (canvas.width !== fullW || canvas.height !== fullH) {
                isProcessingQueueRef.current = false;
                processFrameQueue();
                return;
              }
              ctx.drawImage(img, x, y, w, h);
            } else {
              canvas.width = img.width;
              canvas.height = img.height;
              ctx.drawImage(img, 0, 0);
              remoteCanvasBaseReadyRef.current = true;
            }
          }
        }
        isProcessingQueueRef.current = false;
        processFrameQueue();
      });
    }).catch((err) => {
      console.error(err);
      isProcessingQueueRef.current = false;
      processFrameQueue();
    });
  };

  const applyFrame = (src: string, delta?: import('./api').DeltaMeta) => {
    const devId = standaloneDeviceId ?? focusedSessionId ?? activeSessions[0]?.id;
    if (!devId) return;
    if (hqStreamOnCanvasRef.current) return;

    // Guardar siempre para que re-renders de React tengan el frame correcto
    latestLiveFrameRef.current = src;

    // Telemetría HTTP puede marcar offline durante switch de sesión; si hay frames, está online
    setActiveSessions(prev =>
      prev.map(s => (s.id === devId && !s.is_online ? { ...s, is_online: true } : s))
    );

    if (liveCanvasRef.current) {
      if (frameQueueRef.current.length >= 2) {
        frameQueueRef.current = [{ src, delta }];
      } else {
        frameQueueRef.current.push({ src, delta });
      }
      processFrameQueue();
    } else {
      // ── FALLBACK: img no montada aún (primera conexión) ─────────────────
      setSessionFrames(prev => ({ ...prev, [devId]: src }));
    }
  };

  const beginSessionSwitch = useCallback((deviceId: number, targetWindowsSessionId: number) => {
    pendingSwitchWindowsSessionRef.current = targetWindowsSessionId;
    setSessionSwitchError('');
    setSessionSwitching(true);
    setSessionSwitchingDeviceId(deviceId);
    hqStreamOnCanvasRef.current = false;
    frameQueueRef.current = [];
    remoteCanvasBaseReadyRef.current = false;
  }, []);

  const cancelSessionSwitch = useCallback(() => {
    pendingSwitchWindowsSessionRef.current = null;
    setSessionSwitching(false);
    setSessionSwitchingDeviceId(null);
    setSessionSwitchError('');
    setLoginLoading(false);
  }, []);
  // ── FIN LIVE VIDEO REF ─────────────────────────────────────────────────────



  const handleViewerMessage = useCallback((msg: Record<string, unknown>) => {
    const streamDev = standaloneDeviceId ?? focusedSessionId;
    if (msg.type === 'session_list') {
      type WS = { id: number; name: string; username: string; state: string; current: boolean; };
      const sessions = (msg.sessions as WS[]) ?? [];
      setWinSessions(sessions);
      if (streamDev) {
        setWinSessionsByDevice(prev => ({ ...prev, [streamDev]: sessions }));
      }
      const pending = pendingSwitchWindowsSessionRef.current;
      if (pending != null) {
        const current = sessions.find(s => s.current);
        if (current?.id === pending) {
          pendingSwitchWindowsSessionRef.current = null;
          setSessionSwitching(false);
          setSessionSwitchingDeviceId(null);
          setSessionSwitchError('');
        }
      } else {
        setSessionSwitching(false);
        if (streamDev) setSessionSwitchingDeviceId(null);
      }
    } else if (msg.type === 'session_switching') {
      setSessionSwitching(true);
      setSessionSwitchError('');
      const target = msg.target_session_id as number | undefined;
      if (target != null) pendingSwitchWindowsSessionRef.current = target;
      if (streamDev) setSessionSwitchingDeviceId(streamDev);
    } else if (msg.type === 'session_switched') {
      pendingSwitchWindowsSessionRef.current = null;
      setSessionSwitching(false);
      setSessionSwitchError('');
      if (streamDev) setSessionSwitchingDeviceId(null);
      const sid = msg.session_id as number;
      const patch = (list: WinSession[]) => list.map(s => ({ ...s, current: s.id === sid }));
      setWinSessions(patch);
      if (streamDev) {
        setWinSessionsByDevice(prev => ({
          ...prev,
          [streamDev]: patch(prev[streamDev] ?? []),
        }));
      }
      sendViewerCommandRef.current({ type: 'refresh_frame' });
      sendViewerCommandRef.current({ type: 'get_sessions' });
    } else if (msg.type === 'session_switch_failed') {
      pendingSwitchWindowsSessionRef.current = null;
      setSessionSwitching(false);
      setSessionSwitchingDeviceId(null);
      setSessionSwitchError((msg.error as string) ?? 'No se pudo cambiar de sesión');
      setLoginLoading(false);
    } else if (msg.type === 'login_result') {
      if (msg.success) {
        const sid = (msg.session_id as number) ?? pendingSwitchWindowsSessionRef.current;
        if (sid != null) pendingSwitchWindowsSessionRef.current = sid;
        setSessionSwitching(true);
        setSessionSwitchError('');
        if (streamDev) setSessionSwitchingDeviceId(streamDev);
        setShowLoginModal(false);
        setLoginDeviceId(null);
        setLoginLoading(false);
        sendViewerCommandRef.current({ type: 'refresh_frame' });
      } else {
        pendingSwitchWindowsSessionRef.current = null;
        setSessionSwitching(false);
        setLoginError((msg.error as string) ?? 'Credenciales inválidas');
        setLoginLoading(false);
      }
    } else if (msg.type === 'webrtc_answer' && webrtcPcRef.current) {
      const sdp = String(msg.sdp || '');
      if (sdp) {
        webrtcPcRef.current.setRemoteDescription({ type: 'answer', sdp }).then(() => {
          const pending = webrtcPendingIceRef.current;
          webrtcPendingIceRef.current = [];
          pending.forEach((c) => {
            webrtcPcRef.current?.addIceCandidate(c).catch(() => {});
          });
        }).catch((err) => {
          console.error('[WEBRTC] answer', err);
          setWebrtcState('failed');
        });
      }
    } else if (msg.type === 'webrtc_ice') {
      const cand = String(msg.candidate || '');
      if (!cand) return;
      const init: RTCIceCandidateInit = {
        candidate: cand,
        sdpMid: (msg.sdpMid as string) ?? undefined,
        sdpMLineIndex: msg.sdpMLineIndex == null ? undefined : Number(msg.sdpMLineIndex),
      };
      if (webrtcPcRef.current?.remoteDescription) {
        webrtcPcRef.current.addIceCandidate(init).catch(() => {});
      } else {
        webrtcPendingIceRef.current.push(init);
      }
    } else if (msg.type === 'webrtc_state') {
      const st = String(msg.state || '');
      if (st === 'open' || st === 'connected') {
        setWebrtcState('open');
        setShowNotification('Canal rápido conectado (P2P/UDP)');
        setTimeout(() => setShowNotification(null), 2500);
      } else if (st === 'failed' || st === 'disconnected') {
        setWebrtcState('failed');
      } else if (st === 'closed') {
        setWebrtcState('off');
      }
    } else if (msg.type === 'webrtc_error') {
      setWebrtcState('failed');
      setShowNotification(String(msg.message || 'Canal rápido no disponible'));
      setTimeout(() => setShowNotification(null), 4000);
    } else if (msg.type === 'hq_unavailable') {
      setHqEnabled(false);
      try {
        const key = (standaloneDeviceId ?? focusedSessionId)
          ? `hq_mode_${standaloneDeviceId ?? focusedSessionId}`
          : null;
        if (key) localStorage.setItem(key, '0');
      } catch { /* ignore */ }
      hqStreamOnCanvasRef.current = false;
      setHqState('off');
      setShowNotification(String(msg.message || 'HD no disponible en este equipo — calidad estándar'));
      setTimeout(() => setShowNotification(null), 4500);
      logFrontendRef.current(
        `[FRONTEND-HQ] Agente rechazo HD (${msg.reason || 'n/a'})`,
        'WARN',
      );
    } else if (msg.type === 'capture_warning') {
      const text = String(msg.message || 'Pantalla en negro — revisá si el Escritorio remoto está minimizado.');
      setCaptureWarning(text);
      setShowNotification(text);
      setTimeout(() => setShowNotification(null), 8000);
      logFrontendRef.current(`[FRONTEND-CAPTURA] ${msg.reason || 'warning'}: ${text}`, 'WARN');
    } else if (msg.type === 'capture_ok') {
      setCaptureWarning(null);
    } else if (msg.type === 'clipboard_sync') {
      const text = String(msg.text || '');
      if (text) {
        setRemoteClipboard(text);
        navigator.clipboard.writeText(text).catch(() => {});
      }
    } else if (msg.type === 'clipboard_files_set') {
      const count = Number(msg.count || 0);
      const ok = Boolean(msg.ok);
      setShowNotification(
        ok
          ? `${count} archivo(s) listos. Cerrá el menú y clic derecho → Pegar.`
          : 'No se pudo preparar el portapapeles del cliente.',
      );
      setTimeout(() => setShowNotification(null), 4500);
    } else if (msg.type === 'clipboard_files_ready') {
      const files = (msg.files as { name?: string; url: string }[]) || [];
      if (files.length) {
        const sig = files.map(f => f.url).join('|');
        if (sig !== lastRemoteClipFilesRef.current) {
          lastRemoteClipFilesRef.current = sig;
          const origin = API_URL.replace(/\/api\/?$/, '');
          files.forEach((f) => {
            const href = f.url.startsWith('http') ? f.url : `${origin}${f.url.startsWith('/') ? '' : '/'}${f.url}`;
            const a = document.createElement('a');
            a.href = href;
            a.download = f.name || 'archivo';
            document.body.appendChild(a);
            a.click();
            a.remove();
          });
          setShowNotification(`${files.length} archivo(s) copiados del cliente`);
          setTimeout(() => setShowNotification(null), 3500);
        }
      }
    }
  }, [standaloneDeviceId, focusedSessionId]);

  const { sendCommand: sendViewerCommand } = useViewerWebSocket({
    deviceId: standaloneDeviceId ?? focusedSessionId ?? (activeSessions.length === 1 ? activeSessions[0].id : null),
    enabled: isAuthenticated && (!!standaloneDeviceId || !!focusedSessionId || activeSessions.length === 1),
    onFrame: (src, delta) => {
      applyFrame(src, delta);
      setWsViewerConnected(true);
      const now = performance.now();
      frameTimestampsRef.current.push(now);
      const twoSecsAgo = now - 2000;
      frameTimestampsRef.current = frameTimestampsRef.current.filter(t => t > twoSecsAgo);
      const fps = Math.round(frameTimestampsRef.current.length / 2);
      setConnectionFps(fps);
      setConnectionQuality(connectionQualityFromFps(fps));
      if (sessionSwitchingRef.current && src) {
        pendingSwitchWindowsSessionRef.current = null;
        setSessionSwitching(false);
        setSessionSwitchingDeviceId(null);
        setSessionSwitchError('');
      }
    },
    onHqChunk: (chunk) => {
      setWsViewerConnected(true);
      setHqState('open');
      feedHqChunkImplRef.current(chunk);
    },
    onQuality: (fps, quality) => {
      setConnectionFps(fps);
      setConnectionQuality(quality);
    },
    onMessage: handleViewerMessage,
    onClose: () => {
      setWsViewerConnected(false);
      remoteCanvasBaseReadyRef.current = false;
      frameQueueRef.current = [];
    },
  });
  sendViewerCommandRef.current = sendViewerCommand;

  const sendRemoteControl = useCallback((deviceId: number, payload: Record<string, unknown>) => {
    const useWs = wsViewerConnected && (standaloneDeviceId === deviceId || focusedSessionId === deviceId);
    if (useWs) {
      sendViewerCommandRef.current(payload);
      return Promise.resolve();
    }
    return sendCentinelaControl(deviceId, payload);
  }, [wsViewerConnected, standaloneDeviceId, focusedSessionId]);

  const stopWebRtc = useCallback(() => {
    webrtcPendingIceRef.current = [];
    const pc = webrtcPcRef.current;
    webrtcPcRef.current = null;
    if (pc) {
      try { pc.close(); } catch { /* */ }
    }
    if (webrtcVideoRef.current) webrtcVideoRef.current.srcObject = null;
    sendViewerCommandRef.current({ type: 'webrtc_hangup' });
    setWebrtcState('off');
  }, []);

  const startWebRtc = useCallback(async () => {
    if (!wsViewerConnected) {
      setShowNotification('Sin conexión al visor.');
      setTimeout(() => setShowNotification(null), 2500);
      return;
    }
    stopWebRtc();
    setWebrtcState('connecting');
    setShowNotification('Abriendo canal rápido (P2P)…');
    try {
      const iceServers = await getWebRtcIceServers();
      const pc = new RTCPeerConnection({
        iceServers: iceServers.length ? iceServers : [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun.cloudflare.com:3478' },
        ],
      });
      webrtcPcRef.current = pc;
      pc.addTransceiver('video', { direction: 'recvonly' });
      pc.ontrack = (ev) => {
        const stream = ev.streams[0];
        if (webrtcVideoRef.current && stream) {
          webrtcVideoRef.current.srcObject = stream;
          webrtcVideoRef.current.play().catch(() => {});
        }
        setWebrtcState('open');
        setConnectionFps(20);
        setConnectionQuality('excellent');
        setShowNotification('Canal rápido conectado (P2P/UDP)');
        setTimeout(() => setShowNotification(null), 2500);
        sendViewerCommandRef.current({ type: 'stop_hq' });
      };
      pc.onicecandidate = (ev) => {
        if (!ev.candidate) return;
        sendViewerCommandRef.current({
          type: 'webrtc_ice',
          candidate: ev.candidate.candidate,
          sdpMid: ev.candidate.sdpMid,
          sdpMLineIndex: ev.candidate.sdpMLineIndex,
        });
      };
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
          // Cerrar peer y volver al stream normal (no dejar pantalla negra).
          stopWebRtc();
          setWebrtcState('failed');
          sendViewerCommandRef.current({ type: 'refresh_frame' });
          setShowNotification('Canal rápido falló. Volviendo a HD/WebP…');
          setTimeout(() => setShowNotification(null), 4000);
        }
      };
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      sendViewerCommandRef.current({
        type: 'webrtc_offer',
        sdp: offer.sdp,
        ice_servers: iceServers,
      });
      window.setTimeout(() => {
        if (webrtcPcRef.current === pc && webrtcVideoRef.current && !webrtcVideoRef.current.srcObject) {
          stopWebRtc();
          setWebrtcState('failed');
          sendViewerCommandRef.current({ type: 'refresh_frame' });
          setShowNotification('Canal rápido no contestó. Se sigue con HD/WebP (agente 3.3.4+).');
          setTimeout(() => setShowNotification(null), 5000);
        }
      }, 12000);
    } catch (err: any) {
      setWebrtcState('failed');
      setShowNotification(err?.message || 'No se pudo abrir el canal rápido');
      setTimeout(() => setShowNotification(null), 3500);
    }
  }, [stopWebRtc, wsViewerConnected]);

  const toggleWebRtc = useCallback(() => {
    if (webrtcState === 'open' || webrtcState === 'connecting') {
      stopWebRtc();
      return;
    }
    startWebRtc();
  }, [webrtcState, startWebRtc, stopWebRtc]);

  const agentSupportsPasteText = useCallback((deviceId: number) => {
    const telem = centinelasRef.current[deviceId] || centinelasRef.current[String(deviceId)];
    const ver = String(telem?.agent_version || '');
    return /^3\.2\.(?:[7-9]|\d{2,})/.test(ver) || /^3\.[3-9]/.test(ver) || /^[4-9]\./.test(ver);
  }, []);

  const pasteTextToRemote = useCallback(async (deviceId: number, text: string) => {
    if (!text) return;
    if (agentSupportsPasteText(deviceId)) {
      await sendRemoteControl(deviceId, { type: 'paste_text', text });
    } else {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/centinelas/devices/${deviceId}/clipboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ text }),
      });
      await new Promise(r => setTimeout(r, 250));
      await sendRemoteControl(deviceId, { type: 'key_press', key: 'ctrl+v' });
    }
    setShowNotification('Texto pegado en el cliente.');
    setTimeout(() => setShowNotification(null), 2000);
  }, [agentSupportsPasteText, sendRemoteControl]);

  const pasteFilesToRemote = useCallback(async (deviceId: number, fileList: File[] | FileList) => {
    const files = Array.from(fileList).filter(f => f && f.size >= 0).slice(0, 8);
    if (!files.length) return;
    const tooBig = files.find(f => f.size > 25 * 1024 * 1024);
    if (tooBig) {
      setShowNotification(`${tooBig.name} supera 25 MB`);
      setTimeout(() => setShowNotification(null), 3500);
      return;
    }
    setShowNotification(`Enviando ${files.length} archivo(s) al cliente...`);
    try {
      await pasteFilesToCentinela(deviceId, files);
      setShowNotification(`Preparando ${files.length} archivo(s) en el cliente...`);
    } catch (err: any) {
      setShowNotification(err?.message || 'No se pudieron enviar los archivos');
    }
    setTimeout(() => setShowNotification(null), 4500);
  }, []);

  const pullRemoteClipboardToLocal = useCallback(async (deviceId: number) => {
    try {
      const clip = await getCentinelaClipboard(deviceId);
      if (clip.files?.length) {
        const sig = clip.files.map(f => f.url).join('|');
        if (sig !== lastRemoteClipFilesRef.current) {
          lastRemoteClipFilesRef.current = sig;
          const origin = API_URL.replace(/\/api\/?$/, '');
          clip.files.forEach((f) => {
            const href = f.url.startsWith('http') ? f.url : `${origin}${f.url.startsWith('/') ? '' : '/'}${f.url}`;
            const a = document.createElement('a');
            a.href = href;
            a.download = f.name || 'archivo';
            document.body.appendChild(a);
            a.click();
            a.remove();
          });
          setShowNotification(`${clip.files.length} archivo(s) copiados del cliente`);
          setTimeout(() => setShowNotification(null), 3500);
        }
        return; // archivos tienen prioridad sobre texto residual
      }
      if (clip.text) {
        setRemoteClipboard(clip.text);
        try { await navigator.clipboard.writeText(clip.text); } catch { /* permiso clipboard */ }
      }
    } catch (err) {
      console.error('Error leyendo portapapeles remoto', err);
    }
  }, []);

  const lastMouseMoveAtRef = useRef(0);
  const mouseButtonsDownRef = useRef(0);

  const connectionFpsRef = useRef(0);
  useEffect(() => {
    connectionFpsRef.current = connectionFps;
  }, [connectionFps]);

  const viewerStreamDeviceId = standaloneDeviceId ?? focusedSessionId ?? (activeSessions.length === 1 ? activeSessions[0]?.id : null);
  const clipBridgeSeenRef = useRef(false);
  useEffect(() => {
    if (!viewerStreamDeviceId) {
      setClipBridgeOn(false);
      return;
    }
    let stopped = false;
    let lastSeq = -1;
    let busy = false;
    let failCount = 0;
    const MAX_FAILS = 3;
    const tick = async () => {
      if (stopped || busy) return;
      if (failCount >= MAX_FAILS) return;
      try {
        const res = await fetch('http://127.0.0.1:47915/clipboard', { cache: 'no-store' });
        if (!res.ok) {
          if (!stopped) setClipBridgeOn(false);
          failCount++;
          return;
        }
        failCount = 0;
        const data = await res.json();
        if (stopped) return;
        setClipBridgeOn(true);
        if (!clipBridgeSeenRef.current) {
          clipBridgeSeenRef.current = true;
          setShowNotification('Portapapeles de tu PC conectado. Ctrl+C en un archivo lo manda al cliente.');
          setTimeout(() => setShowNotification(null), 4000);
        }
        const seq = Number(data.seq || 0);
        const changedAt = Number(data.changed_at || 0) * 1000;
        const items = Array.isArray(data.files) ? data.files : [];
        const fresh = changedAt > 0 && Date.now() - changedAt < 20000;
        if (lastSeq < 0) {
          lastSeq = seq;
          if (!(fresh && items.length)) return;
        } else if (!items.length || seq === lastSeq) {
          lastSeq = seq;
          return;
        }
        lastSeq = seq;
        busy = true;
        const files: File[] = [];
        for (const item of items.slice(0, 8)) {
          const fr = await fetch(`http://127.0.0.1:47915/file?i=${item.index}`, { cache: 'no-store' });
          if (!fr.ok) continue;
          const blob = await fr.blob();
          files.push(new File([blob], item.name || 'archivo'));
        }
        if (!stopped && files.length) await pasteFilesToRemote(viewerStreamDeviceId, files);
      } catch {
        if (!stopped) setClipBridgeOn(false);
        failCount++;
      } finally {
        busy = false;
      }
    };
    const id = window.setInterval(tick, 1000);
    tick();
    return () => {
      stopped = true;
      window.clearInterval(id);
    };
  }, [viewerStreamDeviceId, pasteFilesToRemote]);
  useEffect(() => {
    return () => {
      const pc = webrtcPcRef.current;
      webrtcPcRef.current = null;
      if (pc) {
        try { pc.close(); } catch { /* */ }
      }
    };
  }, [viewerStreamDeviceId]);
  const streamPresetStorageKey = viewerStreamDeviceId != null ? `apollo_stream_preset_${viewerStreamDeviceId}` : null;
  const [streamPreset, setStreamPreset] = useState<StreamPreset>('auto');

  // ── ALTO RENDIMIENTO (HQ MODE) ──────────────────────────────────────────────
  const hqDeviceId = standaloneDeviceId ?? focusedSessionId ?? (activeSessions.length === 1 ? activeSessions[0]?.id : null);
  const hqStorageKey = hqDeviceId ? `hq_mode_${hqDeviceId}` : null;

  const [hqEnabled, setHqEnabled] = useState<boolean>(() => {
    if (!hqStorageKey) return false;
    const stored = localStorage.getItem(hqStorageKey);
    if (stored !== null) return stored === 'true';
    return false;
  });
  const [hqState, setHqState] = useState<'connecting' | 'open' | 'closed' | 'off'>(() => {
    if (!hqStorageKey) return 'off';
    const stored = localStorage.getItem(hqStorageKey);
    if (stored !== null) return stored === 'true' ? 'connecting' : 'off';
    return 'off';
  });
  const [hqReconnectAttempt, setHqReconnectAttempt] = useState(0);
  const [captureWarning, setCaptureWarning] = useState<string | null>(null);
  const [viewerToolsOpen, setViewerToolsOpen] = useState(false);
  const [clipBridgeOn, setClipBridgeOn] = useState(false);

  const destroyHqDecoders = useCallback(() => {
    if (mediaSourceRef.current && mediaSourceRef.current.readyState === 'open') {
      try { mediaSourceRef.current.endOfStream(); } catch { /* */ }
    }
    mediaSourceRef.current = null;
    sourceBufferRef.current = null;
    mseReadyRef.current = false;
    mseAppendQueueRef.current = [];
    hqBufferRef.current = new Uint8Array(0);
    hqPendingChunksRef.current = [];
    hqPendingWarnedRef.current = false;
  }, []);

  const MSE_CODEC_CANDIDATES = [
    'video/mp4; codecs="avc1.42E01E"',
    'video/mp4; codecs="avc1.42E00D"',
    'video/mp4; codecs="avc1.4D401E"',
    'video/mp4; codecs="avc1.64001E"',
    'video/mp4',
  ];

  const initMSE = useCallback(() => {
    if (!videoRef.current) {
      console.warn('[MSE] videoRef no disponible');
      return false;
    }
    if (!('MediaSource' in window)) {
      console.error('[MSE] MediaSource no soportado');
      logFrontendRef.current('[FRONTEND-MSE] MediaSource Extensions no soportado en este navegador', 'ERROR');
      return false;
    }

    let supportedCodec: string | null = null;
    for (const codec of MSE_CODEC_CANDIDATES) {
      try {
        if (MediaSource.isTypeSupported(codec)) {
          supportedCodec = codec;
          console.log(`[MSE] Codec soportado: ${codec}`);
          logFrontendRef.current(`[FRONTEND-MSE] Codec soportado: ${codec}`, 'INFO');
          break;
        }
      } catch (e) {
        console.warn(`[MSE] Error verificando codec ${codec}:`, e);
      }
    }

    if (!supportedCodec) {
      supportedCodec = MSE_CODEC_CANDIDATES[0];
      console.warn(`[MSE] Ningún codec verificado, usando: ${supportedCodec}`);
      logFrontendRef.current(`[FRONTEND-MSE] Ningún codec verificado, usando: ${supportedCodec}`, 'WARNING');
    }

    try {
      const ms = new MediaSource();
      videoRef.current.src = URL.createObjectURL(ms);
      mediaSourceRef.current = ms;

      ms.addEventListener('sourceopen', () => {
        console.log('[MSE] MediaSource abierto');
        logFrontendRef.current('[FRONTEND-MSE] MediaSource abierto', 'INFO');
        try {
          const sb = ms.addSourceBuffer(supportedCodec!);
          sb.mode = 'segments';
          sourceBufferRef.current = sb;
          mseReadyRef.current = true;
          console.log(`[MSE] SourceBuffer creado con: ${supportedCodec}`);
          logFrontendRef.current(`[FRONTEND-MSE] SourceBuffer creado con: ${supportedCodec}`, 'INFO');

          sb.addEventListener('updateend', () => {
            if (mseAppendQueueRef.current.length > 0 && !sb.updating) {
              try {
                sb.appendBuffer(mseAppendQueueRef.current.shift()!);
              } catch (e) {
                console.error('[MSE] Error en appendBuffer:', e);
                logFrontendRef.current(`[FRONTEND-MSE] Error en appendBuffer: ${e}`, 'ERROR');
              }
            }
          });

          sb.addEventListener('error', (e) => {
            console.error('[MSE] SourceBuffer error:', e);
            logFrontendRef.current('[FRONTEND-MSE] SourceBuffer error', 'ERROR');
          });

          sb.addEventListener('abort', () => {
            console.warn('[MSE] SourceBuffer abort');
            logFrontendRef.current('[FRONTEND-MSE] SourceBuffer abort', 'WARNING');
          });
        } catch (e) {
          console.error('[MSE] Error creando SourceBuffer:', e);
          logFrontendRef.current(`[FRONTEND-MSE] Error creando SourceBuffer: ${e}`, 'ERROR');
          mseReadyRef.current = false;
        }
      });

      ms.addEventListener('error', (e) => {
        console.error('[MSE] MediaSource error:', e);
        logFrontendRef.current('[FRONTEND-MSE] MediaSource error', 'ERROR');
        mseReadyRef.current = false;
      });

      ms.addEventListener('sourceclose', () => {
        console.warn('[MSE] MediaSource cerrado');
        logFrontendRef.current('[FRONTEND-MSE] MediaSource cerrado', 'WARNING');
        mseReadyRef.current = false;
      });

      return true;
    } catch (e) {
      console.error('[MSE] Error creando MediaSource:', e);
      logFrontendRef.current(`[FRONTEND-MSE] Error creando MediaSource: ${e}`, 'ERROR');
      return false;
    }
  }, []);

  const appendMseChunk = useCallback((arrayBuffer: ArrayBuffer) => {
    if (!sourceBufferRef.current || !mseReadyRef.current) {
      return;
    }

    try {
      if (sourceBufferRef.current.updating || mseAppendQueueRef.current.length > 0) {
        mseAppendQueueRef.current.push(arrayBuffer);
        if (mseAppendQueueRef.current.length > 50) {
          console.warn(`[MSE] Cola creciendo: ${mseAppendQueueRef.current.length}`);
          mseAppendQueueRef.current.shift();
        }
      } else {
        sourceBufferRef.current.appendBuffer(arrayBuffer);
      }
    } catch (e: any) {
      console.error('[MSE] Error en appendMseChunk:', e);
      if (e.name === 'QuotaExceededError') {
        console.warn('[MSE] Buffer lleno, limpiando...');
        logFrontendRef.current('[FRONTEND-MSE] Buffer lleno, limpiando...', 'WARNING');
        try {
          if (sourceBufferRef.current.buffered.length > 0) {
            const start = sourceBufferRef.current.buffered.start(0);
            const end = sourceBufferRef.current.buffered.end(sourceBufferRef.current.buffered.length - 1);
            const removeEnd = start + (end - start) / 2;
            sourceBufferRef.current.remove(start, removeEnd);
            console.log(`[MSE] Buffer limpiado: ${start.toFixed(2)}s a ${removeEnd.toFixed(2)}s`);
          }
        } catch (e2) {
          console.error('[MSE] Error limpiando buffer:', e2);
        }
      }
    }
  }, []);

  const flushHqPendingChunks = useCallback(() => {
    const pending = hqPendingChunksRef.current;
    if (pending.length === 0) return;
    hqPendingChunksRef.current = [];
    hqPendingWarnedRef.current = false;
    for (const chunk of pending) {
      appendMseChunk(chunk);
    }
  }, [appendMseChunk]);

  feedHqChunkImplRef.current = (chunk: ArrayBuffer) => {
    if (mseReadyRef.current && sourceBufferRef.current) {
      appendMseChunk(chunk);
      return;
    }
    hqPendingChunksRef.current.push(chunk);
    if (hqPendingChunksRef.current.length > 300) hqPendingChunksRef.current.shift();
    if (!hqPendingWarnedRef.current) {
      hqPendingWarnedRef.current = true;
      logFrontendRef.current('[FRONTEND-HQ] Chunks fMP4 en cola (MSE no listo aún)', 'WARNING');
    }
  };

  useEffect(() => {
    const useHqVideo = hqEnabled && hqState === 'open' && mseReadyRef.current;
    hqStreamOnCanvasRef.current = useHqVideo;
    if (useHqVideo) {
      frameQueueRef.current = [];
      isProcessingQueueRef.current = false;
    }
  }, [hqEnabled, hqState]);

  // HD activo pero sin chunks: volver a WebP para no dejar pantalla negra
  useEffect(() => {
    if (!hqEnabled || !wsViewerConnected || hqState === 'open' || webrtcState === 'open') return;
    const timer = window.setTimeout(() => {
      if (!hqEnabled) return;
      if (connectionFpsRef.current > 0) return;
      logFrontendRef.current(
        '[FRONTEND-HQ] Sin video HD en 12s — fallback a calidad estándar',
        'WARNING',
      );
      setHqEnabled(false);
      setHqState('off');
      hqStreamOnCanvasRef.current = false;
      if (hqStorageKey) localStorage.setItem(hqStorageKey, 'false');
      destroyHqDecoders();
      sendViewerCommandRef.current({ type: 'stop_hq' });
      sendViewerCommandRef.current({ type: 'refresh_frame' });
    }, 5000);
    return () => window.clearTimeout(timer);
  }, [hqEnabled, hqState, wsViewerConnected, hqStorageKey, destroyHqDecoders, webrtcState]);

  useEffect(() => {
    if (!hqEnabled) {
      destroyHqDecoders();
      return;
    }
    if (hqState === 'open' && videoRef.current && !mediaSourceRef.current) {
      if (initMSE()) {
        logFrontendRef.current('[FRONTEND-MSE] Decodificador fMP4/MSE activo', 'INFO');
        logFrontendRef.current(`[VERSION] Portal ${APP_VERSION_LABEL} build ${APP_BUILD}`, 'INFO');
        videoRef.current.play().catch(() => {});
        flushHqPendingChunks();
      } else {
        logFrontendRef.current('[FRONTEND-MSE] Error inicializando MSE, volviendo a modo estándar', 'ERROR');
        setHqEnabled(false);
        setHqState('off');
        if (hqStorageKey) localStorage.setItem(hqStorageKey, 'false');
        sendViewerCommandRef.current({ type: 'stop_hq' });
        sendViewerCommandRef.current({ type: 'refresh_frame' });
        setShowNotification('HD no soportado en este navegador — volviendo a modo normal');
        setTimeout(() => setShowNotification(null), 4000);
      }
    }
  }, [hqEnabled, hqState, destroyHqDecoders, flushHqPendingChunks, initMSE, hqStorageKey]);

  // Al cambiar de sesión Windows: apagar HQ y pedir frames WebP (evita canvas negro)
  useEffect(() => {
    if (!sessionSwitching) return;
    hqStreamOnCanvasRef.current = false;
    destroyHqDecoders();
    if (hqEnabled) {
      sendViewerCommand({ type: 'stop_hq' });
      setHqEnabled(false);
      setHqState('off');
      if (hqStorageKey) localStorage.setItem(hqStorageKey, 'false');
    }
    sendViewerCommand({ type: 'refresh_frame' });
    const tick = window.setInterval(() => {
      sendViewerCommandRef.current({ type: 'refresh_frame' });
      sendViewerCommandRef.current({ type: 'get_sessions' });
    }, 1500);
    return () => window.clearInterval(tick);
  }, [sessionSwitching, hqEnabled, hqStorageKey, sendViewerCommand]);
  // ────────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!streamPresetStorageKey) return;
    const v = localStorage.getItem(streamPresetStorageKey);
    if (v === 'auto' || v === 'max' || v === 'balanced' || v === 'speed') setStreamPreset(v);
  }, [streamPresetStorageKey]);

  useEffect(() => {
    if (!streamPresetStorageKey) return;
    localStorage.setItem(streamPresetStorageKey, streamPreset);
  }, [streamPreset, streamPresetStorageKey]);

  const streamAutoTierRef = useRef(3);
  const streamLowFpsStreakRef = useRef(0);
  const streamHighFpsStreakRef = useRef(0);

  const sendStreamTier = useCallback(
    (tierIdx: number) => {
      const t = STREAM_QUALITY_TIERS[Math.max(0, Math.min(3, tierIdx))];
      sendViewerCommand({
        type: 'set_stream_params',
        max_width: t.max_width,
        webp_still: t.webp_still,
        webp_motion: t.webp_motion,
      });
    },
    [sendViewerCommand],
  );

  useEffect(() => {
    if (!wsViewerConnected || !viewerStreamDeviceId) return;
    if (streamPreset !== 'auto') {
      const idx = streamTierForManualPreset(streamPreset);
      streamAutoTierRef.current = idx;
      sendStreamTier(idx);
    }
  }, [wsViewerConnected, viewerStreamDeviceId, streamPreset, sendStreamTier]);

  useEffect(() => {
    if (!wsViewerConnected || !viewerStreamDeviceId || streamPreset !== 'auto' || hqEnabled) return;
    // Arrancar siempre en calidad máxima y NO bajar nunca automáticamente.
    // El autoajuste agresivo causaba set_stream_params constantes que interrumpían el flujo.
    streamAutoTierRef.current = 3;
    streamLowFpsStreakRef.current = 0;
    streamHighFpsStreakRef.current = 0;
    sendStreamTier(3);
    // No hay intervalo de ajuste automático — el usuario puede cambiar manualmente con el selector.
  }, [wsViewerConnected, viewerStreamDeviceId, streamPreset, hqEnabled, sendStreamTier]);

  /* Stream quality selector (compact, reused in header + fullscreen bar) */
  const streamQualitySelect = activeSessions.length === 1 ? (
    <select
      value={streamPreset}
      onChange={(e) => setStreamPreset(e.target.value as StreamPreset)}
      className="bg-slate-800/90 border border-white/10 rounded-lg text-[10px] sm:text-xs text-slate-200 px-2 py-1.5 max-w-[128px] sm:max-w-none"
      title={`Calidad WebP remoto. Auto baja si <${REMOTE_STREAM_WORKABLE_FPS} FPS (piso para trabajo). Máxima = resolución nativa.`}
    >
      <option value="auto">Calidad · Auto</option>
      <option value="max">Calidad · Máxima</option>
      <option value="balanced">Calidad · Equilibrada</option>
      <option value="speed">Calidad · Velocidad</option>
    </select>
  ) : null;

  // Pedir lista de sesiones al conectar (con retry)
  useEffect(() => {
    if (!wsViewerConnected) return;
    sendViewerCommand({ type: 'get_sessions' });
    sendViewerCommand({ type: 'release_input' });
  }, [wsViewerConnected, sendViewerCommand]);

  const refreshWindowsSessionsForDevice = useCallback(async (deviceId: number) => {
    try {
      await sendCentinelaControl(deviceId, { type: 'get_sessions' });
    } catch { /* agente puede estar offline */ }
    for (let i = 0; i < 8; i++) {
      await new Promise(r => setTimeout(r, 300));
      try {
        const sessions = await fetchWindowsSessions(deviceId);
        if (sessions.length) {
          setWinSessionsByDevice(prev => ({ ...prev, [deviceId]: sessions }));
          if ((standaloneDeviceId ?? focusedSessionId) === deviceId) {
            setWinSessions(sessions);
          }
          return;
        }
      } catch { break; }
    }
  }, [standaloneDeviceId, focusedSessionId]);

  useEffect(() => {
    if (!viewerStreamDeviceId) return;
    const cached = winSessionsByDevice[viewerStreamDeviceId];
    if (cached?.length) setWinSessions(cached);
  }, [viewerStreamDeviceId, winSessionsByDevice]);

  useEffect(() => {
    if (!sessionSwitching) return;
    const warnTimer = setTimeout(() => {
      if (pendingSwitchWindowsSessionRef.current != null) {
        setSessionSwitchError(prev => prev || 'El cambio está tardando. Puede cancelar e intentar de nuevo.');
      }
    }, 45000);
    const failTimer = setTimeout(() => {
      if (pendingSwitchWindowsSessionRef.current != null) {
        cancelSessionSwitch();
        setSessionSwitchError('Tiempo agotado al cambiar de sesión. Actualice el agente en el servidor e intente otra vez.');
      }
    }, 50000);
    return () => {
      clearTimeout(warnTimer);
      clearTimeout(failTimer);
    };
  }, [sessionSwitching, cancelSessionSwitch]);

  const submitWindowsLogin = useCallback(async () => {
    if (!loginCreds.username || !loginCreds.password) return;
    const targetId = loginDeviceId ?? standaloneDeviceId ?? focusedSessionId ?? activeSessions[0]?.id;
    if (!targetId) return;
    setLoginLoading(true);
    setLoginError('');
    localStorage.setItem('last_remote_username', loginCreds.username);
    localStorage.setItem('last_remote_domain', loginCreds.domain);
    const sessions = winSessionsByDevice[targetId] ?? winSessions;
    const consoleSess = sessions.find(w => w.name?.toLowerCase() === 'console');
    const winSessId = consoleSess?.id ?? 1;
    beginSessionSwitch(targetId, winSessId);
    const payload = {
      type: 'login_session' as const,
      ...loginCreds,
      session_id: winSessId,
    };
    const useWs = wsViewerConnected && (standaloneDeviceId === targetId || focusedSessionId === targetId);
    try {
      if (useWs) {
        sendViewerCommand(payload);
      } else {
        await sendCentinelaControl(targetId, payload);
      }
    } catch (e: any) {
      setLoginError(e?.message ?? 'Error al iniciar sesión');
      setLoginLoading(false);
    }
  }, [
    loginCreds, loginDeviceId, standaloneDeviceId, focusedSessionId, activeSessions,
    winSessionsByDevice, winSessions, wsViewerConnected, sendViewerCommand, beginSessionSwitch,
  ]);
  // ─────────────────────────────────────────────────────────────────────

  // Refs eliminados para MSE (usando MJPEG nativo)

  const logFrontendToBackend = useCallback(async (message: string, level: string = 'INFO') => {
    if (!hqDeviceId) return;
    try {
      const token = localStorage.getItem('token');
      const authHeader = token ? `Bearer ${token}` : '';
      const { API_URL } = await import('./api');
      await fetch(`${API_URL}/centinelas/logs/frontend?device_id=${hqDeviceId}&message=${encodeURIComponent(message)}&level=${level}`, {
        method: 'POST',
        headers: {
          'Authorization': authHeader
        }
      });
    } catch (err) {
      console.error('Error logging to backend:', err);
    }
  }, [hqDeviceId]);

  useEffect(() => {
    logFrontendRef.current = logFrontendToBackend;
  }, [logFrontendToBackend]);

  // Capturador global de excepciones, errores y rechazos de promesas en la consola para telemetría
  useEffect(() => {
    if (!hqDeviceId) return;

    const handleGlobalError = (event: ErrorEvent) => {
      const msg = `[FRONTEND-CONSOLA-ERROR] ${event.message || 'Error sin mensaje'} en ${event.filename || 'desconocido'}:${event.lineno || 0}:${event.colno || 0}`;
      logFrontendToBackend(msg, 'ERROR');
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const errorMsg = event.reason?.message || (typeof event.reason === 'object' ? JSON.stringify(event.reason) : String(event.reason));
      const msg = `[FRONTEND-CONSOLA-RECHAZO] Promesa no manejada: ${errorMsg}`;
      logFrontendToBackend(msg, 'ERROR');
    };

    window.addEventListener('error', handleGlobalError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    
    // Log de confirmación de versión
    logFrontendToBackend(
      `[VERSION] Portal ${APP_VERSION_LABEL} build ${APP_BUILD} (${APP_VERSION_TAG}) MSE=fMP4`,
      'INFO',
    );

    return () => {
      window.removeEventListener('error', handleGlobalError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [hqDeviceId, logFrontendToBackend]);

  useEffect(() => {
    if (!wsViewerConnected || !hqEnabled) return;
    // WebP primero; HD un poco después para no dejar pantalla negra al conectar
    sendViewerCommand({ type: 'refresh_frame' });
    const t = window.setTimeout(() => {
      if (hqEnabled) sendViewerCommand({ type: 'start_hq' });
    }, 2000);
    return () => window.clearTimeout(t);
  }, [wsViewerConnected, hqEnabled, sendViewerCommand]);

  const toggleHqMode = () => {
    const next = !hqEnabled;
    setHqEnabled(next);
    setHqState(next ? 'connecting' : 'off');
    if (hqStorageKey) localStorage.setItem(hqStorageKey, String(next));
    if (!next) {
      // Al apagar HD: liberar canvas para WebP (si no, queda negro/barras verdes)
      hqStreamOnCanvasRef.current = false;
      destroyHqDecoders();
      frameQueueRef.current = [];
      isProcessingQueueRef.current = false;
      try {
        const c = liveCanvasRef.current;
        if (c) {
          const ctx = c.getContext('2d');
          if (ctx) ctx.clearRect(0, 0, c.width || 0, c.height || 0);
        }
      } catch { /* ignore */ }
    }
    sendViewerCommand({ type: next ? 'start_hq' : 'stop_hq' });
    if (!next) {
      sendViewerCommand({ type: 'refresh_frame' });
      window.setTimeout(() => sendViewerCommand({ type: 'refresh_frame' }), 400);
    }
  };
  
  const handleAltViewer = (e: React.MouseEvent) => {
    e.preventDefault();
    if (!hqDeviceId) return;
    
    // Buscar el dispositivo en activeSessions o buscarlo en la DB si estuviera disponible.
    // Asumimos que activeSessions[0] es el dispositivo actual en la vista remota principal.
    const activeDevice = standaloneDeviceId 
        ? null 
        : activeSessions.find(s => s.id === hqDeviceId);
        
    let id = activeDevice?.alt_remote_id || null;
    const storageKey = `alt_viewer_id_${hqDeviceId}`;
    
    if (!id) {
        id = localStorage.getItem(storageKey);
    }
    
    // Si presiona Shift o Ctrl, o no hay ID, pedimos uno nuevo
    if (!id || e.shiftKey || e.ctrlKey) {
      const promptText = id 
        ? `ID actual de RustDesk/Nativo: ${id}\nIngrese el nuevo ID de conexión nativa (en blanco para borrar):` 
        : `No se detectó un ID nativo automáticamente desde el Centinela.\nIngrese el ID de la conexión nativa de RustDesk manualmente:`;
      const newId = prompt(promptText, id || '');
      if (newId !== null) {
        id = newId.replace(/\s+/g, ''); // Limpiar espacios
        if (id) {
            localStorage.setItem(storageKey, id);
        } else {
            localStorage.removeItem(storageKey);
            return;
        }
      } else {
        return; // Cancelado
      }
    }

    if (id) {
      setNativeConnectionState('connecting');

      // 1. Usar un iframe oculto para abrir el protocolo sin recargar la página y evitar que el WebSocket se desconecte.
      let iframe = document.getElementById('native-protocol-iframe') as HTMLIFrameElement;
      if (!iframe) {
        iframe = document.createElement('iframe');
        iframe.id = 'native-protocol-iframe';
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
      }
      iframe.src = `rustdesk://${id}`;

      // 2. Detección inteligente de lanzamiento exitoso:
      // Si el navegador abre con éxito la aplicación de RustDesk, la ventana del navegador perderá el foco (blur).
      // Si no la tiene instalada, el foco no se perderá nunca.
      let hasBlurred = false;
      const handleBlur = () => {
        hasBlurred = true;
      };
      window.addEventListener('blur', handleBlur);

      setTimeout(() => {
        window.removeEventListener('blur', handleBlur);
        if (hasBlurred) {
          setNativeConnectionState('success');
          // Volver a estado normal después de 4 segundos
          setTimeout(() => setNativeConnectionState('idle'), 4000);
        } else {
          setNativeConnectionState('error');
          alert(`❌ No se pudo abrir RustDesk automáticamente (ID: ${id})\n\n` +
                `Razones posibles:\n` +
                `1. No tienes la aplicación de RustDesk instalada en esta computadora.\n` +
                `2. RustDesk no tiene registrado su protocolo "rustdesk://" en tu Windows.\n\n` +
                `Por favor, abre la aplicación de RustDesk manualmente en tu PC e introduce el ID: ${id}`);
          setTimeout(() => setNativeConnectionState('idle'), 5000);
        }
      }, 1500);
    }
  };

  const getNativeButtonStyles = () => {
    switch (nativeConnectionState) {
      case 'connecting':
        return 'bg-amber-600 border-amber-500/30 text-amber-100 animate-pulse';
      case 'success':
        return 'bg-emerald-600 border-emerald-500/30 text-white shadow-emerald-500/20';
      case 'error':
        return 'bg-rose-600 border-rose-500/30 text-white shadow-rose-500/20';
      default:
        return 'bg-blue-600/80 border-blue-500/30 text-white hover:bg-blue-500/80';
    }
  };

  const getNativeButtonText = (short: boolean = false) => {
    switch (nativeConnectionState) {
      case 'connecting':
        return short ? 'Abriendo...' : '🚀 Abriendo...';
      case 'success':
        return short ? 'Conectado' : '✅ ¡Abierto!';
      case 'error':
        return short ? 'Error' : '❌ Error';
      default:
        return short ? 'Visor Nativo' : '🚀 Visor Nativo';
    }
  };


  
  useEffect(() => {
    if (wsViewerConnected && hqEnabled) {
      sendViewerCommand({ type: 'start_hq' });
    }
  }, [wsViewerConnected, hqEnabled, sendViewerCommand]);
  // ── FIN ALTO RENDIMIENTO ────────────────────────────────────────────────────




  // ─── NOTIFICACIONES DEL NAVEGADOR (Browser Notifications API) ─────────────
  // Solicita permiso al cargar y dispara alertas cuando un dispositivo cambia de estado
  const notificationPermissionRef = useRef<NotificationPermission>('default');

  useEffect(() => {
    // Pedir permiso de notificaciones al inicio de sesión autenticada
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().then(p => {
        notificationPermissionRef.current = p;
      });
    } else if ('Notification' in window) {
      notificationPermissionRef.current = Notification.permission;
    }
  }, []);

  const sendBrowserNotification = (title: string, body: string, icon?: string) => {
    if ('Notification' in window && notificationPermissionRef.current === 'granted') {
      const n = new Notification(title, {
        body,
        icon: icon || '/apollo_logo.png',
        badge: '/apollo_logo.png',
        tag: title, // Agrupa notificaciones del mismo tipo (no spamea)
        silent: false,
      });
      // Auto-cerrar en 8 segundos
      setTimeout(() => n.close(), 8000);
      // También reproducir sonido sutil
      try {
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.1);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.4);
      } catch (_) {}
    }
  };
  // ───────────────────────────────────────────────────────────────

  // Sincronizar título de ventana con Nombre de PC y Cliente de forma robusta
  useEffect(() => {
    if (standaloneIdInit && activeSessions.length > 0) {
      const session = activeSessions[0];
      if (session && session.device_name && session.device_name !== "Cargando Terminal...") {
        const clientName = session.client_name || session.razon_social || "Cliente";
        document.title = `🔴 ${clientName} — ${session.device_name} | ApolloSupport`;
      }
    }
  }, [standaloneIdInit, activeSessions]);

  // Sincronizar foco: una PC → siempre; varias → primera válida o la que el técnico eligió
  useEffect(() => {
    if (activeSessions.length === 0) {
      setFocusedSessionId(null);
      return;
    }
    if (activeSessions.length === 1) {
      setFocusedSessionId(activeSessions[0].id);
      return;
    }
    setFocusedSessionId(prev => {
      if (prev != null && activeSessions.some(s => s.id === prev)) return prev;
      return activeSessions[0].id;
    });
  }, [activeSessions]);

  // Nuevos estados para Intervenciones
  const [interventions, setInterventions] = useState<any[]>([]);
  const [transferAreaId, setTransferAreaId] = useState<number | null>(null);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [attachmentUrl, setAttachmentUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const [areas, setAreas] = useState<any[]>([]);
  const [resellers, setResellers] = useState<any[]>([]);
  const [selectedArea, setSelectedArea] = useState<number | null>(null);
  const [ticketsVista, setTicketsVista] = useState<'activa' | 'historico'>('activa');

  // Estados de Personal, ABM y Perfil (NUEVO)
  const [users, setUsers] = useState<any[]>([]);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showUserAbmModal, setShowUserAbmModal] = useState(false);
  const [selectedUserForEdit, setSelectedUserForEdit] = useState<any>(null); // null para nuevo, user para editar
  const [profileForm, setProfileForm] = useState({
    nombre: '',
    full_name: '',
    celular: '',
    departamento: '',
    password: '',
    profile_picture: ''
  });
  const [userAbmForm, setUserAbmForm] = useState({
    nombre: '',
    email: '',
    full_name: '',
    password: '',
    rol: 'soporte',
    celular: '',
    departamento: 'Atención al Cliente',
    actividades: ['Atención al Cliente'] as string[],
    profile_picture: '',
    activo: true,
    reseller_id: null as number | null
  });
  const [showResellerModal, setShowResellerModal] = useState(false);
  const [selectedResellerForEdit, setSelectedResellerForEdit] = useState<any>(null);
  const [resellerForm, setResellerForm] = useState({
    nombre: '',
    contacto: '',
    email: '',
    telefono: '',
    comision_pct: 0,
    notas: '',
    activo: true
  });

  // Estados de Historial de Sesión y Reporte IA (NUEVO)
  const [lastSupportSession, setLastSupportSession] = useState<any>(null);
  const [isLastSessionBannerDismissed, setIsLastSessionBannerDismissed] = useState<boolean>(false);
  const [showEndSessionModal, setShowEndSessionModal] = useState<boolean>(false);
  const [endSessionComment, setEndSessionComment] = useState<string>("");
  const [endSessionResult, setEndSessionResult] = useState<any>(null);
  const [isFinishingSession, setIsFinishingSession] = useState<boolean>(false);

  useEffect(() => {
    if (darkMode) document.body.classList.add('dark');
    else document.body.classList.remove('dark');
  }, [darkMode]);

  // --- DETECTOR DE INACTIVIDAD (Cierre de sesión automático tras 1 hora) ---
  const lastActivityRef = useRef<number>(Date.now());

  useEffect(() => {
    if (!isAuthenticated) return;

    // Inicializar el tiempo de última actividad
    lastActivityRef.current = Date.now();

    const handleUserInteraction = () => {
      lastActivityRef.current = Date.now();
    };

    // Escuchar eventos globales de interacción física del usuario
    const events = ['mousemove', 'keydown', 'mousedown', 'scroll', 'touchstart'];
    events.forEach(event => {
      window.addEventListener(event, handleUserInteraction, { passive: true });
    });

    // Validar inactividad cada 10 segundos
    const checkInterval = setInterval(() => {
      const inactiveDuration = Date.now() - lastActivityRef.current;
      const oneHourMs = 1 * 60 * 60 * 1000; // 1 hora en ms

      if (inactiveDuration >= oneHourMs) {
        clearInterval(checkInterval);
        handleLogout();
        alert("🔒 Su sesión ha sido cerrada automáticamente por inactividad de más de 1 hora.");
      }
    }, 10000);

    return () => {
      events.forEach(event => {
        window.removeEventListener(event, handleUserInteraction);
      });
      clearInterval(checkInterval);
    };
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      const stored = localStorage.getItem('user');
      if (stored) {
        try {
          setUserProfile(JSON.parse(stored));
        } catch (e) {
          console.error("Error parsing user profile", e);
          handleLogout();
        }
      }
      loadData();
    }
  }, [isAuthenticated, selectedArea, ticketsVista]);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      getTickets(selectedArea || undefined, ticketsVista),
      getClients(),
      getAreas(),
      getPendingCentinelas(),
      getUsers().catch(() => []),
      getResellers().catch(() => [])
    ]).then(([tData, cData, aData, pData, uData, rData]) => {
      setTickets(tData);
      setClients(cData);
      setAreas(aData);
      setPendingDevices(pData || []);
      setUsers(uData || []);
      setResellers(rData || []);
      setLoading(false);
    }).catch((err) => {
      setLoading(false);
      if (err?.message === 'Sesión Expirada' || err?.message?.includes('401')) {
        handleLogout();
      } else {
        console.error("Error cargando datos:", err);
      }
    });
  }

  // Actualizar automáticamente la tarea y página del usuario en tiempo real
  useEffect(() => {
    if (isAuthenticated && userProfile) {
      let task = "Revisando el panel";
      let page = "Dashboard";
      
      if (activeTab === 'tickets') {
        page = "Bandeja Unificada";
        task = selectedArea ? `Viendo tickets de Sector: ${areas.find(a => a.id === selectedArea)?.nombre || ''}` : "Revisando Bandeja Unificada";
      } else if (activeTab === 'monitor') {
        page = "Terminal Remota";
        task = activeSessions.length > 0 
          ? `Asistiendo a PC: ${activeSessions.map(s => s.device_name).join(', ')}` 
          : "Explorando Flota de Terminales";
      } else if (activeTab === 'agenda') {
        page = "Agenda";
        task = "Reuniones y grabaciones";
      } else if (activeTab === 'clients') {
        page = "Base Clientes";
        task = "Buscando/Editando Clientes";
      } else if (activeTab === 'licenses') {
        page = "Licencias";
        task = "Administrando Licencias Centinela";
      } else if (activeTab === 'settings') {
        page = "Ajustes";
        task = "Ajustando Configuración";
      } else if (activeTab === 'personnel') {
        page = "Plantel de Personal";
        task = "Monitoreando Actividad del Personal";
      }
      
      updateUserStatus(true, task, page)
        .then((updatedUser) => {
          // Mantener perfil sincronizado localmente con campos nuevos
          const stored = localStorage.getItem('user');
          if (stored) {
            const parsed = JSON.parse(stored);
            const merged = { ...parsed, ...updatedUser };
            localStorage.setItem('user', JSON.stringify(merged));
            setUserProfile(merged);
          }
        })
        .catch(err => console.error("Error actualizando estado online", err));
    }
  }, [activeTab, selectedArea, activeSessions, isAuthenticated]);

  // Heartbeat de actividad de personal y recarga de plantel
  useEffect(() => {
    let interval: any;
    if (isAuthenticated) {
      interval = setInterval(async () => {
        try {
          // Enviar heartbeat para mantener el estado is_online = True
          await updateUserStatus(true);
          
          // Si está en la pestaña de personal, recargar la lista para ver actividad en vivo
          if (activeTab === 'personnel') {
            const uData = await getUsers();
            setUsers(uData);
          }
        } catch (e) {
          console.error("Heartbeat error:", e);
        }
      }, 15000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, activeTab]);

  // Parámetro de URL para modo Ventana Independiente (Standalone Remote Window)
  const params = new URLSearchParams(window.location.search);
  const standaloneId = params.get('remote_device_id');

  useEffect(() => {
    let interval: any;
    if (isAuthenticated && (activeTab === 'monitor' || activeTab === 'agenda' || standaloneId)) {
      const fetchTelemetry = async () => {
        try {
          const telemetryData = await getActiveCentinelas();
          setCentinelas(telemetryData);
          const clientsData = await getClients();
          setClients(clientsData);
          const pendingData = await getPendingCentinelas();
          setPendingDevices(pendingData || []);

          if (standaloneId) {
            const devId = parseInt(standaloneId);
            let matchedDev = clientsData.flatMap((c: any) => c.devices || []).find((d: any) => d.id === devId);
            if (!matchedDev && pendingData) {
              matchedDev = pendingData.find((d: any) => d.id === devId);
            }
            if (matchedDev) {
              const client = clientsData.find((c: any) => c.id === matchedDev.client_id);
              const clientName = client ? client.razon_social : "Cliente Pendiente";
              setActiveSessions([{
                id: devId,
                ...matchedDev,
                device_name: matchedDev.device_name,
                client_name: clientName,
              }]);
              document.title = `${APP_VERSION_LABEL} · ${clientName} — ${matchedDev.device_name} | ApolloSupport`;

              // Leer cantidad de monitores desde la telemetría en vivo del agente
              const liveTelem = telemetryData[String(devId)];
              if (liveTelem?.monitor_count) {
                setMonitorCount(liveTelem.monitor_count);
              }
            }
          }
        } catch (e: any) {
          if (e?.message === 'Sesión Expirada' || e?.message?.includes('401')) {
            handleLogout();
          } else {
            console.error("Error en telemetría:", e);
          }
        }
      };
      fetchTelemetry();
      interval = setInterval(fetchTelemetry, 3000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, activeTab, standaloneId]);

  // Poller de Chat en tiempo real para sesiones activas
  useEffect(() => {
    let interval: any;
    if (isAuthenticated && standaloneId) {
      const devId = parseInt(standaloneId);
      const isChatVisible = chatVisibility[String(devId)];
      if (isChatVisible) {
        const pollChat = () => {
          fetchChatHistory(devId);
        };
        pollChat();
        interval = setInterval(pollChat, 2000); // Polling cada 2 segundos
      }
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, standaloneId, chatVisibility]);

  // Poller de Portapapeles Remoto
  useEffect(() => {
    let interval: any;
    if (isAuthenticated && standaloneId) {
      const devId = parseInt(standaloneId);
      const pollClipboard = async () => {
        try {
          const clip = await getCentinelaClipboard(devId);
          if (clip.text && clip.text !== remoteClipboard) {
            setRemoteClipboard(clip.text);
            try { await navigator.clipboard.writeText(clip.text); } catch { /* permiso clipboard */ }
          }
        } catch (err) {
          console.error("Error polling clipboard", err);
        }
      };
      pollClipboard();
      interval = setInterval(pollClipboard, 3000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, standaloneId, remoteClipboard, pullRemoteClipboardToLocal]);

  // Polling de frames — FALLBACK para multi-sesión o cuando el WS no está disponible.
  // Con 1 sesión y WS activo, el hook useViewerWebSocket ya entrega los frames por push.
  useEffect(() => {
    let active = true;
    let timeoutId: any;

    // Si el WS viewer está activo y solo hay 1 sesión, el WS ya está entregando frames.
    // El polling solo corre para multi-sesión o como fallback si el WS no conectó.
    const wsStreamDeviceId = wsViewerConnected
      ? (standaloneDeviceId ?? focusedSessionId ?? (activeSessions.length === 1 ? activeSessions[0]?.id : null))
      : null;
    const usePolling = isAuthenticated && activeSessions.length > 0 &&
      (activeSessions.length > 1 || !wsViewerConnected);

    if (usePolling) {
      const fetchFrames = async () => {
        if (!active) return;
        let changed = false;
        const updatedFrames: Record<string, string> = {};
        const pollTargets = wsStreamDeviceId
          ? activeSessions.filter(s => s.id !== wsStreamDeviceId)
          : activeSessions;

        try {
          await Promise.all(pollTargets.map(async (s) => {
            const frame = await getCentinelaFrame(s.id);
            if (frame && frame !== sessionFramesRef.current[s.id]) {
              updatedFrames[s.id] = frame;
              changed = true;

              const now = performance.now();
              frameTimestampsRef.current.push(now);
              const twoSecsAgo = now - 2000;
              frameTimestampsRef.current = frameTimestampsRef.current.filter(t => t > twoSecsAgo);

              const fps = Math.round(frameTimestampsRef.current.length / 2);
              setConnectionFps(fps);
              setConnectionQuality(connectionQualityFromFps(fps));
            }
          }));

          if (changed && active) {
            setSessionFrames(prev => ({ ...prev, ...updatedFrames }));
          }
        } catch (err) {
          console.error("Error fetching frames", err);
        }

        if (active) {
          const delay = pollTargets.length === 0 ? 250
            : (activeSessions.length > 1 ? 110 : 75);
          timeoutId = setTimeout(fetchFrames, delay);
        }
      };

      fetchFrames();
    } else if (!wsViewerConnected && isAuthenticated) {
      setConnectionFps(0);
      setConnectionQuality('disconnected');
    }

    return () => {
      active = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [isAuthenticated, activeSessions, wsViewerConnected, focusedSessionId, standaloneDeviceId]);

  useEffect(() => {
    const targetSessionId = standaloneId ? parseInt(standaloneId) : focusedSessionId;
    if (!targetSessionId) return;

    const specialKeys: Record<string, string> = {
      'ArrowUp': 'up',
      'ArrowDown': 'down',
      'ArrowLeft': 'left',
      'ArrowRight': 'right',
      'Escape': 'escape',
      'Tab': 'tab',
      'Backspace': 'backspace',
      ' ': 'space',
      'Enter': 'enter',
      'Delete': 'delete',
      'PageUp': 'pgup',
      'PageDown': 'pgdn',
      'Home': 'home',
      'End': 'end',
      'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4', 'F5': 'f5', 'F6': 'f6',
      'F7': 'f7', 'F8': 'f8', 'F9': 'f9', 'F10': 'f10', 'F11': 'f11', 'F12': 'f12',
      'Shift': 'shift',
      'Control': 'ctrl',
      'Alt': 'alt',
      'Meta': 'win',
      'CapsLock': 'capslock',
      'Insert': 'insert',
      'ContextMenu': 'apps',   // tecla Menú (clic derecho por teclado)
      'NumLock': 'numlock',
      'ScrollLock': 'scrolllock',
      'Pause': 'pause',
      'PrintScreen': 'printscreen',
    };

    const codeToVk: Record<string, string> = {
      Minus: '-', Equal: '=', Comma: ',', Period: '.', Slash: '/',
      Backslash: '\\', Semicolon: ';', Quote: "'",
      BracketLeft: '[', BracketRight: ']', Backquote: '`',
      IntlBackslash: 'oem102', IntlRo: '/', IntlYen: '\\',
      NumpadDecimal: 'numpaddecimal', NumpadComma: 'numpaddecimal',
      NumpadAdd: 'numpadadd', NumpadSubtract: 'numpadsubtract',
      NumpadDivide: 'numpaddivide', NumpadMultiply: 'numpadmultiply',
      NumpadEnter: 'numpadenter',
    };
    const punctToVk: Record<string, string> = {
      '.': '.', ',': ',', '-': '-', '_': '-',
      '=': '=', '+': '=',
      '/': '/', '?': '/',
      '\\': '\\', '|': '\\',
      ';': ';', ':': ';',
      "'": "'", '"': "'",
      '[': '[', '{': '[',
      ']': ']', '}': ']',
      '`': '`', '~': '`',
      '<': ',', '>': '.',
      '*': '*',
    };

    const mapRemoteKey = (e: KeyboardEvent): string | null => {
      if (e.key in specialKeys) return specialKeys[e.key];
      if (/^Key[A-Z]$/.test(e.code)) return e.code.slice(3).toLowerCase();
      if (/^Digit[0-9]$/.test(e.code)) return e.code.slice(5);
      if (/^Numpad[0-9]$/.test(e.code)) return e.code.slice(6);
      if (e.code in codeToVk) return codeToVk[e.code];
      if (e.key.length === 1) {
        const ch = e.key.toLowerCase();
        if (/[a-z0-9]/.test(ch)) return ch;
        if (punctToVk[e.key]) return punctToVk[e.key];
      }
      return null;
    };

    const releaseModifiers = () => {
      ['shift', 'ctrl', 'alt', 'win'].forEach((k) => {
        sendRemoteControl(targetSessionId, { type: 'key_up', key: k });
      });
    };

    const handleKeyDown = async (e: KeyboardEvent) => {
      if (!isControlEnabled) return;
      if (isModalOpen || showLicenseModal || assignModal) return;
      const activeEl = document.activeElement;
      if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || (activeEl as HTMLElement).isContentEditable)) {
        return;
      }
      if (e.repeat) return;

      const isCaps = e.getModifierState && e.getModifierState('CapsLock');
      if (isCaps !== undefined) {
        setIsCapsLockActive(isCaps);
      }

      // AltGr (Ctrl+Alt derecho) se reporta como ctrlKey+altKey en el navegador.
      // En teclado español produce @ \ | # ~ [ ] { } etc. NO es un atajo: es un
      // caracter imprimible y debe ir por write_text (unicode), no como combo.
      const isAltGr = !!(e.getModifierState && e.getModifierState('AltGraph'));

      // Combos: C/X/V van por el puente de portapapeles (texto y archivos).
      // El resto (Ctrl+A/Z…) se manda atómico a la PC remota.
      const mappedForCombo = mapRemoteKey(e);
      const isModifierKey = e.key === 'Control' || e.key === 'Shift' || e.key === 'Alt' || e.key === 'Meta';
      if (!isModifierKey && mappedForCombo && (e.ctrlKey || e.altKey || e.metaKey) && !isAltGr) {
        const parts: string[] = [];
        if (e.ctrlKey || e.metaKey) parts.push('ctrl');
        if (e.altKey) parts.push('alt');
        if (e.shiftKey) parts.push('shift');
        parts.push(mappedForCombo);
        const combo = parts.join('+');
        if (combo === 'ctrl+c' || combo === 'ctrl+x') {
          e.preventDefault();
          await sendRemoteControl(targetSessionId, { type: 'key_press', key: combo });
          // El upload del agente puede tardar; reintentar varias veces
          [400, 1200, 2500, 4500, 7000].forEach((ms) => {
            window.setTimeout(() => { pullRemoteClipboardToLocal(targetSessionId); }, ms);
          });
          return;
        }
        if (combo === 'ctrl+v') {
          // Sin preventDefault: si no, Chrome no dispara paste y no llegan los archivos del Explorador.
          releaseModifiers();
          return;
        }
        e.preventDefault();
        await sendRemoteControl(targetSessionId, { type: 'key_press', key: combo });
        return;
      }

      const mapped = mapRemoteKey(e);
      const usePhysicalPrintableKey =
        !isAltGr &&
        e.key.length === 1 &&
        ((e.code in codeToVk) || /^Digit[0-9]$/.test(e.code) || /^Numpad/.test(e.code));
      if (usePhysicalPrintableKey && mapped) {
        e.preventDefault();
        await sendRemoteControl(targetSessionId, { type: 'key_down', key: mapped, code: e.code });
        return;
      }

      const typedChar =
        e.key.length === 1 &&
        !(e.key in specialKeys) &&
        (isAltGr || (!usePhysicalPrintableKey && !e.ctrlKey && !e.altKey && !e.metaKey))
          ? e.key
          : null;
      const isPrintableSymbol = !!(typedChar && !/[a-zA-Z0-9]/.test(typedChar));

      if (isPrintableSymbol && typedChar) {
        e.preventDefault();
        await sendRemoteControl(targetSessionId, {
          type: 'write_text',
          text: typedChar,
          restore_modifiers: e.shiftKey && !isAltGr ? ['shift'] : [],
        });
        return;
      }

      if (mapped) {
        e.preventDefault();
        await sendRemoteControl(targetSessionId, { type: 'key_down', key: mapped, code: e.code });
        return;
      }

      if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
        e.preventDefault();
        await sendRemoteControl(targetSessionId, {
          type: 'write_text',
          text: e.key,
          restore_modifiers: e.shiftKey ? ['shift'] : [],
        });
      }
    };

    const handleKeyUp = async (e: KeyboardEvent) => {
      if (!isControlEnabled) return;
      if (isModalOpen || showLicenseModal || assignModal) return;
      const activeEl = document.activeElement;
      if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || (activeEl as HTMLElement).isContentEditable)) {
        return;
      }
      const isAltGr = !!(e.getModifierState && e.getModifierState('AltGraph'));
      const mapped = mapRemoteKey(e);
      const usePhysicalPrintableKey =
        !isAltGr &&
        e.key.length === 1 &&
        ((e.code in codeToVk) || /^Digit[0-9]$/.test(e.code) || /^Numpad/.test(e.code));
      if (usePhysicalPrintableKey && mapped) {
        e.preventDefault();
        await sendRemoteControl(targetSessionId, { type: 'key_up', key: mapped, code: e.code });
        return;
      }
      const isPrintableSymbol =
        e.key.length === 1 &&
        !usePhysicalPrintableKey &&
        !/[a-zA-Z0-9]/.test(e.key) &&
        (isAltGr || (!e.ctrlKey && !e.altKey && !e.metaKey)) &&
        !(e.key in specialKeys);
      if (isPrintableSymbol) {
        e.preventDefault();
        return;
      }
      if (!mapped) return;
      e.preventDefault();
      await sendRemoteControl(targetSessionId, { type: 'key_up', key: mapped, code: e.code });
    };

    const handleBlur = () => releaseModifiers();

    const handlePaste = async (e: ClipboardEvent) => {
      if (!isControlEnabled) return;
      if (isModalOpen || showLicenseModal || assignModal) return;
      const activeEl = document.activeElement;
      if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || (activeEl as HTMLElement).isContentEditable)) {
        return;
      }
      const picked: File[] = [];
      const dt = e.clipboardData;
      if (dt?.files?.length) {
        for (const f of Array.from(dt.files)) picked.push(f);
      }
      if (!picked.length && dt?.items) {
        for (const item of Array.from(dt.items)) {
          if (item.kind !== 'file') continue;
          const f = item.getAsFile();
          if (f) picked.push(f);
        }
      }
      const text = dt?.getData('text') || '';
      if (picked.length > 0) {
        e.preventDefault();
        await pasteFilesToRemote(targetSessionId, picked);
        return;
      }
      if (text) {
        e.preventDefault();
        await pasteTextToRemote(targetSessionId, text);
        return;
      }
      setShowNotification('El navegador no recibió el archivo. Usá Pegar archivo en la barra, o arrastralo sobre la pantalla.');
      setTimeout(() => setShowNotification(null), 4500);
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('paste', handlePaste);
    window.addEventListener('blur', handleBlur);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('paste', handlePaste);
      window.removeEventListener('blur', handleBlur);
      releaseModifiers();
    };
  }, [standaloneId, focusedSessionId, isControlEnabled, sendRemoteControl, isModalOpen, showLicenseModal, assignModal, pasteTextToRemote, pasteFilesToRemote, pullRemoteClipboardToLocal]);

  useEffect(() => {
    let interval: any;
    if (isAuthenticated) {
      const fetchAlerts = async () => {
        try {
          const alerts = await getCentinelaAlerts();
          setActiveAlerts((prev: any) => {
            Object.entries(alerts).forEach(([id, list]: any) => {
              if (list.length > 0 && !prev[id]) {
                setShowNotification(`¡Alerta Crítica en PC #${id}!`);
                triggerPushNotification("⚠️ Alerta Crítica de Centinela", `¡Problema detectado en PC #${id}! Detalle: ${list.join(', ')}`, `/?remote_device_id=${id}`);
                setTimeout(() => setShowNotification(null), 5000);
              }
            });
            return alerts;
          });
        } catch (e: any) {
          if (e?.message === 'Sesión Expirada' || e?.message?.includes('401')) {
            handleLogout();
          } else {
            console.error("Error en alertas:", e);
          }
        }
      };
      fetchAlerts();
      interval = setInterval(fetchAlerts, 5000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated]);


  const handleLogout = () => {
    logoutUser(); // Marcar offline en backend
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setIsAuthenticated(false);
  }

  const handleProfilePicChange = (e: React.ChangeEvent<HTMLInputElement>, isAbm: boolean) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = reader.result as string;
        if (isAbm) {
          setUserAbmForm(prev => ({ ...prev, profile_picture: base64String }));
        } else {
          setProfileForm(prev => ({ ...prev, profile_picture: base64String }));
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profileForm.nombre) return;
    try {
      const updated = await updateUser(userProfile.id, {
        nombre: profileForm.nombre,
        full_name: profileForm.full_name,
        celular: profileForm.celular,
        password: profileForm.password || undefined,
        profile_picture: profileForm.profile_picture || undefined
      });
      // Sincronizar en localStorage y state
      const merged = { ...userProfile, ...updated };
      localStorage.setItem('user', JSON.stringify(merged));
      setUserProfile(merged);
      setShowProfileModal(false);
      loadData();
      setShowNotification("¡Tu perfil fue actualizado con éxito!");
      setTimeout(() => setShowNotification(null), 3000);
    } catch (err: any) {
      alert(err.message || "Error al actualizar perfil.");
    }
  };

  const handleSaveUserAbm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userAbmForm.nombre || !userAbmForm.email || (!selectedUserForEdit && !userAbmForm.password)) {
      alert("Por favor completa los campos requeridos.");
      return;
    }
    if (!userAbmForm.actividades.length) {
      alert("Seleccioná al menos una actividad (Atención, Desarrollo, Finanzas...).");
      return;
    }
    const departamento = userAbmForm.actividades.join(' / ');
    const area_ids = areas.filter((a: any) => userAbmForm.actividades.includes(a.nombre)).map((a: any) => a.id);
    try {
      if (selectedUserForEdit) {
        // Modificar existente
        await updateUser(selectedUserForEdit.id, {
          nombre: userAbmForm.nombre,
          email: userAbmForm.email,
          full_name: userAbmForm.full_name,
          password: userAbmForm.password || undefined,
          rol: userAbmForm.rol,
          celular: userAbmForm.celular,
          departamento,
          area_ids,
          reseller_id: userAbmForm.rol === 'reseller' ? userAbmForm.reseller_id : null,
          profile_picture: userAbmForm.profile_picture || undefined,
          activo: userAbmForm.activo
        });
        setShowNotification(`Usuario ${userAbmForm.nombre} actualizado.`);
      } else {
        // Crear nuevo
        await createUser({
          nombre: userAbmForm.nombre,
          email: userAbmForm.email,
          full_name: userAbmForm.full_name,
          password: userAbmForm.password,
          rol: userAbmForm.rol,
          celular: userAbmForm.celular,
          departamento,
          area_ids,
          reseller_id: userAbmForm.rol === 'reseller' ? userAbmForm.reseller_id : null,
          profile_picture: userAbmForm.profile_picture || undefined,
          activo: userAbmForm.activo
        });
        setShowNotification(`Usuario ${userAbmForm.nombre} creado.`);
      }
      setShowUserAbmModal(false);
      loadData();
      setTimeout(() => setShowNotification(null), 3000);
    } catch (err: any) {
      alert(err.message || "Error al guardar usuario.");
    }
  };

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSubject.trim() || !newDesc.trim()) return;
    if (newOrigen === "cliente" && !newClientId) {
      alert("Seleccioná el cliente del pedido.");
      return;
    }
    const destArea = areas.find(a => /desarroll|programac/i.test(a.nombre || ""));
    setIsSubmitting(true);
    try {
      const adjuntos: { url: string; filename: string; tipo: string }[] = [];
      for (const file of newPedidoFiles) {
        const uploaded = await uploadFile(file);
        if (!uploaded?.url) throw new Error(`No se pudo subir ${file.name}`);
        adjuntos.push({
          url: uploaded.url,
          filename: uploaded.filename || file.name,
          tipo: adjuntoTipoFromFile(file),
        });
      }
      await createTicket({
        client_id: newClientId ? parseInt(newClientId) : null,
        asunto: newSubject.trim(),
        descripcion: newDesc.trim(),
        prioridad: newPriority,
        origen: newOrigen,
        assigned_user_id: newAssigneeId ? parseInt(newAssigneeId) : null,
        initial_area_id: destArea?.id || null,
        adjuntos,
      });
      setIsModalOpen(false);
      setNewSubject("");
      setNewDesc("");
      setNewClientId("");
      setNewAssigneeId("");
      setNewOrigen("cliente");
      setNewPriority("media");
      setNewPedidoFiles([]);
      setShowNotification("Pedido enviado a Programación. Todo el sector puede verlo.");
      setTimeout(() => setShowNotification(null), 4000);
      const destId = destArea?.id || null;
      if (destId) {
        setActiveTab('tickets');
        setSelectedArea(destId);
      }
      loadData();
    } catch (err: any) {
      alert(err?.message || "Error de comunicación backend.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConsultarIA = async () => {
    if (!selectedTicket) return;
    setIsAiLoading(true);
    const result = await fetchAiAnalysis(selectedTicket.id);
    setAiSuggestion(result?.analysis || "Hubo un corte en la conexión neuronal. Intente nuevamente.");
    setIsAiLoading(false);
  }

  const openTicketModal = async (t: any) => {
    setSelectedTicket(t);
    setAiSuggestion(null);
    setInterventions(t.intervenciones || []);
    setTransferAreaId(null);
    setAttachment(null);
    setAttachmentUrl(null);
    setIsEditingTicket(false);
    setEditSubject(t.asunto || "");
    setEditDesc(t.descripcion || "");
    setEditPriority(t.prioridad || "media");
    setEditOrigen((t.origen === "interno" ? "interno" : "cliente") as "cliente" | "interno");
    setEditClientId(t.client_id ? String(t.client_id) : "");
  }

  const closeTicketModal = () => {
    setSelectedTicket(null);
    setInterventions([]);
    setNewMessage("");
    setIsEditingTicket(false);
    setIsSavingTicketEdit(false);
  }

  const handleSaveTicketEdit = async () => {
    if (!selectedTicket) return;
    if (!editSubject.trim() || !editDesc.trim()) {
      alert("Completá asunto y descripción.");
      return;
    }
    if (editOrigen === "cliente" && !editClientId) {
      alert("Seleccioná el cliente del pedido.");
      return;
    }
    setIsSavingTicketEdit(true);
    try {
      const payload: any = {
        asunto: editSubject.trim(),
        descripcion: editDesc.trim(),
        prioridad: editPriority,
        origen: editOrigen,
      };
      if (editClientId) {
        payload.client_id = parseInt(editClientId, 10);
      } else {
        payload.clear_client = true;
      }
      const updated = await updateTicket(selectedTicket.id, payload);
      const clientName =
        updated?.cliente?.razon_social
        || clients.find((c: any) => c.id === updated?.client_id)?.razon_social
        || (updated?.origen === "interno" ? "Interno" : selectedTicket.clientName);
      setSelectedTicket({ ...selectedTicket, ...updated, clientName });
      setInterventions(updated?.intervenciones || interventions);
      setIsEditingTicket(false);
      loadData();
      setShowNotification("Pedido actualizado.");
      setTimeout(() => setShowNotification(null), 3000);
    } catch (err: any) {
      alert(err?.message || "No se pudo guardar el pedido.");
    } finally {
      setIsSavingTicketEdit(false);
    }
  };

  useEffect(() => {
    if (!selectedTicket) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeTicketModal();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedTicket]);

  const toggleRemoteSession = async (centinela: any) => {
    const exists = activeSessions.find(s => s.id === centinela.id);
    if (exists) {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/centinelas/devices/${centinela.id}/end-session`, {
        method: "POST",
        headers: { 'Authorization': `Bearer ${token}` }
      });

      setActiveSessions(activeSessions.filter(s => s.id !== centinela.id));
      const newFrames = { ...sessionFrames };
      delete newFrames[centinela.id];
      setSessionFrames(newFrames);
      loadData();
      sendBrowserNotification(
        '🔴 Sesión Cerrada',
        `Conexión con ${centinela.device_name || `Dispositivo #${centinela.id}`} finalizada.`
      );
    } else {
      setActiveSessions([...activeSessions, centinela]);
      if (!sessionCmds[centinela.id]) {
        setSessionCmds({ ...sessionCmds, [centinela.id]: { current: "", history: [] } });
      }
      sendBrowserNotification(
        '🟢 Sesión Iniciada',
        `Conectado a ${centinela.device_name || `Dispositivo #${centinela.id}`}.`
      );
    }
  };

  // Cargar el historial de la última sesión de soporte al iniciar conexión remota (NUEVO)
  useEffect(() => {
    if (isAuthenticated && standaloneId) {
      const devId = parseInt(standaloneId);
      const fetchLastSession = async () => {
        try {
          const token = localStorage.getItem('token');
          const response = await fetch(`${API_URL}/centinelas/devices/${devId}/last-session`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (response.ok) {
            const data = await response.json();
            if (data) {
              setLastSupportSession(data);
            }
          }
        } catch (e) {
          console.error("Error fetching last session:", e);
        }
      };
      fetchLastSession();
    }
  }, [isAuthenticated, standaloneId]);

  const handleEndSessionSupport = async (deviceId: number) => {
    setIsFinishingSession(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/end-session`, {
        method: "POST",
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}` 
        },
        body: JSON.stringify({ comment: endSessionComment })
      });
      if (response.ok) {
        const data = await response.json();
        setEndSessionResult(data);
      } else {
        alert("Error al finalizar la sesión.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    } finally {
      setIsFinishingSession(false);
    }
  };

  const handleImageInteraction = async (
    e: React.MouseEvent<HTMLElement>,
    deviceId: number,
    clickType: 'left' | 'right' | 'double'
  ) => {
    if (!isControlEnabled) return;
    setFocusedSessionId(deviceId);
    e.preventDefault();
    const coords = getCoordinates(e);

    if (coords) {
      await sendCentinelaControl(deviceId, {
        type: 'mouse_click',
        x: coords.x,
        y: coords.y,
        click_type: clickType
      });
    }
  };

  const getCoordinates = (e: React.MouseEvent<HTMLElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const target = e.currentTarget;
    let originalWidth = 0;
    let originalHeight = 0;

    if (target instanceof HTMLImageElement) {
      originalWidth = target.naturalWidth;
      originalHeight = target.naturalHeight;
    } else if (target instanceof HTMLCanvasElement) {
      originalWidth = target.width;
      originalHeight = target.height;
    } else if (target instanceof HTMLVideoElement) {
      originalWidth = target.videoWidth;
      originalHeight = target.videoHeight;
    }

    // Fallback: si el tamaño intrínseco todavía no está disponible (p.ej. el video P2P
    // recién abierto reporta videoWidth=0 un instante), usar el tamaño renderizado para
    // NO descartar el click. Con dims = rect no hay letterbox: el mapeo sigue siendo correcto.
    if (!originalWidth || !originalHeight) {
      originalWidth = rect.width;
      originalHeight = rect.height;
    }

    if (!originalWidth || !originalHeight) return null;

    const containerWidth = rect.width;
    const containerHeight = rect.height;

    const containerRatio = containerWidth / containerHeight;
    const imageRatio = originalWidth / originalHeight;

    let renderWidth = containerWidth;
    let renderHeight = containerHeight;
    let offsetX = 0;
    let offsetY = 0;

    if (containerRatio > imageRatio) {
      renderHeight = containerHeight;
      renderWidth = containerHeight * imageRatio;
      offsetX = (containerWidth - renderWidth) / 2;
    } else {
      renderWidth = containerWidth;
      renderHeight = containerWidth / imageRatio;
      offsetY = (containerHeight - renderHeight) / 2;
    }

    const clickX = e.clientX - rect.left - offsetX;
    const clickY = e.clientY - rect.top - offsetY;

    const x = clickX / renderWidth;
    const y = clickY / renderHeight;

    if (x >= 0 && x <= 1 && y >= 0 && y <= 1) {
      return { x, y };
    }
    return null;
  };

  /** Al clic en la pantalla remota, sacar el foco de TECLADO/CONSOLA
   *  para que keydown del window llegue al agente (si no, el teclado "no anda"). */
  const stealRemoteKeyboardFocus = (el?: EventTarget | null) => {
    const active = document.activeElement as HTMLElement | null;
    if (
      active &&
      (active.tagName === 'INPUT' ||
        active.tagName === 'TEXTAREA' ||
        active.tagName === 'SELECT' ||
        active.isContentEditable)
    ) {
      active.blur();
    }
    const target = el as HTMLElement | null;
    if (target && typeof target.focus === 'function') {
      try {
        target.focus({ preventScroll: true });
      } catch {
        try { target.focus(); } catch { /* ignore */ }
      }
    }
  };

  const handleMouseDown = async (e: React.MouseEvent<HTMLElement>, deviceId: number) => {
    if (!isControlEnabled) return;
    e.preventDefault();
    e.stopPropagation();
    setFocusedSessionId(deviceId);
    stealRemoteKeyboardFocus(e.currentTarget);
    const buttonMap: { [key: number]: string } = { 0: 'left', 1: 'middle', 2: 'right' };
    const button = buttonMap[e.button];
    if (!button) return;
    mouseButtonsDownRef.current |= (1 << e.button);

    const coords = getCoordinates(e);
    const _t = e.currentTarget as HTMLElement;
    console.log('[MOUSE] down', {
      button,
      el: _t?.tagName,
      videoW: (_t as HTMLVideoElement)?.videoWidth,
      webrtc: webrtcState,
      coords,
    });
    if (coords) {
      await sendRemoteControl(deviceId, {
        type: 'mouse_down',
        x: coords.x,
        y: coords.y,
        button
      });
    }
  };

  const handleMouseUp = async (e: React.MouseEvent<HTMLElement>, deviceId: number) => {
    if (!isControlEnabled) return;
    e.preventDefault();
    e.stopPropagation();
    const buttonMap: { [key: number]: string } = { 0: 'left', 1: 'middle', 2: 'right' };
    const button = buttonMap[e.button];
    if (!button) return;
    mouseButtonsDownRef.current &= ~(1 << e.button);

    const coords = getCoordinates(e);
    if (coords) {
      await sendRemoteControl(deviceId, {
        type: 'mouse_up',
        x: coords.x,
        y: coords.y,
        button
      });
    }
  };

  const handleMouseLeave = (e: React.MouseEvent<HTMLElement>, deviceId: number) => {
    if (!isControlEnabled) return;
    const down = mouseButtonsDownRef.current;
    if (!down) return;
    const coords = getCoordinates(e);
    const buttonMap = ['left', 'middle', 'right'] as const;
    buttonMap.forEach((button, i) => {
      if (down & (1 << i)) {
        sendRemoteControl(deviceId, {
          type: 'mouse_up',
          x: coords?.x ?? 0.5,
          y: coords?.y ?? 0.5,
          button,
        });
      }
    });
    mouseButtonsDownRef.current = 0;
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLElement>, deviceId: number) => {
    if (!isControlEnabled) return;
    const now = performance.now();
    if (now - lastMouseMoveAtRef.current < 16) return;
    lastMouseMoveAtRef.current = now;
    const coords = getCoordinates(e);
    if (!coords) return;
    sendRemoteControl(deviceId, {
      type: 'mouse_move',
      x: coords.x,
      y: coords.y,
    });
  };

  const handleImageWheel = async (e: React.WheelEvent<HTMLElement>, deviceId: number) => {
    if (!isControlEnabled) return;
    e.preventDefault();
    e.stopPropagation();
    const direction = e.deltaY > 0 ? 'down' : 'up';
    const steps = Math.max(1, Math.min(10, Math.round(Math.abs(e.deltaY) / 40)));
    const coords = getCoordinates(e as unknown as React.MouseEvent<HTMLElement>);
    await sendRemoteControl(deviceId, {
      type: 'mouse_scroll',
      direction,
      amount: steps,
      ...(coords ? { x: coords.x, y: coords.y } : {})
    });
  };

  const handleSendCommand = async (clientId: number) => {
    const sessionInfo = sessionCmds[clientId];
    if (!sessionInfo?.current.trim()) return;

    const ok = await runCentinelaCommand(clientId, sessionInfo.current);
    if (ok) {
      setSessionCmds({
        ...sessionCmds,
        [clientId]: {
          current: "",
          history: [sessionInfo.current, ...sessionInfo.history].slice(0, 5)
        }
      });
      setShowNotification(`Comando enviado a PC #${clientId}`);
      setTimeout(() => setShowNotification(null), 3000);
    } else {
      alert("Error al enviar comando. ¿Está el agente conectado?");
    }
  }

  const handleSendIntervention = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTicket || (!newMessage.trim() && !attachmentUrl && !transferAreaId)) return;

    setIsSubmitting(true);
    const data = {
      mensaje: newMessage,
      tipo: transferAreaId ? 'transferencia' : 'comentario',
      to_area_id: transferAreaId || undefined,
      adjunto_url: attachmentUrl || undefined,
      adjunto_tipo: attachment ? (attachment.type.startsWith('audio') ? 'audio' : attachment.type.startsWith('image') ? 'imagen' : 'documento') : undefined
    };

    try {
      const sent = await addIntervention(selectedTicket.id, data);
      if (sent) {
        setInterventions([...interventions, sent]);
        setNewMessage("");
        setTransferAreaId(null);
        setAttachment(null);
        setAttachmentUrl(null);
        loadData();
      }
    } catch (err: any) {
      alert(err?.message || "No se pudo grabar la intervención");
    } finally {
      setIsSubmitting(false);
    }
  }

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    try {
      const res = await uploadFile(file);
      setAttachment(file);
      setAttachmentUrl(res.url);
    } catch (err: any) {
      alert(err?.message || "Error al subir archivo");
    } finally {
      setIsUploading(false);
    }
  }

  const handleCreateOrUpdateClient = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    let result;
    const versi = (clientForm.version_apollo || 'E').toUpperCase().slice(0, 1);
    let codigo = (clientForm.codigo || '').trim().toUpperCase();
    if (/^\d+$/.test(codigo)) codigo = codigo.padStart(4, '0');
    const payload = {
      ...clientForm,
      codigo,
      version_apollo: versi,
      activo: clientForm.activo !== false,
      fecha_vencimiento: clientForm.fecha_vencimiento || null,
      fecha_ultimo_pago: clientForm.fecha_ultimo_pago || null,
    };
    const first = codigo.slice(0, 1);
    const okVersi = (versi === 'E' && first < 'M') || (versi === 'S' && first === 'M') || (versi === 'R' && first === 'R') || (versi === 'P' && first === 'V');
    if (codigo && !okVersi) {
      setIsSubmitting(false);
      alert('El número de Cliente (Serie) no coincide con la Versión de AGC. ERP: dígito < M · Single: M · Clock: R · Pharmakos: V');
      return;
    }
    try {
      if (editingClient) result = await updateClient(editingClient, payload);
      else result = await createClient(payload);
    } catch (err: any) {
      setIsSubmitting(false);
      showToast(err?.message || 'Error al procesar el cliente.', 'error', 7000);
      return;
    }
    setIsSubmitting(false);

    if (result && result.id) {
      if (!editingClient) {
        setEditingClient(result.id);
        setClientActiveTab('erp_licensing');
        setShowNotification("Cliente dado de alta. Generá el serial GesActi en Activaciones ERP.");
        setTimeout(() => setShowNotification(null), 5000);
        loadData();
        return;
      }
      setIsClientModalOpen(false);
      setEditingClient(null);
      setClientForm({
        codigo: '',
        razon_social: '',
        nombre_fantasia: '',
        identificador_fiscal: '',
        cparte: '',
        version_apollo: 'E',
        telefono: '',
        email: '',
        localidad: '',
        fecha_vencimiento: '',
        modulos: 'Base, Facturación',
        apikey_apollo: '',
        remote_password: '',
        saldo: 0.0,
        vendedor_codigo: '',
        vendedor_nombre: '',
        clasificacion_codigo: '',
        clasificacion_nombre: '',
        extracto: '',
        cclifac: '',
        fecha_ultimo_pago: '',
        activo: true,
        reseller_id: null,
      });
      loadData();
    } else alert("Error al procesar el cliente.");
  };

  const handleVerifyRemotePassword = async (deviceId: number, pin: string = "") => {
    const token = localStorage.getItem('token');
    try {
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/verify-password`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ password: pin || "" })
      });
      if (response.ok) {
        const url = `${window.location.origin}${window.location.pathname}?remote_device_id=${deviceId}`;
        const windowName = `Remote_${deviceId}`;
        window.open(url, windowName, 'width=1280,height=800,menubar=no,status=no,toolbar=no');
        setShowNotification("Conexión iniciada.");
      } else {
        if (response.status === 401) {
          alert("Tu sesión de usuario ha expirado. Por favor, cierra sesión y vuelve a ingresar.");
          return;
        }
        let errMsg = "No se pudo iniciar la sesión remota.";
        try {
          const errData = await response.json();
          if (errData && errData.detail) errMsg = typeof errData.detail === 'string' ? errData.detail : errMsg;
        } catch { /* */ }
        alert(errMsg);
      }
    } catch (error) {
      alert("Error de red: No se pudo conectar con el servidor. Revisa si el backend de producción se encuentra activo.");
    }
  };

  const handleReleaseDeviceSession = async (deviceId: number, deviceName: string) => {
    if (!window.confirm(`¿Liberar sesión colgada en ${deviceName}?`)) return;
    try {
      const res = await releaseCentinelaSession(deviceId);
      setShowNotification(res.message || `Sesión liberada en ${deviceName}`);
      setTimeout(() => setShowNotification(null), 3500);
      loadData();
    } catch (e: any) {
      alert(e?.message || 'Error al liberar sesión');
    }
  };

  const handleForceRefreshDevice = async (deviceId: number, deviceName: string) => {
    try {
      const res = await forceCentinelaRefresh(deviceId);
      if (res.commands_sent) {
        setShowNotification(`Refresh enviado a ${deviceName}`);
      } else {
        alert(res.message || 'El agente no tiene WebSocket activo. Reiniciá Centinela en la PC cliente.');
      }
      setTimeout(() => setShowNotification(null), 3500);
    } catch (e: any) {
      alert(e?.message || 'Error al forzar refresh del agente');
    }
  };

  const handleDeleteDevice = async (deviceId: number) => {
    if (window.confirm("¿Está seguro de que desea eliminar este dispositivo? Esto liberará un cupo en la licencia.")) {
      try {
        const ok = await deleteCentinelaDevice(deviceId);
        if (ok) {
          setShowNotification("Dispositivo eliminado correctamente.");
          setTimeout(() => setShowNotification(null), 3000);
          loadData();
        } else {
          alert("Error al eliminar el dispositivo.");
        }
      } catch (e) {
        alert("Error de comunicación con el servidor.");
      }
    }
  };

  const handleSaveDeviceNotes = async () => {
    if (!deviceNotesModal) return;
    try {
      const ok = await updateCentinelaDeviceNotes(deviceNotesModal.deviceId, deviceNotesModal.notes);
      if (ok) {
        setClients(prev => prev.map(c => ({
          ...c,
          devices: c.devices?.map((d: any) => d.id === deviceNotesModal.deviceId ? { ...d, notes: deviceNotesModal.notes } : d)
        })));
        setDeviceNotesModal(null);
        setShowNotification("Notas del dispositivo guardadas correctamente.");
        setTimeout(() => setShowNotification(null), 3000);
      } else {
        alert("Error al guardar notas.");
      }
    } catch (e: any) {
      alert("Error de comunicación: " + e.message);
    }
  };

  const handleAssignLicense = async () => {
    if (!assignModal || !assignClientId) return;
    try {
      const res = await assignCentinelaLicense(assignModal.id, parseInt(assignClientId));
      showToast(res.message || 'Dispositivo asignado exitosamente.', 'success');
      setAssignModal(null);
      setAssignClientId("");
      loadData();
    } catch (e: any) {
      showToast(e.message || 'No se pudo asignar la licencia al dispositivo.', 'error', 7000);
    }
  };

  const sendRemoteChat = async (deviceId: number, message: string) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/chat`, {
      method: "POST",
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ message, sender_type: 'tech' })
    });
    if (response.ok) fetchChatHistory(deviceId);
  };

  const fetchChatHistory = async (deviceId: number) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/chat`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (response.ok) {
      const data = await response.json();
      setSessionChats(prev => ({ ...prev, [deviceId]: data }));
    }
  };

  const syncRemoteClipboard = async (deviceId: number, text: string) => {
    const token = localStorage.getItem('token');
    await fetch(`${API_URL}/centinelas/devices/${deviceId}/clipboard`, {
      method: "POST",
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ text })
    });
    setShowNotification("Portapapeles sincronizado.");
    setTimeout(() => setShowNotification(null), 2000);
  };

  /** Captura el frame remoto actual y lo deja en el portapapeles local (Ctrl+V en Word, chat, etc.). */
  const captureRemoteScreenToClipboard = async (deviceId: number) => {
    try {
      let blob: Blob | null = null;

      const canvas = liveCanvasRef.current;
      if (canvas && canvas.width > 0 && canvas.height > 0) {
        blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
      }

      if (!blob && videoRef.current && videoRef.current.videoWidth > 0) {
        const v = videoRef.current;
        const c = document.createElement('canvas');
        c.width = v.videoWidth;
        c.height = v.videoHeight;
        const ctx = c.getContext('2d');
        if (ctx) {
          ctx.drawImage(v, 0, 0);
          blob = await new Promise<Blob | null>((resolve) => c.toBlob(resolve, 'image/png'));
        }
      }

      if (!blob) {
        const raw =
          latestLiveFrameRef.current ||
          sessionFramesRef.current[deviceId] ||
          sessionFramesRef.current[String(deviceId)] ||
          '';
        if (!raw) {
          setShowNotification('No hay imagen del cliente para capturar.');
          setTimeout(() => setShowNotification(null), 3000);
          return;
        }
        const dataUrl = raw.startsWith('data:') || raw.startsWith('blob:')
          ? raw
          : `data:image/jpeg;base64,${raw}`;
        const img = await new Promise<HTMLImageElement>((resolve, reject) => {
          const i = new Image();
          i.onload = () => resolve(i);
          i.onerror = reject;
          i.src = dataUrl;
        });
        const c = document.createElement('canvas');
        c.width = img.naturalWidth || img.width;
        c.height = img.naturalHeight || img.height;
        const ctx = c.getContext('2d');
        if (!ctx || !c.width) {
          setShowNotification('No se pudo procesar la captura.');
          setTimeout(() => setShowNotification(null), 3000);
          return;
        }
        ctx.drawImage(img, 0, 0);
        blob = await new Promise<Blob | null>((resolve) => c.toBlob(resolve, 'image/png'));
      }

      if (!blob) {
        setShowNotification('No se pudo generar la captura.');
        setTimeout(() => setShowNotification(null), 3000);
        return;
      }

      if (typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        setShowNotification('Captura lista en el portapapeles — Ctrl+V donde quieras.');
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `apollo-captura-${deviceId}-${Date.now()}.png`;
        a.click();
        URL.revokeObjectURL(url);
        setShowNotification('Navegador sin clipboard de imagen: se descargó el PNG.');
      }
      setTimeout(() => setShowNotification(null), 3500);
    } catch (err: any) {
      console.error('captureRemoteScreenToClipboard', err);
      setShowNotification(err?.message || 'No se pudo copiar la captura (permiso del navegador).');
      setTimeout(() => setShowNotification(null), 3500);
    }
  };

  const fetchRemoteFiles = async (deviceId: number, path: string = "C:\\") => {
    const token = localStorage.getItem('token');
    setSessionFiles(prev => ({ ...prev, [deviceId]: { ...prev[deviceId], path, loading: true } }));
    try {
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/files?path=${encodeURIComponent(path)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        if (data.type === 'dir_list' || data.files) {
          setSessionFiles(prev => ({
            ...prev,
            [deviceId]: {
              path: data.path || path,
              files: data.files || [],
              loading: false,
              visible: true
            }
          }));
        } else {
          // Si el backend está cargando los archivos, reintentamos en 1 segundo
          setTimeout(() => fetchRemoteFiles(deviceId, path), 1000);
        }
      } else {
        setSessionFiles(prev => ({ ...prev, [deviceId]: { ...prev[deviceId], loading: false } }));
      }
    } catch (e) {
      setSessionFiles(prev => ({ ...prev, [deviceId]: { ...prev[deviceId], loading: false } }));
    }
  };

  const downloadRemoteFile = async (deviceId: number, path: string) => {
    const token = localStorage.getItem('token');
    setShowNotification("Esperando transmisión del archivo...");
    try {
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/files/download?path=${encodeURIComponent(path)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) {
        throw new Error("Error en la descarga");
      }
      const blob = await response.blob();
      const filename = path.split('\\').pop() || path.split('/').pop() || 'archivo_remoto';
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setShowNotification("Archivo descargado con éxito.");
    } catch (err) {
      setShowNotification("Error al descargar archivo del agente.");
    }
  };

  const fetchLicenses = async () => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/licenses`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (response.ok) {
      const data = await response.json();
      setLicenses(data);
    }
  };

  const fetchTelemetryLogs = async () => {
    setLogsLoading(true);
    try {
      const devId = logsFilterDevice !== 'all' ? Number(logsFilterDevice) : undefined;
      const lvl = logsFilterLevel !== 'all' ? logsFilterLevel : undefined;
      const src = logsFilterSource !== 'all' ? logsFilterSource : undefined;
      const data = await getCentinelaLogs(devId, lvl, src, 100);
      setTelemetryLogs(data);
    } catch (err: any) {
      console.error("Error fetching telemetry logs:", err);
    } finally {
      setLogsLoading(false);
    }
  };

  const fetchDeviceLogs = async (deviceId: number) => {
    setDeviceLogsLoading(true);
    try {
      const data = await getCentinelaLogs(deviceId, undefined, undefined, 100);
      setDeviceLogs(data);
    } catch (err: any) {
      console.error("Error fetching device logs:", err);
    } finally {
      setDeviceLogsLoading(false);
    }
  };

  const handleClearTelemetryLogs = async (deviceId?: number | null) => {
    if (!window.confirm("¿Está seguro de que desea limpiar el historial de logs? Esta acción no se puede deshacer.")) return;
    try {
      await clearCentinelaLogs(deviceId);
      setShowNotification("Historial de logs limpiado con éxito.");
      if (deviceId) {
        fetchDeviceLogs(deviceId);
      } else {
        fetchTelemetryLogs();
      }
    } catch (err: any) {
      alert("Error al limpiar logs: " + err.message);
    }
  };

  // Poll para bitácora global de logs
  useEffect(() => {
    if (activeTab === 'logs') {
      fetchTelemetryLogs();
    }
  }, [activeTab, logsFilterDevice, logsFilterLevel, logsFilterSource]);

  useEffect(() => {
    if (activeTab !== 'logs' || !logsAutoRefresh) return;
    const interval = setInterval(() => {
      fetchTelemetryLogs();
    }, 3000);
    return () => clearInterval(interval);
  }, [activeTab, logsAutoRefresh, logsFilterDevice, logsFilterLevel, logsFilterSource]);

  // Poll para logs de dispositivo en vivo (soporte standalone)
  useEffect(() => {
    const devId = standaloneDeviceId ?? (activeSessions.length === 1 ? activeSessions[0]?.id : null);
    if (!devId || !isDeviceLogsOpen) return;
    
    fetchDeviceLogs(devId);
    
    if (!logsAutoRefresh) return;
    const interval = setInterval(() => {
      fetchDeviceLogs(devId);
    }, 3000);
    return () => clearInterval(interval);
  }, [isDeviceLogsOpen, logsAutoRefresh, activeSessions]);

  const generateLicense = async (clientId: number, devices: number, days: number) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/licenses`, {
      method: "POST",
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ client_id: clientId, max_devices: devices, duration_days: days })
    });
    if (response.ok) {
      setShowNotification("Licencia generada con éxito.");
      fetchLicenses();
      setShowLicenseModal(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'licenses' || activeTab === 'monitor') fetchLicenses();
  }, [activeTab]);

  const handleUploadFile = async (deviceId: number, file: File) => {
    const token = localStorage.getItem('token');
    const currentPath = sessionFiles[deviceId]?.path || "C:\\";
    setShowNotification("Subiendo archivo al agente...");
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/files/upload?dest_path=${encodeURIComponent(currentPath)}`, {
        method: "POST",
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      if (response.ok) {
        setShowNotification("Archivo enviado con éxito al agente.");
        setTimeout(() => fetchRemoteFiles(deviceId, currentPath), 1500);
      } else {
        setShowNotification("Error al subir archivo.");
      }
    } catch (err) {
      setShowNotification("Error en la conexión al subir archivo.");
    }
  };

  const openClientModal = (c?: any) => {
    setClientActiveTab('basic');
    if (c) {
      setEditingClient(c.id);
      setClientForm({
        codigo: c.codigo || '',
        razon_social: c.razon_social,
        nombre_fantasia: c.nombre_fantasia || '',
        identificador_fiscal: c.identificador_fiscal || '',
        cparte: c.cparte || '',
        version_apollo: c.version_apollo || 'E',
        telefono: c.telefono || '',
        email: c.email || '',
        localidad: c.localidad || '',
        fecha_vencimiento: c.fecha_vencimiento ? c.fecha_vencimiento.split('T')[0] : '',
        modulos: c.modulos || 'Base, Facturación',
        apikey_apollo: c.apikey_apollo || '',
        remote_password: c.remote_password || '',
        saldo: c.saldo || 0.0,
        vendedor_codigo: c.vendedor_codigo || '',
        vendedor_nombre: c.vendedor_nombre || '',
        clasificacion_codigo: c.clasificacion_codigo || '',
        clasificacion_nombre: c.clasificacion_nombre || '',
        extracto: c.extracto || '',
        cclifac: c.cclifac || '',
        fecha_ultimo_pago: c.fecha_ultimo_pago || '',
        activo: c.activo !== false,
        reseller_id: c.reseller_id || null,
      });
    } else {
      setEditingClient(null);
      setClientForm({
        codigo: '',
        razon_social: '',
        nombre_fantasia: '',
        identificador_fiscal: '',
        cparte: '',
        version_apollo: 'E',
        telefono: '',
        email: '',
        localidad: '',
        fecha_vencimiento: '',
        modulos: 'Base, Facturación',
        apikey_apollo: '',
        remote_password: '',
        saldo: 0.0,
        vendedor_codigo: '',
        vendedor_nombre: '',
        clasificacion_codigo: '',
        clasificacion_nombre: '',
        extracto: '',
        cclifac: '',
        fecha_ultimo_pago: '',
        activo: true,
        reseller_id: null,
      });
      suggestNextGesactiCode('E');
    }
    setIsClientModalOpen(true);
  }

  if (!isAuthenticated) {
    if (showCentinelaPublic) {
      return (
        <CentinelaPublicPage
          onBack={() => {
            setShowCentinelaPublic(false);
            try {
              const url = new URL(window.location.href);
              url.searchParams.delete('centinela');
              url.searchParams.delete('page');
              url.hash = '';
              window.history.replaceState({}, '', url.pathname + url.search);
            } catch { /* ignore */ }
          }}
        />
      );
    }

    return (
      <Login
        onLogin={() => setIsAuthenticated(true)}
        onOpenCentinelaInstall={() => {
          setShowCentinelaPublic(true);
          try {
            const url = new URL(window.location.href);
            url.searchParams.set('centinela', '1');
            window.history.replaceState({}, '', url.toString());
          } catch { /* ignore */ }
        }}
      />
    );
  }
  // --- RENDERING INDEPENDIENTE PARA SESIONES REMOTAS INDEPENDIENTES (STANDALONE WINDOWS) ---
  if (standaloneId) {
    const session = activeSessions[0];
    if (!session) {
      return (
        <div className="flex h-screen items-center justify-center bg-slate-950 text-white">
          <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-500 border-t-transparent" />
        </div>
      );
    }

    const frame = sessionFrames[session.id];
    const cmdInfo = sessionCmds[session.id] || { current: "", history: [] };
    const isChatOpen = !!chatVisibility[String(session.id)];
    const isFilesOpen = !!sessionFiles[session.id]?.visible;
    const viewerClientName = session.client_name
      || clients.find((c: any) => c.id === session.client_id)?.razon_social
      || '';

    // Video en canvas (latestLiveFrameRef) puede seguir visible aunque frame en state esté vacío tras switch
    const hasLiveRemoteVideo = !!(
      frame ||
      latestLiveFrameRef.current ||
      sessionSwitching ||
      wsViewerConnected ||
      hqState === 'open' ||
      connectionFps > 0
    );
    const showDisconnectedOverlay = !sessionSwitching && !hasLiveRemoteVideo && !session.is_online;

    // ─── OVERLAY DE FULLSCREEN REAL DEL VISOR DECORADO (MANEJADO EN EL CONTENEDOR PRINCIPAL) ───

    return (
      <div className="flex h-screen w-screen flex-col bg-slate-950 text-white p-1 overflow-hidden select-none">
        {/* Cabecera fina: cliente + PC siempre visibles. El resto va al panel lateral. */}
        <div className="flex items-center gap-2 mb-1 px-1 min-h-[40px]" style={{ display: isViewerFullscreen ? 'none' : 'flex' }}>
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${hasLiveRemoteVideo ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
          <div className="min-w-0 flex-1">
            <h1 className="text-sm font-black tracking-tight truncate leading-tight" title={viewerClientName || 'Cliente'}>
              {viewerClientName || 'Cliente'}
            </h1>
            <p className="text-[11px] text-slate-400 truncate leading-tight" title={session.device_name}>
              PC: {session.device_name || '—'}
              {deviceAssistLabel(session) ? ` · ID ${deviceAssistLabel(session)}` : ''}
            </p>
          </div>
          <span className={`hidden sm:inline text-[9px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider shrink-0 ${hasLiveRemoteVideo ? (isControlEnabled ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/15 text-amber-400 border border-amber-500/20') : 'bg-red-500/15 text-red-400 border border-red-500/20'}`}>
            {!hasLiveRemoteVideo ? 'OFF' : (isControlEnabled ? 'Control' : 'Ver')}
          </span>
          {clipBridgeOn && (
            <span className="hidden sm:inline text-[9px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider shrink-0 bg-sky-500/15 text-sky-300 border border-sky-500/30" title="Ctrl+C en un archivo de tu PC lo deja listo para Pegar en el cliente">
              Copiar activo
            </span>
          )}
          {hasLiveRemoteVideo && (
            <span className="hidden md:inline text-[10px] font-mono text-slate-400 shrink-0">{connectionFps} FPS</span>
          )}
          <label
            className="shrink-0 px-3 py-1.5 rounded-xl text-[11px] font-black uppercase tracking-wider border border-sky-500/40 bg-sky-700 hover:bg-sky-600 text-white cursor-pointer"
            title="Elegí el archivo de tu PC. Después, en el cliente: cerrá el menú y clic derecho → Pegar. También podés arrastrarlo a la pantalla o Ctrl+V con la ventana enfocada."
          >
            Pegar archivo
            <input
              type="file"
              multiple
              className="hidden"
              onChange={async (e) => {
                const list = e.target.files;
                if (list?.length) await pasteFilesToRemote(session.id, list);
                e.target.value = '';
              }}
            />
          </label>
          <button
            type="button"
            onClick={() => setViewerToolsOpen(v => !v)}
            className={`shrink-0 px-3 py-1.5 rounded-xl text-[11px] font-black uppercase tracking-wider border transition-all ${viewerToolsOpen ? 'bg-brand-500 border-brand-400 text-white' : 'bg-slate-800 border-white/10 text-slate-200 hover:bg-slate-700'}`}
            title="Mostrar u ocultar herramientas, consola y teclado"
          >
            {viewerToolsOpen ? 'Ocultar panel' : 'Panel'}
          </button>
          <button
            onClick={() => setShowEndSessionModal(true)}
            className="shrink-0 bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 rounded-xl text-[11px] font-bold"
          >
            Cerrar
          </button>
        </div>

        {viewerToolsOpen && (
          <aside className="fixed top-12 right-2 z-40 w-96 max-h-[calc(100vh-3.5rem)] overflow-y-auto rounded-2xl border border-white/10 bg-slate-950/95 p-3 shadow-2xl flex flex-col gap-3">
            {/* Selector de Monitor (visible solo cuando hay 2+ monitores) */}
            {monitorCount > 1 && (
              <div className="flex items-center gap-1 bg-slate-800/80 rounded-xl px-2 py-1 border border-white/5">
                <span className="text-[9px] text-slate-400 font-bold mr-1 uppercase tracking-wider">Monitor</span>
                {Array.from({ length: monitorCount }, (_, i) => i + 1).map(idx => (
                  <button
                    key={idx}
                    onClick={() => switchMonitor(session.id, idx)}
                    className={`w-6 h-6 rounded-lg text-[10px] font-black transition-all ${
                      activeMonitor === idx
                        ? 'bg-brand-500 text-white shadow-sm shadow-brand-500/40'
                        : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                    }`}
                    title={`Cambiar a Monitor ${idx}`}
                  >
                    {idx}
                  </button>
                ))}
              </div>
            )}
            {/* Selector de sesiones Windows (RDP / Consola) */}
            {viewerStreamDeviceId && (
              <div className="relative flex-shrink-0">
                <button
                  onClick={async () => {
                    sendViewerCommand({ type: 'get_sessions' });
                    if (!showSessionPicker) await refreshWindowsSessionsForDevice(viewerStreamDeviceId);
                    setShowSessionPicker(v => !v);
                  }}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border transition-all ${
                    sessionSwitching
                      ? 'bg-amber-600/70 border-amber-500/30 text-amber-100 animate-pulse'
                      : (winSessionsByDevice[viewerStreamDeviceId] ?? winSessions).length === 0
                        ? 'bg-slate-700 border-white/10 text-slate-500 hover:bg-slate-600'
                        : 'bg-slate-700 border-white/10 text-slate-300 hover:bg-slate-600 hover:text-white'
                  }`}
                  title="Cambiar sesión de usuario Windows"
                >
                  <span>👤</span>
                  <span className="hidden sm:inline">
                    {sessionSwitching ? 'Cambiando...' :
                     (winSessionsByDevice[viewerStreamDeviceId] ?? winSessions).find(s => s.current)?.username || 'Sesión'}
                  </span>
                </button>

                {/* Dropdown de sesiones */}
                {showSessionPicker && !sessionSwitching && (
                  <div className="absolute right-0 top-full mt-2 z-50 min-w-[220px] bg-slate-900 border border-white/10 rounded-xl shadow-2xl p-1 animate-in slide-in-from-top-2">
                    <div className="px-3 py-1.5 text-[10px] text-slate-500 font-bold uppercase tracking-widest border-b border-white/5 mb-1">
                      Sesiones Windows
                    </div>
                    {(winSessionsByDevice[viewerStreamDeviceId] ?? winSessions).length === 0 ? (
                      <div className="px-3 py-2 text-xs text-slate-500 italic">Cargando sesiones...</div>
                    ) : (
                      (winSessionsByDevice[viewerStreamDeviceId] ?? winSessions).map(s => (
                        <button
                          key={s.id}
                          onClick={() => {
                            setShowSessionPicker(false);
                            if (!s.current && viewerStreamDeviceId) {
                              const disc = (s.state || '').toLowerCase().includes('disc');
                              if (disc) {
                                setSessionSwitchError('Sesión RDP desconectada: elegí Consola o una sesión Activa.');
                                return;
                              }
                              if (s.id < 1 || s.id > 65535) return;
                              beginSessionSwitch(viewerStreamDeviceId, s.id);
                              sendViewerCommand({ type: 'switch_session', session_id: s.id });
                              setShowSessionPicker(false);
                            }
                          }}
                          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all text-left ${
                            s.current
                              ? 'bg-brand-500/20 text-brand-300 cursor-default'
                              : 'hover:bg-slate-700 text-slate-300 cursor-pointer'
                          }`}
                        >
                          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            s.state?.toLowerCase().includes('activ') ? 'bg-green-400' :
                            s.state?.toLowerCase().includes('disc') ? 'bg-yellow-400' : 'bg-slate-500'
                          }`} />
                          <span className="flex-1 truncate">
                            {s.name?.toLowerCase() === 'console' && !s.username
                              ? `Consola (#${s.id})`
                              : (s.username || s.name || `Sesión ${s.id}`)}
                          </span>
                          <span className="text-slate-500 text-[10px]">{s.state}</span>
                          {s.current && <span className="text-brand-400 text-[10px]">● actual</span>}
                        </button>
                      ))
                    )}
                    <div className="border-t border-white/5 mt-1 pt-1">
                      <button
                        onClick={() => { setShowSessionPicker(false); setLoginDeviceId(viewerStreamDeviceId); setShowLoginModal(true); setLoginError(''); }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-slate-400 hover:bg-slate-700 hover:text-white transition-all text-left"
                      >
                        <span>🔑</span> Iniciar sesión con credenciales
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {streamQualitySelect}

            {/* ⚡ Alto Rendimiento — siempre visible */}

            <button
              onClick={toggleHqMode}
              className={`flex-shrink-0 px-3 py-2 rounded-xl text-xs font-bold border transition-all flex items-center gap-1.5 ${
                hqEnabled
                  ? 'bg-violet-600 border-violet-500/30 text-white shadow-violet-500/20 shadow-lg'
                  : 'bg-slate-700 border-white/10 text-slate-400 hover:bg-violet-700/50 hover:text-white'
              }`}
              title="Modo Alto Rendimiento H.264 (fMP4/MSE, ~24 FPS)"
            >
              <span>⚡</span>
              <span className="hidden sm:inline">
                {hqEnabled ? 'HD ON' : 'HD'}
              </span>
            </button>
            <button
              onClick={toggleWebRtc}
              className={`flex-shrink-0 px-3 py-2 rounded-xl text-xs font-bold border transition-all flex items-center gap-1.5 ${
                webrtcState === 'open'
                  ? 'bg-emerald-600 border-emerald-500/30 text-white'
                  : webrtcState === 'connecting'
                    ? 'bg-amber-600 border-amber-500/30 text-white'
                    : webrtcState === 'failed'
                      ? 'bg-slate-700 border-red-500/40 text-red-300'
                      : 'bg-slate-700 border-white/10 text-slate-400 hover:bg-emerald-700/50 hover:text-white'
              }`}
              title="Canal rápido UDP/P2P (fase 1). Si no conecta, se sigue con HD. Requiere agente 3.3.4+ con aiortc."
            >
              <span>⚡</span>
              <span className="hidden sm:inline">
                {webrtcState === 'open' ? 'P2P ON' : webrtcState === 'connecting' ? 'P2P…' : webrtcState === 'failed' ? 'P2P falló' : 'Canal rápido'}
              </span>
            </button>

            {/* 🗔 Restaurar / Despertar Pantalla Minimizada */}
            <button
              onClick={() => {
                sendViewerCommand({ type: 'wake_screen' });
                sendViewerCommand({ type: 'refresh_frame' });
                setShowNotification('Enviando señal para des-minimizar ventanas y despertar pantalla...');
                setTimeout(() => setShowNotification(null), 3500);
              }}
              className="flex-shrink-0 bg-slate-700 hover:bg-amber-600/40 hover:border-amber-400/50 text-slate-300 hover:text-amber-200 px-3 py-2 rounded-xl text-xs font-bold transition-all shadow-lg border border-white/10 flex items-center gap-1.5"
              title="Si ves negro: maximizá el Escritorio remoto en TU PC; este botón despierta ventanas en el cliente"
            >
              <span>🗔</span>
              <span className="hidden md:inline">Restaurar Pantalla</span>
            </button>

            {/* Botón de Pantalla Completa del Visor */}

            <button
              onClick={enterViewerFullscreen}
              className="bg-slate-800 hover:bg-slate-700 text-white px-3.5 py-2 rounded-xl text-xs font-bold transition-all shadow-lg border border-white/5 flex items-center justify-center gap-2"
              title="Pantalla Completa del Visor Remoto"
            >
              <Maximize2 className="w-4 h-4 text-brand-400" /> Pantalla Completa
            </button>

            {/* Herramientas — una sola fila dentro del panel (sin barra flotante) */}
            <div className="mt-1 pt-3 border-t border-white/10 flex flex-col gap-2.5">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-500 px-0.5">Herramientas</div>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => setIsControlEnabled(!isControlEnabled)}
                  className={`flex flex-col items-center justify-center gap-1 px-2 py-2.5 rounded-xl text-[10px] font-bold border transition-all min-w-0 ${
                    isControlEnabled
                      ? 'bg-brand-500 border-brand-400 text-white'
                      : 'bg-slate-800 border-white/10 text-slate-300 hover:bg-slate-700'
                  }`}
                  title={isControlEnabled ? 'Control activo' : 'Solo observar'}
                >
                  <Monitor size={16} />
                  {isControlEnabled ? 'Control' : 'Ver'}
                </button>
                <button
                  onClick={() => {
                    const idStr = String(session.id);
                    if (!chatVisibility[idStr]) fetchChatHistory(session.id);
                    setChatVisibility(prev => ({ ...prev, [idStr]: !prev[idStr] }));
                  }}
                  className={`flex flex-col items-center justify-center gap-1 px-2 py-2.5 rounded-xl text-[10px] font-bold border transition-all min-w-0 ${
                    isChatOpen ? 'bg-brand-600 border-brand-500 text-white' : 'bg-slate-800 border-white/10 text-slate-300 hover:bg-slate-700'
                  }`}
                  title="Chat con cliente"
                >
                  <MessageSquare size={16} />
                  Chat
                </button>
                <button
                  onClick={async () => {
                    try {
                      let sentFiles = false;
                      try {
                        const items = await navigator.clipboard.read();
                        const files: File[] = [];
                        for (const item of items) {
                          for (const type of item.types) {
                            if (type === 'text/plain') continue;
                            const blob = await item.getType(type);
                            const ext = type.split('/')[1] || 'bin';
                            files.push(new File([blob], `portapapeles.${ext}`, { type }));
                          }
                        }
                        if (files.length) {
                          await pasteFilesToRemote(session.id, files);
                          sentFiles = true;
                        }
                      } catch { /* clipboard.read archivos no siempre disponible */ }
                      if (sentFiles) return;
                      const text = await navigator.clipboard.readText();
                      if (!text) {
                        setShowNotification('Portapapeles vacío. Arrastrá archivos a la pantalla o usá Enviar archivos.');
                        setTimeout(() => setShowNotification(null), 3000);
                        return;
                      }
                      await pasteTextToRemote(session.id, text);
                    } catch {
                      const text = prompt('Texto a enviar al portapapeles del cliente:');
                      if (text !== null) await pasteTextToRemote(session.id, text);
                    }
                  }}
                  className="flex flex-col items-center justify-center gap-1 px-2 py-2.5 rounded-xl text-[10px] font-bold border bg-blue-700/80 border-blue-500/40 text-white hover:bg-blue-600 min-w-0"
                  title="Pegar texto del portapapeles en el cliente. Archivos: arrastrar a la pantalla o Enviar archivos."
                >
                  <Clipboard size={16} />
                  Pegar
                </button>
                <button
                  onClick={() => captureRemoteScreenToClipboard(session.id)}
                  className="flex flex-col items-center justify-center gap-1 px-2 py-2.5 rounded-xl text-[10px] font-bold border bg-slate-800 border-white/10 text-slate-300 hover:bg-violet-700/60 hover:text-white min-w-0"
                  title="Capturar pantalla del cliente → tu portapapeles"
                >
                  <Camera size={16} />
                  Captura
                </button>
                <button
                  onClick={() => {
                    const visible = !sessionFiles[session.id]?.visible;
                    if (visible) fetchRemoteFiles(session.id);
                    setSessionFiles(prev => ({ ...prev, [session.id]: { ...prev[session.id], visible } }));
                  }}
                  className={`flex flex-col items-center justify-center gap-1 px-2 py-2.5 rounded-xl text-[10px] font-bold border transition-all min-w-0 ${
                    isFilesOpen ? 'bg-emerald-600 border-emerald-500 text-white' : 'bg-slate-800 border-white/10 text-slate-300 hover:bg-slate-700'
                  }`}
                  title="Explorador de archivos remoto"
                >
                  <FileText size={16} />
                  Archivos
                </button>
                <button
                  onClick={() => setIsDeviceLogsOpen(prev => !prev)}
                  className={`flex flex-col items-center justify-center gap-1 px-2 py-2.5 rounded-xl text-[10px] font-bold border transition-all min-w-0 ${
                    isDeviceLogsOpen ? 'bg-violet-600 border-violet-500 text-white' : 'bg-slate-800 border-white/10 text-slate-300 hover:bg-slate-700'
                  }`}
                  title="Bitácora / consola"
                >
                  <Terminal size={16} />
                  Logs
                </button>
              </div>
              <label className="flex items-center justify-center gap-2 px-2 py-2 rounded-xl text-[10px] font-bold bg-emerald-700/80 hover:bg-emerald-600 text-white border border-emerald-500/40 cursor-pointer transition-all">
                <input
                  type="file"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const list = e.target.files;
                    if (list?.length) await pasteFilesToRemote(session.id, list);
                    e.target.value = '';
                  }}
                />
                <span>📁</span> Enviar archivos al cliente
              </label>
              <p className="text-[9px] text-slate-500 leading-snug px-0.5">
                Tip: también podés arrastrar archivos sobre la pantalla o Ctrl+V con archivos copiados.
              </p>
            </div>

            {/* Consola rápida */}
            <div className="mt-1 pt-3 border-t border-white/10 flex flex-col gap-2">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Consola</div>
              <div className="flex gap-1.5 items-center">
                <input
                  type="text"
                  value={cmdInfo.current}
                  onChange={(e) => setSessionCmds({ ...sessionCmds, [session.id]: { ...cmdInfo, current: e.target.value } })}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendCommand(session.id)}
                  className="flex-1 min-w-0 bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-[11px] text-emerald-400 font-mono outline-none"
                  placeholder="Comando..."
                />
                <button onClick={() => handleSendCommand(session.id)} className="bg-emerald-600 p-1.5 rounded-lg text-white hover:bg-emerald-700 shrink-0">
                  <ArrowUpRight size={14} />
                </button>
              </div>
              <div className="flex flex-wrap gap-1">
                <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'ctrl+alt+del' })} className="bg-red-500/20 hover:bg-red-500/40 text-[9px] font-extrabold text-red-400 px-2 py-1 rounded-md border border-red-500/30" title="Ctrl+Alt+Sup">
                  Ctrl+Alt+Sup
                </button>
                <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'enter' })} className="bg-slate-800 text-[9px] font-bold text-white px-2 py-1 rounded-md border border-white/5 hover:bg-slate-700">Enter</button>
                <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'escape' })} className="bg-slate-800 text-[9px] font-bold text-white px-2 py-1 rounded-md border border-white/5 hover:bg-slate-700">Esc</button>
                <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'tab' })} className="bg-slate-800 text-[9px] font-bold text-white px-2 py-1 rounded-md border border-white/5 hover:bg-slate-700">Tab</button>
              </div>
            </div>
          </aside>
        )}

        {/* ÚLTIMO ACCESO — compacto bajo el header */}
        {viewerToolsOpen && lastSupportSession && !isLastSessionBannerDismissed && !isViewerFullscreen && (
          <div className="fixed top-12 left-2 z-40 max-w-xs p-2.5 rounded-xl glass-dark border border-brand-500/20 text-slate-300 shadow-lg">
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-brand-400 text-[9px] font-black uppercase tracking-widest mb-0.5">Último acceso</div>
                <div className="text-[11px] text-slate-300 truncate">
                  {lastSupportSession.technician_name} · {new Date(lastSupportSession.end_time).toLocaleString()}
                </div>
                {lastSupportSession.comments && (
                  <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">"{lastSupportSession.comments}"</p>
                )}
              </div>
              <button
                onClick={() => setIsLastSessionBannerDismissed(true)}
                className="text-slate-500 hover:text-white p-1 shrink-0"
                title="Ocultar"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* Cuerpo Principal */}
        <div className="flex-1 min-w-0 flex flex-col lg:flex-row gap-4 overflow-hidden min-h-0">
          {/* Pantalla Remota */}
          <div 
            className={isViewerFullscreen 
              ? "fixed inset-0 z-[9999] bg-black flex items-center justify-center select-none" 
              : "flex-1 min-w-0 bg-black rounded-2xl border border-white/5 relative overflow-hidden min-h-0"}
            onMouseMove={isViewerFullscreen ? resetToolbarTimer : undefined}
            onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); }}
            onDragOver={(e) => {
              if (!isControlEnabled) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = 'copy';
              setIsDraggingFiles(true);
            }}
            onDragLeave={() => setIsDraggingFiles(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDraggingFiles(false);
              if (!isControlEnabled) return;
              if (e.dataTransfer.files?.length) pasteFilesToRemote(session.id, e.dataTransfer.files);
            }}
            style={{ cursor: isViewerFullscreen ? (toolbarVisible ? 'default' : 'none') : 'default' }}
          >
            {isDraggingFiles && (
              <div className="absolute inset-0 z-40 flex items-center justify-center bg-brand-600/30 border-4 border-dashed border-brand-300 pointer-events-none">
                <span className="text-white text-sm font-bold bg-black/60 px-4 py-2 rounded-xl">Soltar para pegar archivos en el cliente</span>
              </div>
            )}
            {(hqEnabled || frame || latestLiveFrameRef.current || wsViewerConnected) ? (
              <div className="absolute inset-0">
                <canvas
                  ref={setLiveCanvasRef}
                  tabIndex={0}
                  onMouseDown={(e) => handleMouseDown(e, session.id)}
                  onMouseUp={(e) => handleMouseUp(e, session.id)}
                  onMouseMove={(e) => handleMouseMove(e, session.id)}
                  onMouseLeave={(e) => handleMouseLeave(e, session.id)}
                  onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); }}
                  onWheel={(e) => handleImageWheel(e, session.id)}
                  style={{ display: webrtcState === 'open' || hqState === 'open' ? 'none' : 'block' }}
                  className={`absolute inset-0 w-full h-full object-contain cursor-default select-none outline-none ${showDisconnectedOverlay ? 'filter blur-[4px] brightness-[0.35] grayscale contrast-75' : captureWarning ? 'filter blur-[3px] brightness-[0.45] saturate-50' : ''}`}
                />

                <video
                  ref={webrtcVideoRef}
                  tabIndex={0}
                  autoPlay muted playsInline
                  onMouseDown={(e) => handleMouseDown(e, session.id)}
                  onMouseUp={(e) => handleMouseUp(e, session.id)}
                  onMouseMove={(e) => handleMouseMove(e, session.id)}
                  onMouseLeave={(e) => handleMouseLeave(e, session.id)}
                  onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); }}
                  onWheel={(e) => handleImageWheel(e, session.id)}
                  style={{ display: webrtcState === 'open' ? 'block' : 'none' }}
                  className={`absolute inset-0 w-full h-full object-contain outline-none ${captureWarning ? 'filter blur-[3px] brightness-[0.45] saturate-50' : ''}`}
                />
                
                <video
                  ref={videoRef}
                  tabIndex={0}
                  autoPlay muted playsInline
                  onMouseDown={(e) => handleMouseDown(e, session.id)}
                  onMouseUp={(e) => handleMouseUp(e, session.id)}
                  onMouseMove={(e) => handleMouseMove(e, session.id)}
                  onMouseLeave={(e) => handleMouseLeave(e, session.id)}
                  onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); }}
                  onWheel={(e) => handleImageWheel(e, session.id)}
                  style={{ display: webrtcState !== 'open' && hqState === 'open' ? 'block' : 'none' }}
                  className={`absolute inset-0 w-full h-full object-contain outline-none ${captureWarning ? 'filter blur-[3px] brightness-[0.45] saturate-50' : ''}`}
                />

                {hqEnabled && hqState !== 'open' && wsViewerConnected && connectionFps === 0 && (
                  <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20 max-w-md px-4 py-2 rounded-xl bg-violet-500/15 border border-violet-500/30 text-violet-100 text-xs text-center pointer-events-none">
                    Modo HD: conectando… Si la pantalla sigue negra, se activará calidad estándar en unos segundos (o desactiva HD).
                  </div>
                )}

                {captureWarning && (
                  <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 max-w-lg w-[92%] px-4 py-3 rounded-xl bg-amber-500/20 border border-amber-400/40 text-amber-50 text-xs text-center shadow-lg flex flex-col gap-2 items-center">
                    <p className="font-semibold leading-relaxed">{captureWarning}</p>
                    <button
                      type="button"
                      onClick={() => setCaptureWarning(null)}
                      className="px-3 py-1 rounded-lg bg-amber-500/30 border border-amber-400/40 text-[10px] font-black uppercase tracking-wider hover:bg-amber-500/40"
                    >
                      Entendido
                    </button>
                  </div>
                )}

                {sessionSwitching && (
                  <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/20 border border-amber-500/30 text-amber-200 text-xs font-bold shadow-lg pointer-events-none">
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-amber-400 border-t-transparent" />
                    Cambiando sesión Windows…
                  </div>
                )}

                {showDisconnectedOverlay && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/40 backdrop-blur-[1px] p-6 text-center z-20 animate-in fade-in duration-300">
                    <div className="p-4 rounded-[2rem] border border-red-500/20 bg-red-500/10 text-red-400 animate-bounce mb-3 shadow-2xl shadow-red-500/10">
                      <AlertCircle className="w-8 h-8 animate-pulse text-red-500" />
                    </div>
                    <h3 className="text-sm sm:text-base font-black text-red-400 uppercase tracking-widest bg-red-500/5 border border-red-500/10 px-4 py-1 rounded-full">
                      Enlace Remoto Interrumpido
                    </h3>
                    <p className="text-[11px] sm:text-xs text-slate-400 mt-2 max-w-sm leading-relaxed">
                      El agente Centinela se ha desconectado de internet o la PC se apagó. El enlace se restablecerá automáticamente en cuanto vuelva a estar en línea.
                    </p>
                  </div>
                )}

                {/* ── Barra flotante auto-oculta en Fullscreen ── */}
                {isViewerFullscreen && (
                  <div
                    className="absolute top-0 left-0 right-0 z-30 transition-all duration-500"
                    style={{
                      opacity: toolbarVisible ? 1 : 0,
                      transform: toolbarVisible ? 'translateY(0)' : 'translateY(-100%)',
                      pointerEvents: toolbarVisible ? 'auto' : 'none',
                    }}
                  >
                    <div className="flex items-center justify-between gap-3 px-5 py-3"
                      style={{ background: 'linear-gradient(to bottom, rgba(2,6,23,0.96) 0%, rgba(2,6,23,0) 100%)' }}
                    >
                      {/* Info izquierda */}
                      <div className="flex items-center gap-3">
                        <span className={`w-2.5 h-2.5 rounded-full ${hasLiveRemoteVideo ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
                        <span className="text-white font-bold text-sm tracking-tight">{session.device_name || 'Soporte Remoto'}</span>
                        {deviceAssistLabel(session) ? (
                          <span className="text-sky-400 text-xs font-mono font-black bg-sky-500/10 border border-sky-500/20 px-2 py-0.5 rounded-md" title="ID de asistencia">
                            ID: {deviceAssistLabel(session)}
                          </span>
                        ) : (
                          <span className="text-slate-400 text-xs font-mono bg-slate-800/70 px-2 py-0.5 rounded-md">#{session.id}</span>
                        )}
                        {session.alt_remote_id && (
                          <span className="text-slate-500 text-[10px] font-mono bg-slate-800/50 px-2 py-0.5 rounded-md">RD: {session.alt_remote_id}</span>
                        )}
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider border ${isControlEnabled ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/15 text-amber-400 border-amber-500/20'}`}>
                          {isControlEnabled ? '⚡ Control Activo' : '👁 Solo Observando'}
                        </span>
                        {isCapsLockActive && (
                          <span className="text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-md font-bold flex items-center gap-1 animate-pulse">
                            🔠 MAYÚS
                          </span>
                        )}
                        <span className="text-slate-500 text-[10px]">Mover el mouse para mostrar/ocultar barra · ESC para salir</span>
                      </div>

                      {/* Controles derecha */}
                      <div className="flex items-center gap-2">
                        {streamQualitySelect}
                        {/* ── ALTO RENDIMIENTO TOGGLE ── */}
                        <button
                          onClick={toggleHqMode}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${
                            hqEnabled
                              ? 'bg-violet-600/80 border-violet-500/30 text-white shadow-violet-500/20 shadow-lg'
                              : 'bg-slate-700/60 border-white/10 text-slate-400 hover:bg-violet-700/50 hover:text-white'
                          }`}
                          title="Modo Alto Rendimiento H.264 (fMP4/MSE, ~24 FPS)"
                        >
                          {hqEnabled ? '⚡ HD ON' : '⚡ Alto Rendimiento'}
                        </button>
                        <button
                          onClick={() => setIsControlEnabled(v => !v)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${isControlEnabled ? 'bg-emerald-600/80 border-emerald-500/30 text-white hover:bg-red-600/80 hover:border-red-500/30' : 'bg-slate-700/80 border-white/10 text-slate-300 hover:bg-emerald-600/80'}`}
                          title="Alternar Control / Solo Ver"
                        >
                          {isControlEnabled ? '🖱 Control ON' : '👁 Solo Ver'}
                        </button>
                        <button
                          onClick={exitViewerFullscreen}
                          className="flex items-center gap-1.5 bg-red-600/80 hover:bg-red-600 border border-red-500/30 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-lg"
                          title="Salir de Pantalla Completa (ESC)"
                        >
                          <Minimize className="w-3.5 h-3.5" /> Salir Fullscreen
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Indicador discreto de "mover mouse" en Fullscreen */}
                {isViewerFullscreen && !toolbarVisible && (
                  <div
                    className="absolute top-2 left-1/2 -translate-x-1/2 text-[10px] text-white/20 pointer-events-none select-none transition-opacity duration-500 z-30"
                  >
                    ↑ mover mouse para ver controles
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-500 border-t-transparent" />
                <span className="text-xs text-slate-500">Esperando imagen del cliente...</span>
              </div>
            )}

            {/* Panel de Herramientas — unificado dentro del aside (derecha) */}
          </div>

          {/* Paneles de Apoyo: Chat, Archivos y Logs */}
          {(isChatOpen || isFilesOpen || isDeviceLogsOpen) && (
            <div className="w-full lg:w-80 flex flex-col gap-4 overflow-y-auto">
              {isChatOpen && (
                <div className="flex-1 bg-slate-900 border border-white/5 rounded-2xl p-4 flex flex-col min-h-[250px]">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 mb-3">Chat de Soporte</h3>
                  <div className="flex-1 overflow-y-auto space-y-2 mb-3 pr-1 text-xs">
                    {(sessionChats[session.id] || []).map((msg: any, i: number) => (
                      <div key={i} className={`p-2.5 rounded-xl max-w-[85%] ${msg.sender_type === 'tech' ? 'bg-brand-500 text-white ml-auto' : 'bg-slate-800 text-slate-300'}`}>
                        {msg.message}
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      id={`chat-input-${session.id}`}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          const input = e.currentTarget;
                          if (input.value.trim()) {
                            sendRemoteChat(session.id, input.value.trim());
                            input.value = '';
                          }
                        }
                      }}
                      className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-xs outline-none"
                      placeholder="Escribe al cliente..."
                    />
                  </div>
                </div>
              )}

              {isFilesOpen && (
                <div className="flex-1 bg-slate-900 border border-white/5 rounded-2xl p-4 flex flex-col min-h-[250px]">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 mb-3">Archivos Remotos</h3>
                  <div className="flex items-center gap-2 mb-2">
                    <input
                      type="text"
                      id={`path-input-${session.id}`}
                      defaultValue={sessionFiles[session.id]?.path || "C:\\"}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          fetchRemoteFiles(session.id, e.currentTarget.value);
                        }
                      }}
                      className="flex-1 bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 text-xs font-mono outline-none"
                    />
                  </div>
                  <div className="flex-1 overflow-y-auto space-y-1.5 text-xs font-mono">
                    {sessionFiles[session.id]?.loading ? (
                      <div className="text-slate-500 animate-pulse text-center mt-4">Leyendo disco remoto...</div>
                    ) : (
                      (sessionFiles[session.id]?.files || []).map((f: any, idx: number) => (
                        <div key={idx} className="flex justify-between items-center p-1.5 hover:bg-white/5 rounded-lg">
                          <span
                            onClick={() => f.is_dir && fetchRemoteFiles(session.id, f.path)}
                            className={`cursor-pointer ${f.is_dir ? 'text-brand-400 font-bold' : 'text-slate-300'}`}
                          >
                            {f.is_dir ? '📁' : '📄'} {f.name}
                          </span>
                          {!f.is_dir && (
                            <button
                              onClick={() => downloadRemoteFile(session.id, f.path)}
                              className="text-[10px] text-emerald-400 hover:underline"
                            >
                              Bajar
                            </button>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                  <div className="mt-2 pt-2 border-t border-white/5">
                    <input
                      type="file"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadFile(session.id, file);
                      }}
                      className="text-[10px] text-slate-500 cursor-pointer"
                    />
                  </div>
                </div>
              )}

              {isDeviceLogsOpen && (
                <div className="flex-1 bg-slate-900 border border-white/5 rounded-2xl p-4 flex flex-col min-h-[300px]">
                  <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2">
                    <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                      <Terminal size={14} className="text-violet-400 animate-pulse" /> Logs de Telemetría
                    </h3>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => fetchDeviceLogs(session.id)}
                        className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-bold transition-all"
                        title="Actualizar ahora"
                      >
                        🔄
                      </button>
                      <button
                        onClick={() => handleClearTelemetryLogs(session.id)}
                        className="p-1 rounded bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white text-[10px] font-bold transition-all"
                        title="Limpiar logs"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                  
                  {/* Feed de Logs */}
                  <div className="flex-1 overflow-y-auto space-y-2 mb-2 pr-1 font-mono text-[10px] leading-tight select-text scrollbar-thin max-h-[400px]">
                    {deviceLogsLoading && deviceLogs.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-full text-slate-500 py-8">
                        <div className="animate-spin rounded-full h-4 w-4 border-2 border-brand-500 border-t-transparent mb-2" />
                        <span>Cargando logs...</span>
                      </div>
                    ) : deviceLogs.length === 0 ? (
                      <div className="text-center text-slate-500 italic py-8">
                        No hay logs registrados para este dispositivo.
                      </div>
                    ) : (
                      deviceLogs.map((log: any) => {
                        let levelColor = "text-slate-300 bg-slate-800/40 border-slate-700/20";
                        if (log.level === 'DEBUG') levelColor = "text-cyan-400 bg-cyan-950/20 border-cyan-800/10";
                        if (log.level === 'WARNING') levelColor = "text-amber-400 bg-amber-950/20 border-amber-800/10 animate-pulse";
                        if (log.level === 'ERROR') levelColor = "text-red-400 bg-red-950/20 border-red-800/20 font-bold border shadow-sm shadow-red-500/5";

                        return (
                          <div key={log.id} className={`p-2 rounded-lg border bg-slate-950/40 hover:bg-slate-950/60 transition-all`}>
                            <div className="flex items-center justify-between gap-1 mb-1 text-[9px] text-slate-500 border-b border-white/5 pb-0.5">
                              <span className="font-sans">
                                {new Date(log.timestamp).toLocaleTimeString('es-AR')}
                              </span>
                              <span className={`px-1 rounded text-[8px] font-extrabold uppercase ${levelColor.split(' ').slice(0,2).join(' ')}`}>
                                {log.level}
                              </span>
                            </div>
                            <p className={`whitespace-pre-wrap break-all ${log.level === 'ERROR' ? 'text-red-300' : log.level === 'WARNING' ? 'text-amber-300' : 'text-slate-300'}`}>
                              {log.message}
                            </p>
                          </div>
                        );
                      })
                    )}
                  </div>
                  
                  {/* Pie de Panel */}
                  <div className="flex items-center justify-between text-[9px] text-slate-500 border-t border-white/5 pt-2">
                    <span className="flex items-center gap-1">
                      <span className={`w-1.5 h-1.5 rounded-full ${logsAutoRefresh ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
                      {logsAutoRefresh ? 'Auto-refrescando' : 'Pausado'}
                    </span>
                    <button 
                      onClick={() => setLogsAutoRefresh(v => !v)}
                      className="text-brand-400 hover:text-brand-300 font-bold"
                    >
                      {logsAutoRefresh ? 'Pausar' : 'Activar'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* MODAL DE COMENTARIO Y REPORTE IA AL FINALIZAR SESIÓN (NUEVO) */}
        {/* 🔑 MODAL LOGIN SESIÓN WINDOWS */}
        {showLoginModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 backdrop-blur-md p-4 animate-in fade-in">
            <div className="w-full max-w-[340px] px-5 pt-6 pb-5 rounded-2xl border border-white/10 glass-dark shadow-2xl flex flex-col gap-4 animate-in slide-in-from-bottom-8">
              <div className="flex justify-between items-center">
                <div>
                  <span className="text-violet-400 font-bold text-[10px] uppercase tracking-widest bg-violet-500/10 px-2 py-0.5 rounded-full">
                    Acceso Windows
                  </span>
                  <h3 className="text-base font-black text-white mt-1">Iniciar Sesión Remota</h3>
                </div>
                <button onClick={() => setShowLoginModal(false)} className="text-slate-500 hover:text-white p-1">✕</button>
              </div>

              <div className="flex flex-col gap-4 pt-2">
                <div>
                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2 block">Usuario</label>
                  <input
                    type="text"
                    value={loginCreds.username}
                    onChange={e => setLoginCreds(c => ({...c, username: e.target.value}))}
                    placeholder="nombre.usuario"
                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-3 text-sm leading-5 text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50"
                    autoFocus
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2 block">
                    Dominio <span className="text-slate-600 font-normal normal-case">(opcional, dejar '.' para local)</span>
                  </label>
                  <input
                    type="text"
                    value={loginCreds.domain}
                    onChange={e => setLoginCreds(c => ({...c, domain: e.target.value}))}
                    placeholder="."
                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-3 text-sm leading-5 text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowLoginPassword(!showLoginPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                    title={showLoginPassword ? "Ocultar" : "Mostrar"}
                  >
                    {showLoginPassword ? "👁️‍🗨️" : "👁️"}
                  </button>
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2 block">Contraseña</label>
                  <div className="relative">
                    <input
                      type={showLoginPassword ? "text" : "password"}
                      value={loginCreds.password}
                      onChange={e => setLoginCreds(c => ({...c, password: e.target.value}))}
                      placeholder="••••••••"
                      onKeyDown={e => {
                        if (e.key === 'Enter' && loginCreds.username && loginCreds.password) {
                          submitWindowsLogin();
                        }
                      }}
                      className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-3 text-sm leading-5 text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowLoginPassword(!showLoginPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white flex items-center justify-center"
                      title={showLoginPassword ? "Ocultar contraseña" : "Ver contraseña"}
                    >
                      {showLoginPassword ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" y1="2" x2="22" y2="22"/></svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                      )}
                    </button>
                  </div>
                </div>
                {loginError && (
                  <div className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                    ⚠ {loginError}
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => setShowLoginModal(false)}
                  className="flex-1 py-2 rounded-xl text-xs font-bold bg-slate-700 hover:bg-slate-600 text-slate-300 transition-all"
                >Cancelar</button>
                <button
                  onClick={() => submitWindowsLogin()}
                  disabled={loginLoading || !loginCreds.username || !loginCreds.password}
                  className="flex-1 py-2 rounded-xl text-xs font-bold bg-violet-600 hover:bg-violet-500 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loginLoading ? '⏳ Iniciando...' : '🔑 Iniciar Sesión'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 🔄 OVERLAY CAMBIO DE SESION */}
        {sessionSwitching && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-md animate-in fade-in p-4">
            <div className="text-center flex flex-col items-center gap-4 max-w-sm">
              <div className="w-12 h-12 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-white font-bold">Cambiando sesión...</p>
              <p className="text-slate-400 text-xs">El agente se reconectará en la nueva sesión (Consola o RDP)</p>
              {sessionSwitchError && (
                <p className="text-amber-300 text-xs bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
                  {sessionSwitchError}
                </p>
              )}
              <button
                type="button"
                onClick={cancelSessionSwitch}
                className="mt-2 px-4 py-2 rounded-xl text-xs font-bold bg-slate-700 hover:bg-slate-600 text-slate-200"
              >
                Cancelar y volver
              </button>
            </div>
          </div>
        )}

        {showEndSessionModal && (

          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/90 backdrop-blur-md p-4 overflow-y-auto animate-in fade-in">
            <div className="w-full max-w-xl p-6 sm:p-8 rounded-[2rem] border border-brand-500/15 glass-dark shadow-2xl flex flex-col gap-6 animate-in slide-in-from-bottom-8">
              
              {/* Cabecera */}
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-indigo-400 font-extrabold text-[10px] sm:text-xs uppercase tracking-widest bg-indigo-500/10 px-3 py-1 rounded-full mb-2 inline-block">
                    Mantenimiento de Bitácora
                  </span>
                  <h3 className="text-lg sm:text-xl font-black text-white">Finalizar Sesión de Soporte</h3>
                </div>
                {!endSessionResult && (
                  <button 
                    onClick={() => setShowEndSessionModal(false)}
                    className="text-slate-400 hover:text-white p-2 hover:bg-white/5 rounded-xl transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                )}
              </div>

              {!endSessionResult ? (
                /* PASO 1: Ingresar Comentarios */
                <div className="flex flex-col gap-4">
                  <p className="text-xs text-slate-400">
                    Por favor, ingresa un comentario con los detalles de las tareas realizadas en este equipo. El sistema combinará estas notas con las acciones del terminal para compilar el reporte automático de IA.
                  </p>
                  
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase tracking-wider">¿Qué se hizo en esta PC? *</label>
                    <textarea
                      value={endSessionComment}
                      onChange={(e) => setEndSessionComment(e.target.value)}
                      placeholder="Ej: Se destrabó spooler fiscal y se borraron archivos corruptos de FoxPro..."
                      className="bg-slate-900/50 border border-white/5 rounded-2xl p-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-brand-500 h-28 resize-none transition-all placeholder:text-slate-600"
                    />
                  </div>

                  <div className="flex gap-3 mt-4">
                    <button
                      type="button"
                      onClick={() => setShowEndSessionModal(false)}
                      className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white transition-colors"
                    >
                      Volver
                    </button>
                    <button
                      type="button"
                      disabled={isFinishingSession || !endSessionComment.trim()}
                      onClick={() => handleEndSessionSupport(session.id)}
                      className="flex-1 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white font-extrabold py-3 rounded-2xl shadow-lg transition-all text-sm uppercase tracking-wider flex items-center justify-center gap-2"
                    >
                      {isFinishingSession ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                          Generando...
                        </>
                      ) : (
                        'Grabar y Generar Reporte'
                      )}
                    </button>
                  </div>
                </div>
              ) : (
                /* PASO 2: Mostrar reporte finalizado y reporte de IA */
                <div className="flex flex-col gap-4">
                  <div className="bg-emerald-500/10 border border-emerald-500/20 p-4 rounded-2xl text-center">
                    <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                    <h4 className="text-sm font-black text-emerald-400 uppercase tracking-wider">¡Sesión Cerrada con Éxito!</h4>
                    <p className="text-xs text-slate-400 mt-1">La bitácora y el análisis han sido almacenados de forma permanente.</p>
                  </div>

                  {endSessionResult.duration !== undefined && (
                    <div className="text-xs text-slate-500 text-center font-mono">
                      Duración total de conexión: <strong className="text-slate-300">{Math.round(endSessionResult.duration / 60)} minutos</strong>
                    </div>
                  )}

                  {endSessionResult.ai_report && (
                    <div className="bg-slate-900/50 border border-white/5 p-4 rounded-2xl flex flex-col gap-2">
                      <span className="text-indigo-400 font-black text-[10px] sm:text-xs uppercase tracking-widest flex items-center gap-1.5 mb-1">
                        <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" /> Reporte de Actividad Consolidado por IA
                      </span>
                      <div className="text-slate-300 text-xs sm:text-sm space-y-1 pl-1 font-sans leading-relaxed">
                        {endSessionResult.ai_report.split('\n').map((line: string, i: number) => {
                          if (line.trim().startsWith('*') || line.trim().startsWith('-')) {
                            return <div key={i} className="flex gap-1.5 items-start pl-1">
                              <span className="text-indigo-500 font-bold">•</span>
                              <span>{line.replace(/^[\*\-\s]+/, '')}</span>
                            </div>;
                          }
                          return <p key={i}>{line}</p>;
                        })}
                      </div>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => {
                      window.close();
                    }}
                    className="w-full bg-slate-800 hover:bg-slate-700 text-white font-extrabold py-3.5 rounded-2xl shadow-lg transition-all text-sm uppercase tracking-wider mt-4"
                  >
                    Salir y Cerrar Ventana
                  </button>
                </div>
              )}

            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden selection:bg-brand-500/30">
      {/* Backdrop traslúcido para móvil */}
      {isSidebarOpen && (
        <div 
          onClick={() => setIsSidebarOpen(false)}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[40] lg:hidden animate-in fade-in duration-200"
        />
      )}

      <aside className={`
        fixed lg:static inset-y-0 left-0 w-64 flex flex-col transition-all duration-300 border-r z-[50]
        ${darkMode ? 'glass-dark border-dark-border bg-slate-950/95' : 'glass border-slate-200 bg-white'}
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="h-[72px] flex items-center px-6 border-b border-opacity-10 border-white">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-400 to-orange-600 flex items-center justify-center text-white font-bold text-xl mr-3 shadow-lg shadow-brand-500/30">A</div>
          <span className="text-xl font-extrabold tracking-tight">
            <span className="text-slate-800 dark:text-white">Apollo</span>
            <span className="text-brand-500">Support</span>
          </span>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          {userProfile?.rol === 'reseller' ? (
            <>
              <div className="mb-4">
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Mi Panel</p>
                <NavItem icon={<Ticket size={20} />} text="Mis Pedidos" badge={tickets.length > 0 ? tickets.length.toString() : ""} active={activeTab === 'tickets'} onClick={() => { setActiveTab('tickets'); setSelectedArea(null); setIsSidebarOpen(false); }} />
                <NavItem icon={<Monitor size={20} />} text="Terminal Remota" active={activeTab === 'monitor'} onClick={() => { setActiveTab('monitor'); setIsSidebarOpen(false); }} />
                <NavItem icon={<Users size={20} />} text="Mis Clientes" active={activeTab === 'clients'} onClick={() => { setActiveTab('clients'); setIsSidebarOpen(false); }} />
              </div>
            </>
          ) : (
            <>
              <div className="mb-4">
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Vistas Principales</p>
                <NavItem icon={<Ticket size={20} />} text="Bandeja Unificada" badge={tickets.length > 0 ? tickets.length.toString() : ""} active={activeTab === 'tickets' && selectedArea === null} onClick={() => { setActiveTab('tickets'); setSelectedArea(null); setIsSidebarOpen(false); }} />
                <NavItem icon={<Monitor size={20} />} text="Terminal Remota" badge="En Vivo" active={activeTab === 'monitor'} onClick={() => { setActiveTab('monitor'); setIsSidebarOpen(false); }} />
                <NavItem icon={<Video size={20} />} text="Agenda" active={activeTab === 'agenda'} onClick={() => { setActiveTab('agenda'); setIsSidebarOpen(false); }} />
                <NavItem icon={<Users size={20} />} text="Base Clientes" active={activeTab === 'clients'} onClick={() => { setActiveTab('clients'); setIsSidebarOpen(false); }} />
              </div>

              <div className="mb-4">
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Sectores Operativos</p>
                {areas.map(area => (
                  <NavItem
                    key={area.id}
                    icon={<Folder size={18} className={selectedArea === area.id ? "text-brand-500" : "text-slate-400"} />}
                    text={area.nombre}
                    active={activeTab === 'tickets' && selectedArea === area.id}
                    onClick={() => { setActiveTab('tickets'); setSelectedArea(area.id); setIsSidebarOpen(false); }}
                  />
                ))}
              </div>

              <div className="mb-4">
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Control Interno</p>
                <NavItem icon={<Activity size={20} />} text="Plantel de Personal" active={activeTab === 'personnel'} onClick={() => { setActiveTab('personnel'); setIsSidebarOpen(false); }} />
                <NavItem icon={<CreditCard size={20} />} text="Revendedores" active={activeTab === 'resellers'} onClick={() => { setActiveTab('resellers'); setIsSidebarOpen(false); }} />
                <NavItem icon={<Smartphone size={20} />} text="Dispositivos Móviles" active={activeTab === 'android_devices'} onClick={() => { setActiveTab('android_devices'); setIsSidebarOpen(false); }} />
                <NavItem icon={<Clock size={20} />} text="Activaciones OL" active={activeTab === 'acti_pending'} onClick={() => { setActiveTab('acti_pending'); setIsSidebarOpen(false); }} />
                <NavItem icon={<CalendarDays size={20} />} text="Extensiones OL" active={activeTab === 'extensiones'} onClick={() => { setActiveTab('extensiones'); setIsSidebarOpen(false); }} />
              </div>

              <div className="mb-4">
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Diagnóstico</p>
                <NavItem icon={<Terminal size={20} />} text="Bitácora de Logs" active={activeTab === 'logs'} onClick={() => { setActiveTab('logs'); setIsSidebarOpen(false); }} />
              </div>

              <div>
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Sistema</p>
                <NavItem icon={<Sparkles size={20} />} text="IA Copiloto" badge="Beta" onClick={() => setIsSidebarOpen(false)} />
                <NavItem icon={<FileText size={20} />} text="Licencias" active={activeTab === 'licenses'} onClick={() => { setActiveTab('licenses'); setIsSidebarOpen(false); }} />
                <NavItem icon={<Settings size={20} />} text="Ajustes" active={activeTab === 'settings'} onClick={() => { setActiveTab('settings'); setIsSidebarOpen(false); }} />
              </div>
            </>
          )}
        </nav>

        <div className="p-4 border-t border-opacity-10 border-white relative group">
          <div 
            onClick={() => {
              setProfileForm({
                nombre: userProfile?.nombre || '',
                full_name: userProfile?.full_name || '',
                celular: userProfile?.celular || '',
                departamento: userProfile?.departamento || '',
                password: '',
                profile_picture: userProfile?.profile_picture || ''
              });
              setShowProfileModal(true);
            }}
            className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors border border-transparent hover:border-white/10 shadow-sm cursor-pointer"
          >
            {userProfile?.profile_picture ? (
              <img src={userProfile.profile_picture} alt="Avatar" className="w-10 h-10 rounded-full shadow-md border-2 border-brand-500/50 object-cover" />
            ) : (
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-400 to-orange-500 flex items-center justify-center text-white font-bold text-xs shadow-md border-2 border-brand-500/50 shrink-0">
                {(userProfile?.full_name || userProfile?.nombre || 'AG').substring(0, 2).toUpperCase()}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate text-slate-800 dark:text-white">{userProfile?.full_name || userProfile?.nombre || 'Agente'}</p>
              <p className="text-xs text-brand-500 font-medium truncate uppercase">{userProfile?.rol === 'reseller' ? 'Reseller' : userProfile?.rol === 'admin' ? 'Administrador' : userProfile?.rol || 'Soporte'} {userActivities(userProfile).length ? `| ${userActivities(userProfile).join(' · ')}` : (userProfile?.departamento ? `| ${userProfile.departamento}` : '')}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="absolute right-6 top-[28px] p-2 rounded-full hidden group-hover:flex bg-red-500 text-white shadow-lg animate-in fade-in zoom-in transition hover:bg-red-600">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col relative w-full bg-slate-50 dark:bg-dark-bg/95 transition-colors">
        <div className="absolute top-[-15%] left-[10%] w-[50%] h-[50%] bg-brand-500/10 rounded-full blur-[140px] pointer-events-none" />

        <header className={`h-[72px] flex items-center justify-between px-4 sm:px-8 border-b transition-colors duration-300 z-10 ${darkMode ? 'bg-dark-bg/50 border-dark-border backdrop-blur-md' : 'bg-white/60 border-slate-200 backdrop-blur-md'}`}>
          <div className="flex items-center gap-3 sm:gap-4 flex-1 min-w-0">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="lg:hidden p-2 rounded-xl border border-slate-200 dark:border-dark-border hover:bg-slate-100 dark:hover:bg-white/5 transition-all text-slate-600 dark:text-slate-300"
            >
              <Menu size={20} />
            </button>
            <div className={`flex items-center gap-2 px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl w-full max-w-[150px] sm:max-w-xs md:max-w-md lg:w-96 transition-all ring-1 focus-within:ring-2 focus-within:ring-brand-500 ${darkMode ? 'bg-dark-card/50 ring-dark-border shadow-inner' : 'bg-white ring-slate-200 shadow-sm'}`}>
              <Search size={16} className="text-slate-400 shrink-0" />
              <input 
                type="text" 
                placeholder="Buscador global..." 
                value={globalSearchTerm}
                onChange={e => {
                  const val = e.target.value;
                  setGlobalSearchTerm(val);
                  setClientSearchTerm(val);
                }}
                className="bg-transparent border-none outline-none w-full text-xs sm:text-sm font-medium placeholder:text-slate-400" 
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2.5 rounded-full bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border hover:border-brand-500/50 transition-all shadow-sm">
              <Bell size={18} className="text-slate-600 dark:text-slate-300" />
            </button>
            <button onClick={() => setDarkMode(!darkMode)} className="p-2.5 rounded-full bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border hover:border-brand-500/50 transition-all shadow-sm group">
              {darkMode ? <Sun size={18} className="text-amber-400 group-hover:scale-110" /> : <Moon size={18} className="text-indigo-500 group-hover:scale-110" />}
            </button>
          </div>
        </header>

        {toast && (
          <div className="fixed top-20 right-4 sm:right-8 z-[100] animate-in slide-in-from-right-full max-w-md">
            <div className={`${TOAST_META[toast.kind].bar} text-white px-5 py-4 rounded-2xl shadow-2xl flex items-start gap-3 border ${TOAST_META[toast.kind].border} ring-4 ${TOAST_META[toast.kind].ring}`}>
              {toast.kind === 'success' ? (
                <CheckCircle2 size={22} className="shrink-0 mt-0.5" />
              ) : toast.kind === 'error' ? (
                <AlertCircle size={22} className="shrink-0 mt-0.5" />
              ) : (
                <Bell size={22} className="shrink-0 mt-0.5" />
              )}
              <div className="min-w-0 flex-1">
                <p className="font-black text-sm uppercase tracking-tighter">{TOAST_META[toast.kind].title}</p>
                <p className="text-xs font-semibold opacity-95 leading-relaxed break-words">{toast.message}</p>
              </div>
              <button onClick={() => setToast(null)} className="shrink-0 hover:bg-white/20 p-1 rounded-full transition-colors"><X size={16} /></button>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-auto p-4 sm:p-8 z-10 relative">
          <div className="max-w-7xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-700">
            {activeTab === 'tickets' && (
              <>
                <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                  <div>
                    <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight">
                      {ticketsVista === 'historico'
                        ? 'Histórico de pedidos'
                        : selectedArea && /desarroll|programac/i.test(areas.find(a => a.id === selectedArea)?.nombre || '')
                          ? 'Pedidos a Programación'
                          : 'Análisis Operativo'}
                    </h1>
                    <p className="text-sm text-slate-400 mt-1">
                      {ticketsVista === 'historico'
                        ? 'Pedidos ya entregados / cerrados. No aparecen en la bandeja activa.'
                        : 'Atención carga pedidos. Programación resuelve → Atención entrega al cliente → Histórico.'}
                    </p>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                    <div className={`flex rounded-xl border p-1 ${darkMode ? 'border-dark-border bg-dark-card/40' : 'border-slate-200 bg-white'}`}>
                      <button
                        type="button"
                        onClick={() => setTicketsVista('activa')}
                        className={`px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-wider transition-all ${ticketsVista === 'activa' ? 'bg-brand-500 text-white' : 'text-slate-400 hover:text-slate-200'}`}
                      >
                        Activos
                      </button>
                      <button
                        type="button"
                        onClick={() => setTicketsVista('historico')}
                        className={`px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-wider transition-all ${ticketsVista === 'historico' ? 'bg-brand-500 text-white' : 'text-slate-400 hover:text-slate-200'}`}
                      >
                        Histórico
                      </button>
                    </div>
                    {ticketsVista === 'activa' && (
                      <button onClick={() => { setIsModalOpen(true); setNewOrigen('cliente'); setNewPedidoFiles([]); }} className="w-full sm:w-auto bg-brand-500 hover:bg-brand-600 text-white px-6 py-2.5 rounded-xl font-bold shadow-[0_0_15px_rgba(245,158,11,0.3)] transition-all hover:-translate-y-1 text-center text-xs sm:text-sm">
                        + Pedido a Programación
                      </button>
                    )}
                  </div>
                </div>

                <div className={`rounded-2xl border p-1 shadow-sm ${darkMode ? 'glass-dark border-dark-border' : 'bg-white border-slate-200'}`}>
                  <div className="p-5 pb-0"><h2 className="text-lg font-bold">{ticketsVista === 'historico' ? 'Cerrados / entregados' : 'Solicitudes Recientes'}</h2></div>
                  <div className="p-4 mt-2">
                    <div className="hidden md:grid grid-cols-12 gap-4 pb-3 border-b border-slate-100 dark:border-dark-border/50 text-xs font-bold text-slate-400 tracking-wider uppercase">
                      <div className="col-span-1 pl-2">ID</div>
                      <div className="col-span-1">Origen</div>
                      <div className="col-span-2">Empresa / Pedido</div>
                      <div className="col-span-2">Asunto</div>
                      <div className="col-span-1">Estado</div>
                      <div className="col-span-1">Fecha</div>
                      <div className="col-span-2">Registró</div>
                      <div className="col-span-2">Dirigido a</div>
                    </div>
                    <div className="space-y-1 mt-2 min-h-[150px]">
                      {loading ? <div className="flex justify-center p-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500"></div></div> :
                        tickets.length === 0 ? <div className="text-center p-8 text-slate-400">No hay pedidos en esta bandeja.</div> :
                          tickets.map((t: any) => {
                            const c = t.cliente || clients.find(cl => cl.id === t.client_id);
                            const isInternal = (t.origen || 'cliente') === 'interno';
                            return (
                              <div key={t.id} onClick={() => openTicketModal({ ...t, clientName: isInternal ? (c?.razon_social || 'Pedido interno') : (c?.razon_social || 'Sin cliente') })}>
                                <TicketRow
                                  id={`#${t.id}`}
                                  origen={t.origen || 'cliente'}
                                  client={isInternal ? (c ? `${c.razon_social} · interno` : 'Pedido interno') : (c ? c.razon_social : 'Sin cliente')}
                                  subject={t.asunto}
                                  status={t.estado}
                                  priority={t.prioridad}
                                  createdAt={t.fecha_creacion}
                                  assignee={t.asignado_a?.full_name || t.asignado_a?.nombre || ''}
                                  registeredBy={ticketRegisteredBy(t)}
                                  hasAttachments={(t.intervenciones || []).some((inv: any) => inv.adjunto_url)}
                                  darkMode={darkMode}
                                />
                              </div>
                            )
                          })}
                    </div>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'agenda' && (
              <AgendaPanel
                darkMode={darkMode}
                clients={clients}
                users={users}
                currentUserId={userProfile?.id}
                onlineDeviceIds={Object.keys(centinelas || {}).map(Number).filter(n => !Number.isNaN(n))}
                onNotify={(msg) => {
                  setShowNotification(msg);
                  setTimeout(() => setShowNotification(null), 3500);
                }}
              />
            )}

            {activeTab === 'monitor' && (
              <div className="space-y-8 animate-in slide-in-from-bottom-8">
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <h1 className="text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      Flota de Terminales <span className="relative flex h-4 w-4"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500"></span></span>
                    </h1>
                    <p className="text-slate-400 mt-2">Visor maestro de las computadoras registradas por cliente.</p>
                  </div>
                  <label className="shrink-0 cursor-pointer bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-100 text-xs font-black uppercase tracking-wider px-4 py-2.5 rounded-xl">
                    Importar TeamViewer
                    <input
                      type="file"
                      accept=".csv,.txt,text/csv"
                      className="hidden"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        e.target.value = '';
                        if (!file) return;
                        try {
                          const res = await importTeamviewerCsv(file);
                          const lines = [
                            `PCs nuevas: ${res.creadas ?? 0}`,
                            `Actualizadas: ${res.actualizadas ?? 0}`,
                            `Sin cliente en Support: ${res.sin_cliente ?? 0}`,
                          ];
                          const detail = (res.sin_cliente_detalle || []).slice(0, 12)
                            .map((r: any) => `Fila ${r.fila}: ${r.equipo} (${r.grupo || 'sin grupo'}) — ${r.motivo}`)
                            .join('\n');
                          alert(detail ? `${lines.join('\n')}\n\n${detail}` : lines.join('\n'));
                          loadData();
                        } catch (err: any) {
                          alert(err?.message || 'No se pudo importar el CSV');
                        }
                      }}
                    />
                  </label>
                </div>

                {pendingDevices && pendingDevices.length > 0 && (
                  <div className="p-6 rounded-[2rem] bg-gradient-to-br from-indigo-500/10 via-purple-500/5 to-transparent border border-indigo-500/20 shadow-2xl space-y-4 animate-in zoom-in-95">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="relative flex h-3 w-3">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
                        </span>
                        <h2 className="text-lg font-black text-indigo-400">🚨 Terminales en Espera de Licencia ({pendingDevices.length})</h2>
                      </div>
                      <span className="text-xs font-bold text-slate-500 bg-slate-500/10 px-3 py-1 rounded-full uppercase">Autodetectado</span>
                    </div>
                    <p className="text-xs text-slate-400">
                      Estas terminales han iniciado el agente Centinela por primera vez sin configurar una clave de licencia. Puedes asignarlas a un cliente de inmediato para activarlas de forma remota y sin intervención del usuario.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
                      {pendingDevices.map((dev: any) => (
                        <div key={dev.id} className="p-4 rounded-2xl border border-indigo-500/20 bg-slate-900/60 flex flex-col gap-3 hover:border-indigo-500/40 transition-all group">
                          {/* Cabecera: nombre + botones */}
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <span className="text-[10px] font-extrabold text-indigo-400 uppercase tracking-widest block">Nombre del Equipo</span>
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-black text-white">{dev.device_name}</span>
                                {(dev.assist_id) && (
                                  <span className="text-[11px] font-mono font-black text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded-lg border border-sky-500/20 shadow-sm" title="ID de asistencia (el que dicta el cliente)">
                                    ID: {formatAssistId(dev.assist_id)}
                                  </span>
                                )}
                                {!dev.assist_id && (
                                  <span className="text-[10px] font-mono text-slate-500 bg-slate-500/10 px-2 py-0.5 rounded-lg border border-slate-500/20" title="Sin ID de asistencia aún (reconectar agente)">
                                    #{dev.id}
                                  </span>
                                )}
                                {dev.remote_password && (
                                  <span className="text-[11px] font-mono font-black text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-lg border border-emerald-500/20 shadow-sm" title="PIN de Conexión">
                                    PIN: {dev.remote_password}
                                  </span>
                                )}
                                {dev.alt_remote_id && (
                                  <span className="text-[10px] font-mono text-slate-400 bg-slate-500/10 px-2 py-0.5 rounded-lg border border-slate-500/20" title="ID RustDesk / AnyDesk">
                                    RD: {dev.alt_remote_id}
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                onClick={() => {
                                  setAssignModal(dev);
                                  setAssignClientId("");
                                }}
                                className="bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-[10px] px-3 py-2 rounded-xl transition-all shadow-md shadow-indigo-600/10 whitespace-nowrap"
                              >
                                Asignar Licencia
                              </button>
                              <button
                                onClick={() => handleDeleteDevice(dev.id)}
                                className="p-2 rounded-xl bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white transition-all"
                                title="Rechazar / Eliminar"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>

                          {/* Info de identificación */}
                          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px]">
                            {/* Fecha de registro */}
                            {dev.last_seen && (
                              <div className="col-span-2 flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">🕐 Detectado:</span>
                                <span className="font-bold text-slate-300">
                                  {new Date(dev.last_seen).toLocaleString('es-AR', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})}
                                </span>
                              </div>
                            )}

                            {/* Sistema operativo */}
                            {(dev.system_info?.windows_name || dev.os) && (
                              <div className="col-span-2 flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">🪟</span>
                                <span className="font-semibold text-slate-300 truncate">{dev.system_info?.windows_name || dev.os}</span>
                                {dev.system_info?.windows_build && (
                                  <span className="text-slate-500 ml-1">Build {dev.system_info.windows_build}</span>
                                )}
                              </div>
                            )}

                            {/* Usuario logueado */}
                            {dev.system_info?.logged_user && (
                              <div className="col-span-2 flex items-center gap-1">
                                <span className="text-slate-500">👤</span>
                                <span className="font-bold text-cyan-400">{dev.system_info.user_full || dev.system_info.logged_user}</span>
                              </div>
                            )}

                            {/* CPU y RAM en vivo */}
                            {(dev.cpu !== null && dev.cpu !== undefined) && (
                              <div className="flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">⚡</span>
                                <span>CPU <span className="font-bold text-white">{dev.cpu}%</span></span>
                              </div>
                            )}
                            {(dev.ram !== null && dev.ram !== undefined) && (
                              <div className="flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">🧠</span>
                                <span>RAM <span className="font-bold text-white">{dev.ram}%</span></span>
                              </div>
                            )}

                            {/* Último Windows Update */}
                            {dev.system_info?.last_windows_update && dev.system_info.last_windows_update !== 'No disponible' && (
                              <div className="col-span-2 flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">🔄 Último update:</span>
                                <span className="font-bold text-amber-400">{dev.system_info.last_windows_update}</span>
                              </div>
                            )}

                            {/* IPs */}
                            {dev.system_info?.network_ips && dev.system_info.network_ips.length > 0 && (
                              <div className="col-span-2 flex flex-wrap gap-1 mt-0.5">
                                {dev.system_info.network_ips.slice(0, 3).map((n: any, i: number) => (
                                  <span key={i} className="font-mono text-[9px] bg-slate-800 text-emerald-400 px-1.5 py-0.5 rounded-md border border-slate-700">
                                    {n.ip}
                                  </span>
                                ))}
                              </div>
                            )}

                            {/* Propuesta de cliente por serial */}
                            {dev.proposed_client && (
                              <div className="col-span-2 flex items-center gap-1 mt-1 bg-indigo-500/10 border border-indigo-500/20 rounded-lg px-2 py-1">
                                <span className="text-indigo-400 text-[10px]">💡 Posible cliente:</span>
                                <span className="font-extrabold text-indigo-300 text-[10px]">{dev.proposed_client.razon_social}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {clients.filter(client => {
                    if (!globalSearchTerm) return true;
                    const term = globalSearchTerm.toLowerCase();
                    const matchSocial = client.razon_social?.toLowerCase().includes(term);
                    const matchFantasia = client.nombre_fantasia?.toLowerCase().includes(term);
                    const matchLocalidad = client.localidad?.toLowerCase().includes(term);
                    const matchCodigo = client.codigo?.toLowerCase().includes(term);
                    const matchFac = client.cclifac?.toLowerCase().includes(term);
                    return matchSocial || matchFantasia || matchLocalidad || matchCodigo || matchFac;
                  }).sort((a, b) => {
                    const aMaxSeen = a.devices && a.devices.length > 0
                      ? Math.max(...a.devices.map((d: any) => d.last_support_date ? new Date(d.last_support_date).getTime() : 0))
                      : 0;
                    const bMaxSeen = b.devices && b.devices.length > 0
                      ? Math.max(...b.devices.map((d: any) => d.last_support_date ? new Date(d.last_support_date).getTime() : 0))
                      : 0;
                    return bMaxSeen - aMaxSeen; // Descending (newest activity first)
                  }).map(client => {
                    const sortedDevices = [...(client.devices || [])].sort((da, db) => {
                      const daOnline = centinelas[da.id] ? 1 : 0;
                      const dbOnline = centinelas[db.id] ? 1 : 0;
                      if (daOnline !== dbOnline) return dbOnline - daOnline;
                      const daSeen = da.last_seen ? new Date(da.last_seen).getTime() : 0;
                      const dbSeen = db.last_seen ? new Date(db.last_seen).getTime() : 0;
                      return dbSeen - daSeen;
                    });

                    const clientLic = licenses.find(lic => lic.client_id === client.id);

                    return (
                      <div key={client.id} className={`p-6 rounded-[2rem] border shadow-2xl ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'}`}>
                        <h3 className="text-xl font-black mb-4 flex items-center justify-between text-brand-500">
                          {client.razon_social}
                          <span className="text-[10px] bg-brand-500/10 px-3 py-1 rounded-full uppercase tracking-widest">{client.devices?.length || 0} PCs</span>
                        </h3>

                        <div className="flex items-center gap-2 mb-3 -mt-2">
                          {clientLic ? (
                            <div className="flex items-center gap-2 bg-brand-500/10 text-brand-500 border border-brand-500/20 px-3 py-1.5 rounded-2xl text-xs font-mono select-all hover:bg-brand-500/20 transition-all cursor-pointer shadow-sm" title="Doble clic o clic largo para copiar clave">
                              🔑 <span className="font-extrabold tracking-wider">{clientLic.license_key}</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5 bg-slate-500/10 text-slate-400 border border-slate-500/25 px-3 py-1.5 rounded-2xl text-[10px] font-black uppercase tracking-wider">
                              Sin Clave Soporte
                            </div>
                          )}
                        </div>

                        {/* Fila de Acciones de Gestión de Cliente (Siempre Visibles, Altamente Responsivas) */}
                        <div className="grid grid-cols-2 gap-2 mb-4">
                          {/* Botón Ver Extracto (Siempre Visible, Deshabilitado si no posee cclifac) */}
                          <button
                            onClick={() => {
                              if (!client.cclifac) {
                                alert(`El cliente ${client.razon_social} no posee un código de facturación (CCLIFAC) configurado en el sistema.`);
                                return;
                              }
                              handleOpenExtracto(client);
                            }}
                            className={`flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-2xl text-xs font-black transition-all border ${
                              client.cclifac
                                ? 'bg-indigo-500/10 hover:bg-indigo-500/25 text-indigo-400 border-indigo-500/20 hover:border-indigo-500/40 cursor-pointer shadow-sm hover:-translate-y-0.5'
                                : 'bg-slate-500/5 text-slate-500 border-slate-500/10 cursor-not-allowed opacity-40'
                            }`}
                            title={client.cclifac ? "Ver Extracto de Cuenta Corriente en Tiempo Real" : "No posee código de vinculación de facturación (CCLIFAC)"}
                          >
                            <FileText size={13} />
                            <span>Extracto ERP</span>
                          </button>

                          {/* Botón Administrar Activaciones/Licencias ERP (Siempre Visible y Activo) */}
                          <button
                            onClick={() => {
                              openClientModal(client);
                              setClientActiveTab('erp_licensing');
                            }}
                            className="flex items-center justify-center gap-1.5 px-3 py-2.5 bg-brand-500/10 hover:bg-brand-500/25 text-brand-500 border border-brand-500/20 hover:border-brand-500/40 rounded-2xl text-xs font-black transition-all shadow-sm cursor-pointer hover:-translate-y-0.5"
                            title="Gestionar Licencias, Seriales y Activaciones ERP"
                          >
                            <Key size={13} />
                            <span>Licencias ERP</span>
                          </button>
                        </div>

                        <div className="space-y-2">
                          {(!sortedDevices || sortedDevices.length === 0) ? (
                            <p className="text-xs text-slate-500 italic p-4 text-center">Sin dispositivos registrados aún.</p>
                          ) : (
                            sortedDevices.map((dev: any) => {
                              const telemetry = centinelas[dev.id];
                              const isOnline = !!telemetry;
                              const isBusy = dev.current_technician_id !== null;

                              return (
                                <div key={dev.id} className={`p-4 rounded-2xl border transition-all flex flex-col gap-3 ${isOnline ? (isBusy ? 'bg-amber-500/5 border-amber-500/20' : 'bg-emerald-500/5 border-emerald-500/20') : 'bg-slate-500/5 border-slate-500/10 grayscale opacity-70'}`}>
                                  <div className="flex items-start gap-3 min-w-0">
                                    <div className={`w-3 h-3 rounded-full flex-shrink-0 mt-1 ${isOnline ? (isBusy ? 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.4)]' : 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]') : 'bg-slate-400'}`} />
                                    <div className="min-w-0 flex-1">
                                      <div className="text-sm font-extrabold flex items-center gap-2 flex-wrap">
                                        {dev.device_name}
                                        {(dev.assist_id || telemetry?.assist_id) ? (
                                          <span className="text-[10px] font-mono bg-sky-500/10 text-sky-400 px-2 py-0.5 rounded-full border border-sky-500/20" title="ID de asistencia">
                                            ID {formatAssistId(dev.assist_id || telemetry?.assist_id)}
                                          </span>
                                        ) : null}
                                        {dev.alt_remote_id && (
                                          <span className="text-[9px] font-mono text-slate-500 bg-slate-500/10 px-1.5 py-0.5 rounded-full border border-slate-500/20" title="RustDesk / AnyDesk">
                                            RD {dev.alt_remote_id}
                                          </span>
                                        )}
                                        {(telemetry?.remote_password || dev.remote_password) && (
                                          <span className="text-[10px] font-mono bg-brand-500/10 text-brand-500 px-2.5 py-0.5 rounded-full flex items-center gap-1 shadow-sm">🔑 {telemetry?.remote_password || dev.remote_password}</span>
                                        )}
                                      </div>
                                      <div className="flex items-center gap-2 text-[9px] uppercase font-bold text-slate-500">
                                        {isOnline ? (
                                          <>CPU: {telemetry?.cpu || 0}% | RAM: {telemetry?.ram || 0}% {telemetry?.agent_version && <span className="text-amber-500 font-extrabold ml-1">V{telemetry.agent_version}</span>}</>
                                        ) : 'Desconectado'}
                                      </div>
                                      {/* Info extendida del sistema — viene de system_info en telemetría */}
                                      {isOnline && telemetry?.system_info && (
                                        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5">
                                          {telemetry.system_info.logged_user && (
                                            <span className="text-[9px] text-cyan-400 font-bold">
                                              👤 {telemetry.system_info.user_full || telemetry.system_info.logged_user}
                                            </span>
                                          )}
                                          {telemetry.system_info.windows_name && (
                                            <span className="text-[9px] text-slate-400 font-semibold">
                                              🪟 {telemetry.system_info.windows_name}
                                            </span>
                                          )}
                                          
                                            {telemetry.system_info.last_windows_update && telemetry.system_info.last_windows_update !== 'No disponible' && (
                                              <span className="text-[9px] text-amber-400 font-semibold">
                                                🗓️ Update: {telemetry.system_info.last_windows_update}
                                              </span>
                                            )}
                                          </div>
                                        )}
                                        {/* OTA PROGRESS Y BOTON */}
                                        {isOnline && (
                                          <div className="mt-1 w-full pr-4">
                                            {telemetry?.ota_status && (
                                              <>
                                                <div className="flex justify-between items-center text-[9px] text-amber-500 font-bold mb-1 uppercase">
                                                  <span>Actualización OTA: {telemetry.ota_status}</span>
                                                  <span>{telemetry.ota_progress}%</span>
                                                </div>
                                                <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                                  <div className="bg-amber-500 h-1.5 transition-all" style={{ width: `${telemetry.ota_progress}%` }}></div>
                                                </div>
                                              </>
                                            )}
                                            {telemetry?.agent_version && !telemetry?.ota_status && (
                                              <button
                                                onClick={async (e) => {
                                                  e.stopPropagation();
                                                  if (window.confirm(`¿Forzar actualización OTA en ${dev.device_name}?`)) {
                                                    try {
                                                      await forceCentinelaUpdate(dev.id);
                                                      alert('Comando OTA enviado. Verás el progreso en breve.');
                                                    } catch (err) {
                                                      alert('Error al forzar OTA');
                                                    }
                                                  }
                                                }}
                                                className="mt-1 flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-lg bg-amber-500/10 text-amber-500 hover:bg-amber-500 hover:text-white transition-colors"
                                                title="Forzar actualización OTA ahora"
                                              >
                                                <ArrowUpRight size={10} /> Forzar Actualización OTA
                                              </button>
                                            )}
                                          </div>
                                        )}

                                      {renderLastErpUpdate(dev.last_erp_update, telemetry)}
                                    </div>
                                  </div>

                                  {isBusy && (
                                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[9px] px-1">
                                      <span className="font-black text-amber-500 uppercase tracking-widest">Ocupado por</span>
                                      <span className="font-extrabold text-amber-400">{dev.technician_name || 'Técnico'}</span>
                                      <span className="font-bold text-slate-400">
                                        hace {Math.floor((new Date().getTime() - new Date(dev.session_start).getTime()) / 60000)}m
                                      </span>
                                    </div>
                                  )}

                                  <div className="flex flex-wrap items-center gap-1.5 justify-end border-t border-white/5 pt-2">
                                  <button
                                    onClick={() => setDeviceNotesModal({ deviceId: dev.id, name: dev.device_name, notes: dev.notes || "" })}
                                    className={`p-2 rounded-lg transition-all shadow-sm ${
                                      dev.notes
                                        ? 'bg-purple-500/20 text-purple-400 hover:bg-purple-500 hover:text-white border border-purple-500/30'
                                        : 'bg-slate-500/10 hover:bg-slate-500 text-slate-400 hover:text-white border border-transparent'
                                    }`}
                                    title="Notas y Recordatorios (Claves Windows, etc.)"
                                  >
                                    <FileText size={14} />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleReleaseDeviceSession(dev.id, dev.device_name);
                                    }}
                                    className={`p-2 rounded-lg transition-all shadow-sm ${
                                      isBusy
                                        ? 'bg-amber-500/20 text-amber-400 hover:bg-amber-500 hover:text-white border border-amber-500/30'
                                        : 'bg-slate-500/10 text-slate-400 hover:bg-amber-500/20 hover:text-amber-300 border border-transparent'
                                    }`}
                                    title="Liberar sesión colgada (quita Ocupado por...)"
                                  >
                                    <Unlock size={14} />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleForceRefreshDevice(dev.id, dev.device_name);
                                    }}
                                    disabled={!isOnline}
                                    className={`p-2 rounded-lg transition-all shadow-sm ${
                                      isOnline
                                        ? 'bg-sky-500/10 text-sky-400 hover:bg-sky-500 hover:text-white border border-sky-500/20'
                                        : 'bg-slate-200 text-slate-400'
                                    }`}
                                    title="Forzar refresh del agente (pantalla negra / sin video)"
                                  >
                                    <RefreshCw size={14} />
                                  </button>
                                  <button
                                    onClick={() => {
                                      if (isOnline) {
                                        handleVerifyRemotePassword(dev.id, telemetry?.remote_password || dev.remote_password || "");
                                      }
                                    }}
                                    disabled={!isOnline}
                                    className={`p-2 rounded-lg transition-all ${isOnline ? 'bg-brand-500 text-white hover:bg-brand-600 shadow-lg shadow-brand-500/20' : 'bg-slate-200 text-slate-400'}`}
                                    title="Conectar control remoto"
                                  >
                                    <Monitor size={14} />
                                  </button>
                                  <button
                                    onClick={() => handleDeleteDevice(dev.id)}
                                    className="p-2 rounded-lg bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white transition-all shadow-sm"
                                    title="Eliminar dispositivo (libera cupo)"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              </div>
            )}

            {activeTab === 'clients' && (
              <>
                <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                  <div>
                    <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight">Base Maestra de Clientes</h1>
                    <p className="text-xs sm:text-sm text-slate-400 mt-2">Gestión centralizada de licencias y empresas ApolloGesCom.</p>
                  </div>
                  <div className="flex gap-3 w-full sm:w-auto">
                    <button
                      onClick={async () => {
                        setIsSyncing(true);
                        try {
                          // Solo saldos ERP (Clientes:CSaldo). NO pide CLIGESCO.DBF en el servidor.
                          const res = await syncSaldosFromErp();
                          const n = res?.updated;
                          setShowNotification(
                            n != null
                              ? `Sync OK: ${n} saldos desde Clientes:CSaldo`
                              : "¡Saldos ERP actualizados!"
                          );
                          setTimeout(() => setShowNotification(null), 4000);
                          loadData();
                        } catch (err: any) {
                          alert(err.message || "Error al sincronizar");
                        } finally {
                          setIsSyncing(false);
                        }
                      }}
                      disabled={isSyncing}
                      className={`flex items-center justify-center gap-2 w-full sm:w-auto px-5 py-2.5 rounded-xl font-bold shadow-md transition-all text-xs sm:text-sm border ${darkMode ? 'bg-slate-900 border-white/10 text-slate-300 hover:bg-slate-800' : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'}`}
                    >
                      <Sparkles className={`w-4 h-4 text-brand-500 ${isSyncing ? 'animate-spin' : ''}`} />
                      {isSyncing ? 'Sincronizando...' : 'Sincronizar saldos ERP'}
                    </button>
                    <button onClick={() => openClientModal()} className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-2.5 rounded-xl font-bold shadow-lg transition-all hover:-translate-y-1 text-center text-xs sm:text-sm">
                      + Alta cliente
                    </button>
                  </div>
                </div>

                {/* Panel de Totalizadores */}
                <div className="flex mt-6 animate-in fade-in slide-in-from-top-4 duration-300">
                  {/* Card 1: Total Clientes Activos */}
                  <div className={`w-full sm:w-72 p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-slate-900/40 hover:bg-slate-900/60' : 'bg-white border-slate-200 hover:shadow-md hover:border-slate-300'}`}>
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Clientes Activos</p>
                        <h3 className="text-2xl sm:text-3xl font-extrabold text-slate-800 dark:text-white mt-2">
                          {clients.length}
                        </h3>
                      </div>
                      <div className={`p-3 rounded-xl ${darkMode ? 'bg-brand-500/10 text-brand-400' : 'bg-brand-50 text-brand-600'}`}>
                        <Users size={20} />
                      </div>
                    </div>
                    <div className="mt-4 flex items-center gap-1.5 text-xs text-slate-400">
                      <span className="font-semibold text-emerald-500">GesActi</span>
                      <span>alta, baja y «Sincronizar Support»</span>
                    </div>
                  </div>
                </div>

                <div className={`rounded-2xl border p-1 shadow-sm mt-6 ${darkMode ? 'glass-dark border-dark-border' : 'bg-white border-slate-200'}`}>
                  <div className="p-5 flex flex-col sm:flex-row gap-4 sm:items-center justify-between border-b dark:border-dark-border/50">
                    <h2 className="text-lg font-bold">Empresas Registradas</h2>
                    <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                      <div className="relative w-full sm:w-72">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                          type="text"
                          placeholder="Buscar por nombre, código, CUIT o localidad..."
                          value={clientSearchTerm}
                          onChange={e => setClientSearchTerm(e.target.value)}
                          className={`w-full pl-9 pr-4 py-2 rounded-xl text-sm border outline-none focus:ring-2 focus:ring-brand-500 ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50 border-slate-200'}`}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="px-5 py-3 flex flex-wrap gap-2 border-b dark:border-dark-border/50">
                    {(() => {
                      const visibleCodes = clients
                        .filter(c => {
                          const term = clientSearchTerm.toLowerCase();
                          const code4 = c.codigo ? String(c.codigo).trim().padStart(4, '0') : '';
                          const textOk = (
                            (c.razon_social || '').toLowerCase().includes(term) ||
                            (c.nombre_fantasia || '').toLowerCase().includes(term) ||
                            (c.codigo || '').toLowerCase().includes(term) ||
                            (c.cclifac || '').toLowerCase().includes(term) ||
                            (c.identificador_fiscal || '').toLowerCase().includes(term) ||
                            (c.localidad || '').toLowerCase().includes(term) ||
                            (c.clasificacion_codigo || '').toLowerCase().includes(term) ||
                            (c.clasificacion_nombre || '').toLowerCase().includes(term)
                          );
                          return textOk && clientMatchesCartelFilter(code4) && clientMatchesEstadoFilter(c);
                        })
                        .map((c: any) => c.codigo ? String(c.codigo).trim().padStart(4, '0') : '')
                        .filter(Boolean);
                      const btn = `px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wide border transition-all ${darkMode ? 'border-white/10 bg-white/5 hover:bg-white/10 text-slate-200' : 'border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700'}`;
                      return (
                        <>
                          <button type="button" className={btn} onClick={() => setSelectedClientCodes(visibleCodes)} title="Marcar todos los filtrados">Todo</button>
                          <button type="button" className={btn} onClick={() => setSelectedClientCodes([])}>Nada</button>
                          <button type="button" className={btn} onClick={() => {
                            setSelectedClientCodes(prev => {
                              const set = new Set(prev);
                              return visibleCodes.filter(code => !set.has(code)).concat(prev.filter(code => !visibleCodes.includes(code) && set.has(code)));
                            });
                          }}>Invierte</button>
                          <select
                            value={cartelFilter}
                            onChange={e => setCartelFilter(e.target.value)}
                            title="Filtrar por tipo de cartel"
                            className={`${btn} max-w-[200px] normal-case font-bold`}
                          >
                            <option value="all">Cartel: todos</option>
                            <option value="con">Con cartel</option>
                            <option value="sin">Sin cartel</option>
                            {erpTemplates.filter((t: any) => Number(t.m_num ?? t.id) > 1).map((t: any) => (
                              <option key={t.m_num ?? t.id} value={String(t.m_num ?? t.id)}>
                                Tipo {t.m_num ?? t.id} — {t.m_des || t.label || 'Aviso'}
                              </option>
                            ))}
                          </select>
                          <select
                            value={estadoCtaFilter}
                            onChange={e => setEstadoCtaFilter(e.target.value)}
                            title="Filtrar por estado de cuenta corriente (ClasiCli)"
                            className={`${btn} max-w-[220px] normal-case font-bold`}
                          >
                            <option value="all">Estado Cta: todos</option>
                            <option value="sin">Sin estado</option>
                            {estadosCta.filter((e: any) => e.activo !== false).map((e: any) => (
                              <option key={e.codigo} value={normalizeEstadoCodigo(e.codigo)}>
                                {e.codigo} — {e.descripcion}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            className={`${btn} ${selectedClientCodes.length ? 'text-amber-400 border-amber-500/30' : 'opacity-50'}`}
                            disabled={selectedClientCodes.length === 0}
                            title="Cartel / corte completo (GesActi Monitoreo)"
                            onClick={() => {
                              if (selectedClientCodes.length === 0) return;
                              loadErpTemplates();
                              const tipFromFilter = /^\d+$/.test(cartelFilter) ? parseInt(cartelFilter, 10) : 1;
                              const modes = selectedClientCodes.flatMap(code => {
                                const s = licensePanelSummary[code] || {};
                                return Array.isArray(s.showmodes) && s.showmodes.length
                                  ? s.showmodes
                                  : (s.m_showmode ? [s.m_showmode] : []);
                              });
                              const uniqueModes = Array.from(new Set(modes.filter(Boolean)));
                              // Preferir demora única de los marcados; si mezclan, dejar 15s (03) como default operativo
                              const preferredMode = uniqueModes.length === 1
                                ? String(uniqueModes[0]).padStart(2, '0')
                                : (uniqueModes.includes('04') ? '04' : uniqueModes.includes('03') ? '03' : uniqueModes.includes('05') ? '05' : '03');
                              setBannerForm({
                                serial: '',
                                client_codes: selectedClientCodes,
                                m_down: false,
                                m_newdate: '',
                                m_tipmsg: tipFromFilter > 1 ? tipFromFilter : 1,
                                m_showmode: preferredMode,
                                m_text: ''
                              });
                              setShowBannerConfigModal(true);
                            }}
                          >
                            Monitoreo ({selectedClientCodes.length})
                          </button>
                          <button
                            type="button"
                            className={`${btn} ${selectedClientCodes.length ? 'text-emerald-400 border-emerald-500/30' : 'opacity-50'}`}
                            disabled={selectedClientCodes.length === 0}
                            title="Quitar cartel (m_tipmsg=1) a los marcados"
                            onClick={() => applyBulkCartelToMarked(1)}
                          >
                            Quitar carteles
                          </button>
                          <select
                            disabled={selectedClientCodes.length === 0}
                            defaultValue=""
                            title="Poner un tipo de cartel a los marcados"
                            className={`${btn} ${selectedClientCodes.length ? 'text-amber-300 border-amber-500/30' : 'opacity-50'} max-w-[220px] normal-case font-bold`}
                            onChange={e => {
                              const v = parseInt(e.target.value, 10);
                              e.target.value = '';
                              if (v > 1) applyBulkCartelToMarked(v);
                            }}
                          >
                            <option value="">Poner cartel a marcados…</option>
                            {erpTemplates.filter((t: any) => Number(t.m_num ?? t.id) > 1).map((t: any) => (
                              <option key={t.m_num ?? t.id} value={String(t.m_num ?? t.id)}>
                                {t.m_num ?? t.id} — {t.m_des || t.label || 'Aviso'}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            className={`${btn} text-amber-300`}
                            title="Catálogo de carteles de aviso (misi_messages)"
                            onClick={() => {
                              loadErpTemplates();
                              setAvisoEdit({ m_num: 0, m_des: '', m_text: '' });
                              setShowAvisosCatalog(true);
                            }}
                          >
                            Catálogo
                          </button>
                          <button
                            type="button"
                            className={`${btn} text-teal-300`}
                            title="ABM Estados de Cuenta Corriente (ClasiCli ERP)"
                            onClick={() => {
                              loadEstadosCta(false);
                              setEstadoCtaEdit({ codigo: '', descripcion: '', activo: true });
                              setShowEstadosCtaModal(true);
                            }}
                          >
                            Estados Cta
                          </button>
                          <span className="text-[10px] text-slate-500 self-center ml-auto font-mono">
                            {selectedClientCodes.length} marcados · {visibleCodes.length} visibles
                          </span>
                        </>
                      );
                    })()}
                  </div>
                  <div className="p-4">
                    <div className="hidden md:grid grid-cols-12 gap-3 pb-3 border-b border-slate-100 dark:border-dark-border/50 text-xs font-bold text-slate-400 tracking-wider uppercase">
                      <div className="col-span-1 pl-2">Sel / Cód.</div>
                      <div className="col-span-2">Razón Social / Fantasía</div>
                      <div className="col-span-2"># Lic / Cortado / Cartel · demora</div>
                      <div className="col-span-1">Estado Cta</div>
                      <div className="col-span-1 text-right">Saldo ERP</div>
                      <div className="col-span-1 text-right">Últ. Pago</div>
                      <div className="col-span-2">CUIT / Email</div>
                      <div className="col-span-2 text-right pr-2">Acciones</div>
                    </div>
                    <div className="space-y-2 mt-2">
                      {clients
                        .filter(c => {
                          const term = clientSearchTerm.toLowerCase();
                          const code4 = c.codigo ? String(c.codigo).trim().padStart(4, '0') : '';
                          const textOk = (
                            (c.razon_social || '').toLowerCase().includes(term) ||
                            (c.nombre_fantasia || '').toLowerCase().includes(term) ||
                            (c.codigo || '').toLowerCase().includes(term) ||
                            (c.cclifac || '').toLowerCase().includes(term) ||
                            (c.identificador_fiscal || '').toLowerCase().includes(term) ||
                            (c.localidad || '').toLowerCase().includes(term) ||
                            (c.clasificacion_codigo || '').toLowerCase().includes(term) ||
                            (c.clasificacion_nombre || '').toLowerCase().includes(term)
                          );
                          return textOk && clientMatchesCartelFilter(code4) && clientMatchesEstadoFilter(c);
                        })
                        .map((c: any) => {
                          const isExpired = c.fecha_vencimiento && new Date(c.fecha_vencimiento) < new Date();
                          const formattedSaldo = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(c.saldo || 0);
                          const isSaldoPendiente = (c.saldo || 0) > 0;
                          
                          const code4 = c.codigo ? String(c.codigo).trim().padStart(4, '0') : '';
                          const licSum = licensePanelSummary[code4] || licensePanelSummary[c.codigo] || {};
                          const isMarked = selectedClientCodes.includes(code4);
                          const tipLabel = licSum.cartel
                            ? `${licSum.m_tipmsg || '?'}${licSum.m_tipmsg_des ? ` · ${String(licSum.m_tipmsg_des).slice(0, 14)}` : ''}`
                            : '—';
                          const demoraModes: string[] = Array.isArray(licSum.showmodes) && licSum.showmodes.length
                            ? licSum.showmodes
                            : (licSum.m_showmode ? [licSum.m_showmode] : []);
                          const demoraLabel = licSum.cartel
                            ? (demoraModes.length
                              ? Array.from(new Set(demoraModes.map((m: string) => formatShowmodeLabel(m)).filter(Boolean))).join('/')
                              : '—')
                            : '';
                          
                          return (
                            <div key={c.id} className={`
                              flex flex-col md:grid md:grid-cols-12 gap-3 md:gap-3 p-4 md:p-3.5 rounded-2xl items-start md:items-center
                              ${isMarked ? (darkMode ? 'bg-amber-500/10 border border-amber-500/20' : 'bg-amber-50 border border-amber-200') : ''}
                              ${!isMarked && (darkMode ? 'hover:bg-slate-800/60 bg-white/[0.01] border border-white/5 md:border-transparent md:bg-transparent' : 'hover:bg-slate-50 bg-slate-50/50 border border-slate-100 md:border-transparent md:bg-transparent')}
                              w-full
                            `}>
                              <div className="flex justify-between items-center w-full md:w-auto md:col-span-1">
                                <div className="flex items-center gap-2">
                                  <input
                                    type="checkbox"
                                    checked={isMarked}
                                    onChange={() => {
                                      setSelectedClientCodes(prev => isMarked ? prev.filter(x => x !== code4) : [...prev, code4]);
                                    }}
                                    className="w-4 h-4 accent-amber-500 cursor-pointer"
                                    title="Marcar para Monitoreo (como ENTER en GesActi)"
                                  />
                                  <div className="flex flex-col items-start gap-0.5">
                                  <span className="text-[10px] font-mono font-bold bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400 px-1.5 py-0.5 rounded" title="Código de Cliente ERP">
                                    {c.codigo || `-`}
                                  </span>
                                  {c.cclifac && (
                                    <span className="text-[9px] font-mono font-black text-brand-500 bg-brand-500/10 px-1.5 py-0.2 rounded" title="Código de Relación Facturación">
                                      {c.cclifac}
                                    </span>
                                  )}
                                </div>
                                </div>
                                <span className="md:hidden text-[9px] font-bold px-2 py-0.5 rounded bg-brand-500/10 text-brand-500">CLIENTE</span>
                              </div>
                              <div className="md:col-span-2 truncate w-full">
                                <div className="text-sm font-bold text-slate-800 dark:text-white leading-tight truncate" title={c.razon_social}>
                                  {c.razon_social}
                                </div>
                                <div className="flex items-center gap-2 mt-0.5">
                                  {c.nombre_fantasia && (
                                    <span className="text-[10px] text-slate-400 font-medium truncate max-w-[150px]">
                                      {c.nombre_fantasia}
                                    </span>
                                  )}
                                  {c.localidad && (
                                    <span className="text-[9px] bg-brand-500/10 text-brand-500 font-bold px-1.5 py-0.2 rounded uppercase">
                                      {c.localidad}
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div className="flex flex-col md:block md:col-span-2 gap-1 w-full">
                                <span className="md:hidden text-[10px] font-bold text-slate-400 uppercase">Licencias GesActi:</span>
                                <div className="flex flex-wrap items-center gap-1.5 md:justify-start">
                                  <span className="text-[10px] font-mono font-black text-slate-600 dark:text-slate-300" title="Cantidad de seriales">
                                    {licSum.lic_total != null ? licSum.lic_total : '—'} lic
                                  </span>
                                  <span
                                    className={`text-[9px] font-black px-1.5 py-0.5 rounded uppercase ${licSum.cortado ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-slate-100 dark:bg-white/5 text-slate-500'}`}
                                    title={licSum.lic_cortadas ? `${licSum.lic_cortadas} seriales con m_down` : 'Sin corte'}
                                  >
                                    {licSum.cortado ? 'Cortado' : 'Ok'}
                                  </span>
                                  <span
                                    className={`text-[9px] font-black px-1.5 py-0.5 rounded uppercase max-w-[140px] truncate ${licSum.cartel ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'bg-slate-100 dark:bg-white/5 text-slate-500'}`}
                                    title={
                                      licSum.cartel
                                        ? `Tipo ${licSum.m_tipmsg}${licSum.m_tipmsg_des ? ` — ${licSum.m_tipmsg_des}` : ''} · ${licSum.lic_cartel || 0} serial(es)`
                                          + (Array.isArray(licSum.tipmsgs) && licSum.tipmsgs.length > 1 ? ` · tipos: ${licSum.tipmsgs.join(', ')}` : '')
                                          + (demoraLabel ? ` · demora: ${demoraLabel}` : '')
                                        : 'Sin cartel'
                                    }
                                  >
                                    {tipLabel}
                                  </span>
                                  {licSum.cartel && demoraLabel && (
                                    <span
                                      className="text-[9px] font-black px-1.5 py-0.5 rounded font-mono bg-sky-500/15 text-sky-300 border border-sky-500/25"
                                      title={`Modo de muestra (m_showmode): ${demoraModes.join(', ')} — uso habitual 15/30/180 s`}
                                    >
                                      {demoraLabel}
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div className="flex justify-between items-center w-full md:block md:col-span-1 mt-1 md:mt-0">
                                <span className="md:hidden text-[10px] font-bold text-slate-400 uppercase">Estado Cta:</span>
                                {c.clasificacion_codigo || c.clasificacion_nombre ? (
                                  <div className="min-w-0">
                                    <div className="text-[10px] font-mono font-black text-teal-400 truncate" title={c.clasificacion_codigo}>
                                      {normalizeEstadoCodigo(c.clasificacion_codigo) || '—'}
                                    </div>
                                    <div className="text-[9px] text-slate-400 truncate max-w-[110px]" title={c.clasificacion_nombre || ''}>
                                      {c.clasificacion_nombre || '—'}
                                    </div>
                                  </div>
                                ) : (
                                  <span className="text-[10px] text-slate-500">—</span>
                                )}
                              </div>
                              <div className="flex justify-between items-center w-full md:block md:col-span-1 md:text-right mt-1 md:mt-0">
                                <span className="md:hidden text-[10px] font-bold text-slate-400 uppercase font-mono">Saldo:</span>
                                <div className="flex items-center gap-1.5 md:justify-end">
                                  <div className={`text-sm font-black font-mono leading-tight ${isSaldoPendiente ? 'text-rose-500 dark:text-rose-400' : 'text-emerald-500 dark:text-emerald-400'}`}>
                                    {formattedSaldo}
                                  </div>
                                  <button
                                    onClick={async (e) => {
                                      e.stopPropagation();
                                      if (!c.cclifac) {
                                        alert("Este cliente no posee código de facturación (CCLIFAC) del ERP.");
                                        return;
                                      }
                                      try {
                                        const res = await getClientBalance(c.id);
                                        setClients(prev => prev.map(cl => cl.id === c.id ? { ...cl, saldo: res.saldo_real_erp, fecha_ultimo_pago: res.fecha_ultimo_pago ?? cl.fecha_ultimo_pago } : cl));
                                        setShowNotification(`Saldo real ERP actualizado: ${new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(res.saldo_real_erp)}`);
                                        setTimeout(() => setShowNotification(null), 3500);
                                      } catch (err: any) {
                                        alert(err.message || "Error al actualizar saldo");
                                      }
                                    }}
                                    className="p-1 hover:bg-slate-100 dark:hover:bg-white/10 rounded text-indigo-400 hover:text-brand-500 transition-colors"
                                    title="Sincronizar saldo y último pago desde el ERP"
                                  >
                                    <Sparkles size={11} className="text-brand-500 animate-pulse" />
                                  </button>
                                </div>
                              </div>
                              <div className="flex justify-between items-center w-full md:block md:col-span-1 md:text-right mt-1 md:mt-0">
                                <span className="md:hidden text-[10px] font-bold text-slate-400 uppercase">Últ. pago:</span>
                                <div className={`text-xs font-bold font-mono ${c.fecha_ultimo_pago ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400'}`} title="Fecha de último pago (CULPA)">
                                  {formatFechaLocal(c.fecha_ultimo_pago) || '—'}
                                </div>
                              </div>
                              <div className="flex flex-col w-full md:block md:col-span-2">
                                <span className="md:hidden text-[10px] font-bold text-slate-400 uppercase">CUIT / Contacto:</span>
                                <div className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 truncate font-mono">
                                  {c.identificador_fiscal || 'SIN CUIT'}
                                </div>
                                <div className="text-[10px] text-slate-400 truncate mt-0.5">
                                  {c.email || 'sin-email@dominio.com'}
                                </div>
                              </div>
                              <div className="flex justify-between items-center w-full md:col-span-2 md:justify-end gap-2 border-t md:border-t-0 border-slate-100 dark:border-white/5 pt-2 md:pt-0 mt-1 md:mt-0">
                                <button
                                  onClick={() => {
                                    openClientModal(c);
                                    setClientActiveTab('erp_licensing');
                                  }}
                                  className="flex items-center gap-1 p-2 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 rounded-xl transition-all text-[10px] font-black uppercase"
                                  title="Licencias (GesActi)"
                                >
                                  <Key size={13} />
                                  <span className="hidden xl:inline">Licencias</span>
                                </button>
                                {c.cclifac && (
                                  <button
                                    onClick={() => handleOpenLicFacturadas(c)}
                                    className="flex items-center gap-1 p-2 bg-teal-500/10 hover:bg-teal-500/20 text-teal-400 border border-teal-500/20 rounded-xl transition-all"
                                    title="Licencias facturadas (LisArtC)"
                                  >
                                    <DollarSign size={14} />
                                    <span className="hidden xl:inline text-[10px] font-black uppercase">Lic Fac</span>
                                  </button>
                                )}
                                <button
                                  onClick={() => handleOpenCbus(c)}
                                  className="flex items-center gap-1 p-2 bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/20 rounded-xl transition-all"
                                  title="CBU / débito automático (ventas_ClienDA)"
                                >
                                  <CreditCard size={14} />
                                  <span className="hidden xl:inline text-[10px] font-black uppercase">CBU</span>
                                </button>
                                {c.cclifac && (
                                  <button
                                    onClick={() => handleOpenExtracto(c)}
                                    className="flex items-center gap-1 p-2 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/20 rounded-xl transition-all"
                                    title="Ver Extracto de Cuenta Corriente del ERP"
                                  >
                                    <FileText size={14} />
                                    <span className="md:hidden text-xs font-bold">Extracto</span>
                                  </button>
                                )}
                                <button onClick={() => openClientModal(c)} className="flex items-center gap-1.5 p-2 bg-slate-100 hover:bg-brand-500/10 text-slate-500 hover:text-brand-500 rounded-xl transition-all border border-slate-200 dark:bg-white/5 dark:border-white/10">
                                  <Settings size={14} />
                                  <span className="md:hidden text-xs font-bold">Ajustar</span>
                                </button>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'personnel' && (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-6 duration-300">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      Plantel de Personal
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                      </span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-400 mt-1">Control de actividades, asistencia en vivo y ABM de personal.</p>
                  </div>
                  
                  {userProfile?.rol === 'admin' && (
                    <button
                      onClick={() => {
                        setSelectedUserForEdit(null); // Nuevo
                        setUserAbmForm({
                          nombre: '',
                          email: '',
                          full_name: '',
                          password: '',
                          rol: 'soporte',
                          celular: '',
                          departamento: 'Atención al Cliente',
                          actividades: ['Atención al Cliente'],
                          profile_picture: '',
                          activo: true,
                          reseller_id: null
                        });
                        setShowUserAbmModal(true);
                      }}
                      className="bg-brand-500 hover:bg-brand-600 text-white px-5 py-2.5 rounded-xl font-bold shadow-lg shadow-brand-500/20 transition-all hover:-translate-y-1 text-xs sm:text-sm flex items-center justify-center gap-2"
                    >
                      <UserPlus size={18} />
                      + Registrar Personal
                    </button>
                  )}
                </div>

                {/* Tarjetas de Resumen del Plantel */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                  {/* Total de Personal */}
                  <div className={`p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-slate-900/30' : 'bg-white border-slate-200 shadow-sm'}`}>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Total Plantel</p>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-3xl font-black">{users.length}</span>
                      <span className="text-xs font-bold text-slate-400">Colaboradores</span>
                    </div>
                  </div>
                  
                  {/* Conectados en Vivo */}
                  <div className={`p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-emerald-500/5' : 'bg-white border-slate-200 shadow-sm'}`}>
                    <p className="text-xs font-bold text-emerald-500 uppercase tracking-widest">En Línea</p>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-3xl font-black text-emerald-500">{users.filter(u => u.is_online).length}</span>
                      <span className="text-xs font-bold text-emerald-400">Activos en Vivo</span>
                    </div>
                  </div>

                  {/* Desarrollo */}
                  <div className={`p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-indigo-500/5' : 'bg-white border-slate-200 shadow-sm'}`}>
                    <p className="text-xs font-bold text-indigo-400 uppercase tracking-widest">Desarrollo</p>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-3xl font-black text-indigo-400">{users.filter(u => userInActivity(u, 'Desarrollo')).length}</span>
                      <span className="text-xs font-bold text-indigo-400">Ingenieros</span>
                    </div>
                  </div>

                  {/* Atención al Cliente */}
                  <div className={`p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-amber-500/5' : 'bg-white border-slate-200 shadow-sm'}`}>
                    <p className="text-xs font-bold text-amber-500 uppercase tracking-widest">Atención al Cliente</p>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-3xl font-black text-amber-500">{users.filter(u => userInActivity(u, 'Atención al Cliente')).length}</span>
                      <span className="text-xs font-bold text-amber-400">Agentes</span>
                    </div>
                  </div>
                </div>

                {/* Grid de Personal */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {users.map((u: any) => {
                    const isCurrentUser = u.id === userProfile?.id;
                    const actividadesUser = userActivities(u);

                    return (
                      <div 
                        key={u.id} 
                        className={`p-6 rounded-3xl border flex flex-col justify-between transition-all hover:-translate-y-1 relative overflow-hidden ${
                          darkMode 
                            ? 'glass-dark border-dark-border bg-slate-900/40 hover:bg-slate-900/60' 
                            : 'bg-white border-slate-200 hover:shadow-lg hover:border-slate-300'
                        }`}
                      >
                        {/* Brillo ambiental si está online */}
                        {u.is_online && (
                          <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl pointer-events-none" />
                        )}

                        <div className="space-y-4">
                          {/* Cabecera de la Tarjeta */}
                          <div className="flex items-start gap-4 justify-between">
                            <div className="flex items-center gap-3">
                              {u.profile_picture ? (
                                <img src={u.profile_picture} alt={u.full_name} className="w-12 h-12 rounded-full border-2 border-brand-500/30 object-cover shadow-md" />
                              ) : (
                                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-brand-400 to-orange-500 flex items-center justify-center text-white font-bold text-sm shadow-md border-2 border-brand-500/30">
                                  {(u.full_name || u.nombre || 'AG').substring(0, 2).toUpperCase()}
                                </div>
                              )}
                              <div>
                                <h3 className="font-bold text-base text-slate-800 dark:text-white flex items-center gap-1.5">
                                  {u.full_name || u.nombre}
                                  {isCurrentUser && <span className="text-[9px] font-black bg-brand-500 text-white px-1.5 py-0.5 rounded-md uppercase">Tú</span>}
                                </h3>
                                <p className="text-xs text-slate-400">{u.email}</p>
                              </div>
                            </div>

                            {/* Badge de estado Online/Offline */}
                            {u.is_online ? (
                              <span className="flex items-center gap-1 bg-emerald-500/10 text-emerald-500 text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wider border border-emerald-500/20">
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                Online
                              </span>
                            ) : (
                              <span className="text-[10px] font-black text-slate-400 px-2.5 py-1 rounded-full uppercase tracking-wider bg-slate-500/10 border border-transparent">
                                Offline
                              </span>
                            )}
                          </div>

                          {/* Sector / Actividades */}
                          <div className="flex flex-wrap gap-2 pt-1">
                            {(actividadesUser.length ? actividadesUser : ['Soporte']).map((act) => (
                              <span key={act} className={`text-[10px] font-black px-3 py-1 rounded-full border uppercase tracking-wide ${activityBadgeClass(act)}`}>
                                {act}
                              </span>
                            ))}
                            <span className="text-[10px] font-black px-3 py-1 rounded-full border border-slate-700 bg-slate-800/20 text-slate-400 uppercase tracking-wide">
                              {u.rol === 'admin' ? '🔑 Administrador' : u.rol === 'reseller' ? '🏢 Reseller' : '🛠️ Operador'}
                            </span>
                            {!u.activo && (
                              <span className="text-[10px] font-black px-3 py-1 rounded-full bg-red-500/10 text-red-500 border border-red-500/20 uppercase tracking-wide animate-pulse">
                                🚫 Suspendido
                              </span>
                            )}
                          </div>

                          {/* Estado de Actividad en Tiempo Real (Bloque de Control) */}
                          <div className={`p-4 rounded-2xl border ${darkMode ? 'bg-black/30 border-white/5' : 'bg-slate-50 border-slate-100'}`}>
                            <div className="space-y-3 text-xs">
                              {/* Página actual */}
                              <div className="flex items-center justify-between">
                                <span className="text-slate-400 font-semibold">📍 Pantalla actual:</span>
                                <span className="font-extrabold text-slate-700 dark:text-slate-300">
                                  {u.is_online ? (u.current_page || 'Dashboard') : 'Ninguna'}
                                </span>
                              </div>
                              {/* Tarea actual */}
                              <div className="flex items-start justify-between gap-4">
                                <span className="text-slate-400 font-semibold shrink-0">⚡ Actividad actual:</span>
                                <span className="font-extrabold text-brand-500 text-right truncate max-w-[150px]">
                                  {u.is_online ? (u.current_task || 'Inactivo') : 'Desconectado'}
                                </span>
                              </div>
                              {/* Última actividad */}
                              <div className="flex items-center justify-between">
                                <span className="text-slate-400 font-semibold">🕒 Actividad hace:</span>
                                <span className="font-bold text-slate-500">
                                  {u.last_activity ? `${Math.max(0, Math.floor((new Date().getTime() - new Date(u.last_activity).getTime()) / 60000))} minutos` : 'N/D'}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Datos de contacto */}
                          <div className="flex items-center gap-3 pt-2 text-xs">
                            {u.celular ? (
                              <a 
                                href={`https://wa.me/${u.celular.replace(/\D/g, '')}`} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border transition-all ${
                                  darkMode 
                                    ? 'bg-slate-800/40 border-white/5 text-slate-300 hover:bg-slate-800' 
                                    : 'bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200'
                                }`}
                              >
                                <Phone size={14} className="text-emerald-500" />
                                {u.celular}
                              </a>
                            ) : (
                              <span className="text-slate-500 italic text-xs">Celular no registrado</span>
                            )}
                          </div>
                        </div>

                        {/* Botones de acción (Admin Only) */}
                        {userProfile?.rol === 'admin' && (
                          <div className="flex items-center gap-2 border-t border-slate-200 dark:border-white/5 pt-4 mt-4">
                            <button
                              onClick={() => {
                                setSelectedUserForEdit(u);
                                setUserAbmForm({
                                  nombre: u.nombre || '',
                                  email: u.email || '',
                                  full_name: u.full_name || '',
                                  password: '', // En blanco para no cambiar
                                  rol: u.rol || 'soporte',
                                  celular: u.celular || '',
                                  departamento: u.departamento || 'Atención al Cliente',
                                  actividades: userActivities(u).length ? userActivities(u) : ['Atención al Cliente'],
                                  profile_picture: u.profile_picture || '',
                                  activo: u.activo,
                                  reseller_id: u.reseller_id || null
                                });
                                setShowUserAbmModal(true);
                              }}
                              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold bg-brand-500/10 text-brand-500 hover:bg-brand-500/20 border border-brand-500/20 transition-all"
                            >
                              <Edit2 size={13} />
                              Modificar
                            </button>
                            {u.id !== userProfile?.id && (
                              <button
                                onClick={async () => {
                                  if (confirm(`¿Estás seguro de que deseas ${u.activo ? 'desactivar' : 'activar'} a ${u.full_name || u.nombre}?`)) {
                                    try {
                                      await toggleUserStatus(u.id);
                                      loadData();
                                      setShowNotification(`Estado de ${u.nombre} actualizado.`);
                                      setTimeout(() => setShowNotification(null), 3000);
                                    } catch (err: any) {
                                      alert(err.message || 'Error al cambiar estado.');
                                    }
                                  }
                                }}
                                className={`flex-1 py-2 rounded-xl text-xs font-bold uppercase border transition-all ${
                                  u.activo 
                                    ? 'bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20' 
                                    : 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20'
                                }`}
                              >
                                {u.activo ? 'Desactivar' : 'Activar'}
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {activeTab === 'resellers' && (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-6 duration-300">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      <CreditCard className="text-brand-500" size={28} />
                      Revendedores
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-400 mt-1">ABM de empresas revendedoras, sus clientes y usuarios.</p>
                  </div>
                  {userProfile?.rol === 'admin' && (
                    <button
                      onClick={() => {
                        setResellerForm({ nombre: '', contacto: '', email: '', telefono: '', comision_pct: 0, notas: '', activo: true });
                        setSelectedResellerForEdit(null);
                        setShowResellerModal(true);
                      }}
                      className="bg-brand-500 hover:bg-brand-600 text-white px-5 py-2.5 rounded-xl font-bold shadow-lg shadow-brand-500/20 transition-all hover:-translate-y-1 text-xs sm:text-sm flex items-center justify-center gap-2"
                    >
                      <Plus size={18} /> Nuevo Reseller
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {resellers.map((r: any) => (
                    <div key={r.id} className={`rounded-2xl border p-5 transition-all hover:shadow-lg ${darkMode ? 'bg-slate-900/50 border-white/5' : 'bg-white border-slate-200'}`}>
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="font-bold text-lg text-slate-800 dark:text-white">{r.nombre}</h3>
                          {r.contacto && <p className="text-xs text-slate-500">{r.contacto}</p>}
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${r.activo !== false ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
                          {r.activo !== false ? 'Activo' : 'Inactivo'}
                        </span>
                      </div>
                      <div className="space-y-1 text-xs text-slate-500 mb-4">
                        {r.email && <p className="flex items-center gap-1"><Mail size={12} /> {r.email}</p>}
                        {r.telefono && <p className="flex items-center gap-1"><Phone size={12} /> {r.telefono}</p>}
                        <p className="flex items-center gap-1"><Users size={12} /> {r.cantidad_clientes || 0} clientes · {r.cantidad_usuarios || 0} usuarios</p>
                        {r.comision_pct > 0 && <p className="text-brand-500 font-bold">Comisión: {r.comision_pct}%</p>}
                      </div>
                      {userProfile?.rol === 'admin' && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setSelectedResellerForEdit(r);
                              setResellerForm({
                                nombre: r.nombre || '',
                                contacto: r.contacto || '',
                                email: r.email || '',
                                telefono: r.telefono || '',
                                comision_pct: r.comision_pct || 0,
                                notas: r.notas || '',
                                activo: r.activo !== false
                              });
                              setShowResellerModal(true);
                            }}
                            className="flex-1 py-2 rounded-xl text-xs font-bold bg-brand-500/10 text-brand-500 hover:bg-brand-500/20 border border-brand-500/20 transition-all"
                          >
                            Editar
                          </button>
                          <button
                            onClick={async () => {
                              if (!confirm(`¿Eliminar "${r.nombre}"? Sus clientes y usuarios quedarán sin asignar.`)) return;
                              try {
                                await deleteReseller(r.id);
                                setShowNotification(`Reseller ${r.nombre} eliminado.`);
                                loadData();
                                setTimeout(() => setShowNotification(null), 3000);
                              } catch (err: any) {
                                alert(err.message || 'Error al eliminar');
                              }
                            }}
                            className="py-2 px-3 rounded-xl text-xs font-bold bg-red-500/10 text-red-500 hover:bg-red-500/20 border border-red-500/20 transition-all"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                  {resellers.length === 0 && (
                    <div className="col-span-full text-center py-12 text-slate-500">
                      <CreditCard size={48} className="mx-auto mb-4 opacity-20" />
                      <p className="font-bold">No hay revendedores cargados</p>
                      <p className="text-xs mt-1">Creá el primero para empezar a operar con el modelo multiempresa.</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="max-w-2xl mx-auto py-12 animate-in slide-in-from-bottom-8">
                <div className={`p-10 rounded-3xl border shadow-2xl transition-all ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'}`}>
                  <div className="flex flex-col items-center text-center gap-6">
                    <img src="https://i.pravatar.cc/150?img=11" alt="Avatar" className="w-32 h-32 rounded-full border-4 border-brand-500/30 shadow-2xl" />
                    <div>
                      <h2 className="text-3xl font-black tracking-tighter">{userProfile?.nombre || 'Agente de Soporte'}</h2>
                      <p className="text-brand-500 font-extrabold uppercase tracking-[0.2em] text-sm mt-1">{userProfile?.rol || 'Soporte'}</p>
                    </div>
                  </div>

                  <div className="mt-12 space-y-6 pt-10 border-t border-slate-200 dark:border-white/5">
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">Correo Institucional</label>
                        <div className={`p-4 rounded-2xl border font-bold text-sm ${darkMode ? 'bg-black/20 border-white/5 text-slate-300' : 'bg-slate-50 border-slate-100 text-slate-600'}`}>{userProfile?.email || 'soporte@apollo.com'}</div>
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">Contraseña</label>
                        <div className={`p-4 rounded-2xl border font-bold text-sm flex justify-between items-center ${darkMode ? 'bg-black/20 border-white/5 text-slate-300' : 'bg-slate-50 border-slate-100 text-slate-600'}`}>
                          ••••••••••••
                          <button className="text-brand-500 hover:text-brand-400 text-[10px] uppercase font-black">Cambiar</button>
                        </div>
                      </div>
                    </div>

                    {/* Sección PWA e Installability */}
                    <div className="pt-6 border-t border-slate-200 dark:border-white/5 space-y-4">
                      <h4 className="text-xs font-black uppercase tracking-wider text-slate-400">Aplicación PWA y Alertas</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className={`p-4 rounded-2xl border flex flex-col justify-between gap-3 ${darkMode ? 'bg-black/20 border-white/5' : 'bg-slate-50 border-slate-100'}`}>
                          <div>
                            <span className="text-xs font-black text-amber-500 uppercase tracking-widest block mb-1">Notificaciones Push</span>
                            <p className="text-[11px] leading-relaxed text-slate-400">Recibe avisos nativos en tu escritorio en tiempo real ante alertas críticas de los clientes.</p>
                          </div>
                          <button
                            onClick={async () => {
                              if (!('Notification' in window)) {
                                alert("Este navegador no soporta notificaciones de escritorio.");
                                return;
                              }
                              const permission = await Notification.requestPermission();
                              if (permission === 'granted') {
                                triggerPushNotification("🔔 Notificaciones Activas", "¡Felicidades! Recibirás alertas del Centinela en tiempo real en tu escritorio.");
                              }
                            }}
                            className="bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs py-2.5 px-4 rounded-xl transition-all w-full text-center"
                          >
                            {('Notification' in window && Notification.permission === 'granted') ? '✓ Habilitadas' : 'Habilitar Notificaciones'}
                          </button>
                        </div>

                        <div className={`p-4 rounded-2xl border flex flex-col justify-between gap-3 ${darkMode ? 'bg-black/20 border-white/5' : 'bg-slate-50 border-slate-100'}`}>
                          <div>
                            <span className="text-xs font-black text-emerald-500 uppercase tracking-widest block mb-1">Instalación Local</span>
                            <p className="text-[11px] leading-relaxed text-slate-400">Instala ApolloSupport como una aplicación nativa en tu escritorio o teléfono móvil.</p>
                          </div>
                          <button
                            disabled={!deferredPrompt}
                            onClick={() => {
                              if (deferredPrompt) {
                                deferredPrompt.prompt();
                                deferredPrompt.userChoice.then((choiceResult: any) => {
                                  if (choiceResult.outcome === 'accepted') {
                                    console.log('Usuario aceptó la instalación PWA');
                                  }
                                  setDeferredPrompt(null);
                                });
                              } else {
                                alert("La app ya está instalada o tu navegador no ofrece la instalación en este momento.");
                              }
                            }}
                            className={`font-bold text-xs py-2.5 px-4 rounded-xl transition-all w-full text-center ${deferredPrompt ? 'bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer shadow-lg' : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-white/5'}`}
                          >
                            {deferredPrompt ? 'Instalar App (PWA)' : '✓ Ya Instalado'}
                          </button>
                        </div>
                      </div>
                    </div>

                    <button onClick={handleLogout} className="w-full flex items-center justify-center gap-3 py-4 bg-red-600/10 hover:bg-red-600/20 text-red-500 rounded-2xl font-bold transition-all border border-red-500/20 mt-6">
                      <LogOut size={20} /> Cerrar Sesión
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'licenses' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-2xl font-black text-white">Central de Licenciamiento</h2>
                    <p className="text-slate-400 text-sm">Administra llaves de activación y límites comerciales.</p>
                  </div>
                  <button onClick={() => setShowLicenseModal(true)} className="bg-brand-500 hover:bg-brand-600 text-white px-5 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2 shadow-lg transition-all">
                    <Plus size={18} /> Generar Nueva Licencia
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {licenses.filter(lic => {
                    if (!globalSearchTerm) return true;
                    const term = globalSearchTerm.toLowerCase();
                    const client = clients.find(c => c.id === lic.client_id);
                    
                    const matchKey = lic.license_key?.toLowerCase().includes(term);
                    const matchId = String(lic.client_id).includes(term);
                    const matchClientSocial = client?.razon_social?.toLowerCase().includes(term);
                    const matchClientFantasia = client?.nombre_fantasia?.toLowerCase().includes(term);
                    const matchClientCodigo = client?.codigo?.toLowerCase().includes(term);
                    const matchClientFac = client?.cclifac?.toLowerCase().includes(term);
                    
                    return matchKey || matchId || matchClientSocial || matchClientFantasia || matchClientCodigo || matchClientFac;
                  }).map((lic) => {
                    const client = clients.find(c => c.id === lic.client_id);
                    return (
                      <div key={lic.id} className="bg-slate-800/50 border border-white/5 rounded-2xl p-5 hover:border-brand-500/30 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                          <span className={`px-2 py-1 rounded-md text-[10px] font-black uppercase tracking-widest ${lic.is_active ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
                            {lic.is_active ? 'Activa' : 'Suspendida'}
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">ID #{lic.id}</span>
                        </div>
                        <h3 className="text-lg font-mono font-bold text-white mb-1 select-all">{lic.license_key}</h3>
                        <div className="flex flex-wrap items-center gap-1.5 mb-4">
                          <span className="text-xs text-brand-400 font-bold truncate max-w-[180px]" title={client?.razon_social}>
                            {client ? client.razon_social : `Cliente ID: ${lic.client_id}`}
                          </span>
                          {client?.codigo && (
                            <span className="text-[9px] bg-slate-700/60 text-slate-300 font-mono px-1.5 py-0.5 rounded uppercase tracking-wider">
                              Cód: {client.codigo}
                            </span>
                          )}
                          {client?.cclifac && (
                            <span className="text-[9px] bg-emerald-500/15 text-emerald-400 border border-emerald-500/10 font-mono px-1.5 py-0.5 rounded">
                              Fac: {client.cclifac}
                            </span>
                          )}
                        </div>
                        <div className="space-y-3">
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-slate-500">Capacidad:</span>
                            <span className="text-white font-bold">{lic.max_devices} PCs</span>
                          </div>
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-slate-500">Expiración:</span>
                            <span className="text-brand-400 font-bold">{lic.expiry_date ? new Date(lic.expiry_date).toLocaleDateString() : 'Ilimitada'}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {activeTab === 'logs' && (
              <div className="space-y-8 animate-in slide-in-from-bottom-8">
                {/* Cabecera premium */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div>
                    <h1 className="text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      Bitácora de Telemetría <span className="relative flex h-3 w-3"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-violet-500"></span></span>
                    </h1>
                    <p className="text-slate-400 mt-2">Diagnóstico de eventos del agente Centinela y el servidor en tiempo real.</p>
                  </div>
                  
                  {/* Botones de acción */}
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      onClick={() => fetchTelemetryLogs()}
                      className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs px-4 py-3 rounded-2xl border border-white/5 transition-all shadow-md cursor-pointer"
                      title="Refrescar logs ahora"
                    >
                      🔄 Refrescar
                    </button>
                    <button
                      onClick={() => handleClearTelemetryLogs(null)}
                      className="flex items-center gap-2 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white font-bold text-xs px-4 py-3 rounded-2xl border border-red-500/20 transition-all cursor-pointer"
                    >
                      🗑️ Limpiar Bitácora
                    </button>
                  </div>
                </div>

                {/* Filtros */}
                <div className={`p-6 rounded-[2rem] border shadow-2xl ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'} space-y-4`}>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                    {/* Búsqueda */}
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Buscar Mensaje</label>
                      <div className="relative">
                        <Search size={14} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                          type="text"
                          value={logsSearchTerm}
                          onChange={(e) => setLogsSearchTerm(e.target.value)}
                          className={`w-full pl-10 pr-4 py-2.5 rounded-xl text-xs font-semibold outline-none border transition-all ${
                            darkMode ? 'bg-black/30 border-white/10 text-white focus:border-brand-500' : 'bg-slate-50 border-slate-200 text-slate-700 focus:border-brand-500'
                          }`}
                          placeholder="Buscar término..."
                        />
                      </div>
                    </div>

                    {/* Dispositivo */}
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Filtrar por PC</label>
                      <select
                        value={logsFilterDevice}
                        onChange={(e) => setLogsFilterDevice(e.target.value)}
                        className={`w-full px-4 py-2.5 rounded-xl text-xs font-semibold outline-none border transition-all ${
                          darkMode ? 'bg-slate-900 border-white/10 text-slate-300 focus:border-brand-500' : 'bg-slate-50 border-slate-200 text-slate-700 focus:border-brand-500'
                        }`}
                      >
                        <option value="all">🖥️ Todos los Equipos</option>
                        {clients.flatMap(c => c.devices || []).map((dev: any) => (
                          <option key={dev.id} value={dev.id}>
                            🖥️ {dev.device_name}{deviceAssistLabel(dev) ? ` (ID: ${deviceAssistLabel(dev)})` : ` (#${dev.id})`}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Nivel */}
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Nivel de Gravedad</label>
                      <select
                        value={logsFilterLevel}
                        onChange={(e) => setLogsFilterLevel(e.target.value)}
                        className={`w-full px-4 py-2.5 rounded-xl text-xs font-semibold outline-none border transition-all ${
                          darkMode ? 'bg-slate-900 border-white/10 text-slate-300 focus:border-brand-500' : 'bg-slate-50 border-slate-200 text-slate-700 focus:border-brand-500'
                        }`}
                      >
                        <option value="all">⚖️ Todos los niveles</option>
                        <option value="DEBUG">🔵 DEBUG</option>
                        <option value="INFO">🟢 INFO</option>
                        <option value="WARNING">🟡 WARNING</option>
                        <option value="ERROR">🔴 ERROR</option>
                      </select>
                    </div>

                    {/* Origen */}
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Origen del Evento</label>
                      <select
                        value={logsFilterSource}
                        onChange={(e) => setLogsFilterSource(e.target.value)}
                        className={`w-full px-4 py-2.5 rounded-xl text-xs font-semibold outline-none border transition-all ${
                          darkMode ? 'bg-slate-900 border-white/10 text-slate-300 focus:border-brand-500' : 'bg-slate-50 border-slate-200 text-slate-700 focus:border-brand-500'
                        }`}
                      >
                        <option value="all">🔌 Todos los orígenes</option>
                        <option value="agent">🤖 Agente Centinela</option>
                        <option value="backend">☁️ Servidor Backend</option>
                      </select>
                    </div>
                  </div>

                  {/* Auto refresh status */}
                  <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-200 dark:border-white/5">
                    <div className="flex items-center gap-2">
                      <span className={`relative flex h-2.5 w-2.5 ${logsAutoRefresh ? 'inline-flex' : 'hidden'}`}>
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                      </span>
                      <span>
                        {logsAutoRefresh ? 'Auto-actualizando cada 3 segundos' : 'Actualización automática en pausa'}
                      </span>
                    </div>
                    <button
                      onClick={() => setLogsAutoRefresh(v => !v)}
                      className={`font-extrabold text-[10px] uppercase px-3 py-1.5 rounded-lg border transition-all ${
                        logsAutoRefresh 
                          ? 'bg-slate-800 border-white/5 text-slate-400 hover:text-white' 
                          : 'bg-brand-500/10 border-brand-500/20 text-brand-400 hover:bg-brand-500/20'
                      }`}
                    >
                      {logsAutoRefresh ? 'Pausar' : 'Activar Auto-Refresh'}
                    </button>
                  </div>
                </div>

                {/* Tabla de Logs */}
                <div className={`rounded-[2rem] border shadow-2xl overflow-hidden ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'}`}>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-white/5 bg-slate-850 dark:bg-black/30 text-[10px] uppercase font-black tracking-wider text-slate-400">
                          <th className="py-4 px-6 w-24">Hora</th>
                          <th className="py-4 px-6 w-32">Nivel</th>
                          <th className="py-4 px-6 w-32">Origen</th>
                          <th className="py-4 px-6 w-48">PC / Dispositivo</th>
                          <th className="py-4 px-6">Mensaje</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-white/5 font-medium">
                        {logsLoading && telemetryLogs.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-12 text-center text-slate-500">
                              <div className="flex flex-col items-center justify-center gap-3">
                                <div className="animate-spin rounded-full h-8 w-8 border-4 border-brand-500 border-t-transparent" />
                                <span>Cargando bitácora de logs...</span>
                              </div>
                            </td>
                          </tr>
                        ) : telemetryLogs.filter(log => {
                          if (!logsSearchTerm) return true;
                          return log.message?.toLowerCase().includes(logsSearchTerm.toLowerCase());
                        }).length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-12 text-center text-slate-500 italic">
                              No se encontraron logs con los filtros aplicados.
                            </td>
                          </tr>
                        ) : (
                          telemetryLogs
                            .filter(log => {
                              if (!logsSearchTerm) return true;
                              return log.message?.toLowerCase().includes(logsSearchTerm.toLowerCase());
                            })
                            .map((log: any) => {
                              let levelBadge = "";
                              if (log.level === 'DEBUG') levelBadge = "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20";
                              else if (log.level === 'WARNING') levelBadge = "bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse";
                              else if (log.level === 'ERROR') levelBadge = "bg-red-500/20 text-red-400 border border-red-500/30 font-black shadow-md shadow-red-500/5";
                              else levelBadge = "bg-emerald-500/10 text-emerald-400 border border-emerald-500/10";

                              const isAgent = log.source === 'agent';
                              const sourceBadge = isAgent 
                                ? "bg-orange-500/10 text-orange-400 border border-orange-500/20" 
                                : "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20";

                              return (
                                <tr key={log.id} className="hover:bg-slate-900/40 dark:hover:bg-white/[0.02] transition-colors select-text">
                                  <td className="py-4 px-6 text-slate-400 font-mono whitespace-nowrap">
                                    {new Date(log.timestamp).toLocaleString('es-AR', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'})}
                                  </td>
                                  <td className="py-4 px-6">
                                    <span className={`px-2 py-1 rounded-full text-[9px] uppercase font-black ${levelBadge}`}>
                                      {log.level}
                                    </span>
                                  </td>
                                  <td className="py-4 px-6">
                                    <span className={`px-2.5 py-1 rounded-full text-[9px] uppercase font-bold ${sourceBadge}`}>
                                      {isAgent ? '🤖 Agente' : '☁️ Servidor'}
                                    </span>
                                  </td>
                                  <td className="py-4 px-6 font-bold text-slate-300">
                                    {log.device_id ? (
                                      <div className="flex flex-col">
                                        <span className="text-slate-200">{log.device_name}</span>
                                        <span className="text-[9px] text-slate-500 font-mono font-normal">ID: {log.device_id}</span>
                                      </div>
                                    ) : (
                                      <span className="text-slate-500 italic">No aplica</span>
                                    )}
                                  </td>
                                  <td className="py-4 px-6 font-mono text-slate-300 break-all whitespace-pre-wrap leading-relaxed max-w-xl">
                                    {log.message}
                                  </td>
                                </tr>
                              );
                            })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* ====================================================== */}
            {/* SECCIÓN: DISPOSITIVOS MÓVILES ANDROID                  */}
            {/* ====================================================== */}
            {activeTab === 'android_devices' && (
              <div className="space-y-6 animate-in slide-in-from-bottom-8">

                {/* Cabecera */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div>
                    <h1 className="text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      <Smartphone className="text-emerald-400" size={36} />
                      Dispositivos Móviles
                      {androidSummaryLoading && (
                        <span className="relative flex h-3 w-3 ml-1">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                        </span>
                      )}
                    </h1>
                    <p className="text-slate-400 mt-1.5">
                      Control de licencias móviles y web (TCK en PC) por cliente y aplicación · {androidSummary.length} clientes con dispositivos registrados
                    </p>
                  </div>
                  <button
                    onClick={() => { setAndroidSelectedClient(null); loadAndroidSummary(); }}
                    className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs px-4 py-3 rounded-2xl border border-white/5 transition-all shadow-md cursor-pointer"
                  >
                    🔄 Actualizar
                  </button>
                </div>

                {/* KPI Cards */}
                {(() => {
                  const totalHab = androidSummary.reduce((a, c) => a + (c.total_habilitados || 0), 0);
                  const totalDev = androidSummary.reduce((a, c) => a + (c.total_dispositivos || 0), 0);
                  const totalClientes = androidSummary.length;
                  // Contar por app
                  const appCounts: Record<string, number> = {};
                  androidSummary.forEach(c => {
                    Object.entries(c.apps || {}).forEach(([app, info]: [string, any]) => {
                      appCounts[app] = (appCounts[app] || 0) + (info.habilitados || 0);
                    });
                  });
                  const topApps = Object.entries(appCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);

                  return (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className={`p-5 rounded-2xl border ${darkMode ? 'bg-slate-900 border-white/5' : 'bg-white border-slate-200'} flex flex-col gap-1`}>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Clientes</span>
                        <span className="text-3xl font-black text-white">{totalClientes}</span>
                        <span className="text-[10px] text-slate-500">con dispositivos registrados</span>
                      </div>
                      <div className={`p-5 rounded-2xl border ${darkMode ? 'bg-slate-900 border-white/5' : 'bg-white border-slate-200'} flex flex-col gap-1`}>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Total Dispositivos</span>
                        <span className="text-3xl font-black text-white">{totalDev}</span>
                        <span className="text-[10px] text-slate-500">registros totales en BD</span>
                      </div>
                      <div className={`p-5 rounded-2xl border ${darkMode ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-emerald-50 border-emerald-200'} flex flex-col gap-1`}>
                        <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">Habilitados</span>
                        <span className="text-3xl font-black text-emerald-400">{totalHab}</span>
                        <span className="text-[10px] text-slate-500">activos actualmente</span>
                      </div>
                      <div className={`p-5 rounded-2xl border ${darkMode ? 'bg-slate-900 border-white/5' : 'bg-white border-slate-200'} flex flex-col gap-2`}>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Top Apps</span>
                        {topApps.map(([app, count]) => (
                          <div key={app} className="flex items-center justify-between">
                            <span className="text-xs font-bold text-slate-300">{app}</span>
                            <span className="text-xs font-black text-white bg-slate-800 px-2 py-0.5 rounded-lg">{count}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}

                {/* Layout de dos columnas: tabla izquierda + detalle derecha */}
                <div className={`flex flex-col lg:flex-row gap-5 ${androidSelectedClient ? 'lg:items-start' : ''}`}>

                  {/* Tabla de clientes */}
                  <div className={`${androidSelectedClient ? 'lg:w-2/5' : 'w-full'} transition-all duration-300`}>
                    <div className={`rounded-[1.75rem] border shadow-xl overflow-hidden ${darkMode ? 'bg-slate-900 border-white/5' : 'bg-white border-slate-200'}`}>
                      {/* Buscador */}
                      <div className="p-4 border-b border-white/5">
                        <div className="relative">
                          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                          <input
                            type="text"
                            value={androidSearchTerm}
                            onChange={e => setAndroidSearchTerm(e.target.value)}
                            placeholder="Buscar cliente por código o razón social..."
                            className={`w-full pl-9 pr-4 py-2.5 rounded-xl text-xs font-semibold outline-none border transition-all ${darkMode ? 'bg-black/30 border-white/10 text-white focus:border-emerald-500' : 'bg-slate-50 border-slate-200 text-slate-700'}`}
                          />
                        </div>
                      </div>

                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="border-b border-white/5 bg-black/20 text-[10px] uppercase font-black tracking-wider text-slate-400">
                              <th className="py-3 px-4">Cliente</th>
                              <th className="py-3 px-3 text-center">PRV</th>
                              <th className="py-3 px-3 text-center">ROU</th>
                              <th className="py-3 px-3 text-center">FIR</th>
                              <th className="py-3 px-3 text-center">INV</th>
                              <th className="py-3 px-3 text-center">FRA</th>
                              <th className="py-3 px-3 text-center">Otros</th>
                              <th className="py-3 px-3 text-center">Total</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/5">
                            {androidSummaryLoading && androidSummary.length === 0 ? (
                              <tr><td colSpan={8} className="py-12 text-center text-slate-500">
                                <div className="flex flex-col items-center gap-3">
                                  <div className="animate-spin rounded-full h-7 w-7 border-4 border-emerald-500 border-t-transparent" />
                                  <span>Cargando dispositivos...</span>
                                </div>
                              </td></tr>
                            ) : (() => {
                              const filtered = androidSummary.filter(c => {
                                const term = androidSearchTerm.toLowerCase();
                                if (!term) return true;
                                const clientData = clients.find((cl: any) => cl.codigo === c.client_code);
                                const razon = clientData?.razon_social?.toLowerCase() || '';
                                return c.client_code?.toLowerCase().includes(term) || razon.includes(term);
                              });

                              if (filtered.length === 0) {
                                return <tr><td colSpan={8} className="py-10 text-center text-slate-500 italic text-xs">No se encontraron clientes con los filtros aplicados.</td></tr>;
                              }

                              const MAIN_APPS = ['PRV', 'ROU', 'FIR', 'INV', 'FRA'];

                              return filtered
                                .sort((a, b) => (b.total_habilitados || 0) - (a.total_habilitados || 0))
                                .map((row: any) => {
                                  const clientData = clients.find((cl: any) => cl.codigo === row.client_code);
                                  const razon = clientData?.razon_social || `Cliente ${row.client_code}`;
                                  const isSelected = androidSelectedClient?.client_code === row.client_code;

                                  const getAppCount = (app: string) => {
                                    const info = row.apps?.[app];
                                    return info ? info.habilitados : 0;
                                  };

                                  const otrosCount = Object.entries(row.apps || {})
                                    .filter(([app]: [string, any]) => !MAIN_APPS.includes(app))
                                    .reduce((sum: number, [, info]: [string, any]) => sum + ((info as any).habilitados || 0), 0);

                                  return (
                                    <tr
                                      key={row.client_code}
                                      onClick={() => {
                                        setAndroidSelectedClient(row);
                                        setAndroidFilterApp('all');
                                        setAndroidFilterHabilitado('all');
                                        loadAndroidClientDevices(row.client_code);
                                      }}
                                      className={`cursor-pointer transition-all duration-150 hover:bg-emerald-500/5 ${isSelected ? 'bg-emerald-500/10 border-l-2 border-emerald-500' : ''}`}
                                    >
                                      <td className="py-3 px-4">
                                        <div className="font-bold text-white leading-tight">{razon.length > 30 ? razon.substring(0, 28) + '…' : razon}</div>
                                        <div className="text-[10px] text-slate-500 font-mono mt-0.5">Cód: {row.client_code}</div>
                                        {row.ultimo_acceso && (
                                          <div className="text-[9px] text-slate-600 mt-0.5">
                                            Últ: {new Date(row.ultimo_acceso).toLocaleDateString('es-AR')}
                                          </div>
                                        )}
                                      </td>
                                      {MAIN_APPS.map(app => (
                                        <td key={app} className="py-3 px-3 text-center">
                                          {getAppCount(app) > 0 ? (
                                            <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-emerald-500/15 text-emerald-400 font-black text-xs border border-emerald-500/20">
                                              {getAppCount(app)}
                                            </span>
                                          ) : (
                                            <span className="text-slate-700 text-xs">—</span>
                                          )}
                                        </td>
                                      ))}
                                      <td className="py-3 px-3 text-center">
                                        {otrosCount > 0 ? (
                                          <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-amber-500/15 text-amber-400 font-black text-xs border border-amber-500/20">{otrosCount}</span>
                                        ) : <span className="text-slate-700">—</span>}
                                      </td>
                                      <td className="py-3 px-3 text-center">
                                        <span className={`inline-flex items-center justify-center h-7 px-2.5 rounded-full font-black text-xs ${row.total_habilitados > 0 ? 'bg-white/10 text-white' : 'bg-slate-800 text-slate-500'}`}>
                                          {row.total_habilitados}
                                        </span>
                                      </td>
                                    </tr>
                                  );
                                });
                            })()}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  {/* Panel de detalle del cliente seleccionado */}
                  {androidSelectedClient && (
                    <div className="lg:flex-1 animate-in slide-in-from-right-4">
                      <div className={`rounded-[1.75rem] border shadow-xl overflow-hidden ${darkMode ? 'bg-slate-900 border-emerald-500/20' : 'bg-white border-emerald-200'}`}>
                        {/* Header del panel */}
                        <div className="p-5 border-b border-white/5 flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-mono bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded-lg border border-emerald-500/20">
                                COD: {androidSelectedClient.client_code}
                              </span>
                              <span className="text-xs bg-white/5 text-slate-400 px-2 py-0.5 rounded-lg">
                                {androidSelectedClient.total_habilitados} activos / {androidSelectedClient.total_dispositivos} total
                              </span>
                            </div>
                            <h3 className="text-base font-extrabold text-white">
                              {clients.find((c: any) => c.codigo === androidSelectedClient.client_code)?.razon_social || `Cliente ${androidSelectedClient.client_code}`}
                            </h3>
                            {androidSelectedClient.ultimo_acceso && (
                              <p className="text-[11px] text-slate-500 mt-0.5">
                                Último acceso: {new Date(androidSelectedClient.ultimo_acceso).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })}
                              </p>
                            )}
                          </div>
                          <button onClick={() => setAndroidSelectedClient(null)} className="hover:bg-white/10 p-1.5 rounded-xl transition-all shrink-0">
                            <X size={16} className="text-slate-400" />
                          </button>
                        </div>

                        {/* Resumen por app */}
                        <div className="p-4 border-b border-white/5 flex flex-wrap gap-2">
                          {Object.values(androidSelectedClient.apps || {}).map((appInfo: any) => (
                            <div key={appInfo.app} className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-bold transition-all cursor-pointer ${androidFilterApp === appInfo.app ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300' : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'}`}
                              onClick={() => setAndroidFilterApp(androidFilterApp === appInfo.app ? 'all' : appInfo.app)}
                            >
                              <span>{appInfo.app}</span>
                              <span className="bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded-md text-[10px]">{appInfo.habilitados}</span>
                              {appInfo.deshabilitados > 0 && (
                                <span className="bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded-md text-[10px]">{appInfo.deshabilitados} inact</span>
                              )}
                            </div>
                          ))}
                        </div>

                        {/* Filtro habilitado */}
                        <div className="px-4 py-3 border-b border-white/5 flex gap-2">
                          {['all', 'true', 'false'].map(val => (
                            <button
                              key={val}
                              onClick={() => setAndroidFilterHabilitado(val)}
                              className={`px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all ${androidFilterHabilitado === val ? 'bg-emerald-500 text-white' : 'bg-white/5 text-slate-400 hover:bg-white/10'}`}
                            >
                              {val === 'all' ? 'Todos' : val === 'true' ? '✅ Activos' : '❌ Inactivos'}
                            </button>
                          ))}
                        </div>

                        {/* Lista de dispositivos */}
                        <div className="max-h-[520px] overflow-y-auto custom-scrollbar divide-y divide-white/5">
                          {androidClientDevicesLoading ? (
                            <div className="py-10 flex flex-col items-center gap-3 text-slate-500">
                              <div className="animate-spin rounded-full h-7 w-7 border-4 border-emerald-500 border-t-transparent" />
                              <span className="text-xs">Cargando dispositivos...</span>
                            </div>
                          ) : (() => {
                            const filtered = androidClientDevices.filter(d => {
                              const appOk = androidFilterApp === 'all' || d.app === androidFilterApp;
                              const habOk = androidFilterHabilitado === 'all' || String(d.habilitado) === androidFilterHabilitado;
                              return appOk && habOk;
                            });
                            if (filtered.length === 0) {
                              return <div className="py-10 text-center text-slate-500 text-xs italic">No hay dispositivos con los filtros seleccionados.</div>;
                            }
                            return filtered.map((dev: any) => {
                              const primary = androidDevicePrimaryLabel(dev);
                              const identityLines = androidDeviceIdentityLines(dev).filter(
                                l => l.label !== 'Usuario / Vendedor' || primary !== l.value
                              );
                              return (
                              <div
                                key={dev.id}
                                onClick={() => setAndroidDeviceDetailModal(dev)}
                                className="p-4 cursor-pointer hover:bg-white/[0.03] transition-colors flex items-start gap-3"
                              >
                                {/* Estado badge */}
                                <div className={`mt-1 shrink-0 w-2 h-2 rounded-full ${dev.habilitado ? 'bg-emerald-500 shadow-emerald-500/40 shadow-sm' : 'bg-red-500'}`} />
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-black border ${
                                      dev.app === 'PRV' ? 'bg-blue-500/15 text-blue-400 border-blue-500/20' :
                                      dev.app === 'ROU' ? 'bg-purple-500/15 text-purple-400 border-purple-500/20' :
                                      dev.app === 'FIR' ? 'bg-amber-500/15 text-amber-400 border-amber-500/20' :
                                      dev.app === 'INV' ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20' :
                                      dev.app === 'FRA' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' :
                                      dev.app === 'TCK' ? 'bg-violet-500/15 text-violet-300 border-violet-500/25' :
                                      'bg-slate-500/15 text-slate-400 border-slate-500/20'
                                    }`}>
                                      {dev.app}
                                    </span>
                                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wide">{dev.app_nombre || dev.app}</span>
                                    {!dev.habilitado && <span className="text-[9px] text-red-400 font-bold">INACTIVO</span>}
                                  </div>
                                  <div className="text-xs font-bold text-white mt-1 truncate" title={primary}>{primary}</div>
                                  <div className="flex flex-col gap-0.5 mt-1.5">
                                    {identityLines.slice(0, 4).map(line => (
                                      <div key={line.label} className="flex items-baseline gap-1.5 min-w-0">
                                        <span className="text-[9px] text-slate-600 font-black uppercase shrink-0">{line.label}:</span>
                                        <span
                                          className={`text-[10px] text-slate-400 truncate ${line.mono ? 'font-mono' : ''}`}
                                          title={line.value}
                                        >
                                          {line.value}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5">
                                    {dev.ult_acceso && <span className="text-[10px] text-slate-500">Acc: {new Date(dev.ult_acceso).toLocaleDateString('es-AR')}</span>}
                                    {dev.fecha_registro && <span className="text-[10px] text-slate-600">Alta: {new Date(dev.fecha_registro).toLocaleDateString('es-AR')}</span>}
                                  </div>
                                </div>
                                <div
                                  className="shrink-0 flex flex-col items-end gap-2"
                                  onClick={e => e.stopPropagation()}
                                >
                                  <button
                                    type="button"
                                    title={dev.habilitado ? 'Desactivar' : 'Activar'}
                                    onClick={() => handleToggleAndroidDevice(dev, !dev.habilitado)}
                                    className={`px-2.5 py-1 rounded-lg text-[10px] font-black uppercase border transition-all ${
                                      dev.habilitado
                                        ? 'bg-red-950/40 text-red-400 border-red-500/20 hover:bg-red-900/50'
                                        : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/30'
                                    }`}
                                  >
                                    {dev.habilitado ? 'Desact.' : 'Activar'}
                                  </button>
                                  <Search size={14} className="text-slate-600" />
                                </div>
                              </div>
                            );});
                          })()}
                        </div>
                        <div className={`px-5 py-3 border-t border-white/5 flex items-center justify-between ${darkMode ? 'bg-black/20' : 'bg-slate-50'}`}>
                          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                            {androidClientDevices.filter(d => {
                              const appOk = androidFilterApp === 'all' || d.app === androidFilterApp;
                              const habOk = androidFilterHabilitado === 'all' || String(d.habilitado) === androidFilterHabilitado;
                              return appOk && habOk;
                            }).length} dispositivos mostrados
                          </span>
                          <button
                            onClick={() => loadAndroidClientDevices(androidSelectedClient.client_code)}
                            className="text-[10px] text-emerald-400 hover:text-emerald-300 font-bold transition-colors"
                          >
                            🔄 Recargar
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ====================================================== */}
            {/* SECCIÓN: ACTIVACIONES PENDIENTES OnLine (misi_request) */}
            {/* ====================================================== */}
            {activeTab === 'acti_pending' && (
              <div className="space-y-6 animate-in slide-in-from-bottom-8">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div>
                    <h1 className="text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      <Clock className="text-amber-400" size={36} />
                      Activaciones OnLine
                    </h1>
                    <p className="text-slate-400 mt-1.5">
                      Solicitudes de activación (misi_request) · mismo flujo que GesActi ActiPenOL
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        const next = !actiShowAll;
                        setActiShowAll(next);
                        loadActiRequests(next);
                      }}
                      className={`px-4 py-3 rounded-2xl text-xs font-bold border transition-all ${actiShowAll ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' : 'bg-slate-800 text-slate-300 border-white/5'}`}
                    >
                      {actiShowAll ? 'Solo pendientes' : 'Ver todas'}
                    </button>
                    <button
                      type="button"
                      onClick={() => loadActiRequests()}
                      className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs px-4 py-3 rounded-2xl border border-white/5"
                    >
                      🔄 Actualizar
                    </button>
                  </div>
                </div>

                <div className={`rounded-[1.75rem] border shadow-xl overflow-hidden ${darkMode ? 'bg-slate-900 border-white/5' : 'bg-white border-slate-200'}`}>
                  {actiRequestsLoading ? (
                    <div className="p-12 text-center text-slate-400 text-sm">Cargando solicitudes…</div>
                  ) : actiRequests.length === 0 ? (
                    <div className="p-12 text-center text-slate-500 text-sm">No hay solicitudes {actiShowAll ? '' : 'pendientes'}.</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-black/20 text-[10px] uppercase tracking-wider text-slate-500">
                          <tr>
                            <th className="px-4 py-3">ID</th>
                            <th className="px-4 py-3">Cliente</th>
                            <th className="px-4 py-3">Serial</th>
                            <th className="px-4 py-3">PC / Usuario</th>
                            <th className="px-4 py-3">Path / OS</th>
                            <th className="px-4 py-3">Estado</th>
                            <th className="px-4 py-3 text-right">Acciones</th>
                          </tr>
                        </thead>
                        <tbody>
                          {actiRequests.map((req) => {
                            const cli = clients.find(c => String(c.codigo) === String(req.client_code));
                            return (
                              <tr key={req.KeyID} className="border-t border-white/5 hover:bg-white/[0.02]">
                                <td className="px-4 py-3 font-mono text-slate-500">{req.KeyID}</td>
                                <td className="px-4 py-3">
                                  <div className="font-bold text-slate-200">{req.client_code}</div>
                                  <div className="text-[10px] text-slate-500 truncate max-w-[140px]">{cli?.razon_social || cli?.nombre_fantasia || '—'}</div>
                                </td>
                                <td className="px-4 py-3 font-mono text-[11px] text-amber-300">{req.r_number}</td>
                                <td className="px-4 py-3">
                                  <div className="font-semibold text-slate-200 truncate max-w-[160px]">{req.r_id || '—'}</div>
                                  <div className="text-[10px] text-slate-500">{req.r_user || '—'}</div>
                                </td>
                                <td className="px-4 py-3">
                                  <div className="truncate max-w-[180px] text-slate-400" title={req.r_path}>{req.r_path || '—'}</div>
                                  <div className="text-[10px] text-slate-500 truncate max-w-[180px]">{req.r_OS || '—'}</div>
                                </td>
                                <td className="px-4 py-3">
                                  <span className={`px-2 py-1 rounded-lg text-[10px] font-black border ${
                                    req.r_state === '0' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                                    req.r_state === '1' || req.r_state === '3' || req.r_state === '4' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                                    req.r_state === '2' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                                    'bg-slate-800 text-slate-400 border-white/5'
                                  }`}>{req.r_state_label || req.r_state}</span>
                                </td>
                                <td className="px-4 py-3">
                                  <div className="flex flex-wrap gap-1 justify-end">
                                    <button type="button" onClick={() => handleResolveActiRequest(req, '1')} className="px-2 py-1 rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 text-[10px] font-black">Activar</button>
                                    <button type="button" onClick={() => handleResolveActiRequest(req, '2')} className="px-2 py-1 rounded-lg bg-red-500/15 text-red-400 border border-red-500/20 text-[10px] font-black">Denegar</button>
                                    <button type="button" onClick={() => handleResolveActiRequest(req, '0')} className="px-2 py-1 rounded-lg bg-slate-800 text-slate-300 border border-white/10 text-[10px] font-black">Pendiente</button>
                                    <button type="button" onClick={() => handleResolveActiRequest(req, '3')} className="px-2 py-1 rounded-lg bg-sky-500/15 text-sky-400 border border-sky-500/20 text-[10px] font-black">+Msg</button>
                                    <button type="button" onClick={() => handleResolveActiRequest(req, '4')} className="px-2 py-1 rounded-lg bg-violet-500/15 text-violet-400 border border-violet-500/20 text-[10px] font-black">+Fecha</button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ====================================================== */}
            {/* SECCIÓN: EXTENSIONES OnLine (misi_extension)           */}
            {/* ====================================================== */}
            {activeTab === 'extensiones' && (
              <div className="space-y-6 animate-in slide-in-from-bottom-8">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div>
                    <h1 className="text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      <CalendarDays className="text-sky-400" size={36} />
                      Extensiones OnLine
                    </h1>
                    <p className="text-slate-400 mt-1.5">
                      Pedidos de extensión (misi_extension) · Generar = e_date + l_period → nueva expiración
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        const next = !extShowAll;
                        setExtShowAll(next);
                        loadExtensiones(next);
                      }}
                      className={`px-4 py-3 rounded-2xl text-xs font-bold border transition-all ${extShowAll ? 'bg-sky-500/20 text-sky-300 border-sky-500/30' : 'bg-slate-800 text-slate-300 border-white/5'}`}
                    >
                      {extShowAll ? 'Solo pendientes' : 'Ver todas'}
                    </button>
                    <button
                      type="button"
                      onClick={() => loadExtensiones()}
                      className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs px-4 py-3 rounded-2xl border border-white/5"
                    >
                      🔄 Actualizar
                    </button>
                  </div>
                </div>

                <div className={`rounded-[1.75rem] border shadow-xl overflow-hidden ${darkMode ? 'bg-slate-900 border-white/5' : 'bg-white border-slate-200'}`}>
                  {extensionesLoading ? (
                    <div className="p-12 text-center text-slate-400 text-sm">Cargando extensiones…</div>
                  ) : extensiones.length === 0 ? (
                    <div className="p-12 text-center text-slate-500 text-sm">No hay extensiones {extShowAll ? '' : 'pendientes'}.</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-black/20 text-[10px] uppercase tracking-wider text-slate-500">
                          <tr>
                            <th className="px-4 py-3">Cliente</th>
                            <th className="px-4 py-3">Serial</th>
                            <th className="px-4 py-3">Expiración</th>
                            <th className="px-4 py-3">Nueva / Sugerida</th>
                            <th className="px-4 py-3">Periodo</th>
                            <th className="px-4 py-3 text-right">Acción</th>
                          </tr>
                        </thead>
                        <tbody>
                          {extensiones.map((ext) => (
                            <tr key={ext.KeyID} className="border-t border-white/5 hover:bg-white/[0.02]">
                              <td className="px-4 py-3">
                                <div className="font-bold text-slate-200">{ext.client_code}</div>
                                <div className="text-[10px] text-slate-500 truncate max-w-[160px]">{ext.client_name || '—'}</div>
                              </td>
                              <td className="px-4 py-3 font-mono text-[11px] text-sky-300">{ext.e_number}</td>
                              <td className="px-4 py-3 font-mono">{ext.e_date || '—'}</td>
                              <td className="px-4 py-3 font-mono">
                                {ext.e_newdate ? (
                                  <span className="text-emerald-400">{ext.e_newdate}</span>
                                ) : (
                                  <span className="text-amber-400">{ext.suggested_newdate || '—'}</span>
                                )}
                              </td>
                              <td className="px-4 py-3">{ext.l_period ?? '—'} días</td>
                              <td className="px-4 py-3 text-right">
                                {ext.pending ? (
                                  <button
                                    type="button"
                                    onClick={() => handleApproveExtension(ext)}
                                    className="px-3 py-1.5 rounded-xl bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-500/30 text-[10px] font-black uppercase"
                                  >
                                    Generar
                                  </button>
                                ) : (
                                  <span className="text-[10px] text-emerald-500 font-bold uppercase">Generada</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}

          </div>
        </div>

        {activeSessions.length > 0 && (
          <div className="absolute inset-0 z-[60] flex items-center justify-center bg-black/90 backdrop-blur-md animate-in fade-in p-8">
            <div className="w-full h-full flex flex-col gap-6 animate-in zoom-in-95">
              <div className="flex justify-between items-center text-white">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  <Monitor className="text-emerald-500" />
                  Centro de Comando Remoto ({activeSessions.length} Activas)
                </h2>
                <button onClick={() => setActiveSessions([])} className="hover:bg-white/10 p-2 rounded-full transition-colors"><X size={32} /></button>
              </div>

              <div className={`flex-1 grid gap-6 ${activeSessions.length === 1 ? 'grid-cols-1' : 'grid-cols-2 lg:grid-cols-3'} overflow-y-auto pr-2 custom-scrollbar`}>
                {activeSessions.map((session) => {
                  const frame = sessionFrames[session.id];
                  const cmdInfo = sessionCmds[session.id] || { current: "", history: [] };
                  const isFocused = focusedSessionId === session.id;
                  return (
                    <div key={session.id} className={`bg-slate-900 rounded-3xl overflow-hidden flex flex-col relative group shadow-2xl transition-all duration-300 border-2 ${isFocused ? 'border-brand-500 shadow-brand-500/15 ring-2 ring-brand-500/20 scale-[1.01]' : 'border-white/10'}`}>
                      {/* Cabecera de Sesión en Rejilla */}
                      <div className="flex items-center justify-between px-5 py-3 bg-slate-950/40 border-b border-white/5 select-none shrink-0">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${(session.is_online || frame) ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
                          <span className="text-xs font-black text-slate-200 truncate max-w-[140px]" title={session.device_name}>
                            {session.device_name || "PC Remota"}
                          </span>
                          {deviceAssistLabel(session) ? (
                            <span className="text-[9px] bg-sky-500/15 text-sky-400 border border-sky-500/20 px-1.5 py-0.5 rounded font-mono font-black" title="ID de asistencia">
                              ID {deviceAssistLabel(session)}
                            </span>
                          ) : (
                            <span className="text-[9px] bg-slate-800/60 text-slate-400 px-1.5 py-0.5 rounded font-mono font-bold">
                              #{session.id}
                            </span>
                          )}
                          {session.alt_remote_id && (
                            <span className="text-[8px] bg-slate-800/40 text-slate-500 px-1 py-0.5 rounded font-mono" title="RustDesk">
                              RD {session.alt_remote_id}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5">
                          {(() => {
                            const gridSessions = winSessionsByDevice[session.id] ?? [];
                            const gridSwitching = sessionSwitchingDeviceId === session.id
                              || (sessionSwitching && focusedSessionId === session.id);
                            const gridPickerOpen = sessionPickerDeviceId === session.id;
                            const wsForCard = wsViewerConnected && focusedSessionId === session.id;
                            return (
                              <div className="relative">
                                <button
                                  type="button"
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    setFocusedSessionId(session.id);
                                    if (gridPickerOpen) {
                                      setSessionPickerDeviceId(null);
                                    } else {
                                      setSessionPickerDeviceId(session.id);
                                      await refreshWindowsSessionsForDevice(session.id);
                                    }
                                  }}
                                  className={`text-[9px] font-bold px-2 py-0.5 rounded border transition-all ${
                                    gridSwitching
                                      ? 'bg-amber-600/40 border-amber-500/40 text-amber-200 animate-pulse'
                                      : 'bg-slate-800/80 border-white/10 text-slate-400 hover:text-white hover:bg-slate-700'
                                  }`}
                                  title="Sesiones Windows (Consola / RDP)"
                                >
                                  👤 {gridSwitching ? '…' : (gridSessions.find(s => s.current)?.username?.split('\\').pop() || 'Sesión')}
                                </button>
                                {gridPickerOpen && !gridSwitching && (
                                  <div
                                    className="absolute right-0 top-full mt-1 z-[80] min-w-[200px] bg-slate-900 border border-white/10 rounded-xl shadow-2xl p-1"
                                    onClick={e => e.stopPropagation()}
                                  >
                                    <div className="px-2 py-1 text-[9px] text-slate-500 font-bold uppercase">Sesiones</div>
                                    {gridSessions.length === 0 ? (
                                      <div className="px-2 py-2 text-[10px] text-slate-500 italic">Cargando…</div>
                                    ) : gridSessions.map(s => (
                                      <button
                                        key={s.id}
                                        type="button"
                                        onClick={async () => {
                                          setSessionPickerDeviceId(null);
                                          setFocusedSessionId(session.id);
                                          if (s.current) return;
                                          const disc = (s.state || '').toLowerCase().includes('disc');
                                          if (disc) {
                                            setSessionSwitchError('Sesión RDP desconectada: elegí Consola o una sesión Activa.');
                                            return;
                                          }
                                          if (s.id < 1 || s.id > 65535) return;
                                          beginSessionSwitch(session.id, s.id);
                                          if (wsForCard) {
                                            sendViewerCommand({ type: 'switch_session', session_id: s.id });
                                          } else {
                                            await sendCentinelaControl(session.id, { type: 'switch_session', session_id: s.id });
                                          }
                                        }}
                                        className={`w-full text-left px-2 py-1.5 rounded text-[10px] ${
                                          s.current ? 'bg-brand-500/20 text-brand-300' : 'hover:bg-slate-700 text-slate-300'
                                        }`}
                                      >
                                        {s.name?.toLowerCase() === 'console' && !s.username
                                          ? `Consola (#${s.id})`
                                          : (s.username || s.name || `#${s.id}`)}
                                        {s.current ? ' ●' : ''}
                                      </button>
                                    ))}
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setSessionPickerDeviceId(null);
                                        setLoginDeviceId(session.id);
                                        setFocusedSessionId(session.id);
                                        setShowLoginModal(true);
                                        setLoginError('');
                                      }}
                                      className="w-full text-left px-2 py-1.5 rounded text-[10px] text-slate-400 hover:bg-slate-700 border-t border-white/5 mt-1"
                                    >
                                      🔑 Iniciar sesión
                                    </button>
                                  </div>
                                )}
                              </div>
                            );
                          })()}
                          {isFocused && (
                            <span className="text-[8px] bg-brand-500/20 text-brand-400 border border-brand-500/30 px-1.5 py-0.5 rounded font-extrabold flex items-center gap-1 animate-pulse">
                              ⌨️ CONTROL
                            </span>
                          )}
                          {isCapsLockActive && isFocused && (
                            <span className="text-[8px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-1.5 py-0.5 rounded font-extrabold flex items-center gap-1 animate-pulse">
                              🔠 MAYÚS
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="absolute top-16 right-4 z-20 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => {
                          const idStr = String(session.id);
                          if (!chatVisibility[idStr]) fetchChatHistory(session.id);
                          setChatVisibility(prev => ({ ...prev, [idStr]: !prev[idStr] }));
                        }} className={`p-2 rounded-xl text-white shadow-lg border border-white/10 ${chatVisibility[String(session.id)] ? 'bg-brand-600' : 'bg-brand-500/80'}`}>
                          <MessageSquare size={16} />
                        </button>
                        <button onClick={async () => {
                          try {
                            const text = await navigator.clipboard.readText();
                            if (!text) return;
                            await pasteTextToRemote(session.id, text);
                          } catch (err) {
                            const text = prompt("Ingrese el texto a enviar al portapapeles de la PC cliente:");
                            if (text !== null) {
                              await pasteTextToRemote(session.id, text);
                            }
                          }
                        }} className="bg-blue-500/80 p-2 rounded-xl text-white shadow-lg border border-white/10" title="Pegar texto o archivos en el cliente">
                          <Clipboard size={16} />
                        </button>
                        <button
                          onClick={() => captureRemoteScreenToClipboard(session.id)}
                          className="bg-violet-500/80 p-2 rounded-xl text-white shadow-lg border border-white/10"
                          title="Capturar pantalla → portapapeles"
                        >
                          <Camera size={16} />
                        </button>
                        <button onClick={() => fetchRemoteFiles(session.id)} className="bg-emerald-500/80 p-2 rounded-xl text-white shadow-lg border border-white/10">
                          <FileText size={16} />
                        </button>
                      </div>

                      <div
                        className="flex-1 bg-black flex items-center justify-center relative min-h-[300px]"
                        onDragOver={(e) => {
                          if (!isControlEnabled) return;
                          e.preventDefault();
                          e.dataTransfer.dropEffect = 'copy';
                          setIsDraggingFiles(true);
                        }}
                        onDragLeave={() => setIsDraggingFiles(false)}
                        onDrop={(e) => {
                          e.preventDefault();
                          setIsDraggingFiles(false);
                          if (!isControlEnabled) return;
                          if (e.dataTransfer.files?.length) pasteFilesToRemote(session.id, e.dataTransfer.files);
                        }}
                      >
                        {frame ? (
                          <img
                            src={frame.startsWith('blob:') || frame.startsWith('data:') ? frame : `data:image;base64,${frame}`}
                            tabIndex={0}
                            onMouseDown={(e) => handleMouseDown(e, session.id)}
                            onMouseUp={(e) => handleMouseUp(e, session.id)}
                            onMouseMove={(e) => handleMouseMove(e, session.id)}
                            onMouseLeave={(e) => handleMouseLeave(e, session.id)}
                            onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); }}
                            onWheel={(e) => handleImageWheel(e, session.id)}
                            className="w-full h-full object-contain cursor-crosshair select-none outline-none"
                            alt="Remote Screen"
                          />
                        ) : (
                          <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-500 border-t-transparent" />
                        )}
                      </div>

                      <div className="p-4 bg-slate-900 border-t border-white/5 flex flex-col gap-3">
                        {/* Consola Remota */}
                        <div className="flex gap-2 items-center">
                          <span className="text-[10px] uppercase font-black text-slate-500 w-16">Consola:</span>
                          <input
                            type="text"
                            value={cmdInfo.current}
                            onChange={(e) => setSessionCmds({ ...sessionCmds, [session.id]: { ...cmdInfo, current: e.target.value } })}
                            onKeyDown={(e) => e.key === 'Enter' && handleSendCommand(session.id)}
                            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-xs text-emerald-400 font-mono outline-none"
                            placeholder="Comando de sistema..."
                          />
                          <button onClick={() => handleSendCommand(session.id)} className="bg-emerald-600 p-2 rounded-xl text-white hover:bg-emerald-700 transition-all">
                            <ArrowUpRight size={16} />
                          </button>
                        </div>
                        
                        {/* Teclado Typist Remoto */}
                        <div className="flex gap-2 items-center">
                          <span className="text-[10px] uppercase font-black text-slate-500 w-16">Teclado:</span>
                          <input
                            type="text"
                            id={`text-input-${session.id}`}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                const input = e.currentTarget;
                                if (input.value) {
                                  sendCentinelaControl(session.id, { type: 'write_text', text: input.value });
                                  input.value = '';
                                }
                              }
                            }}
                            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-xs text-brand-400 font-mono outline-none"
                            placeholder="Escribe texto y presiona Enter para escribirlo allá..."
                          />
                          <button
                            onClick={() => {
                              const input = document.getElementById(`text-input-${session.id}`) as HTMLInputElement;
                              if (input && input.value) {
                                sendCentinelaControl(session.id, { type: 'write_text', text: input.value });
                                input.value = '';
                              }
                            }}
                            className="bg-brand-500 p-2 rounded-xl text-white hover:bg-brand-600 transition-all"
                          >
                            <Sparkles size={16} />
                          </button>
                        </div>

                        {/* Teclas Rápidas */}
                        <div className="flex gap-2 items-center flex-wrap pl-16">
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'enter' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ⏎ Enter
                          </button>
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'escape' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ⎋ Esc
                          </button>
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'tab' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ⇥ Tab
                          </button>
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'backspace' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ⌫ Borrar
                          </button>
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'space' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ␣ Espacio
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Modal Detalle de Dispositivo Android */}
        {androidToggleConfirm && (
          <div className="fixed inset-0 z-[95] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in">
            <div className="bg-slate-900 border border-white/10 rounded-3xl max-w-md w-full shadow-2xl animate-in zoom-in-95 overflow-hidden">
              <div className={`p-5 border-b border-white/10 ${androidToggleConfirm.habilitado ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                <h3 className="text-lg font-black text-white flex items-center gap-2">
                  <Power size={20} className={androidToggleConfirm.habilitado ? 'text-emerald-400' : 'text-red-400'} />
                  {androidToggleConfirm.habilitado ? 'Activar dispositivo' : 'Desactivar dispositivo'}
                </h3>
              </div>
              <div className="p-5 space-y-3">
                <p className="text-sm text-slate-300 leading-relaxed">
                  {androidToggleConfirm.habilitado ? '¿Confirmás la activación de este nodo?' : '¿Confirmás la desactivación de este nodo?'}
                </p>
                <div className="rounded-2xl border border-white/10 bg-black/25 p-4 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-black bg-violet-500/20 text-violet-300 border border-violet-500/30">
                      {androidToggleConfirm.dev.app}
                    </span>
                    <span className="text-sm font-bold text-white">{androidDevicePrimaryLabel(androidToggleConfirm.dev)}</span>
                  </div>
                  {androidDeviceIdentityLines(androidToggleConfirm.dev).map(line => (
                    <div key={line.label} className="flex gap-2 text-[11px] min-w-0">
                      <span className="text-slate-500 font-black uppercase shrink-0 w-28">{line.label}</span>
                      <span className={`text-slate-200 break-all ${line.mono ? 'font-mono text-[10px]' : ''}`}>{line.value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="p-5 pt-0 flex gap-3">
                <button
                  type="button"
                  disabled={androidToggleBusy}
                  onClick={() => setAndroidToggleConfirm(null)}
                  className="flex-1 py-3 rounded-2xl text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 border border-white/10 transition-all disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  disabled={androidToggleBusy}
                  onClick={executeAndroidDeviceToggle}
                  className={`flex-1 py-3 rounded-2xl text-sm font-extrabold transition-all disabled:opacity-60 flex items-center justify-center gap-2 ${
                    androidToggleConfirm.habilitado
                      ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                      : 'bg-red-600 hover:bg-red-500 text-white'
                  }`}
                >
                  {androidToggleBusy ? 'Procesando…' : androidToggleConfirm.habilitado ? 'Activar' : 'Desactivar'}
                </button>
              </div>
            </div>
          </div>
        )}

        {androidDeviceDetailModal && (
          <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm animate-in fade-in p-4">
            <div className={`w-full max-w-lg rounded-3xl shadow-2xl border animate-in zoom-in-95 overflow-hidden ${darkMode ? 'bg-slate-900 border-white/10 text-white' : 'bg-white border-slate-200 text-slate-800'}`}>
              {/* Header */}
              <div className={`p-5 border-b border-white/10 flex items-center justify-between ${androidDeviceDetailModal.habilitado ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                <div className="flex items-center gap-3 min-w-0">
                  <Smartphone size={22} className={`shrink-0 ${androidDeviceDetailModal.habilitado ? 'text-emerald-400' : 'text-red-400'}`} />
                  <div className="min-w-0">
                    <h3 className="text-base font-extrabold text-white truncate">{androidDevicePrimaryLabel(androidDeviceDetailModal)}</h3>
                    <p className="text-[11px] text-slate-400 truncate">
                      {androidDeviceDetailModal.app_nombre} ({androidDeviceDetailModal.app})
                      {androidDeviceDetailModal.id != null ? ` · #${androidDeviceDetailModal.id}` : ''}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-[10px] font-black px-3 py-1.5 rounded-full border ${androidDeviceDetailModal.habilitado ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'}`}>
                    {androidDeviceDetailModal.habilitado ? '✅ HABILITADO' : '❌ INACTIVO'}
                  </span>
                  <button onClick={() => setAndroidDeviceDetailModal(null)} className="hover:bg-white/10 p-2 rounded-xl transition-all">
                    <X size={18} className="text-slate-400" />
                  </button>
                </div>
              </div>

              {/* Body */}
              <div className="p-5 space-y-3">
                {androidDeviceIdentityLines(androidDeviceDetailModal).map(({ label, value, mono }) => (
                  <div key={label} className={`flex items-start gap-3 p-3 rounded-xl ${darkMode ? 'bg-white/[0.03]' : 'bg-slate-50'}`}>
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-wider w-32 shrink-0 mt-0.5">{label}</span>
                    <span className={`text-xs font-semibold text-slate-200 break-all ${mono ? 'font-mono text-[10px]' : ''}`}>{value}</span>
                  </div>
                ))}

                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div className={`p-3 rounded-xl ${darkMode ? 'bg-white/[0.03]' : 'bg-slate-50'}`}>
                    <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider mb-1">Último acceso</div>
                    <div className="text-xs font-bold text-slate-200">
                      {androidDeviceDetailModal.ult_acceso ? new Date(androidDeviceDetailModal.ult_acceso).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                    </div>
                  </div>
                  <div className={`p-3 rounded-xl ${darkMode ? 'bg-white/[0.03]' : 'bg-slate-50'}`}>
                    <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider mb-1">Fecha de alta</div>
                    <div className="text-xs font-bold text-slate-200">
                      {androidDeviceDetailModal.fecha_registro ? new Date(androidDeviceDetailModal.fecha_registro).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-5 pb-5 flex gap-2">
                <button
                  type="button"
                  onClick={() => handleToggleAndroidDevice(androidDeviceDetailModal, !androidDeviceDetailModal.habilitado)}
                  className={`flex-1 py-3 rounded-2xl text-sm font-bold transition-all border flex items-center justify-center gap-2 ${
                    androidDeviceDetailModal.habilitado
                      ? 'bg-red-950/50 hover:bg-red-900/60 text-red-300 border-red-500/20'
                      : 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-400/30'
                  }`}
                >
                  <Power size={16} />
                  {androidDeviceDetailModal.habilitado ? 'Desactivar' : 'Activar esta PC / dispositivo'}
                </button>
                <button onClick={() => setAndroidDeviceDetailModal(null)} className="px-5 py-3 bg-slate-800 hover:bg-slate-700 rounded-2xl text-sm font-bold text-slate-300 transition-all border border-white/5">
                  Cerrar
                </button>
              </div>
            </div>
          </div>
        )}

        {isClientModalOpen && (
          <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm animate-in fade-in p-4 overflow-y-auto">
            <div className={`w-full ${clientActiveTab === 'erp_licensing' ? 'max-w-5xl font-sans' : 'max-w-2xl'} max-h-[90vh] flex flex-col p-6 rounded-3xl shadow-2xl border animate-in zoom-in-95 transition-all duration-300 ${darkMode ? 'bg-slate-900 border-white/10 text-white shadow-[0_0_50px_rgba(245,158,11,0.08)]' : 'bg-white border-slate-200 text-slate-800'}`}>
              <div className="flex justify-between items-center mb-6 border-b pb-4 dark:border-white/5 shrink-0">
                <div>
                  <h3 className="text-xl font-extrabold tracking-tight">
                    {editingClient ? 'Editar cliente GesActi' : 'Alta de cliente GesActi'}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">Mismos datos que F2 Alta de GesActi: código de 4 caracteres, producto y cliente de facturación. Después se genera el serial.</p>
                </div>
                <button onClick={() => setIsClientModalOpen(false)} className="hover:bg-white/10 p-2 rounded-xl transition-all">
                  <X size={20} />
                </button>
              </div>

              {/* Tabs */}
              <div className="flex gap-2 border-b pb-3 mb-6 dark:border-white/5 overflow-x-auto shrink-0">
                {[
                  { id: 'basic', label: 'Básico' },
                  { id: 'erp', label: 'ERP & Cuenta' },
                  { id: 'support', label: 'Soporte & Licencia' },
                  ...(editingClient ? [{ id: 'erp_licensing', label: 'Activaciones ERP (MySQL)' }] : [])
                ].map(tab => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setClientActiveTab(tab.id)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${clientActiveTab === tab.id ? 'bg-brand-500 text-white shadow-md' : 'text-slate-400 hover:bg-white/5'}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <form onSubmit={handleCreateOrUpdateClient} className="flex-1 flex flex-col min-h-0 space-y-0">
                <div className="flex-1 overflow-y-auto pr-1.5 space-y-6 min-h-0 custom-scrollbar mb-4 pb-2">
                {/* Tab: Básico */}
                {clientActiveTab === 'basic' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in duration-200">
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Producto ApolloGesCom</label>
                      <select
                        disabled={!!editingClient}
                        value={(clientForm.version_apollo || 'E').toUpperCase().slice(0, 1)}
                        onChange={e => {
                          const v = e.target.value;
                          setClientForm({ ...clientForm, version_apollo: v });
                          if (!editingClient) suggestNextGesactiCode(v);
                        }}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      >
                        <option value="E">Apollo ERP (código &lt; M, ej. 0677)</option>
                        <option value="S">ApolloGesCom Single (código M…)</option>
                        <option value="R">Apollo Clock (código R…)</option>
                        <option value="P">Apollo Pharmakos (código V…)</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Código GesCom (4 car.)</label>
                      <div className="flex gap-2">
                        <input
                          placeholder="Ej. 0677"
                          maxLength={4}
                          disabled={!!editingClient}
                          value={clientForm.codigo}
                          onChange={e => setClientForm({ ...clientForm, codigo: e.target.value.toUpperCase() })}
                          className={`w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 font-mono ${editingClient ? 'opacity-60 cursor-not-allowed dark:border-white/5' : 'dark:border-white/10'}`}
                        />
                        {!editingClient && (
                          <button type="button" onClick={() => suggestNextGesactiCode(clientForm.version_apollo || 'E')} className="px-3 rounded-xl border border-white/10 text-[10px] font-black uppercase whitespace-nowrap">Siguiente</button>
                        )}
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Cliente GesCom facturación (F10 / CCLIFAC)</label>
                      <input
                        placeholder="Ej. 0100154"
                        value={clientForm.cclifac}
                        onChange={e => setClientForm({ ...clientForm, cclifac: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10 font-mono"
                      />
                    </div>
                    {userProfile?.rol === 'admin' && resellers.length > 0 && (
                      <div className="md:col-span-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Revendedor Asignado</label>
                        <select
                          className="w-full p-3 rounded-xl border bg-slate-800 text-white text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                          value={clientForm.reseller_id || ''}
                          onChange={e => setClientForm({ ...clientForm, reseller_id: e.target.value ? Number(e.target.value) : null })}
                        >
                          <option value="" className="bg-slate-800 text-white">— Sin asignar (cliente directo) —</option>
                          {resellers.filter((r: any) => r.activo !== false).map((r: any) => (
                            <option key={r.id} value={r.id} className="bg-slate-800 text-white">{r.nombre}</option>
                          ))}
                        </select>
                      </div>
                    )}
                    <div className="flex items-center gap-3 md:col-span-2 bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <input
                        type="checkbox"
                        checked={clientForm.activo !== false}
                        onChange={e => setClientForm({ ...clientForm, activo: e.target.checked })}
                      />
                      <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Cliente activo</span>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">CUIT o DNI (Identificador Fiscal)</label>
                      <input
                        placeholder="Ej. 201506230"
                        value={clientForm.identificador_fiscal}
                        onChange={e => setClientForm({ ...clientForm, identificador_fiscal: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Razón Social</label>
                      <input
                        required
                        placeholder="Razón Social Legal de la Empresa"
                        value={clientForm.razon_social}
                        onChange={e => setClientForm({ ...clientForm, razon_social: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nombre Fantasía</label>
                      <input
                        placeholder="Nombre comercial o fantasía"
                        value={clientForm.nombre_fantasia}
                        onChange={e => setClientForm({ ...clientForm, nombre_fantasia: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Localidad / Ciudad</label>
                      <input
                        placeholder="Ej. GUALEGUAYCHU"
                        value={clientForm.localidad}
                        onChange={e => setClientForm({ ...clientForm, localidad: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Teléfono de Contacto</label>
                      <input
                        placeholder="Teléfono"
                        value={clientForm.telefono}
                        onChange={e => setClientForm({ ...clientForm, telefono: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Email Principal</label>
                      <input
                        type="email"
                        placeholder="ejemplo@empresa.com"
                        value={clientForm.email}
                        onChange={e => setClientForm({ ...clientForm, email: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                  </div>
                )}

                {/* Tab: ERP & Cuenta */}
                {clientActiveTab === 'erp' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in duration-200">
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Saldo Cuenta Corriente</label>
                      <div className={`p-4 rounded-2xl border flex items-center justify-between ${darkMode ? 'bg-black/20' : 'bg-slate-50'}`}>
                        <span className="text-xs text-slate-400 font-bold">Estado de Cuenta</span>
                        <span className={`text-xl font-black font-mono ${(clientForm.saldo || 0) > 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                          {new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(clientForm.saldo || 0)}
                        </span>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Fecha último pago</label>
                      <div className={`p-4 rounded-2xl border ${darkMode ? 'bg-black/20' : 'bg-slate-50'}`}>
                        <span className="text-sm font-black font-mono text-slate-700 dark:text-slate-200">
                          {formatFechaLocal(clientForm.fecha_ultimo_pago) || 'Sin registro'}
                        </span>
                      </div>
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Estado de Cuenta Corriente (ClasiCli)</label>
                      <select
                        value={normalizeEstadoCodigo(clientForm.clasificacion_codigo) || ''}
                        onChange={e => {
                          const cod = e.target.value;
                          const est = estadosCta.find((x: any) => normalizeEstadoCodigo(x.codigo) === cod);
                          setClientForm({
                            ...clientForm,
                            clasificacion_codigo: cod,
                            clasificacion_nombre: est?.descripcion || '',
                          });
                        }}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      >
                        <option value="">Sin estado</option>
                        {estadosCta.filter((e: any) => e.activo !== false).map((e: any) => (
                          <option key={e.id || e.codigo} value={normalizeEstadoCodigo(e.codigo)}>
                            {e.codigo} — {e.descripcion}
                          </option>
                        ))}
                      </select>
                      <p className="text-[10px] text-slate-500 mt-1.5">
                        Mismo catálogo que ERP → Cobranzas → Estados de Ctas Ctes. Gestionar con el botón «Estados Cta».
                      </p>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Código Vendedor</label>
                      <input
                        placeholder="Código Vend."
                        value={clientForm.vendedor_codigo}
                        onChange={e => setClientForm({ ...clientForm, vendedor_codigo: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Vendedor Asignado</label>
                      <input
                        placeholder="Nombre Vendedor"
                        value={clientForm.vendedor_nombre}
                        onChange={e => setClientForm({ ...clientForm, vendedor_nombre: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                  </div>
                )}

                {/* Tab: Soporte & Licencia */}
                {clientActiveTab === 'support' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in duration-200">
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Versión Apollo ERP</label>
                      <input
                        placeholder="Ej. E o 3"
                        value={clientForm.version_apollo}
                        onChange={e => setClientForm({ ...clientForm, version_apollo: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Fecha Vencimiento Soporte</label>
                      <input
                        type="date"
                        value={clientForm.fecha_vencimiento}
                        onChange={e => setClientForm({ ...clientForm, fecha_vencimiento: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10 text-slate-400"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Módulos Habilitados (Separados por coma)</label>
                      <input
                        placeholder="Base, Facturación, etc."
                        value={clientForm.modulos}
                        onChange={e => setClientForm({ ...clientForm, modulos: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">API Key de Integración Apollo</label>
                      <input
                        placeholder="Generada automáticamente o ingresada"
                        value={clientForm.apikey_apollo}
                        onChange={e => setClientForm({ ...clientForm, apikey_apollo: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10 font-mono"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">PIN Acceso Soporte Remoto (Centinela)</label>
                      <input
                        type="text"
                        placeholder="PIN de acceso remoto"
                        value={clientForm.remote_password}
                        onChange={e => setClientForm({ ...clientForm, remote_password: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10 font-mono"
                      />
                    </div>
                  </div>
                )}

                {/* Tab: Activaciones ERP (MySQL) */}
                {clientActiveTab === 'erp_licensing' && (
                  <div className="space-y-6 animate-in fade-in duration-200 text-slate-300">
                    <div className="flex flex-wrap gap-4 items-center justify-between bg-slate-900/50 p-4 rounded-2xl border border-white/5">
                      <div>
                        <h4 className="text-sm font-extrabold text-white">Licenciamiento de Cliente en Servidor Activo</h4>
                        <p className="text-xs text-slate-400 mt-0.5">Gestión directa de seriales y nodos en mysql1.apollogescom.com.ar</p>
                      </div>
                      <div className="flex gap-2 font-sans">
                        <button
                          type="button"
                          onClick={async () => {
                            const mods = await loadErpModules();
                            const d = new Date();
                            d.setDate(d.getDate() + 60);
                            const dateSugg = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
                            setNewSerialForm({
                              l_number: '',
                              l_date: dateSugg,
                              l_peri2016: 30,
                              l_raso: clientForm.razon_social || '',
                              l_nomfa: clientForm.nombre_fantasia || '',
                              l_cuit: clientForm.identificador_fiscal || '',
                              l_tele: clientForm.telefono || '',
                              l_locali: clientForm.localidad || ''
                            });
                            const v = (clientForm.version_apollo || 'E').toUpperCase().slice(0, 1);
                            const preset = v === 'S' ? 'S' : v === 'R' ? 'R' : v === 'P' ? 'P' : 'E';
                            const key = ({ E: 'm_erp', S: 'm_single', R: 'm_clock', P: 'm_pharmakos' } as Record<string, string>)[preset];
                            setSerialAllModules(false);
                            setSerialModuleNums((mods || []).filter((m: any) => m[key] && m.m_exe !== 'GESACTI').map((m: any) => m.m_num));
                            setShowNewSerialForm(true);
                          }}
                          className="bg-brand-500 hover:bg-brand-600 text-white px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-md"
                        >
                          <Plus size={14} /> Generar serial GesActi
                        </button>
                        <button
                          type="button"
                          onClick={() => loadErpLicenses(clientForm.codigo)}
                          className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 border border-white/5"
                        >
                          Recargar
                        </button>
                      </div>
                    </div>

                    {/* Formulario de Nuevo Serial */}
                    {showNewSerialForm && (
                      <div className="p-5 bg-slate-900/80 rounded-2xl border border-brand-500/30 space-y-4 animate-in slide-in-from-top-4 shadow-lg">
                        <div className="flex justify-between items-center border-b border-white/5 pb-2">
                          <h5 className="text-xs font-black text-brand-400 uppercase tracking-widest">Generar número de serie (GesActi)</h5>
                          <button
                            type="button"
                            onClick={() => setShowNewSerialForm(false)}
                            className="text-slate-400 hover:text-white"
                          >
                            <X size={16} />
                          </button>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-sans">
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Serial generado (25 car.)</label>
                            <input
                              readOnly
                              value={newSerialForm.l_number}
                              placeholder="Elegí módulos y tocá Generar"
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white font-mono outline-none"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Fecha expiración (máx. 60 días)</label>
                            <input
                              type="date"
                              required
                              value={newSerialForm.l_date}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_date: e.target.value })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500 text-slate-400"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Días Renovación Automática (Auto-Ext)</label>
                            <input
                              type="number"
                              value={newSerialForm.l_peri2016}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_peri2016: parseInt(e.target.value) || 30 })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Razón Social</label>
                            <input
                              value={newSerialForm.l_raso}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_raso: e.target.value })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">CUIT</label>
                            <input
                              value={newSerialForm.l_cuit}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_cuit: e.target.value })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Localidad</label>
                            <input
                              value={newSerialForm.l_locali}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_locali: e.target.value })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex flex-wrap gap-1.5">
                            {[
                              ['E', 'ERP Enterprise'],
                              ['C', 'Commerce'],
                              ['S', 'Single'],
                              ['L', 'Little'],
                              ['R', 'Reloj'],
                              ['P', 'Pharmakos'],
                              ['TODOS', 'Todos (incl. futuros)'],
                            ].map(([id, label]) => (
                              <button
                                key={id}
                                type="button"
                                onClick={() => applySerialPreset(id)}
                                className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-[10px] font-black uppercase border border-white/10"
                              >
                                {label}
                              </button>
                            ))}
                          </div>
                          {serialAllModules ? (
                            <p className="text-[11px] text-amber-400">Serial con todos los módulos ($$$$$$$$$$$$), igual que Alt+F10 en GesActi.</p>
                          ) : (
                            <div className="max-h-40 overflow-y-auto grid grid-cols-1 sm:grid-cols-2 gap-1 pr-1">
                              {erpModules.filter((m: any) => m.m_exe !== 'GESACTI').map((m: any) => (
                                <label key={m.m_num} className="flex items-center gap-2 text-[11px] text-slate-300 bg-black/20 rounded-lg px-2 py-1">
                                  <input
                                    type="checkbox"
                                    checked={serialModuleNums.includes(m.m_num)}
                                    onChange={() => {
                                      setSerialModuleNums(prev => prev.includes(m.m_num) ? prev.filter(x => x !== m.m_num) : [...prev, m.m_num]);
                                    }}
                                  />
                                  <span className="font-mono text-slate-500">{m.m_num}</span>
                                  <span className="truncate">{m.m_desc || m.m_exe}</span>
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                          <button
                            type="button"
                            onClick={() => setShowNewSerialForm(false)}
                            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-400 text-xs transition-colors"
                          >
                            Cancelar
                          </button>
                          <button
                            type="button"
                            onClick={handleGenerateGesactiSerial}
                            className="px-3.5 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs"
                          >
                            Generar serial
                          </button>
                          <button
                            type="button"
                            onClick={handleCreateNewErpSerial}
                            disabled={!newSerialForm.l_number}
                            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white font-bold text-xs transition-colors"
                          >
                            Guardar en MySQL
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Tabla de Licencias */}
                    {isErpLicensesLoading ? (
                      <div className="flex justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-500 border-t-transparent" />
                      </div>
                    ) : erpLicenses.length === 0 ? (
                      <div className="text-center py-8 bg-slate-900/30 border border-dashed border-white/5 rounded-2xl">
                        <AlertCircle className="w-8 h-8 text-slate-500 mx-auto mb-2" />
                        <p className="text-slate-400 text-xs">No se encontraron licencias comerciales en MySQL para este código de cliente ({clientForm.codigo}).</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                        {/* Lista de Licencias */}
                        <div className="space-y-3 lg:col-span-5 w-full min-w-0">
                          <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Licencias del Cliente ({erpLicenses.length})</label>
                          
                          {/* Desktop View Table */}
                          <div className="hidden xl:block overflow-x-auto rounded-2xl border border-white/5 bg-slate-950/40">
                            <table className="w-full text-left border-collapse text-xs">
                              <thead>
                                <tr className="border-b border-white/5 bg-white/5 font-extrabold text-slate-400">
                                  <th className="p-3">Número de Serial</th>
                                  <th className="p-3">Vencimiento</th>
                                  <th className="p-3 text-center">Auto-Ext</th>
                                  <th className="p-3">Estado</th>
                                  <th className="p-3 text-right">Acciones</th>
                                </tr>
                              </thead>
                              <tbody>
                                {erpLicenses.map(lic => {
                                  const isSelected = selectedErpSerial === lic.l_number;
                                  return (
                                    <tr
                                      key={lic.l_number}
                                      onClick={() => {
                                        setSelectedErpSerial(lic.l_number);
                                        loadErpTerminals(lic.l_number);
                                      }}
                                      className={`border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors ${isSelected ? 'bg-brand-500/10 border-l-4 border-l-brand-500' : ''}`}
                                    >
                                      <td className="p-3 font-mono font-bold text-white whitespace-nowrap text-[11px]" title={lic.l_number}>{lic.l_number}</td>
                                      <td className="p-3 whitespace-nowrap">
                                        <div className="font-semibold text-slate-200 text-[11px]">{lic.l_date || "S/V"}</div>
                                        {lic.m_newdate && (
                                          <div className="text-[9px] text-brand-400">Forzado: {lic.m_newdate}</div>
                                        )}
                                      </td>
                                      <td className="p-3 text-center font-mono font-semibold text-slate-300 text-[11px]">{lic.l_peri2016} d</td>
                                      <td className="p-3">
                                        {lic.l_desact ? (
                                          <span className="bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-0.5 rounded-full text-[9px] font-bold">DESACT</span>
                                        ) : (
                                          <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full text-[9px] font-bold">ACTIVA</span>
                                        )}
                                      </td>
                                      <td className="p-3 text-right whitespace-nowrap" onClick={e => e.stopPropagation()}>
                                        <div className="flex gap-1 justify-end">
                                          <button
                                            type="button"
                                            title="Configurar Cartel y Bloqueo"
                                            onClick={() => {
                                              loadErpTemplates();
                                              setBannerForm({
                                                serial: lic.l_number,
                                                client_codes: [],
                                                m_down: lic.m_down,
                                                m_newdate: lic.m_newdate || '',
                                                m_tipmsg: lic.m_tipmsg || 1,
                                                m_showmode: lic.m_showmode || '01',
                                                m_text: lic.m_text || ''
                                              });
                                              setShowBannerConfigModal(true);
                                            }}
                                            className="p-1 bg-slate-800 hover:bg-slate-700 text-amber-400 rounded-lg transition-colors border border-white/5"
                                          >
                                            <AlertCircle size={13} />
                                          </button>
                                          <button
                                            type="button"
                                            title="Reportes (GesActi) — Nodos / System"
                                            onClick={() => openReportsForSerial(lic.l_number)}
                                            className="p-1 bg-slate-800 hover:bg-slate-700 text-indigo-400 rounded-lg transition-colors border border-white/5"
                                          >
                                            <FileText size={13} />
                                          </button>
                                          <button
                                            type="button"
                                            title="Cambiar Auto-Extensión"
                                            onClick={() => handleExtendErpLicense(lic.l_number, parseInt(lic.l_peri2016) || 30, lic.l_date)}
                                            className="p-1 bg-slate-800 hover:bg-slate-700 text-brand-400 rounded-lg transition-colors border border-white/5"
                                          >
                                            <Edit2 size={13} />
                                          </button>
                                          <button
                                            type="button"
                                            title={lic.l_desact ? "Activar Licencia" : "Desactivar Licencia"}
                                            onClick={() => handleToggleErpLicense(lic.l_number, lic.l_desact)}
                                            className={`p-1 rounded-lg transition-colors border border-white/5 ${lic.l_desact ? 'bg-emerald-950/50 hover:bg-emerald-900/50 text-emerald-400' : 'bg-red-950/50 hover:bg-red-900/50 text-red-400'}`}
                                          >
                                            <Shield size={13} />
                                          </button>
                                        </div>
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>

                          {/* Mobile View / Intermediate Tablet Cards */}
                          <div className="block xl:hidden space-y-3">
                            {erpLicenses.map(lic => {
                              const isSelected = selectedErpSerial === lic.l_number;
                              return (
                                <div
                                  key={lic.l_number}
                                  onClick={() => {
                                    setSelectedErpSerial(lic.l_number);
                                    loadErpTerminals(lic.l_number);
                                  }}
                                  className={`p-3 rounded-2xl border transition-all cursor-pointer ${
                                    isSelected
                                      ? 'bg-brand-500/10 border-brand-500/40 shadow-lg shadow-brand-500/5'
                                      : 'bg-slate-950/20 border-white/5 hover:border-white/10'
                                  } space-y-2.5`}
                                >
                                  <div className="flex justify-between items-start text-left">
                                    <div>
                                      <span className="text-[11px] font-mono font-bold text-white block select-all">{lic.l_number}</span>
                                      <span className="text-[9px] text-slate-500 block mt-0.5">Vence: {lic.l_date || "S/V"}</span>
                                    </div>
                                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                                      <button
                                        type="button"
                                        title="Configurar Cartel y Bloqueo"
                                        onClick={() => {
                                          loadErpTemplates();
                                          setBannerForm({
                                            serial: lic.l_number,
                                            client_codes: [],
                                            m_down: lic.m_down,
                                            m_newdate: lic.m_newdate || '',
                                            m_tipmsg: lic.m_tipmsg || 1,
                                            m_showmode: lic.m_showmode || '01',
                                            m_text: lic.m_text || ''
                                          });
                                          setShowBannerConfigModal(true);
                                        }}
                                        className="p-1 bg-slate-800 hover:bg-slate-700 text-amber-400 rounded-lg transition-colors border border-white/5"
                                      >
                                        <AlertCircle size={13} />
                                      </button>
                                      <button
                                        type="button"
                                        title="Reportes (GesActi)"
                                        onClick={() => openReportsForSerial(lic.l_number)}
                                        className="p-1 bg-slate-800 hover:bg-slate-700 text-indigo-400 rounded-lg transition-colors border border-white/5"
                                      >
                                        <FileText size={13} />
                                      </button>
                                      <button
                                        type="button"
                                        title="Cambiar Auto-Extensión"
                                        onClick={() => handleExtendErpLicense(lic.l_number, parseInt(lic.l_peri2016) || 30, lic.l_date)}
                                        className="p-1 bg-slate-800 hover:bg-slate-700 text-brand-400 rounded-lg transition-colors border border-white/5"
                                      >
                                        <Edit2 size={13} />
                                      </button>
                                      <button
                                        type="button"
                                        title={lic.l_desact ? "Activar Licencia" : "Desactivar Licencia"}
                                        onClick={() => handleToggleErpLicense(lic.l_number, lic.l_desact)}
                                        className={`p-1 rounded-lg transition-colors border border-white/5 ${lic.l_desact ? 'bg-emerald-950/50 hover:bg-emerald-900/50 text-emerald-400' : 'bg-red-950/50 hover:bg-red-900/50 text-red-400'}`}
                                      >
                                        <Shield size={13} />
                                      </button>
                                    </div>
                                  </div>

                                  <div className="flex flex-wrap gap-1.5 items-center text-[9px]">
                                    <div>
                                      {lic.l_desact ? (
                                        <span className="bg-red-500/10 text-red-400 border border-red-500/20 px-1.5 py-0.5 rounded font-bold">DESACT</span>
                                      ) : (
                                        <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded font-bold">ACTIVA</span>
                                      )}
                                    </div>
                                    <div>
                                      <span className="bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded font-semibold font-mono">Auto-Ext: {lic.l_peri2016}d</span>
                                    </div>
                                    {lic.m_down && (
                                      <span className="bg-red-500/10 text-red-400 border border-red-500/20 px-1 py-0.5 rounded font-bold">SUSPENDIDA</span>
                                    )}
                                    {lic.m_tipmsg > 1 && (
                                      <span className="bg-amber-500/15 text-amber-400 border border-amber-500/20 px-1 py-0.5 rounded font-bold flex items-center gap-0.5">
                                        CARTEL
                                      </span>
                                    )}
                                    {lic.m_tipmsg > 1 && (
                                      <span
                                        className="bg-sky-500/15 text-sky-300 border border-sky-500/25 px-1 py-0.5 rounded font-black font-mono"
                                        title={`m_showmode=${lic.m_showmode || '01'}`}
                                      >
                                        {formatShowmodeLabel(lic.m_showmode) || 'OK'}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>

                        {/* Detalle de Nodos (Terminales) de la Licencia Seleccionada */}
                        <div className="space-y-3 lg:col-span-7 w-full min-w-0">
                          <div className="flex justify-between items-center">
                            <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block truncate text-left">
                              Terminales para <span className="font-mono text-white text-[11px] pl-1">{selectedErpSerial || 'ninguno'}</span>
                            </label>
                            {selectedErpSerial && (
                              <button
                                type="button"
                                onClick={() => loadErpTerminals(selectedErpSerial)}
                                className="text-[10px] font-bold text-slate-400 hover:text-white transition-colors flex items-center gap-1 shrink-0"
                              >
                                Actualizar Nodos
                              </button>
                            )}
                          </div>

                          {isErpTerminalsLoading ? (
                            <div className="flex justify-center py-6 bg-slate-950/20 rounded-2xl border border-white/5">
                              <div className="animate-spin rounded-full h-6 w-6 border-2 border-brand-500 border-t-transparent" />
                            </div>
                          ) : !selectedErpSerial ? (
                            <div className="text-center py-6 bg-slate-950/20 rounded-2xl border border-dashed border-white/5 text-slate-500 text-xs">
                              Seleccione un serial para visualizar sus computadoras terminales asociadas.
                            </div>
                          ) : erpTerminals.length === 0 ? (
                            <div className="text-center py-6 bg-slate-950/20 rounded-2xl border border-white/5 text-slate-400 text-xs">
                              No hay terminales registradas para este serial.
                            </div>
                          ) : (
                            <>
                              {/* Desktop View Table */}
                              <div className="hidden xl:block overflow-x-auto rounded-2xl border border-white/5 bg-slate-950/40 min-w-0 w-full">
                                <table className="w-full text-left border-collapse text-xs">
                                  <thead>
                                    <tr className="border-b border-white/5 bg-white/5 font-extrabold text-slate-400">
                                      <th className="p-3">Nombre PC (ID)</th>
                                      <th className="p-3">Usuario Windows</th>
                                      <th className="p-3">S.O.</th>
                                      <th className="p-3">Último Acceso</th>
                                      <th className="p-3">MAC / Placa</th>
                                      <th className="p-3">Ruta</th>
                                      <th className="p-3 text-right">Desact</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {erpTerminals.map(terminal => (
                                      <tr key={terminal.KeyID} className="border-b border-white/5 hover:bg-white/5 text-slate-300 font-sans">
                                        <td className="p-3 font-bold text-white whitespace-nowrap text-[11px]">{terminal.t_id || "Desconocida"}</td>
                                        <td className="p-3 whitespace-nowrap text-[11px]">{terminal.t_user || "N/A"}</td>
                                        <td className="p-3 text-slate-400 whitespace-nowrap text-[11px]">{terminal.t_OS || "Windows"}</td>
                                        <td className="p-3 whitespace-nowrap">
                                          <div className="font-semibold text-[11px]">{terminal.t_access || terminal.t_active || "N/A"}</div>
                                          <div className="text-[9px] text-slate-500">Reg: {terminal.t_active}</div>
                                        </td>
                                        <td className="p-3 font-mono text-[10px] text-slate-400 whitespace-nowrap">{terminal.t_netmac || "N/A"}</td>
                                        <td className="p-3 text-slate-400 max-w-[120px] truncate text-[11px]" title={terminal.t_path}>{terminal.t_path || "N/A"}</td>
                                        <td className="p-3 text-right whitespace-nowrap">
                                          <button
                                            type="button"
                                            onClick={() => handleDeactivateErpNode(terminal)}
                                            title="Desactivar / Bloquear esta PC"
                                            className="p-1 bg-red-950/45 hover:bg-red-900/60 text-red-400 rounded-lg transition-colors border border-red-500/10"
                                          >
                                            <Trash2 size={13} />
                                          </button>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>

                              {/* Mobile View / Intermediate Tablet Cards */}
                              <div className="block xl:hidden space-y-3">
                                {erpTerminals.map(terminal => (
                                  <div key={terminal.KeyID} className="p-3 rounded-2xl border border-white/5 bg-slate-950/20 space-y-2 text-left">
                                    <div className="flex justify-between items-start gap-2">
                                      <div className="truncate">
                                        <span className="text-[11px] font-black text-white block truncate">{terminal.t_id || "Desconocida"}</span>
                                        <span className="text-[9px] text-slate-500 block">Usuario: {terminal.t_user || "N/A"}</span>
                                      </div>
                                      <button
                                        type="button"
                                        onClick={() => handleDeactivateErpNode(terminal)}
                                        title="Desactivar / Bloquear esta PC"
                                        className="p-1 bg-red-950/45 hover:bg-red-900/60 text-red-400 rounded-lg transition-colors border border-red-500/10 shrink-0"
                                      >
                                        <Trash2 size={13} />
                                      </button>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 text-[9px] font-sans">
                                      <div>
                                        <span className="text-slate-500 block font-bold tracking-wider">S.O.</span>
                                        <span className="text-slate-300 font-semibold">{terminal.t_OS || "Windows"}</span>
                                      </div>
                                      <div>
                                        <span className="text-slate-500 block font-bold tracking-wider">Acceso</span>
                                        <span className="text-slate-300 font-semibold">{terminal.t_access || terminal.t_active || "N/A"}</span>
                                      </div>
                                      <div className="col-span-2">
                                        <span className="text-slate-500 block font-bold tracking-wider">MAC / Placa</span>
                                        <span className="text-slate-400 font-mono font-semibold">{terminal.t_netmac || "N/A"}</span>
                                      </div>
                                      <div className="col-span-2">
                                        <span className="text-slate-500 block font-bold tracking-wider">Ruta Instalación</span>
                                        <span className="text-slate-400 font-semibold truncate block max-w-full" title={terminal.t_path}>{terminal.t_path || "N/A"}</span>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                </div>

                {clientActiveTab !== 'erp_licensing' ? (
                  <div className="flex gap-3 pt-4 border-t dark:border-white/5 shrink-0">
                    <button
                      type="button"
                      onClick={() => setIsClientModalOpen(false)}
                      className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white transition-colors"
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-extrabold py-3 rounded-2xl shadow-lg transition-all text-sm uppercase tracking-wider"
                    >
                      {isSubmitting ? 'Guardando...' : 'Guardar Cambios'}
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-3 pt-4 border-t dark:border-white/5 shrink-0">
                    <button
                      type="button"
                      onClick={() => setIsClientModalOpen(false)}
                      className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3 rounded-2xl shadow-lg transition-all text-sm uppercase tracking-wider text-center"
                    >
                      Cerrar Panel de Activaciones
                    </button>
                  </div>
                )}
              </form>
            </div>
          </div>
        )}

        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4 animate-in fade-in">
            <div className={`w-full max-w-xl p-6 sm:p-8 rounded-[2rem] border shadow-2xl animate-in slide-in-from-bottom-6 ${darkMode ? 'glass-dark border-brand-500/15' : 'bg-white border-slate-200'}`}>
              <div className="flex justify-between items-start mb-5">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-widest text-brand-500 mb-1">Atención → Programación</p>
                  <h3 className="text-xl font-black">Nuevo pedido</h3>
                  <p className="text-xs text-slate-400 mt-1">Lo ve todo el sector de desarrollo, aunque lo dirijas a un programador.</p>
                </div>
                <button type="button" onClick={() => setIsModalOpen(false)} className="p-2 hover:bg-red-500/10 rounded-full"><X size={20} className="text-slate-400" /></button>
              </div>
              <form onSubmit={handleCreateTicket} className="space-y-4">
                <div className="grid grid-cols-2 gap-2">
                  <button type="button" onClick={() => setNewOrigen('cliente')} className={`py-2.5 rounded-xl text-xs font-black uppercase tracking-wider border transition-all ${newOrigen === 'cliente' ? 'bg-sky-500/15 text-sky-400 border-sky-500/30' : 'border-white/10 text-slate-400'}`}>Pedido de cliente</button>
                  <button type="button" onClick={() => { setNewOrigen('interno'); }} className={`py-2.5 rounded-xl text-xs font-black uppercase tracking-wider border transition-all ${newOrigen === 'interno' ? 'bg-violet-500/15 text-violet-400 border-violet-500/30' : 'border-white/10 text-slate-400'}`}>Pedido interno</button>
                </div>

                <div className="space-y-2">
                  {newOrigen === 'interno' && (
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Cliente relacionado (opcional)</p>
                  )}
                  <ClientSearchSelect
                    clients={clients}
                    valueId={newClientId}
                    onChange={(id) => setNewClientId(id)}
                    darkMode={darkMode}
                    placeholder={newOrigen === 'cliente' ? 'Buscar cliente por código o nombre (ej. 1307 Aguilar)...' : 'Buscar cliente (opcional)...'}
                    optionalLabel={newOrigen === 'interno' ? 'Sin cliente — pedido interno' : undefined}
                  />
                </div>

                <input required type="text" value={newSubject} onChange={e => setNewSubject(e.target.value)} placeholder="Asunto del pedido..." className={`w-full p-2.5 rounded-xl border outline-none text-sm ${darkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-slate-50 border-slate-200'}`} />
                <textarea required value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="Detalle para programación..." rows={4} className={`w-full p-2.5 rounded-xl border outline-none text-sm resize-none ${darkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-slate-50 border-slate-200'}`} />

                <div className={`rounded-xl border p-3 space-y-2 ${darkMode ? 'bg-black/20 border-white/10' : 'bg-slate-50 border-slate-200'}`}>
                  <label className="flex items-center justify-between gap-3 cursor-pointer">
                    <span className="flex items-center gap-2 text-xs font-bold text-slate-300">
                      <Paperclip size={14} className="text-brand-500" />
                      Adjuntos
                    </span>
                    <span className="text-[10px] font-black uppercase tracking-wider text-brand-500 bg-brand-500/10 px-2.5 py-1 rounded-lg border border-brand-500/20">
                      + Agregar archivos
                    </span>
                    <input
                      type="file"
                      multiple
                      accept=".xls,.xlsx,.csv,.jpg,.jpeg,.png,.gif,.webp,.bmp,.txt,.pdf,.doc,.docx,.zip,.xml,.json,.dbf"
                      className="hidden"
                      onChange={(e) => {
                        const picked = Array.from(e.target.files || []);
                        if (!picked.length) return;
                        const tooBig = picked.find((f) => f.size > 20 * 1024 * 1024);
                        if (tooBig) {
                          alert(`"${tooBig.name}" supera el límite de 20 MB.`);
                          e.target.value = '';
                          return;
                        }
                        setNewPedidoFiles((prev) => {
                          const names = new Set(prev.map((f) => `${f.name}-${f.size}`));
                          const extra = picked.filter((f) => !names.has(`${f.name}-${f.size}`));
                          return [...prev, ...extra].slice(0, 8);
                        });
                        e.target.value = '';
                      }}
                    />
                  </label>
                  <p className="text-[10px] text-slate-500">Excel, JPG, PNG, TXT, PDF y similares. Hasta 8 archivos / 20 MB c/u.</p>
                  {newPedidoFiles.length > 0 && (
                    <div className="space-y-1.5">
                      {newPedidoFiles.map((file, idx) => (
                        <div key={`${file.name}-${idx}`} className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-black/20 border border-white/5">
                          <FileText size={14} className="text-brand-400 shrink-0" />
                          <span className="flex-1 min-w-0 text-[11px] font-bold truncate text-slate-200">{file.name}</span>
                          <span className="text-[9px] text-slate-500 shrink-0">{file.size > 1024 * 1024 ? `${(file.size / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(file.size / 1024))} KB`}</span>
                          <button
                            type="button"
                            onClick={() => setNewPedidoFiles((prev) => prev.filter((_, i) => i !== idx))}
                            className="p-1 rounded-md text-slate-500 hover:text-red-400 hover:bg-red-500/10"
                            title="Quitar"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <select value={newPriority} onChange={e => setNewPriority(e.target.value)} className={`w-full p-2.5 rounded-xl border outline-none text-sm ${darkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-slate-50 border-slate-200'}`}>
                    <option value="baja">Prioridad baja</option>
                    <option value="media">Prioridad media</option>
                    <option value="alta">Prioridad alta</option>
                    <option value="critica">Prioridad crítica</option>
                  </select>
                  <select value={newAssigneeId} onChange={e => setNewAssigneeId(e.target.value)} className={`w-full p-2.5 rounded-xl border outline-none text-sm ${darkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-slate-50 border-slate-200'}`}>
                    <option value="">Todo el sector (sin asignar)</option>
                    {(users.filter((u: any) => userInDesarrollo(u)).length
                      ? users.filter((u: any) => userInDesarrollo(u))
                      : users
                    ).map((u: any) => (
                      <option key={u.id} value={u.id}>{u.full_name || u.nombre}</option>
                    ))}
                  </select>
                </div>

                <button type="submit" disabled={isSubmitting} className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white font-extrabold py-3.5 rounded-xl shadow-lg shadow-brand-500/20 transition-colors tracking-wide">
                  {isSubmitting ? (newPedidoFiles.length ? 'Subiendo adjuntos...' : 'Enviando...') : 'Enviar a Programación'}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* MODAL DEL TICKET (Derivador + IA Copiloto) */}
        {selectedTicket && (
          <div
            className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-900/80 backdrop-blur-sm p-3 sm:p-4 overflow-y-auto animate-in fade-in"
            onClick={closeTicketModal}
            onKeyDown={(e) => { if (e.key === 'Escape') closeTicketModal(); }}
            role="dialog"
            aria-modal="true"
          >
            <div
              className={`relative w-full max-w-4xl max-h-[92vh] overflow-y-auto p-5 sm:p-8 rounded-[2rem] border shadow-2xl flex flex-col gap-6 animate-in slide-in-from-bottom-8 ${darkMode ? 'glass-dark border-brand-500/15' : 'bg-white border-slate-200'}`}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Botón cerrar fijo: siempre visible aunque DevTools estreche la pantalla */}
              <button
                type="button"
                onClick={closeTicketModal}
                className="absolute top-3 right-3 z-20 flex items-center gap-1.5 px-3 py-2 rounded-xl bg-red-500/15 border border-red-500/40 text-red-300 hover:bg-red-500/30 hover:text-white transition-all shadow-lg"
                title="Cerrar (Esc)"
              >
                <X size={18} />
                <span className="text-[10px] font-black uppercase tracking-wider">Cerrar</span>
              </button>
              
              {/* Cabecera */}
              <div className="flex justify-between items-start gap-4 pr-24">
                <div>
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <span className="text-brand-500 font-extrabold text-[10px] sm:text-xs uppercase tracking-widest bg-brand-500/10 px-3 py-1 rounded-full">
                      Requerimiento #{selectedTicket.id}
                    </span>
                    <span className={`font-extrabold text-[10px] sm:text-xs uppercase tracking-widest px-3 py-1 rounded-full ${
                      (selectedTicket.estado || '').toLowerCase() === 'entregado'
                        ? 'text-sky-400 bg-sky-500/10'
                        : (selectedTicket.estado || '').toLowerCase() === 'resuelto'
                          ? 'text-emerald-400 bg-emerald-500/10'
                          : (selectedTicket.estado || '').toLowerCase() === 'en_curso'
                            ? 'text-brand-400 bg-brand-500/10'
                            : 'text-blue-400 bg-blue-500/10'
                    }`}>
                      {(selectedTicket.estado || 'nuevo').replace('_', ' ')}
                    </span>
                    <span className={`font-extrabold text-[10px] sm:text-xs uppercase tracking-widest px-3 py-1 rounded-full ${(selectedTicket.origen || 'cliente') === 'interno' ? 'text-violet-400 bg-violet-500/10' : 'text-sky-400 bg-sky-500/10'}`}>
                      {(selectedTicket.origen || 'cliente') === 'interno' ? 'Pedido interno' : 'Pedido de cliente'}
                    </span>
                    <span className="text-slate-400 font-extrabold text-[10px] sm:text-xs uppercase tracking-widest bg-slate-500/10 px-3 py-1 rounded-full">
                      {selectedTicket.clientName || selectedTicket.cliente?.razon_social || (selectedTicket.origen === 'interno' ? 'Interno' : 'Sin cliente')}
                    </span>
                    {ticketRegisteredBy(selectedTicket) && (
                      <span className="text-amber-300 font-extrabold text-[10px] sm:text-xs uppercase tracking-widest bg-amber-500/10 px-3 py-1 rounded-full">
                        Registró: {ticketRegisteredBy(selectedTicket)}
                      </span>
                    )}
                  </div>
                  <h2 className="text-xl sm:text-2xl font-black text-slate-800 dark:text-white leading-tight">
                    {selectedTicket.asunto}
                  </h2>
                </div>
                <div className="hidden sm:flex items-center gap-2 shrink-0 flex-wrap justify-end max-w-[40%]">
                  {(selectedTicket.estado || '').toLowerCase() !== 'entregado' && !isEditingTicket && (
                    <button
                      type="button"
                      onClick={() => {
                        setEditSubject(selectedTicket.asunto || "");
                        setEditDesc(selectedTicket.descripcion || "");
                        setEditPriority(selectedTicket.prioridad || "media");
                        setEditOrigen((selectedTicket.origen === "interno" ? "interno" : "cliente") as "cliente" | "interno");
                        setEditClientId(selectedTicket.client_id ? String(selectedTicket.client_id) : "");
                        setIsEditingTicket(true);
                      }}
                      className="px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/25 transition-all"
                      title="Corregir asunto, detalle, cliente u origen"
                    >
                      Editar pedido
                    </button>
                  )}
                  {(selectedTicket.estado || '').toLowerCase() === 'resuelto' && (
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          const updated = await updateTicketStatus(selectedTicket.id, 'entregado');
                          setSelectedTicket({ ...selectedTicket, ...updated, clientName: selectedTicket.clientName });
                          loadData();
                          setShowNotification('Pedido entregado → pasó a histórico');
                          setTimeout(() => setShowNotification(null), 3000);
                          closeTicketModal();
                        } catch (err: any) {
                          alert(err?.message || 'No se pudo dar por entregado');
                        }
                      }}
                      className="px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider bg-sky-500/15 text-sky-300 border border-sky-500/30 hover:bg-sky-500/25 transition-all"
                      title="Cierra el pedido y lo mueve al histórico"
                    >
                      Dar por entregado
                    </button>
                  )}
                  {(selectedTicket.estado || '').toLowerCase() !== 'resuelto' && (selectedTicket.estado || '').toLowerCase() !== 'entregado' && (
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          const updated = await updateTicketStatus(selectedTicket.id, 'resuelto');
                          setSelectedTicket({ ...selectedTicket, ...updated, clientName: selectedTicket.clientName });
                          loadData();
                          setShowNotification('Resuelto: vuelve a Atención para entrega');
                          setTimeout(() => setShowNotification(null), 3000);
                        } catch (err: any) {
                          alert(err?.message || 'No se pudo marcar como resuelto');
                        }
                      }}
                      className="px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 transition-all"
                    >
                      Marcar resuelto
                    </button>
                  )}
                </div>
              </div>

              {/* Grid Principal: Izquierda (Detalle e Intervenciones) | Derecha (IA Copiloto y Control Remoto) */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 overflow-hidden">
                
                {/* Columna Izquierda: Historial e Intervención (7 cols) */}
                <div className="lg:col-span-7 flex flex-col gap-4">
                  <div className={`p-5 rounded-2xl border flex flex-col gap-4 max-h-[480px] overflow-y-auto custom-scrollbar ${darkMode ? 'bg-dark-bg/60 border-white/5' : 'bg-slate-50 border-slate-200'}`}>
                    
                    {/* Requerimiento Original */}
                    <div className="border-l-4 border-brand-500 pl-4 py-1 mb-2 bg-brand-500/5 p-3 rounded-r-xl">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <p className="text-[9px] font-black text-brand-500 uppercase tracking-widest">Descripción del Problema</p>
                        {(selectedTicket.estado || '').toLowerCase() !== 'entregado' && !isEditingTicket && (
                          <button
                            type="button"
                            onClick={() => {
                              setEditSubject(selectedTicket.asunto || "");
                              setEditDesc(selectedTicket.descripcion || "");
                              setEditPriority(selectedTicket.prioridad || "media");
                              setEditOrigen((selectedTicket.origen === "interno" ? "interno" : "cliente") as "cliente" | "interno");
                              setEditClientId(selectedTicket.client_id ? String(selectedTicket.client_id) : "");
                              setIsEditingTicket(true);
                            }}
                            className="sm:hidden text-[9px] font-black uppercase tracking-wider text-amber-300"
                          >
                            Editar
                          </button>
                        )}
                      </div>
                      {isEditingTicket ? (
                        <div className="space-y-3 mt-2">
                          <div className="grid grid-cols-2 gap-2">
                            <button type="button" onClick={() => setEditOrigen('cliente')} className={`py-2 rounded-xl text-[10px] font-black uppercase tracking-wider border transition-all ${editOrigen === 'cliente' ? 'bg-sky-500/15 text-sky-400 border-sky-500/30' : 'border-white/10 text-slate-400'}`}>Pedido de cliente</button>
                            <button type="button" onClick={() => setEditOrigen('interno')} className={`py-2 rounded-xl text-[10px] font-black uppercase tracking-wider border transition-all ${editOrigen === 'interno' ? 'bg-violet-500/15 text-violet-400 border-violet-500/30' : 'border-white/10 text-slate-400'}`}>Pedido interno</button>
                          </div>
                          <ClientSearchSelect
                            clients={clients}
                            valueId={editClientId}
                            onChange={(id) => setEditClientId(id)}
                            darkMode={darkMode}
                            placeholder={editOrigen === 'cliente' ? 'Buscar cliente...' : 'Cliente (opcional)...'}
                            optionalLabel={editOrigen === 'interno' ? 'Sin cliente — pedido interno' : undefined}
                          />
                          <input
                            type="text"
                            value={editSubject}
                            onChange={(e) => setEditSubject(e.target.value)}
                            className={`w-full p-2.5 rounded-xl border outline-none text-sm font-semibold ${darkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-white border-slate-200'}`}
                            placeholder="Asunto..."
                          />
                          <textarea
                            value={editDesc}
                            onChange={(e) => setEditDesc(e.target.value)}
                            rows={5}
                            className={`w-full p-2.5 rounded-xl border outline-none text-sm resize-y ${darkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-white border-slate-200'}`}
                            placeholder="Detalle..."
                          />
                          <select
                            value={editPriority}
                            onChange={(e) => setEditPriority(e.target.value)}
                            className={`w-full p-2.5 rounded-xl border outline-none text-sm ${darkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-white border-slate-200'}`}
                          >
                            <option value="baja">Prioridad baja</option>
                            <option value="media">Prioridad media</option>
                            <option value="alta">Prioridad alta</option>
                            <option value="critica">Prioridad crítica</option>
                          </select>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              disabled={isSavingTicketEdit}
                              onClick={handleSaveTicketEdit}
                              className="flex-1 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider bg-brand-500 hover:bg-brand-600 text-white disabled:opacity-50"
                            >
                              {isSavingTicketEdit ? 'Guardando...' : 'Guardar cambios'}
                            </button>
                            <button
                              type="button"
                              disabled={isSavingTicketEdit}
                              onClick={() => setIsEditingTicket(false)}
                              className="px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider border border-white/10 text-slate-400 hover:bg-white/5"
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      ) : (
                      <p className="text-sm font-semibold text-slate-700 dark:text-slate-200 whitespace-pre-wrap">{selectedTicket.descripcion}</p>
                      )}
                      {((selectedTicket.intervenciones || interventions || []).filter((inv: any) => inv.adjunto_url)).length > 0 && (
                        <div className="mt-3 space-y-1.5">
                          <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Archivos adjuntos</p>
                          {(selectedTicket.intervenciones || interventions || []).filter((inv: any) => inv.adjunto_url).map((inv: any) => (
                            <a
                              key={`adj-${inv.id}`}
                              href={attachmentHref(inv.adjunto_url)}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-2 px-2.5 py-2 rounded-xl bg-black/20 border border-white/5 hover:border-brand-500/30 transition-all"
                            >
                              <Paperclip size={13} className="text-brand-400 shrink-0" />
                              <span className="flex-1 min-w-0 text-[11px] font-extrabold truncate text-slate-200">
                                {attachmentDisplayName(inv.adjunto_url, inv.mensaje?.replace(/^Adjunto del pedido:\s*/i, ''))}
                              </span>
                              <ArrowUpRight size={13} className="text-brand-500 shrink-0" />
                            </a>
                          ))}
                        </div>
                      )}
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                          Visible para todo Programación
                        </span>
                        <select
                          value={selectedTicket.assigned_user_id || ""}
                          onClick={e => e.stopPropagation()}
                          onChange={async (e) => {
                            const val = e.target.value ? parseInt(e.target.value) : null;
                            try {
                              const updated = await assignTicket(selectedTicket.id, val);
                              setSelectedTicket({ ...selectedTicket, ...updated, clientName: selectedTicket.clientName });
                              loadData();
                            } catch (err: any) {
                              alert(err?.message || "No se pudo asignar.");
                            }
                          }}
                          className={`text-[10px] font-black px-3 py-1.5 rounded-xl border outline-none uppercase tracking-wider ${darkMode ? 'bg-black/20 border-white/5 text-slate-300' : 'bg-white border-slate-200'}`}
                        >
                          <option value="">Todo el sector (sin asignar)</option>
                          {users.filter((u: any) => userInDesarrollo(u)).map((u: any) => (
                            <option key={u.id} value={u.id}>{u.full_name || u.nombre}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Intervenciones */}
                    <div className="space-y-5">
                      {interventions.length === 0 ? (
                        <p className="text-xs text-slate-500 italic text-center p-4">No hay intervenciones previas registradas.</p>
                      ) : (
                        interventions.map((inv: any) => (
                          <div key={inv.id} className="relative pl-6 animate-in fade-in slide-in-from-left-2 transition-all">
                            <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-slate-200 dark:bg-white/10" />
                            <div className="absolute left-[-4px] top-2 w-2 h-2 rounded-full bg-brand-500 ring-4 ring-brand-500/10 shadow-[0_0_8px_rgba(245,158,11,0.3)]" />

                            <div className="flex justify-between items-start mb-1.5">
                              <div>
                                <span className="text-[11px] font-extrabold text-slate-800 dark:text-slate-200">{inv.usuario?.full_name || 'Sistema'}</span>
                                {inv.area_destino && (
                                  <span className="ml-2 text-[8px] font-black px-2 py-0.5 rounded-md bg-brand-500/15 text-brand-500 uppercase tracking-widest border border-brand-500/10">
                                    Pase a {inv.area_destino.nombre}
                                  </span>
                                )}
                              </div>
                              <span className="text-[8px] font-bold text-slate-500 uppercase">{new Date(inv.fecha_creacion).toLocaleString()}</span>
                            </div>

                            <div className={`p-4 rounded-2xl text-xs sm:text-sm ${darkMode ? 'bg-white/5 border border-white/5 text-slate-300' : 'bg-white border border-slate-200 shadow-sm text-slate-700'}`}>
                              {inv.mensaje && <p className="leading-relaxed whitespace-pre-wrap">{inv.mensaje}</p>}

                              {inv.adjunto_url && (
                                <div className="mt-2 p-2.5 rounded-xl bg-black/20 border border-white/5 flex items-center gap-2.5">
                                  <FileText size={16} className="text-brand-400" />
                                  <div className="flex-1 min-w-0">
                                    <p className="text-[11px] font-extrabold truncate">{inv.adjunto_url.split('/').pop()}</p>
                                    <p className="text-[8px] text-slate-500 uppercase">{inv.adjunto_tipo}</p>
                                  </div>
                                  <a href={attachmentHref(inv.adjunto_url)} target="_blank" rel="noreferrer" className="text-brand-500 hover:text-brand-400"><ArrowUpRight size={14} /></a>
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Formulario de Intervención */}
                  <form onSubmit={handleSendIntervention} className={`p-4 rounded-2xl border space-y-4 ${darkMode ? 'bg-dark-bg/30 border-white/5' : 'bg-slate-50 border-slate-200'}`}>
                    <textarea
                      value={newMessage}
                      onChange={e => setNewMessage(e.target.value)}
                      placeholder="Escribe un comentario técnico o pase de área..."
                      rows={2}
                      className={`w-full p-3 rounded-xl border outline-none text-xs sm:text-sm transition-all resize-none ${darkMode ? 'bg-black/20 border-white/5 text-white focus:border-brand-500/50' : 'bg-white border-slate-200 focus:border-brand-500'}`}
                    />

                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex flex-wrap gap-2">
                        <select
                          value={transferAreaId || ""}
                          onChange={e => setTransferAreaId(e.target.value ? parseInt(e.target.value) : null)}
                          className={`text-[10px] font-black px-3 py-2 rounded-xl border outline-none transition-all uppercase tracking-wider ${darkMode ? 'bg-black/20 border-white/5 text-slate-300' : 'bg-slate-50 border-slate-200'}`}
                        >
                          <option value="">Soporte (Sector Actual)</option>
                          {areas.filter(a => a.id !== selectedTicket.current_area_id).map(a => (
                            <option key={a.id} value={a.id}>Derivar a {a.nombre}</option>
                          ))}
                        </select>

                        <label className={`cursor-pointer p-2 rounded-xl border transition-all flex items-center gap-1.5 ${attachment ? 'bg-brand-500 border-brand-500 text-white' : 'bg-white/5 border-white/10 text-slate-400 hover:text-brand-500'}`}>
                          {isUploading ? <div className="animate-spin h-3 w-3 border-2 border-brand-500 border-t-transparent" /> : <Plus size={14} />}
                          <span className="text-[9px] font-black uppercase tracking-wider">{attachment ? attachment.name.slice(0,10) + '...' : 'Subir Adjunto'}</span>
                          <input type="file" className="hidden" onChange={e => e.target.files?.[0] && handleFileUpload(e.target.files[0])} />
                        </label>
                      </div>

                      <button
                        type="submit"
                        disabled={isSubmitting || (!newMessage.trim() && !attachmentUrl && !transferAreaId)}
                        className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30 transition-all text-center"
                      >
                        {isSubmitting ? 'Registrando...' : 'Grabar Intervención'}
                      </button>
                    </div>
                  </form>
                </div>

                {/* Columna Derecha: IA Copiloto y Control Remoto (5 cols) */}
                <div className="lg:col-span-5 flex flex-col gap-4">
                  
                  {/* Panel de IA Copiloto */}
                  <div className="p-5 rounded-2xl border bg-gradient-to-br from-indigo-500/5 to-transparent border-indigo-500/20 shadow-xl flex flex-col gap-4">
                    <h3 className="text-sm font-black flex items-center gap-2 text-indigo-400 uppercase tracking-widest border-b border-indigo-500/10 pb-2">
                      <Sparkles size={16} className="animate-pulse text-indigo-400" /> Copiloto Inteligente IA
                    </h3>
                    
                    {!aiSuggestion ? (
                      <div className="text-center py-4 space-y-3">
                        <p className="text-xs text-slate-400 leading-relaxed font-medium">
                          Analiza el incidente con el motor neuronal de Apollo para diagnosticar causas raíz (FoxPro, Spooler, Índices CDX), proponer acciones rápidas y redactar respuestas empáticas para clientes y pases técnicos a desarrollo.
                        </p>
                        <button
                          onClick={handleConsultarIA}
                          disabled={isAiLoading}
                          className="w-full bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 disabled:opacity-50 text-white font-extrabold py-3 rounded-xl shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 transition-all text-xs sm:text-sm uppercase tracking-wider"
                        >
                          {isAiLoading ? 'Analizando Diagnóstico Completo...' : 'Consultar Solución IA'}
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="max-h-[340px] overflow-y-auto pr-2 custom-scrollbar">
                          {renderAiAnalysisText(aiSuggestion)}
                        </div>
                        <div className="flex gap-2 border-t border-indigo-500/10 pt-3">
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(aiSuggestion);
                              setShowNotification("Análisis completo copiado al portapapeles.");
                              setTimeout(() => setShowNotification(null), 3000);
                            }}
                            className="flex-1 py-2 text-[10px] font-black text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/20 rounded-xl uppercase tracking-wider border border-indigo-500/15 transition-all"
                          >
                            Copiar Análisis
                          </button>
                          <button
                            onClick={() => setAiSuggestion(null)}
                            className="py-2 px-3 text-[10px] font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-xl border border-white/5 uppercase transition-all"
                          >
                            Volver a Consultar
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Panel de Mantenimiento Remoto Directo */}
                  <div className="p-5 rounded-2xl border border-slate-500/10 bg-slate-500/5 shadow-xl flex flex-col gap-4">
                    <h3 className="text-sm font-black flex items-center gap-2 text-slate-300 uppercase tracking-widest border-b border-white/5 pb-2">
                      <Monitor size={16} className="text-brand-500" /> Diagnóstico y Control de PCs
                    </h3>
                    
                    <div className="space-y-3.5">
                      {(() => {
                        const client = clients.find(c => c.id === selectedTicket.client_id);
                        if (!client || !client.devices || client.devices.length === 0) {
                          return <p className="text-xs text-slate-500 italic text-center py-2">Sin terminales registradas para este cliente.</p>;
                        }
                        return client.devices.map((dev: any) => {
                          const isOnline = centinelas[dev.id];
                          return (
                            <div key={dev.id} className={`p-3.5 rounded-xl border flex flex-col gap-2.5 transition-all ${isOnline ? 'bg-brand-500/5 border-brand-500/25' : 'bg-slate-500/5 border-slate-500/10 opacity-70'}`}>
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                  <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse' : 'bg-slate-400'}`} />
                                  <span className="text-xs font-extrabold text-white">{dev.device_name}</span>
                                  {deviceAssistLabel(dev) && (
                                    <span className="text-[9px] font-mono font-black text-sky-400 bg-sky-500/10 border border-sky-500/20 px-1.5 py-0.5 rounded-md">
                                      ID {deviceAssistLabel(dev)}
                                    </span>
                                  )}
                                </div>
                                <span className="text-[8px] font-mono font-bold text-slate-500 uppercase" title="ID interno">#{dev.id}</span>
                              </div>

                              {isOnline ? (
                                <div className="grid grid-cols-3 gap-2.5">
                                  <button
                                    onClick={async () => {
                                      const ok = await runCentinelaCommand(dev.id, "net stop spooler && net start spooler");
                                      if (ok) {
                                        setShowNotification("Comando de Spooler enviado con éxito.");
                                        setTimeout(() => setShowNotification(null), 3000);
                                      }
                                    }}
                                    className="py-2 px-1 text-[8px] font-black uppercase text-brand-500 bg-brand-500/10 hover:bg-brand-500/25 border border-brand-500/20 rounded-xl transition-all text-center"
                                  >
                                    Spooler
                                  </button>
                                  <button
                                    onClick={async () => {
                                      const ok = await runCentinelaCommand(dev.id, "del /q /s %temp%\\*");
                                      if (ok) {
                                        setShowNotification("Comando de Limpieza de Temporales enviado.");
                                        setTimeout(() => setShowNotification(null), 3000);
                                      }
                                    }}
                                    className="py-2 px-1 text-[8px] font-black uppercase text-red-400 bg-red-500/10 hover:bg-red-500/25 border border-red-500/20 rounded-xl transition-all text-center"
                                  >
                                    Limpiar Temp
                                  </button>
                                  <button
                                    onClick={() => handleVerifyRemotePassword(dev.id, isOnline?.remote_password || dev.remote_password || "")}
                                    className="py-2 px-1 text-[8px] font-black uppercase text-white bg-brand-500 hover:bg-brand-600 rounded-xl transition-all text-center"
                                  >
                                    Control
                                  </button>
                                </div>
                              ) : (
                                <p className="text-[9px] text-slate-500 italic">Desconectado. Visto por última vez: {dev.last_seen ? new Date(dev.last_seen).toLocaleDateString() : 'NUNCA'}</p>
                              )}
                            </div>
                          );
                        });
                      })()}
                    </div>
                  </div>

                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-3">
                <div className="flex flex-wrap gap-2 sm:hidden">
                  {(selectedTicket.estado || '').toLowerCase() === 'resuelto' && (
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          const updated = await updateTicketStatus(selectedTicket.id, 'entregado');
                          setSelectedTicket({ ...selectedTicket, ...updated, clientName: selectedTicket.clientName });
                          loadData();
                          closeTicketModal();
                        } catch (err: any) {
                          alert(err?.message || 'No se pudo dar por entregado');
                        }
                      }}
                      className="px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider bg-sky-500/15 text-sky-300 border border-sky-500/30"
                    >
                      Dar por entregado
                    </button>
                  )}
                  {(selectedTicket.estado || '').toLowerCase() !== 'resuelto' && (selectedTicket.estado || '').toLowerCase() !== 'entregado' && (
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          const updated = await updateTicketStatus(selectedTicket.id, 'resuelto');
                          setSelectedTicket({ ...selectedTicket, ...updated, clientName: selectedTicket.clientName });
                          loadData();
                        } catch (err: any) {
                          alert(err?.message || 'No se pudo marcar como resuelto');
                        }
                      }}
                      className="px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                    >
                      Marcar resuelto
                    </button>
                  )}
                </div>
                <button
                  type="button"
                  onClick={closeTicketModal}
                  className="ml-auto px-5 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider bg-slate-700/80 text-slate-100 border border-white/10 hover:bg-slate-600 transition-all"
                >
                  Cerrar ventana
                </button>
              </div>

            </div>
          </div>
        )}

      </main>

      {showBannerConfigModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl p-6 max-w-lg w-full space-y-6 shadow-2xl animate-in zoom-in-95 text-slate-300">
            <div className="flex justify-between items-center border-b border-white/5 pb-4">
              <div>
                <h3 className="text-lg font-black text-white flex items-center gap-2 font-sans">
                  <AlertCircle className="text-amber-500 animate-pulse" /> {bannerForm.client_codes?.length ? 'Monitoreo masivo (GesActi)' : 'Control y Configuración de Cartel ERP'}
                </h3>
                <p className="text-[11px] text-slate-400 mt-1">
                  {bannerForm.client_codes?.length
                    ? `Clientes marcados: ${bannerForm.client_codes.length} · se aplica a todas las licencias activas`
                    : <>Serial Licencia: <span className="font-mono font-bold text-slate-200">{bannerForm.serial}</span></>}
                </p>
              </div>
              <button onClick={() => setShowBannerConfigModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveBannerConfig} className="space-y-4 text-xs font-sans">
              {/* Suspender Licencia */}
              <div className="flex items-center justify-between bg-slate-800/40 p-4 rounded-xl border border-white/5">
                <div>
                  <label className="text-sm font-bold text-white block">Suspender Licencia de Forma Preventiva</label>
                  <p className="text-[10px] text-slate-400">Si se activa, impedirá el inicio y uso del ERP para todas las terminales.</p>
                </div>
                <input
                  type="checkbox"
                  checked={bannerForm.m_down}
                  onChange={e => setBannerForm({ ...bannerForm, m_down: e.target.checked })}
                  className="w-5 h-5 accent-brand-500 cursor-pointer"
                />
              </div>

              {/* Forzar Vencimiento */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">Forzar Vencimiento Manual (Ignorar Fecha de Serial)</label>
                <input
                  type="date"
                  value={bannerForm.m_newdate}
                  onChange={e => setBannerForm({ ...bannerForm, m_newdate: e.target.value })}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-xs"
                />
                <p className="text-[9px] text-slate-500 mt-1 font-sans">Deje vacío para respetar el vencimiento regular de la licencia.</p>
              </div>

              {/* Tipo de Mensaje */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Cartel de aviso (misi_messages)</label>
                  <button
                    type="button"
                    className="text-[10px] font-black uppercase text-amber-400 hover:text-amber-300"
                    onClick={() => { loadErpTemplates(); setShowAvisosCatalog(true); }}
                  >
                    Editar catálogo
                  </button>
                </div>
                <select
                  value={bannerForm.m_tipmsg}
                  onChange={e => {
                    const num = parseInt(e.target.value) || 1;
                    const tpl = erpTemplates.find((t: any) => Number(t.m_num ?? t.id) === num);
                    const tplText = (tpl?.m_text || tpl?.text || '').replace(/CRLF/g, '\n');
                    setBannerForm({
                      ...bannerForm,
                      m_tipmsg: num,
                      m_text: num <= 1 ? bannerForm.m_text : (tplText || bannerForm.m_text)
                    });
                  }}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-xs"
                >
                  <option value={1}>1 — Sin cartel / mensaje particular</option>
                  {erpTemplates.filter((t: any) => Number(t.m_num ?? t.id) > 1).map((t: any) => (
                    <option key={t.m_num ?? t.id} value={t.m_num ?? t.id}>
                      {t.m_num ?? t.id} — {t.m_des || t.label || 'Aviso'}
                    </option>
                  ))}
                </select>
                {erpTemplates.length === 0 && (
                  <p className="text-[10px] text-rose-400 mt-1">No se pudieron cargar los carteles de MySQL. Revisá el backend / conexión a misi_messages.</p>
                )}
              </div>

              {/* Modo de Muestra */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">
                  Demora / modo de muestra (habitual: 15 · 30 · 180 s)
                </label>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {[
                    { code: '03', label: '15s' },
                    { code: '04', label: '30s' },
                    { code: '05', label: '180s' },
                  ].map(opt => (
                    <button
                      key={opt.code}
                      type="button"
                      onClick={() => setBannerForm({ ...bannerForm, m_showmode: opt.code })}
                      className={`px-3 py-1.5 rounded-lg text-[10px] font-black border transition-all ${
                        bannerForm.m_showmode === opt.code
                          ? 'bg-sky-500/25 text-sky-200 border-sky-400/40'
                          : 'bg-slate-800 text-slate-300 border-white/10 hover:border-sky-500/30'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setBannerForm({ ...bannerForm, m_showmode: '01' })}
                    className={`px-3 py-1.5 rounded-lg text-[10px] font-black border transition-all ${
                      bannerForm.m_showmode === '01'
                        ? 'bg-slate-600 text-white border-white/20'
                        : 'bg-slate-800 text-slate-400 border-white/10'
                    }`}
                  >
                    OK
                  </button>
                </div>
                <select
                  value={bannerForm.m_showmode}
                  onChange={e => setBannerForm({ ...bannerForm, m_showmode: e.target.value })}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-xs font-sans"
                >
                  <option value="03">★ Demora 15 segundos (uso habitual)</option>
                  <option value="04">★ Demora 30 segundos (uso habitual)</option>
                  <option value="05">★ Demora 180 segundos (uso habitual)</option>
                  <option value="01">Formulario con botón Aceptar (una vez al inicio)</option>
                  <option value="02">Demora al inicio (5 segundos)</option>
                  <option value="06">Demora al inicio (60 segundos)</option>
                  <option value="07">Demora al inicio (120 segundos)</option>
                  <option value="08">Demora al inicio (240 segundos)</option>
                  <option value="09">Demora al inicio (300 segundos)</option>
                </select>
                <p className="text-[10px] text-slate-500 mt-1.5">
                  En cambios masivos, si no querés pisar demoras distintas, usá «Poner cartel» y elegí <strong className="text-slate-300">keep</strong>.
                </p>
              </div>

              {/* Mensaje de Cartel */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Texto del cartel (particular o del tipo elegido)</label>
                  <button
                    type="button"
                    onClick={() => setShowAvisoPreview(true)}
                    className="text-[10px] font-black uppercase text-brand-400 hover:text-brand-300"
                  >
                    Vista previa
                  </button>
                </div>
                <textarea
                  value={bannerForm.m_text}
                  onChange={e => setBannerForm({ ...bannerForm, m_text: e.target.value })}
                  placeholder="Si está vacío, GesCom usa el texto del tipo de cartel. Si escribís acá, ese es el que ve el cliente."
                  rows={4}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-xs resize-none"
                />
              </div>

              {/* Botones de acción */}
              <div className="flex gap-3 pt-2 font-sans">
                <button
                  type="button"
                  onClick={() => setShowBannerConfigModal(false)}
                  className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-400 hover:text-white transition-all text-xs font-bold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-black uppercase tracking-wider transition-all text-xs shadow-md"
                >
                  Aplicar {bannerForm.client_codes?.length ? 'a marcados' : 'cambios'} en MySQL
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showAvisoPreview && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4" onClick={() => setShowAvisoPreview(false)}>
          <div
            className="bg-[#1e3a5f] border-2 border-amber-400 rounded-sm shadow-2xl w-full max-w-md p-5 text-white font-sans"
            onClick={e => e.stopPropagation()}
          >
            <div className="text-center text-sm font-black uppercase tracking-widest text-amber-300 mb-3">Aviso ApolloGesCom</div>
            <div className="whitespace-pre-wrap text-sm leading-relaxed bg-black/30 rounded p-4 min-h-[120px]">
              {previewAvisoText()}
            </div>
            <p className="text-[10px] text-slate-300 mt-3 text-center">
              Visualización: {
                ({
                  '01': 'Botón Aceptar al inicio',
                  '02': 'Espera 5 s', '03': 'Espera 15 s', '04': 'Espera 30 s', '05': 'Espera 180 s',
                  '06': 'Espera 60 s', '07': 'Espera 120 s', '08': 'Espera 240 s', '09': 'Espera 300 s',
                } as Record<string, string>)[bannerForm.m_showmode] || bannerForm.m_showmode
              }
            </p>
            <button
              type="button"
              onClick={() => setShowAvisoPreview(false)}
              className="mt-4 w-full py-2 rounded bg-amber-500 hover:bg-amber-400 text-slate-900 font-black uppercase text-xs"
            >
              Aceptar
            </button>
          </div>
        </div>
      )}

      {showAvisosCatalog && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-amber-500/30 rounded-3xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto space-y-4 text-slate-300">
            <div className="flex justify-between items-center border-b border-white/5 pb-3">
              <div>
                <h3 className="text-lg font-black text-white">Carteles de aviso</h3>
                <p className="text-[11px] text-slate-400">Tabla misi_messages — los mismos textos que usa GesActi en el ERP del cliente.</p>
              </div>
              <button onClick={() => setShowAvisosCatalog(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400"><X size={20} /></button>
            </div>
            {erpTemplates.length === 0 ? (
              <p className="text-xs text-rose-400">No hay carteles en MySQL o falló la conexión.</p>
            ) : (
              <div className="space-y-2">
                {erpTemplates.map((t: any) => (
                  <button
                    type="button"
                    key={t.m_num ?? t.id}
                    onClick={() => setAvisoEdit({
                      m_num: Number(t.m_num ?? t.id),
                      m_des: t.m_des || t.label || '',
                      m_text: (t.m_text || t.text || '').replace(/CRLF/g, '\n'),
                    })}
                    className={`w-full text-left p-3 rounded-xl border transition-all ${avisoEdit.m_num === Number(t.m_num ?? t.id) ? 'border-amber-500/50 bg-amber-500/10' : 'border-white/5 bg-white/5 hover:bg-white/10'}`}
                  >
                    <div className="text-[11px] font-black text-amber-400">{t.m_num ?? t.id} — {t.m_des || t.label}</div>
                    <div className="text-[11px] text-slate-400 mt-1 whitespace-pre-wrap line-clamp-3">{(t.m_text || t.text || '').replace(/CRLF/g, '\n') || '(sin texto)'}</div>
                  </button>
                ))}
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 pt-2 border-t border-white/5">
              <input
                type="number"
                min={1}
                placeholder="Nº"
                value={avisoEdit.m_num || ''}
                onChange={e => setAvisoEdit({ ...avisoEdit, m_num: parseInt(e.target.value) || 0 })}
                className="sm:col-span-1 bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
              />
              <input
                placeholder="Nombre del cartel"
                value={avisoEdit.m_des}
                onChange={e => setAvisoEdit({ ...avisoEdit, m_des: e.target.value })}
                className="sm:col-span-3 bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
              />
              <textarea
                placeholder="Texto que verá el cliente (Enter = salto de línea)"
                value={avisoEdit.m_text}
                onChange={e => setAvisoEdit({ ...avisoEdit, m_text: e.target.value })}
                rows={4}
                className="sm:col-span-4 bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-white resize-none"
              />
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => setAvisoEdit({ m_num: (erpTemplates.reduce((m: number, t: any) => Math.max(m, Number(t.m_num || t.id || 0)), 0) + 1), m_des: '', m_text: '' })} className="px-4 py-2 rounded-xl border border-white/10 text-[10px] font-black uppercase">Nuevo</button>
              <button type="button" onClick={saveAvisoTemplate} className="flex-1 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-[10px] font-black uppercase">Guardar cartel</button>
            </div>
          </div>
        </div>
      )}

      {showEstadosCtaModal && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-teal-500/30 rounded-3xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto space-y-4 text-slate-300">
            <div className="flex justify-between items-center border-b border-white/5 pb-3">
              <div>
                <h3 className="text-lg font-black text-white">Estados de Cuenta Corriente</h3>
                <p className="text-[11px] text-slate-400">
                  Catálogo ClasiCli del ERP (Cobranzas → Estados de Ctas Ctes). Se usa para clasificar clientes (CCLAS).
                </p>
              </div>
              <button onClick={() => setShowEstadosCtaModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400"><X size={20} /></button>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleSyncEstadosCtaErp}
                className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-[10px] font-black uppercase"
              >
                Sincronizar desde ERP
              </button>
              <button
                type="button"
                onClick={() => loadEstadosCta(false)}
                className="px-4 py-2 rounded-xl border border-white/10 text-[10px] font-black uppercase"
              >
                Recargar
              </button>
            </div>

            {estadosCtaLoading ? (
              <p className="text-xs text-slate-500 py-6 text-center">Cargando…</p>
            ) : estadosCta.length === 0 ? (
              <p className="text-xs text-amber-400 py-4">Sin estados. Tocá «Sincronizar desde ERP» para importar ClasiCli.</p>
            ) : (
              <div className="space-y-2 max-h-[40vh] overflow-y-auto">
                {estadosCta.map((e: any) => (
                  <div
                    key={e.id}
                    className={`flex items-center justify-between gap-3 p-3 rounded-xl border ${e.activo === false ? 'opacity-50 border-white/5 bg-white/[0.02]' : 'border-white/5 bg-white/5'}`}
                  >
                    <button
                      type="button"
                      className="text-left min-w-0 flex-1"
                      onClick={() => setEstadoCtaEdit({
                        id: e.id,
                        codigo: e.codigo,
                        descripcion: e.descripcion || '',
                        activo: e.activo !== false,
                      })}
                    >
                      <div className="text-[11px] font-black text-teal-400 font-mono">{e.codigo}</div>
                      <div className="text-xs text-slate-200 truncate">{e.descripcion}</div>
                      <div className="text-[9px] text-slate-500 uppercase mt-0.5">{e.origen || 'manual'}{e.activo === false ? ' · inactivo' : ''}</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteEstadoCta(e)}
                      className="px-2 py-1 rounded-lg text-[9px] font-black uppercase text-rose-400 border border-rose-500/20 hover:bg-rose-500/10"
                    >
                      Baja
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 pt-2 border-t border-white/5">
              <input
                placeholder="Código"
                disabled={!!estadoCtaEdit.id}
                value={estadoCtaEdit.codigo}
                onChange={e => setEstadoCtaEdit({ ...estadoCtaEdit, codigo: e.target.value })}
                className="sm:col-span-1 bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-white font-mono disabled:opacity-60"
              />
              <input
                placeholder="Descripción (ej. DEBITO AUTOMATICO)"
                value={estadoCtaEdit.descripcion}
                onChange={e => setEstadoCtaEdit({ ...estadoCtaEdit, descripcion: e.target.value })}
                className="sm:col-span-2 bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
              />
              <label className="sm:col-span-1 flex items-center gap-2 text-[10px] font-bold uppercase text-slate-400 px-1">
                <input
                  type="checkbox"
                  checked={estadoCtaEdit.activo}
                  onChange={e => setEstadoCtaEdit({ ...estadoCtaEdit, activo: e.target.checked })}
                  className="accent-teal-500"
                />
                Activo
              </label>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setEstadoCtaEdit({ codigo: '', descripcion: '', activo: true })}
                className="px-4 py-2 rounded-xl border border-white/10 text-[10px] font-black uppercase"
              >
                Nuevo
              </button>
              <button
                type="button"
                onClick={handleSaveEstadoCta}
                className="flex-1 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-[10px] font-black uppercase"
              >
                {estadoCtaEdit.id ? 'Actualizar estado' : 'Alta estado'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showReportsModal && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-indigo-500/30 rounded-3xl p-6 max-w-5xl w-full max-h-[92vh] overflow-y-auto space-y-4 text-slate-300">
            <div className="flex justify-between items-start border-b border-white/5 pb-3 gap-3">
              <div>
                <h3 className="text-lg font-black text-white flex items-center gap-2">
                  <FileText className="text-indigo-400" size={18} /> Reportes serial
                </h3>
                <p className="text-[11px] text-slate-400 mt-1 font-mono">{reportsSerial}</p>
                <p className="text-[10px] text-slate-500 mt-0.5">Igual que GesActi → Licencias → Reportes → Nodos / System</p>
              </div>
              <button type="button" onClick={() => setShowReportsModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400"><X size={20} /></button>
            </div>
            <div className="flex flex-wrap gap-2 items-end">
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1">Desde</label>
                <input type="date" value={reportsFrom} onChange={e => setReportsFrom(e.target.value)} className="bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-white" />
              </div>
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1">Hasta</label>
                <input type="date" value={reportsTo} onChange={e => setReportsTo(e.target.value)} className="bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-white" />
              </div>
              <button type="button" onClick={loadErpReports} className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-black uppercase">
                Buscar reportes
              </button>
            </div>
            {erpReportsLoading ? (
              <div className="py-10 flex justify-center"><div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-500 border-t-transparent" /></div>
            ) : erpReports.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-6 text-center">Sin reportes en el rango (o todavía no buscaste).</p>
            ) : (
              <div className="overflow-x-auto rounded-2xl border border-white/5">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="bg-white/5 text-slate-400 font-black uppercase">
                      <th className="p-2">Fecha</th>
                      <th className="p-2">Hora</th>
                      <th className="p-2 text-right"># Fac</th>
                      <th className="p-2">Fec Fac 1</th>
                      <th className="p-2">Fec Fac 2</th>
                      <th className="p-2">IP Ext</th>
                      <th className="p-2">IP+MAC</th>
                      <th className="p-2 text-right">Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {erpReports.map((r: any) => (
                      <tr key={r.KeyID} className={`border-t border-white/5 ${selectedReportId === r.KeyID ? 'bg-indigo-500/10' : 'hover:bg-white/[0.03]'}`}>
                        <td className="p-2 font-mono">{r.r_date || '—'}</td>
                        <td className="p-2 font-mono">{r.r_hour || '—'}</td>
                        <td className="p-2 text-right font-mono">{r.r_regfac ?? '—'}</td>
                        <td className="p-2 font-mono">{r.r_FeFacI || '—'}</td>
                        <td className="p-2 font-mono">{r.r_FeFacF || '—'}</td>
                        <td className="p-2 font-mono text-[10px]">{r.r_ipexterna || '—'}</td>
                        <td className="p-2 font-mono text-[10px] max-w-[160px] truncate" title={r.r_NetMac}>{r.r_NetMac || '—'}</td>
                        <td className="p-2 text-right whitespace-nowrap">
                          <button type="button" onClick={() => loadReportNodes(r.KeyID)} className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-300 text-[9px] font-black uppercase mr-1">Nodos</button>
                          <button type="button" onClick={() => loadReportSystem(r.KeyID)} className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-emerald-300 text-[9px] font-black uppercase">System</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {reportDetailTab === 'nodes' && reportNodes && (
              <div className="space-y-2 border-t border-white/5 pt-3">
                <h4 className="text-xs font-black text-white uppercase">
                  Nodos · Total {reportNodes.total} · &lt;60 días {reportNodes.recent_60} · &gt;60 días {reportNodes.stale_60}
                </h4>
                <div className="max-h-56 overflow-y-auto rounded-xl border border-white/5 divide-y divide-white/5">
                  {(reportNodes.nodes || []).map((n: any) => (
                    <div key={n.KeyID} className={`p-2 text-[10px] ${n.stale ? 'text-rose-400' : 'text-slate-300'}`}>
                      <div className="font-bold text-white">{n.n_id || '—'} <span className="text-slate-500 font-normal">· {n.n_user || '—'}</span></div>
                      <div className="font-mono truncate text-slate-500">{n.n_path}</div>
                      <div className="mt-0.5">Act {n.n_active || '—'} · Acc {n.n_acces || '—'} · {n.n_netmac || ''}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {reportDetailTab === 'system' && (
              <div className="space-y-2 border-t border-white/5 pt-3">
                <h4 className="text-xs font-black text-white uppercase">System / Empresa</h4>
                {reportSystem.length === 0 ? (
                  <p className="text-xs text-slate-500 italic">Sin registros system.</p>
                ) : reportSystem.map((s: any) => (
                  <div key={s.KeyID} className="p-3 rounded-xl bg-white/5 text-[11px] grid grid-cols-2 gap-2">
                    <div><span className="text-slate-500">Nombre</span><div className="font-bold text-white">{s.s_name || '—'}</div></div>
                    <div><span className="text-slate-500">Empresa</span><div className="font-bold text-white">{s.s_empre || '—'}</div></div>
                    <div className="col-span-2"><span className="text-slate-500">Razón</span><div className="font-bold text-white">{s.s_raso || '—'}</div></div>
                    <div><span className="text-slate-500">CUIT</span><div className="font-mono">{s.s_cuit || '—'}</div></div>
                    <div><span className="text-slate-500">CliGes</span><div className="font-mono">{s.s_cliges || '—'}</div></div>
                    <div><span className="text-slate-500">Localidad</span><div>{s.s_loc || '—'}</div></div>
                    <div><span className="text-slate-500">Tel</span><div>{s.s_tel || '—'}</div></div>
                    <div className="col-span-2"><span className="text-slate-500">Mail</span><div>{s.s_mail || '—'}</div></div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {showLicenseModal && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl px-6 pt-6 pb-5 max-w-[360px] w-full space-y-5 shadow-2xl animate-in zoom-in-95">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-black text-white flex items-center gap-2">
                <Sparkles className="text-brand-500" /> Generar Licencia
              </h3>
              <button onClick={() => setShowLicenseModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>
            
            <div className="space-y-4 pt-2">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2.5">Cliente Asociado</label>
                <ClientSearchSelect
                  clients={clients}
                  valueId={licClientId}
                  onChange={(id) => setLicClientId(id)}
                  placeholder="Buscar cliente por código o nombre..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Límite de PCs</label>
                  <input 
                    type="number" 
                    min={1}
                    max={1000}
                    className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold" 
                    value={licMaxDevices}
                    onChange={(e) => setLicMaxDevices(parseInt(e.target.value) || 5)}
                    placeholder="Ej. 40"
                  />
                </div>
                
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Duración (Días)</label>
                  <input 
                    type="number" 
                    min={1}
                    max={36500}
                    className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-sm" 
                    value={licDurationDays}
                    onChange={(e) => setLicDurationDays(parseInt(e.target.value) || 365)}
                    placeholder="Ej. 365"
                  />
                </div>
              </div>

              <div className="pt-4">
                <button 
                  onClick={() => {
                    if (!licClientId) {
                      alert("Por favor seleccione un cliente.");
                      return;
                    }
                    generateLicense(parseInt(licClientId), licMaxDevices, licDurationDays);
                  }} 
                  className="w-full bg-brand-500 hover:bg-brand-600 active:scale-[0.98] text-white font-black py-4 rounded-2xl shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Crear Llave de Activación
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {deviceNotesModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl px-6 pt-6 pb-5 max-w-[420px] w-full space-y-5 shadow-2xl animate-in zoom-in-95">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-black text-white flex items-center gap-2">
                <FileText className="text-purple-500 animate-pulse" /> Notas de {deviceNotesModal.name}
              </h3>
              <button onClick={() => setDeviceNotesModal(null)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4 pt-2">
              <p className="text-xs text-slate-400">
                Guarda recordatorios, claves de Windows, usuarios de red o cualquier anotación importante sobre esta terminal.
              </p>

              <div>
                <textarea
                  rows={10}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-2xl px-4 py-3.5 leading-5 text-white outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all text-sm font-mono"
                  value={deviceNotesModal.notes}
                  onChange={(e) => setDeviceNotesModal({ ...deviceNotesModal, notes: e.target.value })}
                  placeholder="Escribe aquí las claves de Windows, usuarios de red o notas..."
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setDeviceNotesModal(null)}
                  className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-2xl transition-all"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleSaveDeviceNotes}
                  className="flex-1 bg-purple-600 hover:bg-purple-700 text-white font-extrabold py-3 rounded-2xl shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Guardar Notas
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {assignModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-indigo-500/30 rounded-3xl px-6 pt-6 pb-5 max-w-[360px] w-full space-y-5 shadow-2xl animate-in zoom-in-95">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-black text-white flex items-center gap-2">
                <Sparkles className="text-indigo-500 animate-pulse" /> Activar Terminal
              </h3>
              <button onClick={() => setAssignModal(null)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4 pt-2">
              <p className="text-xs text-slate-400">
                Selecciona la empresa o cliente al que deseas asignar la PC <strong className="text-white">{assignModal.device_name}</strong>. El agente Centinela recibirá la licencia asignada automáticamente.
              </p>

              {/* Información de ERP ApolloGesCom detectado */}
              <div className="bg-slate-800/50 border border-white/5 rounded-2xl p-4 space-y-3">
                <span className="text-[10px] font-black text-indigo-400 block tracking-widest uppercase">Detección de Sistema Apollo</span>
                {assignModal.apollo_serials && assignModal.apollo_serials.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-[11px] text-slate-300">
                      Se detectó el ERP instalado en la terminal con los siguientes números de serie:
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {assignModal.apollo_serials.map((s: string, idx: number) => (
                        <span key={idx} className="bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 font-mono text-[10px] px-2 py-0.5 rounded-lg">
                          🔑 {s}
                        </span>
                      ))}
                    </div>
                    
                    {assignModal.proposed_client ? (
                      <div className="bg-emerald-500/10 border border-emerald-500/25 rounded-xl p-3 mt-3 space-y-2">
                        <p className="text-[11px] text-emerald-400 font-bold flex items-center gap-1">
                          ✨ Cliente Propuesto Detectado
                        </p>
                        <p className="text-[10px] text-slate-300 leading-relaxed">
                          El prefijo coincide con el cliente <strong>{assignModal.proposed_client.razon_social}</strong> ({assignModal.proposed_client.codigo}).
                        </p>
                        <button
                          type="button"
                          onClick={() => {
                            setAssignClientId(String(assignModal.proposed_client.id));
                          }}
                          className="w-full bg-emerald-600/95 hover:bg-emerald-500 text-white font-extrabold text-[10px] py-2 rounded-xl transition-all shadow-md shadow-emerald-600/10 active:scale-[0.98]"
                        >
                          Asociar Automáticamente
                        </button>
                      </div>
                    ) : (
                      <p className="text-[10px] text-amber-400 italic mt-1 bg-amber-500/5 border border-amber-500/10 p-2 rounded-lg">
                        ⚠️ Ningún cliente registrado coincide con los primeros 4 dígitos de estos seriales.
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-400 italic bg-slate-950/20 p-2 rounded-lg border border-white/5">
                    ❌ No se encontró el ERP ApolloGesCom instalado en el registro de esta PC.
                  </p>
                )}
              </div>

              <div className="relative">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2 font-mono">Empresa / Cliente</label>
                <ClientSearchSelect
                  clients={clients}
                  valueId={assignClientId}
                  onChange={(id) => setAssignClientId(id)}
                  placeholder="Escribí código o nombre para filtrar..."
                />
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => setAssignModal(null)}
                  className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-2xl transition-all"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleAssignLicense}
                  disabled={!assignClientId}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-extrabold py-3 rounded-2xl shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Activar y Vincular
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showProfileModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl px-6 pt-6 pb-5 max-w-[360px] w-full space-y-5 shadow-2xl animate-in zoom-in-95">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-black text-white flex items-center gap-2">
                <Camera className="text-brand-500 animate-pulse" /> Mi Perfil de Agente
              </h3>
              <button onClick={() => setShowProfileModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveProfile} className="space-y-4 pt-2">
              {/* Imagen de Perfil y Preview */}
              <div className="flex flex-col items-center gap-3">
                {profileForm.profile_picture ? (
                  <img src={profileForm.profile_picture} alt="Preview" className="w-24 h-24 rounded-full border-4 border-brand-500/50 object-cover shadow-lg" />
                ) : (
                  <div className="w-24 h-24 rounded-full bg-gradient-to-br from-brand-400 to-orange-500 flex items-center justify-center text-white font-bold text-3xl shadow-lg border-4 border-brand-500/30">
                    {(profileForm.full_name || profileForm.nombre || 'AG').substring(0, 2).toUpperCase()}
                  </div>
                )}
                
                <label className="cursor-pointer bg-brand-500/10 hover:bg-brand-500/20 text-brand-500 text-xs font-bold px-4 py-2 rounded-xl border border-brand-500/20 transition-all flex items-center gap-1.5 shadow-sm">
                  <Camera size={14} />
                  Cambiar Foto de Perfil
                  <input type="file" accept="image/*" onChange={(e) => handleProfilePicChange(e, false)} className="hidden" />
                </label>
              </div>

              {/* Nombre de Usuario */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Usuario (Login)</label>
                <input
                  type="text" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  value={profileForm.nombre}
                  onChange={(e) => setProfileForm({ ...profileForm, nombre: e.target.value })}
                />
              </div>

              {/* Nombre Completo */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nombre Completo (Mostrar)</label>
                <input
                  type="text" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  value={profileForm.full_name}
                  onChange={(e) => setProfileForm({ ...profileForm, full_name: e.target.value })}
                />
              </div>

              {/* Celular */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Celular de Contacto</label>
                <input
                  type="text"
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder="Ej. +543446123456"
                  value={profileForm.celular}
                  onChange={(e) => setProfileForm({ ...profileForm, celular: e.target.value })}
                />
              </div>

              {/* Nueva Contraseña (Opcional) */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nueva Contraseña (Dejar vacío para mantener)</label>
                <input
                  type="password"
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder="Escribe para cambiar..."
                  value={profileForm.password}
                  onChange={(e) => setProfileForm({ ...profileForm, password: e.target.value })}
                />
              </div>

              {/* Botones de Acción */}
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowProfileModal(false)}
                  className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-2xl transition-all"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 bg-brand-500 hover:bg-brand-600 text-white font-extrabold py-3 rounded-2xl shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Guardar Perfil
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showUserAbmModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl px-6 pt-6 pb-5 max-w-[360px] w-full space-y-5 shadow-2xl animate-in zoom-in-95 max-h-[90vh] overflow-y-auto scrollbar-thin">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-black text-white flex items-center gap-2">
                <Shield className="text-brand-500 animate-pulse" /> {selectedUserForEdit ? 'Editar Miembro del Plantel' : 'Registrar Nuevo Personal'}
              </h3>
              <button onClick={() => setShowUserAbmModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveUserAbm} className="space-y-4 pt-2">
              {/* Imagen de Perfil y Preview */}
              <div className="flex flex-col items-center gap-3">
                {userAbmForm.profile_picture ? (
                  <img src={userAbmForm.profile_picture} alt="Preview" className="w-24 h-24 rounded-full border-4 border-brand-500/50 object-cover shadow-lg" />
                ) : (
                  <div className="w-24 h-24 rounded-full bg-gradient-to-br from-brand-400 to-orange-500 flex items-center justify-center text-white font-bold text-3xl shadow-lg border-4 border-brand-500/30">
                    {(userAbmForm.full_name || userAbmForm.nombre || 'AG').substring(0, 2).toUpperCase()}
                  </div>
                )}
                
                <label className="cursor-pointer bg-brand-500/10 hover:bg-brand-500/20 text-brand-500 text-xs font-bold px-4 py-2 rounded-xl border border-brand-500/20 transition-all flex items-center gap-1.5 shadow-sm">
                  <Camera size={14} />
                  Subir Foto de Perfil
                  <input type="file" accept="image/*" onChange={(e) => handleProfilePicChange(e, true)} className="hidden" />
                </label>
              </div>

              {/* Nombre de Usuario */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Usuario (Login)</label>
                <input
                  type="text" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  value={userAbmForm.nombre}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, nombre: e.target.value })}
                />
              </div>

              {/* Email */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Email Oficial</label>
                <input
                  type="email" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder="ejemplo@masteris.com"
                  value={userAbmForm.email}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, email: e.target.value })}
                />
              </div>

              {/* Nombre Completo */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nombre Completo</label>
                <input
                  type="text" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  value={userAbmForm.full_name}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, full_name: e.target.value })}
                />
              </div>

              {/* Contraseña */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">
                  Contraseña {selectedUserForEdit ? '(Dejar vacío para mantener)' : '(Requerido)'}
                </label>
                <input
                  type="password"
                  required={!selectedUserForEdit}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder={selectedUserForEdit ? "Sin cambios..." : "Contraseña inicial (ej: user1234)"}
                  value={userAbmForm.password}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, password: e.target.value })}
                />
              </div>

              {/* Rol */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Rol del Sistema</label>
                <select
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold"
                  value={userAbmForm.rol}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, rol: e.target.value })}
                >
                  <option value="soporte">Soporte Técnico (Operador)</option>
                  <option value="desarrollo">Desarrollador</option>
                  <option value="admin">Administrador del Sistema</option>
                  <option value="reseller">Reseller (Revendedor)</option>
                </select>
              </div>

              {/* Reseller (solo si el rol es reseller) */}
              {userAbmForm.rol === 'reseller' && (
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Empresa Reseller</label>
                  <select
                    className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold"
                    value={userAbmForm.reseller_id || ''}
                    onChange={(e) => setUserAbmForm({ ...userAbmForm, reseller_id: e.target.value ? Number(e.target.value) : null })}
                  >
                    <option value="">— Sin asignar —</option>
                    {resellers.filter((r: any) => r.activo !== false).map((r: any) => (
                      <option key={r.id} value={r.id}>{r.nombre}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Actividades (puede tener más de una) */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Actividades</label>
                <p className="text-[10px] text-slate-500 mb-2">Puede estar en más de una: Atención y Desarrollo, o Desarrollo y Finanzas.</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {ACTIVIDADES.map((act) => {
                    const checked = userAbmForm.actividades.includes(act.key);
                    return (
                      <label
                        key={act.key}
                        className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl border cursor-pointer transition-all ${
                          checked
                            ? 'border-brand-500/50 bg-brand-500/10 text-white'
                            : 'border-white/10 bg-slate-800/60 text-slate-300 hover:border-white/20'
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="w-4 h-4 rounded text-brand-500 focus:ring-brand-500 bg-slate-800 border-white/10"
                          checked={checked}
                          onChange={() => {
                            const next = checked
                              ? userAbmForm.actividades.filter((item) => item !== act.key)
                              : [...userAbmForm.actividades, act.key];
                            setUserAbmForm({ ...userAbmForm, actividades: next, departamento: next.join(' / ') });
                          }}
                        />
                        <span className="text-xs font-bold">{act.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Celular */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Celular de Contacto</label>
                <input
                  type="text"
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder="Ej. +543446123456"
                  value={userAbmForm.celular}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, celular: e.target.value })}
                />
              </div>

              {/* Estado Activo */}
              <div className="flex items-center gap-3 py-2">
                <input
                  type="checkbox"
                  id="user_abm_activo"
                  className="w-4 h-4 rounded text-brand-500 focus:ring-brand-500 bg-slate-800 border-white/10"
                  checked={userAbmForm.activo}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, activo: e.target.checked })}
                />
                <label htmlFor="user_abm_activo" className="text-xs font-bold text-slate-300 uppercase tracking-wider cursor-pointer">
                  Usuario Activo (Permitir Ingreso)
                </label>
              </div>

              {/* Botones de Acción */}
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowUserAbmModal(false)}
                  className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-2xl transition-all"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 bg-brand-500 hover:bg-brand-600 text-white font-extrabold py-3 rounded-2xl shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Guardar Usuario
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showResellerModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl px-6 pt-6 pb-5 max-w-[400px] w-full space-y-5 shadow-2xl animate-in zoom-in-95 max-h-[90vh] overflow-y-auto scrollbar-thin">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-black text-white flex items-center gap-2">
                <CreditCard className="text-brand-500" /> {selectedResellerForEdit ? 'Editar Reseller' : 'Nuevo Reseller'}
              </h3>
              <button onClick={() => setShowResellerModal(false)} className="text-slate-400 hover:text-white"><X size={20} /></button>
            </div>
            <form onSubmit={async (e) => {
              e.preventDefault();
              if (!resellerForm.nombre) { alert('El nombre es obligatorio.'); return; }
              try {
                if (selectedResellerForEdit) {
                  await updateReseller(selectedResellerForEdit.id, resellerForm);
                  setShowNotification(`Reseller ${resellerForm.nombre} actualizado.`);
                } else {
                  await createReseller(resellerForm);
                  setShowNotification(`Reseller ${resellerForm.nombre} creado.`);
                }
                setShowResellerModal(false);
                loadData();
                setTimeout(() => setShowNotification(null), 3000);
              } catch (err: any) {
                alert(err.message || 'Error al guardar');
              }
            }} className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nombre / Razón Social *</label>
                <input required className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 text-sm font-bold" value={resellerForm.nombre} onChange={(e) => setResellerForm({ ...resellerForm, nombre: e.target.value })} />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Persona de Contacto</label>
                <input className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 text-sm font-bold" value={resellerForm.contacto} onChange={(e) => setResellerForm({ ...resellerForm, contacto: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Email</label>
                  <input type="email" className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 text-sm font-bold" value={resellerForm.email} onChange={(e) => setResellerForm({ ...resellerForm, email: e.target.value })} />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Teléfono</label>
                  <input className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 text-sm font-bold" value={resellerForm.telefono} onChange={(e) => setResellerForm({ ...resellerForm, telefono: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Comisión (%)</label>
                <input type="number" step="0.1" min="0" max="100" className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 text-sm font-bold" value={resellerForm.comision_pct} onChange={(e) => setResellerForm({ ...resellerForm, comision_pct: parseFloat(e.target.value) || 0 })} />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Notas Internas</label>
                <textarea rows={2} className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 text-sm font-bold resize-none" value={resellerForm.notas} onChange={(e) => setResellerForm({ ...resellerForm, notas: e.target.value })} />
              </div>
              <div className="flex items-center gap-3 py-2">
                <input type="checkbox" id="reseller_activo" className="w-4 h-4 rounded text-brand-500 bg-slate-800 border-white/10" checked={resellerForm.activo} onChange={(e) => setResellerForm({ ...resellerForm, activo: e.target.checked })} />
                <label htmlFor="reseller_activo" className="text-xs font-bold text-slate-300 uppercase tracking-wider cursor-pointer">Reseller Activo</label>
              </div>
              <div className="flex gap-3 pt-4">
                <button type="button" onClick={() => setShowResellerModal(false)} className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-2xl transition-all">Cancelar</button>
                <button type="submit" className="flex-1 bg-brand-500 hover:bg-brand-600 text-white font-extrabold py-3 rounded-2xl shadow-lg shadow-brand-500/20 transition-all text-sm uppercase tracking-wider">Guardar</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Lic Facturadas (LisArtC) */}
      {licFactModal.isOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200">
          <div className={`relative w-full max-w-3xl rounded-3xl p-6 sm:p-8 flex flex-col max-h-[90vh] shadow-2xl border animate-in zoom-in-95 duration-200 ${darkMode ? 'glass-dark border-white/10 text-white' : 'bg-white border-slate-200 text-slate-800'}`}>
            <div className="flex justify-between items-start gap-4 border-b pb-4 dark:border-white/10">
              <div>
                <span className="text-[10px] uppercase font-black tracking-widest text-teal-400 bg-teal-500/10 px-2.5 py-1 rounded-full">
                  LisArtC · ERP
                </span>
                <h3 className="text-xl sm:text-2xl font-black mt-2 leading-none">
                  Lic Facturadas: <span className="text-teal-400">{licFactModal.client?.razon_social}</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1 font-medium">
                  CCLIFAC: <strong className="font-mono text-slate-300">{licFactModal.client?.cclifac}</strong>
                </p>
              </div>
              <button
                onClick={() => setLicFactModal(prev => ({ ...prev, isOpen: false }))}
                className="hover:bg-red-500/10 hover:text-red-500 p-2 rounded-xl transition-all"
              >
                <X size={20} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto mt-4">
              {licFactModal.loading ? (
                <div className="py-16 text-center text-slate-400 text-sm">Consultando LisArtC…</div>
              ) : licFactModal.items.length === 0 ? (
                <div className="py-16 text-center text-slate-500 text-sm">Sin artículos facturados (códigos de 7 dígitos) para este cliente.</div>
              ) : (
                <table className="w-full text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-white/10">
                    <tr>
                      <th className="py-2 pr-2">Cód.</th>
                      <th className="py-2 pr-2">Descripción</th>
                      <th className="py-2 pr-2 text-right">Neto</th>
                      <th className="py-2 pr-2 text-right">Final</th>
                      <th className="py-2 pr-2 text-right">Cant.</th>
                      <th className="py-2 text-right">Parte</th>
                    </tr>
                  </thead>
                  <tbody>
                    {licFactModal.items.map((row, idx) => (
                      <tr key={`${row.l_art}-${idx}`} className="border-b border-white/5">
                        <td className="py-2.5 pr-2 font-mono text-teal-300">{row.l_art}</td>
                        <td className="py-2.5 pr-2 text-slate-200">{row.a_des || '—'}</td>
                        <td className="py-2.5 pr-2 text-right font-mono">{Number(row.precio_neto || 0).toLocaleString('es-AR', { minimumFractionDigits: 2 })}</td>
                        <td className="py-2.5 pr-2 text-right font-mono font-bold">{Number(row.precio_final || 0).toLocaleString('es-AR', { minimumFractionDigits: 2 })}</td>
                        <td className="py-2.5 pr-2 text-right font-mono">{row.l_can}</td>
                        <td className="py-2.5 text-right font-mono text-slate-500">{row.l_parte || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="mt-4 pt-4 border-t dark:border-white/10 flex justify-between items-center">
              <span className="text-xs text-slate-400">{licFactModal.items.length} ítem(s)</span>
              <button
                type="button"
                onClick={() => setLicFactModal(prev => ({ ...prev, isOpen: false }))}
                className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 rounded-xl text-xs font-bold text-white border border-white/5"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {cbuModal.isOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200">
          <div className={`relative w-full max-w-4xl rounded-3xl p-6 sm:p-8 flex flex-col max-h-[90vh] shadow-2xl border animate-in zoom-in-95 duration-200 ${darkMode ? 'glass-dark border-white/10 text-white' : 'bg-white border-slate-200 text-slate-800'}`}>
            <div className="flex justify-between items-start gap-4 border-b pb-4 dark:border-white/10">
              <div>
                <span className="text-[10px] uppercase font-black tracking-widest text-sky-400 bg-sky-500/10 px-2.5 py-1 rounded-full">
                  ventas_ClienDA · SQL
                </span>
                <h3 className="text-xl sm:text-2xl font-black mt-2 leading-none">
                  CBU: <span className="text-sky-400">{cbuModal.client?.razon_social}</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1 font-medium">
                  CCLIFAC: <strong className="font-mono text-slate-300">{cbuModal.client?.cclifac || cbuModal.client?.codigo}</strong>
                </p>
              </div>
              <button
                onClick={() => setCbuModal(prev => ({ ...prev, isOpen: false }))}
                className="hover:bg-red-500/10 hover:text-red-500 p-2 rounded-xl transition-all"
              >
                <X size={20} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto mt-4">
              {cbuModal.loading ? (
                <div className="py-16 text-center text-slate-400 text-sm">Consultando ventas_ClienDA…</div>
              ) : cbuModal.items.length === 0 ? (
                <div className="py-16 text-center text-slate-500 text-sm">Este cliente no tiene CBU cargados.</div>
              ) : (
                <table className="w-full text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-white/10">
                    <tr>
                      <th className="py-2 pr-2">Estado</th>
                      <th className="py-2 pr-2">CBU</th>
                      <th className="py-2 pr-2">Banco del CBU</th>
                      <th className="py-2 pr-2">Cuenta débito</th>
                      <th className="py-2">Nro. cuenta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cbuModal.items.map((row: any) => {
                      const cbu = String(row.cbu || '');
                      const cbuFmt = cbu.length === 22 ? `${cbu.slice(0, 8)} ${cbu.slice(8)}` : cbu;
                      const cuenta = [row.cban, row.cuenta_nombre, row.cuenta_servicio].filter(Boolean).join(' · ');
                      return (
                        <tr key={row.id} className="border-b border-white/5">
                          <td className="py-2.5 pr-2">
                            <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded ${row.activo ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-500/20 text-slate-400 border border-slate-500/30'}`}>
                              {row.activo ? 'Activo' : 'Inactivo'}
                            </span>
                          </td>
                          <td className="py-2.5 pr-2 font-mono text-sky-300 select-all">{cbuFmt || '—'}</td>
                          <td className="py-2.5 pr-2 text-slate-200">{row.banco_cbu || '—'}</td>
                          <td className="py-2.5 pr-2 text-slate-300">{cuenta || '—'}</td>
                          <td className="py-2.5 font-mono text-slate-400">{row.cuenta_numero || '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            <div className="mt-4 pt-4 border-t dark:border-white/10 flex justify-between items-center">
              <span className="text-xs text-slate-400">{cbuModal.items.length} CBU</span>
              <button
                type="button"
                onClick={() => setCbuModal(prev => ({ ...prev, isOpen: false }))}
                className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 rounded-xl text-xs font-bold text-white border border-white/5"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Extracto General (ERP) con Diseño Ultra-Premium Glass */}
      {showExtractoModal.isOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200">
          <div className={`relative w-full max-w-4xl rounded-3xl p-6 sm:p-8 flex flex-col max-h-[90vh] shadow-2xl border animate-in zoom-in-95 duration-200 ${darkMode ? 'glass-dark border-white/10 text-white' : 'bg-white border-slate-200 text-slate-800'}`}>
            
            {/* Cabecera */}
            <div className="flex justify-between items-start gap-4 border-b pb-4 dark:border-white/10">
              <div>
                <span className="text-[10px] uppercase font-black tracking-widest text-brand-500 bg-brand-500/10 px-2.5 py-1 rounded-full">
                  Conexión ERP Activa
                </span>
                <h3 className="text-xl sm:text-2xl font-black mt-2 leading-none">
                  Extracto de Cuenta: <span className="text-brand-500">{showExtractoModal.client?.razon_social}</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1 font-medium">
                  Código ERP: <strong className="font-mono text-slate-300">{showExtractoModal.client?.codigo}</strong> | CUIT: <strong className="font-mono text-slate-300">{showExtractoModal.client?.identificador_fiscal || "Sin CUIT"}</strong>
                </p>
              </div>
              <button
                onClick={() => setShowExtractoModal(prev => ({ ...prev, isOpen: false }))}
                className="hover:bg-red-500/10 hover:text-red-500 p-2 rounded-xl transition-all"
              >
                <X size={20} />
              </button>
            </div>

            {/* Filtros de Fecha */}
            <div className="flex flex-col sm:flex-row gap-3 items-end justify-between bg-slate-500/5 border dark:border-white/5 p-4 rounded-2xl mt-4">
              <div className="grid grid-cols-2 gap-3 w-full sm:w-auto">
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Fecha Desde</label>
                  <input
                    type="date"
                    value={showExtractoModal.desde}
                    onChange={(e) => setShowExtractoModal({ ...showExtractoModal, desde: e.target.value })}
                    className={`w-full rounded-xl px-3 py-2 text-xs border outline-none focus:ring-2 focus:ring-brand-500 ${darkMode ? 'bg-slate-900 border-white/10 text-white' : 'bg-white border-slate-200'}`}
                  />
                </div>
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Fecha Hasta</label>
                  <input
                    type="date"
                    value={showExtractoModal.hasta}
                    onChange={(e) => setShowExtractoModal({ ...showExtractoModal, hasta: e.target.value })}
                    className={`w-full rounded-xl px-3 py-2 text-xs border outline-none focus:ring-2 focus:ring-brand-500 ${darkMode ? 'bg-slate-900 border-white/10 text-white' : 'bg-white border-slate-200'}`}
                  />
                </div>
              </div>
              <button
                onClick={() => handleOpenExtracto(showExtractoModal.client, showExtractoModal.desde, showExtractoModal.hasta)}
                disabled={showExtractoModal.loading}
                className="w-full sm:w-auto bg-brand-500 hover:bg-brand-600 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition-all shadow-md"
              >
                {showExtractoModal.loading ? "Consultando..." : "Filtrar Extracto"}
              </button>
            </div>

            {/* Grilla de Resultados */}
            <div className="flex-1 overflow-y-auto mt-4 min-h-[250px] pr-1">
              {showExtractoModal.loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                  <Sparkles className="w-8 h-8 text-indigo-400 animate-spin" />
                  <p className="text-sm text-slate-400 font-bold animate-pulse">Sincronizando con el motor de gestión Harbour...</p>
                </div>
              ) : showExtractoModal.data.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-400 text-sm font-semibold">
                  <FileText size={32} className="text-slate-500 mb-2" />
                  No se registran comprobantes en el rango de fechas seleccionado.
                </div>
              ) : (
                <div className="border border-white/5 dark:border-white/5 rounded-2xl overflow-hidden">
                  <div className="hidden sm:grid grid-cols-12 gap-3 p-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider bg-slate-500/10 border-b dark:border-white/5">
                    <div className="col-span-2">Fecha</div>
                    <div className="col-span-4">Comprobante / Detalle</div>
                    <div className="col-span-2 text-right">Importe</div>
                    <div className="col-span-2 text-right">Saldo</div>
                    <div className="col-span-2 text-center">Acciones</div>
                  </div>
                  <div className="divide-y divide-slate-100 dark:divide-white/5 max-h-[40vh] overflow-y-auto">
                    {showExtractoModal.data.map((row, idx) => {
                      const importe = parseFloat(row.Importe || 0);
                      const saldo = parseFloat(row.Saldo || 0);
                      
                      const fmtImporte = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(importe);
                      const fmtSaldo = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(saldo);
                      
                      // Formatear fecha
                      let cleanDate = row.Fecha;
                      if (cleanDate && cleanDate.includes('-')) {
                        const parts = cleanDate.split('T')[0].split('-');
                        if (parts.length === 3) {
                          cleanDate = `${parts[2]}/${parts[1]}/${parts[0]}`;
                        }
                      }
                      
                      return (
                        <div key={idx} className={`flex flex-col sm:grid sm:grid-cols-12 gap-2 sm:gap-3 p-3 items-start sm:items-center text-xs font-semibold ${darkMode ? 'hover:bg-white/5' : 'hover:bg-slate-50'} border-b border-slate-100 dark:border-white/5`}>
                          <div className="sm:col-span-2 font-mono text-slate-400 text-[10px] sm:text-xs">{cleanDate}</div>
                          <div className="sm:col-span-4 truncate font-bold leading-tight w-full text-left" title={row.Documento}>
                            {row.Documento}
                          </div>
                          <div className="flex sm:contents justify-between w-full mt-1 sm:mt-0">
                            <span className="sm:hidden text-[10px] text-slate-500 uppercase font-bold">Importe</span>
                            <div className={`sm:col-span-2 text-right font-black font-mono ${importe < 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                              {fmtImporte}
                            </div>
                          </div>
                          <div className="flex sm:contents justify-between w-full mt-1 sm:mt-0">
                            <span className="sm:hidden text-[10px] text-slate-500 uppercase font-bold">Saldo</span>
                            <div className="sm:col-span-2 text-right font-extrabold font-mono text-slate-300">
                              {fmtSaldo}
                            </div>
                          </div>
                          <div className="flex sm:contents justify-between w-full mt-2 sm:mt-0 items-center border-t border-dashed border-white/5 pt-2 sm:pt-0 sm:border-0">
                            <span className="sm:hidden text-[10px] text-slate-500 uppercase font-bold">Acción</span>
                            <div className="sm:col-span-2 flex justify-center w-auto">
                              {row.CodFac ? (
                                <button
                                  onClick={() => viewVoucherPdf(row.CodFac)}
                                  className="flex items-center gap-1.5 px-3 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/10 hover:border-rose-500/30 rounded-lg text-[10px] font-black uppercase transition-all shadow-sm"
                                  title="Visualizar Comprobante original del ERP en formato PDF"
                                >
                                  <FileText size={11} />
                                  PDF
                                </button>
                              ) : (
                                <span className="text-[10px] text-slate-500 font-bold font-mono">-</span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Totalizadores en el Pie */}
            <div className="flex flex-col sm:flex-row justify-between items-center border-t pt-4 mt-6 dark:border-white/10 gap-3">
              <div className="flex gap-4">
                <div className="text-xs">
                  <span className="text-slate-400">Total Comprobantes:</span> <strong className="text-white">{showExtractoModal.data.length}</strong>
                </div>
                <div className="text-xs">
                  <span className="text-slate-400">Saldo Actual en ERP:</span> <strong className="text-emerald-400 font-mono font-black">{new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(showExtractoModal.client?.saldo || 0)}</strong>
                </div>
              </div>
              <button
                onClick={() => setShowExtractoModal(prev => ({ ...prev, isOpen: false }))}
                className="w-full sm:w-auto bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold px-6 py-2.5 rounded-xl transition-all border border-white/10"
              >
                Cerrar Ventana
              </button>
            </div>
            
          </div>
        </div>
      )}
    </div>
  );
}

const NavItem = ({ icon, text, active, badge, onClick }: any) => (
  <button onClick={onClick} className={`w-full flex items-center justify-between px-4 py-3.5 rounded-xl transition-all group ${active ? 'bg-gradient-to-r from-brand-500/20 to-transparent text-brand-500 font-extrabold' : 'text-slate-400 hover:bg-white/5'}`}>
    <div className="flex items-center gap-3 text-sm"><span>{icon}</span>{text}</div>
    {badge && <span className="text-[10px] font-extrabold px-2.5 py-1 rounded-full bg-slate-800 text-slate-400">{badge}</span>}
  </button>
);

function ticketRegisteredBy(t: any): string {
  const u = t?.creado_por;
  if (u?.full_name || u?.nombre) return String(u.full_name || u.nombre).trim();
  const first = (t?.intervenciones || []).find((inv: any) => inv?.usuario?.full_name || inv?.usuario?.nombre)?.usuario;
  if (first?.full_name || first?.nombre) return String(first.full_name || first.nombre).trim();
  return '';
}

const TicketRow = ({ id, client, subject, status, priority, origen, createdAt, assignee, registeredBy, hasAttachments, darkMode }: any) => {
  const statusColors: any = { 'nuevo': 'text-blue-500 bg-blue-500/10', 'en_curso': 'text-brand-500 bg-brand-500/10', 'resuelto': 'text-emerald-500 bg-emerald-500/10', 'entregado': 'text-sky-500 bg-sky-500/10', 'bloqueado': 'text-rose-500 bg-rose-500/10' };
  const isInternal = (origen || 'cliente') === 'interno';
  return (
    <div className={`grid grid-cols-12 gap-4 p-3.5 rounded-xl items-center cursor-pointer transition-all ${darkMode ? 'hover:bg-white/5' : 'hover:bg-slate-50'}`}>
      <div className="col-span-1 text-xs font-bold text-slate-500">{id}</div>
      <div className="col-span-1">
        <span className={`px-2 py-1 rounded-full text-[9px] font-black uppercase tracking-wider ${isInternal ? 'text-violet-400 bg-violet-500/10' : 'text-sky-400 bg-sky-500/10'}`}>
          {isInternal ? 'Interno' : 'Cliente'}
        </span>
      </div>
      <div className="col-span-2 text-sm font-extrabold text-brand-500 truncate">{client}</div>
      <div className="col-span-2 text-sm truncate flex items-center gap-1.5">
        {hasAttachments && <Paperclip size={12} className="text-brand-500 shrink-0" />}
        <span className="truncate">{subject}</span>
      </div>
      <div className="col-span-1"><span className={`px-2 py-1 rounded-full text-[9px] font-bold uppercase ${statusColors[(status || '').toLowerCase()] || 'text-slate-400 bg-slate-400/10'}`}>{status}</span></div>
      <div className="col-span-1 text-[10px] font-bold text-slate-400" title={createdAt ? new Date(createdAt).toLocaleString() : 'Sin fecha de creación'}>
        {createdAt ? new Date(createdAt).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'}
      </div>
      <div className="col-span-2 text-[10px] font-bold text-amber-200/90 truncate" title={registeredBy || 'Sin dato de quién lo cargó'}>
        {registeredBy || '—'}
      </div>
      <div className="col-span-2 text-[10px] font-bold text-slate-400 truncate" title={assignee || 'Visible para todo el sector'}>
        {assignee ? assignee : 'Todo el sector'}
        {priority ? <span className="block text-[9px] uppercase text-slate-500">{priority}</span> : null}
      </div>
    </div>
  );
};


