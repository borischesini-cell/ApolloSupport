# Lecciones aprendidas — Control remoto ApolloSupport

Registro de errores reales y cómo **no repetirlos**. Usar como checklist en code review y deploy.

---

## 1. Pantalla negra con HD “conectado”

**Error:** Con `start_hq`, el loop WebSocket hacía `continue` y **no enviaba WebP**. Si ffmpeg fallaba o el decoder no abría, el técnico veía negro y “Espera”.

**Regla:** Nunca cortar el único stream que funciona (WebP) hasta que H.264 esté demostrado en el cliente.

**Implementación correcta:**
- Agente: WebP sigue en el loop aunque `HQ_MODE_ACTIVE`.
- Portal: `refresh_frame` al conectar; `start_hq` retrasado 2 s; fallback a estándar a los 5 s sin FPS.

---

## 2. Cuadraditos (parches sueltos)

**Error:** `USE_DIRTY_RECT=True` enviaba solo regiones cambiadas. El canvas del navegador arrancaba vacío → parches flotando.

**Regla:** Dirty rect solo si el cliente **siempre** tiene un framebuffer completo (frame key inicial + `fw`/`fh`).

**Implementación correcta:**
- `USE_DIRTY_RECT = False` en producción hasta tener keyframe garantizado.
- Frontend: si llega delta, inicializar canvas `fw×fh` en negro antes de pintar.
- `FORCE_NEXT_FRAME=True` en connect / `refresh_frame` → agente manda frame completo.

---

## 3. Sesión Windows equivocada

**Error:** Companion en sesión **50 Disc** (WTS 1008) mientras el técnico creía ver la consola. Miniatura de otra sesión, pantalla negra o login.

**Regla:** La sesión del companion = la sesión que se captura. El picker debe mostrar ● **actual** y no permitir Disc para “ver escritorio”.

**Implementación correcta:**
- `session_suitable_for_companion()` — False para Disc sin login.
- Switch a Disc → redirigir o rechazar en UI.
- `_pinned_session` tras switch manual para que el monitor no vuelva a otra sesión.

---

## 4. session_id 65536 y OverflowError

**Error:** Switch a `65536` (valor inválido / mal parseado de `query session`) → APIs WTS con tipos incorrectos → `int too long to convert`.

**Regla:** Validar `1 <= session_id <= 65535` y existencia en `WTSEnumerateSessions` antes de spawn.

**Implementación:** `normalize_windows_session_id()` en `centinela_svc.py` + filtro en `get_windows_sessions()`.

---

## 5. Mutex global del companion

**Error:** `Global\ApolloCentinelaCompanion` único → solo una sesión podía tener companion; las demás en bucle de relanzamiento ~2 s.

**Regla:** Mutex **por sesión**: `Global\ApolloCentinelaCompanion_S{session_id}`.

---

## 6. Doble spawn al boot

**Error:** Servicio lanzaba companion al iniciar **y** el monitor lo relanzaba → PIDs duplicados, kills en cadena.

**Regla:** **Un solo dueño** del spawn: `companion_monitor()` únicamente.

---

## 7. WebCodecs `InvalidStateError`

**Error:** Chunks H.264 llegando tras `codec.close()` en reconnect.

**Regla:** Flag `closed` en el player; no llamar `decode` si cerrado; destruir decoder en switch de sesión y al fallback HD.

---

## 8. Versiones desalineadas

**Error:** Portal v5.x en pantalla, repo 3.2.2 → técnicos y soporte no saben qué está desplegado.

**Regla:** Un solo bump (`bump.py` o lista en RUNBOOK) + verificar `version.txt` en producción.

---

## 9. ffmpeg olvidado

**Error:** HD ON sin `ffmpeg.exe` junto al exe → sin chunks H.264, antes sin WebP → negro total.

**Regla:** Instalador debe copiar `ffmpeg.exe`; runbook incluye `Test-Path`.

---

## 10. Scripts peligrosos en el repo

**Error:** `patch.py` pone `USE_DIRTY_RECT = True`.

**Regla:** No ejecutar patches sueltos en producción; solo MSI/build oficial tras `verify_release.py`.

---

## Anti-patrones en PR / deploy

| No hacer | Hacer en su lugar |
|----------|------------------|
| `continue` en loop WebP cuando HQ | WebP paralelo o HQ demostrado |
| Dirty rect sin keyframe | Frame completo cada N segundos o rect off |
| Switch a sesión Disc “para ver” | Consola o RDP Active |
| Confiar en `query session` sin validar ID | `normalize_windows_session_id` |
| Subir solo `ApolloCentinela.exe` sin servicio | Par agente + servicio + dist portal |
| Probar solo con HD ON | Probar WebP primero, luego HD |

---

## 11. Ctrl+Alt+Sup sin video de login

**Error:** Tras `SendSAS`, el servicio relanzaba el companion con `--type-credentials`. Ese modo **inyecta password y hace `sys.exit(0)`** sin abrir WS ni captura → el técnico no ve la pantalla de logueo de Windows.

**Regla:** Separar roles:
- `--type-credentials` = inyección corta de usuario/clave (sale).
- `--winlogon --headless` = companion vivo en `winsta0\Winlogon` para **ver y teclear** en el login.

**Implementación:** `_force_relaunch_winlogon` spawnea `--winlogon --headless`; `spawn_in_user_session` fuerza desktop Winlogon con ese flag.

---

## 12. Corrupción por patches sueltos

**Error:** `patch_panic_release.py` dejó `.start()pt Exception:` en `centinela.py` → **SyntaxError**, el agente no compilaba.

**Regla:** No aplicar `patch_*.py` en producción; cambios solo en el fuente + build oficial. Tras cualquier patch, `python -m py_compile agent/centinela.py`.

---

## Evolución futura (cuando el día a día esté estable)

1. Dirty rect con keyframe cada 30 s + deltas entre medias.
2. Mostrar en UI: “Companion sesión #N” junto al picker.
3. Test de integración: mock `session_list` + primer frame WebP.
4. Health endpoint en companion: `{session, fps, hq_ok, ffmpeg_ok}`.

---

*Mantener este archivo actualizado cuando un incidente nuevo tenga causa raíz clara.*
