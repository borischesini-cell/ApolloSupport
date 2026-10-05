# Configuración de línea WhatsApp para soporte (Grupo Master SRL)

## Objetivo

Dar de alta la línea **+54 9 3446 527365** (titular: Grupo Master SRL) en ApolloSupport para uso interno de soporte técnico. Esta línea reemplaza el bridge neonize que baneaba el número.

## Pre-requisitos

### 1. Verificar que el backend esté corriendo

```bash
# En el servidor (192.168.11.223)
nssm status ApolloBackend
# Debe decir "SERVICE_RUNNING"
```

Si no está corriendo:
```bash
nssm start ApolloBackend
```

### 2. Verificar variables de entorno en el servidor

Abrir `C:\ApolloSupport\backend\.env` (o el path donde esté el backend en producción) y confirmar que existen estas variables:

```env
# OBLIGATORIAS para WhatsApp
APOLLO_SECRET_KEY=<64 chars aleatorios>
WA_APP_SECRET=<App secret de Meta>
WA_WEBHOOK_VERIFY_TOKEN=<string aleatorio>
GESACTI_SYNC_KEY=<clave propia, NO el default>
```

**Cómo generarlas si faltan:**

```bash
# APOLLO_SECRET_KEY (clave maestra para cifrar tokens)
python -c "import secrets; print(secrets.token_hex(32))"

# WA_WEBHOOK_VERIFY_TOKEN (token para el webhook de Meta)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# GESACTI_SYNC_KEY (clave para el canal ERP)
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

**WA_APP_SECRET** se obtiene de:
- Meta for Developers → App Dashboard → Basic → App secret

Después de editar el `.env`:
```bash
nssm restart ApolloBackend
```

### 3. Obtener los IDs de Meta

Necesitás tres valores del panel de Meta for Developers:

#### a) `waba_id` (WhatsApp Business Account ID)

1. Ir a [Meta for Developers](https://developers.facebook.com/)
2. Seleccionar la app de WhatsApp de Grupo Master SRL
3. WhatsApp → API Setup → Business Account ID
4. Copiar el número (ej: `807028593951690`)

#### b) `phone_number_id` (ID del número +54 9 3446 527365)

1. WhatsApp → API Setup → Phone numbers
2. Click en el número +54 9 3446 527365
3. En la URL aparece el ID: `https://business.facebook.com/wa/manage-phone-numbers/<PHONE_NUMBER_ID>/`
4. Copiar ese número

#### c) `access_token` (System User Token)

**IMPORTANTE**: Este token es de larga duración y se cifra al guardar en la DB.

1. Meta for Developers → System Users
2. Seleccionar o crear un System User con permisos:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
3. Generar token con los assets:
   - WABA de Grupo Master SRL (permisos: `whatsapp_business_messaging`, `whatsapp_business_management`)
   - App de WhatsApp (permisos: `whatsapp_business_messaging`)
4. Copiar el token (aparece una sola vez)

**Alternativa**: Si ya tenés un token de prueba en el panel, podés usarlo temporalmente, pero hay que reemplazarlo por uno de System User antes de producción.

### 4. Obtener el PIN de 6 dígitos

Meta pide un PIN de 6 dígitos para registrar el número. Se obtiene así:

1. WhatsApp → API Setup → Step 2: "Send a test message"
2. Click en "Generate PIN"
3. Copiar el PIN de 6 dígitos (ej: `123456`)

**Este PIN se usa una sola vez** en el paso de registro.

## Paso 1: Dar de alta la cuenta en ApolloSupport

### a) Verificar que exista el cliente "Grupo Master SRL" en la DB

```bash
curl -X GET "http://127.0.0.1:8001/api/clients" \
  -H "Authorization: Bearer <TOKEN_ADMIN>" | \
  python -m json.tool | grep -A5 "GRUPO MASTER"
```

Si no existe, hay que crearlo primero (ver documentación de clientes).

**Nota**: Para "nosotros" (soporte interno), el `client_id` puede ser el de Grupo Master SRL o un cliente especial "SOPORTE_INTERNO". Lo importante es que exista en la tabla `clients`.

### b) POST para crear la cuenta

```bash
curl -X POST "http://127.0.0.1:8001/api/whatsapp/accounts" \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": <CLIENT_ID_GRUPO_MASTER>,
    "business_id": "807028593951690",
    "waba_id": "<WABA_ID>",
    "phone_number_id": "<PHONE_NUMBER_ID>",
    "display_phone_number": "+5493446527365",
    "verified_name": "GRUPO MASTER SRL",
    "access_token": "<SYSTEM_USER_TOKEN>",
    "pin": "<PIN_6_DIGITOS>",
    "allowed_categories": "UTILITY,SERVICE",
    "monthly_message_quota": 10000,
    "rate_currency": "USD",
    "notes": "Linea de soporte interno - reemplazo de neonize",
    "erp_send_enabled": false,
    "erp_invoice_template": "factura_apollo",
    "erp_invoice_language": "es"
  }'
```

**Respuesta esperada:**

```json
{
  "id": 1,
  "client_id": 123,
  "business_id": "807028593951690",
  "waba_id": "<WABA_ID>",
  "phone_number_id": "<PHONE_NUMBER_ID>",
    "display_phone_number": "+5493446527365",
  "verified_name": "GRUPO MASTER SRL",
  "status": "pending",
  "allowed_categories": "UTILITY,SERVICE",
  "monthly_message_quota": 10000,
  "messages_sent_this_month": 0,
  "rate_currency": "USD",
  "erp_send_enabled": false,
  "erp_invoice_template": "factura_apollo",
  "erp_invoice_language": "es",
  "created_at": "2026-09-29T...",
  "updated_at": "2026-09-29T..."
}
```

**IMPORTANTE**: Guardar el `id` de la cuenta (ej: `1`) para los siguientes pasos.

## Paso 2: Registrar el número en Meta

```bash
curl -X POST "http://127.0.0.1:8001/api/whatsapp/accounts/1/register" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

**Respuesta esperada:**

```json
{
  "status": "registered",
  "meta": {
    "success": true
  }
}
```

**Qué hace este paso:**
- Registra el número en la Cloud API de Meta
- El número **deja de poder usarse en la app de WhatsApp común** del teléfono
- El estado de la cuenta cambia a `"registered"`

**Si falla:**
- Verificar que el PIN sea correcto (6 dígitos)
- Verificar que el token tenga permisos sobre el WABA
- Verificar que el número no esté ya registrado en otra cuenta

## Paso 3: Probar la conexión con Meta

```bash
curl -X POST "http://127.0.0.1:8001/api/whatsapp/accounts/1/test" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

**Respuesta esperada:**

```json
{
  "status": "connected",
  "cuenta": {
    "id": 1,
    "status": "connected",
    "quality_rating": "GREEN",
    "messaging_limit_tier": "TIER_1K",
    "verified_name": "GRUPO MASTER SRL",
    ...
  },
  "meta": {
    "id": "<PHONE_NUMBER_ID>",
    "display_phone_number": "+54 9 3446 527365",
    "verified_name": "GRUPO MASTER SRL",
    "quality_rating": "GREEN",
    "messaging_limit_tier": "TIER_1K",
    "platform_type": "CLOUD_API",
    "name_verification_status": "VERIFIED"
  }
}
```

**Qué significa:**
- `quality_rating`: GREEN (bueno), YELLOW (advertencia), RED (riesgo de baneo)
- `messaging_limit_tier`: TIER_1K (1000 mensajes/día), TIER_10K, TIER_100K, TIER_UNLIMITED
- `status`: ahora es `"connected"`

## Paso 4: Habilitar el canal ERP

```bash
curl -X PUT "http://127.0.0.1:8001/api/whatsapp/accounts/1" \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -H "Content-Type: application/json" \
  -d '{
    "erp_send_enabled": true
  }'
```

**Respuesta esperada:**

```json
{
  "id": 1,
  ...
  "erp_send_enabled": true,
  "erp_invoice_template": "factura_apollo",
  "erp_invoice_language": "es",
  ...
}
```

## Paso 5: Generar la api_key para el canal ERP

```bash
curl -X POST "http://127.0.0.1:8001/api/whatsapp/erp/clients/<CODIGO_CLIENTE>/rotate-key" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

Donde `<CODIGO_CLIENTE>` es el código del cliente en la tabla `clients` (ej: `GM001` o el que corresponda a Grupo Master SRL).

**Respuesta esperada:**

```json
{
  "client_code": "GM001",
  "api_key": "aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890",
  "note": "Entregala al cliente por un canal seguro: no queda guardada en otro lado."
}
```

**IMPORTANTE**: 
- La `api_key` se muestra **una sola vez**
- Se guarda en `Client.apikey_apollo` (columna preexistente en la tabla `clients`)
- El puesto la pide en cada arranque con `X-GesActi-Key`
- Si se pierde, hay que rotarla de nuevo con este endpoint

## Paso 6: Configurar el INI del puesto

En el puesto donde se va a probar (o en todos los puestos de soporte), editar `..\GescomPdf.ini` y agregar la sección:

```ini
[WhatsApp]
CloudUrl=http://192.168.11.223:8001
CloudCode=GM001
CloudGesActi=<GESACTI_SYNC_KEY_DEL_SERVER>
CloudSerial=<SERIAL_GESCOM_DEL_PUESTO>
CloudUser=<USUARIO_GESCOM>
CloudPathPfx=C:\ApolloSupport\wa_logs
CloudTemplate=factura_apollo
CloudLanguage=es
CloudLog=1
```

**Explicación de cada campo:**

- `CloudUrl`: URL del backend de ApolloSupport (sin `/api/whatsapp`)
- `CloudCode`: Código del cliente en la tabla `clients` (el mismo que usaste en el paso 5)
- `CloudGesActi`: La `GESACTI_SYNC_KEY` del `.env` del servidor
- `CloudSerial`: Serial de GesCom del puesto (aparece en el menú Acerca de)
- `CloudUser`: Usuario de GesCom con el que se loguea el operador
- `CloudPathPfx`: Path local donde se guardan los logs de envío (opcional, default: `C:\ApolloSupport\wa_logs`)
- `CloudTemplate`: Nombre de la plantilla UTILITY (default: `factura_apollo`)
- `CloudLanguage`: Idioma de la plantilla (default: `es`)
- `CloudLog`: 1 = guarda logs detallados en `CloudLog_<YYYYMMDD>.log` (recomendado para debugging)

## Paso 7: Probar el envío de una factura

1. Abrir GesCom en el puesto configurado
2. Ir a Facturación → Consultar factura
3. Seleccionar una factura de prueba
4. Click en "Enviar por WhatsApp" (o el botón que hayas configurado)
5. El sistema debería:
   - Llamar a `WapCloudSend()` en `TWhatsAppCloud.prg`
   - Hacer bootstrap contra `/api/whatsapp/erp/bootstrap`
   - Subir el PDF a `/api/whatsapp/erp/documents`
   - Support lo sube a Meta y devuelve `media_id`
   - Se envía la plantilla `factura_apollo` con el PDF adjunto

**Verificar en los logs:**

```bash
# En el servidor
tail -f C:\ApolloSupport\backend\logs\apollo.log | grep "WA/ERP"

# En el puesto
type C:\ApolloSupport\wa_logs\CloudLog_20260929.log
```

**Mensajes esperados en el log del servidor:**

```
[WA/ERP] bootstrap serial=ABCD-1234567 cliente=GM001
[WA/ERP] upload document media_id=...
[WA/ERP] send template factura_apollo to +5493446123456 doc_ref="Factura 0001-00000123"
```

## Paso 8: Verificar el consumo

```bash
curl -X GET "http://127.0.0.1:8001/api/whatsapp/erp/clients/GM001/usage?month=2026-09" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

**Respuesta esperada:**

```json
{
  "client_code": "GM001",
  "month": "2026-09",
  "messages": [
    {
      "id": 1,
      "created_at": "2026-09-29T10:30:00Z",
      "to": "+5493446123456",
      "template_name": "factura_apollo",
      "erp_doc_ref": "Factura 0001-00000123",
      "erp_serial": "ABCD-1234567",
      "erp_operator": "ADMIN",
      "billable": true,
      "cost_amount": 0.0225,
      "status": "delivered"
    }
  ],
  "total_messages": 1,
  "total_cost": 0.0225,
  "currency": "USD"
}
```

## Troubleshooting

### Error 401 en /erp/bootstrap

**Causa**: `GESACTI_SYNC_KEY` del puesto no coincide con la del servidor.

**Solución**: Verificar que `CloudGesActi` en `GescomPdf.ini` sea igual a `GESACTI_SYNC_KEY` en el `.env` del servidor.

### Error 403 en /erp/documents

**Causa**: Firma HMAC inválida o reloj desincronizado.

**Solución**:
- Verificar que el reloj del puesto esté sincronizado (NTP)
- Aumentar `WA_ERP_MAX_SKEW_SECONDS` en el `.env` del servidor (default: 300)

### Error 409 en /erp/documents

**Causa**: Plantilla no aprobada o fuera de ventana de 24h.

**Solución**:
- Verificar que la plantilla `factura_apollo` esté aprobada en Meta
- Si el cliente no escribió en las últimas 24h, el envío debe ser con plantilla (no texto libre)

### El número sigue en la app de WhatsApp común

**Causa**: No se ejecutó el paso 2 (register).

**Solución**: Ejecutar `POST /api/whatsapp/accounts/{id}/register` con el PIN correcto.

### Error "access_token expired"

**Causa**: El token de System User expiró (si era de prueba).

**Solución**: Generar un nuevo token de larga duración en Meta for Developers y actualizarlo con `PUT /api/whatsapp/accounts/{id}`.

## Próximos pasos

Una vez que la línea de soporte esté operativa:

1. **Crear la plantilla `factura_apollo`** en Meta (UTILITY, 3 variables: comprobante, nombre del cliente, fecha)
2. **Probar el envío real** de una factura desde el puesto
3. **Monitorear el consumo** con `/erp/clients/{codigo}/usage`
4. **Configurar el panel de control** en el portal (pendiente 1 del MD)
5. **Dar de alta líneas para clientes** que lo soliciten (repetir este proceso para cada cliente)

## Referencias

- Documentación completa: `P:\ApolloSupport\backend\WHATSAPP_CLOUD_API.md`
- Nota de deploy: `Y:\ApolloSupport\ACTUALIZAR_WHATSAPP_CLOUD_API.txt`
- Código del canal ERP: `X:\ERPS_Comunes\TWhatsAppCloud.prg`
- Hook en facturación: `X:\ERP_Facturac\Source\FEConsulta.prg` (líneas 1984-2046)
