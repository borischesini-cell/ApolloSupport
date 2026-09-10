# ApolloSupport v3.2.3 — Pantalla negra / switch de sesión

**Fecha:** 2026-06-03

## Qué corrige

- **Servicio:** no mata el companion hasta que el spawn en la sesión destino **funciona** (evita quedar sin imagen si falla el switch).
- **Backend:** tras ~12 s sin sesión destino, **vuelve a reenviar frames** de la sesión activa; al abrir el visor se limpia un switch pendiente viejo.
- **Frontend:** HD **apagado por defecto**; FPS se actualiza al recibir frames por WebSocket (deja de quedar en "Espera" con imagen llegando).

## Build (en máquina de desarrollo)

### 1. Portal + backend

```bat
build_frontend.bat
```

O:

```powershell
cd p:\ApolloSupport\frontend
npm run build
```

Desplegar `frontend\dist\` y `backend\main.py` + `backend\updates\version.json`:

```powershell
.\deploy\deploy_prod.ps1 -Server \\192.168.10.220
```

(Reinicia `ApolloBackend` en el servidor.)

Verificar en el navegador:

- https://support.ultimate.net.ar/version.txt → `version=3.2.3`
- Ctrl+Shift+R en el visor

### 2. Agente en SERVIDOR-GESCOM (y clientes afectados)

```bat
cd p:\ApolloSupport\agent
build_all_and_installer.bat
```

Instaladores en `agent\installer_output\`:

- `ApolloSetup_v3.2.3.exe` (auto arquitectura)
- `ApolloSetup_v3.2.3_x64.exe` / `_x86.exe`

**En el servidor remoto (como administrador):**

1. Ejecutar el instalador correcto (x64 en SERVIDOR-GESCOM si es 64 bits).
2. Borrar si existe: `C:\ProgramData\ApolloSupport\switch_session.txt`
3. Reiniciar servicio **ApolloCentinela** (Servicios de Windows).
4. Conectar desde el portal; **HD desactivado** la primera vez (activar solo si hace falta).

### 3. Comprobar que quedó bien

| Dónde | Qué buscar |
|-------|------------|
| `service.log` | `Apollo Centinela Service v3.2.3 iniciando` |
| `centinela.log` | `Apollo Centinela v3.2.3` y `[VIDEO] Primer frame enviado` |
| Portal | Badge **v3.2.3**, imagen visible sin HD |
| Tras switch fallido | Imagen sigue en sesión actual en &lt;15 s |

## Recuperación rápida (sin reinstalar aún)

1. Borrar `switch_session.txt`
2. Reiniciar servicio ApolloCentinela
3. En el navegador: apagar HD, Ctrl+F5, reconectar

## Archivos de versión alineados

- `VERSION`, `bump.py` (3.2.3)
- `agent/centinela.py`, `agent/centinela_svc.py`
- `backend/main.py`, `backend/updates/version.json`
- `frontend/src/version.ts`, `vite.config.ts`, `package.json`, `index.html`
- Instaladores `.iss`
