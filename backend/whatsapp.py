"""
-------------------------------------------------------------------------
Integración WhatsApp Cloud API (oficial de Meta)
Proyecto: ApolloSupport
Descripción:
  Gestión multi-tenant de líneas de WhatsApp Business. Cada cliente tiene
  SU propia WABA + número, con contadores de consumo separados para poder
  facturar a fin de mes.

  Reemplaza el puente "neonize" (cliente no oficial de WhatsApp Web) que
  producía baneos del número.

  Este módulo NO usa la API de Cloud de terceros (BSP): habla directo con
  graph.facebook.com, con System User Tokens propios de cada cuenta.

Seguridad:
  * Los access_token se guardan CIFRADOS (Fernet derivado de APOLLO_SECRET_KEY).
    Nunca se devuelven en una respuesta de API.
  * El webhook valida X-Hub-Signature-256 con WA_APP_SECRET antes de procesar.
  * Cualquier ruta que no sea el webhook exige JWT (rol 'admin' para escribir).

Documentación de uso, alta de una línea y registro de cambios: WHATSAPP_CLOUD_API.md
(validator offline de la lógica de cobro: _wa_recheck.py).
-------------------------------------------------------------------------
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

import models
import schemas
from database import SessionLocal, get_db

logger = logging.getLogger("apollosupport.whatsapp")

# ── Configuración ────────────────────────────────────────────────────────────
GRAPH_VERSION = os.getenv("WA_GRAPH_VERSION", "v23.0")
GRAPH_BASE = os.getenv("WA_GRAPH_BASE", f"https://graph.facebook.com/{GRAPH_VERSION}").rstrip("/")
WA_APP_SECRET = os.getenv("WA_APP_SECRET", "")
WA_VERIFY_TOKEN = os.getenv("WA_WEBHOOK_VERIFY_TOKEN", "")
WA_TIMEOUT = float(os.getenv("WA_GRAPH_TIMEOUT", "30"))
WA_DEFAULT_COUNTRY = os.getenv("WA_DEFAULT_COUNTRY_CODE", "54")

# Tarifa por mensaje ENTREGADO (Meta facturación por mensaje desde 07/2025).
# Son USD y deben ajustarse a la tarifa vigente del país del número: verificar
# en Meta -> Billing before trusting these figures for invoicing.
DEFAULT_RATES: Dict[str, float] = {
    "utility": float(os.getenv("WA_RATE_UTILITY", "0.0225")),
    "marketing": float(os.getenv("WA_RATE_MARKETING", "0.0625")),
    "authentication": float(os.getenv("WA_RATE_AUTHENTICATION", "0.0375")),
    "service": 0.0,  # ventana abierta por el cliente: sin cargo
}

# Recargo propio sobre el costo de Meta antes de facturar al cliente
WA_MARKUP_PCT = float(os.getenv("WA_MARKUP_PCT", "30"))

CONVERSATION_WINDOW_HOURS = 24

# ── Canal ERP (ApolloGesCom) ─────────────────────────────────────────────────
# El puesto del ERP NO ve el token de Meta: firma su pedido con una clave por
# cliente, sube el PDF y Support habla con Graph. Así el historial que justifica
# el cobro de fin de mes se escribe acá y no en el puesto del cliente.
WA_ERP_SIGNATURE_PREFIX = "apollo-wa-erp-v1"
WA_ERP_MAX_SKEW = int(os.getenv("WA_ERP_MAX_SKEW_SECONDS", "300"))
WA_ERP_MAX_PDF_MB = float(os.getenv("WA_ERP_MAX_PDF_MB", "8"))
WA_ERP_NONCE_TTL = int(os.getenv("WA_ERP_NONCE_TTL_SECONDS", "900"))
# Plantilla de factura usada cuando el cliente no escribió en las últimas 24 h.
# Cada cuenta puede pisarla en WhatsAppAccount.erp_invoice_template.
WA_ERP_INVOICE_TEMPLATE = os.getenv("WA_ERP_INVOICE_TEMPLATE", "factura_apollo")
WA_ERP_INVOICE_LANG = os.getenv("WA_ERP_INVOICE_LANGUAGE", "es")

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])

_get_current_user = None  # inyectado por setup_whatsapp()


# ═════════════════════════════════════════════════════════════════════════════
# Cifrado de credenciales
# ═════════════════════════════════════════════════════════════════════════════

def _fernet() -> Fernet:
    """Clave Fernet derivada de APOLLO_SECRET_KEY (no se hardcodea ninguna)."""
    secret = os.getenv("APOLLO_SECRET_KEY", "")
    if not secret:
        raise HTTPException(
            status_code=500,
            detail="APOLLO_SECRET_KEY no está definido en .env: no se pueden cifrar tokens de WhatsApp.",
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(plain: Optional[str]) -> Optional[str]:
    if not plain:
        return None
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(enc: Optional[str]) -> Optional[str]:
    if not enc:
        return None
    try:
        return _fernet().decrypt(enc.encode("ascii")).decode("utf-8")
    except InvalidToken:
        logger.error("[WA] Token no decryptable: APOLLO_SECRET_KEY cambió desde el alta de la cuenta")
        raise HTTPException(status_code=500, detail="No se pudo descifrar el token (APOLLO_SECRET_KEY cambió).")


def get_account_token(account: models.WhatsAppAccount) -> str:
    token = decrypt_secret(account.access_token_enc)
    if not token:
        raise HTTPException(
            status_code=409,
            detail=f"La cuenta {account.id} no tiene access_token configurado.",
        )
    return token


# ═════════════════════════════════════════════════════════════════════════════
# Utilidades: teléfonos, fechas, plantillas
# ═════════════════════════════════════════════════════════════════════════════

def now_utc() -> datetime:
    return datetime.utcnow()


def normalize_wa_phone(raw: Optional[str]) -> str:
    """
    Normaliza a lo que espera Meta: dígitos con código país, sin '+'.
    Asume Argentina (código 54) cuando el número viene sin código de país,
    porque la base de clientes de Apollo es local. Cambiar WA_DEFAULT_COUNTRY_CODE
    para otros mercados.
    """
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return ""
    if digits.startswith(WA_DEFAULT_COUNTRY) or WA_DEFAULT_COUNTRY == "":
        return digits
    if WA_DEFAULT_COUNTRY == "54":
        # Móvil AR: 11 + 8 dígitos -> 549 + 11 + 8
        if len(digits) == 10 and digits.startswith("11"):
            return f"549{digits}"
        # Fijo con código de área (ej. 3446 467530)
        if len(digits) in (10, 11):
            return f"54{digits}"
    return f"{WA_DEFAULT_COUNTRY}{digits}"


def epoch_to_naive(ts: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.utcfromtimestamp(int(ts))
    except (TypeError, ValueError):
        return None


TEMPLATE_NAME_RE = re.compile(r"^[a-z0-9_]{1,255}$")


def validate_template_name(name: str) -> str:
    if not TEMPLATE_NAME_RE.match(name or ""):
        raise HTTPException(
            status_code=422,
            detail="El nombre de plantilla debe ser minúsculas, números y guión bajo (sin espacios).",
        )
    return name


def get_rates(account: models.WhatsAppAccount) -> Dict[str, float]:
    """Tarifas efectivas de una cuenta: defaults globales + override por cuenta."""
    rates = dict(DEFAULT_RATES)
    raw = None
    if account and account.rate_overrides:
        raw = account.rate_overrides
    if raw:
        try:
            loaded = json.loads(raw) if isinstance(raw, str) else raw
            for k, v in (loaded or {}).items():
                rates[str(k).lower()] = float(v)
        except (ValueError, TypeError) as e:
            logger.warning("[WA] rate_overrides inválidos en cuenta %s: %s", account.id, e)
    return rates


def parse_categories(csv: Optional[str]) -> List[str]:
    return [c.strip().upper() for c in (csv or "").split(",") if c.strip()]


# ═════════════════════════════════════════════════════════════════════════════
# Cliente de la Graph API
# ═════════════════════════════════════════════════════════════════════════════

def _meta_error(data: Dict[str, Any]) -> str:
    err = data.get("error") or {}
    parts = []
    if err.get("message"):
        parts.append(str(err["message"]))
    if err.get("code") is not None:
        parts.append(f"(code {err['code']})")
    if err.get("error_data", {}).get("details"):
        parts.append(err["error_data"]["details"])
    return " ".join(parts) or json.dumps(data)[:300]


async def graph_request(
    method: str,
    path: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Llamada a graph.facebook.com. Levanta 502 con el mensaje textual de Meta,
    porque los códigos de error de WhatsApp sin contexto son incomprensibles.
    """
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=WA_TIMEOUT) as client:
            resp = await client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                params=params,
                json=payload,
            )
    except httpx.HTTPError as e:
        logger.error("[WA] Error de red contra Graph %s: %s", url, e)
        raise HTTPException(status_code=504, detail=f"No se pudo contactar a Meta ({url}): {e}")

    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text[:1000]}

    if resp.status_code >= 400:
        detail = _meta_error(data)
        logger.error("[WA] Graph %s %s -> %s: %s", method, path, resp.status_code, detail)
        raise HTTPException(status_code=502, detail=f"Meta respondió {resp.status_code}: {detail}")
    return data


async def graph_send_message(account: models.WhatsAppAccount, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not account.phone_number_id:
        raise HTTPException(status_code=409, detail="La cuenta no tiene phone_number_id configurado.")
    return await graph_request("POST", f"{account.phone_number_id}/messages", get_account_token(account), payload)


async def graph_upload_media(account: models.WhatsAppAccount, filename: str,
                             content: bytes, mime: str = "application/pdf") -> str:
    """
    Sube un archivo a Graph y devuelve el media_id. Meta lo mantiene 30 días y
    después expira: por eso el reenvío del mismo comprobante vuelve a subir.
    Es multipart, no JSON, así que no pasa por graph_request.
    """
    if not account.phone_number_id:
        raise HTTPException(status_code=409, detail="La cuenta no tiene phone_number_id configurado.")
    url = f"{GRAPH_BASE}/{account.phone_number_id}/media"
    token = get_account_token(account)
    try:
        async with httpx.AsyncClient(timeout=max(WA_TIMEOUT, 60.0)) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                data={"messaging_product": "whatsapp", "filename": filename},
                files={"file": (filename, content, mime)},
            )
    except httpx.HTTPError as e:
        logger.error("[WA] Error de red subiendo media a Graph %s: %s", url, e)
        raise HTTPException(status_code=504, detail=f"No se pudo contactar a Meta para subir el archivo: {e}")

    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text[:1000]}
    if resp.status_code >= 400 or not data.get("id"):
        detail = _meta_error(data)
        logger.error("[WA] Upload media %s -> %s: %s", filename, resp.status_code, detail)
        raise HTTPException(status_code=502, detail=f"Meta rechazó la subida del archivo: {detail}")
    logger.info("[WA] media subida: %s -> %s (%d bytes)", filename, data["id"], len(content))
    return str(data["id"])


def decode_b64_media(b64: Optional[str], filename: str = "") -> bytes:
    """Valida tamaño y que el PDF empiece como PDF antes de gastar un upload."""
    if not b64:
        raise HTTPException(status_code=422, detail="Falta el archivo (media_b64 vacío).")
    # El ERP histórico manda "data:application/pdf;base64,..."; se acepta y se limpia.
    clean = re.sub(r"^data:[^,]*;base64,", "", b64.strip())
    clean = re.sub(r"\s+", "", clean)
    try:
        raw = base64.b64decode(clean + "=" * (-len(clean) % 4), validate=True)
    except Exception:
        raise HTTPException(status_code=422, detail="media_b64 no es base64 válido.")
    limit = int(WA_ERP_MAX_PDF_MB * 1024 * 1024)
    if not raw:
        raise HTTPException(status_code=422, detail="El archivo pesa 0 bytes.")
    if len(raw) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo pesa {len(raw) / 1048576:.1f} MB; el tope es {WA_ERP_MAX_PDF_MB:.0f} MB.",
        )
    if filename.lower().endswith(".pdf") and not raw[:5].startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="El archivo no es un PDF (falta cabecera %PDF).")
    return raw


# ═════════════════════════════════════════════════════════════════════════════
# Conversaciones / ventana de 24 h
# ═════════════════════════════════════════════════════════════════════════════

def find_account(db: Session, account_id: int) -> models.WhatsAppAccount:
    account = (
        db.query(models.WhatsAppAccount)
        .options(joinedload(models.WhatsAppAccount.client))
        .filter(models.WhatsAppAccount.id == account_id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta de WhatsApp inexistente.")
    return account


def get_open_conversation(db: Session, account_id: int, phone: str) -> Optional[models.WhatsAppConversation]:
    """Conversación viva dentro de las 24 h (abierta por el cliente o por nosotros)."""
    return (
        db.query(models.WhatsAppConversation)
        .filter(
            models.WhatsAppConversation.account_id == account_id,
            models.WhatsAppConversation.contact_phone == phone,
            models.WhatsAppConversation.status == "open",
            models.WhatsAppConversation.expires_at > now_utc(),
        )
        .order_by(models.WhatsAppConversation.expires_at.desc())
        .first()
    )


def customer_window_open(conv: Optional[models.WhatsAppConversation]) -> bool:
    """
    True sólo si el CLIENTE escribió en las últimas 24 h. Una conversación que
    iniciamos nosotros con una plantilla NO habilita texto libre: Meta lo
    rechaza con 131026 y el mensaje nunca sale.
    """
    return (
        conv is not None
        and conv.last_inbound_at is not None
        and conv.expires_at is not None
        and conv.expires_at > now_utc()
    )


def touch_conversation(
    db: Session,
    account_id: int,
    phone: str,
    *,
    category: str,
    contact_name: Optional[str] = None,
    billable: Optional[bool] = None,
    preview: Optional[str] = None,
    inbound: bool = False,
) -> models.WhatsAppConversation:
    """
    Devuelve la conversación de destino, creándola si hace falta.
    inbound=True reactiva la ventana (los 24 h vuelven a correr desde ahí).
    Es el único punto que suma contadores de mensaje.
    """
    conv = get_open_conversation(db, account_id, phone)
    if conv is None:
        conv = models.WhatsAppConversation(
            account_id=account_id,
            contact_phone=phone,
            contact_name=contact_name,
            category=category,
            status="open",
            started_at=now_utc(),
            expires_at=now_utc() + timedelta(hours=CONVERSATION_WINDOW_HOURS),
            billable=bool(billable) if billable is not None else category != "service",
            first_message_preview=(preview or "")[:280] or None,
        )
        db.add(conv)
        db.flush()
    else:
        if contact_name and not conv.contact_name:
            conv.contact_name = contact_name

    if inbound:
        conv.last_inbound_at = now_utc()
        conv.expires_at = conv.last_inbound_at + timedelta(hours=CONVERSATION_WINDOW_HOURS)
        conv.inbound_count += 1
        # Un mensaje entrante abre ventana de servicio gratuita
        if conv.status == "open":
            conv.category = "service"
            conv.billable = False
    else:
        conv.outbound_count += 1
    conv.message_count += 1
    return conv


def ensure_month_period(account: models.WhatsAppAccount) -> None:
    """Rotea el contador mensual cuando cambia el mes calendario."""
    today = date.today()
    first = today.replace(day=1)
    if account.period_start is None or account.period_start < first:
        account.period_start = first
        account.messages_sent_this_month = 0


# ═════════════════════════════════════════════════════════════════════════════
# construcción del payload de envío
# ═════════════════════════════════════════════════════════════════════════════

def build_send_payload(
    db: Session,
    account: models.WhatsAppAccount,
    req: Any,
) -> Tuple[Dict[str, Any], str, str]:
    """
    Devuelve (payload, body_legible, categoria_de_pricing).
    Fuera de ventana sólo se permiten plantillas: Meta rechaza el texto libre
    con error 131026 y el mensaje nunca sale, así que lo anticipamos acá.
    """
    to = normalize_wa_phone(req.to)
    if not to:
        raise HTTPException(status_code=422, detail="Destinatario inválido o vacío.")

    msg_type = (req.type or "text").lower()
    common: Dict[str, Any] = {"messaging_product": "whatsapp", "to": to}

    if msg_type == "template":
        if not req.template_name:
            raise HTTPException(status_code=422, detail="type=template requiere template_name.")
        tpl = (
            db.query(models.WhatsAppTemplate)
            .filter(
                models.WhatsAppTemplate.account_id == account.id,
                models.WhatsAppTemplate.name == req.template_name,
            )
            .first()
        )
        if tpl and tpl.status != "APPROVED":
            raise HTTPException(
                status_code=409,
                detail=f"La plantilla '{tpl.name}' está en estado {tpl.status}; Meta sólo envía aprobadas.",
            )
        category = (tpl.category if tpl else "UTILITY").upper()
        if category not in parse_categories(account.allowed_categories):
            raise HTTPException(
                status_code=403,
                detail=f"La categoría {category} no está habilitada para esta cuenta "
                       f"(permitidas: {account.allowed_categories}).",
            )
        template: Dict[str, Any] = {
            "name": req.template_name,
            "language": {"code": req.language or (tpl.language if tpl else "es")},
        }
        if req.components:
            template["components"] = req.components
        common["type"] = "template"
        common["template"] = template
        return common, f"[plantilla {req.template_name}]", category.lower()

    if msg_type not in ("text", "image", "document", "audio", "video", "sticker"):
        raise HTTPException(status_code=422, detail=f"Tipo de mensaje no soportado: {req.type}")

    # Cualquier mensaje que no es plantilla necesita que el cliente haya escrito
    # en las últimas 24 h; una conversación iniciada por nosotros no alcanza.
    if not customer_window_open(get_open_conversation(db, account.id, to)):
        raise HTTPException(
            status_code=409,
            detail=(
                f"No hay ventana abierta con {to}. Fuera de los 24 h desde su último mensaje "
                "entrante sólo se puede escribir con una plantilla aprobada."
            ),
        )

    if msg_type == "text":
        if not req.body:
            raise HTTPException(status_code=422, detail="type=text requiere body.")
        common["type"] = "text"
        common["text"] = {"preview_url": True, "body": req.body[:4096]}
        return common, req.body[:4096], "service"

    if not req.media_url and not req.media_id:
        raise HTTPException(status_code=422, detail=f"type={msg_type} requiere media_url o media_id.")
    node: Dict[str, Any] = {}
    # Meta acepta id O link, nunca los dos: si Support ya subió el PDF prima el id.
    if req.media_id:
        node["id"] = req.media_id
    elif req.media_url:
        node["link"] = req.media_url
    if msg_type == "document" and req.filename:
        node["filename"] = req.filename
    if req.caption and msg_type in ("image", "video", "document"):
        node["caption"] = req.caption[:1024]
    common["type"] = msg_type
    common[msg_type] = node
    return common, req.caption or f"[{msg_type}]", "service"


# ═════════════════════════════════════════════════════════════════════════════
# Serialización
# ═════════════════════════════════════════════════════════════════════════════

def account_out(a: models.WhatsAppAccount) -> schemas.WhatsAppAccountOut:
    overrides = None
    if a.rate_overrides:
        try:
            overrides = json.loads(a.rate_overrides)
        except (ValueError, TypeError):
            overrides = None
    return schemas.WhatsAppAccountOut(
        id=a.id,
        client_id=a.client_id,
        client_name=a.client.razon_social if a.client else None,
        business_id=a.business_id,
        waba_id=a.waba_id,
        phone_number_id=a.phone_number_id,
        display_phone_number=a.display_phone_number,
        verified_name=a.verified_name,
        status=a.status,
        registration_state=a.registration_state,
        quality_rating=a.quality_rating,
        messaging_limit_tier=a.messaging_limit_tier,
        allowed_categories=a.allowed_categories,
        monthly_message_quota=a.monthly_message_quota,
        messages_sent_this_month=a.messages_sent_this_month or 0,
        period_start=a.period_start,
        rate_currency=a.rate_currency,
        rate_overrides=overrides,
        notes=a.notes,
        erp_send_enabled=bool(a.erp_send_enabled),
        erp_invoice_template=a.erp_invoice_template,
        erp_invoice_language=a.erp_invoice_language,
        has_token=bool(a.access_token_enc),
        webhook_verify_token=a.webhook_verify_token,
        created_at=a.created_at,
        connected_at=a.connected_at,
    )


def message_out(m: models.WhatsAppMessage) -> schemas.WhatsAppMessageOut:
    return schemas.WhatsAppMessageOut.model_validate(m)


def conversation_out(c: models.WhatsAppConversation) -> schemas.WhatsAppConversationOut:
    return schemas.WhatsAppConversationOut(
        id=c.id,
        account_id=c.account_id,
        client_name=c.account.client.razon_social if c.account and c.account.client else None,
        contact_phone=c.contact_phone,
        contact_name=c.contact_name,
        category=c.category,
        billable=bool(c.billable),
        status=c.status,
        started_at=c.started_at,
        expires_at=c.expires_at,
        last_inbound_at=c.last_inbound_at,
        message_count=c.message_count or 0,
        outbound_count=c.outbound_count or 0,
        inbound_count=c.inbound_count or 0,
        first_message_preview=c.first_message_preview,
        is_open=bool(c.is_open),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Webhook: firma y procesamiento
# ═════════════════════════════════════════════════════════════════════════════

def verify_signature(raw: bytes, header: Optional[str]) -> bool:
    """X-Hub-Signature-256: sha256=<hex>. Sin WA_APP_SECRET no se puede validar."""
    if not WA_APP_SECRET:
        logger.warning("[WA] WA_APP_SECRET vacío: webhook sin validar firma (NO apto para producción)")
        return os.getenv("WA_ALLOW_UNSIGNED_WEBHOOK", "0") == "1"
    if not header:
        return False
    expected = "sha256=" + hmac.new(WA_APP_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def _resolve_account_from_event(db: Session, phone_number_id: Optional[str]) -> Optional[models.WhatsAppAccount]:
    if not phone_number_id:
        return None
    return (
        db.query(models.WhatsAppAccount)
        .filter(models.WhatsAppAccount.phone_number_id == str(phone_number_id))
        .first()
    )


def process_webhook_payload(db: Session, data: Dict[str, Any], account_hint: Optional[models.WhatsAppAccount] = None) -> int:
    """
    Recorre entry[].changes[].value y aterriza mensajes, estados y cambios de
    plantilla. Devuelve cuántos ítems se procesaron.
    """
    if data.get("object") not in ("whatsapp_business_account", None):
        logger.info("[WA] Webhook de objeto %s (ignorado)", data.get("object"))
    processed = 0

    for entry in data.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            field = change.get("field")
            value = change.get("value", {}) or {}
            meta = value.get("metadata", {}) or {}
            account = account_hint or _resolve_account_from_event(db, meta.get("phone_number_id"))

            if field == "message_template_status_update":
                processed += _handle_template_status(db, value)
                continue
            if account is None:
                logger.warning(
                    "[WA] Webhook para phone_number_id %s sin cuenta dada de alta (¿falta darla de alta en Apollo?)",
                    meta.get("phone_number_id"),
                )
                continue

            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", []) or []}

            if field == "messages":
                processed += _handle_inbound_messages(db, account, value, names)
                processed += _handle_status_updates(db, account, value)

    db.commit()
    return processed


def _handle_inbound_messages(db: Session, account: models.WhatsAppAccount, value: Dict[str, Any],
                             names: Dict[str, Any]) -> int:
    n = 0
    for msg in value.get("messages", []) or []:
        phone = normalize_wa_phone(msg.get("from"))
        if not phone:
            continue
        meta_id = msg.get("id")
        # Meta reenvía el webhook (retry o duplicado): sin esta guarda el mismo
        # mensaje entrante contaría dos veces en la bandeja y en el cierre.
        if meta_id and db.query(models.WhatsAppMessage.id).filter(
            models.WhatsAppMessage.account_id == account.id,
            models.WhatsAppMessage.meta_message_id == meta_id,
        ).first():
            continue
        msg_type = msg.get("type") or "text"
        body = None
        media_url = None
        media_id = None
        if msg_type == "text":
            body = (msg.get("text") or {}).get("body")
        elif msg_type == "button":
            body = (msg.get("button") or {}).get("text")
        elif msg_type == "interactive":
            inter = msg.get("interactive") or {}
            body = json.dumps(inter, ensure_ascii=False)[:2000]
        elif msg_type == "template":
            tpl = msg.get("template") or {}
            body = f"[plantilla {tpl.get('name')}]"
        else:
            node = msg.get(msg_type) or {}
            body = node.get("caption") or node.get("filename") or f"[{msg_type}]"
            media_id = node.get("id")
            media_url = node.get("link")

        contact_name = names.get(msg.get("from")) or None
        conv = touch_conversation(
            db, account.id, phone,
            category="service",
            contact_name=contact_name,
            billable=False,
            preview=body,
            inbound=True,
        )
        db.add(models.WhatsAppMessage(
            account_id=account.id,
            conversation_id=conv.id,
            direction="inbound",
            contact_phone=phone,
            contact_name=contact_name,
            message_type=msg_type,
            body_text=body,
            media_id=media_id,
            media_url=media_url,
            meta_message_id=msg.get("id"),
            status="received",
            pricing_category="service",
            billable=False,
            created_at=epoch_to_naive(msg.get("timestamp")) or now_utc(),
            wa_timestamp=epoch_to_naive(msg.get("timestamp")),
        ))
        n += 1
    return n


def _handle_status_updates(db: Session, account: models.WhatsAppAccount, value: Dict[str, Any]) -> int:
    """statuses llega en el mismo field 'messages' que los entrantes."""
    n = 0
    rates = get_rates(account)
    rank = {"sent": 1, "delivered": 2, "read": 3, "failed": 4}
    for st in value.get("statuses", []) or []:
        wamid = st.get("id")
        if not wamid:
            continue
        msg = (
            db.query(models.WhatsAppMessage)
            .filter(
                models.WhatsAppMessage.account_id == account.id,
                models.WhatsAppMessage.meta_message_id == wamid,
            )
            .first()
        )
        new_status = st.get("status")
        pricing = st.get("pricing") or {}
        category = (pricing.get("category") or "").lower() or None
        if msg is None:
            # Mensaje enviado desde fuera de Apollo (otro panel, Business App):
            # se registra igual para no perder consumo facturable.
            phone = normalize_wa_phone(st.get("recipient_id"))
            if not phone:
                continue
            conv = touch_conversation(db, account.id, phone, category=category or "utility", billable=bool(pricing.get("billable")))
            msg = models.WhatsAppMessage(
                account_id=account.id,
                conversation_id=conv.id,
                direction="outbound",
                contact_phone=phone,
                message_type="unknown",
                body_text="[enviado fuera de Apollo]",
                meta_message_id=wamid,
                status=new_status or "sent",
                created_at=now_utc(),
            )
            db.add(msg)
        else:
            prev = rank.get(msg.status or "", 0)
            if rank.get(new_status or "", 0) >= prev:
                msg.status = new_status
                msg.status_updated_at = now_utc()

        if category:
            msg.pricing_category = category
        if "billable" in pricing:
            msg.billable = bool(pricing["billable"])
        if msg.billable and category:
            msg.cost_amount = rates.get(category, 0.0)
        errors = st.get("errors") or []
        if new_status == "failed" and errors:
            msg.error_code = str(errors[0].get("code"))
            msg.error_title = errors[0].get("title")
        n += 1
    return n


# Meta envía el evento de plantilla como texto ("APPROVED"); la vieja API
# On-Premises usaba códigos numéricos. Se aceptan las dos formas para no dejar
# una plantilla aprobada congelada en PENDING por no entender el webhook.
_TEMPLATE_EVENTS = {1: "REJECTED", 2: "PENDING", 3: "APPROVED", 4: "DELETED", 5: "EDITED"}

# Único texto que puede quedar guardado en WhatsAppTemplate.status. Si Meta
# publica un evento nuevo se descarta, en vez de pisar el estado con un valor
# desconocido que después bloquea el envío (sólo se manda con status=APPROVED).
_TEMPLATE_STATUSES = {"PENDING", "APPROVED", "REJECTED", "DISABLED", "DELETED", "ARCHIVED", "EDITED"}


def _lang_root(code: Optional[str]) -> str:
    """'es_AR' / 'es-AR' / 'es' -> 'es' (Meta no es consistente entre endpoints)."""
    return (code or "").replace("-", "_").split("_")[0].lower()


def _handle_template_status(db: Session, value: Dict[str, Any]) -> int:
    raw_event = value.get("event")
    status = raw_event.upper() if isinstance(raw_event, str) else _TEMPLATE_EVENTS.get(raw_event)
    if status not in _TEMPLATE_STATUSES:
        logger.warning("[WA] Webhook de plantilla con evento no reconocido: %r", raw_event)
        return 0

    meta_id = str(value.get("message_template_id") or "")
    name = value.get("message_template_name")
    lang_root = _lang_root(value.get("message_template_language"))

    tpl = db.query(models.WhatsAppTemplate).filter(
        models.WhatsAppTemplate.meta_template_id == meta_id).first() if meta_id else None
    if tpl is None and name:
        # Creadas en WhatsApp Manager o con push_to_meta=False: no traen
        # meta_template_id, así que se emparejan por nombre + idioma.
        tpl = next((c for c in db.query(models.WhatsAppTemplate).filter(
            models.WhatsAppTemplate.name == name).all() if _lang_root(c.language) == lang_root), None)
    if tpl is None:
        logger.info("[WA] Cambio de estado de plantilla desconocida %s (%s)", meta_id, name)
        return 0

    tpl.status = status
    if meta_id and not tpl.meta_template_id:
        tpl.meta_template_id = meta_id
    if value.get("reason"):
        tpl.rejection_reason = str(value["reason"])[:1000]
    tpl.updated_at = now_utc()
    logger.info("[WA] Plantilla %s (%s/%s) -> %s", meta_id or tpl.meta_template_id,
                tpl.name, tpl.language, tpl.status)
    return 1


# ═════════════════════════════════════════════════════════════════════════════
# Envío (helper reutilizable, también desde el outbox)
# ═════════════════════════════════════════════════════════════════════════════

class WhatsAppSendable:
    """Vista mínima de un pedido de envío (compatibiliza con schemas.WhatsAppSendRequest)."""

    def __init__(self, **kw: Any):
        self.__dict__.update(kw)


async def perform_send(
    db: Session,
    account: models.WhatsAppAccount,
    req: Any,
    *,
    source: str = "api",
    channel: Optional[str] = None,
) -> models.WhatsAppMessage:
    """Valida cuota, manda a Meta y registra el mensaje con su estado inicial."""
    to = normalize_wa_phone(req.to)

    # Un puesto que se cayó a mitad de envío reintenta con la misma clave:
    # no debe gastar un mensaje de más del cliente.
    idem = (getattr(req, "idempotency_key", None) or "").strip() or None
    if idem:
        prev = find_idempotent(db, account.id, idem)
        if prev is not None:
            logger.info("[WA] Reenvío ignorado: key=%s ya produjo el mensaje %s", idem, prev.id)
            return prev

    # El PDF puede venir en base64 desde el puesto: se sube a Graph acá y el
    # payload del mensaje usa el media_id resultante.
    await resolve_media_id(account, req)

    payload, preview, pricing_cat = build_send_payload(db, account, req)

    ensure_month_period(account)
    if account.monthly_message_quota and (account.messages_sent_this_month or 0) >= account.monthly_message_quota:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Se alcanzó el tope mensual de {account.monthly_message_quota} envíos "
                f"del período {account.period_start}. Aumentar la cuota o esperar al cierre."
            ),
        )

    msg = models.WhatsAppMessage(
        account_id=account.id,
        client_id=account.client_id,
        contact_phone=to,
        contact_name=getattr(req, "contact_name", None),
        message_type=(req.type or "text").lower(),
        body_text=preview,
        template_name=getattr(req, "template_name", None),
        media_url=getattr(req, "media_url", None),
        media_id=getattr(req, "media_id", None),
        media_mime="application/pdf" if (getattr(req, "media_id", None)
                                        and (req.type or "text").lower() == "document") else None,
        direction="outbound",
        status="queued",
        pricing_category=pricing_cat,
        source_channel=channel or "panel",
        erp_serial=getattr(req, "serial", None),
        erp_operator=getattr(req, "operator", None),
        erp_doc_ref=getattr(req, "doc_ref", None),
        idempotency_key=idem,
        created_at=now_utc(),
    )
    # touch_conversation es el único que cuenta mensajes, así no se duplica acá
    open_conv = get_open_conversation(db, account.id, to)
    # Estimación del cargo: Meta lo confirma con pricing.billable en el webhook de
    # estados. Desde 07/2025 se factura por mensaje entregado, pero UTILITY y
    # AUTHENTICATION enviadas dentro de la ventana que el cliente abrió son gratis.
    if pricing_cat == "service":
        msg.billable = False
    elif pricing_cat == "marketing":
        msg.billable = True
    else:
        msg.billable = not customer_window_open(open_conv)

    conv = touch_conversation(
        db, account.id, to,
        category=pricing_cat or "utility",
        contact_name=msg.contact_name,
        billable=(pricing_cat != "service"),
        preview=preview,
    )
    msg.conversation_id = conv.id
    if not msg.contact_name and conv.contact_name:
        msg.contact_name = conv.contact_name
    db.add(msg)
    db.flush()

    try:
        resp = await graph_send_message(account, payload)
    except HTTPException:
        msg.status = "failed"
        msg.error_title = "Rechazado por Meta al enviar"
        db.commit()
        raise

    rid = (resp.get("messages") or [{}])[0]
    msg.meta_message_id = rid.get("id")
    msg.status = "sent"
    msg.wa_timestamp = now_utc()
    account.messages_sent_this_month = (account.messages_sent_this_month or 0) + 1
    extra: Dict[str, Any] = {"source": source}
    if channel:
        extra["channel"] = channel
    if getattr(req, "ref_ticket_id", None):
        extra["ref_ticket_id"] = req.ref_ticket_id
    msg.payload_json = json.dumps(extra)
    db.commit()
    db.refresh(msg)
    logger.info("[WA] enviado cuenta=%s -> %s id=%s", account.id, to, msg.meta_message_id)
    return msg


# ═════════════════════════════════════════════════════════════════════════════
# Canal ERP (ApolloGesCom): credencial por cliente, firma HMAC y comprobantes
# ═════════════════════════════════════════════════════════════════════════════

def ensure_erp_columns() -> None:
    """
    create_all() no agrega columnas a una tabla que ya existe, y la auditoría del
    canal ERP necesita las suyas. ALTER/CREATE idempotentes (patrón de main.py);
    en SQLite no aplica: ahí create_all sí levanta el modelo completo.
    """
    from database import engine
    from sqlalchemy import text

    if engine.dialect.name != "postgresql":
        return
    stmts = [
        "ALTER TABLE whatsapp_accounts ADD COLUMN IF NOT EXISTS erp_send_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE whatsapp_accounts ADD COLUMN IF NOT EXISTS erp_invoice_template VARCHAR",
        "ALTER TABLE whatsapp_accounts ADD COLUMN IF NOT EXISTS erp_invoice_language VARCHAR",
        "ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS client_id INTEGER",
        "ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS source_channel VARCHAR",
        "ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS erp_serial VARCHAR",
        "ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS erp_operator VARCHAR",
        "ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS erp_doc_ref VARCHAR",
        "ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_accounts_erp_send_enabled ON whatsapp_accounts (erp_send_enabled)",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_client_id ON whatsapp_messages (client_id)",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_source_channel ON whatsapp_messages (source_channel)",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_erp_serial ON whatsapp_messages (erp_serial)",
        # Anti-duplicado: sólo cuando el puesto manda clave. Los envíos del panel
        # y del outbox quedan con idempotency_key NULL y no chocan entre sí.
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_whatsapp_messages_idem ON whatsapp_messages "
        "(account_id, idempotency_key) WHERE idempotency_key IS NOT NULL",
    ]
    try:
        with engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))
        logger.info("[WA/ERP] Columnas e índices del canal ERP asegurados")
    except Exception as e:
        logger.warning("[WA/ERP] No se pudieron asegurar las columnas del canal ERP: %s", e)


def find_idempotent(db: Session, account_id: int, key: Optional[str]) -> Optional[models.WhatsAppMessage]:
    if not key:
        return None
    return db.query(models.WhatsAppMessage).filter(
        models.WhatsAppMessage.account_id == account_id,
        models.WhatsAppMessage.idempotency_key == key,
    ).first()


async def resolve_media_id(account: models.WhatsAppAccount, req: Any) -> Optional[str]:
    """Convierte media_b64 en media_id de Graph. Si ya trae id, no hace nada."""
    b64 = getattr(req, "media_b64", None)
    if not b64 or getattr(req, "media_id", None):
        return None
    fname = safe_media_name(getattr(req, "filename", None))
    raw = decode_b64_media(b64, fname)
    media_id = await graph_upload_media(account, fname, raw, "application/pdf")
    try:
        req.media_id = media_id
        req.media_b64 = None
    except (AttributeError, TypeError):
        pass
    return media_id


def safe_media_name(name: Optional[str], fallback: str = "documento.pdf") -> str:
    """
    El nombre viaja a Meta y se muestra al destinatario: sin rutas ni caracteres
    raros. Un puesto mal configurado no puede escribir '../' o un nombre con salto
    de línea en el comprobante del cliente.
    """
    base = (name or "").replace("\\", "/").split("/")[-1].strip()
    base = re.sub(r"[^\w()\-. ]+", "_", base, flags=re.UNICODE)[:120].strip()
    if not base:
        base = fallback
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    return base


def build_invoice_components(media_ref: Dict[str, str], filename: str,
                            body_vars: List[str]) -> List[Dict[str, Any]]:
    """
    Plantilla con HEADER de documento: el PDF va adjunto en la cabecera y el cuerpo
    lleva {{1}}..{{n}}. Meta rechaza la plantilla si faltan variables, así que sólo
    se agregan cuando el llamante las pasa.

    media_ref es {"id": ...} si Support subió el PDF o {"link": ...} si el puesto
    ya lo dejó en un URL público (Meta descarga del link y lo cachea ~30 días).
    """
    comps: List[Dict[str, Any]] = [{
        "type": "header",
        "parameters": [{
            "type": "document",
            "document": dict(media_ref, filename=filename),
        }],
    }]
    vars_clean = [str(v or "").strip()[:600] for v in (body_vars or []) if str(v or "").strip()]
    if vars_clean:
        comps.append({
            "type": "body",
            "parameters": [{"type": "text", "text": v} for v in vars_clean[:10]],
        })
    return comps


def estimate_cost(account: Optional[models.WhatsAppAccount], category: Optional[str],
                  billable: bool) -> float:
    """Costo esperado ANTES del webhook: sirve para avisar al puesto, no para facturar."""
    if not billable or not category:
        return 0.0
    rates = get_rates(account) if account else DEFAULT_RATES
    return float(rates.get(str(category).lower(), 0.0) or 0.0)


# ── Firma del pedido ERP ─────────────────────────────────────────────────────
# base = prefijo + METHOD + path + timestamp + nonce + sha256(body), HMAC-SHA256
# con la clave del cliente (Client.apikey_apollo). El timestamp acota la ventana
# y el nonce se guarda un rato para que un pedido robado no se vuelva a usar.

_ERP_NONCES: Dict[str, datetime] = {}


def erp_base_string(method: str, path: str, ts: str, nonce: str, body: bytes) -> str:
    body_hash = hashlib.sha256(body or b"").hexdigest()
    return "\n".join([
        WA_ERP_SIGNATURE_PREFIX,
        (method or "POST").upper(),
        path,
        str(ts),
        nonce,
        body_hash,
    ])


def erp_signature(secret: str, method: str, path: str, ts: str, nonce: str, body: bytes) -> str:
    base = erp_base_string(method, path, ts, nonce, body)
    return hmac.new(secret.encode("utf-8"), base.encode("utf-8"), hashlib.sha256).hexdigest()


def _nonce_used_or_remember(nonce: str) -> bool:
    now = now_utc()
    if len(_ERP_NONCES) > 8192:
        for k in [k for k, exp in _ERP_NONCES.items() if exp <= now]:
            _ERP_NONCES.pop(k, None)
    expiry = _ERP_NONCES.get(nonce)
    if expiry is not None and expiry > now:
        return True
    _ERP_NONCES[nonce] = now + timedelta(seconds=WA_ERP_NONCE_TTL)
    return False


async def require_erp_client(
    request: Request,
    db: Session = Depends(get_db),
) -> Tuple[models.Client, models.WhatsAppAccount]:
    """
    Autenticación del puesto del ERP. No usa JWT: el puesto no es un usuario del
    portal. Devuelve el cliente y su línea habilitada, o levanta 4xx con el motivo
    exacto para que Soporte vea qué falta sin abrir el código.
    """
    headers = request.headers
    code = (headers.get("X-Apollo-Code") or "").strip().upper()
    ts = (headers.get("X-Apollo-Timestamp") or "").strip()
    nonce = (headers.get("X-Apollo-Nonce") or "").strip().lower()
    signature = (headers.get("X-Apollo-Signature") or "").strip().lower()
    serial = (headers.get("X-Apollo-Serial") or "").strip()

    missing = [n for n, v in (("X-Apollo-Code", code), ("X-Apollo-Timestamp", ts),
                              ("X-Apollo-Nonce", nonce), ("X-Apollo-Signature", signature)) if not v]
    if missing:
        raise HTTPException(status_code=401, detail="Faltan headers de firma: " + ", ".join(missing))
    if not ts.isdigit():
        raise HTTPException(status_code=401, detail="X-Apollo-Timestamp debe ser epoch en segundos.")
    skew = abs(now_utc().timestamp() - float(ts))
    if skew > WA_ERP_MAX_SKEW:
        raise HTTPException(
            status_code=401,
            detail=(f"Reloj del puesto desincronizado ({skew:.0f} s de diferencia; "
                    f"tope {WA_ERP_MAX_SKEW} s)."),
        )
    if len(nonce) < 16 or not re.fullmatch(r"[0-9a-f]+", nonce):
        raise HTTPException(status_code=401, detail="X-Apollo-Nonce debe ser hexadecimal de 16+ caracteres.")
    if _nonce_used_or_remember(nonce):
        logger.warning("[WA/ERP] Noné repetido desde client=%s", code)
        raise HTTPException(status_code=401, detail="Noné ya utilizado (pedido duplicado o replay).")

    client = db.query(models.Client).filter(
        func.upper(func.coalesce(models.Client.codigo, "")) == code).first()
    if not client:
        raise HTTPException(status_code=401, detail=f"El código {code} no está dado de alta en Support.")
    if client.activo is False:
        raise HTTPException(status_code=403, detail=f"El cliente {code} está de baja en Support.")
    secret = (client.apikey_apollo or "").strip()
    if not secret:
        raise HTTPException(
            status_code=401,
            detail=f"El cliente {code} no tiene clave de API. Pedí el alta del canal ERP en Support.",
        )

    body = await request.body()
    expected = erp_signature(secret, request.method, request.url.path, ts, nonce, body)
    if not hmac.compare_digest(expected, signature):
        logger.warning("[WA/ERP] Firma inválida del cliente %s en %s", code, request.url.path)
        raise HTTPException(status_code=401, detail="Firma inválida (clave, body o URL no coinciden).")

    account = (
        db.query(models.WhatsAppAccount)
        .filter(
            models.WhatsAppAccount.client_id == client.id,
            models.WhatsAppAccount.status.in_(["connected", "registered"]),
        )
        .order_by(models.WhatsAppAccount.id).first()
    )
    if account is None:
        raise HTTPException(
            status_code=409,
            detail=f"{code} no tiene línea de WhatsApp activa en Support.",
        )
    if not account.erp_send_enabled:
        raise HTTPException(
            status_code=403,
            detail=f"La línea {account.display_phone_number} no está habilitada para el ERP.",
        )
    if serial and account.client_id != client.id:
        raise HTTPException(status_code=403, detail="El serial no pertenece a esta línea.")
    return client, account


def _erp_target_account(db: Session, client: models.Client) -> Optional[models.WhatsAppAccount]:
    """La línea del cliente, exista o no (para bootstrap y reportes de uso)."""
    return (
        db.query(models.WhatsAppAccount)
        .filter(models.WhatsAppAccount.client_id == client.id)
        .order_by(models.WhatsAppAccount.id).first()
    )


def erp_new_api_key() -> str:
    return secrets.token_hex(24)


def erp_norm_serial(value: Optional[str]) -> str:
    """Los l_number vienen de DBF: pueden traer espacios o mayúsculas distintas."""
    return re.sub(r"\s+", "", str(value or "")).upper()


def erp_client_licenses(codigo: str) -> List[Dict[str, Any]]:
    """
    Licencias del cliente en misi_licenses. Falla cerrado: si el server de licencias
    no contesta no se entrega ninguna clave, que es justamente lo que hay que
    garantizar cuando el cliente reclama "a mí me activaron la línea sin licencia".
    """
    try:
        from erp_licensing import fetch_licenses_by_client
        return list(fetch_licenses_by_client(codigo) or [])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[WA/ERP] No se pudo consultar misi_licenses de %s: %s", codigo, e)
        raise HTTPException(
            status_code=502,
            detail="No se pudo verificar la licencia contra el servidor de licencias. Reintentá.",
        )


def erp_license_for(licenses: List[Dict[str, Any]], serial: str) -> Optional[Dict[str, Any]]:
    wanted = erp_norm_serial(serial)
    for lic in licenses or []:
        if erp_norm_serial(lic.get("l_number")) == wanted:
            return lic
    return None


def _erp_audit(db: Session, client: models.Client, action: str,
               serial: Optional[str], operator: Optional[str]) -> None:
    """
    Deja rastro en access_logs de quién pidió credenciales. Si un cliente niega
    haber habilitado el canal, acá está la fecha y el serial con el que se pidió.
    Commit propio: los caminos de rechazo levantan HTTPException después y el
    registro tiene que quedar igual.
    """
    db.add(models.AccessLog(
        client_id=client.id,
        action=f"{action} serial={serial or '-'} operador={operator or '-'}"[:250],
    ))
    db.commit()


def _erp_usage(db: Session, client: models.Client, start: date, end: date,
               serial: Optional[str] = None, limit: int = 200) -> schemas.WhatsAppErpUsageReport:
    """
    Consumo del cliente en un rango, con el detalle por serial/operador/comprobante
    que hace falta cuando el cliente discute una factura de fin de mes.
    """
    lo = datetime.combine(start, datetime.min.time())
    hi = datetime.combine(end, datetime.max.time())
    REACHED = ("delivered", "read")

    def filtered(*extra):
        q = db.query(models.WhatsAppMessage).filter(
            models.WhatsAppMessage.client_id == client.id,
            models.WhatsAppMessage.direction == "outbound",
            models.WhatsAppMessage.created_at >= lo,
            models.WhatsAppMessage.created_at <= hi,
        )
        if serial:
            q = q.filter(models.WhatsAppMessage.erp_serial == serial)
        for cond in extra:
            q = q.filter(cond)
        return q

    sent = filtered().count()
    billable_q = filtered(models.WhatsAppMessage.status.in_(list(REACHED)),
                          models.WhatsAppMessage.billable.is_(True))
    billable = billable_q.count()

    account = _erp_target_account(db, client)
    rates = get_rates(account) if account else DEFAULT_RATES
    agg = (
        db.query(models.WhatsAppMessage.pricing_category, func.count(models.WhatsAppMessage.id))
        .filter(
            models.WhatsAppMessage.client_id == client.id,
            models.WhatsAppMessage.direction == "outbound",
            models.WhatsAppMessage.created_at >= lo,
            models.WhatsAppMessage.created_at <= hi,
            models.WhatsAppMessage.status.in_(list(REACHED)),
            models.WhatsAppMessage.billable.is_(True),
        )
        .group_by(models.WhatsAppMessage.pricing_category).all()
    )
    cost = round(sum(int(n) * float(rates.get(str(cat or "").lower(), 0.0) or 0.0)
                     for cat, n in agg), 4)

    serial_q = (
        db.query(models.WhatsAppMessage.erp_serial, func.count(models.WhatsAppMessage.id))
        .filter(
            models.WhatsAppMessage.client_id == client.id,
            models.WhatsAppMessage.direction == "outbound",
            models.WhatsAppMessage.created_at >= lo,
            models.WhatsAppMessage.created_at <= hi,
        )
        .group_by(models.WhatsAppMessage.erp_serial).all()
    )
    by_serial = {(s or "sin serial"): int(n) for s, n in serial_q}

    rows = filtered().order_by(models.WhatsAppMessage.created_at.desc()).limit(limit).all()
    pct = WA_MARKUP_PCT
    return schemas.WhatsAppErpUsageReport(
        client_id=client.id,
        client_name=client.razon_social,
        period_start=start,
        period_end=end,
        sent_total=sent,
        billable_total=billable,
        cost_amount=cost,
        markup_pct=pct,
        amount_to_invoice=round(cost * (1 + pct / 100.0), 4),
        currency=(account.rate_currency if account and account.rate_currency else "USD"),
        by_serial=by_serial,
        rows=[
            schemas.WhatsAppErpUsageRow(
                id=m.id,
                created_at=m.created_at,
                serial=m.erp_serial,
                operator=m.erp_operator,
                doc_ref=m.erp_doc_ref,
                contact_phone=m.contact_phone,
                template_name=m.template_name,
                message_type=m.message_type,
                status=m.status,
                pricing_category=m.pricing_category,
                billable=bool(m.billable),
                cost_amount=m.cost_amount,
            )
            for m in rows
        ],
    )


async def erp_send_document(
    db: Session,
    account: models.WhatsAppAccount,
    payload: schemas.WhatsAppErpSendIn,
    *,
    client: models.Client,
    serial: Optional[str],
    operator: Optional[str],
) -> Tuple[models.WhatsAppMessage, str, bool]:
    """
    Envío de un comprobante del ERP. Devuelve (mensaje, canal usado, duplicado).

    mode=auto: si el cliente escribió en las últimas 24 h sale como documento
    (categoría service, sin cargo de plantilla); si no, sale con la plantilla de
    factura aprobada, que es la única forma que Meta permite para abrir de cero.
    """
    to = normalize_wa_phone(payload.to)
    if not to:
        raise HTTPException(status_code=422, detail="Destinatario inválido o vacío.")

    idem = (payload.idempotency_key or "").strip() or None
    prev = find_idempotent(db, account.id, idem)
    if prev is not None:
        logger.info("[WA/ERP] key=%s ya envió el mensaje %s (no se repite)", idem, prev.id)
        return prev, (prev.message_type or "template"), True

    doc_ref = (payload.doc_ref or "").strip()[:120] or None
    filename = safe_media_name(payload.filename, fallback=(doc_ref or "documento") + ".pdf")
    if not payload.media_b64 and not payload.media_url:
        raise HTTPException(
            status_code=422,
            detail="No se recibió el archivo: media_b64 (PDF del puesto) o media_url.",
        )

    mode = (payload.mode or "auto").lower()
    conv = get_open_conversation(db, account.id, to)
    if mode == "auto":
        mode = "document" if customer_window_open(conv) else "template"
    if mode not in ("document", "template"):
        raise HTTPException(status_code=422, detail=f"mode inválido: {payload.mode}")

    media_id = await resolve_media_id(
        account, WhatsAppSendable(media_b64=payload.media_b64, filename=filename,
                                  media_id=None, media_url=payload.media_url))

    if mode == "document":
        req = WhatsAppSendable(
            to=to, type="document", media_id=media_id, media_url=payload.media_url,
            filename=filename, caption=payload.caption, contact_name=payload.contact_name,
            serial=serial, operator=operator, doc_ref=doc_ref, idempotency_key=idem,
        )
    else:
        tpl_name = (payload.template_name or account.erp_invoice_template
                    or WA_ERP_INVOICE_TEMPLATE)
        lang = (payload.language or account.erp_invoice_language or WA_ERP_INVOICE_LANG)
        if media_id:
            media_ref = {"id": media_id}
        elif payload.media_url:
            media_ref = {"link": payload.media_url}
        else:
            raise HTTPException(
                status_code=422,
                detail="La plantilla de factura adjunta el PDF: hace falta media_b64 o media_url.",
            )
        vars_ = payload.template_vars or [
            doc_ref or filename,
            (payload.contact_name or client.razon_social or "")[:600],
            now_utc().strftime("%d/%m/%Y"),
        ]
        req = WhatsAppSendable(
            to=to, type="template", template_name=tpl_name, language=lang,
            components=build_invoice_components(media_ref, filename, vars_),
            media_id=media_id,
            media_url=payload.media_url if not media_id else None,
            contact_name=payload.contact_name, serial=serial, operator=operator,
            doc_ref=doc_ref, idempotency_key=idem,
        )

    msg = await perform_send(db, account, req, source=f"erp:{serial or 'sin-serial'}",
                            channel="erp")
    return msg, mode, False


# ═════════════════════════════════════════════════════════════════════════════
# Cableado de dependencias y registro de rutas (patrón de agenda.py)
# ═════════════════════════════════════════════════════════════════════════════

def setup_whatsapp(app: FastAPI, get_current_user, gesacti_key: Optional[str] = None) -> None:
    """
    Registra las rutas del módulo. Llamar desde main.py tras crear `app`.
    gesacti_key: la clave de la que ya usa /api/clients/gesacti/*; la reutilizamos
    para /erp/bootstrap, que es el único punto donde un puesto pide su secreto HMAC.
    """
    global _get_current_user
    _get_current_user = get_current_user
    _gesacti_key = gesacti_key or os.getenv("GESACTI_SYNC_KEY", "")

    def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
        if getattr(current_user, "rol", None) != "admin":
            raise HTTPException(status_code=403, detail="Se requiere rol admin para gestionar WhatsApp.")
        return current_user

    # ── Webhook (público, validado por firma) ────────────────────────────────

    @app.get("/api/whatsapp/webhook", response_class=PlainTextResponse, tags=["WhatsApp"])
    async def webhook_verify(
        hub_mode: str = Query(None, alias="hub.mode"),
        hub_verify_token: str = Query(None, alias="hub.verify_token"),
        hub_challenge: str = Query(None, alias="hub.challenge"),
        db: Session = Depends(get_db),
    ):
        """Challenge que Meta golpea al configurar la suscripción."""
        if hub_mode != "subscribe":
            raise HTTPException(status_code=400, detail="hub.mode inválido.")
        candidates = {WA_VERIFY_TOKEN} if WA_VERIFY_TOKEN else set()
        if hub_verify_token:
            rows = db.query(models.WhatsAppAccount.webhook_verify_token).all()
            candidates |= {r[0] for r in rows if r[0]}
            if hub_verify_token in candidates:
                logger.info("[WA] Webhook verificado para token ***%s", hub_verify_token[-4:])
                return hub_challenge or ""
        logger.warning("[WA] Intento de verificación de webhook con token no reconocido")
        raise HTTPException(status_code=403, detail="verify_token no coincide.")

    @app.post("/api/whatsapp/webhook", tags=["WhatsApp"])
    async def webhook_receive(request: Request, db: Session = Depends(get_db)):
        """
        Meta exige HTTP < 200 ó > 20 s para reintentar: siempre respondemos 200
        y el procesamiento pesado va a cola (whatsapp_webhook_events).
        """
        raw = await request.body()
        header = request.headers.get("X-Hub-Signature-256")
        signature_ok = verify_signature(raw, header)
        if not signature_ok:
            logger.warning("[WA] Webhook rechazado por firma inválida (%s bytes)", len(raw))
            raise HTTPException(status_code=401, detail="Firma inválida.")

        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Body no es JSON válido.")

        meta = (((((data.get("entry") or [{}])[0]).get("changes") or [{}])[0]).get("value") or {})
        pnid = ((meta.get("metadata") or {}).get("phone_number_id")) or None
        account = _resolve_account_from_event(db, pnid)
        fields = [c.get("field") for c in (((data.get("entry") or [{}])[0]).get("changes") or [])]
        evt = models.WhatsAppWebhookEvent(
            account_id=account.id if account else None,
            phone_number_id=pnid,
            event_type=",".join([f for f in fields if f]) or None,
            payload=raw.decode("utf-8", errors="replace")[:200000],
            signature_ok=True,
        )
        db.add(evt)
        db.commit()
        db.refresh(evt)

        try:
            n = process_webhook_payload(db, data, account)
            evt.processed = True
            evt.processed_at = now_utc()
            evt.attempts = (evt.attempts or 0) + 1
            db.commit()
            logger.info("[WA] webhook procesado: %d ítems (cuenta=%s)", n, account.id if account else None)
        except Exception as e:  # noqa: BLE001 - el evento ya quedó guardado para re-procesar
            evt.attempts = (evt.attempts or 0) + 1
            evt.error_message = str(e)[:1000]
            evt.processed = False
            db.commit()
            logger.exception("[WA] falló el procesamiento del webhook, encola para reintento")
        return {"status": "ok"}

    # ── Cuentas ──────────────────────────────────────────────────────────────

    @router.get("/accounts", response_model=List[schemas.WhatsAppAccountOut])
    def list_accounts(
        client_id: Optional[int] = None,
        status_f: Optional[str] = Query(None, alias="status"),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        q = db.query(models.WhatsAppAccount).options(joinedload(models.WhatsAppAccount.client))
        if client_id:
            q = q.filter(models.WhatsAppAccount.client_id == client_id)
        if status_f:
            q = q.filter(models.WhatsAppAccount.status == status_f)
        return [account_out(a) for a in q.order_by(models.WhatsAppAccount.id).all()]

    @router.get("/accounts/{account_id}", response_model=schemas.WhatsAppAccountOut)
    def get_account(
        account_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        return account_out(find_account(db, account_id))

    @router.post("/accounts", response_model=schemas.WhatsAppAccountOut)
    def create_account(
        payload: schemas.WhatsAppAccountCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        client = db.query(models.Client).filter(models.Client.id == payload.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="El cliente indicado no existe.")
        if payload.phone_number_id:
            dup = db.query(models.WhatsAppAccount).filter(
                models.WhatsAppAccount.phone_number_id == payload.phone_number_id).first()
            if dup:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ese phone_number_id ya está cargado en la cuenta {dup.id} (cliente {dup.client_id}).",
                )
        account = models.WhatsAppAccount(
            client_id=payload.client_id,
            business_id=payload.business_id,
            waba_id=payload.waba_id,
            phone_number_id=payload.phone_number_id,
            display_phone_number=normalize_wa_phone(payload.display_phone_number) or None,
            verified_name=payload.verified_name,
            access_token_enc=encrypt_secret(payload.access_token),
            pin=payload.pin,
            webhook_verify_token=secrets.token_urlsafe(24),
            status="pending",
            allowed_categories=payload.allowed_categories or "UTILITY,SERVICE",
            monthly_message_quota=payload.monthly_message_quota,
            period_start=date.today().replace(day=1),
            messages_sent_this_month=0,
            rate_currency=payload.rate_currency or "USD",
            rate_overrides=json.dumps(payload.rate_overrides) if payload.rate_overrides else None,
            notes=payload.notes,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        logger.info("[WA] alta cuenta id=%s cliente=%s %s", account.id, client.codigo, account.display_phone_number)
        return account_out(account)

    @router.put("/accounts/{account_id}", response_model=schemas.WhatsAppAccountOut)
    def update_account(
        account_id: int,
        payload: schemas.WhatsAppAccountUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        account = find_account(db, account_id)
        data = payload.model_dump(exclude_unset=True)
        if "access_token" in data:
            token = data.pop("access_token")
            account.access_token_enc = encrypt_secret(token) if token else None
        if "phone_number_id" in data and data["phone_number_id"]:
            dup = db.query(models.WhatsAppAccount).filter(
                models.WhatsAppAccount.phone_number_id == data["phone_number_id"],
                models.WhatsAppAccount.id != account_id,
            ).first()
            if dup:
                raise HTTPException(status_code=409, detail=f"phone_number_id ya usado por la cuenta {dup.id}.")
        if "rate_overrides" in data:
            ro = data.pop("rate_overrides")
            account.rate_overrides = json.dumps(ro) if ro else None
        if "display_phone_number" in data and data["display_phone_number"]:
            data["display_phone_number"] = normalize_wa_phone(data["display_phone_number"])
        for k, v in data.items():
            setattr(account, k, v)
        account.updated_at = now_utc()
        db.commit()
        db.refresh(account)
        return account_out(account)

    @router.delete("/accounts/{account_id}")
    def delete_account(
        account_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        """Baja del registro local. NO desregistra el número en Meta (eso es destructivo)."""
        account = find_account(db, account_id)
        account.status = "disabled"
        account.updated_at = now_utc()
        db.commit()
        return {"status": "disabled", "id": account_id,
                "detalle": "Cuenta desactivada localmente. El historial de mensajes se conserva."}

    @router.post("/accounts/{account_id}/test")
    async def test_account(
        account_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        """Pregunta a Meta por el número: comprueba token, registro y límites."""
        account = find_account(db, account_id)
        if not account.phone_number_id:
            raise HTTPException(status_code=409, detail="Falta el phone_number_id.")
        data = await graph_request(
            "GET", account.phone_number_id, get_account_token(account),
            params={
                "fields": "id,display_phone_number,verified_name,quality_rating,"
                          "messaging_limit_tier,platform_type,name_verification_status",
            },
        )
        account.quality_rating = (data.get("quality_rating") or "").lower() or account.quality_rating
        account.messaging_limit_tier = data.get("messaging_limit_tier") or account.messaging_limit_tier
        account.verified_name = data.get("verified_name") or account.verified_name
        account.status = "connected"
        account.connected_at = account.connected_at or now_utc()
        account.updated_at = now_utc()
        db.commit()
        return {"status": "connected", "cuenta": account_out(account), "meta": data}

    @router.post("/accounts/{account_id}/register")
    async def register_number(
        account_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        """
        Registra el número en la Cloud API con el PIN de 6 dígitos. Una vez
        registrado, ese número deja de poder usarse en la app de WhatsApp
        común del teléfono.
        """
        account = find_account(db, account_id)
        if not (account.phone_number_id and account.pin):
            raise HTTPException(status_code=409, detail="Se requieren phone_number_id y pin (6 dígitos).")
        data = await graph_request(
            "POST", f"{account.phone_number_id}/register", get_account_token(account),
            {"messaging_product": "whatsapp", "pin": account.pin},
        )
        account.registration_state = json.dumps(data)[:1000]
        account.status = "registered"
        account.updated_at = now_utc()
        db.commit()
        return {"status": "registered", "meta": data}

    @router.post("/accounts/{account_id}/templates/sync")
    async def sync_templates(
        account_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        """Trae las plantillas existentes en la WABA (útil tras crearlas en el panel de Meta)."""
        account = find_account(db, account_id)
        if not account.waba_id:
            raise HTTPException(status_code=409, detail="Falta el waba_id de la cuenta.")
        data = await graph_request(
            "GET", f"{account.waba_id}/message_templates", get_account_token(account),
            params={"limit": 250},
        )
        created, updated = 0, 0
        for t in data.get("data", []) or []:
            name = t.get("name")
            lang = (t.get("language") or "").split(":")[0] or "es"
            comp = {c.get("type"): c for c in (t.get("components") or []) if isinstance(c, dict)}
            body = (comp.get("BODY") or {}).get("text")
            header = (comp.get("HEADER") or {}).get("text")
            footer = (comp.get("FOOTER") or {}).get("text")
            buttons = (comp.get("BUTTONS") or {}).get("buttons")
            existing = db.query(models.WhatsAppTemplate).filter(
                models.WhatsAppTemplate.account_id == account.id,
                models.WhatsAppTemplate.name == name,
                models.WhatsAppTemplate.language == lang,
            ).first()
            payload = {
                "header_text": header,
                "body_text": body,
                "footer_text": footer,
                "buttons_json": json.dumps(buttons, ensure_ascii=False) if buttons else None,
                "category": (t.get("category") or "UTILITY").upper(),
                "status": (t.get("status") or "PENDING").upper(),
                "meta_template_id": str(t.get("id") or "") or None,
            }
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(models.WhatsAppTemplate(account_id=account.id, name=name, language=lang, **payload))
                created += 1
        db.commit()
        return {"creadas": created, "actualizadas": updated}

    # ── Plantillas ───────────────────────────────────────────────────────────

    @router.get("/accounts/{account_id}/templates", response_model=List[schemas.WhatsAppTemplateOut])
    def list_templates(
        account_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        find_account(db, account_id)
        rows = (
            db.query(models.WhatsAppTemplate)
            .filter(models.WhatsAppTemplate.account_id == account_id)
            .order_by(models.WhatsAppTemplate.name)
            .all()
        )
        return [schemas.WhatsAppTemplateOut.model_validate(t) for t in rows]

    @router.post("/accounts/{account_id}/templates", response_model=schemas.WhatsAppTemplateOut)
    async def create_template(
        account_id: int,
        payload: schemas.WhatsAppTemplateCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        account = find_account(db, account_id)
        if not account.waba_id:
            raise HTTPException(status_code=409, detail="La cuenta necesita waba_id para crear plantillas.")
        name = validate_template_name(payload.name)
        category = (payload.category or "UTILITY").upper()
        if category not in parse_categories(account.allowed_categories):
            raise HTTPException(
                status_code=403,
                detail=f"Categoría {category} no habilitada para esta cuenta ({account.allowed_categories}).",
            )
        if db.query(models.WhatsAppTemplate).filter(
            models.WhatsAppTemplate.account_id == account_id,
            models.WhatsAppTemplate.name == name,
            models.WhatsAppTemplate.language == payload.language,
        ).first():
            raise HTTPException(status_code=409, detail=f"Ya existe la plantilla {name}/{payload.language}.")

        components: List[Dict[str, Any]] = []
        if payload.header_text:
            components.append({"type": "HEADER", "format": "TEXT", "text": payload.header_text[:60]})
        components.append({"type": "BODY", "text": payload.body_text[:700]})
        if payload.footer_text:
            components.append({"type": "FOOTER", "text": payload.footer_text[:60]})
        if payload.buttons:
            components.append({"type": "BUTTONS", "buttons": payload.buttons})

        meta_resp = None
        if payload.push_to_meta:
            meta_resp = await graph_request(
                "POST", f"{account.waba_id}/message_templates", get_account_token(account),
                {"messaging_product": "whatsapp",
                 "templates": [{"name": name, "language": payload.language,
                                "category": category, "components": components}]},
            )
            item = (meta_resp.get("payload") or [{}])[0]
            meta_id = str(item.get("id") or "") or None
            meta_status = (item.get("status") or "PENDING").upper()
        else:
            meta_id, meta_status = None, "PENDING"

        tpl = models.WhatsAppTemplate(
            account_id=account_id,
            name=name,
            language=payload.language,
            category=category,
            status=meta_status,
            header_text=payload.header_text,
            body_text=payload.body_text,
            footer_text=payload.footer_text,
            buttons_json=json.dumps(payload.buttons, ensure_ascii=False) if payload.buttons else None,
            components_json=json.dumps(components, ensure_ascii=False),
            meta_template_id=meta_id,
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        logger.info("[WA] plantilla %s/%s creada en cuenta %s (meta_id=%s)",
                    name, payload.language, account_id, meta_id)
        return schemas.WhatsAppTemplateOut.model_validate(tpl)

    @router.delete("/templates/{template_id}")
    async def delete_template(
        template_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        tpl = db.query(models.WhatsAppTemplate).filter(models.WhatsAppTemplate.id == template_id).first()
        if not tpl:
            raise HTTPException(status_code=404, detail="Plantilla inexistente.")
        account = find_account(db, tpl.account_id)
        if tpl.status == "APPROVED":
            raise HTTPException(
                status_code=409,
                detail="Meta no permite borrar una plantilla aprobada: archivála desde WhatsApp Manager.",
            )
        if tpl.meta_template_id and account.waba_id:
            await graph_request(
                "DELETE", f"{account.waba_id}/message_templates", get_account_token(account),
                params={"name": tpl.name, "language": tpl.language},
            )
        db.delete(tpl)
        db.commit()
        return {"status": "deleted", "id": template_id}

    # ── Envío y lectura ──────────────────────────────────────────────────────

    @router.post("/accounts/{account_id}/send", response_model=schemas.WhatsAppMessageOut)
    async def send_message(
        account_id: int,
        payload: schemas.WhatsAppSendRequest,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        account = find_account(db, account_id)
        msg = await perform_send(db, account, payload, source=f"user:{current_user.id}")
        return message_out(msg)

    @router.get("/accounts/{account_id}/messages", response_model=List[schemas.WhatsAppMessageOut])
    def list_messages(
        account_id: int,
        conversation_id: Optional[int] = None,
        direction: Optional[str] = None,
        limit: int = Query(100, le=500),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        q = db.query(models.WhatsAppMessage).filter(models.WhatsAppMessage.account_id == account_id)
        if conversation_id:
            q = q.filter(models.WhatsAppMessage.conversation_id == conversation_id)
        if direction:
            q = q.filter(models.WhatsAppMessage.direction == direction)
        rows = q.order_by(models.WhatsAppMessage.created_at.desc()).limit(limit).all()
        return [message_out(m) for m in reversed(rows)]

    @router.get("/accounts/{account_id}/conversations", response_model=List[schemas.WhatsAppConversationOut])
    def list_conversations(
        account_id: int,
        status_f: Optional[str] = Query(None, alias="status"),
        q: Optional[str] = None,
        limit: int = Query(100, le=500),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        query = db.query(models.WhatsAppConversation).filter(
            models.WhatsAppConversation.account_id == account_id)
        if status_f:
            query = query.filter(models.WhatsAppConversation.status == status_f)
        if q:
            like = f"%{q}%"
            query = query.filter(
                models.WhatsAppConversation.contact_phone.like(like)
                | models.WhatsAppConversation.contact_name.like(like)
            )
        rows = query.order_by(models.WhatsAppConversation.started_at.desc()).limit(limit).all()
        return [conversation_out(c) for c in rows]

    # ── Facturación ──────────────────────────────────────────────────────────

    @router.get("/accounts/{account_id}/billing", response_model=schemas.WhatsAppBillingRow)
    def account_billing(
        account_id: int,
        month: Optional[str] = Query(None, description="YYYY-MM, default mes actual"),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        account = find_account(db, account_id)
        start, end = _month_range(month)
        return _billing_row(db, account, start, end)

    @router.get("/billing/report", response_model=schemas.WhatsAppBillingReport)
    def billing_report(
        month: Optional[str] = Query(None, description="YYYY-MM, default mes actual"),
        client_id: Optional[int] = None,
        markup_pct: Optional[float] = None,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        """Cierre de todos los clientes con línea de WA: base para facturar."""
        start, end = _month_range(month)
        q = db.query(models.WhatsAppAccount).options(joinedload(models.WhatsAppAccount.client))
        if client_id:
            q = q.filter(models.WhatsAppAccount.client_id == client_id)
        rows = [_billing_row(db, a, start, end) for a in q.order_by(models.WhatsAppAccount.id).all()]
        pct = WA_MARKUP_PCT if markup_pct is None else markup_pct
        total = 0.0
        for r in rows:
            r.cost_amount = round(r.cost_amount * (1 + pct / 100.0), 4)
            total += r.cost_amount
        return schemas.WhatsAppBillingReport(
            period_start=start,
            period_end=end,
            rows=rows,
            total_cost=round(total, 4),
            currency="USD",
            rates=DEFAULT_RATES,
        )

    @router.post("/billing/close", response_model=List[schemas.WhatsAppBillingPeriodOut])
    def close_billing_period(
        month: str = Query(..., description="YYYY-MM a cerrar"),
        client_id: Optional[int] = None,
        markup_pct: Optional[float] = None,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        """
        Foto del mes en whatsapp_billing_periods (única por cuenta+mes).
        Reabrir un mes ya cerrado pisa los totales; uno ya facturado ('invoiced')
        no se toca: la factura emitida es el documento válido.
        """
        start, end = _month_range(month)
        if end >= date.today():
            raise HTTPException(
                status_code=422,
                detail=f"{month} todavía no terminó: cerrá sólo meses completos.",
            )
        pct = WA_MARKUP_PCT if markup_pct is None else markup_pct
        q = db.query(models.WhatsAppAccount).options(joinedload(models.WhatsAppAccount.client))
        if client_id:
            q = q.filter(models.WhatsAppAccount.client_id == client_id)
        out: List[schemas.WhatsAppBillingPeriodOut] = []
        for account in q.order_by(models.WhatsAppAccount.id).all():
            row = _billing_row(db, account, start, end)
            period = db.query(models.WhatsAppBillingPeriod).filter(
                models.WhatsAppBillingPeriod.account_id == account.id,
                models.WhatsAppBillingPeriod.period_start == start,
            ).first()
            if period is None:
                period = models.WhatsAppBillingPeriod(
                    account_id=account.id, client_id=account.client_id,
                    period_start=start, period_end=end,
                )
                db.add(period)
            elif period.status == "invoiced":
                out.append(_period_out(period, account))
                continue
            for fld in ("sent_total", "delivered_total", "read_total", "failed_total",
                        "inbound_total", "utility_msgs", "marketing_msgs",
                        "authentication_msgs", "service_msgs", "conversations_total"):
                setattr(period, fld, getattr(row, fld))
            period.period_end = end
            period.cost_amount = row.cost_amount
            period.currency = row.currency
            period.markup_pct = pct
            period.amount_to_invoice = round(row.cost_amount * (1 + pct / 100.0), 4)
            period.status = "closed"
            period.closed_at = now_utc()
            db.flush()
            out.append(_period_out(period, account))
        db.commit()
        logger.info("[WA] cierre %s: %s líneas, total a facturar %.4f %s",
                    month, len(out), sum(r.amount_to_invoice for r in out),
                    out[0].currency if out else "USD")
        return out

    @router.get("/billing/periods", response_model=List[schemas.WhatsAppBillingPeriodOut])
    def list_billing_periods(
        account_id: Optional[int] = None,
        client_id: Optional[int] = None,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        q = db.query(models.WhatsAppBillingPeriod).options(
            joinedload(models.WhatsAppBillingPeriod.account))
        if account_id:
            q = q.filter(models.WhatsAppBillingPeriod.account_id == account_id)
        if client_id:
            q = q.filter(models.WhatsAppBillingPeriod.client_id == client_id)
        rows = q.order_by(models.WhatsAppBillingPeriod.period_start.desc(),
                          models.WhatsAppBillingPeriod.account_id).all()
        return [_period_out(p, p.account) for p in rows]

    @router.put("/billing/periods/{period_id}", response_model=schemas.WhatsAppBillingPeriodOut)
    def mark_period_invoiced(
        period_id: int,
        invoice_ref: str = Query(..., description="Comprobante emitido al cliente"),
        status_f: str = Query("invoiced", alias="status", pattern="^(closed|invoiced)$"),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        """Une el cierre de WhatsApp con la factura emitida (GesFactu / manual)."""
        period = db.query(models.WhatsAppBillingPeriod).filter(
            models.WhatsAppBillingPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Cierre inexistente.")
        period.status = status_f
        period.invoice_ref = invoice_ref
        db.commit()
        db.refresh(period)
        return _period_out(period, period.account)

    # ── Canal ERP (ApolloGesCom) ─────────────────────────────────────────────

    @router.post("/erp/bootstrap", response_model=schemas.WhatsAppErpBootstrapOut,
                 tags=["WhatsApp", "ERP"])
    def erp_bootstrap(
        payload: schemas.WhatsAppErpBootstrapIn,
        db: Session = Depends(get_db),
        rotate: bool = Query(False, description="Reemplaza una clave ya entregada"),
        x_gesacti_key: Optional[str] = Header(None, alias="X-GesActi-Key"),
    ):
        """
        Un puesto nuevo pregunta por su credencial: valida el serial de la licencia
        contra misi_licenses y entrega la clave HMAC del cliente UNA sola vez por
        llamado. No usa JWT porque lo invoca GesCom en el arranque, no un usuario
        del portal. La clave se comparte con la misma clave interna de GesActi.
        """
        if not _gesacti_key:
            raise HTTPException(status_code=500,
                                detail="GESACTI_SYNC_KEY no está definido en el servidor.")
        if not x_gesacti_key or not hmac.compare_digest(str(x_gesacti_key), str(_gesacti_key)):
            raise HTTPException(status_code=401, detail="Clave GesActi inválida.")

        serial = erp_norm_serial(payload.serial)
        if not serial:
            raise HTTPException(status_code=422, detail="Falta el serial de ApolloGesCom.")
        codigo = erp_norm_serial(payload.codigo) or serial[:4]
        client = db.query(models.Client).filter(
            func.upper(func.coalesce(models.Client.codigo, "")) == codigo).first()
        if not client:
            raise HTTPException(status_code=404,
                                detail=f"El cliente {codigo} no existe en Support.")

        account = _erp_target_account(db, client)
        operator = (payload.operator or "").strip()[:40] or None

        if client.activo is False:
            _erp_audit(db, client, "wa-erp-baja", serial, operator)
            return schemas.WhatsAppErpBootstrapOut(
                status="deshabilitado", client_code=codigo, serial=serial,
                account_id=(account.id if account else None),
                display_phone_number=(account.display_phone_number if account else None),
                use_cloud_api=False,
                signature_prefix=WA_ERP_SIGNATURE_PREFIX, max_pdf_mb=WA_ERP_MAX_PDF_MB,
            )

        licenses = erp_client_licenses(codigo)
        lic = erp_license_for(licenses, serial)
        if lic is None:
            _erp_audit(db, client, "wa-erp-serial-no-valido", serial, operator)
            raise HTTPException(
                status_code=403,
                detail=f"El serial {serial} no corresponde a las licencias del cliente {codigo}.",
            )
        if lic.get("l_desact") or lic.get("m_down"):
            _erp_audit(db, client, "wa-erp-licencia-desactivada", serial, operator)
            return schemas.WhatsAppErpBootstrapOut(
                status="deshabilitado", client_code=codigo, serial=serial,
                account_id=(account.id if account else None),
                display_phone_number=(account.display_phone_number if account else None),
                use_cloud_api=False,
                signature_prefix=WA_ERP_SIGNATURE_PREFIX, max_pdf_mb=WA_ERP_MAX_PDF_MB,
            )

        api_key = (client.apikey_apollo or "").strip()
        issued = False
        if rotate or not api_key:
            api_key = erp_new_api_key()
            client.apikey_apollo = api_key
            issued = True
        _erp_audit(db, client, ("wa-erp-clave-emitida" if issued else "wa-erp-clave-entregada"),
                   serial, operator)
        db.commit()

        habilitada = bool(account and account.erp_send_enabled)
        conectada = bool(account and (account.status or "") in ("connected", "registered"))
        return schemas.WhatsAppErpBootstrapOut(
            status=("ok" if (habilitada and conectada) else "sin_linea"),
            client_code=codigo,
            api_key=api_key,
            serial=serial,
            account_id=(account.id if account else None),
            display_phone_number=(account.display_phone_number if account else None),
            erp_send_enabled=habilitada,
            invoice_template=(account.erp_invoice_template if account else None) or WA_ERP_INVOICE_TEMPLATE,
            invoice_language=(account.erp_invoice_language if account else None) or WA_ERP_INVOICE_LANG,
            use_cloud_api=(habilitada and conectada),
            signature_prefix=WA_ERP_SIGNATURE_PREFIX,
            max_pdf_mb=WA_ERP_MAX_PDF_MB,
        )

    @router.post("/erp/documents", response_model=schemas.WhatsAppErpSendOut,
                 tags=["WhatsApp", "ERP"])
    async def erp_send(
        payload: schemas.WhatsAppErpSendIn,
        request: Request,
        pair: Tuple[models.Client, models.WhatsAppAccount] = Depends(require_erp_client),
        db: Session = Depends(get_db),
    ):
        """
        Envío de un comprobante desde el puesto. Soporte sube el PDF a Graph y
        registra client_id / serial / operador / comprobante en el mensaje: esa fila
        es el justificante del cobro de fin de mes.
        """
        client, account = pair
        serial = erp_norm_serial(payload.serial) or erp_norm_serial(request.headers.get("X-Apollo-Serial"))
        operator = (payload.operator or "").strip()[:40] or None
        msg, channel_used, duplicate = await erp_send_document(
            db, account, payload, client=client, serial=serial or None, operator=operator)
        cost = msg.cost_amount
        if cost is None:
            cost = estimate_cost(account, msg.pricing_category, bool(msg.billable))
        return schemas.WhatsAppErpSendOut(
            message_id=msg.id,
            meta_message_id=msg.meta_message_id,
            status=msg.status,
            channel_used=channel_used,
            pricing_category=msg.pricing_category,
            billable=bool(msg.billable),
            cost_amount=cost,
            duplicate=duplicate,
            detail=("El PDF ya fue enviado con esa idempotency_key; no se gastó otro mensaje."
                    if duplicate else None),
        )

    @router.get("/erp/usage", response_model=schemas.WhatsAppErpUsageReport,
                tags=["WhatsApp", "ERP"])
    def erp_usage_self(
        request: Request,
        month: Optional[str] = Query(None, description="YYYY-MM; se omite = mes en curso"),
        serial: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        pair: Tuple[models.Client, models.WhatsAppAccount] = Depends(require_erp_client),
    ):
        """Consumo del propio cliente: el puesto puede mostrar cuánto lleva gastado."""
        client, _account = pair
        start, end = _month_range(month)
        return _erp_usage(db, client, start, end, serial=erp_norm_serial(serial) or None)

    @router.get("/erp/clients/{codigo}/usage", response_model=schemas.WhatsAppErpUsageReport,
                tags=["WhatsApp"])
    def erp_usage_admin(
        codigo: str,
        month: Optional[str] = Query(None, description="YYYY-MM"),
        serial: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        """El reporte que se abre cuando el cliente discute la factura de WhatsApp."""
        client = db.query(models.Client).filter(
            func.upper(func.coalesce(models.Client.codigo, "")) == erp_norm_serial(codigo)).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente inexistente.")
        start, end = _month_range(month)
        return _erp_usage(db, client, start, end, serial=erp_norm_serial(serial) or None)

    @router.post("/erp/clients/{codigo}/rotate-key", response_model=Dict[str, Any],
                 tags=["WhatsApp"])
    def erp_rotate_key(
        codigo: str,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(require_admin),
    ):
        """
        Se filtró una clave: se reemplaza y se muestra una sola vez acá. El puesto
        vuelve a pedir bootstrap y queda registrado quién y cuándo la pidió.
        """
        client = db.query(models.Client).filter(
            func.upper(func.coalesce(models.Client.codigo, "")) == erp_norm_serial(codigo)).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente inexistente.")
        client.apikey_apollo = erp_new_api_key()
        _erp_audit(db, client, "wa-erp-clave-rotada", None, f"user:{current_user.id}")
        db.commit()
        return {"client_code": client.codigo, "api_key": client.apikey_apollo,
                "note": "Entregala al cliente por un canal seguro: no queda guardada en otro lado."}

    app.include_router(router)
    logger.info("[WA] módulo WhatsApp Cloud API montado en /api/whatsapp")


# ═════════════════════════════════════════════════════════════════════════════
# Agregaciones de facturación
# ═════════════════════════════════════════════════════════════════════════════

def _month_range(month: Optional[str]) -> Tuple[date, date]:
    if month:
        try:
            y, m = int(month[:4]), int(month[5:7])
            start = date(y, m, 1)
        except (ValueError, IndexError):
            raise HTTPException(status_code=422, detail="month debe tener formato YYYY-MM.")
    else:
        start = date.today().replace(day=1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(start.year, start.month + 1, 1) - timedelta(days=1)
    return start, end


def _billing_row(db: Session, account: models.WhatsAppAccount,
                 start: date, end: date) -> schemas.WhatsAppBillingRow:
    """
    Meta factura el mensaje de plantilla cuando LLEGA (delivered). Como `status`
    se pisa con 'read' al confirmarse la lectura, contabilizar sólo status=delivered
    dejaría afuera los leídos: por eso se cuenta sobre el conjunto entregado+leído.
    Sólo entran los marcados billable: una utility dentro de la ventana de servicio
    no se cobra, y el webhook de estados es quien lo confirma.
    """
    lo = datetime.combine(start, datetime.min.time())
    hi = datetime.combine(end, datetime.max.time())
    rates = get_rates(account)
    REACHED = ("delivered", "read")

    def count(statuses=None, direction="outbound", **kw: Any) -> int:
        q = db.query(models.WhatsAppMessage).filter(
            models.WhatsAppMessage.account_id == account.id,
            models.WhatsAppMessage.created_at >= lo,
            models.WhatsAppMessage.created_at <= hi,
            models.WhatsAppMessage.direction == direction,
        )
        if statuses:
            q = q.filter(models.WhatsAppMessage.status.in_(list(statuses)))
        for k, v in kw.items():
            q = q.filter(getattr(models.WhatsAppMessage, k) == v)
        return q.count()

    outbound = count()
    delivered = count(statuses=REACHED)
    read_ = count(statuses=("read",))
    failed = count(statuses=("failed",))
    inbound = count(direction="inbound")

    utility = count(statuses=REACHED, pricing_category="utility", billable=True)
    marketing = count(statuses=REACHED, pricing_category="marketing", billable=True)
    auth = count(statuses=REACHED, pricing_category="authentication", billable=True)
    service = count(statuses=REACHED, pricing_category="service")

    conv_total = db.query(func.count(models.WhatsAppConversation.id)).filter(
        models.WhatsAppConversation.account_id == account.id,
        models.WhatsAppConversation.started_at >= lo,
        models.WhatsAppConversation.started_at <= hi,
    ).scalar() or 0

    cost = (utility * rates["utility"] + marketing * rates["marketing"]
            + auth * rates["authentication"])

    return schemas.WhatsAppBillingRow(
        account_id=account.id,
        client_id=account.client_id,
        client_name=account.client.razon_social if account.client else None,
        display_phone_number=account.display_phone_number,
        sent_total=outbound,
        delivered_total=delivered,
        read_total=read_,
        failed_total=failed,
        inbound_total=inbound,
        utility_msgs=utility,
        marketing_msgs=marketing,
        authentication_msgs=auth,
        service_msgs=service,
        conversations_total=conv_total,
        cost_amount=round(cost, 4),
        currency=account.rate_currency or "USD",
    )


def _period_out(period: models.WhatsAppBillingPeriod,
                account: Optional[models.WhatsAppAccount]) -> schemas.WhatsAppBillingPeriodOut:
    """Série cerrada + identificación del cliente (no es columna del cierre)."""
    out = schemas.WhatsAppBillingPeriodOut.model_validate(period)
    if account is not None:
        out.client_name = account.client.razon_social if account.client else None
        out.display_phone_number = account.display_phone_number
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Canal "whatsapp" del NotificationOutbox + worker de mantenimiento
# ═════════════════════════════════════════════════════════════════════════════

def resolve_account_for_outbox(db: Session, target: str) -> Tuple[Optional[models.WhatsAppAccount], str]:
    """
    El outbox no tiene columna de cuenta: se resuelve por cliente.
    target admite "cliente:<id>:<telefono>" o sólo el teléfono.
    """
    m = re.match(r"^cliente:(\d+)[:=](.*)$", (target or "").strip(), re.IGNORECASE)
    if m:
        client_id, phone = int(m.group(1)), m.group(2)
        account = db.query(models.WhatsAppAccount).filter(
            models.WhatsAppAccount.client_id == client_id,
            models.WhatsAppAccount.status.in_(["connected", "registered"]),
        ).first()
        return account, normalize_wa_phone(phone)
    return db.query(models.WhatsAppAccount).filter(
        models.WhatsAppAccount.status.in_(["connected", "registered"])
    ).order_by(models.WhatsAppAccount.id).first(), normalize_wa_phone(target)


async def process_whatsapp_outbox_once() -> int:
    """Drena notificaciones pendientes del canal whatsapp. Lo llama el worker."""
    handled = 0
    db = SessionLocal()
    try:
        pending = db.query(models.NotificationOutbox).filter(
            models.NotificationOutbox.channel == "whatsapp",
            models.NotificationOutbox.status == "pending",
            models.NotificationOutbox.send_at <= now_utc(),
        ).limit(25).all()
        for note in pending:
            account, phone = resolve_account_for_outbox(db, note.target or "")
            if not account or not phone:
                note.status = "failed"
                note.error_message = "Sin cuenta de WhatsApp activa para el destinatario"
                db.commit()
                continue
            req = WhatsAppSendable(to=phone, type="text", body=note.body,
                                   contact_name=note.subject)
            try:
                await perform_send(db, account, req, source="outbox", channel="outbox")
                note.status = "sent"
                note.sent_at = now_utc()
                handled += 1
            except HTTPException as e:
                note.status = "failed"
                note.error_message = str(e.detail)[:500]
            db.commit()
    finally:
        db.close()
    return handled


async def retry_unprocessed_events() -> int:
    """Reintenta webhooks que fallaron al procesarse (máx. 5 intentos)."""
    db = SessionLocal()
    n = 0
    try:
        rows = db.query(models.WhatsAppWebhookEvent).filter(
            models.WhatsAppWebhookEvent.processed == False,  # noqa: E712
            models.WhatsAppWebhookEvent.attempts < 5,
        ).limit(50).all()
        for evt in rows:
            try:
                data = json.loads(evt.payload)
            except ValueError:
                evt.processed = True
                evt.error_message = "payload no es JSON"
                db.commit()
                continue
            try:
                process_webhook_payload(db, data)
                evt.processed = True
                evt.processed_at = now_utc()
                evt.error_message = None
                n += 1
            except Exception as e:  # noqa: BLE001
                evt.attempts = (evt.attempts or 0) + 1
                evt.error_message = str(e)[:1000]
                logger.warning("[WA] webhook %s sin procesar (intento %s): %s",
                               evt.id, evt.attempts, e)
            db.commit()
    finally:
        db.close()
    return n


async def close_expired_conversations() -> int:
    db = SessionLocal()
    try:
        rows = db.query(models.WhatsAppConversation).filter(
            models.WhatsAppConversation.status == "open",
            models.WhatsAppConversation.expires_at <= now_utc(),
        ).update({"status": "expired"}, synchronize_session=False)
        db.commit()
        return rows or 0
    finally:
        db.close()


async def periodic_whatsapp_worker(interval: int = 60) -> None:
    """
    Bucle del módulo: cierra ventanas vencidas, drena el outbox de WhatsApp y
    reintenta eventos de webhook en error. Registrar como task desde main.py.
    """
    logger.info("[WA] worker periódico iniciado (intervalo %ss)", interval)
    while True:
        try:
            await close_expired_conversations()
            await asyncio.sleep(1)
        except Exception:  # noqa: BLE001
            logger.exception("[WA] worker: cierre de ventanas falló")
        try:
            await process_whatsapp_outbox_once()
        except Exception:  # noqa: BLE001
            logger.exception("[WA] worker: outbox falló")
        try:
            await retry_unprocessed_events()
        except Exception:  # noqa: BLE001
            logger.exception("[WA] worker: reintentos de webhook fallaron")
        await asyncio.sleep(interval)
