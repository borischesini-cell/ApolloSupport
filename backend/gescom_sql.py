"""
Lectura del Gescom SQL (MySQL agc_sql_grupomaster).
CBU / débito automático: ventas_clienda + cuenta bancaria (bancos_datosda) + banco BCRA (caja_bcra).
"""
from __future__ import annotations

import os
from typing import Any

import pymysql
from pymysql.cursors import DictCursor


def _cfg() -> dict:
    return {
        "host": os.getenv("GESCOM_SQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("GESCOM_SQL_PORT", "3316")),
        "user": os.getenv("GESCOM_SQL_USER", "root"),
        "password": os.getenv("GESCOM_SQL_PASSWORD", "ingenieria"),
        "database": os.getenv("GESCOM_SQL_DB", "agc_sql_grupomaster"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "connect_timeout": 8,
        "read_timeout": 15,
    }


def _connect():
    cfg = _cfg()
    hosts: list[str] = []
    for raw in (cfg["host"], os.getenv("GESCOM_SQL_HOSTS", "192.168.11.223,127.0.0.1")):
        for host in str(raw or "").split(","):
            host = host.strip()
            if host and host not in hosts:
                hosts.append(host)
    last_err: Exception | None = None
    for host in hosts:
        try:
            cfg["host"] = host
            return pymysql.connect(**cfg)
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    raise RuntimeError("Sin host MySQL GesCom")


def search_clients(query: str, limit: int = 80) -> list[dict]:
    """Busca clientes en ventas_clientes (GesCom SQL) por nombre o CCOD."""
    raw = (query or "").strip()
    if len(raw) < 2:
        return []
    like = f"%{raw}%"
    digits = "".join(ch for ch in raw if ch.isdigit()).lstrip("0")
    sql = """
        SELECT
            TRIM(CCOD) AS codigo,
            TRIM(CRASO) AS razon_social,
            TRIM(IFNULL(CNOMFA, '')) AS nombre_fantasia
        FROM ventas_clientes
        WHERE UPPER(CRASO) LIKE UPPER(%s)
           OR UPPER(IFNULL(CNOMFA, '')) LIKE UPPER(%s)
           OR TRIM(CCOD) LIKE %s
    """
    params: list[Any] = [like, like, like]
    if digits:
        sql += " OR TRIM(CCOD) LIKE %s OR RIGHT(TRIM(CCOD), %s) = %s"
        params.extend([f"%{digits}%", len(digits), digits])
    sql += " ORDER BY CCOD LIMIT %s"
    params.append(int(limit))

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() or []
    finally:
        conn.close()

    hits = []
    seen: set[str] = set()
    for r in rows:
        codigo = _trim(r.get("codigo"))
        if not codigo or codigo in seen:
            continue
        seen.add(codigo)
        hits.append({
            "codigo": codigo,
            "razon_social": _trim(r.get("razon_social")) or f"Cliente {codigo}",
            "nombre_fantasia": _trim(r.get("nombre_fantasia")) or None,
            "cclifac": codigo,
            "activo": True,
        })
    return hits


def _codes_for_cli(code: str) -> list[str]:
    raw = str(code or "").strip()
    if not raw:
        return []
    codes = [raw]
    if raw.isdigit():
        padded = raw.zfill(7)
        if padded not in codes:
            codes.append(padded)
        stripped = raw.lstrip("0") or "0"
        if stripped not in codes:
            codes.append(stripped)
        if len(raw) < 7:
            codes.append(raw.zfill(4))
    return codes


def _trim(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\x00", "").strip()


def get_client_cbus(client_code: str) -> list[dict]:
    codes = _codes_for_cli(client_code)
    if not codes:
        return []

    placeholders = ",".join(["%s"] * len(codes))
    sql = f"""
        SELECT
            d.KeyID AS id,
            TRIM(d.CCLI) AS ccli,
            TRIM(d.CCBU) AS cbu,
            TRIM(d.CBAN) AS cban,
            d.CACT AS activo,
            TRIM(d.CTAR) AS tarifa,
            TRIM(d.CNUMTAR) AS nro_tarjeta,
            TRIM(b.DNOMORD) AS cuenta_nombre,
            TRIM(b.DNUMCUE) AS cuenta_numero,
            TRIM(b.DCODSER) AS cuenta_servicio,
            TRIM(bc.DESCRIPCIO) AS banco_cbu
        FROM ventas_clienda d
        LEFT JOIN bancos_datosda b
            ON TRIM(b.DBAN) = TRIM(d.CBAN)
        LEFT JOIN caja_bcra bc
            ON bc.CODBAN = LPAD(LEFT(TRIM(IFNULL(d.CCBU, '')), 3), 4, '0')
        WHERE TRIM(d.CCLI) IN ({placeholders})
        ORDER BY IFNULL(d.CACT, 0) DESC, d.KeyID ASC
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, codes)
            rows = cur.fetchall() or []
    finally:
        conn.close()

    out = []
    for r in rows:
        activo = r.get("activo")
        out.append({
            "id": r.get("id"),
            "ccli": _trim(r.get("ccli")),
            "cbu": _trim(r.get("cbu")),
            "cban": _trim(r.get("cban")),
            "activo": bool(int(activo)) if activo not in (None, "") else False,
            "tarifa": _trim(r.get("tarifa")),
            "nro_tarjeta": _trim(r.get("nro_tarjeta")),
            "cuenta_nombre": _trim(r.get("cuenta_nombre")),
            "cuenta_numero": _trim(r.get("cuenta_numero")),
            "cuenta_servicio": _trim(r.get("cuenta_servicio")),
            "banco_cbu": _trim(r.get("banco_cbu")),
        })
    return out
