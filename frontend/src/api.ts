export const API_URL = import.meta.env.VITE_API_URL || 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8001/api'
    : 'https://support.ultimate.net.ar/api');

// URL base para WebSockets (http→ws, https→wss automático)
export const WS_BASE_URL = API_URL.replace(/^http/, 'ws');

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
export const REMOTE_STREAM_WORKABLE_FPS = 8;
/** Holgura para volver a subir calidad en modo automático sin quedar en el límite. */
export const REMOTE_STREAM_COMFORTABLE_FPS = 12;

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
  /** Se llama al cerrar el socket (antes de reintentar). Reactiva polling HTTP si el WS no entrega. */
  onClose?: () => void;
}


export function useViewerWebSocket({ deviceId, enabled, onFrame, onQuality, onMessage, onClose }: ViewerWsOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const backoffRef = useRef<number>(1000);
  const failCountRef = useRef<number>(0);
  const frameTimestampsRef = useRef<number[]>([]);
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
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return; }
      backoffRef.current = 1000;   // Resetear backoff en conexión exitosa
      failCountRef.current = 0;

      // Ping periódico cada 25s para mantener viva la conexión
      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 25000);
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
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
          const fps = Math.round(frameTimestampsRef.current.length / 2);

          onQuality?.(fps, connectionQualityFromFps(fps));
        } else if (data.type === 'ping') {
          /* keepalive del servidor */
        } else if (onMessage) {
          // Otros mensajes del agente (session_list, login_result, etc.)
          onMessage(data as Record<string, unknown>);
        }
        // ping/pong manejado por servidor, no necesita acción en cliente
      } catch (_) {}
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

      const cap = Math.min(backoffRef.current, 30000);
      const delay = cap + Math.floor(Math.random() * 600);
      backoffRef.current = Math.min(backoffRef.current * 2, 30000);

      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current && enabled) connect();
      }, delay);
    };
  }, [deviceId, enabled, onFrame, onQuality, onMessage, onClose, cleanup]);

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


const getAuthHeaders = () => ({
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
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
};

export const updateClient = async (clientId: number, data: any) => {
    const response = await fetch(`${API_URL}/clients/${clientId}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(data)
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return await response.json();
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
    if (!response.ok) throw new Error('Error al sincronizar clientes con la base de datos DBF');
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

export const assignCentinelaLicense = async (deviceId: number, clientId: number) => {
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/assign/${clientId}`, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (response.status === 401) throw new Error('Sesión Expirada');
    return response.ok;
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
}

export function useHqViewerWebSocket({ deviceId, enabled, onChunk, onStateChange }: HqViewerOptions) {
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

  const connect = useCallback(() => {
    if (!mountedRef.current || !deviceId || !enabled) return;
    cleanup();

    const token = localStorage.getItem('token');
    if (!token) return;

    const url = `${WS_BASE_URL}/ws/viewer/${deviceId}/hq?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';   // recibir chunks como ArrayBuffer, no Blob
    wsRef.current = ws;
    onStateChange?.('connecting');

    let firstChunkReceived = false;
    let noDataTimer: ReturnType<typeof setTimeout> | null = null;

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return; }
      backoffRef.current = 1000;
      // NO ponemos 'open' aqui — esperamos el primer chunk real.
      // Mientras hqState = 'connecting', la imagen normal sigue visible.
      // Timeout: si en 30s no llegan datos, el agente no soporta HQ → cerrar.
      noDataTimer = setTimeout(() => {
        if (!firstChunkReceived && ws.readyState === WebSocket.OPEN) {
          console.warn('[HQ] Sin datos en 30s — agente no soporta HQ o backend no reiniciado');
          ws.close();
        }
      }, 30000);
      // Ping cada 25s para mantener viva la conexión
      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 25000);
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      if (event.data instanceof ArrayBuffer && event.data.byteLength > 0) {
        if (!firstChunkReceived) {
          firstChunkReceived = true;
          if (noDataTimer) { clearTimeout(noDataTimer); noDataTimer = null; }
          onStateChange?.('open');  // ← ahora si: hay datos reales
        }
        onChunk(event.data);
      }
      // Ignorar mensajes de texto (ping/pong del servidor)
    };

    ws.onerror = () => { /* handled in onclose */ };

    ws.onclose = () => {
      if (pingTimerRef.current) { clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
      onStateChange?.('closed');
      if (!mountedRef.current || !enabled) return;
      const cap = Math.min(backoffRef.current, 30000);
      const delay = cap + Math.floor(Math.random() * 600);
      backoffRef.current = Math.min(backoffRef.current * 2, 30000);
      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current && enabled) connect();
      }, delay);
    };
  }, [deviceId, enabled, onChunk, onStateChange, cleanup]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled && deviceId) connect();
    else cleanup();
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [deviceId, enabled, connect, cleanup]);
}

