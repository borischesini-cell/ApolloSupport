"""
Mantiene CLIGESCO.DBF de GesActi en alta, modificación y baja lógica.

La tabla viva está en M:\programa\ (junto a MODULOS, CLIESERI, etc.).
Otras copias (bases, Util_Activacion) no se tocan salvo que se listen en
CLIGESCO_DBF_EXTRA.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import dbf

LIVE_CLIGESCO = r"m:\programa\CLIGESCO.DBF"

DEFAULT_PATHS = [
    os.getenv("CLIGESCO_DBF", "").strip(),
    LIVE_CLIGESCO,
]


def cligesco_paths() -> list[str]:
    extra = os.getenv("CLIGESCO_DBF_EXTRA", "")
    seen = set()
    paths = []
    for raw in DEFAULT_PATHS + [p.strip() for p in extra.split(";")]:
        if not raw:
            continue
        path = os.path.abspath(raw)
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        if os.path.isfile(path):
            paths.append(path)
    return paths


def primary_cligesco_path() -> str | None:
    """Tabla en uso real: M:\\programa\\CLIGESCO.DBF."""
    live = os.path.abspath(os.getenv("CLIGESCO_DBF", "").strip() or LIVE_CLIGESCO)
    if os.path.isfile(live):
        return live
    paths = cligesco_paths()
    return paths[0] if paths else None


def _clip(value: Any, length: int) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\x00", "").strip()
    return text[:length]


def _as_date(value: Any) -> date | None:
    if value in (None, "", "None"):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _open_table(path: str):
    table = dbf.Table(path, codepage="cp1252")
    table.open(mode=dbf.READ_WRITE)
    return table


def list_codes() -> set[str]:
    codes: set[str] = set()
    for path in cligesco_paths():
        table = None
        try:
            table = dbf.Table(path, codepage="cp1252")
            table.open(mode=dbf.READ_ONLY)
            for rec in table:
                if dbf.is_deleted(rec):
                    continue
                code = str(rec.CCOD or "").strip().upper()
                if code:
                    codes.add(code)
        except Exception:
            continue
        finally:
            if table is not None:
                try:
                    table.close()
                except Exception:
                    pass
    return codes


def upsert_client(payload: dict, *, create: bool = False) -> dict:
    """
    Inserta o actualiza por CCOD en todas las copias de CLIGESCO.DBF.
    No pisa CSERIAL / CCANFAC / CCANSER / CDIASTOPE en modificación si no vienen.
    """
    codigo = _clip(payload.get("codigo"), 4).upper()
    if codigo.isdigit():
        codigo = codigo.zfill(4)[:4]
    if not codigo:
        raise ValueError("El cliente no tiene código GesCom (CCOD) para grabar en CLIGESCO.DBF.")

    paths = cligesco_paths()
    if not paths:
        raise FileNotFoundError(
            "No se encontró CLIGESCO.DBF en M:\\programa\\. "
            "Definí CLIGESCO_DBF si está en otra ruta."
        )

    razon = _clip(payload.get("razon_social"), 50)
    fantasia = _clip(payload.get("nombre_fantasia") or razon, 30)
    cdes = fantasia or _clip(razon, 30)
    activo = payload.get("activo")
    if activo is None:
        activo = True

    fields = {
        "CCOD": codigo.ljust(4)[:4],
        "CDES": cdes,
        "CPARTE": _clip(payload.get("cparte") or payload.get("identificador_fiscal"), 9),
        "CACTI": bool(activo),
        "CNOMFA": fantasia,
        "CVERSION": _clip(payload.get("version_apollo") or "E", 1).upper() or "E",
        "CCLIFAC": _clip(payload.get("cclifac"), 7),
        "CSALDO": float(payload.get("saldo") or 0.0),
        "CRASO": razon or cdes,
        "CVENDEDOR": _clip(payload.get("vendedor_codigo"), 5),
        "CNOMVEN": _clip(payload.get("vendedor_nombre"), 30),
        "CCLAS": _clip(payload.get("clasificacion_codigo"), 5),
        "CNOMCLAS": _clip(payload.get("clasificacion_nombre"), 30),
        "CLOCALIDA": _clip(payload.get("localidad"), 30),
        "CEMAIL": _clip(payload.get("email"), 100),
        "CEXTRACTO": payload.get("extracto") or "",
    }
    fecha_reg = _as_date(payload.get("fecha_registro")) or date.today()
    fecha_pago = _as_date(payload.get("fecha_ultimo_pago"))
    dias_tope = payload.get("dias_tope")
    written = []
    errors = []

    for path in paths:
        table = None
        try:
            table = _open_table(path)
            found = None
            for rec in table:
                if dbf.is_deleted(rec):
                    continue
                if str(rec.CCOD or "").strip().upper() == codigo:
                    found = rec
                    break
            if found is None:
                if not create and not payload.get("force_insert"):
                    # Alta implícita si el código no está en esta copia
                    pass
                table.append({
                    **fields,
                    "CSERIAL": "",
                    "CDIASTOPE": int(dias_tope) if dias_tope not in (None, "") else 60,
                    "CCANFAC": 0,
                    "CCANSER": 0,
                    "CFECHA": fecha_reg,
                    "CULPA": fecha_pago,
                })
                written.append({"path": path, "action": "insert"})
            else:
                with found as rec:
                    rec.CDES = fields["CDES"]
                    rec.CPARTE = fields["CPARTE"]
                    rec.CACTI = fields["CACTI"]
                    rec.CNOMFA = fields["CNOMFA"]
                    rec.CVERSION = fields["CVERSION"]
                    rec.CCLIFAC = fields["CCLIFAC"]
                    rec.CSALDO = fields["CSALDO"]
                    rec.CRASO = fields["CRASO"]
                    rec.CVENDEDOR = fields["CVENDEDOR"]
                    rec.CNOMVEN = fields["CNOMVEN"]
                    rec.CCLAS = fields["CCLAS"]
                    rec.CNOMCLAS = fields["CNOMCLAS"]
                    rec.CLOCALIDA = fields["CLOCALIDA"]
                    rec.CEMAIL = fields["CEMAIL"]
                    rec.CEXTRACTO = fields["CEXTRACTO"]
                    if fecha_pago is not None:
                        rec.CULPA = fecha_pago
                    if create or not rec.CFECHA:
                        rec.CFECHA = fecha_reg
                    if dias_tope not in (None, ""):
                        rec.CDIASTOPE = int(dias_tope)
                written.append({"path": path, "action": "update"})
        except Exception as e:
            errors.append(f"{path}: {e}")
        finally:
            if table is not None:
                try:
                    table.close()
                except Exception:
                    pass

    if not written:
        raise OSError("No se pudo grabar CLIGESCO.DBF (" + "; ".join(errors) + ")")
    return {"codigo": codigo, "written": written, "errors": errors}


def set_activo(codigo: str, activo: bool) -> dict:
    codigo = _clip(codigo, 4).upper()
    if codigo.isdigit():
        codigo = codigo.zfill(4)[:4]
    if not codigo:
        raise ValueError("Sin código para actualizar CACTI en CLIGESCO.DBF.")
    written, errors = [], []
    for path in cligesco_paths():
        table = None
        try:
            table = _open_table(path)
            for rec in table:
                if dbf.is_deleted(rec):
                    continue
                if str(rec.CCOD or "").strip().upper() == codigo:
                    with rec:
                        rec.CACTI = bool(activo)
                    written.append(path)
                    break
        except Exception as e:
            errors.append(f"{path}: {e}")
        finally:
            if table is not None:
                try:
                    table.close()
                except Exception:
                    pass
    if not written:
        raise OSError("No se pudo actualizar CACTI en CLIGESCO.DBF (" + "; ".join(errors) + ")")
    return {"codigo": codigo, "activo": bool(activo), "written": written, "errors": errors}


def code_exists(codigo: str) -> bool:
    code = (codigo or "").strip().upper()
    if code.isdigit():
        code = code.zfill(4)[:4]
    return code in list_codes()
