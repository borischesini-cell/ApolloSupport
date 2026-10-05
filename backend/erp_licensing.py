"""
-------------------------------------------------------------------------
Servicio de Gesti?n de Licencias ERP (Conexi?n a MySQL Remoto)
Proyecto: ApolloSupport
Descripci?n: Maneja la l?gica de negocio, encriptaci?n/desencriptaci?n
             y consultas directas al servidor de licencias MySQL.
-------------------------------------------------------------------------
"""

import os
import json
import pymysql
from datetime import datetime, timedelta, date

# Credenciales fijas obtenidas de ODBC/Registry
MYSQL_HOST = 'mysql1.apollogescom.com.ar'
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'Mas1Ter2Isi3'
MYSQL_DB = 'apolloge_masterisi'

# Proxy HTTP para consultar misi_licand en el hosting de masterisi.com.ar
# (El hosting compartido no permite conexiones MySQL remotas directas)
ANDROID_PROXY_URL = os.getenv('ANDROID_PROXY_URL', 'https://www.masterisi.com.ar/WebService/android_proxy.php')
ANDROID_PROXY_TOGGLE_URL = os.getenv(
    'ANDROID_PROXY_TOGGLE_URL',
    'https://www.masterisi.com.ar/WebService/android_proxy_toggle.php',
)
ANDROID_PROXY_KEY = os.getenv('ANDROID_PROXY_KEY', 'Apollo_Masterisi_Proxy_2025_SecureKey')

# Opcional: MySQL directo a masterisi_licenmovil si el servidor Support tiene IP permitida
LICENMOVIL_MYSQL_HOST = os.getenv('LICENMOVIL_MYSQL_HOST', '').strip()
LICENMOVIL_MYSQL_USER = os.getenv('LICENMOVIL_MYSQL_USER', 'masterisi_root')
LICENMOVIL_MYSQL_PASSWORD = os.getenv('LICENMOVIL_MYSQL_PASSWORD', 'Isi-2010')
LICENMOVIL_MYSQL_DB = os.getenv('LICENMOVIL_MYSQL_DB', 'masterisi_licenmovil')

def get_mysql_connection():
    """ Abre y retorna una conexi?n directa a la base de datos de licencias de MySQL """
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# Mapa de c?digos de app a nombres legibles
APP_NAMES = {
    'PRV': 'Preventa',
    'ROU': 'RouteONE',
    'FIR': 'Firma',
    'INV': 'Inventario',
    'FRA': 'Facturación',
    'MON': 'Monitor',
    'COB': 'Cobranzas',
    'PWA': 'PWA Web',
    'TCK': 'Tickets / Navegador Web',
}

def _call_android_proxy(params: dict, *, method: str = 'GET'):
    """
    Llama al proxy PHP en masterisi.com.ar para consultar misi_licand.
    Devuelve lista (summary/client) o dict (toggle).
    """
    import requests as _requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    all_params = {'key': ANDROID_PROXY_KEY, **params}
    headers = _android_proxy_headers()
    if method.upper() == 'POST':
        resp = _requests.post(
            ANDROID_PROXY_URL,
            params={'key': ANDROID_PROXY_KEY},
            data=params,
            headers=headers,
            timeout=20.0,
            verify=False,
        )
    else:
        resp = _requests.get(
            ANDROID_PROXY_URL,
            params=all_params,
            headers=headers,
            timeout=20.0,
            verify=False,
        )
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Respuesta inválida del proxy Android ({resp.status_code}): {resp.text[:200]}") from exc
    if isinstance(data, dict) and data.get('error'):
        msg = data.get('message') or str(data.get('error'))
        if 'invalid action' in msg.lower() or data.get('error') in ('Invalid action', 'invalid_action'):
            raise RuntimeError(
                "Falta actualizar android_proxy.php en masterisi.com.ar (acción toggle). "
                "Subir el archivo desde backend/deploy/android_proxy.php del puente Y:."
            )
        raise RuntimeError(msg)
    if resp.status_code >= 400:
        raise RuntimeError(f"Proxy Android HTTP {resp.status_code}: {data}")
    resp.raise_for_status()
    return data


def _android_proxy_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }


def _parse_android_proxy_response(resp, *, context: str):
    import requests as _requests  # noqa: F401 — used by callers
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Respuesta inválida del proxy Android ({context}, HTTP {resp.status_code}): {resp.text[:200]}") from exc
    if isinstance(data, dict) and data.get('error'):
        msg = data.get('message') or str(data.get('error'))
        raise RuntimeError(msg)
    if resp.status_code >= 400:
        raise RuntimeError(f"Proxy Android HTTP {resp.status_code}: {data}")
    resp.raise_for_status()
    return data


def _toggle_android_device_mysql(key_id: int, habilitado: bool) -> dict:
    if not LICENMOVIL_MYSQL_HOST:
        raise RuntimeError('MySQL licenmovil no configurado')
    status = 1 if habilitado else 0
    conn = pymysql.connect(
        host=LICENMOVIL_MYSQL_HOST,
        user=LICENMOVIL_MYSQL_USER,
        password=LICENMOVIL_MYSQL_PASSWORD,
        database=LICENMOVIL_MYSQL_DB,
        charset='utf8mb4',
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            affected = cur.execute(
                'UPDATE misi_licand SET lc_habilitado = %s WHERE KeyId = %s',
                (status, int(key_id)),
            )
        conn.commit()
        if not affected:
            raise RuntimeError(f'No se encontró dispositivo KeyId={key_id}')
    finally:
        conn.close()
    return {'status': 'success', 'KeyId': int(key_id), 'lc_habilitado': status}


def _call_android_proxy_toggle(key_id: int, habilitado: bool) -> dict:
    """Endpoint dedicado android_proxy_toggle.php (archivo nuevo en masterisi)."""
    import requests as _requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    params = {
        'key': ANDROID_PROXY_KEY,
        'id': int(key_id),
        'status': 1 if habilitado else 0,
    }
    resp = _requests.get(
        ANDROID_PROXY_TOGGLE_URL,
        params=params,
        headers=_android_proxy_headers(),
        timeout=20.0,
        verify=False,
    )
    # 404 HTML = archivo no subido; 404 JSON = dispositivo inexistente
    if resp.status_code == 404 and 'json' not in (resp.headers.get('Content-Type') or '').lower():
        raise RuntimeError(
            'Falta subir android_proxy_toggle.php en masterisi.com.ar/WebService/. '
            'Ver backend/deploy/SUBIR_A_MASTERISI.txt en el puente Y:'
        )
    return _parse_android_proxy_response(resp, context='toggle')


def toggle_android_device(key_id: int, habilitado: bool):
    """Activa o desactiva un registro de misi_licand (celular o PC/navegador TCK)."""
    errors = []

    if LICENMOVIL_MYSQL_HOST:
        try:
            return _toggle_android_device_mysql(key_id, habilitado)
        except Exception as e:
            errors.append(f"MySQL directo: {e}")

    try:
        return _call_android_proxy_toggle(key_id, habilitado)
    except Exception as e:
        errors.append(str(e))

    try:
        data = _call_android_proxy({
            'action': 'toggle',
            'id': int(key_id),
            'status': 1 if habilitado else 0,
        }, method='GET')
        if isinstance(data, dict) and data.get('error'):
            raise RuntimeError(data.get('message') or data['error'])
        return data if isinstance(data, dict) else {
            'status': 'success',
            'KeyId': key_id,
            'lc_habilitado': 1 if habilitado else 0,
        }
    except Exception as e:
        errors.append(str(e))

    hint = (
        'Subir android_proxy_toggle.php a masterisi.com.ar '
        '(Y:\\ApolloSupport\\backend\\deploy\\android_proxy_toggle.php). '
        'Instrucciones: backend/deploy/SUBIR_A_MASTERISI.txt'
    )
    raise RuntimeError(f"{errors[-1] if errors else 'Error desconocido'}. {hint}")



def fetch_android_devices_summary():
    """
    Devuelve un resumen de dispositivos Android agrupado por cliente (primeros 4 chars del serial)
    y por tipo de app. Ideal para la vista principal del panel de control.
    """
    rows = _call_android_proxy({'action': 'summary'})

    # Reorganizar en estructura { client_code: { app: {...}, ... }, ... }
    summary = {}
    for r in rows:
        cc = r.get('client_code', '') or ''
        app = r.get('lc_app', '') or 'N/A'
        total = int(r.get('total', 0) or 0)
        habilitados = int(r.get('habilitados', 0) or 0)
        deshabilitados = int(r.get('deshabilitados', 0) or 0)

        if cc not in summary:
            summary[cc] = {
                'client_code': cc,
                'apps': {},
                'total_habilitados': 0,
                'total_dispositivos': 0,
                'ultimo_acceso': None,
                'primer_registro': None,
            }
        summary[cc]['apps'][app] = {
            'app': app,
            'app_nombre': APP_NAMES.get(app, app),
            'total': total,
            'habilitados': habilitados,
            'deshabilitados': deshabilitados,
        }
        summary[cc]['total_habilitados'] += habilitados
        summary[cc]['total_dispositivos'] += total

        # Actualizar fecha m?s reciente
        ua = r.get('ultimo_acceso')
        if ua:
            ua_str = str(ua)
            if summary[cc]['ultimo_acceso'] is None or ua_str > summary[cc]['ultimo_acceso']:
                summary[cc]['ultimo_acceso'] = ua_str

        pr = r.get('primer_registro')
        if pr:
            pr_str = str(pr)
            if summary[cc]['primer_registro'] is None or pr_str < summary[cc]['primer_registro']:
                summary[cc]['primer_registro'] = pr_str

    return list(summary.values())


def fetch_android_devices_by_client(client_code: str):
    """
    Devuelve el listado completo de dispositivos Android registrados para un cliente dado,
    identificado por los primeros 4 caracteres de su serial (ej: '0115').
    """
    rows = _call_android_proxy({'action': 'client', 'code': client_code})

    devices = []
    for r in rows:
        app = r.get('lc_app', '') or 'N/A'
        devices.append({
            'id': r.get('KeyId'),
            'android_id': r.get('lc_android_id') or '',
            'imei_serial': r.get('lc_imei_serial') or '',
            'serial_gescom': r.get('lc_serial_gescom') or '',
            'cuenta_google': r.get('lc_cuenta_google') or '',
            'modelo': r.get('lc_android_so') or '',
            'telefono': r.get('lc_no_telefono') or '',
            'habilitado': bool(int(r.get('lc_habilitado', 0) or 0)),
            'ult_acceso': str(r['lc_ult_acceso']) if r.get('lc_ult_acceso') else None,
            'fecha_registro': str(r['lc_fecha_registro']) if r.get('lc_fecha_registro') else None,
            'usuario_asignado': r.get('lc_fabricante') or '',
            'app': app,
            'app_nombre': APP_NAMES.get(app, app),
        })
    return devices

# -------------------------------------------------------------------------
# ALGORITMOS DE ENCRIPTACI��N / DESENCRIPTACI��N (Reconstruidos del ERP)
# -------------------------------------------------------------------------

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$"

def sym_alfa(num):
    if num < 10:
        return str(num)
    elif 10 <= num <= 35:
        return chr(55 + num)
    elif 36 <= num <= 61:
        return chr(61 + num)
    elif num == 62:
        return '#'
    elif num == 63:
        return '$'
    return '0'

def sym_alfa_r(sym):
    if sym == '#':
        return 62
    elif sym == '$':
        return 63
    elif sym < 'A':
        try:
            return int(sym)
        except ValueError:
            return 0
    elif 'A' <= sym <= 'Z':
        return ord(sym) - 55
    elif 'a' <= sym <= 'z':
        return ord(sym) - 61
    return 0

def deci2alfa(num):
    val = int(num)
    if val == 0:
        return "0"
    cadena = ""
    while val > 0:
        resto = val % 64
        cadena = sym_alfa(resto) + cadena
        val = val // 64
    return cadena

def alfa2deci(alfa):
    cadena = alfa.strip()
    valor = 0
    for i, sym in enumerate(reversed(cadena)):
        valor += sym_alfa_r(sym) * (64 ** i)
    return str(valor)

def decrip_fecha(exp_hex):
    """ Desencripta un string hexadecimal de fecha del ERP a formato 'YYYY-MM-DD' """
    if not exp_hex:
        return ""
    try:
        expira = bytes.fromhex(exp_hex).decode('latin1').strip()
    except Exception:
        return ""
    if len(expira) < 4:
        return ""
    year = alfa2deci(expira[:2])
    month = alfa2deci(expira[2:3]).zfill(2)
    day = alfa2deci(expira[3:4]).zfill(2)
    return f"{year}-{month}-{day}"

def encrip_fecha(date_str):
    """ Encripta una fecha 'YYYY-MM-DD' a formato hexadecimal compatible con el ERP """
    if not date_str:
        return ""
    try:
        parts = date_str.split('-')
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
    except Exception:
        return ""
    
    year_alfa = deci2alfa(year).rjust(2, '0')
    month_alfa = deci2alfa(month)
    day_alfa = deci2alfa(day)
    
    plain_str = f"{year_alfa}{month_alfa}{day_alfa}"
    return plain_str.encode('latin1').hex().upper()

def hex_to_num(hex_str):
    try:
        return int(hex_str, 16)
    except ValueError:
        return 0

def decriptar(en_str):
    """ Desencripta textos generales (como IDs, usuarios y rutas de terminales) """
    if not en_str or len(en_str) < 1:
        return ""
    factor = ord(en_str[0]) - 60
    if factor == 0:
        return ""
    en_str = en_str[1:]
    ss = ""
    while len(en_str) > 0:
        aux_hex = en_str[:3]
        aux = hex_to_num(aux_hex)
        aux_val = int(aux / factor)
        if aux_val > 0:
            ss += chr(aux_val)
        else:
            return ""
        en_str = en_str[3:]
    return ss

# -------------------------------------------------------------------------
# FUNCIONES DE CONSULTA Y EDICI��N A LA BASE DE DATOS
# -------------------------------------------------------------------------

def fetch_license_panel_summary():
    """
    Resumen por cliente (primeros 4 chars del serial), igual que Panel2016:
    cantidad de licencias, cortadas (m_down) y con cartel (m_tipmsg > 1).
    Incluye el tipo de cartel dominante (m_tipmsg) y su nombre en misi_messages.
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT m_num, m_des FROM misi_messages ORDER BY m_num ASC")
            msg_labels = {
                int(r["m_num"]): (r.get("m_des") or "").strip()
                for r in (cursor.fetchall() or [])
                if r.get("m_num") is not None
            }
            query = """
                SELECT
                    LEFT(l.l_number, 4) AS client_code,
                    COUNT(*) AS lic_total,
                    SUM(CASE WHEN COALESCE(l.l_desact, 0) = 0 THEN 1 ELSE 0 END) AS lic_activas,
                    SUM(CASE WHEN m.m_down THEN 1 ELSE 0 END) AS lic_cortadas,
                    SUM(CASE WHEN COALESCE(m.m_tipmsg, 1) > 1 THEN 1 ELSE 0 END) AS lic_cartel,
                    MAX(CASE WHEN COALESCE(m.m_tipmsg, 1) > 1 THEN m.m_tipmsg ELSE NULL END) AS tipmsg_max,
                    GROUP_CONCAT(DISTINCT CASE WHEN COALESCE(m.m_tipmsg, 1) > 1 THEN m.m_tipmsg ELSE NULL END
                                 ORDER BY m.m_tipmsg SEPARATOR ',') AS tipmsgs,
                    GROUP_CONCAT(DISTINCT CASE
                        WHEN COALESCE(m.m_tipmsg, 1) > 1 AND TRIM(IFNULL(m.m_showmode,'')) <> ''
                        THEN TRIM(m.m_showmode) ELSE NULL END
                        ORDER BY m.m_showmode SEPARATOR ',') AS showmodes
                FROM misi_licenses l
                LEFT JOIN misi_managelicen m ON l.l_number = m.m_number
                GROUP BY LEFT(l.l_number, 4)
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            summary = {}
            for r in rows:
                code = (r.get("client_code") or "").strip()
                total = int(r.get("lic_total") or 0)
                cortadas = int(r.get("lic_cortadas") or 0)
                cartel = int(r.get("lic_cartel") or 0)
                tipmsg = int(r["tipmsg_max"]) if r.get("tipmsg_max") is not None else 1
                tipmsgs_raw = (r.get("tipmsgs") or "").strip()
                tipmsgs = []
                if tipmsgs_raw:
                    for part in tipmsgs_raw.split(","):
                        part = part.strip()
                        if part.isdigit():
                            tipmsgs.append(int(part))
                showmodes_raw = (r.get("showmodes") or "").strip()
                showmodes = []
                if showmodes_raw:
                    for part in showmodes_raw.split(","):
                        part = part.strip()
                        if part and part not in showmodes:
                            showmodes.append(part)
                tipmsg_des = msg_labels.get(tipmsg, "") if tipmsg > 1 else ""
                summary[code] = {
                    "client_code": code,
                    "lic_total": total,
                    "lic_activas": int(r.get("lic_activas") or 0),
                    "lic_cortadas": cortadas,
                    "lic_cartel": cartel,
                    "cortado": total > 0 and cortadas >= total,
                    "cartel": cartel > 0,
                    "m_tipmsg": tipmsg if cartel > 0 else 1,
                    "m_tipmsg_des": tipmsg_des,
                    "tipmsgs": tipmsgs,
                    "m_showmode": showmodes[0] if len(showmodes) == 1 else (showmodes[0] if showmodes else "01"),
                    "showmodes": showmodes,
                }
            return summary
    finally:
        conn.close()


def save_license_management_for_clients(
    client_codes: list, m_down: bool, m_newdate: str, m_tipmsg: int, m_showmode: str, m_text: str
):
    """Aplica cartel/corte a todas las licencias activas de los clientes marcados (Monitoreo GesActi)."""
    codes = [str(c).strip()[:4].zfill(4) if str(c).strip().isdigit() else str(c).strip()[:4] for c in (client_codes or [])]
    codes = [c for c in codes if c]
    if not codes:
        raise ValueError("Debe indicar al menos un codigo de cliente.")

    applied = 0
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(codes))
            cursor.execute(
                f"SELECT l_number FROM misi_licenses WHERE COALESCE(l_desact, 0) = 0 AND LEFT(l_number, 4) IN ({placeholders})",
                codes,
            )
            serials = [row["l_number"] for row in cursor.fetchall() if row.get("l_number")]
        conn.close()
    except Exception:
        conn.close()
        raise

    for serial in serials:
        save_license_management(serial, m_down, m_newdate, m_tipmsg, m_showmode, m_text)
        applied += 1
    return {"status": "success", "aplicadas": applied, "clientes": len(codes)}


def fetch_licenses_by_client(client_code: str):
    """ Obtiene la lista de licencias de un cliente espec?fico, cruz?ndola con su gesti?n """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            # Seleccionar licencias asociadas al c?digo del cliente (los primeros 4 caracteres de l_number)
            query = """
                SELECT 
                    l.KeyID, l.l_number, l.l_date, l.l_modified, l.l_period, l.l_raso, l.l_nomfa, l.l_cuit, l.l_tele, l.l_locali, l.l_peri2016, l.l_desact,
                    m.m_down, m.m_newdate, m.m_tipmsg, m.m_showmode, m.m_text
                FROM misi_licenses l
                LEFT JOIN misi_managelicen m ON l.l_number = m.m_number
                WHERE LEFT(l.l_number, 4) = %s
            """
            cursor.execute(query, (client_code,))
            rows = cursor.fetchall()
            
            # Desencriptar campos para el frontend
            licenses = []
            for r in rows:
                lic = {
                    "KeyID": r["KeyID"],
                    "l_number": r["l_number"],
                    "l_date_enc": r["l_date"],
                    "l_date": decrip_fecha(r["l_date"]),
                    "l_modified_enc": r["l_modified"],
                    "l_modified": decrip_fecha(r["l_modified"]),
                    "l_period": r["l_period"],
                    "l_raso": r["l_raso"].strip() if r["l_raso"] else "",
                    "l_nomfa": r["l_nomfa"].strip() if r["l_nomfa"] else "",
                    "l_cuit": r["l_cuit"].strip() if r["l_cuit"] else "",
                    "l_tele": r["l_tele"].strip() if r["l_tele"] else "",
                    "l_locali": r["l_locali"].strip() if r["l_locali"] else "",
                    "l_peri2016": r["l_peri2016"].strip() if r["l_peri2016"] else "0",
                    "l_desact": bool(r["l_desact"]),
                    
                    # Datos de gesti?n de carteles / bloqueo
                    "m_down": bool(r["m_down"]) if r["m_down"] is not None else False,
                    "m_newdate": r["m_newdate"].strftime("%Y-%m-%d") if r["m_newdate"] else None,
                    "m_tipmsg": int(r["m_tipmsg"]) if r["m_tipmsg"] is not None else 1,
                    "m_showmode": r["m_showmode"] if r["m_showmode"] else "01",
                    "m_text": r["m_text"] if r["m_text"] else ""
                }
                licenses.append(lic)
            return licenses
    finally:
        conn.close()

def fetch_terminals_by_license(serial_number: str):
    """ Obtiene todos los nodos de terminal registrados para una licencia/serial, desencriptados """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT * FROM misi_terminals 
                WHERE t_number = %s AND t_passed != '5' AND (t_down IS NULL OR t_down != 'D')
            """
            cursor.execute(query, (serial_number,))
            rows = cursor.fetchall()
            
            terminals = []
            for r in rows:
                terminals.append({
                    "KeyID": r["KeyID"],
                    "t_number": r["t_number"],
                    "t_id": decriptar(r["t_id"]),
                    "t_id_enc": r["t_id"],
                    "t_user": decriptar(r["t_user"]),
                    "t_user_enc": r["t_user"],
                    "t_path": decriptar(r["t_path"]),
                    "t_path_enc": r["t_path"],
                    "t_OS": decriptar(r["t_OS"]),
                    "t_active": decrip_fecha(r["t_active"]),
                    "t_access": decrip_fecha(r["t_access"]),
                    "t_netmac": decriptar(r["t_netmac"]),
                    "t_disk": decriptar(r["t_disk"]),
                    "t_proc": decriptar(r["t_proc"]),
                    "t_moth": decriptar(r["t_moth"]),
                    "t_nofactu": r["t_nofactu"],
                    "t_obs": r["t_obs"].strip() if r["t_obs"] else "",
                    "t_passed": r["t_passed"]
                })
            return terminals
    finally:
        conn.close()


def fetch_reports_by_serial(serial: str, date_from: str = None, date_to: str = None):
    """Reportes de uso del serial (misi_report), igual que ReporteLicen de GesActi."""
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM misi_report WHERE r_number = %s"
            params = [serial]
            if date_from:
                sql += " AND r_date >= %s"
                params.append(date_from)
            if date_to:
                sql += " AND r_date <= %s"
                params.append(date_to)
            sql += " ORDER BY r_date DESC, r_hour DESC"
            cursor.execute(sql, params)
            rows = cursor.fetchall() or []
            out = []
            for r in rows:
                r_date = r.get("r_date")
                if hasattr(r_date, "strftime"):
                    r_date = r_date.strftime("%Y-%m-%d")
                f1 = r.get("r_FeFacI")
                f2 = r.get("r_FeFacF")
                if hasattr(f1, "strftime"):
                    f1 = f1.strftime("%Y-%m-%d")
                if hasattr(f2, "strftime"):
                    f2 = f2.strftime("%Y-%m-%d")
                out.append({
                    "KeyID": r.get("KeyID") or r.get("KeyId") or r.get("keyid"),
                    "r_number": r.get("r_number"),
                    "r_date": r_date,
                    "r_hour": (r.get("r_hour") or "").strip() if r.get("r_hour") else "",
                    "r_regfac": r.get("r_regfac"),
                    "r_FeFacI": f1,
                    "r_FeFacF": f2,
                    "r_NetMac": (r.get("r_NetMac") or "").strip() if r.get("r_NetMac") else "",
                    "r_ipexterna": (r.get("r_ipexterna") or "").strip() if r.get("r_ipexterna") else "",
                })
            return out
    finally:
        conn.close()


def fetch_report_nodes(report_id: int):
    """Nodos de un reporte (misi_nodorepo), igual que DetaNodos."""
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM misi_nodorepo WHERE n_idrepo = %s ORDER BY KeyID ASC",
                (int(report_id),),
            )
            rows = cursor.fetchall() or []
            from datetime import date, timedelta
            cutoff = date.today() - timedelta(days=60)
            nodes = []
            stale = 0
            recent = 0
            for r in rows:
                access = decrip_fecha(r.get("n_acces") or "")
                active = decrip_fecha(r.get("n_active") or "")
                is_stale = False
                if access:
                    try:
                        y, m, d = [int(x) for x in access.split("-")]
                        is_stale = date(y, m, d) < cutoff
                    except Exception:
                        pass
                if is_stale:
                    stale += 1
                else:
                    recent += 1
                nodes.append({
                    "KeyID": r.get("KeyID") or r.get("KeyId"),
                    "n_id": decriptar(r.get("n_id") or ""),
                    "n_user": decriptar(r.get("n_user") or ""),
                    "n_path": decriptar(r.get("n_path") or ""),
                    "n_active": active,
                    "n_acces": access,
                    "n_netmac": decriptar(r.get("n_netmac") or ""),
                    "n_disk": decriptar(r.get("n_disk") or ""),
                    "n_proc": decriptar(r.get("n_proc") or ""),
                    "n_moth": decriptar(r.get("n_moth") or ""),
                    "stale": is_stale,
                })
            return {
                "nodes": nodes,
                "total": len(nodes),
                "recent_60": recent,
                "stale_60": stale,
            }
    finally:
        conn.close()


def fetch_report_system(report_id: int):
    """Datos system/empresa del reporte (misi_sysrepo), igual que DetaSystem."""
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM misi_sysrepo WHERE s_idrepo = %s",
                (int(report_id),),
            )
            rows = cursor.fetchall() or []
            out = []
            for r in rows:
                out.append({
                    "KeyID": r.get("KeyID") or r.get("KeyId"),
                    "s_name": (r.get("s_name") or "").strip(),
                    "s_empre": (r.get("s_empre") or "").strip(),
                    "s_raso": (r.get("s_raso") or "").strip(),
                    "s_dir": (r.get("s_dir") or "").strip(),
                    "s_loc": (r.get("s_loc") or "").strip(),
                    "s_cp": (r.get("s_cp") or "").strip(),
                    "s_provinci": (r.get("s_provinci") or "").strip(),
                    "s_cuit": (r.get("s_cuit") or "").strip(),
                    "s_cliges": (r.get("s_cliges") or "").strip(),
                    "s_tel": (r.get("s_tel") or "").strip(),
                    "s_suc": (r.get("s_suc") or "").strip(),
                    "s_pv": (r.get("s_pv") or "").strip(),
                    "s_mail": (r.get("s_mail") or "").strip(),
                    "s_serial": (r.get("s_serial") or "").strip(),
                })
            return out
    finally:
        conn.close()


def save_license_management(serial: str, m_down: bool, m_newdate: str, m_tipmsg: int, m_showmode: str, m_text: str):
    """ Crea o actualiza las configuraciones de bloqueo y carteles para un serial.
    Si m_showmode es vacío / 'keep', conserva la demora actual (15/30/180) al cambiar el cartel.
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT m_showmode, m_text FROM misi_managelicen WHERE m_number = %s LIMIT 1",
                (serial,),
            )
            existing = cursor.fetchone()
            exists = bool(existing)

            keep_mode = str(m_showmode or "").strip().lower() in ("", "keep", "mantener")
            if keep_mode and exists and (existing.get("m_showmode") or "").strip():
                m_showmode = str(existing["m_showmode"]).strip()
            elif keep_mode:
                m_showmode = "01"
            else:
                m_showmode = str(m_showmode or "01").strip()[:2].zfill(2)

            db_date = None
            if m_newdate:
                try:
                    db_date = datetime.strptime(m_newdate, "%Y-%m-%d").date()
                except ValueError:
                    pass

            if exists:
                query = """
                    UPDATE misi_managelicen 
                    SET m_down = %s, m_newdate = %s, m_tipmsg = %s, m_showmode = %s, m_text = %s
                    WHERE m_number = %s
                """
                cursor.execute(query, (1 if m_down else 0, db_date, m_tipmsg, m_showmode, m_text, serial))
            else:
                query = """
                    INSERT INTO misi_managelicen (m_number, m_down, m_newdate, m_tipmsg, m_showmode, m_text)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (serial, 1 if m_down else 0, db_date, m_tipmsg, m_showmode, m_text))

            conn.commit()
            return {
                "status": "success",
                "message": "Gestión de cartel/bloqueo de licencia guardada exitosamente.",
                "m_showmode": m_showmode,
            }
    finally:
        conn.close()

def toggle_license_status(serial: str, is_desact: bool):
    """ Activa o desactiva por completo una licencia en misi_licenses """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            query = "UPDATE misi_licenses SET l_desact = %s WHERE l_number = %s"
            cursor.execute(query, (1 if is_desact else 0, serial))
            conn.commit()
            return {"status": "success", "l_desact": is_desact}
    finally:
        conn.close()

def update_license_auto_ext(serial: str, days: int, expiry_date: str = None):
    """ Actualiza el n?mero de d?as de auto-extensi?n y opcionalmente su fecha de expiraci?n """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            updates = ["l_peri2016 = %s"]
            params = [str(days)]
            
            if expiry_date:
                enc_date = encrip_fecha(expiry_date)
                updates.append("l_date = %s")
                params.append(enc_date)
                
            # Agregar la fecha de modificaci?n actual
            now_str = datetime.now().strftime("%Y-%m-%d")
            updates.append("l_modified = %s")
            params.append(encrip_fecha(now_str))
            
            params.append(serial)
            query = f"UPDATE misi_licenses SET {', '.join(updates)} WHERE l_number = %s"
            cursor.execute(query, params)
            conn.commit()
            return {"status": "success", "l_peri2016": days, "l_date": expiry_date}
    finally:
        conn.close()

def deactivate_terminal_node(serial: str, t_id_enc: str, t_user_enc: str, t_path_enc: str):
    """ Marca un nodo como desactivado (t_passed = '5') de forma que no pueda volver a usarse """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            # Desactivar en misi_terminals (como en Registro.prg)
            query = """
                UPDATE misi_terminals 
                SET t_passed = '5'
                WHERE t_number = %s AND t_id = %s AND t_user = %s AND t_path = %s
            """
            cursor.execute(query, (serial, t_id_enc, t_user_enc, t_path_enc))
            conn.commit()
            return {"status": "success", "message": "Terminal desactivada correctamente."}
    finally:
        conn.close()

def register_new_serial(
    l_number: str, l_date: str, l_peri2016: int, l_raso: str, l_nomfa: str, 
    l_cuit: str, l_tele: str, l_locali: str
):
    """ Registra una nueva licencia directamente en misi_licenses """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            # Verificar si ya existe
            cursor.execute("SELECT COUNT(*) as cant FROM misi_licenses WHERE l_number = %s", (l_number,))
            if cursor.fetchone()["cant"] > 0:
                raise ValueError("El n?mero serial ya existe en la base de datos.")
                
            enc_date = encrip_fecha(l_date)
            now_str = datetime.now().strftime("%Y-%m-%d")
            enc_mod = encrip_fecha(now_str)
            
            query = """
                INSERT INTO misi_licenses (
                    l_number, l_date, l_modified, l_peri2016, l_raso, l_nomfa, 
                    l_cuit, l_tele, l_locali, l_desact, l_period, l_passed
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, '12', '0')
            """
            cursor.execute(query, (
                l_number, enc_date, enc_mod, str(l_peri2016), l_raso, l_nomfa,
                l_cuit, l_tele, l_locali
            ))
            conn.commit()
            return {"status": "success", "l_number": l_number}
    finally:
        conn.close()


def _harbour_val(ch) -> int:
    s = str(ch or "").strip()
    if not s:
        return 0
    digits = ""
    for c in s:
        if c.isdigit() or (c == "." and "." not in digits):
            digits += c
        else:
            break
    if not digits or digits == ".":
        return 0
    try:
        return int(float(digits))
    except ValueError:
        return 0


def bin2deci(binario: str) -> int:
    cadena = (binario or "").strip()
    valor = 0
    for i, ch in enumerate(reversed(cadena)):
        valor += (1 if ch == "1" else 0) * (2 ** i)
    return valor


def bin2alfa(binario: str) -> str:
    return deci2alfa(bin2deci(binario))


def load_gesacti_modules():
    """M?dulos ApolloGesCom (tabla Modulos de GesActi en M:\\programa)."""
    json_path = os.path.join(os.path.dirname(__file__), "data", "modulos_gesacti.json")
    dbf_paths = [
        os.getenv("GESACTI_MODULOS_DBF", ""),
        r"\\192.168.10.24\X\programa\MODULOS.DBF",
        r"m:\programa\MODULOS.DBF",
        r"x:\Util_Activacion\MODULOS.DBF",
        os.path.join(os.path.dirname(__file__), "data", "MODULOS.DBF"),
    ]
    try:
        from dbfread import DBF
        for path in dbf_paths:
            if path and os.path.exists(path):
                rows = []
                for r in DBF(path, encoding="latin1"):
                    rows.append({
                        "m_num": str(r.get("MNUM") or "").strip().zfill(3),
                        "m_exe": str(r.get("MEXE") or "").strip(),
                        "m_desc": str(r.get("MDESC") or "").strip(),
                        "m_erp": bool(r.get("MERP")),
                        "m_single": bool(r.get("MSINGLE")),
                        "m_pharmakos": bool(r.get("MPHARMAKOS")),
                        "m_clock": bool(r.get("MCLOCK")),
                        "m_commerce": bool(r.get("MCOMMERCE")),
                        "m_little": bool(r.get("MLITTLE")),
                    })
                if rows:
                    return rows
    except Exception:
        pass
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def check_client_code_version(code: str, versi: str) -> bool:
    """Misma regla que CheckVersi de GesActi (E/S/R/P)."""
    c = ((code or " ") + " ")[0].upper()
    v = (versi or "E").upper()[:1]
    if v == "E":
        return c < "M"
    if v == "S":
        return c == "M"
    if v == "R":
        return c == "R"
    if v == "P":
        return c == "V"
    return True


def encode_serial_date(expiry: date) -> str:
    aux = expiry.strftime("%Y%m%d")
    return deci2alfa(int(aux[:4])) + deci2alfa(int(aux[4:6])) + deci2alfa(int(aux[6:8]))


def generate_gesacti_serial(client_code: str, expiry_date: str, module_nums=None, all_modules: bool = False):
    """
    Replica CalculaNuevoSerial de GesActi (Activa.prg).
    Formato 25: CCCC-FECH-MODULOSXXXX-CRC
    """
    code = (client_code or "").strip().upper().ljust(4)[:4]
    if len(code.strip()) != 4:
        raise ValueError("El c?digo de cliente GesCom debe tener 4 caracteres.")
    try:
        y, m, d = [int(x) for x in expiry_date.split("-")]
        exp = date(y, m, d)
    except Exception:
        raise ValueError("Fecha de expiraci?n inv?lida (YYYY-MM-DD).")
    today = date.today()
    if exp < today or exp > today + timedelta(days=60):
        raise ValueError("La fecha otorgada est? fuera del rango permitido (hoy a +60 d?as), igual que GesActi.")

    aux_crc = 0
    aux_serial = code + "-"
    for i, ch in enumerate(aux_serial[:4], start=1):
        aux_crc += _harbour_val(ch) * i

    encoded_date = encode_serial_date(exp)
    if len(encoded_date) != 4:
        encoded_date = (encoded_date + "0000")[:4]
    for i in range(4):
        aux_crc += ord(encoded_date[i]) * 7
    aux_serial += encoded_date + "-"

    if all_modules:
        aux2 = "$$$$$$$$$$$$"
    else:
        bits = ["0"] * 72
        for num in module_nums or []:
            try:
                n = int(str(num).strip())
            except ValueError:
                continue
            if 1 <= n <= 72:
                bits[72 - n] = "1"
        bitstr = "".join(bits)
        aux2 = ""
        for i in range(12):
            chunk = bitstr[i * 6:(i + 1) * 6]
            aux2 += bin2alfa(chunk)
        aux2 = (aux2 + "0" * 12)[:12]

    for i in range(12):
        aux_crc += ord(aux2[i])
    aux_serial += aux2 + "-"

    crc_alfa = deci2alfa(aux_crc)
    if len(crc_alfa) == 1:
        crc_alfa = "0" + crc_alfa
    aux_serial += crc_alfa[-2:]
    return aux_serial


def fetch_messages_templates():
    """ Trae los carteles de aviso tipificados (misi_messages). """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT m_num, m_des, m_text FROM misi_messages ORDER BY m_num ASC")
            rows = cursor.fetchall() or []
            templates = []
            for r in rows:
                num = int(r.get("m_num") or 0)
                text = (r.get("m_text") or "").replace("CRLF", "\n")
                des = (r.get("m_des") or "").strip()
                templates.append({
                    "id": num,
                    "m_num": num,
                    "label": des,
                    "m_des": des,
                    "text": text,
                    "m_text": text,
                })
            return templates
    finally:
        conn.close()


def save_message_template(m_num: int, m_des: str, m_text: str):
    """Crea o actualiza un cartel de aviso en misi_messages."""
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS cant FROM misi_messages WHERE m_num = %s", (m_num,))
            exists = cursor.fetchone()["cant"] > 0
            text = (m_text or "").replace("\r\n", "\n").replace("\n", "CRLF")
            des = (m_des or "")[:30]
            if exists:
                cursor.execute(
                    "UPDATE misi_messages SET m_des = %s, m_text = %s WHERE m_num = %s",
                    (des, text, m_num),
                )
            else:
                cursor.execute(
                    "INSERT INTO misi_messages (m_num, m_des, m_text) VALUES (%s, %s, %s)",
                    (m_num, des, text),
                )
            conn.commit()
            return {"status": "success", "m_num": m_num}
    finally:
        conn.close()


# -------------------------------------------------------------------------
# Activaciones pendientes (misi_request) y Extensiones (misi_extension)
# -------------------------------------------------------------------------

REQUEST_STATE_LABELS = {
    "0": "Pendiente",
    "1": "Activado",
    "2": "Denegado",
    "3": "Activado c/mensaje",
    "4": "Activado c/fecha",
    "": "Sin estado",
}


def fetch_activation_requests(pending_only: bool = True):
    """Listado de solicitudes OnLine (misi_request), como ActiPenOL de GesActi."""
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            if pending_only:
                cursor.execute(
                    "SELECT * FROM misi_request WHERE r_state = %s OR r_state = %s OR TRIM(IFNULL(r_state,'')) = %s "
                    "ORDER BY KeyID DESC",
                    ("0", "", ""),
                )
            else:
                cursor.execute("SELECT * FROM misi_request ORDER BY KeyID DESC LIMIT 500")
            rows = cursor.fetchall() or []
            out = []
            for r in rows:
                state = (r.get("r_state") or "").strip() or "0"
                out.append({
                    "KeyID": r.get("KeyID"),
                    "r_number": (r.get("r_number") or "").strip(),
                    "client_code": ((r.get("r_number") or "")[:4] or "").strip(),
                    "r_id": decriptar(r.get("r_id")),
                    "r_id_enc": r.get("r_id"),
                    "r_user": decriptar(r.get("r_user")),
                    "r_user_enc": r.get("r_user"),
                    "r_path": decriptar(r.get("r_path")),
                    "r_path_enc": r.get("r_path"),
                    "r_OS": decriptar(r.get("r_OS")),
                    "r_OS_enc": r.get("r_OS"),
                    "r_date": decrip_fecha(r.get("r_date")),
                    "r_date_enc": r.get("r_date"),
                    "r_state": state,
                    "r_state_label": REQUEST_STATE_LABELS.get(state, state),
                    "r_message": (r.get("r_message") or "").strip(),
                    "r_disk": decriptar(r.get("r_disk")),
                    "r_disk_enc": r.get("r_disk"),
                    "r_proc": decriptar(r.get("r_proc")),
                    "r_proc_enc": r.get("r_proc"),
                    "r_moth": decriptar(r.get("r_moth")),
                    "r_moth_enc": r.get("r_moth"),
                    "r_netmac": decriptar(r.get("r_netmac")),
                    "r_netmac_enc": r.get("r_netmac"),
                })
            return out
    finally:
        conn.close()


def resolve_activation_request(key_id: int, state: str, message: str = None, new_date: str = None):
    """
    Resuelve una solicitud (ActivarNormal de GesActi) sobre MySQL web.
    Estados: 0 pendiente, 1 activar, 2 denegar, 3 c/mensaje, 4 c/fecha.
    """
    state = str(state or "").strip()
    if state not in ("0", "1", "2", "3", "4"):
        raise ValueError("Estado inválido. Use 0,1,2,3 o 4.")
    if state == "3" and not (message or "").strip():
        raise ValueError("Debe indicar un mensaje para activar con mensaje.")
    if state == "4" and not (new_date or "").strip():
        raise ValueError("Debe indicar la nueva fecha de expiración (YYYY-MM-DD).")

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM misi_request WHERE KeyID = %s", (int(key_id),))
            req = cursor.fetchone()
            if not req:
                raise ValueError("Solicitud no encontrada.")

            serial = (req.get("r_number") or "").strip()
            cursor.execute("SELECT KeyID, l_number FROM misi_licenses WHERE l_number = %s", (serial,))
            lic = cursor.fetchone()
            if not lic:
                raise ValueError("Ese número Serial no se encuentra Activado.")

            today_enc = encrip_fecha(date.today().isoformat())

            if new_date and state == "4":
                enc_date = encrip_fecha(new_date.strip()[:10])
                if not enc_date:
                    raise ValueError("Fecha de expiración inválida.")
                cursor.execute(
                    "UPDATE misi_licenses SET l_date = %s, l_modified = %s, l_passed = '1' WHERE l_number = %s",
                    (enc_date, today_enc, serial),
                )

            # Upsert terminal (mismo criterio que ActivarNormal web)
            cursor.execute(
                """
                SELECT KeyID FROM misi_terminals
                WHERE t_number = %s AND t_user = %s AND t_id = %s AND t_path = %s
                  AND IFNULL(t_netmac,'') = IFNULL(%s,'')
                  AND IFNULL(t_disk,'') = IFNULL(%s,'')
                  AND IFNULL(t_proc,'') = IFNULL(%s,'')
                  AND IFNULL(t_moth,'') = IFNULL(%s,'')
                LIMIT 1
                """,
                (
                    serial,
                    req.get("r_user"),
                    req.get("r_id"),
                    req.get("r_path"),
                    req.get("r_netmac"),
                    req.get("r_disk"),
                    req.get("r_proc"),
                    req.get("r_moth"),
                ),
            )
            term = cursor.fetchone()
            if term:
                cursor.execute(
                    """
                    UPDATE misi_terminals SET
                        t_active = %s, t_OS = %s, t_passed = '1',
                        t_disk = %s, t_proc = %s, t_moth = %s, t_netmac = %s
                    WHERE KeyID = %s
                    """,
                    (
                        today_enc,
                        req.get("r_OS"),
                        req.get("r_disk"),
                        req.get("r_proc"),
                        req.get("r_moth"),
                        req.get("r_netmac"),
                        term["KeyID"],
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO misi_terminals
                        (t_number, t_user, t_id, t_path, t_active, t_OS, t_passed, t_disk, t_proc, t_moth, t_netmac)
                    VALUES (%s,%s,%s,%s,%s,%s,'1',%s,%s,%s,%s)
                    """,
                    (
                        serial,
                        req.get("r_user"),
                        req.get("r_id"),
                        req.get("r_path"),
                        today_enc,
                        req.get("r_OS"),
                        req.get("r_disk"),
                        req.get("r_proc"),
                        req.get("r_moth"),
                        req.get("r_netmac"),
                    ),
                )

            req_date_enc = req.get("r_date")
            if new_date and state == "4":
                req_date_enc = encrip_fecha(new_date.strip()[:10])

            msg = message if message is not None else (req.get("r_message") or "")
            cursor.execute(
                "UPDATE misi_request SET r_state = %s, r_message = %s, r_date = %s WHERE KeyID = %s",
                (state, (msg or "")[:300], req_date_enc or "", int(key_id)),
            )
            conn.commit()
            return {
                "status": "success",
                "KeyID": int(key_id),
                "r_state": state,
                "r_state_label": REQUEST_STATE_LABELS.get(state, state),
            }
    finally:
        conn.close()


def fetch_pending_extensions(pending_only: bool = True):
    """Extensiones OnLine (misi_extension), como ExtenOl de GesActi."""
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            if pending_only:
                cursor.execute(
                    """
                    SELECT e.*, l.l_period, l.l_raso, l.l_nomfa
                    FROM misi_extension e
                    LEFT JOIN misi_licenses l ON l.l_number = e.e_number
                    WHERE e.e_newdate IS NULL OR TRIM(IFNULL(e.e_newdate,'')) = '' OR e.e_newdate = %s
                    ORDER BY e.KeyID DESC
                    """,
                    ("        ",),
                )
            else:
                cursor.execute(
                    """
                    SELECT e.*, l.l_period, l.l_raso, l.l_nomfa
                    FROM misi_extension e
                    LEFT JOIN misi_licenses l ON l.l_number = e.e_number
                    ORDER BY e.KeyID DESC
                    LIMIT 500
                    """
                )
            rows = cursor.fetchall() or []
            out = []
            for r in rows:
                e_date = decrip_fecha(r.get("e_date"))
                e_new = decrip_fecha(r.get("e_newdate"))
                period = 0
                try:
                    period = int(str(r.get("l_period") or "0").strip() or "0")
                except ValueError:
                    period = 0
                suggested = ""
                if e_date:
                    try:
                        base = datetime.strptime(e_date, "%Y-%m-%d").date()
                        suggested = (base + timedelta(days=period or 0)).isoformat()
                    except Exception:
                        suggested = e_date
                out.append({
                    "KeyID": r.get("KeyID"),
                    "e_number": (r.get("e_number") or "").strip(),
                    "client_code": ((r.get("e_number") or "")[:4] or "").strip(),
                    "client_name": (r.get("l_raso") or r.get("l_nomfa") or "").strip(),
                    "e_date": e_date,
                    "e_date_enc": r.get("e_date"),
                    "e_newdate": e_new,
                    "e_newdate_enc": r.get("e_newdate"),
                    "l_period": period,
                    "suggested_newdate": suggested,
                    "pending": not bool((r.get("e_newdate") or "").strip()),
                })
            return out
    finally:
        conn.close()


def approve_extension(key_id: int, new_date: str = None):
    """
    Genera extensión (ExtenOl G): actualiza misi_licenses.l_date y misi_extension.e_newdate.
    Si no se pasa new_date, usa e_date + l_period días.
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM misi_extension WHERE KeyID = %s", (int(key_id),))
            ext = cursor.fetchone()
            if not ext:
                raise ValueError("Extensión no encontrada.")
            if (ext.get("e_newdate") or "").strip():
                raise ValueError("Esta extensión ya fue generada.")

            serial = (ext.get("e_number") or "").strip()
            cursor.execute(
                "SELECT KeyID, l_number, l_period, l_date FROM misi_licenses WHERE l_number = %s",
                (serial,),
            )
            lic = cursor.fetchone()
            if not lic:
                raise ValueError("El cliente no se encuentra registrado como usuario ApolloGesCom.")

            period = 0
            try:
                period = int(str(lic.get("l_period") or "0").strip() or "0")
            except ValueError:
                period = 0

            if new_date and str(new_date).strip():
                target = str(new_date).strip()[:10]
            else:
                base_s = decrip_fecha(ext.get("e_date")) or decrip_fecha(lic.get("l_date"))
                if not base_s:
                    raise ValueError("No hay fecha base para calcular la extensión.")
                base = datetime.strptime(base_s, "%Y-%m-%d").date()
                target = (base + timedelta(days=period)).isoformat()

            enc_new = encrip_fecha(target)
            if not enc_new:
                raise ValueError("Fecha de vencimiento inválida.")
            today_enc = encrip_fecha(date.today().isoformat())

            cursor.execute(
                "UPDATE misi_licenses SET l_date = %s, l_modified = %s, l_passed = '1' WHERE l_number = %s",
                (enc_new, today_enc, serial),
            )
            cursor.execute(
                "UPDATE misi_extension SET e_newdate = %s WHERE KeyID = %s",
                (enc_new, int(key_id)),
            )
            conn.commit()
            return {
                "status": "success",
                "KeyID": int(key_id),
                "e_number": serial,
                "e_newdate": target,
            }
    finally:
        conn.close()
