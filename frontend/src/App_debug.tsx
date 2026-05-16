import { useState, useEffect } from 'react';
import { Ticket, Users, Settings, Bell, Search, Moon, Sun, Monitor, MessageSquare, X, LogOut, ArrowUpRight, Sparkles, FileText, Clipboard, Plus, Folder } from 'lucide-react';
import { API_URL, getTickets, getClients, createTicket, createClient, updateClient, toggleClientStatus, getActiveCentinelas, fetchAiAnalysis, getCentinelaFrame, getCentinelaAlerts, runCentinelaCommand, getAreas } from './api';
import Login from './Login';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'));
  const [userProfile, setUserProfile] = useState<any>(null);

  const [darkMode, setDarkMode] = useState(true);
  const [activeTab, setActiveTab] = useState('tickets');
  const [licenses, setLicenses] = useState<any[]>([]);
  const [showLicenseModal, setShowLicenseModal] = useState(false);

  const [tickets, setTickets] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [centinelas, setCentinelas] = useState<any>({});
  const [loading, setLoading] = useState(true);

  // Estados Modal Crear
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newClientId, setNewClientId] = useState("");
  const [newSubject, setNewSubject] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPriority] = useState("media");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Estados Clientes
  const [isClientModalOpen, setIsClientModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<any>(null);
  const [clientSearchTerm, setClientSearchTerm] = useState("");
  const [clientForm, setClientForm] = useState({
    razon_social: '',
    identificador_fiscal: '',
    version_apollo: '',
    telefono: '',
    fecha_vencimiento: '',
    modulos: 'Base, Facturación',
    apikey_apollo: '',
    remote_password: ''
  });

  // Estados Modal Detalle + Escalamiento + IA
  const [selectedTicket, setSelectedTicket] = useState<any>(null);
  const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [newMessage, setNewMessage] = useState("");

  // Alertas Proactivas
  const [activeAlerts, setActiveAlerts] = useState<any>({});
  const [showNotification, setShowNotification] = useState<string | null>(null);

  // Estados Centinela (Live View Multi-Sesión)
  const [activeSessions, setActiveSessions] = useState<any[]>([]);
  const [sessionFrames, setSessionFrames] = useState<Record<string, string>>({});
  const [sessionCmds, setSessionCmds] = useState<Record<string, any>>({});
  const [sessionFiles, setSessionFiles] = useState<Record<string, any>>({});
  const [sessionChats, setSessionChats] = useState<Record<string, any[]>>({});
  const [chatVisibility, setChatVisibility] = useState<Record<string, boolean>>({});
  const [showPasswordModal, setShowPasswordModal] = useState<any>(null);
  const [remotePassInput, setRemotePassInput] = useState("");

  // Nuevos estados para Intervenciones
  const [interventions, setInterventions] = useState<any[]>([]);
  const [transferAreaId, setTransferAreaId] = useState<number | null>(null);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [attachmentUrl, setAttachmentUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const [areas, setAreas] = useState<any[]>([]);
  const [selectedArea, setSelectedArea] = useState<number | null>(null);

  useEffect(() => {
    if (darkMode) document.body.classList.add('dark');
    else document.body.classList.remove('dark');
  }, [darkMode]);

  useEffect(() => {
    if (isAuthenticated) {
      const stored = localStorage.getItem('user');
      if (stored) setUserProfile(JSON.parse(stored));
      loadData();
    }
  }, [isAuthenticated, selectedArea]);

  const loadData = () => {
    setLoading(true);
    Promise.all([getTickets(selectedArea || undefined), getClients(), getAreas()]).then(([tData, cData, aData]) => {
      setTickets(tData);
      setClients(cData);
      setAreas(aData);
      setLoading(false);
    }).catch(() => handleLogout());
  }

  useEffect(() => {
    let interval: any;
    if (isAuthenticated && activeTab === 'monitor') {
      const fetchTelemetry = async () => setCentinelas(await getActiveCentinelas());
      fetchTelemetry();
      interval = setInterval(fetchTelemetry, 3000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, activeTab]);

  useEffect(() => {
    let interval: any;
    if (isAuthenticated && activeSessions.length > 0) {
      const fetchFrames = async () => {
        const newFrames = { ...sessionFrames };
        let changed = false;

        await Promise.all(activeSessions.map(async (s) => {
          const frame = await getCentinelaFrame(s.id);
          if (frame && frame !== sessionFrames[s.id]) {
            newFrames[s.id] = frame;
            changed = true;
          }
        }));

        if (changed) setSessionFrames(newFrames);
      };

      fetchFrames();
      interval = setInterval(fetchFrames, 1500);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, activeSessions, sessionFrames]);

  useEffect(() => {
    let interval: any;
    if (isAuthenticated) {
      const fetchAlerts = async () => {
        const alerts = await getCentinelaAlerts();
        setActiveAlerts(alerts);

        Object.entries(alerts).forEach(([id, list]: any) => {
          if (list.length > 0 && !activeAlerts[id]) {
            setShowNotification(`¡Alerta Crítica en PC #${id}!`);
            setTimeout(() => setShowNotification(null), 5000);
          }
        });
      };
      fetchAlerts();
      interval = setInterval(fetchAlerts, 5000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, activeAlerts]);


  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setIsAuthenticated(false);
  }

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClientId || !newSubject || !newDesc) return;
    setIsSubmitting(true);
    const created = await createTicket({ client_id: parseInt(newClientId), asunto: newSubject, descripcion: newDesc, prioridad: newPriority });
    setIsSubmitting(false);
    if (created) {
      setIsModalOpen(false);
      setNewSubject(""); setNewDesc("");
      loadData();
    } else alert("Error de comunicación backend.");
  };


  const handleConsultarIA = async () => {
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

    // Recargar intervenciones frescas
    loadData(); // Refresca lista general
  }

  const closeTicketModal = () => {
    setSelectedTicket(null);
    setInterventions([]);
    setNewMessage("");
  }

  const toggleRemoteSession = async (centinela: any) => {
    const exists = activeSessions.find(s => s.id === centinela.id);
    if (exists) {
      // Notificar al servidor para liberar el dispositivo
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/centinelas/devices/${centinela.id}/end-session`, {
        method: "POST",
        headers: { 'Authorization': `Bearer ${token}` }
      });

      setActiveSessions(activeSessions.filter(s => s.id !== centinela.id));
      const newFrames = { ...sessionFrames };
      delete newFrames[centinela.id];
      setSessionFrames(newFrames);
      loadData(); // Refrescar para ver el LED verde de nuevo
    } else {
      setActiveSessions([...activeSessions, centinela]);
      if (!sessionCmds[centinela.id]) {
        setSessionCmds({ ...sessionCmds, [centinela.id]: { current: "", history: [] } });
      }
    }
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

    const sent = await import('./api').then(m => m.addIntervention(selectedTicket.id, data));
    setIsSubmitting(false);

    if (sent) {
      setInterventions([...interventions, sent]);
      setNewMessage("");
      setTransferAreaId(null);
      setAttachment(null);
      setAttachmentUrl(null);
      loadData(); // Refrescar estado del ticket
    }
  }

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    const res = await import('./api').then(m => m.uploadFile(file));
    setIsUploading(false);
    if (res) {
      setAttachment(file);
      setAttachmentUrl(res.url);
    } else alert("Error al subir archivo");
  }

  const handleCreateOrUpdateClient = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    let result;
    if (editingClient) result = await updateClient(editingClient.id, clientForm);
    else result = await createClient(clientForm);
    setIsSubmitting(false);

    if (result) {
      setIsClientModalOpen(false);
      setEditingClient(null);
      setClientForm({ razon_social: "", identificador_fiscal: "", version_apollo: "", telefono: "", fecha_vencimiento: "", modulos: "Base, Facturación", apikey_apollo: "", remote_password: "" });
      loadData();
    } else alert("Error al procesar el cliente.");
  };

  const handleVerifyRemotePassword = async (deviceId: number) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/verify-password`, {
      method: "POST",
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ password: remotePassInput })
    });
    if (response.ok) {
      const telemetry = centinelas[deviceId];
      setActiveSessions(prev => [...prev, { id: deviceId, ...telemetry }]);
      setShowPasswordModal(null);
      setRemotePassInput("");
      setShowNotification("Conexión Segura Establecida.");
    } else {
      alert("PIN de acceso remoto incorrecto.");
    }
  };

  const sendRemoteChat = async (deviceId: number, message: string) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/chat`, {
      method: "POST",
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ message, sender_type: 'tech' })
    });
    if (response.ok) {
      // Recargar chat
      fetchChatHistory(deviceId);
    }
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
  };

  const fetchRemoteFiles = async (deviceId: number, path: string = "C:\\") => {
    const token = localStorage.getItem('token');
    setSessionFiles(prev => ({ ...prev, [deviceId]: { ...prev[deviceId], path, loading: true } }));
    await fetch(`${API_URL}/centinelas/devices/${deviceId}/files?path=${encodeURIComponent(path)}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
  };

  const downloadRemoteFile = async (deviceId: number, path: string) => {
    const token = localStorage.getItem('token');
    await fetch(`${API_URL}/centinelas/devices/${deviceId}/files/download?path=${encodeURIComponent(path)}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    setShowNotification("Petición de descarga enviada...");
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
    if (activeTab === 'licenses') fetchLicenses();
  }, [activeTab]);

  const handleUploadFile = async (deviceId: number, file: File) => {
    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', file);
    await fetch(`${API_URL}/centinelas/devices/${deviceId}/files/upload`, {
      method: "POST",
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    setShowNotification("Archivo enviado al Agente.");
  };


  const openClientModal = (c?: any) => {
    if (c) {
      setEditingClient(c.id);
      setClientForm({
        razon_social: c.razon_social,
        identificador_fiscal: c.identificador_fiscal || '',
        version_apollo: c.version_apollo || '',
        telefono: c.telefono || '',
        fecha_vencimiento: c.fecha_vencimiento ? c.fecha_vencimiento.split('T')[0] : '',
        modulos: c.modulos || 'Base, Facturación',
        apikey_apollo: c.apikey_apollo || '',
        remote_password: c.remote_password || ''
      });
    } else {
      setEditingClient(null);
      setClientForm({
        razon_social: '',
        identificador_fiscal: '',
        version_apollo: '',
        telefono: '',
        fecha_vencimiento: '',
        modulos: 'Base, Facturación',
        apikey_apollo: '',
        remote_password: ''
      });
    }
    setIsClientModalOpen(true);
  }

  if (!isAuthenticated) return <Login onLogin={() => setIsAuthenticated(true)} />;

  return (
    <div className="flex h-screen overflow-hidden selection:bg-brand-500/30">

      {/* SIDEBAR CORPORATIVA */}
      <aside className={`w-64 flex flex-col transition-all duration-300 border-r ${darkMode ? 'glass-dark border-dark-border' : 'glass border-slate-200'} z-20 relative`}>
        <div className="h-[72px] flex items-center px-6 border-b border-opacity-10 border-white">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-400 to-orange-600 flex items-center justify-center text-white font-bold text-xl mr-3 shadow-lg shadow-brand-500/30">A</div>
          <span className="text-xl font-extrabold tracking-tight">
            <span className="text-slate-800 dark:text-white">Apollo</span>
            <span className="text-brand-500">Support</span>
          </span>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          <div className="mb-4">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Vistas Principales</p>
            <NavItem icon={<Ticket size={20} />} text="Bandeja Unificada" badge={tickets.length > 0 ? tickets.length.toString() : ""} active={activeTab === 'tickets' && selectedArea === null} onClick={() => { setActiveTab('tickets'); setSelectedArea(null); }} />
            <NavItem icon={<Monitor size={20} />} text="Terminal Remota" badge="En Vivo" active={activeTab === 'monitor'} onClick={() => setActiveTab('monitor')} />
            <NavItem icon={<Users size={20} />} text="Base Clientes" active={activeTab === 'clients'} onClick={() => setActiveTab('clients')} />
          </div>

          <div className="mb-4">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Sectores Operativos</p>
            {areas.map(area => (
              <NavItem
                key={area.id}
                icon={<Folder size={18} className={selectedArea === area.id ? "text-brand-500" : "text-slate-400"} />}
                text={area.nombre}
                active={activeTab === 'tickets' && selectedArea === area.id}
                onClick={() => { setActiveTab('tickets'); setSelectedArea(area.id); }}
              />
            ))}
          </div>

          <div>
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Sistema</p>
            <NavItem icon={<Sparkles size={20} />} text="IA Copiloto" badge="Beta" />
            <NavItem icon={<FileText size={20} />} text="Licencias" active={activeTab === 'licenses'} onClick={() => setActiveTab('licenses')} />
            <NavItem icon={<Settings size={20} />} text="Ajustes" active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} />
          </div>
        </nav>

        <div className="p-4 border-t border-opacity-10 border-white relative group">
          <div className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors border border-transparent hover:border-white/10 shadow-sm cursor-default">
            <img src="https://i.pravatar.cc/150?img=11" alt="Avatar" className="w-10 h-10 rounded-full shadow-md border-2 border-brand-500/50" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate text-slate-800 dark:text-white">{userProfile?.nombre || 'Agente'}</p>
              <p className="text-xs text-brand-500 font-medium truncate uppercase">{userProfile?.rol || 'Soporte'}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="absolute right-6 top-[28px] p-2 rounded-full hidden group-hover:flex bg-red-500 text-white shadow-lg animate-in fade-in zoom-in transition hover:bg-red-600">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* ÁREA PRINCIPAL */}
      <main className="flex-1 flex flex-col relative z-10 w-full bg-slate-50 dark:bg-dark-bg/95 transition-colors">
        <div className="absolute top-[-15%] left-[10%] w-[50%] h-[50%] bg-brand-500/10 rounded-full blur-[140px] pointer-events-none" />

        {/* Topbar */}
        <header className={`h-[72px] flex items-center justify-between px-8 border-b transition-colors duration-300 z-10 ${darkMode ? 'bg-dark-bg/50 border-dark-border backdrop-blur-md' : 'bg-white/60 border-slate-200 backdrop-blur-md'}`}>
          <div className="flex items-center gap-4 flex-1">
            <div className={`flex items-center gap-2 px-4 py-2.5 rounded-xl w-96 transition-all ring-1 focus-within:ring-2 focus-within:ring-brand-500 ${darkMode ? 'bg-dark-card/50 ring-dark-border shadow-inner' : 'bg-white ring-slate-200 shadow-sm'}`}>
              <Search size={18} className="text-slate-400" />
              <input type="text" placeholder="Buscador global..." className="bg-transparent border-none outline-none w-full text-sm font-medium placeholder:text-slate-400" />
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

        {/* NOTIFICACIÓN FLOTANTE */}
        {showNotification && (
          <div className="fixed top-20 right-8 z-[100] animate-in slide-in-from-right-full">
            <div className="bg-red-600 text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-4 border border-red-500 ring-4 ring-red-500/10">
              <Bell className="animate-bounce" />
              <div>
                <p className="font-black text-sm uppercase tracking-tighter">Atención Inmediata</p>
                <p className="text-xs font-bold opacity-90">{showNotification}</p>
              </div>
              <button onClick={() => setShowNotification(null)} className="ml-4 hover:bg-white/20 p-1 rounded-full transition-colors"><X size={16} /></button>
            </div>
          </div>
        )}

        {/* CONTENEDOR DE TABLEROS (Multipágina falso) */}
        <div className="flex-1 overflow-auto p-8 z-10 relative">
          <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-700">

            {/* VISTA 1: TICKETS */}
            {activeTab === 'tickets' && (
              <>
                <div className="flex items-end justify-between">
                  <div><h1 className="text-4xl font-extrabold tracking-tight">Análisis Operativo</h1></div>
                  <button onClick={() => setIsModalOpen(true)} className="bg-brand-500 hover:bg-brand-600 text-white px-6 py-2.5 rounded-xl font-bold shadow-[0_0_15px_rgba(245,158,11,0.3)] transition-all hover:-translate-y-1">
                    + Cargar Derivación
                  </button>
                </div>

                <div className={`rounded-2xl border p-1 shadow-sm ${darkMode ? 'glass-dark border-dark-border' : 'bg-white border-slate-200'}`}>
                  <div className="p-5 pb-0"><h2 className="text-lg font-bold">Solicitudes Recientes</h2></div>
                  <div className="p-4 mt-2">
                    <div className="grid grid-cols-12 gap-4 pb-3 border-b border-slate-100 dark:border-dark-border/50 text-xs font-bold text-slate-400 tracking-wider uppercase">
                      <div className="col-span-1 pl-2">ID</div><div className="col-span-3">Empresa</div><div className="col-span-4">Asunto del Problema</div><div className="col-span-2">Estado</div><div className="col-span-2">Urgencia</div>
                    </div>
                    <div className="space-y-1 mt-2 min-h-[150px]">
                      {loading ? <div className="flex justify-center p-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500"></div></div> :
                        tickets.length === 0 ? <div className="text-center p-8 text-slate-400">Excelente, sin tickets pendientes en cola.</div> :
                          tickets.map((t: any) => {
                            const c = clients.find(cl => cl.id === t.client_id);
                            return (
                              <div key={t.id} onClick={() => openTicketModal({ ...t, clientName: c?.razon_social })}>
                                <TicketRow id={`#${t.id}`} client={c ? c.razon_social : "Desconocido"} subject={t.asunto} status={t.estado} priority={t.prioridad} darkMode={darkMode} />
                              </div>
                            )
                          })}
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* VISTA 2: MONITOR DE CENTINELAS (La Magia) */}
            {activeTab === 'monitor' && (
              <div className="space-y-8 animate-in slide-in-from-bottom-8">
                <div className="flex items-end justify-between">
                  <div>
                    <h1 className="text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      Flota de Terminales <span className="relative flex h-4 w-4"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500"></span></span>
                    </h1>
                    <p className="text-slate-400 mt-2">Visor maestro de las computadoras registradas por cliente.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {clients.map(client => (
                    <div key={client.id} className={`p-6 rounded-[2rem] border shadow-2xl ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'}`}>
                      <h3 className="text-xl font-black mb-4 flex items-center justify-between text-brand-500">
                        {client.razon_social}
                        <span className="text-[10px] bg-brand-500/10 px-3 py-1 rounded-full uppercase tracking-widest">{client.devices?.length || 0} PCs</span>
                      </h3>

                      <div className="space-y-2">
                        {(!client.devices || client.devices.length === 0) ? (
                          <p className="text-xs text-slate-500 italic p-4 text-center">Sin dispositivos registrados aún.</p>
                        ) : (
                          client.devices.map((dev: any) => {
                            const isOnline = centinelas[dev.id]; // Usamos dev.id como clave ahora
                            const telemetry = centinelas[dev.id];
                            const isBusy = dev.current_technician_id !== null;

                            return (
                              <div key={dev.id} className={`p-4 rounded-2xl border transition-all flex items-center justify-between group ${isOnline ? (isBusy ? 'bg-amber-500/5 border-amber-500/20' : 'bg-emerald-500/5 border-emerald-500/20') : 'bg-slate-500/5 border-slate-500/10 grayscale opacity-70'}`}>
                                <div className="flex items-center gap-3">
                                  <div className={`w-3 h-3 rounded-full ${isOnline ? (isBusy ? 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.4)]' : 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]') : 'bg-slate-400'}`} />
                                  <div>
                                    <div className="text-sm font-extrabold">{dev.device_name}</div>
                                    <div className="flex items-center gap-2 text-[9px] uppercase font-bold text-slate-500">
                                      {isOnline ? (
                                        <>CPU: {telemetry?.cpu || 0}% | RAM: {telemetry?.ram || 0}%</>
                                      ) : 'Desconectado'}
                                    </div>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2">
                                  {isBusy && (
                                    <div className="flex flex-col items-end mr-2">
                                      <span className="text-[8px] font-black text-amber-600 uppercase">Ocupado</span>
                                      <span className="text-[10px] font-bold text-slate-400">Hace {Math.floor((new Date().getTime() - new Date(dev.session_start).getTime()) / 60000)}m</span>
                                    </div>
                                  )}
                                  <button
                                    onClick={() => {
                                      if (isOnline) {
                                        const session = activeSessions.find(s => s.id === dev.id);
                                        if (session) toggleRemoteSession(session);
                                        else setShowPasswordModal({ deviceId: dev.id, name: dev.device_name });
                                      }
                                    }}
                                    disabled={!isOnline}
                                    className={`p-2.5 rounded-xl transition-all ${isOnline ? 'bg-brand-500 text-white hover:bg-brand-600 shadow-lg shadow-brand-500/20' : 'bg-slate-200 text-slate-400'}`}
                                  >
                                    <Monitor size={16} />
                                  </button>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* VISTA 3: BASE CLIENTES (Phase 4) */}
            {activeTab === 'clients' && (
              <>
                <div className="flex items-end justify-between">
                  <div>
                    <h1 className="text-4xl font-extrabold tracking-tight">Base Maestra de Clientes</h1>
                    <p className="text-slate-400 mt-2">Gestión centralizada de licencias y empresas ApolloGesCom.</p>
                  </div>
                  <button onClick={() => openClientModal()} className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-2.5 rounded-xl font-bold shadow-lg transition-all hover:-translate-y-1">
                    + Nueva Empresa
                  </button>
                </div>

                <div className={`rounded-2xl border p-1 shadow-sm mt-6 ${darkMode ? 'glass-dark border-dark-border' : 'bg-white border-slate-200'}`}>
                  <div className="p-5 flex items-center justify-between border-b dark:border-dark-border/50">
                    <h2 className="text-lg font-bold">Empresas Registradas</h2>
                    <div className="relative w-64">
                      <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        placeholder="Buscar por nombre o CUIT..."
                        value={clientSearchTerm}
                        onChange={e => setClientSearchTerm(e.target.value)}
                        className={`w-full pl-9 pr-4 py-2 rounded-xl text-sm border outline-none focus:ring-2 focus:ring-brand-500 ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50 border-slate-200'}`}
                      />
                    </div>
                  </div>
                  <div className="p-4">
                    <div className="grid grid-cols-12 gap-4 pb-3 border-b border-slate-100 dark:border-dark-border/50 text-xs font-bold text-slate-400 tracking-wider uppercase">
                      <div className="col-span-1 pl-2">ID</div>
                      <div className="col-span-3">Razón Social</div>
                      <div className="col-span-2 text-center">Vencimiento</div>
                      <div className="col-span-2">Modulos</div>
                      <div className="col-span-2 text-center">Estado</div>
                      <div className="col-span-2 text-right pr-4">Acciones</div>
                    </div>
                    <div className="space-y-1 mt-2">
                      {clients
                        .filter(c => c.razon_social.toLowerCase().includes(clientSearchTerm.toLowerCase()) || (c.identificador_fiscal && c.identificador_fiscal.includes(clientSearchTerm)))
                        .map((c: any) => {
                          const isExpired = c.fecha_vencimiento && new Date(c.fecha_vencimiento) < new Date();
                          return (
                            <div key={c.id} className={`grid grid-cols-12 gap-4 p-3.5 rounded-xl items-center ${darkMode ? 'hover:bg-slate-800/60' : 'hover:bg-slate-50'}`}>
                              <div className="col-span-1 text-xs font-bold text-slate-500">#{c.id}</div>
                              <div className="col-span-3 truncate">
                                <div className="text-sm font-bold text-slate-800 dark:text-white leading-tight">{c.razon_social}</div>
                                <div className="text-[10px] text-slate-400 font-mono tracking-tighter">{c.identificador_fiscal || 'SIN CUIT'}</div>
                              </div>
                              <div className="col-span-2 text-center">
                                <span className={`text-[11px] font-black px-2 py-1 rounded-lg ${isExpired ? 'bg-red-500/10 text-red-500 animate-pulse border border-red-500/20' : 'text-slate-500'}`}>
                                  {c.fecha_vencimiento ? new Date(c.fecha_vencimiento).toLocaleDateString() : 'PERPETUO'}
                                </span>
                              </div>
                              <div className="col-span-2">
                                <div className="flex flex-wrap gap-1">
                                  {c.modulos?.split(',').map((m: string) => (
                                    <span key={m} className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/5 text-slate-500 border dark:border-white/5 uppercase">{m.trim()}</span>
                                  ))}
                                </div>
                              </div>
                              <div className="col-span-2 text-center">
                                <button
                                  onClick={async () => { await toggleClientStatus(c.id); loadData(); }}
                                  className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase transition-colors ${c.activo ? 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]' : 'bg-red-500/10 text-red-500 hover:bg-red-500/20'}`}
                                >
                                  {c.activo ? 'Activo' : 'Supendido'}
                                </button>
                              </div>
                              <div className="col-span-2 text-right pr-2">
                                <button onClick={() => { openClientModal(c); }} className="p-2 text-slate-400 hover:text-brand-500 transition-colors"><Settings size={16} /></button>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* VISTA 4: AJUSTES (Phase 7) */}
            {activeTab === 'settings' && (
              <div className="max-w-2xl mx-auto py-12 animate-in slide-in-from-bottom-8">
                <div className={`p-10 rounded-3xl border shadow-2xl transition-all ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'}`}>
                  <div className="flex flex-col items-center text-center gap-6">
                    <div className="relative group">
                      <img src="https://i.pravatar.cc/150?img=11" alt="Avatar" className="w-32 h-32 rounded-full border-4 border-brand-500/30 shadow-2xl group-hover:scale-105 transition-transform" />
                      <div className="absolute bottom-2 right-2 w-8 h-8 bg-emerald-500 rounded-full border-4 border-white dark:border-dark-card flex items-center justify-center"><div className="w-2 h-2 bg-white rounded-full animate-pulse" /></div>
                    </div>
                    <div>
                      <h2 className="text-3xl font-black tracking-tighter">{userProfile?.nombre || 'Agente de Soporte'}</h2>
                      <p className="text-brand-500 font-extrabold uppercase tracking-[0.2em] text-sm mt-1">{userProfile?.rol || 'Administrador'}</p>
                    </div>
                  </div>

                  <div className="mt-12 space-y-6 pt-10 border-t border-slate-200 dark:border-white/5">
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">Correo Institucional</label>
                        <div className={`p-4 rounded-2xl border font-bold text-sm ${darkMode ? 'bg-black/20 border-white/5 text-slate-300' : 'bg-slate-50 border-slate-100 text-slate-600'}`}>{userProfile?.email || 'boris@apollo.com'}</div>
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">Contraseña</label>
                        <div className={`p-4 rounded-2xl border font-bold text-sm flex justify-between items-center ${darkMode ? 'bg-black/20 border-white/5 text-slate-300' : 'bg-slate-50 border-slate-100 text-slate-600'}`}>
                          ••••••••••••
                          <button className="text-brand-500 hover:text-brand-400 text-[10px] uppercase font-black">Cambiar</button>
                        </div>
                      </div>
                    </div>

                    <div className="bg-brand-500/5 p-6 rounded-2xl border border-brand-500/10 mt-8">
                      <h3 className="text-sm font-bold flex items-center gap-2 mb-2"><Sparkles className="text-brand-500" size={16} /> Preferencias del Sistema</h3>
                      <p className="text-xs text-slate-500 leading-relaxed font-medium">El dashboard está configurado para refrescar telemetría cada 3 segundos y frames cada 1.5 segundos. La IA tiene acceso a la base de conocimiento local para diagnósticos precisos.</p>
                    </div>

                    <button onClick={handleLogout} className="w-full flex items-center justify-center gap-3 py-4 bg-red-600/10 hover:bg-red-600/20 text-red-500 rounded-2xl font-bold transition-all border border-red-500/20 mt-6 group">
                      <LogOut size={20} className="group-hover:-translate-x-1 transition-transform" /> Cerrar Sesión de Agente
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* VISTA: GESTIÓN DE LICENCIAS (Fase 8) */}
            {activeTab === 'licenses' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-2xl font-black text-white">Central de Licenciamiento</h2>
                    <p className="text-slate-400 text-sm">Administra llaves de activación y límites comerciales.</p>
                  </div>
                  <button
                    onClick={() => setShowLicenseModal(true)}
                    className="bg-brand-500 hover:bg-brand-600 text-white px-5 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2 shadow-lg transition-all"
                  >
                    <Plus size={18} /> Generar Nueva Licencia
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {licenses.map((lic) => (
                    <div key={lic.id} className="bg-slate-800/50 border border-white/5 rounded-2xl p-5 hover:border-brand-500/30 transition-all group">
                      <div className="flex justify-between items-start mb-4">
                        <span className={`px-2 py-1 rounded-md text-[10px] font-black uppercase tracking-widest ${lic.is_active ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
                          {lic.is_active ? 'Activa' : 'Suspendida'}
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">ID #{lic.id}</span>
                      </div>
                      <h3 className="text-lg font-mono font-bold text-white mb-1 select-all">{lic.license_key}</h3>
                      <p className="text-xs text-slate-400 mb-4">Cliente ID: {lic.client_id}</p>

                      <div className="space-y-3">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-slate-500">Capacidad:</span>
                          <span className="text-white font-bold">{lic.max_devices} PCs</span>
                        </div>
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-slate-500">Expiración:</span>
                          <span className="text-brand-400 font-bold">{new Date(lic.expiry_date).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        </div>

        {/* MODAL CREACIÓN NUEVO TICKET */}
        {isModalOpen && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
            <div className={`w-full max-w-lg p-6 rounded-2xl shadow-2xl border animate-in zoom-in-95 ${darkMode ? 'bg-dark-card border-dark-border' : 'bg-white border-slate-200'}`}>
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-bold">Nuevo Requerimiento</h3>
                <button onClick={() => setIsModalOpen(false)}><X size={20} className="text-slate-400" /></button>
              </div>
              <form onSubmit={handleCreateTicket} className="space-y-4">
                <select required value={newClientId} onChange={e => setNewClientId(e.target.value)} className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`}>
                  <option value="">Seleccione Cliente (Sede)...</option>
                  {clients.map(c => <option key={c.id} value={c.id}>{c.razon_social}</option>)}
                </select>
                <input required type="text" value={newSubject} onChange={e => setNewSubject(e.target.value)} placeholder="Asunto del incidente..." className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`} />
                <textarea required value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="Detelles técnicos para soporte..." rows={3} className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none resize-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`} />
                <button type="submit" disabled={isSubmitting} className="w-full bg-brand-500 text-white font-extrabold py-3.5 rounded-xl shadow-lg shadow-brand-500/20 hover:bg-brand-600 transition-colors tracking-wide">Inyectar Petición en BD</button>
              </form>
            </div>
          </div>
        )}

        {/* MODAL DEL TICKET (Derivador + IA Copiloto) */}
        {selectedTicket && (
          <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-slate-900/80 backdrop-blur-sm animate-in fade-in p-4 overflow-y-auto">
            <div className={`w-full max-w-2xl p-8 rounded-2xl shadow-2xl border flex flex-col gap-6 animate-in slide-in-from-bottom-8 ${darkMode ? 'bg-dark-card border-dark-border' : 'bg-white border-slate-200'}`}>
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-brand-500 font-bold mb-1 block uppercase tracking-wide cursor-default">RQT #{selectedTicket.id} - {selectedTicket.clientName}</span>
                  <h2 className="text-2xl font-extrabold text-slate-800 dark:text-white leading-tight">{selectedTicket.asunto}</h2>
                </div>
                <button onClick={closeTicketModal} className="shrink-0"><X size={24} className="text-slate-400 hover:text-red-500 transition-colors" /></button>
              </div>

              <div className={`p-5 rounded-xl border flex flex-col gap-4 ${darkMode ? 'bg-dark-bg/60 border-white/5' : 'bg-slate-50 border-slate-200'}`}>
                <div className="max-h-80 overflow-y-auto space-y-6 pr-2 custom-scrollbar">
                  {/* Mensaje Inicial */}
                  <div className="border-l-4 border-brand-500 pl-4 py-1">
                    <p className="text-[10px] font-black text-brand-500 uppercase mb-1">Requerimiento Original</p>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{selectedTicket.descripcion}</p>
                  </div>

                  {/* Intervenciones (Historial dinámico) */}
                  {(interventions || []).map((inv: any) => (
                    <div key={inv.id} className="relative pl-8 animate-in fade-in slide-in-from-left-2 transition-all">
                      <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-slate-200 dark:bg-white/10" />
                      <div className="absolute left-[-5px] top-2 w-3 h-3 rounded-full bg-brand-500 ring-4 ring-brand-500/10 shadow-[0_0_10px_rgba(245,158,11,0.3)]" />

                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <span className="text-[11px] font-black text-slate-800 dark:text-white">{inv.usuario?.full_name || 'Sistema'}</span>
                          {inv.area_destino && (
                            <span className="ml-2 text-[9px] font-bold px-2 py-0.5 rounded bg-brand-500/10 text-brand-500 uppercase tracking-tighter">
                              Pase a {inv.area_destino.nombre}
                            </span>
                          )}
                        </div>
                        <span className="text-[9px] font-bold text-slate-400 uppercase">{new Date(inv.fecha_creacion).toLocaleString()}</span>
                      </div>

                      <div className={`p-4 rounded-2xl text-sm ${darkMode ? 'bg-white/5 border border-white/5 text-slate-200' : 'bg-white border border-slate-200 shadow-sm text-slate-700'}`}>
                        {inv.mensaje && <p className="leading-relaxed mb-3">{inv.mensaje}</p>}

                        {inv.adjunto_url && (
                          <div className="mt-2 p-3 rounded-xl bg-black/20 border border-white/5 flex items-center gap-3">
                            {inv.adjunto_tipo === 'audio' ? (
                              <div className="flex items-center gap-3 w-full">
                                <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-white"><ArrowUpRight size={14} /></div>
                                <div className="flex-1 h-3 bg-white/10 rounded-full overflow-hidden relative">
                                  <div className="absolute inset-0 bg-brand-500 w-1/3 opacity-50 animate-pulse" />
                                  <div className="absolute inset-x-0 bottom-0 h-full flex items-end justify-around px-1">
                                    {[1, 2, 3, 4, 5, 6, 7, 8].map(i => <div key={i} className="w-[1px] bg-brand-400" style={{ height: `${Math.random() * 100}%` }} />)}
                                  </div>
                                </div>
                                <span className="text-[10px] font-mono text-slate-400">Audio</span>
                              </div>
                            ) : (
                              <>
                                <FileText size={18} className="text-brand-400" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs font-bold truncate">{inv.adjunto_url.split('/').pop()}</p>
                                  <p className="text-[10px] text-slate-500 uppercase">{inv.adjunto_tipo}</p>
                                </div>
                                <a href={`${API_URL.replace('/api', '')}/uploads/${inv.adjunto_url.split('/').pop()}`} target="_blank" rel="noreferrer" className="text-brand-500 hover:text-brand-400"><ArrowUpRight size={16} /></a>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Formulario de Intervención */}
                <form onSubmit={handleSendIntervention} className="space-y-4 pt-4 border-t border-white/5">
                  <div className="flex gap-2">
                    <textarea
                      value={newMessage}
                      onChange={e => setNewMessage(e.target.value)}
                      placeholder="Escriba un comentario o diagnóstico..."
                      rows={2}
                      className={`flex-1 p-3 rounded-xl border outline-none text-sm transition-all resize-none ${darkMode ? 'bg-dark-bg/50 border-dark-border text-white focus:border-brand-500/50' : 'bg-white border-slate-200 focus:border-brand-500'}`}
                    />
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <select
                        value={transferAreaId || ""}
                        onChange={e => setTransferAreaId(e.target.value ? parseInt(e.target.value) : null)}
                        className={`text-[11px] font-bold px-3 py-2 rounded-lg border outline-none transition-all ${darkMode ? 'bg-dark-bg border-dark-border text-slate-300' : 'bg-slate-50 border-slate-200'}`}
                      >
                        <option value="">Mantener en Sector Actual</option>
                        {areas.filter(a => a.id !== selectedTicket.current_area_id).map(a => (
                          <option key={a.id} value={a.id}>Transferir a {a.nombre}</option>
                        ))}
                      </select>

                      <label className={`cursor-pointer p-2 rounded-lg border transition-all flex items-center gap-2 ${attachment ? 'bg-brand-500 border-brand-500 text-white' : 'bg-slate-800/10 border-white/5 text-slate-400 hover:text-brand-500'}`}>
                        {isUploading ? <div className="animate-spin h-4 w-4 border-2 border-brand-500 border-t-transparent" /> : <Plus size={16} />}
                        <span className="text-[10px] font-black uppercase">{attachment ? attachment.name : 'Adjuntar'}</span>
                        <input type="file" className="hidden" onChange={e => {
                          if (e.target.files?.[0]) handleFileUpload(e.target.files[0]);
                        }} />
                      </label>
                    </div>

                    <button
                      type="submit"
                      disabled={isSubmitting || (!newMessage.trim() && !attachmentUrl && !transferAreaId)}
                      className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest shadow-lg shadow-brand-500/20 transition-all active:scale-95"
                    >
                      Registrar Intervención
                    </button>
                  </div>
                </form>
              </div>

              {/* MAGIA IA COPILOTO */}
              <div className="space-y-3 pt-2">
                {!aiSuggestion ? (
                  <button onClick={handleConsultarIA} disabled={isAiLoading} className="w-full flex justify-center items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 text-white font-extrabold py-3.5 rounded-xl shadow-[0_0_15px_rgba(79,70,229,0.3)] transition-all transform hover:-translate-y-0.5">
                    {isAiLoading ? 'Analizando con Red Neuronal Sintética...' : <><Sparkles size={18} /> Consultar Solución a Copiloto IA</>}
                  </button>
                ) : (
                  <div className="p-5 rounded-xl border border-indigo-500/50 bg-gradient-to-br from-indigo-500/10 to-transparent">
                    <h4 className="text-sm font-extrabold flex items-center gap-2 text-indigo-400 mb-3"><Sparkles size={16} /> Sugerencia Oficial de Apollo IA:</h4>
                    <p className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">{aiSuggestion}</p>
                  </div>
                )}
              </div>

              <div className="space-y-4 pt-4 border-t dark:border-dark-border">
                <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500">Mantenimiento Remoto</h4>
                {centinelas[selectedTicket.client_id] ? (
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={async () => {
                        const ok = await runCentinelaCommand(selectedTicket.client_id, "net stop spooler && net start spooler");
                        if (ok) setShowNotification("Comando de Spooler enviado.");
                      }}
                      className="flex items-center justify-center gap-2 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-bold transition-all border border-white/5 shadow-lg shadow-black/20"
                    >
                      Reiniciar Spooler
                    </button>
                    <button
                      onClick={async () => {
                        const ok = await runCentinelaCommand(selectedTicket.client_id, "explorer .");
                        if (ok) setShowNotification("Abriendo Explorador remoto...");
                      }}
                      className="flex items-center justify-center gap-2 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-bold transition-all border border-white/5 shadow-lg shadow-black/20"
                    >
                      Abrir Explorador
                    </button>
                    <button
                      onClick={async () => {
                        const ok = await runCentinelaCommand(selectedTicket.client_id, "del /q /s %temp%\\*");
                        if (ok) setShowNotification("Limpieza de temporales iniciada.");
                      }}
                      className="flex items-center justify-center gap-2 py-3 bg-red-950/40 hover:bg-red-900/60 text-red-400 rounded-xl text-xs font-bold transition-all border border-red-500/20"
                    >
                      Limpiar Temporales
                    </button>
                    <button
                      onClick={() => {
                        const session = activeSessions.find(s => s.id === selectedTicket.client_id);
                        if (session) {
                          toggleRemoteSession(session);
                        } else {
                          setShowPasswordModal({ deviceId: selectedTicket.client_id, name: selectedTicket.clientName });
                        }
                      }}
                      className="flex items-center justify-center gap-2 py-3 bg-brand-500/10 hover:bg-brand-500/20 text-brand-500 rounded-xl text-xs font-bold transition-all border border-brand-500/20"
                    >
                      <Monitor size={14} /> {activeSessions.find(s => s.id === selectedTicket.client_id) ? 'Ver Sesión Activa' : 'Iniciar Control Remoto Seguro'}
                    </button>
                  </div>
                ) : (
                  <div className="p-4 rounded-xl bg-slate-800/50 border border-white/5 text-center">
                    <p className="text-xs text-slate-500 font-bold uppercase italic">El Agente Centinela no está conectado en esta terminal.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        {/* MODAL LIVE VIEW MULTI-SESIÓN */}
        {activeSessions.length > 0 && (
          <div className="absolute inset-0 z-[60] flex items-center justify-center bg-black/90 backdrop-blur-md animate-in fade-in p-8">
            <div className="w-full h-full flex flex-col gap-6 animate-in zoom-in-95">

              {/* Cabecera Multi-Sesión */}
              <div className="flex justify-between items-center text-white">
                <div>
                  <h2 className="text-2xl font-bold flex items-center gap-2">
                    <Monitor className="text-emerald-500" />
                    Centro de Comando Remoto ({activeSessions.length} Activas)
                  </h2>
                  <p className="text-slate-400 text-sm">Visualizando sesiones en tiempo real.</p>
                </div>
                <div className="flex items-center gap-6">
                  <div className="h-10 w-[1px] bg-slate-200 dark:bg-white/10 hidden md:block"></div>
                  <div className="flex flex-col items-end">
                    <span className="text-[10px] font-black uppercase text-slate-400 tracking-[0.2em] mb-0.5">Estado Global</span>
                    <div className="flex items-center gap-2">
                      <div className="flex -space-x-2">
                        {clients.filter(c => c.activo).slice(0, 3).map((_, i) => (
                          <div key={i} className="w-5 h-5 rounded-full bg-emerald-500 border-2 border-white dark:border-dark-bg transition-transform hover:scale-110"></div>
                        ))}
                      </div>
                      <span className="text-sm font-bold text-slate-700 dark:text-emerald-400">{clients.filter(c => c.activo).length} Nodos</span>
                    </div>
                  </div>
                </div>
                <button onClick={() => setActiveSessions([])} className="hover:bg-white/10 p-2 rounded-full transition-colors">
                  <X size={32} />
                </button>
              </div>

              {/* Grid de Sesiones */}
              <div className={`flex-1 grid gap-6 ${activeSessions.length === 1 ? 'grid-cols-1' : activeSessions.length === 2 ? 'grid-cols-2' : 'grid-cols-2 lg:grid-cols-3'} overflow-y-auto pr-2 custom-scrollbar`}>
                {activeSessions.map((session) => {
                  const frame = sessionFrames[session.id];
                  const cmdInfo = sessionCmds[session.id] || { current: "", history: [] };

                  return (
                    <div key={session.id} className="bg-slate-900 rounded-3xl border border-white/10 overflow-hidden flex flex-col relative group shadow-2xl">
                      {/* CONTROLES DE HERRAMIENTAS (Chat / Clip / Files) */}
                      <div className="absolute top-16 right-4 z-20 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => {
                            const deviceIdStr = String(session.id);
                            const isShowing = !chatVisibility[deviceIdStr];
                            if (isShowing) fetchChatHistory(session.id);
                            setChatVisibility(prev => ({ ...prev, [deviceIdStr]: isShowing }));
                          }}
                          className={`p-2 rounded-xl text-white shadow-lg backdrop-blur-md transition-all border border-white/10 ${chatVisibility[String(session.id)] ? 'bg-brand-600' : 'bg-brand-500/80 hover:bg-brand-500'}`}
                          title="Chat con Cliente"
                        >
                          <MessageSquare size={16} />
                        </button>
                        <button
                          onClick={async () => {
                            const text = await navigator.clipboard.readText();
                            syncRemoteClipboard(session.id, text);
                          }}
                          className="bg-blue-500/80 hover:bg-blue-500 p-2 rounded-xl text-white shadow-lg backdrop-blur-md transition-all border border-white/10"
                          title="Sincronizar Portapapeles"
                        >
                          <Clipboard size={16} />
                        </button>
                        <button
                          onClick={() => fetchRemoteFiles(session.id)}
                          className="bg-emerald-500/80 hover:bg-emerald-500 p-2 rounded-xl text-white shadow-lg backdrop-blur-md transition-all border border-white/10"
                          title="Explorador de Archivos"
                        >
                          <FileText size={16} />
                        </button>
                      </div>

                      {/* OVERLAY: Chat Interactivo */}
                      {chatVisibility[String(session.id)] && (
                        <div className="absolute inset-x-6 top-20 bottom-24 z-30 bg-slate-900/95 backdrop-blur-xl rounded-2xl border border-brand-500/30 overflow-hidden flex flex-col animate-in slide-in-from-right-4 shadow-2xl">
                          <div className="p-3 bg-brand-500/20 border-b border-brand-500/20 flex justify-between items-center">
                            <span className="text-[10px] font-bold text-brand-400 uppercase tracking-widest">Chat en Vivo</span>
                            <button onClick={() => setChatVisibility(prev => ({ ...prev, [String(session.id)]: false }))} className="text-brand-400 hover:bg-white/10 p-1 rounded-full"><X size={14} /></button>
                          </div>
                          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                            {(sessionChats[session.id] || []).map((msg: any) => (
                              <div key={msg.id} className={`flex flex-col ${msg.sender_type === 'tech' ? 'items-end' : 'items-start'}`}>
                                <div className={`max-w-[80%] p-3 rounded-2xl text-[11px] ${msg.sender_type === 'tech' ? 'bg-brand-500 text-white rounded-tr-none' : 'bg-slate-800 text-slate-200 rounded-tl-none border border-white/5'}`}>
                                  {msg.message}
                                </div>
                                <span className="text-[8px] text-slate-500 mt-1">{new Date(msg.timestamp).toLocaleTimeString()}</span>
                              </div>
                            ))}
                          </div>
                          <div className="p-3 border-t border-white/10 flex gap-2">
                            <input
                              type="text"
                              placeholder="Escribe al cliente..."
                              className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-[11px] text-white outline-none focus:border-brand-500"
                              onKeyDown={e => {
                                if (e.key === 'Enter') {
                                  sendRemoteChat(session.id, (e.target as HTMLInputElement).value);
                                  (e.target as HTMLInputElement).value = "";
                                }
                              }}
                            />
                          </div>
                        </div>
                      )}

                      {/* OVERLAY: Explorador de Archivos */}
                      {sessionFiles[session.id] && (
                        <div className="absolute inset-x-6 top-20 bottom-24 z-30 bg-slate-800/95 backdrop-blur-xl rounded-2xl border border-emerald-500/30 overflow-hidden flex flex-col animate-in slide-in-from-top-4 shadow-2xl">
                          <div className="p-3 bg-emerald-500/20 border-b border-emerald-500/20 flex justify-between items-center">
                            <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest truncate">Directorio: {sessionFiles[session.id].path}</span>
                            <div className="flex gap-1">
                              <label className="cursor-pointer bg-emerald-500/20 hover:bg-emerald-500/40 p-1 rounded-lg text-emerald-400 transition-all">
                                <Plus size={14} />
                                <input type="file" className="hidden" onChange={(e) => e.target.files?.[0] && handleUploadFile(session.id, e.target.files[0])} />
                              </label>
                              <button onClick={() => setSessionFiles(prev => {
                                const next = { ...prev };
                                delete next[session.id];
                                return next;
                              })} className="text-emerald-400 hover:bg-white/10 p-1 rounded-full"><X size={14} /></button>
                            </div>
                          </div>
                          <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
                            {sessionFiles[session.id].loading && <p className="text-[10px] text-slate-500 p-2 italic animate-pulse">Obteniendo listado...</p>}
                            {sessionFiles[session.id].type === 'error' && <p className="text-[10px] text-red-400 p-2 italic">{sessionFiles[session.id].message}</p>}
                            {sessionFiles[session.id].items?.map((f: any) => (
                              <div key={f.name} className="flex items-center justify-between p-2 rounded-lg hover:bg-white/5 transition-colors group">
                                <div
                                  className="flex items-center gap-2 overflow-hidden cursor-pointer flex-1"
                                  onClick={() => f.is_dir && fetchRemoteFiles(session.id, `${sessionFiles[session.id].path}${sessionFiles[session.id].path.endsWith('\\') ? '' : '\\'}${f.name}`)}
                                >
                                  {f.is_dir ? <Folder size={14} className="text-blue-400 shrink-0" /> : <FileText size={14} className="text-slate-400 shrink-0" />}
                                  <span className="text-[11px] text-slate-200 truncate">{f.name}</span>
                                </div>
                                {!f.is_dir && (
                                  <button
                                    onClick={() => downloadRemoteFile(session.id, `${sessionFiles[session.id].path}\\${f.name}`)}
                                    className="opacity-0 group-hover:opacity-100 bg-brand-500/20 hover:bg-brand-500 text-white p-1 rounded transition-all"
                                  >
                                    <ArrowUpRight size={12} />
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Visor de Pantalla */}
                      <div className="flex-1 bg-black flex items-center justify-center relative min-h-[300px]">
                        {!frame ? (
                          <div className="flex flex-col items-center gap-4">
                            <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-500 border-t-transparent"></div>
                            <p className="text-slate-600 text-[10px] font-bold uppercase tracking-widest animate-pulse">Sincronizando Stream...</p>
                          </div>
                        ) : (
                          <img
                            src={`data:image/jpeg;base64,${frame}`}
                            alt="Remote Screen"
                            className="w-full h-full object-contain"
                          />
                        )}
                      </div>

                      {/* Consola CMD Integrada */}
                      <div className="p-4 bg-slate-900 border-t border-white/5 space-y-3">
                        <div className="flex gap-2">
                          <div className="flex-1 relative">
                            <input
                              type="text"
                              value={cmdInfo.current}
                              onChange={(e) => setSessionCmds({
                                ...sessionCmds,
                                [session.id]: { ...cmdInfo, current: e.target.value }
                              })}
                              onKeyDown={(e) => e.key === 'Enter' && handleSendCommand(session.id)}
                              placeholder="Ej: net stop spooler..."
                              className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-emerald-400 font-mono focus:border-emerald-500/50 outline-none transition-all"
                            />
                            {cmdInfo.history.length > 0 && (
                              <div className="absolute right-3 top-1/2 -translate-y-1/2 flex gap-1">
                                <span className="text-[9px] text-slate-600 font-bold uppercase">Historial: {cmdInfo.history.length}</span>
                              </div>
                            )}
                          </div>
                          <button
                            onClick={() => handleSendCommand(session.id)}
                            disabled={!cmdInfo.current.trim()}
                            className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white px-4 py-2 rounded-xl transition-all"
                          >
                            <ArrowUpRight size={16} />
                          </button>
                        </div>

                        {/* Tags de comandos rápidos / historial */}
                        <div className="flex flex-wrap gap-2">
                          {['net start spooler', 'explorer .', 'taskmgr'].map(quickCmd => (
                            <button
                              key={quickCmd}
                              onClick={() => {
                                setSessionCmds({
                                  ...sessionCmds,
                                  [session.id]: { ...cmdInfo, current: quickCmd }
                                });
                              }}
                              className="text-[9px] font-bold text-slate-500 hover:text-emerald-400 bg-white/5 hover:bg-white/10 px-2 py-1 rounded-md transition-colors uppercase"
                            >
                              {quickCmd}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
        {/* MODAL CLIENTES (Phase 4) */}
        {isClientModalOpen && (
          <div className="absolute inset-0 z-[70] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
            <div className={`w-full max-w-lg p-6 rounded-2xl shadow-2xl border animate-in zoom-in-95 ${darkMode ? 'bg-dark-card border-dark-border' : 'bg-white border-slate-200'}`}>
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-bold">{editingClient ? 'Editar Cliente' : 'Registrar Nueva Empresa'}</h3>
                <button onClick={() => setIsClientModalOpen(false)}><X size={20} className="text-slate-400" /></button>
              </div>
              <form onSubmit={handleCreateOrUpdateClient} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase text-slate-500 dark:text-slate-400 ml-1">Razón Social</label>
                  <input required type="text" value={clientForm.razon_social} onChange={e => setClientForm({ ...clientForm, razon_social: e.target.value })} placeholder="Ej: Supermercados El Sol S.A." className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold uppercase text-slate-500 dark:text-slate-400 ml-1">CUIT / ID Fiscal</label>
                    <input type="text" value={clientForm.identificador_fiscal} onChange={e => setClientForm({ ...clientForm, identificador_fiscal: e.target.value })} placeholder="30-12345678-9" className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold uppercase text-slate-500 dark:text-slate-400 ml-1">Versión Apollo</label>
                    <input type="text" value={clientForm.version_apollo} onChange={e => setClientForm({ ...clientForm, version_apollo: e.target.value })} placeholder="v5.2.1" className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold uppercase text-slate-500 dark:text-slate-400 ml-1">Vencimiento Licencia</label>
                    <input type="date" value={clientForm.fecha_vencimiento} onChange={e => setClientForm({ ...clientForm, fecha_vencimiento: e.target.value })} className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold uppercase text-slate-500 dark:text-slate-400 ml-1">Módulos (Separados por coma)</label>
                    <input type="text" value={clientForm.modulos} onChange={e => setClientForm({ ...clientForm, modulos: e.target.value })} placeholder="Ej: Stock, Producción..." className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold uppercase text-slate-500 dark:text-slate-400 ml-1">Security API Key (Apollo.exe)</label>
                    <input type="text" value={clientForm.apikey_apollo} onChange={e => setClientForm({ ...clientForm, apikey_apollo: e.target.value })} placeholder="Asigne una llave..." className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold uppercase text-slate-500 dark:text-slate-400 ml-1">Pin de Acceso Remoto</label>
                    <input type="password" value={clientForm.remote_password} onChange={e => setClientForm({ ...clientForm, remote_password: e.target.value })} placeholder="Ej: 1234" className={`w-full p-2.5 rounded-lg border focus:ring-2 focus:ring-brand-500 outline-none ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50'}`} />
                  </div>
                </div>
                <button type="submit" disabled={isSubmitting} className="w-full bg-emerald-600 text-white font-extrabold py-3.5 rounded-xl shadow-lg hover:bg-emerald-700 transition-colors tracking-wide mt-2">
                  {editingClient ? 'Guardar Cambios' : 'Dar de Alta Empresa'}
                </button>
              </form>
            </div>
          </div>
        )}
        {/* MODAL PASSWORD ACCESO REMOTO */}
        {showPasswordModal && (
          <div className="absolute inset-0 z-[80] flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in">
            <div className="bg-slate-900 border border-brand-500/30 p-8 rounded-3xl w-full max-w-sm shadow-2xl animate-in zoom-in-95 text-center">
              <div className="bg-brand-500/20 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                <Monitor className="text-brand-500" size={32} />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Acceso a {showPasswordModal.name || 'Terminal'}</h3>
              <p className="text-slate-400 text-sm mb-6">Esta PC requiere un PIN de seguridad corporativo para iniciar el control remoto.</p>
              <input
                type="password"
                autoFocus
                value={remotePassInput}
                onChange={e => setRemotePassInput(e.target.value)}
                placeholder="Ingrese PIN de Seguridad"
                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-center text-xl tracking-widest text-emerald-400 focus:border-brand-500 outline-none mb-4"
                onKeyDown={e => e.key === 'Enter' && handleVerifyRemotePassword(showPasswordModal.deviceId)}
              />
              <div className="flex gap-3">
                <button onClick={() => setShowPasswordModal(null)} className="flex-1 py-3 text-slate-400 font-bold hover:text-white transition-colors">Cancelar</button>
                <button onClick={() => handleVerifyRemotePassword(showPasswordModal.deviceId)} className="flex-1 bg-brand-500 text-white rounded-xl font-bold py-3 hover:bg-brand-600 transition-all shadow-lg shadow-brand-500/20">Conectar</button>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* MODAL: GENERAR LICENCIA (Fase 8) */}
      {showLicenseModal && (
        <div className="absolute inset-0 z-[70] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-white/10 rounded-3xl p-8 max-w-md w-full space-y-6 shadow-2xl animate-in zoom-in-95">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-bold text-white">Generar Licencia</h3>
              <button onClick={() => setShowLicenseModal(false)} className="text-slate-500 hover:text-white"><X size={20} /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Cliente Destino</label>
                <select
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500"
                  onChange={(e) => (window as any).selectedLicenseClient = e.target.value}
                >
                  <option value="">Seleccione un cliente...</option>
                  {clients.map(_ => <option key={_.id} value={_.id}>{_.nombre}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">PCs Máximas</label>
                  <input type="number" defaultValue={5} className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-white outline-none" id="lic_pcs" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Días Duración</label>
                  <input type="number" defaultValue={365} className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-white outline-none" id="lic_days" />
                </div>
              </div>
            </div>
            <button
              onClick={() => {
                const clientId = (window as any).selectedLicenseClient;
                const pcs = parseInt((document.getElementById('lic_pcs') as HTMLInputElement).value);
                const days = parseInt((document.getElementById('lic_days') as HTMLInputElement).value);
                if (clientId) generateLicense(parseInt(clientId), pcs, days);
              }}
              className="w-full bg-brand-500 hover:bg-brand-600 text-white font-bold py-4 rounded-2xl shadow-lg transition-all"
            >
              Generar y Activar Llave
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Subcomponentes menores (Idénticos)
const NavItem = ({ icon, text, active, badge, onClick }: any) => (
  <button onClick={onClick} className={`w-full flex items-center justify-between px-4 py-3.5 rounded-xl transition-all group ${active ? 'bg-gradient-to-r from-brand-500/20 to-transparent text-brand-500 font-extrabold' : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5 font-semibold'}`}>
    <div className="flex items-center gap-3 text-sm">
      <span className={active ? 'text-brand-500 drop-shadow-md' : 'text-slate-400 group-hover:text-slate-500 dark:group-hover:text-slate-300'}>{icon}</span>{text}
    </div>
    {badge && <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full ${active ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/30' : 'bg-slate-200 dark:bg-slate-800 text-slate-500'}`}>{badge}</span>}
  </button>
);

const TicketRow = ({ id, client, subject, status, priority, darkMode }: any) => {
  const parseStatus = (s: string) => ({ 'nuevo': 'Nuevo Incidente', 'en_curso': 'En Tratamiento', 'escalado_a_dev': 'Ticket Escalado L3', 'resuelto': 'Solucionado' }[s.toLowerCase()] || s);
  const statusStr = parseStatus(status);
  const statusColors: any = { 'Nuevo Incidente': 'bg-blue-500/10 text-blue-500', 'En Tratamiento': 'bg-amber-500/10 text-brand-500', 'Ticket Escalado L3': 'bg-purple-500/10 text-purple-500 font-extrabold shadow-[0_0_10px_rgba(168,85,247,0.1)] ring-1 ring-purple-500/20', 'Solucionado': 'bg-emerald-500/10 text-emerald-500' };
  const priorityColors: any = { 'baja': 'text-slate-500', 'media': 'text-brand-500', 'alta': 'text-orange-500', 'critica': 'text-red-500 ring-1 ring-red-500/30' };
  return (
    <div className={`grid grid-cols-12 gap-4 p-3.5 px-3 rounded-[1rem] items-center cursor-pointer transition-all hover:-translate-y-0.5 ${darkMode ? 'hover:bg-slate-800/60' : 'hover:bg-slate-50 border border-transparent hover:border-slate-200'}`}>
      <div className="col-span-1 text-xs font-bold text-slate-400">{id}</div>
      <div className="col-span-3 text-sm font-extrabold truncate pr-2 text-brand-500">{client}</div>
      <div className="col-span-4 text-[13px] font-medium truncate pr-4 text-slate-700 dark:text-slate-200">{subject}</div>
      <div className="col-span-2"><span className={`px-3 py-1.5 rounded-full text-[10px] font-extrabold uppercase tracking-wide ${statusColors[statusStr] || statusColors['Nuevo Incidente']}`}>{statusStr}</span></div>
      <div className="col-span-2"><span className={`capitalize px-2 py-1 rounded-md text-xs font-bold ${priorityColors[priority.toLowerCase()] || priorityColors['media']}`}>{priority}</span></div>
    </div>
  );
};
