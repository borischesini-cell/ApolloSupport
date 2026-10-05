"""Revalidación offline de los 4 fixes de facturación/webhook (SQLite en memoria, sin red).
Borrador de verificación: se elimina después de correr."""
import asyncio
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timedelta

os.environ["APOLLO_SECRET_KEY"] = "reclavetest-0123456789abcdef"
os.environ["WA_APP_SECRET"] = "app-secret-test"
os.environ.setdefault("DB_PASSWORD", "sin-usar-en-este-test")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import models  # noqa: E402
import whatsapp as wa  # noqa: E402

FAILS = []


def check(name, got, exp):
    ok = got == exp
    print(f"  {'OK ' if ok else 'NO '} {name}: {got!r}" + ("" if ok else f" (esperado {exp!r})"))
    if not ok:
        FAILS.append(name)


engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
models.Base.metadata.create_all(engine, tables=[
    models.Client.__table__,
    models.WhatsAppAccount.__table__,
    models.WhatsAppTemplate.__table__,
    models.WhatsAppConversation.__table__,
    models.WhatsAppMessage.__table__,
    models.WhatsAppBillingPeriod.__table__,
])
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
db = TestingSession()

# ── datos base ───────────────────────────────────────────────────────────────
client = models.Client(id=1, razon_social="MASTERISI SA")
db.add(client)
acc = models.WhatsAppAccount(
    id=1, client_id=1, phone_number_id="PNID1", display_phone_number="+543446675303",
    status="connected", allowed_categories="UTILITY,MARKETING,SERVICE",
    access_token_enc=wa.encrypt_secret("token-sistema"),
)
db.add_all([
    models.WhatsAppTemplate(account_id=1, name="recordatorio_pago", language="es",
                            category="UTILITY", status="APPROVED"),
    models.WhatsAppTemplate(account_id=1, name="promo_mes", language="es",
                            category="MARKETING", status="APPROVED"),
    models.WhatsAppTemplate(account_id=1, name="sin_id_meta", language="es_AR",
                            category="UTILITY", status="PENDING"),
    models.WhatsAppTemplate(account_id=1, name="con_id", language="es",
                            category="UTILITY", status="PENDING", meta_template_id="TPLCONID"),
])
db.add(acc)
db.commit()

P0 = "5491177788999"   # nunca escribió: sin ventana
P1 = "5491122334455"   # ventana abierta por el cliente en [1]
P2 = "5491155667788"   # con ventana abierta por el cliente
P3 = "5491199887766"   # marketing
P4 = "5491133445566"   # texto de servicio

print("\n[1] touch_conversation cuenta el PRIMER mensaje (fix 1)")
conv = wa.touch_conversation(db, 1, P1, category="utility", inbound=True, contact_name="Juan")
db.commit()
check("message_count en el alta", conv.message_count, 1)
check("inbound_count en el alta", conv.inbound_count, 1)
check("inbound abre ventana service gratis", (conv.category, conv.billable), ("service", False))
wa.touch_conversation(db, 1, P1, category="service")
db.commit()
check("segundo mensaje sigue acumulando", (conv.message_count, conv.outbound_count), (2, 1))

print("\n[2] perform_send estima billable según ventana (fix 3)")


async def fake_graph(account, payload):
    fake_graph.calls.append(payload)
    return {"messages": [{"id": f"wamid.{len(fake_graph.calls)}"}]}


fake_graph.calls = []
wa.graph_send_message = fake_graph


def req(**kw):
    base = dict(to=None, type="template", template_name=None, language="es",
                components=None, body=None, media_url=None, media_id=None,
                caption=None, filename=None, contact_name=None, ref_ticket_id=None)
    base.update(kw)
    return wa.WhatsAppSendable(**base)


# P0 nunca escribió: utility fuera de ventana es facturable
m1 = asyncio.get_event_loop().run_until_complete(
    wa.perform_send(db, acc, req(to=P0, template_name="recordatorio_pago")))
check("utility fuera de ventana es billable", m1.billable, True)
check("category de mensaje", m1.pricing_category, "utility")

# P2: el cliente escribe primero y luego sale una utility gratis
wa.touch_conversation(db, 1, P2, category="service", inbound=True)
db.commit()
m2 = asyncio.get_event_loop().run_until_complete(
    wa.perform_send(db, acc, req(to=P2, template_name="recordatorio_pago")))
check("utility dentro de ventana NO se factura", m2.billable, False)

# P3: marketing siempre se factura aunque haya ventana
wa.touch_conversation(db, 1, P3, category="service", inbound=True)
db.commit()
m3 = asyncio.get_event_loop().run_until_complete(
    wa.perform_send(db, acc, req(to=P3, template_name="promo_mes")))
check("marketing siempre billable", m3.billable, True)
check("marketing category", m3.pricing_category, "marketing")

# P4: texto de respuesta = servicio, sin cargo
wa.touch_conversation(db, 1, P4, category="service", inbound=True)
db.commit()
m4 = asyncio.get_event_loop().run_until_complete(
    wa.perform_send(db, acc, req(to=P4, type="text", body="hola")))
check("texto en ventana es service", (m4.pricing_category, m4.billable), ("service", False))

# texto sin ventana: Meta lo rechaza (131026) y el módulo lo anticipa
try:
    asyncio.get_event_loop().run_until_complete(
        wa.perform_send(db, acc, req(to=P0, type="text", body="sin ventana")))
    check("texto fuera de ventana se anticipa", "no lanzó", "409")
except Exception as e:
    check("texto fuera de ventana se anticipa", getattr(e, "status_code", None), 409)

conv2 = wa.get_open_conversation(db, 1, P2)
check("contadores sin duplicar (1 inbound + 1 outbound)",
      (conv2.message_count, conv2.inbound_count, conv2.outbound_count), (2, 1, 1))
check("cuota mensual acumulada de envíos", acc.messages_sent_this_month, 4)

print("\n[3] webhook de plantilla entiende string y número (fix 2)")
tpl = db.query(models.WhatsAppTemplate).filter_by(name="con_id").first()
check("string APPROVED", wa._handle_template_status(db, {
    "event": "APPROVED", "message_template_id": "TPLCONID",
    "message_template_language": "es"}), 1)
db.commit()
check("estado aplicado", tpl.status, "APPROVED")

tpl2 = db.query(models.WhatsAppTemplate).filter_by(name="sin_id_meta").first()
check("evento numérico 3 + lenguaje con región, sin meta_id", wa._handle_template_status(db, {
    "event": 3, "message_template_id": "TLPNEW", "message_template_name": "sin_id_meta",
    "message_template_language": "es"}), 1)
db.commit()
check("plantilla emparejada por nombre", tpl2.status, "APPROVED")
check("se completa el meta_template_id", tpl2.meta_template_id, "TLPNEW")

check("plantilla desconocida no rompe", wa._handle_template_status(db, {
    "event": "APPROVED", "message_template_id": "NOPE",
    "message_template_name": "inexistente", "message_template_language": "es"}), 0)
check("evento ilegible no rompe", wa._handle_template_status(db, {
    "event": "LOQUESEA", "message_template_id": "TPLCONID",
    "message_template_language": "es"}), 0)
check("rechazo guarda el motivo", wa._handle_template_status(db, {
    "event": "REJECTED", "message_template_id": "TPLCONID",
    "message_template_name": "con_id", "message_template_language": "es",
    "reason": "Contenido prohibido"}), 1)
db.commit()
check("estado + reason persistidos", (tpl.status, tpl.rejection_reason), ("REJECTED", "Contenido prohibido"))

print("\n[4] _billing_row sólo cobra los billable (fix 4)")
db.query(models.WhatsAppMessage).delete()
now = datetime.utcnow()
rows = []
for _ in range(2):
    rows.append(dict(pricing_category="utility", billable=True, status="delivered"))
for _ in range(3):
    rows.append(dict(pricing_category="utility", billable=False, status="delivered"))
rows += [
    dict(pricing_category="utility", billable=True, status="read"),
    dict(pricing_category="marketing", billable=True, status="delivered"),
    dict(pricing_category="service", billable=False, status="delivered"),
    dict(pricing_category="utility", billable=True, status="failed"),
]
for i, spec in enumerate(rows):
    db.add(models.WhatsAppMessage(account_id=1, direction="outbound",
                                  contact_phone=P1, created_at=now - timedelta(days=1),
                                  body_text=f"m{i}", **spec))
for _ in range(2):
    db.add(models.WhatsAppMessage(account_id=1, direction="inbound", contact_phone=P1,
                                  status="delivered", created_at=now - timedelta(days=1)))
db.commit()

start = now.replace(day=1)
row = wa._billing_row(db, acc, start.replace(day=1), (start.replace(day=28) if start.day == 1 else start))
check("utility billables", row.utility_msgs, 3)
check("marketing billables", row.marketing_msgs, 1)
check("service no factura", row.service_msgs, 1)
check("costo USD (3*0.0225 + 1*0.0625)", row.cost_amount, round(3 * 0.0225 + 0.0625, 4))
check("entregados", row.delivered_total, 8)
check("leídos", row.read_total, 1)
check("fallidos", row.failed_total, 1)
check("entrantes", row.inbound_total, 2)
check("enviados totales", row.sent_total, 9)

print("\n[5] firma del webhook")
raw = b'{"object":"whatsapp_business_account"}'
good = "sha256=" + hmac.new(b"app-secret-test", raw, hashlib.sha256).hexdigest()
check("firma válida", wa.verify_signature(raw, good), True)
check("firma alterada", wa.verify_signature(raw, "sha256=" + "0" * 64), False)
check("sin firma", wa.verify_signature(raw, None), False)

print("\n[6] canal ERP: firma HMAC, anti-replay, media y auditoría")

import base64 as _b64  # noqa: E402
from datetime import date  # noqa: E402
import schemas  # noqa: E402

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
PATH = "/api/whatsapp/erp/documents"
BODY = b'{"to":"5491122334455"}'
SECRET = "clave-test-erp-hmac"

client.codigo = "ABCD"
client.apikey_apollo = SECRET
client.activo = True
acc.erp_send_enabled = True
acc.erp_invoice_template = "factura_apollo"
db.add(models.WhatsAppTemplate(account_id=1, name="factura_apollo", language="es",
                               category="UTILITY", status="APPROVED"))
db.commit()


def exc_status(fn):
    try:
        fn()
        return None
    except Exception as e:
        return getattr(e, "status_code", None)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── [6.1] serial de licencia ─────────────────────────────────────────────────
check("serial normalizado", wa.erp_norm_serial(" abcd-123 4567 "), "ABCD-1234567")
check("codigo desde el serial", wa.erp_norm_serial("abcd-1234567")[:4], "ABCD")
LICS = [
    {"l_number": "ABCD-1234567 ", "l_desact": False, "m_down": False},
    {"l_number": "ABCD-7654321", "l_desact": True, "m_down": False},
]
check("licencia emparejada sin espacios", wa.erp_license_for(LICS, "abcd-1234567")["l_desact"], False)
check("licencia desactivada se detecta", wa.erp_license_for(LICS, "ABCD-7654321")["l_desact"], True)
check("serial de otro cliente no empareja", wa.erp_license_for(LICS, "EFGH-1"), None)

# ── [6.2] firma ─────────────────────────────────────────────────────────────
TS = str(int(wa.now_utc().timestamp()))
sig = wa.erp_signature(SECRET, "POST", PATH, TS, "a1b2c3d4e5f60718", BODY)
check("firma estable", wa.erp_signature(SECRET, "POST", PATH, TS, "a1b2c3d4e5f60718", BODY), sig)
check("prefijo en la base", wa.erp_base_string("POST", PATH, TS, "n1", BODY).startswith(
    wa.WA_ERP_SIGNATURE_PREFIX), True)
check("hash del body en la base", hashlib.sha256(BODY).hexdigest() in wa.erp_base_string(
    "POST", PATH, TS, "n1", BODY), True)
check("otro body cambia la firma", wa.erp_signature(SECRET, "POST", PATH, TS, "a1b2c3d4e5f60718", b"{}") == sig, False)
check("otra URL cambia la firma", wa.erp_signature(SECRET, "POST", "/otro", TS, "a1b2c3d4e5f60718", BODY) == sig, False)
check("otra clave cambia la firma", wa.erp_signature("otra", "POST", PATH, TS, "a1b2c3d4e5f60718", BODY) == sig, False)
check("nonce nuevo libre", wa._nonce_used_or_remember("deadbeefdeadbeef01"), False)
check("nonce repetido bloqueado", wa._nonce_used_or_remember("deadbeefdeadbeef01"), True)


class _FakeReq:
    def __init__(self, headers, body=BODY, method="POST", path=PATH):
        self.headers = headers
        self._body = body
        self.method = method
        self.url = type("U", (), {"path": path})()

    async def body(self):
        return self._body


def signed(code, secret, nonce, body=BODY, path=PATH, ts=None, serial="", method="POST"):
    ts = ts or str(int(wa.now_utc().timestamp()))
    return {
        "X-Apollo-Code": code,
        "X-Apollo-Timestamp": ts,
        "X-Apollo-Nonce": nonce,
        "X-Apollo-Signature": wa.erp_signature(secret, method, path, ts, nonce, body),
        "X-Apollo-Serial": serial,
    }


def guard(headers, body=BODY, path=PATH):
    return exc_status(lambda: run(wa.require_erp_client(
        request=_FakeReq(headers, body, path=path), db=db)))


ok_pair = run(wa.require_erp_client(
    request=_FakeReq(signed("ABCD", SECRET, "a1b2c3d4e5f60719", serial="ABCD-1234567")), db=db))
check("pedido firmado pasa", (ok_pair[0].codigo, ok_pair[1].id), ("ABCD", 1))
check("faltan headers", guard({}), 401)
check("firma inválida", guard(signed("ABCD", "clave-mala", "a1b2c3d4e5f6071a")), 401)
check("timestamp no numérico", guard(dict(signed("ABCD", SECRET, "a1b2c3d4e5f6071b"),
                                         **{"X-Apollo-Timestamp": "ayer"})), 401)
check("reloj desincronizado", guard(signed("ABCD", SECRET, "a1b2c3d4e5f6071c",
                                           ts=str(int(wa.now_utc().timestamp()) - 99999))), 401)
check("nonce muy corto", guard(dict(signed("ABCD", SECRET, "abc"), **{"X-Apollo-Nonce": "abc"})), 401)
check("replay del mismo nonce", guard(signed("ABCD", SECRET, "deadbeefdeadbeef01")), 401)
check("código inexistente", guard(signed("ZZZZ", SECRET, "a1b2c3d4e5f6071d")), 401)
check("body alterado en tránsito", guard(signed("ABCD", SECRET, "a1b2c3d4e5f6071e"),
                                         body=b'{"to":"5491199999999"}'), 401)

sin_clave = models.Client(id=91, codigo="EFGH", razon_social="Sin clave SA", activo=True)
baja = models.Client(id=92, codigo="IJKL", razon_social="Dados de baja SA", activo=False)
db.add_all([sin_clave, baja])
db.commit()
check("cliente sin apikey", guard(signed("EFGH", SECRET, "a1b2c3d4e5f6071f")), 401)
check("cliente de baja", guard(signed("IJKL", SECRET, "a1b2c3d4e5f60720")), 403)
# apikey_apollo es UNIQUE: cada cliente firma con su propia clave
SECRET_MNOP = "clave-test-erp-mnop"
sin_linea = models.Client(id=93, codigo="MNOP", razon_social="Sin linea SA", activo=True,
                          apikey_apollo=SECRET_MNOP)
db.add(sin_linea)
db.commit()
check("sin línea dada de alta", guard(signed("MNOP", SECRET_MNOP, "a1b2c3d4e5f60721")), 409)
acc.erp_send_enabled = False
db.commit()
check("línea no habilitada para el ERP", guard(signed("ABCD", SECRET, "a1b2c3d4e5f60722")), 403)
acc.erp_send_enabled = True
db.commit()

# ── [6.3] nombre de archivo y base64 ─────────────────────────────────────────
check("ruta hostil neutralizada", wa.safe_media_name("..\\..\\Fac A 0001-123.pdf"),
      "Fac A 0001-123.pdf")
check("extensión forzada", wa.safe_media_name("factura"), "factura.pdf")
check("nombre vacío con fallback", wa.safe_media_name(None, "FA.pdf"), "FA.pdf")
check("nombre largo recortado", len(wa.safe_media_name("x" * 300)), 124)
check("b64 con prefijo data:", wa.decode_b64_media("data:application/pdf;base64," +
      _b64.b64encode(PDF).decode(), "f.pdf"), PDF)
check("b64 con saltos", wa.decode_b64_media(_b64.b64encode(PDF).decode()[:20] + "\n" +
      _b64.b64encode(PDF).decode()[20:], "f.pdf"), PDF)
check("b64 ilegible", exc_status(lambda: wa.decode_b64_media("no-es-base64-@@@", "f.pdf")), 422)
check("que no es pdf", exc_status(lambda: wa.decode_b64_media(
      _b64.b64encode(b"hola mundo").decode(), "f.pdf")), 422)
check("vacío", exc_status(lambda: wa.decode_b64_media(None, "f.pdf")), 422)

# ── [6.4] plantilla con documento y estimación de costo ──────────────────────
comps = wa.build_invoice_components({"id": "M1"}, "FA.pdf", ["FA A 0001-1", "Juan", "01/09/2026"])
check("header con id y nombre", comps[0]["parameters"][0]["document"],
      {"id": "M1", "filename": "FA.pdf"})
check("body con las 3 variables", len(comps[1]["parameters"]), 3)
by_link = wa.build_invoice_components({"link": "https://x/y.pdf"}, "FA.pdf", [])
check("header con link", by_link[0]["parameters"][0]["document"],
      {"link": "https://x/y.pdf", "filename": "FA.pdf"})
check("sin variables no arma body", len(by_link), 1)
check("service no se cobra", wa.estimate_cost(acc, "service", False), 0.0)
check("utility billable al costo Meta", wa.estimate_cost(acc, "utility", True),
      wa.DEFAULT_RATES["utility"])
check("utility gratis en ventana", wa.estimate_cost(acc, "utility", False), 0.0)

# ── [6.5] envío extremo a extremo del comprobante ────────────────────────────
UPLOADS = []


async def fake_upload(account, filename, content, mime="application/pdf"):
    UPLOADS.append((filename, len(content)))
    return f"MEDIA{len(UPLOADS)}"


wa.graph_upload_media = fake_upload

payload_doc = schemas.WhatsAppErpSendIn(
    to=P2, media_b64=_b64.b64encode(PDF).decode(), filename="FA A 0001-00000123.pdf",
    doc_ref="FA A 0001-00000123", serial="ABCD-1234567", operator="BORIS",
    idempotency_key="FA-123")
m_doc, ch_doc, dup_doc = run(wa.erp_send_document(db, acc, payload_doc, client=client,
                                                  serial="ABCD-1234567", operator="BORIS"))
check("con ventana sale como documento", (ch_doc, m_doc.message_type), ("document", "document"))
check("documento en ventana es service gratis", (m_doc.pricing_category, m_doc.billable),
      ("service", False))
check("auditoría del mensaje", (m_doc.source_channel, m_doc.erp_serial, m_doc.erp_operator,
                                m_doc.erp_doc_ref, m_doc.client_id),
      ("erp", "ABCD-1234567", "BORIS", "FA A 0001-00000123", 1))
check("channel también en payload_json", json.loads(m_doc.payload_json).get("channel"), "erp")
check("el PDF se subió a Graph", UPLOADS[-1], ("FA A 0001-00000123.pdf", len(PDF)))

m_re, ch_re, dup_re = run(wa.erp_send_document(db, acc, payload_doc, client=client,
                                               serial="ABCD-1234567", operator="BORIS"))
check("reintento con la misma key no duplica", (dup_re, m_re.id == m_doc.id), (True, True))
check("el reintento no vuelve a subir el PDF", len(UPLOADS), 1)

payload_tpl = schemas.WhatsAppErpSendIn(
    to=P0, media_b64=_b64.b64encode(PDF).decode(), filename="FA A 0001-00000124.pdf",
    doc_ref="FA A 0001-00000124", idempotency_key="FA-124")
m_tpl, ch_tpl, dup_tpl = run(wa.erp_send_document(db, acc, payload_tpl, client=client,
                                                  serial="ABCD-1234567", operator="BORIS"))
check("sin ventana sale con plantilla", (ch_tpl, m_tpl.message_type), ("template", "template"))
check("utility fuera de ventana se factura", (m_tpl.pricing_category, m_tpl.billable),
      ("utility", True))
sent_tpl = fake_graph.calls[-1]
check("la plantilla se llama factura_apollo", sent_tpl["template"]["name"], "factura_apollo")
check("el documento va en el header", sent_tpl["template"]["components"][0]["parameters"][0]
      ["document"], {"id": "MEDIA2", "filename": "FA A 0001-00000124.pdf"})
check("el body lleva comprobante, nombre y fecha",
      [p["text"] for p in sent_tpl["template"]["components"][1]["parameters"]],
      ["FA A 0001-00000124", "MASTERISI SA", wa.now_utc().strftime("%d/%m/%Y")])

db.query(models.WhatsAppMessage).filter(
    models.WhatsAppMessage.idempotency_key.isnot(None)).update({"status": "delivered"})
db.commit()

# ── [6.6] reporte de consumo que justifica la factura ────────────────────────
rep = wa._erp_usage(db, client, date.today().replace(day=1), date.today(),
                    serial="ABCD-1234567")
check("mensajes enviados por el ERP", rep.sent_total, 2)
check("sólo uno facturable", rep.billable_total, 1)
check("costo del período", rep.cost_amount, round(wa.DEFAULT_RATES["utility"], 4))
check("con recargo para facturar", rep.amount_to_invoice,
      round(wa.DEFAULT_RATES["utility"] * (1 + wa.WA_MARKUP_PCT / 100.0), 4))
check("desglose por serial", rep.by_serial, {"ABCD-1234567": 2})
check("el detalle trae comprobante y operador",
      (rep.rows[0].doc_ref, rep.rows[0].operator, rep.rows[0].status),
      ("FA A 0001-00000124", "BORIS", "delivered"))
rep_otro = wa._erp_usage(db, sin_linea, date.today().replace(day=1), date.today())
check("cliente sin uso reporta ceros", (rep_otro.sent_total, rep_otro.cost_amount), (0, 0.0))

db.close()
print("\n" + ("TODO OK" if not FAILS else f"FALLARON: {FAILS}"))
sys.exit(1 if FAILS else 0)
