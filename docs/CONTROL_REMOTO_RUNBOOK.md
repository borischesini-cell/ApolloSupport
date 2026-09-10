# Control remoto ApolloSupport — Runbook operativo

Documento para **poner en producción hoy** y diagnosticar sin repetir errores. Complementa `CONTROL_REMOTO_LECCIONES.md` y `CONTROL_REMOTO_ARQUITECTURA.md`.

**Versión de referencia en repo:** `3.2.2` (agente, servicio, portal, `backend/updates/version.json`).

---

## 1. Arquitectura en 30 segundos

| Componente | Rol |
|------------|-----|
| **ApolloCentinela Service** (`centinela_svc.py`) | Sesión 0 / SYSTEM. Monitor: lanza y relanza `ApolloCentinela.exe` en la sesión Windows correcta. |
| **ApolloCentinela.exe** (`centinela.py`) | Companion en sesión de usuario/consola. WebSocket al backend, captura GDI, WebP + opcional H.264. |
| **Backend** (`backend/main.py`) | Enruta frames por `session_id`, reenvía comandos (`switch_session`, `start_hq`). |
| **Portal** (`frontend/`) | Visor: canvas WebP + WebCodecs H.264 (HD). |

Flujo de vídeo estándar: **Companion → WS `video_frame` (WebP base64) → Backend → WS viewer → canvas**.

HD: **`start_hq`** → ffmpeg H.264 → chunks binarios → WebCodecs en el navegador.

---

## 2. Checklist deploy (orden obligatorio)

### A. Desarrollo / repo

```bat
cd P:\ApolloSupport
python scripts\verify_release.py
build_frontend.bat
```

- `verify_release.py` debe terminar con **0 errores**.
- Compilar MSI/agente con el mismo código que `centinela.py` / `centinela_svc.py`.

### B. Servidor remoto (ej. SERVIDOR-GESCOM)

1. Copiar instalador o binarios a `C:\Program Files (x86)\Apollo Centinela\`:
   - `ApolloCentinela.exe`
   - `ApolloCentinelaService.exe` (o servicio empaquetado)
   - **`ffmpeg.exe` en la misma carpeta** (obligatorio para HD)
2. Reiniciar servicio:
   ```powershell
   Restart-Service ApolloCentinela
   ```
3. Verificar logs (`C:\ProgramData\ApolloSupport\`):
   - `service.log` — companion lanzado en sesión **activa** (no solo 50 Disc)
   - `centinela.log` — `[VIDEO] Primer frame enviado`

### C. Portal (support.ultimate.net.ar)

1. Copiar **todo** `frontend/dist/` al htdocs del portal.
2. Verificar en navegador:
   - `https://support.ultimate.net.ar/version.txt` → `version=3.2.2`
   - Título pestaña / badge **v3.2.2** junto al ID del equipo
3. Hard refresh si el SW cachea: Ctrl+Shift+R o banner de nueva versión.

### D. Prueba funcional mínima (5 min)

| Paso | Esperado |
|------|----------|
| Conectar a equipo | En &lt; 3 s imagen WebP (aunque HD esté ON) |
| Sin tocar sesiones | Sesión con ● **actual** = la que captura el companion |
| Desactivar HD | FPS &gt; 0, imagen estable |
| Activar HD | Tras ~2 s puede mejorar calidad; si negro 5 s → auto fallback estándar |
| Cambiar a **Consola** o RDP **Activa** | Imagen coherente con el escritorio real |
| No elegir RDP **Disc** | UI bloquea o servicio redirige a sesión apta |

---

## 3. Tabla de síntomas → causa → acción

| Síntoma | Causa habitual | Acción |
|---------|----------------|--------|
| Pantalla negra, HD ON, **Espera** 0 FPS | HD sin ffmpeg o WebCodecs; antes WebP cortado con HQ | Desactivar HD; verificar `ffmpeg.exe`; desplegar agente con WebP+HQ en paralelo |
| Cuadraditos sobre negro | `USE_DIRTY_RECT=True` sin frame base | Repo: `USE_DIRTY_RECT=False`; frontend con canvas base negro |
| Miniatura OK, pantalla grande mal | Companion en **otra sesión** | Elegir sesión ● actual; ver `Companion lanzado en sesion N` en service.log |
| Switch a sesión **50** + error 1008 | RDP **desconectada** | Usar Consola o RDP activa; no forzar Disc |
| `[SWITCH] -> 65536` + OverflowError | ID sesión inválido | Actualizar servicio con `normalize_windows_session_id` |
| Relanzamiento cada 2 s | Mutex global / duplicados | Mutex por sesión `Global\ApolloCentinelaCompanion_S{id}`; un solo monitor de spawn |
| `InvalidStateError` WebCodecs | Decoder cerrado en reconnect | Actualizar frontend (`h264WebCodecs.ts` + fallback 5 s) |
| Versión UI distinta (ej. v5.2.2) | Portal o caché viejos | Alinear `version.txt` y `frontend/src/version.ts`; bump con `bump.py` |

---

## 4. Logs que importan

### service.log

```
Companion lanzado en sesion 6 (PID ...)
[SWITCH] Cambio de sesion solicitado -> 50
[SWITCH] Sesion 50 no apta ... redirigiendo a 6
Token obtenido desde winlogon.exe en sesion 50   ← captura suele ser mala si Disc
```

### centinela.log

```
[VIDEO] Loop de video iniciado
[VIDEO] Primer frame enviado al servidor exitosamente
[HQ] Modo Alto Rendimiento activado
```

Si hay **Primer frame** pero el portal negro → problema frontend/backend/caché, no captura.

### Consola navegador (F12)

- `[FRONTEND-HQ] Sin video HD en 5s — fallback a calidad estándar` → comportamiento esperado si ffmpeg falla.

---

## 5. Sesiones Windows — reglas de oro

1. **Un companion por sesión** (mutex `Global\ApolloCentinelaCompanion_S{session_id}`).
2. **Captura útil** solo si:
   - Sesión con **usuario logueado** (token WTS), o
   - **Consola** activa, o
   - Login pendiente (winlogon) con `--type-credentials`.
3. **No usar** sesiones `Disc` / desconectadas para ver el escritorio del usuario.
4. IDs válidos: **1–65535**. Nunca `65536` ni `0xFFFFFFFF` como destino de switch.

Comando manual en el servidor:

```bat
query session
```

---

## 6. Modo HD vs estándar

| Modo | Cuándo usar hoy |
|------|------------------|
| **Estándar (WebP)** | Diagnóstico, RDP lento, si HD falla |
| **HD (H.264)** | Solo con `ffmpeg.exe` presente y tras confirmar WebP OK |

Comportamiento actual del portal (post-fix):

1. Al conectar: `refresh_frame` (WebP).
2. A los 2 s: `start_hq` si HD guardado en localStorage.
3. A los 5 s sin FPS HD: apaga HD y vuelve a WebP.

---

## 7. Archivos críticos (no romper)

| Archivo | Qué controla |
|---------|----------------|
| `agent/centinela.py` | `USE_DIRTY_RECT`, loop vídeo WebP/HQ, `FORCE_NEXT_FRAME` |
| `agent/centinela_svc.py` | Spawn por sesión, switch, `normalize_windows_session_id` |
| `frontend/src/App.tsx` | Canvas, HD fallback, picker sesiones |
| `frontend/src/h264WebCodecs.ts` | Decoder H.264 |
| `backend/main.py` | `device_sessions`, `handle_session_switch` |

**No ejecutar** `patch.py` en producción (reactiva dirty rect).

---

## 8. Bump de versión unificado

Editar `bump.py` → `NEW_VERSION` y ejecutar, o alinear manualmente:

- `agent/centinela.py` → `CLIENT_VERSION`
- `agent/centinela_svc.py` → `__version__`
- `frontend/package.json`, `frontend/src/version.ts`
- `backend/updates/version.json`
- `version.txt` en el servidor web (si existe aparte)

Luego `build_frontend.bat` y redeploy completo.

---

## 9. Pruebas automatizadas / manuales

### Automático (repo)

```bat
python scripts\verify_release.py
cd frontend && npm run build
```

### Manual en servidor

```powershell
Get-Service ApolloCentinela
Get-Content C:\ProgramData\ApolloSupport\service.log -Tail 40
Get-Content C:\ProgramData\ApolloSupport\centinela.log -Tail 40
Test-Path "C:\Program Files (x86)\Apollo Centinela\ffmpeg.exe"
query session
```

### Manual en portal

1. Incógnito → login → conectar GESCOM.
2. Confirmar imagen &lt; 5 s sin HD.
3. HD ON 10 s → imagen o fallback automático.
4. Cambio a Consola → imagen de consola.
5. Intentar sesión Disc → mensaje de error en UI.

### Tests backend (opcional, requiere API local)

- `backend/test_viewer.py`, `test_viewer_connection.py` — con servidor levantado.

---

## 10. Contacto rápido con el estado

Pregunta única: **¿En qué sesión está el companion y llegan frames WebP?**

```text
service.log  → "Companion lanzado en sesion N"
centinela.log → "[VIDEO] Primer frame enviado"
portal       → FPS > 0 sin HD
```

Si las tres no coinciden, arreglar sesión antes de tocar calidad o codecs.

---

*Última revisión: 2026-06-03 — incluye fixes pantalla negra HD, dirty rect off, sesión 65536/50 Disc.*
