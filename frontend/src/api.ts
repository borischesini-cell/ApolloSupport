// ─── CONFIGURACIÓN DE ENTORNO ───────────────────────────────────────────────
// Para cambiar entre local y producción sin recompilar, edita el archivo
// .env.development (local) o .env.production (producción):
//
//   VITE_BACKEND_MODE=local        → apunta a http://localhost:8001
//   VITE_BACKEND_MODE=production   → apunta a https://support.ultimate.net.ar
//
// Si no se define VITE_BACKEND_MODE, se detecta automáticamente por hostname.
// ─────────────────────────────────────────────────────────────────────────────

const BACKEND_MODE = import.meta.env.VITE_BACKEND_MODE as string | undefined;

const LOCAL_API    = 'http://localhost:8001/api';
const PROD_API     = 'https://support.ultimate.net.ar/api';

export const API_URL: string =
  import.meta.env.VITE_API_URL ||
  (BACKEND_MODE === 'local'      ? LOCAL_API  :
   BACKEND_MODE === 'production' ? PROD_API   :
   // Auto-detect por hostname cuando no se define VITE_BACKEND_MODE
   (window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1')
     ? LOCAL_API
     : PROD_API);

// URL base para WebSockets (http→ws, https→wss automático)
export const WS_BASE_URL = API_URL.replace(/^http/, 'ws');

console.info(`[Apollo] Backend mode: ${BACKEND_MODE ?? 'auto'} → ${API_URL}`);

// ──────────────────────────────────────────────────────────────────────────────
// HOOK: useViewerWebSocket
// Conecta al endpoint /api/ws/viewer/{deviceId} para recibir frames vía PUSH.
// El backend empuja cada frame en cuanto lo recibe del agente (sin polling).
// Incluye:
//   - Reconexión automática con backoff exponencial (1s → 2s → 4s → máx 30s)
//   - Ping cada 25s para mantener viva la conexión
//   - Medición de FPS y calidad de señal en tiempo real
//   - Fallback automático a polling HTTP si el WS falla 3 veces seguidas
// ──────────────────────────────────────────────────────────────────────────────
import { useEffect, useRef, useCallback } from 'react';

export type ConnectionQuality = 'excellent' | 'good' | 'poor' | 'disconnected';

/** Por debajo de esto el remoto en WebP es poco usable para operar a diario. */
export const REMOTE_STREAM_WORKABLE_FPS = 12;
/** Holgura para volver a subir calidad en modo automático sin quedar en el límite. */
export const REMOTE_STREAM_COMFORTABLE_FPS = 15;

export function connectionQualityFromFps(fps: number): ConnectionQuality {
  if (fps >= REMOTE_STREAM_COMFORTABLE_FPS) return 'excellent';
  if (fps >= REMOTE_STREAM_WORKABLE_FPS) return 'good';
  return 'poor';
}

// DIRTY_RECT_START ── Metadatos del rectángulo sucio enviado por el agente.
// Si delta === undefined → frame completo (comportamiento original).
// Para revertir: ignorar delta en el callback de onFrame en App.tsx.
export interface DeltaMeta {
  x: number; y: number;   // offset del crop en el frame completo
  w: number; h: number;   // tamaño del crop
  fw: number; fh: number; // tamaño total del frame completo
}
// DIRTY_RECT_END ─────────────────────────────────────────────────────────────

interface ViewerWsOptions {
  deviceId: number | null;
  enabled: boolean;
  onFrame: (base64: string, delta?: DeltaMeta) => void;
  onQuality?: (fps: number, quality: ConnectionQuality) => void;
  onMessage?: (msg: Record<string, unknown>) => void;  // para session_list, login_result, etc.
  onHqChunk?: (chunk: ArrayBuffer) => void; // Manejador de chunks binarios H.264
  /** Se llama al cerrar el socket (antes de reintentar). Reactiva polling HTTP si el WS no entrega. */
  onClose?: () => void;
}


export function useViewerWebSocket({ deviceId, enabled, onFrame, onQuality, onMessage, onClose, onHqChunk }: ViewerWsOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const backoffRef = useRef<number>(1000);
  const failCountRef = useRef<number>(0);
  const frameTimestampsRef = useRef<number[]>([]);
  const lastQualityUpdateRef = useRef<number>(0);
  const mountedRef = useRef<boolean>(true);

  const cleanup = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      if (wsRef.current.readyState < 2) wsRef.current.close();
      wsRef.current = null;
    }
    if (pingTimerRef.current) { clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
    if (reconnectTimerRef.current) { clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current || !deviceId || !enabled) return;
    cleanup();

    const token = localStorage.getItem('token');
    if (!token) return;

    const url = `${WS_BASE_URL}/ws/viewer/${deviceId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return; }
      backoffRef.current = 500;
      failCountRef.current = 0;

      try {
        ws.send(JSON.stringify({ type: 'refresh_frame' }));
        ws.send(JSON.stringify({ type: 'get_sessions' }));
      } catch { /* */ }

      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 20000);
    };

    ws.onmessage = async (event) => {
      if (!mountedRef.current) return;
      
      // Manejar chunks binarios de HQ (H.264)
      if (event.data instanceof ArrayBuffer) {
        if (onHqChunk) {
            onHqChunk(event.data);
            
            // Reusar el calculador de FPS para HQ
            const now = performance.now();
            frameTimestampsRef.current.push(now);
            const twoSecsAgo = now - 2000;
            frameTimestampsRef.current = frameTimestampsRef.current.filter(t => t > twoSecsAgo);
            
            if (!lastQualityUpdateRef.current || now - lastQualityUpdateRef.current >= 2000) {
              const fps = Math.round(frameTimestampsRef.current.length / 2);
              onQuality?.(fps, connectionQualityFromFps(fps));

              lastQualityUpdateRef.current = now;
            }
        }
        return;
      }
      
      if (event.data === 'pong') return; // Ignore pong
      
      if (typeof event.data !== 'string') {
        console.log('[WS] Recibido dato desconocido no-string y no-blob:', typeof event.data, event.data);
      }

      try {
        const data = JSON.parse(event.data);
        if (data.type === 'frame' && data.frame) {
          // DIRTY_RECT_START: pasar delta si el agente lo incluyó
          onFrame(data.frame as string, data.delta as DeltaMeta ?? undefined);
          // DIRTY_RECT_END

          // Calcular FPS
          const now = performance.now();
          frameTimestampsRef.current.push(now);
          const twoSecsAgo = now - 2000;
          frameTimestampsRef.current = frameTimestampsRef.current.filter(t => t > twoSecsAgo);
          
          if (!lastQualityUpdateRef.current || now - lastQualityUpdateRef.current >= 2000) {
            const fps = Math.round(frameTimestampsRef.current.length / 2);
            onQuality?.(fps, connectionQualityFromFps(fps));
            lastQualityUpdateRef.current = now;
          }
        } else if (data.type === 'ping') {
          /* keepalive del servidor */
        } else if (onMessage) {
          // Otros mensajes del agente (session_list, login_result, etc.)
          onMessage(data as Record<string, unknown>);
        }
        // ping/pong manejado por servidor, no necesita acción en cliente
      } catch (e) { console.error('[WS] Error processing JSON message:', e); }
    };


    ws.onerror = () => {
      failCountRef.current += 1;
    };

    ws.onclose = () => {
      if (pingTimerRef.current) { clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
      try {
        onClose?.();
      } catch { /* */ }
      if (!mountedRef.current || !enabled) return;

      const cap = Math.min(backoffRef.current, 3000);
      const delay = cap + Math.floor(Math.random() * 300);
      backoffRef.current = Math.min(backoffRef.current * 1.5, 3000);

      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current && enabled) connect();
      }, delay);
    };
  }, [deviceId, enabled, cleanup]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled && deviceId) {
      connect();
    }
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [deviceId, enabled, connect, cleanup]);

  // Exponer función para enviar comandos al agente vía este WS
  const sendCommand = useCallback((cmd: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(cmd));
    }
  }, []);

  return { sendCommand };
}


const parseApiErrorDetail = (detail: unknown): string => {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail.map((item: any) => item?.msg || JSON.stringify(item)).join('; ');
    }
    return 'Error en la operación';
};

const parseJsonOrThrow = async (response: Response) => {
    if (response.status === 401) throw new Error('Sesión Expirada');
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseApiErrorDetail((data as any).detail));
    return data;
};

export const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'Content-Type': 'application/json'
});

// ==========================================
// TICKETS Y AREAS
// ==========================================
export const getTickets = async (areaId?: number) => {
    const url = areaId ? `${API_URL}/tickets/?area_id=${areaId}` : `${API_URL}/tickets/`;
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al obtener tickets');
    return await response.json();
};

export const createTicket = async (data: any) => {
    const response = await fetch(`${API_URL}/tickets/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data)
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const getAreas = async () => {
    const response = await fetch(`${API_URL}/areas`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const addIntervention = async (ticketId: number, data: any) => {
    const response = await fetch(`${API_URL}/tickets/${ticketId}/interventions`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data)
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

// ==========================================
// CLIENTES
// ==========================================
export const getClients = async () => {
    const response = await fetch(`${API_URL}/clients/?limit=5000`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const createClient = async (data: any) => {
    const response = await fetch(`${API_URL}/clients/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data)
    });
    return await parseJsonOrThrow(response);
};

export const updateClient = async (clientId: number, data: any) => {
    const response = await fetch(`${API_URL}/clients/${clientId}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(data)
    });
    return await parseJsonOrThrow(response);
};

export const toggleClientStatus = async (clientId: number) => {
    const response = await fetch(`${API_URL}/clients/${clientId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const syncClientsFromDbf = async () => {
    const response = await fetch(`${API_URL}/clients/sync`, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al sincronizar clientes con la base de datos DBF');
    }
    return await response.json();
};

export const syncSaldosFromErp = async () => {
    const response = await fetch(`${API_URL}/clients/sync-saldos-erp`, {
        method: 'POST',
        headers: getAuthHeaders(),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al sincronizar saldos ERP');
    }
    return await response.json();
};

// ==========================================
// INTEGRACIÓN ERP (Saldos, Extractos, PDFs)
// ==========================================
export const getClientBalance = async (clientIdOrCode: string | number) => {
    const response = await fetch(`${API_URL}/erp/clientes/${clientIdOrCode}/saldo`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al consultar saldo en el ERP');
    return await response.json();
};

export const getEstadosCuentaCorriente = async (soloActivos = false) => {
    const response = await fetch(
        `${API_URL}/estados-cuenta-corriente?solo_activos=${soloActivos ? 'true' : 'false'}`,
        { headers: getAuthHeaders() }
    );
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al listar estados de cuenta corriente');
    return await response.json();
};

export const createEstadoCuentaCorriente = async (payload: { codigo: string; descripcion: string; activo?: boolean }) => {
    const response = await fetch(`${API_URL}/estados-cuenta-corriente`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al crear estado');
    }
    return await response.json();
};

export const updateEstadoCuentaCorriente = async (id: number, payload: { descripcion?: string; activo?: boolean }) => {
    const response = await fetch(`${API_URL}/estados-cuenta-corriente/${id}`, {
        method: 'PUT',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al actualizar estado');
    }
    return await response.json();
};

export const deleteEstadoCuentaCorriente = async (id: number) => {
    const response = await fetch(`${API_URL}/estados-cuenta-corriente/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al eliminar estado');
    }
    return await response.json();
};

export const syncEstadosCuentaCorrienteFromErp = async () => {
    const response = await fetch(`${API_URL}/estados-cuenta-corriente/sync-erp`, {
        method: 'POST',
        headers: getAuthHeaders(),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al sincronizar estados desde el ERP');
    }
    return await response.json();
};

export const getClientLicFacturadas = async (clientIdOrCode: string | number) => {
    const response = await fetch(`${API_URL}/erp/clientes/${clientIdOrCode}/lic-facturadas`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al consultar licencias facturadas');
    }
    return await response.json();
};

export const getActivationRequests = async (pendingOnly = true) => {
    const response = await fetch(
        `${API_URL}/erp-licenses/activation-requests?pending_only=${pendingOnly ? 'true' : 'false'}`,
        { headers: getAuthHeaders() }
    );
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al consultar activaciones pendientes');
    return await response.json();
};

export const resolveActivationRequest = async (
    keyId: number,
    payload: { state: string; message?: string; new_date?: string }
) => {
    const response = await fetch(`${API_URL}/erp-licenses/activation-requests/${keyId}/resolve`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al resolver la solicitud');
    }
    return await response.json();
};

export const getPendingExtensions = async (pendingOnly = true) => {
    const response = await fetch(
        `${API_URL}/erp-licenses/extensions?pending_only=${pendingOnly ? 'true' : 'false'}`,
        { headers: getAuthHeaders() }
    );
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al consultar extensiones pendientes');
    return await response.json();
};

export const approveExtension = async (keyId: number, newDate?: string) => {
    const response = await fetch(`${API_URL}/erp-licenses/extensions/${keyId}/approve`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_date: newDate || null }),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al generar la extensión');
    }
    return await response.json();
};

export const getClientExtracto = async (clientIdOrCode: string | number, desde?: string, hasta?: string) => {
    let url = `${API_URL}/erp/clientes/${clientIdOrCode}/extracto`;
    const params = new URLSearchParams();
    if (desde) params.append('desde', desde);
    if (hasta) params.append('hasta', hasta);
    if (params.toString()) url += `?${params.toString()}`;

    const response = await fetch(url, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al consultar extracto en el ERP');
    return await response.json();
};

export const viewVoucherPdf = async (hashFac: string) => {
    const response = await fetch(`${API_URL}/erp/comprobantes/${hashFac}/pdf`, {
        headers: getAuthHeaders()
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al generar comprobante PDF del ERP');
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    window.open(objectUrl, '_blank');
};

// ==========================================
// CENTINELA (ACCESOS REMOTOS)
// ==========================================
export const getActiveCentinelas = async () => {
    const response = await fetch(`${API_URL}/centinelas/activos`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export type WindowsSessionInfo = {
  id: number;
  name: string;
  username: string;
  state: string;
  current: boolean;
};

export const fetchWindowsSessions = async (deviceId: number): Promise<WindowsSessionInfo[]> => {
  const response = await fetch(
    `${API_URL}/centinelas/devices/${deviceId}/windows-sessions?refresh=1&t=${Date.now()}`,
    { headers: getAuthHeaders() }
  );
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) return [];
  const data = await response.json();
  return (data.sessions as WindowsSessionInfo[]) ?? [];
};

export const getCentinelaFrame = async (clientId: number) => {
    const headers = {
        ...getAuthHeaders(),
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    };
    const response = await fetch(`${API_URL}/centinelas/devices/${clientId}/frame?t=${Date.now()}`, { headers });
    if (response.status === 401) throw new Error('Sesión Expirada');
    const data = await response.json();
    return data.frame;
};

export const getCentinelaAlerts = async () => {
    const response = await fetch(`${API_URL}/centinelas/alertas`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const runCentinelaCommand = async (clientId: number, command: string) => {
    const response = await fetch(`${API_URL}/centinelas/devices/${clientId}/command`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ command })
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return response.ok;
};

export const sendCentinelaControl = async (deviceId: number, controlData: any) => {
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/control`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(controlData)
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return response.ok;
};

export const deleteCentinelaDevice = async (deviceId: number) => {
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return response.ok;
};

export const updateCentinelaDeviceNotes = async (deviceId: number, notes: string) => {
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/notes`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ notes })
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return response.ok;
};

export const getPendingCentinelas = async () => {
    const response = await fetch(`${API_URL}/centinelas/pending`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (response.ok) return await response.json();
    return [];
};

export const toggleAndroidDevice = async (deviceId: number, habilitado: boolean) => {
    const response = await fetch(`${API_URL}/android-devices/toggle`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ id: deviceId, habilitado: habilitado ? 1 : 0 }),
    });
    return await parseJsonOrThrow(response);
};

export const assignCentinelaLicense = async (deviceId: number, clientId: number) => {
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/assign/${clientId}`, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    return await parseJsonOrThrow(response);
};

export const getCentinelaClipboard = async (deviceId: number) => {
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/clipboard`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    const data = await response.json();
    return data.text;
};


// ==========================================
// UTILIDADES E IA
// ==========================================
export const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
        body: formData
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const fetchAiAnalysis = async (id: number) => {
    const response = await fetch(`${API_URL}/ai/analyze-ticket/${id}`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

// Compatibilidad Legada (Mapeados a nuevas estructuras si es necesario)
export const getTicketMessages = async (ticketId: number) => getTickets().then(ts => ts.find((t: any) => t.id === ticketId)?.intervenciones || []);
export const sendTicketMessage = async (ticketId: number, mensaje: string) => addIntervention(ticketId, { mensaje, tipo: 'comentario' });
export const escalateTicketToDev = async (ticketId: number, nota: string) => addIntervention(ticketId, { mensaje: nota, tipo: 'transferencia', to_area_id: 2 }); // Asumiendo ID 2 es Dev

// ==========================================
// USUARIOS, ABM Y MONITOREO DE PERSONAL (NUEVO)
// ==========================================
export const getUsers = async () => {
    const response = await fetch(`${API_URL}/users`, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const createUser = async (data: any) => {
    const response = await fetch(`${API_URL}/users`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data)
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Error al crear usuario');
    }
    return await response.json();
};

export const updateUser = async (userId: number, data: any) => {
    const response = await fetch(`${API_URL}/users/${userId}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(data)
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Error al actualizar usuario');
    }
    return await response.json();
};

export const toggleUserStatus = async (userId: number) => {
    const response = await fetch(`${API_URL}/users/${userId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const updateUserStatus = async (isOnline?: boolean, currentTask?: string, currentPage?: string) => {
    const response = await fetch(`${API_URL}/users/status`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
            is_online: isOnline,
            current_task: currentTask,
            current_page: currentPage
        })
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const logoutUser = async () => {
    try {
        await fetch(`${API_URL}/users/logout`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
    } catch (e) {
        console.error('Error log out:', e);
    }
};


// ──────────────────────────────────────────────────────────────────────────────
// HOOK: useHqViewerWebSocket — Alto Rendimiento (H.264 binary stream)
// Conecta al endpoint /api/ws/viewer/{deviceId}/hq para recibir chunks binarios
// de H.264/fMP4 que se alimentan directamente a MediaSource Extensions (MSE).
//
// Sin base64, sin JSON. Bytes crudos → browser decode hardware.
// ROLLBACK: si este hook no se usa (hqEnabled=false), no hay overhead alguno.
// ──────────────────────────────────────────────────────────────────────────────
interface HqViewerOptions {
  deviceId: number | null;
  enabled: boolean;                              // true solo cuando toggle HQ está ON
  onChunk: (chunk: ArrayBuffer) => void;         // recibe cada chunk H.264/fMP4
  onStateChange?: (state: 'connecting' | 'open' | 'closed') => void;
  reconnectAttempt?: number;                     // número incremental para forzar reconexión de stream
  logCallback?: (message: string, level?: string) => void; // NUEVO: Callback de telemetría
}

export function useHqViewerWebSocket({ deviceId, enabled, onChunk, onStateChange, reconnectAttempt, logCallback }: HqViewerOptions) {
  const wsRef             = useRef<WebSocket | null>(null);
  const mountedRef        = useRef<boolean>(true);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef      = useRef<ReturnType<typeof setInterval> | null>(null);
  const backoffRef        = useRef<number>(1000);

  const cleanup = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      if (wsRef.current.readyState < 2) wsRef.current.close();
      wsRef.current = null;
    }
    if (pingTimerRef.current)      { clearInterval(pingTimerRef.current);  pingTimerRef.current = null; }
    if (reconnectTimerRef.current) { clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
  }, []);

  const onChunkRef = useRef(onChunk);
  const onStateChangeRef = useRef(onStateChange);
  const logCallbackRef = useRef(logCallback);

  useEffect(() => {
    onChunkRef.current = onChunk;
    onStateChangeRef.current = onStateChange;
    logCallbackRef.current = logCallback;
  }, [onChunk, onStateChange, logCallback]);

  const connect = useCallback(() => {
    if (!mountedRef.current || !deviceId || !enabled) return;
    cleanup();

    const token = localStorage.getItem('token');
    if (!token) {
      console.warn('[HQ-WS] No se encontró token para la conexión WS');
      if (logCallbackRef.current) logCallbackRef.current('[FRONTEND-WS] ERROR: No se encontró token de sesión para la conexión WebSocket', 'ERROR');
      return;
    }

    const url = `${WS_BASE_URL}/ws/viewer/${deviceId}/hq?token=${encodeURIComponent(token)}`;
    console.log(`[HQ-WS] Iniciando WebSocket hacia: ${url}`);
    if (logCallbackRef.current) logCallbackRef.current(`[FRONTEND-WS] Iniciando intento de conexión WebSocket hacia: ${url}`, 'INFO');
    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';   // recibir chunks como ArrayBuffer, no Blob
    wsRef.current = ws;
    onStateChange?.('connecting');

    let firstChunkReceived = false;
    let noDataTimer: ReturnType<typeof setTimeout> | null = null;
    let totalChunksReceived = 0;
    let totalBytesReceived = 0;

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return; }
      console.log('[HQ-WS] Conexión establecida con el Backend. Esperando primer chunk de video...');
      if (logCallbackRef.current) logCallbackRef.current('[FRONTEND-WS] Conexión establecida con el Backend con éxito. Esperando primer chunk de video...', 'INFO');
      backoffRef.current = 1000;
      // Timeout: si en 30s no llegan datos, el agente no soporta HQ o no está transmitiendo.
      noDataTimer = setTimeout(() => {
        if (!firstChunkReceived && ws.readyState === WebSocket.OPEN) {
          console.warn('[HQ-WS] Sin datos en 30s — agente no soporta HQ o backend no reiniciado');
          if (logCallbackRef.current) logCallbackRef.current('[FRONTEND-WS] ADVERTENCIA: Conexión abierta por 30s pero no se ha recibido ningún chunk binario de video. Cerrando.', 'WARNING');
          ws.close();
        }
      }, 30000);
      // Ping cada 25s para mantener viva la conexión
      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          console.log('[HQ-WS] Enviando ping al servidor');
          ws.send('ping');
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      if (event.data instanceof ArrayBuffer && event.data.byteLength > 0) {
        totalChunksReceived++;
        totalBytesReceived += event.data.byteLength;
        
        if (!firstChunkReceived) {
          firstChunkReceived = true;
          if (noDataTimer) { clearTimeout(noDataTimer); noDataTimer = null; }
          console.log(`[HQ-WS] ¡PRIMER CHUNK RECIBIDO! Tamaño: ${event.data.byteLength} bytes. Cambiando estado a OPEN.`);
          if (logCallbackRef.current) logCallbackRef.current(`[FRONTEND-WS] ¡ÉXITO! Recibido primer chunk binario del backend (${event.data.byteLength} bytes). Decodificador MSE listo.`, 'INFO');
          if (onStateChangeRef.current) onStateChangeRef.current('open');  // ← ahora si: hay datos reales
        }
        
        if (totalChunksReceived % 100 === 0) {
          console.log(`[HQ-WS] Estadísticas: Recibidos ${totalChunksReceived} chunks, total ${totalBytesReceived} bytes.`);
          if (logCallbackRef.current) logCallbackRef.current(`[FRONTEND-WS] Estadísticas: Recibidos ${totalChunksReceived} chunks de video (total: ${totalBytesReceived} bytes)`, 'INFO');
        }
        if (onChunkRef.current) onChunkRef.current(event.data);
      } else {
        console.log('[HQ-WS] Mensaje de texto recibido (pong/control):', event.data);
      }
    };

    ws.onerror = (err) => {
      console.error('[HQ-WS] Error en la conexión WebSocket:', err);
      if (logCallbackRef.current) logCallbackRef.current(`[FRONTEND-WS] ERROR en WebSocket: Conexión fallida o rechazada por el servidor/proxy`, 'ERROR');
    };

    ws.onclose = (event) => {
      console.log(`[HQ-WS] Conexión cerrada. Código: ${event.code}, Razón: ${event.reason || 'Sin especificar'}`);
      if (logCallbackRef.current) logCallbackRef.current(`[FRONTEND-WS] Conexión cerrada. Código: ${event.code}, Razón: ${event.reason || 'Sin especificar'}`, 'WARNING');
      if (pingTimerRef.current) { clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
      if (onStateChangeRef.current) onStateChangeRef.current('closed');
      if (!mountedRef.current || !enabled) return;
      const cap = Math.min(backoffRef.current, 3000);
      const delay = cap + Math.floor(Math.random() * 300);
      backoffRef.current = Math.min(backoffRef.current * 1.5, 3000);
      console.log(`[HQ-WS] Intentando reconectar en ${delay}ms...`);
      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current && enabled) connect();
      }, delay);
    };
  }, [deviceId, enabled, cleanup]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled && deviceId) connect();
    else cleanup();
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [deviceId, enabled, connect, cleanup]);

  // Forzar reconexión cuando reconnectAttempt cambie (e.g. por decode error)
  useEffect(() => {
    if (enabled && deviceId && reconnectAttempt && reconnectAttempt > 0) {
      console.log(`[HQ] Forzando reconexion por error de reproduccion. Intento: ${reconnectAttempt}`);
      connect();
    }
  }, [reconnectAttempt, enabled, deviceId, connect]);
}

// ==========================================
// BITÁCORA DE LOGS DE TELEMETRÍA (NUEVO)
// ==========================================
export const getCentinelaLogs = async (deviceId?: number | null, level?: string, source?: string, limit: number = 100) => {
    let url = `${API_URL}/centinelas/logs?limit=${limit}`;
    if (deviceId !== undefined && deviceId !== null) url += `&device_id=${deviceId}`;
    if (level) url += `&level=${encodeURIComponent(level)}`;
    if (source) url += `&source=${encodeURIComponent(source)}`;
    
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al obtener logs de telemetría');
    return await response.json();
};

export const clearCentinelaLogs = async (deviceId?: number | null) => {
    let url = `${API_URL}/centinelas/logs/clear`;
    if (deviceId !== undefined && deviceId !== null) url += `?device_id=${deviceId}`;
    
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al limpiar la bitácora de logs');
    return await response.json();
};



export const forceCentinelaUpdate = async (deviceId: string | number) => {
    const response = await fetch(`${API_URL}/centinela/${deviceId}/force_update`, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Error al forzar actualizacion');
    return response.json();
};

/** Libera sesión remota colgada (quita "Ocupado por..." y cierra SupportSessions abiertas). */
export const releaseCentinelaSession = async (deviceId: number) => {
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/release-session`, {
        method: 'POST',
        headers: getAuthHeaders(),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al liberar sesión');
    }
    return response.json();
};

/** Cancela switch pendiente y fuerza refresh_frame / wake_screen en el agente. */
export const forceCentinelaRefresh = async (deviceId: number) => {
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/force-refresh`, {
        method: 'POST',
        headers: getAuthHeaders(),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al forzar refresh del agente');
    }
    return response.json();
};

// ==========================================
// AGENDA: REUNIONES + GRABACIONES
// ==========================================
export type ScheduledMeeting = {
  id: number;
  client_id: number;
  host_user_id: number;
  title: string;
  agenda?: string | null;
  starts_at: string;
  duration_minutes: number;
  join_url: string;
  status: string;
  notify_minutes_before: number;
  client_email?: string | null;
  client_phone?: string | null;
  alert_sent_at?: string | null;
  client_name?: string | null;
  host_name?: string | null;
};

export type ScheduledRecording = {
  id: number;
  client_id: number;
  device_id: number;
  technician_id: number;
  scheduled_at: string;
  duration_minutes: number;
  status: string;
  file_path?: string | null;
  file_size?: number | null;
  started_at?: string | null;
  ended_at?: string | null;
  error_message?: string | null;
  notes?: string | null;
  client_name?: string | null;
  device_name?: string | null;
  assist_id?: string | null;
  technician_name?: string | null;
  has_video?: boolean;
  duration_seconds?: number | null;
};

export type MeetingShare = {
  join_url: string;
  message: string;
  mailto?: string | null;
  wa_url?: string | null;
  email?: string | null;
  phone?: string | null;
};

export const listAgendaMeetings = async (status?: string): Promise<ScheduledMeeting[]> => {
  const q = status ? `?status=${encodeURIComponent(status)}` : '';
  const response = await fetch(`${API_URL}/agenda/meetings${q}`, { headers: getAuthHeaders() });
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) throw new Error('Error al listar reuniones');
  return response.json();
};

export const createAgendaMeeting = async (payload: {
  client_id: number;
  title: string;
  agenda?: string;
  starts_at: string;
  duration_minutes?: number;
  notify_minutes_before?: number;
  client_email?: string;
  client_phone?: string;
}): Promise<ScheduledMeeting> => {
  const response = await fetch(`${API_URL}/agenda/meetings`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al crear reunión');
  }
  return response.json();
};

export const cancelAgendaMeeting = async (id: number) => {
  const response = await fetch(`${API_URL}/agenda/meetings/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) throw new Error('Error al cancelar reunión');
  return response.json();
};

export const shareAgendaMeeting = async (id: number): Promise<MeetingShare> => {
  const response = await fetch(`${API_URL}/agenda/meetings/${id}/share`, { headers: getAuthHeaders() });
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) throw new Error('Error al obtener datos de compartir');
  return response.json();
};

export const notifyAgendaMeeting = async (id: number) => {
  const response = await fetch(`${API_URL}/agenda/meetings/${id}/notify`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) throw new Error('Error al notificar');
  return response.json();
};

export const listAgendaRecordings = async (status?: string): Promise<ScheduledRecording[]> => {
  const q = status ? `?status=${encodeURIComponent(status)}` : '';
  const response = await fetch(`${API_URL}/agenda/recordings${q}`, { headers: getAuthHeaders() });
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) throw new Error('Error al listar grabaciones');
  return response.json();
};

export const listAgendaRecordingLibrary = async (): Promise<ScheduledRecording[]> => {
  const response = await fetch(`${API_URL}/agenda/recordings/library`, { headers: getAuthHeaders() });
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) throw new Error('Error al cargar biblioteca de videos');
  return response.json();
};

export const createAgendaRecording = async (payload: {
  client_id: number;
  device_id: number;
  technician_id: number;
  scheduled_at: string;
  duration_minutes?: number;
  notes?: string;
}): Promise<ScheduledRecording> => {
  const response = await fetch(`${API_URL}/agenda/recordings`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al programar grabación');
  }
  return response.json();
};

export const cancelAgendaRecording = async (id: number) => {
  const response = await fetch(`${API_URL}/agenda/recordings/${id}/cancel`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (response.status === 401) throw new Error('Sesión Expirada');
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al cancelar grabación');
  }
  return response.json();
};

export const agendaRecordingDownloadUrl = (id: number) =>
  `${API_URL}/agenda/recordings/${id}/download`;

// ==========================================
// APOLLOIA BILLING
// ==========================================
export const getIaBillingMonth = async (desde: string, hasta: string, serial?: string) => {
    const params = new URLSearchParams({ desde, hasta });
    if (serial) params.set('serial', serial);
    const response = await fetch(`${API_URL}/ia/billing-month?${params.toString()}`, {
        headers: getAuthHeaders(),
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    if (!response.ok) throw new Error('Error al obtener consumo ApolloIA');
    return await response.json();
};
