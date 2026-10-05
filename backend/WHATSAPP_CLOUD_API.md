# Integración WhatsApp Cloud API (Meta) — ApolloSupport

## Por qué

El puente viejo (`X:\ERPS_Comunes\WapEngine\`) usa **neonize**, un cliente no oficial de
WhatsApp Web. Meta lo detecta y **banea el número**: es inaceptable para una línea que se
usa con clientes. Se reemplaza por la **WhatsApp Business Platform / Cloud API oficial**,
hablando directo contra `graph.facebook.com` (sin BSP de terceros: se quiere control
absoluto de la integración y del panel).

La **verificación de negocio de Meta fue aprobada el 2026-09-28**. Antes rebotaba porque
la factura de Claro titularizaba la línea 3446-675303 a "CHESINI, BORIS" y no a
"GRUPO MASTER SRL"; se resolvió cambiando la titularidad en Claro.

## Modelo de negocio

* **Una línea dada de alta por cliente.** Cada fila de `whatsapp_accounts` es una WABA +
  `phone_number_id` de UN cliente (`client_id` obligatorio).
* Contadores de consumo **separados por cuenta** (`period_start`, `messages_sent_this_month`,
  `monthly_message_quota`) y **cierre mensual facturable** (`whatsapp_billing_periods`).
* El costo de Meta se traslada con un recargo (`WA_MARKUP_PCT`, 30 % por defecto).

## Archivos

| Archivo | Rol |
|---|---|
| `backend/whatsapp.py` | Módulo completo: Graph client, webhook, plantillas, envío, facturación, canal ERP, worker. Router `/api/whatsapp` montado por `setup_whatsapp(app, get_current_user, gesacti_key)`. |
| `backend/models.py` | 6 modelos: `WhatsAppAccount`, `WhatsAppTemplate`, `WhatsAppConversation`, `WhatsAppMessage`, `WhatsAppWebhookEvent`, `WhatsAppBillingPeriod`. |
| `backend/schemas.py` | Esquemas `WhatsApp*` de entrada/salida. |
| `backend/main.py` | `setup_whatsapp(app, get_current_user, GESACTI_SYNC_KEY)` + `ensure_erp_columns()` + task `periodic_whatsapp_worker` en `startup_event`. |
| `backend/.env.example` | Variables del módulo. |
| `backend/_wa_recheck.py` | Validador offline (SQLite en memoria, Graph simulado, sin red). 6 secciones. |
| `X:\ERPS_Comunes\TWhatsAppCloud.prg` | **Cliente del ERP** (xHarbour). Clase `TWhatsAppCloud`: bootstrap, envío de PDF y consulta de consumo contra estas rutas `/erp/*`. Reemplaza a neonize sin borrarlo. Al pie define el dispatcher `WapCloudSend()` que usa el hook. |
| `X:\ERP_Facturac\Source\FEConsulta.prg` | **Hook real**. En `GenePdfyWapNativoFac()` (líneas ~1984-2046) se **agrega** un intento por la API oficial antes del selector de siempre; el bridge queda intacto dentro del `If !lNube`. Linkea `TWhatsAppCloud.prg` sólo `GesFactu.xpj`, por eso la llamada es `DYNAMIC`. |
| `X:\ERPS_Comunes\Procedim.prg` | Gate de configuración: `IsCloudWap()` / `IsNativeWap()` leen `..\GescomPdf.ini` (`[WhatsApp] CloudUrl`). También declara `DYNAMIC WapCloudSend` a nivel de archivo, que sólo alcanza a este módulo. |

Las tablas se crean solas al levantar el backend (`Base.metadata.create_all`, main.py:167).
**No hay migraciones de WhatsApp**: verificación hecha contra la DB real
(192.168.11.223/apollosupport_db) el 2026-09-28 — 6 tablas presentes, columnas de modelo
y de DB idénticas.

## Configuración obligatoria (.env)

```
APOLLO_SECRET_KEY=...            # sin esto NO se pueden cifrar los tokens (Fernet)
WA_APP_SECRET=...                # Meta: App review → Basic → App secret
WA_WEBHOOK_VERIFY_TOKEN=...      # string propio del challenge GET
GESACTI_SYNC_KEY=...             # protege /erp/bootstrap: la misma de /api/clients/gesacti
```

Opcionales con default razonable: `WA_GRAPH_VERSION` (v23.0), `WA_GRAPH_BASE`,
`WA_GRAPH_TIMEOUT` (30), `WA_DEFAULT_COUNTRY_CODE` (54), `WA_RATE_UTILITY` /
`WA_RATE_MARKETING` / `WA_RATE_AUTHENTICATION`, `WA_MARKUP_PCT` (30),
`WA_ALLOW_UNSIGNED_WEBHOOK` (0 — sólo pruebas locales).

Del canal ERP (todos tienen default, se listan para poder afinarlos):
`WA_ERP_MAX_SKEW_SECONDS` (300 — tolerancia de reloj del puesto),
`WA_ERP_MAX_PDF_MB` (8), `WA_ERP_NONCE_TTL_SECONDS` (900),
`WA_ERP_INVOICE_TEMPLATE` (`factura_apollo`), `WA_ERP_INVOICE_LANGUAGE` (`es`).

El `access_token` de cada cuenta se guarda **cifrado con Fernet derivado de
`APOLLO_SECRET_KEY`** y nunca se devuelve en una respuesta. Si esa clave cambia, los
tokens existentes quedan indecifracibles (error explícito en `decrypt_secret`).
`P:\ApolloSupport\backend\.env` **todavía no tiene `APOLLO_SECRET_KEY`**: hay que
agregarla antes de dar de alta la primera cuenta.

## Alta de una línea (pasos en Meta)

1. Meta for Developers → App de tipo **Business** → agregar producto **WhatsApp**.
2. Business Manager del cliente → **Usuarios del sistema** → crear System User y generar
   su token, con permisos *WhatsApp Business App Management* y *WhatsApp Business
   Messaging*.
3. POST `/api/whatsapp/accounts` (`waba_id`, `phone_number_id`, `access_token`,
   `allowed_categories`). El token se cifra al guardar.
4. POST `/api/whatsapp/accounts/{id}/test` → verifica que Graph responde y toma el
   `display_phone_number` / `verified_name`.
5. POST `/api/whatsapp/accounts/{id}/register` → `POST /{phone_number_id}/register` con
   el `pin` (2FA) si el número lo pide.
6. Webhook: URL `https://<host>/api/whatsapp/webhook`, token = `WA_WEBHOOK_VERIFY_TOKEN`,
   campos suscriptos: `messages`, `message_template_status_update`,
   `phone_number_quality_update`.
7. Plantillas: POST `/api/whatsapp/accounts/{id}/templates` (o `?push_to_meta=0` si ya
   existen en WhatsApp Manager) y `GET .../templates` para leer el estado real.
8. Canal ERP: `PUT /api/whatsapp/accounts/{id}` con `erp_send_enabled = true` y, si el cliente
   no usa `factura_apollo`, su `erp_invoice_template` / `erp_invoice_language`. Después
   `POST /api/whatsapp/erp/bootstrap` desde el puesto (o `?rotate=true` para emitir la clave) y
   `POST /api/whatsapp/erp/clients/{codigo}/rotate-key` si se filtró.

## Reglas de facturación implementadas

* **Ventana de 24 h contada desde el mensaje del CLIENTE.** `customer_window_open()` exige
  `last_inbound_at` vigente: una conversación iniciada por nosotros (plantilla) **no**
  habilita texto libre, porque Meta lo rechaza con 131026 y el mensaje nunca sale.
* Cobranza **por mensaje entregado** (modelo `PER_MESSAGE`, vigente desde 07/2025):
  * `service` (respuesta dentro de la ventana del cliente) = **sin cargo**.
  * `utility` / `authentication` = gratis si se envían **dentro** de esa ventana,
    facturables fuera de ella.
  * `marketing` = siempre facturable.
* `perform_send` hace la **estimación**; el webhook de `statuses[].pricing`
  (`billable`, `category`, `conversation.category`) es quien **confirma** el cargo real y
  pisa `cost_amount`.
* `_billing_row` contabiliza `delivered` + `read` (el estado se pisa a `read` y si no,
  quedaría afuera) **sólo con `billable = True`**, para no sobrefacturar al cliente.
* `POST /api/whatsapp/billing/close` escribe el período en `whatsapp_billing_periods`
  (único por `account_id + period_start`) y `GET /api/whatsapp/billing/report` muestra la
  serie por cliente.

> Las tarifas en `DEFAULT_RATES` son USD de referencia: **confirmar la tarifa de Argentina
> en Meta Billing** antes de facturar. Se puede pisar por cuenta con `rate_overrides`.

## Rutas montadas (26)

```
GET|POST /api/whatsapp/webhook                       (sin JWT: challenge + firma X-Hub-Signature-256)
GET|POST /api/whatsapp/accounts    GET|PUT|DELETE /api/whatsapp/accounts/{id}
POST /api/whatsapp/accounts/{id}/test | /register
GET|POST /api/whatsapp/accounts/{id}/templates | POST .../templates/sync
DELETE /api/whatsapp/templates/{id}
POST /api/whatsapp/accounts/{id}/send
GET  /api/whatsapp/accounts/{id}/messages | /conversations | /billing
GET  /api/whatsapp/billing/report | POST /api/whatsapp/billing/close
GET  /api/whatsapp/billing/periods | PUT /api/whatsapp/billing/periods/{id}
POST /api/whatsapp/erp/bootstrap                     (X-GesActi-Key, sin JWT)
POST /api/whatsapp/erp/documents                     (HMAC por cliente)
GET  /api/whatsapp/erp/usage                         (HMAC por cliente)
GET  /api/whatsapp/erp/clients/{codigo}/usage        (admin)
POST /api/whatsapp/erp/clients/{codigo}/rotate-key   (admin)
```

Lectura: cualquier usuario autenticado. Escritura y configuración: rol **admin**
(`require_admin`). Las `/erp/*` no usan JWT: ver la sección siguiente.

## Canal ERP: enviar facturas desde el puesto

El puesto de ApolloGesCom (`X:\ERPS_Comunes\TWhatsAppCloud.prg`, clase `TWhatsAppCloud`)
nunca habla con Meta. **Soporte es el proxy**: recibe el PDF en base64, lo sube a Graph con
el token de la cuenta del cliente (que nunca baja al puesto) y deja la fila de auditoría.

### Flujo

1. `Create()` lee el INI y llama `Bootstrap(.F.)` → `POST /erp/bootstrap` con
   `X-GesActi-Key` y el serial. Si la cuenta está `connected`/`registered` **y**
   `erp_send_enabled`, devuelve `use_cloud_api = true` y la `api_key` del cliente.
   Con `lCloud = .F.` el llamador debe seguir usando el bridge de siempre.
2. `SendPdf(cFile, cNumero, cDocRef, cNota, cContacto, cMode, cIdem)` arma el JSON con
   `media_b64` + `idempotency_key`, firma y llama `POST /erp/documents`. `cMode` es
   `auto` (documento si la ventana de 24 h está abierta, plantilla si no), `template` o
   `document`; si `cIdem` viene vacío se arma `codigo_cliente|doc_ref|destino` (el destino
   entra a propósito: la idempotencia en Support se mide por línea, así que reenviar la misma
   factura a otro cliente no puede descartarse como duplicado). Conviene pasar igual el número
   de comprobante para que un reintento no cobre dos veces.
3. `Usage(cMonth, cSerialFiltro)` → `GET /erp/usage` para mostrar el consumo del mes.

El base64 del PDF se arma en bloques de 1500 bytes contra un temporal (`ApWaB64File`), no con un
solo `HB_Base64()`: el `HB_BASE64ENCODE` de `LinkerFix.prg` acumula con `+=` y es cuadrático, así
que un PDF de varios MB tardaría horas en el puesto. Ver el registro de 19:22 → 19:30.

El cableado real está en `X:\ERP_Facturac\Source\FEConsulta.prg`, en `GenePdfyWapNativoFac`
(el procedimiento que genera el PDF de la factura y lo ofrece por WhatsApp), en el punto donde
antes sólo había `WapSelectorFinalConNumero`. Se **agrega** un paso delante, no se reemplaza nada:

```harbour
// FEConsulta.prg (punto 5 del procedimiento)
cDocRef := 'Factura ' + AllTrim(NumFac)
lNube := .F.
If IsCloudWap()
     lNube := WapCloudSend(cPdfWa, cNumLimpio, cDocRef, cMensaje, cRaSo, 'AUTO')
EndIf
If !lNube
     WapSelectorFinalConNumero(NomPdf, "Factura " + ..., cNumLimpio, cMensaje)  // bridge, intacto
EndIf
```

El `doc_ref` va **sin la razón social** (`Factura 0001-0000123`, no `Factura ... - Mi Empresa`):
la plantilla de Meta usa `{{1}} = doc_ref` y `{{2}} = contacto`, así que meter el nombre de la
empresa ahí ensucia el comprobante. El nombre de la empresa igual viaja, pero en el `caption`
(`cMensaje`) y como `contact_name` (`cRaSo`).

`WapCloudSend` (`TWhatsAppCloud.prg:1068`) es lo único que ve el llamante, y su contrato es chico:

* devuelve **`.T.`** cuando la nube ya resolvió el envío (éxito, o `duplicate` informado con
  `MyMsgInfo`): el puesto **no** abre el bridge.
* devuelve **`.F.`** cuando el puesto tiene que seguir por el bridge de siempre: no hay
  `CloudUrl`, la línea no está habilitada, o Support rechazó y el operador confirmó el reintento
  por el puente.
* un rechazo **no** cae solo al bridge: `bridge_service` es neonize y esa es justamente la vía que
  banea el número, así que primero se pregunta con `Confirma()`.

El gate `IsCloudWap()` (`Procedim.prg:19843`) replica `IsNativeWap()`: lee `[WhatsApp] CloudUrl`
de `..\GescomPdf.ini`. Sin esa clave el puesto ni instancia la clase, así que un puesto sin alta
en Support sigue exactamente como estaba.

### Topología de link: por qué el dispatcher se llama con `DYNAMIC`

`FEConsulta.prg` se compila en **11 proyectos** (`.xpj`), pero `TWhatsAppCloud.prg` sólo está
linkeado en `GesFactu.xpj`. Sin más, el C generado para la llamada trae
`HB_FUNC_EXTERN( WAPCLOUDSEND )` y los otros 10 productos **rompen en link**.

El fuente ya tiene el mecanismo: la declaración `DYNAMIC` en el **módulo que llama** (no alcanza
con declararla en `Procedim.prg`, porque es por módulo). Con `DYNAMIC WapCloudSend` al pie de las
declaraciones de `GenePdfyWapNativoFac`, el C pasa a emitir

```c
/* Skipped DEFERRED call to: 'WAPCLOUDSEND' */
{ "WAPCLOUDSEND", {HB_FS_PUBLIC | HB_FS_DEFERRED}, {NULL}, NULL },
```

o sea: cero dependencia de link, y en runtime sólo se llega ahí si `IsCloudWap()` es `.T.`. Verificado
también que `_WbFactu.xpj` (el único que no linkea `WapSelector.prg`) linkea `Procedim.prg` +
`_Dummy.prg`, así que `IsCloudWap` y `WapSelectorFinalConNumero` resuelven en los 11.

**Chequeo de sintaxis sin Xailer** (sirve para los tres `.prg` tocados; **no** reemplaza el F9):

```
X:\ERPS_Modelos\harbour.exe <archivo.prg> -iC:\xharbour\Include -iC:\Xailer2.4\Include \
    -iX:\ERPS_Comunes -i<fuente del producto> -s -n -q
```

Dos trampas que hay que conocer para no perseguir fantasmas:

1. **`-n` es obligatorio** en la línea de comando. Sin él, xHarbour 1.2.1 genera el
   *implicit starting procedure* y da `F0002 Redefinition of procedure or function` sobre **cualquier**
   `.prg` cuyo nombre coincide con el de su clase — pasa con `TWebApiClient.prg`, `TEvalCredito.prg`
   y `TWhatsAppCloud.prg`, todos de producción y que linkean bien. Xailer lo pasa por default.
2. El proyecto se arma con **xHarbour** (`GesFactu.xpj` → `Compiler Value="xHarbour"`), no con el
   Harbour de `C:\Xailer9\hb32`: con esos includes `hbclass.ch` truena con `E0025`. El set correcto
   es `C:\xharbour\Include` + `C:\Xailer2.4\Include`.

### Contrato de firma (byte-exact, lado Python y lado xHarbour)

```
base = "apollo-wa-erp-v1" + LF + METHOD + LF + path + LF + timestamp + LF + nonce + LF + sha256(body).hexdigest()
X-Apollo-Signature = HMAC-SHA256(api_key, base)            # hex minúsculas
```

* `path` es **sin query** (`request.url.path`). Consecuencia: la **query no está firmada**,
  así que `Usage()` puede mandar `month=`/`serial=` sin que se rompa la firma (el servidor los
  lee como parámetros normales y sólo usa el path para verificar). Es intencional, pero hay
  que saberlo: un atacante que ya tenga la clave podría cambiar el mes consultado; por eso
  `/erp/usage` siempre devuelve el consumo del cliente de la credencial, nunca de un `codigo`
  pasado por el cliente.
* Headers: `X-Apollo-Code` (código de cliente, 4 primeros del serial), `X-Apollo-Timestamp`
  (epoch segundos), `X-Apollo-Nonce` (hex ≥16, único), `X-Apollo-Signature`,
  `X-Apollo-Serial` (informativo).
* El puesto calcula la firma con PowerShell 5.1 (`System.Security.Cryptography`) lanzado por
  `WScript.Shell:Exec`; **la `api_key` viaja por stdin**, nunca por la línea de comandos, y el
  resultado se lee de un temporal. El body se fuerza a ASCII estricto (`ApWaAscii`) porque el
  hash se saca de un archivo y WinHttp tiene que enviar exactamente los mismos bytes.

### Orden de validación en el servidor y códigos

`require_erp_client` comprueba en este orden, con el motivo exacto en el `detail` (para que
Soporte resuelva sin abrir código): faltan headers `401` · timestamp no numérico `401` ·
reloj fuera de `WA_ERP_MAX_SKEW_SECONDS` `401` · nonce corto/no hex o **replay** `401` ·
código inexistente `401` · cliente de baja `403` · cliente sin `apikey_apollo` `401` ·
firma inválida `401` (comparada con `hmac.compare_digest`) · sin línea conectada `409` ·
línea con `erp_send_enabled = false` `403`. En el envío, media ilegible / no-PDF / vacío /
fuera de tamaño `422`.

### Cinco reglas de seguridad que sostienen el cobro

1. **Una clave por cliente** (`Client.apikey_apollo`): se revoca y rota sin afectar a nadie
   más (`POST /erp/clients/{codigo}/rotate-key`, se muestra una sola vez).
2. **Firma sobre el body**: un PDF alterado en tránsito cambia el `sha256` y da `401`.
3. **Anti-replay**: nonce único en ventana de 900 s + timestamp con 300 s de tolerancia.
4. **El token de Meta no baja al puesto**: sólo Soporte lo ve, cifrado con Fernet.
5. **Toda llamada deja huella**: `_erp_audit` en cada bootstrap y `source_channel='erp'` con
   `client_id`, `erp_serial`, `erp_operator`, `erp_doc_ref` e `idempotency_key` en el mensaje.
   El `idempotency_key` además evita que un reintento del puesto gaste dos mensajes
   facturables (índice único parcial por `account_id + idempotency_key`).

### Configuración del puesto (sección `[WhatsApp]` de `GescomPdf.ini`)

| Clave | Uso |
|---|---|
| `CloudUrl` | Base de Soporte, ej. `http://192.168.11.20:8000` (sin `/`). Sin esto, `lCloud = .F.` |
| `CloudCode` | Código de cliente en Support. Si falta, se derivan los 4 primeros del serial |
| `CloudGesActi` | Valor de `GESACTI_SYNC_KEY`, sólo para el bootstrap |
| `CloudSerial` | Serial ApolloGesCom. Si falta, `GesComSerial` / `ApWaSerial()` |
| `CloudUser` | Operador que aparece en la auditoría. Si falta, `USER` / `ApWaUser()` |
| `CloudPathPfx` | Prefijo para resolver rutas relativas del PDF |
| `CloudTemplate` | Plantilla UTILITY de factura; si falta manda la que devolvió el bootstrap (`factura_apollo`) |
| `CloudLanguage` | Idioma de la plantilla (`es` por default del server) |
| `CloudLog` | Archivo de log, default `ApolloWapCloud.log` |

La `api_key` **no se guarda en disco**: se pide en cada arranque. Es lo que hace que el
control sea real (un cliente dado de baja deja de firmar en cuanto reinicia el puesto), pero
obliga a que el `X-GesActi-Key` esté instalado en cada puesto.

> **Debilidad conocida, documentada sin resolver**: `GESACTI_SYNC_KEY` es **global** y es la
> misma clave que ya protege `/api/clients/gesacti/*` (`_require_gesacti_key`, main.py:773),
> o sea que **ya está instalada en todos los puestos** para la sincronización de licencias.
> Además `main.py:84` le pone un default visible en el código
> (`"Apollo_GesActi_Sync_2026"`) cuando la variable no está en el `.env`: si en producción no
> se define, cualquiera que lea la fuente puede pedir bootstrap con otro `codigo` y recibir la
> `api_key` de ese cliente.
>
> Para cerrarla hay dos caminos, y son una decisión del titular del proyecto, no un detalle de
> implementación: (a) credencial de bootstrap **por cliente**, o (b) que el bootstrap lo haga
> Soporte **una sola vez** al dar de alta la línea y el puesto arranque con la clave HMAC ya
> puesta en su INI. **Mínimo indispensable antes de la primera prueba real**: confirmar que
> `GESACTI_SYNC_KEY` está definido en el `.env` del servidor y que no es el default.

## Worker

`periodic_whatsapp_worker` (cada 60 s, lanzado en `startup_event`):
1. `close_expired_conversations` — cierra ventanas vencidas.
2. `process_whatsapp_outbox_once` — drena `NotificationOutbox` del canal `whatsapp`
   (target `cliente:<id>:<telefono>`). **Ojo:** manda texto libre, así que sólo funciona
   si el cliente escribió en las últimas 24 h; si no, la nota queda `failed` con el
   motivo. Para avisos prolijos hay que usar plantilla.
3. `retry_unprocessed_events` — re-procesa webhooks que fallaron (máx. 5 intentos).

## Validaciones hechas

* Smoke end-to-end del router con `httpx.ASGITransport` sobre la app de pruebas: alta de
  cuenta, webhook firmado, dedupe de reintentos de Meta, cuota mensual (429), billing.
* Revisión offline de la lógica de cobro (**`backend/_wa_recheck.py`**, SQLite en memoria,
  Graph simulado, sin red): contadores de conversación, estimación de `billable` por
  categoría y ventana, normalización del webhook de plantillas (texto y código numérico),
  `_billing_row` y firma HMAC. Correr: `venv\Scripts\python.exe _wa_recheck.py`.
  La sección **[6] canal ERP** cubre además: normalización de serial, emparejamiento de
  licencia, anti-replay, los 12 caminos de rechazo de `require_erp_client`, los 3 de media
  ilegible (422), saneado de nombre de archivo, decodificación del base64, subida real del
  PDF al Graph simulado, idempotencia, costo facturable y el reporte de uso.
  **95 checks en verde, `TODO OK`.**
* **Interoperabilidad de la firma**: el mismo body se firmó con el script de PowerShell que
  usa el puesto (`_wa_hmac_test\apollo_wa_hmac.ps1`) y se validó con `erp_signature()` de
  Python (`test_hmac_v3.py`). Coinciden byte a byte, incluyendo el `sha256` del body y el
  separador LF.
* Importación de `main.py` y registro de las 26 rutas; paridad modelo ↔ DB real.
* **Chequeo de sintaxis xHarbour de los tres `.prg` del canal ERP** (`TWhatsAppCloud.prg`,
  `Procedim.prg`, `FEConsulta.prg`) con `X:\ERPS_Modelos\harbour.exe` en modo `-s` desde un
  directorio temporal: **0 errores, 0 warnings, código generado fuera del árbol fuente**. Ahí
  aparecieron los dos defectos reales del cableado (el `Local` después de `Private` → `E0004`, y el
  `HB_FUNC_EXTERN` que rompía el link en 10 productos), descritos en el registro de las 20:00.
  Sigue pendiente el F9 de verdad: este chequeo valida el fuente, no el link del proyecto.

## Pendientes

1. **Panel de control en el frontend** (usuarios del cliente + línea + consumo del mes +
   botón "probar envío"), que es el objetivo del usuario: gestionar el 100 % desde Support.
2. Prueba real contra Meta con la cuenta ya verificada (alta de la línea 3446-675303 y
   envío de una plantilla de prueba).
3. Confirmar tarifas AR y cargarlas en `.env` / `rate_overrides`.
4. Migrar los flujos de `WapEngine` (exportar PDF de GesFactu → WhatsApp) a esta API.
   **Hecho el cliente** `TWhatsAppCloud.prg` (alta en `GesFactu.xpj`) **y hecho el cableado** en
   `FEConsulta.prg` / `Procedim.prg` (ver "Canal ERP"), con los tres `.prg` pasando el chequeo de
   sintaxis de xHarbour. Falta: **compilar con F9 desde Xailer** (el link de los 11 productos es lo
   que hay que confirmar) y la primera prueba real con log cruzado Xailer ↔ Python.
   Ojo: el hook correcto era `FEConsulta.prg`, **no** `ExportPdf.prg` como decía esta nota hasta
   hoy: en `ExportPdf` no existe número de destino hasta que el operador lo elige en el selector.
   Además `ExportPdf.prg:294-326` es un **bloque huérfano sin cabecera de `FUNCTION`** (resto de un
   refactor viejo que referencia `TWhatsAppNative`, `oIni`, `cNum`, `cMsg`): no se toca ahora, pero
   hay que saber que está ahí. Neonize se retira apenas la línea nueva esté operativa.
5. Cerrar la debilidad de `GESACTI_SYNC_KEY` global (credencial de bootstrap por cliente, o
   bootstrap hecho por Soporte en el alta). **Antes de la primera prueba real**: verificar que
   el `.env` del servidor defina `APOLLO_SECRET_KEY`, `WA_APP_SECRET`,
   `WA_WEBHOOK_VERIFY_TOKEN` y `GESACTI_SYNC_KEY` con valores propios, no el default de
   `main.py:84` (en el `main.py` del puente es la línea 90: lleva 6 líneas más arriba por el
   shim `_to_thread`).
6. Aprobación en Meta de la plantilla `factura_apollo` (UTILITY, 3 variables: comprobante,
   nombre del cliente, fecha) y activar `erp_send_enabled` en la cuenta del cliente. Sin eso
   el bootstrap devuelve `use_cloud_api = false` y el puesto sigue usando el bridge.
7. Indicador de calidad del número (`quality_rating`, `messaging_limit_tier`) en el panel:
   ya se guarda desde el webhook de calidad, falta mostrarlo.
8. **`main.py` está bifurcado P ↔ Y.** El `main.py` del puente lleva trabajo que no está en
   el de desarrollo: helper `_to_thread` + anotaciones `List[...]`/`Set[int]` (compatibilidad
   con el Python del servidor) y el bloque `[WS-FRAME]` de la 3.3.25 (logging de frames y
   `client_frames` en base64). Este promote no lo copió desde `P`: se aplicó **sólo la delta
   del canal ERP** sobre esa versión, para no perder ese trabajo. Saneado pendiente (ajeno a
   WhatsApp): traer esas dos cosas a `P` para que `P` sea de nuevo la única fuente y el
   promote vuelva a ser una copia. Mientras no se haga, **nunca copiar `P\main.py` sobre `Y`**.

## Registro de trabajo

* **2026-09-28 16:02** — Modelos de SQLAlchemy (6 tablas) + esquemas Pydantic. Copias de
  resguardo de `models.py`/`schemas.py`/`main.py` en `D:\Staff\Boris\IABack\` antes de tocar.
* **2026-09-28 16:20** — `whatsapp.py`: Graph client cifrado, webhook con firma, cuentas,
  plantillas, envío, outbox y facturación.
* **2026-09-28 16:39** — Montaje en `main.py` (rutas + worker) y `.env.example` con la
  sección del módulo.
* **2026-09-28 16:44 / 16:51** — Correcciones encontradas al validar:
  1. `touch_conversation` no sumaba el **primer** mensaje de cada conversación (los
     contadores estaban sólo en la rama `else`).
  2. Webhook de plantilla: se normaliza `event` en texto **o** código numérico, se empareja
     por nombre+idioma cuando la plantilla no tiene `meta_template_id`, y un evento
     desconocido ya **no** pisa `status` con basura (lista blanca `_TEMPLATE_STATUSES`).
  3. `perform_send` marcaba `billable` sin criterio de ventana; ahora `service` gratis,
     `marketing` siempre, y `utility`/`authentication` gratis sólo si el cliente abrió la
     ventana (`customer_window_open`).
  4. `_billing_row` contaba todos los mensajes; ahora sólo los `billable`, para no
     sobrefacturar.
  5. `build_send_payload` permitía texto libre en una conversación iniciada por nosotros →
     Meta la rechazaba con 131026. Ahora se anticipa con 409 y mensaje claro.
* **2026-09-28 16:51** — Revalidación: 30 checks en verde; 21 rutas montadas; 6 tablas OK
  contra la DB real.
* **2026-09-28 17:05** — **Al promover al puente se detectó que `models.py`, `schemas.py`,
  `main.py` y `.env.example` habían vuelto a su versión previa a WhatsApp**: quedaron byte a
  byte iguales al resguardo de las 16:02, mientras `whatsapp.py` sí conservaba el trabajo.
  El módulo quedó roto en silencio, porque `whatsapp.py` pide `models.WhatsAppAccount` que ya
  no existía. Se restauraron `models.py` (28.580) y `schemas.py` (23.403) desde
  `D:\Staff\Boris\IABack\*.20260928-163916.bak` y se volvieron a aplicar a mano el montaje en
  `main.py` y la sección de `.env.example`. Lección: al promover se coteja **contenido**
  (`grep setup_whatsapp`, `grep "class WhatsApp"`) además del hash, porque dos copias pueden
  coincidir y estar las dos mal.
* **2026-09-28 17:10** — Revalidación tras la restauración: `_wa_recheck.py` 30/30 en verde,
  21 rutas montadas, `py_compile` OK en los 5 archivos.
* **2026-09-28 17:52 / 17:55** — `models.py` y `schemas.py`: columnas del canal ERP en
  `whatsapp_accounts` (`erp_send_enabled`, `erp_invoice_template`, `erp_invoice_language`) y
  en `whatsapp_messages` (`source_channel`, `erp_serial`, `erp_operator`, `erp_doc_ref`,
  `idempotency_key`), más los esquemas `WhatsAppErp*`. Como `create_all` no altera tablas
  existentes, se sumó `ensure_erp_columns()` (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` +
  índices) para las 6 tablas ya creadas en producción.
* **2026-09-28 18:06** — `whatsapp.py`: canal ERP completo. `erp_norm_serial` /
  `erp_licensing` / `erp_license_for` (empareja el serial del puesto contra `misi_licenses`),
  `erp_base_string` / `erp_signature` (HMAC), `require_erp_client` (orden de validación y
  anti-replay con nonce en memoria, TTL 900 s), `erp_upload_media` (sube el PDF a Graph y
  devuelve `media_id`), `erp_send_document` (plantilla UTILITY fuera de ventana, documento
  directo dentro de ella, `idempotency_key` para que un reintento no gaste dos mensajes) y
  `_erp_usage` (conteos y costo con recargo, detalle por comprobante y operador).
  `main.py` monta ahora 26 rutas.
* **2026-09-28 18:30 → 18:40** — **Prueba cruzada de la firma**: se escribió
  `_wa_hmac_test\apollo_wa_hmac.ps1` (el mismo código que corre en el puesto, con la clave por
  stdin) y `test_hmac_v3.py` (Python, `erp_signature`). La firma de PowerShell validó contra
  la de Python para el mismo body/path/timestamp/nonce, y falló al alterar un byte del body.
  Primer intento con `[long]+[char]10` devolvía un objeto tipado: corregido a
  `$s=[string][...]`.
* **2026-09-28 18:58** — `X:\ERPS_Comunes\TWhatsAppCloud.prg` (nuevo, 1.009 líneas, ASCII
  puro, CP1252 OK). Resguardado antes en `D:\Staff\Boris\IABack\`. Métodos: `Create`,
  `LoadIni`, `Bootstrap`, `SendPdf`, `Usage`, `Request`, `Sign`, `JsonField`, `Esc`, `Log`,
  `Destroy`, más los estáticos `ApWa*`. Patrones tomados del fuente, no inventados: WinHttp y
  timeouts de `TEvalCredito.prg:1005-1034` y `TPedidosYaClass.prg:267-322`; `TIni():New()` con
  guarda de `ExportPdf.prg:151-155`; `TOleAuto` de `TWhatsAppNative.prg`; log tipo
  `WapAuditLog`. **El bridge neonize no se tocó.**
* **2026-09-28 19:07** — Alta de la clase en `X:\ERP_Facturac\GesFactu.xpj`, pegada a
  `TWhatsAppClass.prg` (resguardo `GesFactu_20260928-190722.xpj`). CRLF preservado; el fallo de
  parseo XML del `.xpj` es **preexistente** (termina en `\x1a`), no lo introdujo esta edición.
* **2026-09-28 19:07 → 19:20** — Correcciones encontradas al releer la clase:
  1. `nHex` sin declarar en `ApWaJsonGet` (la rama `\uXXXX` lo usaba).
  2. `TIni():Create()` → `TIni():New()` en `Try/Catch/End` con chequeo de `Nil`, como en el
     resto del fuente.
  3. El base64 se concatenaba ~10 veces (`jSon := jSon + ...`): un PDF de 8 MB son ~11 MB de
     texto y xHarbour copia en cada suma. Ahora se arma `cPre` y `cPos` y se concatena **una
     sola vez**.
  4. `Usage()` usaba `::Esc()` en la query: no hace URL-encoding y un espacio rompía el
     pedido. Nuevo estático `ApWaUrl()` con pct-encoding (la firma igual es sobre el path sin
     query).
  5. Regla `harbour-no-return-in-try`: verificado **0 `Return` dentro de `Try/Catch`** y
     bloques balanceados. No se puede compilar en esta máquina (sin `xbscript.exe` ni
     compilador C/C++): la validación es por escaneo y la compilación real queda pendiente
     con **F9** desde Xailer.
* **2026-09-28 19:13 → 19:22** — `_wa_recheck.py` ampliado con la sección [6] y corrido con
  `backend\venv\Scripts\python.exe` (ojo: el venv está en `backend\`, no en la raíz del
  proyecto): **95 checks en verde, `TODO OK`**, sin errores ni FAIL.
* **2026-09-28 19:22 → 19:30** — **Cuello de botella del base64 en el puesto.** Al cotejar las
  firmas de los métodos contra el fuente, `HB_Base64` resuelve a `LinkerFix.prg:9`
  (`HB_BASE64ENCODE`), que es puro PRG y arma el resultado con `cResult += ...` sobre la cadena
  que va creciendo: el costo es ~`0.89·N·s` (cuadrático). Un PDF de 8 MB implicaría ~57 TB de
  copia — inviable, no "lento". Se resolvió en `TWhatsAppCloud.prg` **sin tocar `LinkerFix.prg`**
  (convive con el resto del ERP) y **sin apostar a `hb_b64encode` del library**, porque el propio
  LinkerFix está ahí precisamente por "unresolved externals" de ese símbolo y acá no hay
  compilador con el que comprobarlo:
  1. Nuevo estático `ApWaB64File(bData, nLen, cFile)`: codifica en bloques de **1500 bytes**
     (múltiplo de 3, así cada bloque termina alineado y no hace falta pegar los base64 parciales)
     y los escribe con `FCreate`/`FWrite`/`FClose`. Ese triplete viene de `GaliciaReci.prg:99-105`,
     no inventado.
  2. `SendPdf` pasa a leer el temporal de una sola pasada con `MemoRead`, lo limpia con
     `FErase` en `Try/Catch/End`, y verifica que el base64 no haya quedado vacío. `cB64File`
     declarado en el `Local` del método.
  3. Costo estimado: ~10 GB de copia en lugar de ~57 TB (segundos en vez de horas).
  4. Riesgo conocido y **preexistente**, no agravado: `HB_BASE64ENCODE` devuelve `""` si
     `Empty(cString)`; sólo ocurriría si un bloque entero fuera `Chr(0)`-puro en un archivo que
     además arrancaría con bytes nulos, y el `If Empty(cB64)` de `SendPdf` lo corta antes de
     firmar.
  5. El archivo quedó en **CRLF** (estaba en LF al crearlo; los cinco `.prg` hermanos son CRLF
     puros): 1057 líneas / 36.195 bytes, `check_prg_cp1252.py` OK y 0 bytes >127. Resguardo previo
     `TWhatsAppCloud_20260928-192210.prg`.
* **2026-09-28 19:30** — Re-escaneo estructural de la clase con `_xtmp\scan_prg.py` (ahora con
  los desbalances impresos y `Method`/`Function` tratados como cierre implícito): **0 bloques
  abiertos, 0 desbalances, 0 `Return` dentro de `Try/Catch`**, 133 `If`/133 `EndIf`,
  10 `Try`/10 `Catch`/10 `End`, 10 `For`/10 `Next`, 5 `Do While`/5 `EndDo`. Los 5 nombres que
  marca como "no declarados" son parámetros del encabezado (`Bootstrap(lForce)`,
  `SendPdf(cFile,...)`, `Request(..., cQuery, jSon, lSign, ...)`): falso positivo del escáner, ya
  verificado contra las líneas 176/258/414. Corrección documental: la idempotencia por default es
  `codigo|doc_ref|destino` (no "`doc_ref + hora`", como decía el flujo de arriba).
* **2026-09-28 19:31 → 19:38** — **Promote a `Y:\ApolloSupport` (puente → servidor).**
  Resguardos previos en `D:\Staff\Boris\IABack\` (`Y-*` los del puente, `P-*` los de desarrollo,
  sufijo `20260928-193153`). Al cotejar tamaño/`mtime` apareció una divergencia que no era mía:
  `Y\main.py` (19:16) es más nuevo que `P\main.py` (18:06) y trae código `[WS-FRAME]` y shims de
  compatibilidad; `Y\schemas.py` traía `last_seen: Optional[datetime] = None`, que `P` no tenía.
  Copiar `P → Y` a ciegas habría roto el video (3.3.25) y el arranque en el Python del server.
  Cómo se hizo, entonces:
  1. `P\schemas.py` recibió el fix de `last_seen` desde `Y` (para que `P` no quede atrás) y
     después sí se copió.
  2. `Y\main.py` **no** se reemplazó: se le aplicó sólo la delta del canal ERP (import
     `ensure_erp_columns`, `setup_whatsapp(app, get_current_user, GESACTI_SYNC_KEY)`, la llamada).
     Verificado después: 13 usos de `_to_thread` y los 4 bloques `[WS-FRAME]` siguen intactos, y
     `ast.parse` del resultado da OK.
  3. Copiados `whatsapp.py`, `models.py`, `schemas.py`, `.env.example`, `_wa_recheck.py` y este
     MD; hash SHA-256 (16 primeros) idéntico `P` ↔ `Y` en los seis. `models.py` no tenía nada
     propio en `Y` (0 líneas `Y`-only), así que la copia es segura; las 5 líneas "propias" de
     `Y\whatsapp.py` eran simplemente las versiones viejas de líneas que `P` cambió.
  4. Escaneo de sintaxis 3.8 sobre los archivos copiados: `whatsapp.py`/`models.py`/`schemas.py`
     limpios (ni `list[...]`/`set[...]`/`dict[...]`, ni `asyncio.to_thread`, ni `X | None`);
     `main.py` de `P` **no** lo está, y es la razón por la que no se copia.
  5. `.env.example` no tenía el bloque `WA_ERP_*` (el MD lo daba por hecho): agregados
     `WA_ERP_MAX_SKEW_SECONDS`, `WA_ERP_NONCE_TTL_SECONDS`, `WA_ERP_MAX_PDF_MB`,
     `WA_ERP_INVOICE_TEMPLATE`, `WA_ERP_INVOICE_LANGUAGE`, todos verificados contra
     `whatsapp.py:80-87`.
  6. Revalidado tras el promote: `_wa_recheck.py` con `backend\venv\Scripts\python.exe` →
     **95 `OK`, `TODO OK`**.
  7. `Y:\ApolloSupport\ACTUALIZAR_WHATSAPP_CLOUD_API.txt` reescrito (resguardo
     `Y-ACTUALIZAR_WHATSAPP_CLOUD_API.txt.20260928-193346.bak`): 26 rutas, columnas del canal ERP,
     la advertencia de no pisar `main.py`, `GESACTI_SYNC_KEY` como obligatoria para el canal, pasos
     6-9 del alta real, verificaciones con `curl` y el estado honesto del lado ERP (cliente hecho,
     **sin compilar con F9**, `ExportPdf.prg` aún no cableado).
  Queda abierta la bifurcación de `main.py` (pendiente 8). El `X-GesActi-Key` del server sigue sin
  definirse en el `.env`: mientras use el default de `main.py:84`, el bootstrap se puede suplantar.
* **2026-09-28 19:45 → 19:52** — **Cableado del canal ERP en el envío de facturas**, con la orden
  del usuario de no borrar el bridge. Altas: `IsCloudWap()` en `Procedim.prg:19843` (replica el
  gate de INI de `IsNativeWap()`), `DYNAMIC ..., WapCloudSend` en `Procedim.prg:19859`, dispatcher
  `WapCloudSend()` al pie de `TWhatsAppCloud.prg` (1068-1092) y la llamada en `FEConsulta.prg`
  (`GenePdfyWapNativoFac`, punto 5) dejando `WapSelectorFinalConNumero` intacto dentro del
  `If !lNube`. Resguardos: `X-Procedim.prg.20260928-194813.bak`,
  `X-TWhatsAppCloud.prg.20260928-194546.bak`, `X-FEConsulta.prg.20260928-194546.bak`.
  **Incidente con la herramienta de edición**: sobre `FEConsulta.prg` (CP1252 con acentos reales)
  el `Edit` re-codificó el archivo como UTF-8 con reemplazo y metió **25 secuencias `EF BF BD`**,
  subiendo los bytes altos de 279 a 329 — acentos destruidos. Se restauró 1:1 desde el resguardo y
  se reaplicó el cambio **a nivel de bytes** con Python (`open('rb')`, patrón único verificado con
  `count==1`, salida CRLF y texto ASCII). Regla operativa: **ningún `.prg` legacy con acentos se
  edita con la herramienta de edición; se parcha en bytes.** En `TWhatsAppCloud.prg` (ASCII puro)
  es inocuo, y en `Procedim.prg` los 466 `EF BF BD` son **preexistentes** (idénticos en el
  resguardo), o sea daño de ediciones pasadas ajenas, no de esta sesión.
* **2026-09-28 20:00 → 20:07** — **Chequeo de sintaxis offline con xHarbour** de los tres `.prg`
  tocados, en `_xtmp\` y sin dejar artefactos en `X:`. Salió el compilador que esta nota daba por
  inexistente: **sí hay** `X:\ERPS_Modelos\harbour.exe` (xHarbour 1.2.1) con `C:\xharbour\Include` +
  `C:\Xailer2.4\Include` (el set que corresponde al `Compiler Value="xHarbour"` del `.xpj`; con los
  includes de `C:\Xailer9\hb32` `hbclass.ch` truena en `E0025`), y están `C:\Xailer2.4`, `C:\Xailer8`
  y `C:\Xailer9`. Lo que no hay es compilador de C, así que el F9 del proyecto sigue siendo del
  usuario. Dos defectos **reales** del cableado, encontrados sólo por este chequeo:
  1. `E0004 LOCAL declaration follows executable statement` en `FEConsulta.prg:1988`: el
     `Local lNube, cDocRef, cPdfWa` había quedado **después** de los dos `Private`, y en Harbour
     `PRIVATE` es sentencia ejecutable. Movido antes de los `Private`. El procedimiento original no
     declaraba `Local` en ningún punto, por eso el error no existía antes de esta edición.
  2. El C generado traía `HB_FUNC_EXTERN( WAPCLOUDSEND )`, o sea **link roto en los 10 productos**
     que arman `FEConsulta.prg` sin linkear `TWhatsAppCloud.prg`. El `DYNAMIC` de `Procedim.prg` no
     alcanza porque es por módulo: se agregó `DYNAMIC WapCloudSend` en la sección de declaraciones de
     `GenePdfyWapNativoFac`. Verificado en el C: ahora `HB_FS_DEFERRED` con `{NULL}` y sin extern.
  Topología confirmada leyendo los `.xpj`: 11 productos compilan `FEConsulta.prg`; 10 linkean
  `WapSelector.prg`, `_WbFactu.xpj` usa `_Dummy.prg` (que ya stubbea `WapSelectorFinalConNumero`) y
  `Procedim.prg` está en todos, así que `IsCloudWap()` resuelve en los 11.
  Resultado final de los tres archivos: `harbour -s -n` **0 errores / 0 warnings**;
  `check_prg_cp1252.py` sin `EF BF BD` nuevos; `FEConsulta.prg` 263.660 B (279 bytes altos, CRLF
  puro, 0 LF sueltos), `Procedim.prg` 675.502 B (idéntico al estado previo, 466 preexistentes),
  `TWhatsAppCloud.prg` 38.147 B ASCII puro / 1.092 líneas. Nota de lectura: en la línea de comando
  hace falta `-n`, sin él xHarbour genera el *implicit starting procedure* y da `F0002` sobre
  cualquier `.prg` cuyo nombre coincide con su clase — le pasa a `TWebApiClient.prg` y
  `TEvalCredito.prg`, que linkean bien en producción.
* **2026-09-28 20:10 → 20:12** — Cierre documental y promoción. La tabla **Archivos** ahora lista
  los tres `.prg` del canal (`TWhatsAppCloud.prg` con su dispatcher, `FEConsulta.prg` con el hook
  real y `Procedim.prg` con el gate de INI), para que el cableado se encuentre desde el índice y no
  sólo releyendo el registro. Verificado que el MD sigue UTF-8 / LF puro / 0 `EF BF BD`
  (39.261 B). Resguardada la versión previa del puente
  (`Y-ApolloSupport-backend-WHATSAPP_CLOUD_API.md.20260928-201051.bak`, 30.484 B) y copiado a `Y:`;
  cotejo de **contenido además del hash**: `sha256` idéntico en P e Y tras la copia final y los tres
  símbolos nuevos presentes en destino (`IsCloudWap` 8 apariciones, `WapCloudSend` 9,
  `GenePdfyWapNativoFac` 6). No se anota acá el `sha256` de esta versión porque el propio registro lo
  modificaría; el de la copia anterior (39.261 B) fue `f93ef5b5…`.
  `ACTUALIZAR_WHATSAPP_CLOUD_API.txt` reemplazó el bloque "PENDIENTE: … ExportPdf.prg aún no la
  llama" (que estaba mal: el hook no va ahí) por el estado real, con el motivo del `DYNAMIC` y la
  receta de compilación; resguardo `Y-ApolloSupport-ACTUALIZAR_WHATSAPP_CLOUD_API.txt.20260928-201139.bak`.
  Chequeo de rutas del módulo: **26** decoradores en `/api/whatsapp`, 5 de ellos `/erp/*`.
  **Lo único que queda del lado ERP es el F9 desde Xailer y la prueba real** — hasta ese momento el
  puesto no usa el canal y el bridge sigue siendo el camino activo.
