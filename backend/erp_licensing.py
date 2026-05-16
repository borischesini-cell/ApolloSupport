"""
-------------------------------------------------------------------------
Servicio de Gestión de Licencias ERP (Conexión a MySQL Remoto)
Proyecto: ApolloSupport
Descripción: Maneja la lógica de negocio, encriptación/desencriptación
             y consultas directas al servidor de licencias MySQL.
-------------------------------------------------------------------------
"""

import os
import pymysql
from datetime import datetime

# Credenciales fijas obtenidas de ODBC/Registry
MYSQL_HOST = 'mysql1.apollogescom.com.ar'
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'Mas1Ter2Isi3'
MYSQL_DB = 'apolloge_masterisi'

def get_mysql_connection():
    """ Abre y retorna una conexión directa a la base de datos de licencias de MySQL """
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# -------------------------------------------------------------------------
# ALGORITMOS DE ENCRIPTACIÓN / DESENCRIPTACIÓN (Reconstruidos del ERP)
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
# FUNCIONES DE CONSULTA Y EDICIÓN A LA BASE DE DATOS
# -------------------------------------------------------------------------

def fetch_licenses_by_client(client_code: str):
    """ Obtiene la lista de licencias de un cliente específico, cruzándola con su gestión """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            # Seleccionar licencias asociadas al código del cliente (los primeros 4 caracteres de l_number)
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
                    
                    # Datos de gestión de carteles / bloqueo
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

def save_license_management(serial: str, m_down: bool, m_newdate: str, m_tipmsg: int, m_showmode: str, m_text: str):
    """ Crea o actualiza las configuraciones de bloqueo y carteles para un serial """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            # Comprobar si ya existe
            cursor.execute("SELECT COUNT(*) as cant FROM misi_managelicen WHERE m_number = %s", (serial,))
            exists = cursor.fetchone()["cant"] > 0
            
            # Convertir fecha
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
            return {"status": "success", "message": "Gestión de cartel/bloqueo de licencia guardada exitosamente."}
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
    """ Actualiza el número de días de auto-extensión y opcionalmente su fecha de expiración """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            updates = ["l_peri2016 = %s"]
            params = [str(days)]
            
            if expiry_date:
                enc_date = encrip_fecha(expiry_date)
                updates.append("l_date = %s")
                params.append(enc_date)
                
            # Agregar la fecha de modificación actual
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
                raise ValueError("El número serial ya existe en la base de datos.")
                
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

def fetch_messages_templates():
    """ Trae los mensajes preconfigurados (carteles tipo) de la base de datos de MySQL """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT m_num, m_des, m_text FROM misi_messages ORDER BY m_num ASC")
            return cursor.fetchall()
    finally:
        conn.close()
