# Arquitectura — Control remoto ApolloSupport

## Diagrama de componentes

```mermaid
flowchart TB
  subgraph browser [Portal técnico]
    UI[App.tsx]
    Canvas[Canvas WebP]
    WC[WebCodecs H.264]
  end

  subgraph server [Backend FastAPI]
    M[ConnectionManager]
    DS[device_sessions por session_id]
  end

  subgraph gescom [SERVIDOR-GESCOM]
    SVC[ApolloCentinela Service S0]
    COMP[ApolloCentinela.exe Sesión N]
    GDI[Captura GDI]
    FF[ffmpeg opcional]
  end

  UI -->|WS viewer| M
  M -->|video_frame / hq_chunk| UI
  COMP -->|WS agente session_id=N| M
  SVC -->|spawn / switch| COMP
  COMP --> GDI
  COMP --> FF
  Canvas --> UI
  WC --> UI
```

## Secuencia: conectar visor

```mermaid
sequenceDiagram
  participant T as Técnico
  participant P as Portal
  participant B as Backend
  participant C as Companion

  T->>P: Abrir control remoto
  P->>B: WS viewer
  B->>C: technician_joined
  C->>C: FORCE_NEXT_FRAME=True
  C->>B: video_frame WebP
  B->>P: frame
  P->>P: refresh_frame
  Note over P: Espera 2s si HD ON
  P->>B: start_hq
  C->>B: H.264 chunks
  alt HD falla 5s
    P->>P: stop_hq fallback WebP
  end
```

## Secuencia: cambio de sesión

```mermaid
sequenceDiagram
  participant P as Portal
  participant B as Backend
  participant S as Service
  participant C as Companion

  P->>B: switch_session id=2
  B->>C: switch_session
  C->>S: switch_session.txt
  S->>S: normalize + suitable?
  S->>S: Terminate companion viejo
  S->>C: spawn sesión 2
  C->>B: WS reconnect session_id=2
  B->>P: session_switched
```

## Estados del companion (servicio)

| Estado | `_pinned_session` | Comportamiento monitor |
|--------|-------------------|-------------------------|
| Auto | `None` | `resolve_companion_session_id()` → consola o RDP con token |
| Tras switch UI | `N` | Mantener N si `session_suitable` |
| Disc pinned | desanclado | Warning + fallback a sesión apta |

## Tipos de mensaje WS relevantes

| Tipo | Dirección | Uso |
|------|-----------|-----|
| `video_frame` | Agente → Viewer | WebP base64, opcional `delta` |
| `hq_chunk` | Agente → Viewer | Binario H.264 |
| `technician_joined` | Backend → Agente | Inicia captura / frame fresco |
| `refresh_frame` | Viewer → Agente | `FORCE_NEXT_FRAME` |
| `start_hq` / `stop_hq` | Viewer ↔ Agente | Modo HD |
| `switch_session` | Viewer → Agente → Service | Reinicio companion |
| `session_list` | Agente → Viewer | Lista `query session` |

## Rutas de archivos en producción

| Ruta | Contenido |
|------|-----------|
| `C:\Program Files (x86)\Apollo Centinela\` | Exes + ffmpeg |
| `C:\ProgramData\ApolloSupport\service.log` | Servicio |
| `C:\ProgramData\ApolloSupport\centinela.log` | Companion |
| `C:\ProgramData\ApolloSupport\switch_session.txt` | Señal switch (efímero) |
| Portal htdocs | `frontend/dist/` |

## Puntos de extensión seguros

1. **Calidad WebP:** `set_stream_params` (`max_width`, `webp_still`, `webp_motion`).
2. **HD:** parámetros ffmpeg en `hq_stream_loop`.
3. **Sesiones:** mejorar parser `get_windows_sessions()` (locale, columnas).
4. **Telemetría:** FPS y `session_id` en bitácora ya parcialmente en logs.

---

Ver runbook: `CONTROL_REMOTO_RUNBOOK.md`.
