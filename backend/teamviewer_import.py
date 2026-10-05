"""
Importa el CSV de computadoras de TeamViewer a centinela_devices.

No crea clientes nuevos: el grupo/empresa tiene que coincidir con un cliente
ya cargado (razón social, nombre de fantasía o código). Reimportar el mismo
ID de TeamViewer actualiza notas y no duplica la PC.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

import models

_ALIAS_COLS = {
    "alias", "computer", "computername", "computer name", "device", "devicename",
    "device name", "nombre", "nombreequipo", "nombre del equipo", "equipo", "pc",
    "hostname", "name",
}
_ID_COLS = {
    "teamviewerid", "teamviewer id", "tvid", "tv id", "id", "id de teamviewer",
    "teamviewer-id",
}
_CLIENT_COLS = {
    "group", "grupo", "cliente", "company", "empresa", "razonsocial", "razon social",
    "razón social", "partner", "cliente facturacion", "cliente de facturacion",
}
_NOTES_COLS = {
    "description", "descripcion", "descripción", "notes", "notas", "comment",
    "comentario", "comments",
}
_CODE_COLS = {"codigo", "código", "ccod", "codigocliente", "código cliente"}


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _header_key(value: str) -> str:
    return _fold(value).replace("_", " ")


def _tv_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _tv_display(digits: str) -> str:
    if len(digits) == 9:
        return f"{digits[0:3]} {digits[3:6]} {digits[6:9]}"
    if len(digits) == 10:
        return f"{digits[0:3]} {digits[3:6]} {digits[6:10]}"
    return digits


def _decode_csv(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _read_rows(text: str) -> list[dict[str, str]]:
    sample = text[:4096]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("El CSV no tiene encabezados.")
    rows = []
    for raw in reader:
        item = {}
        for key, val in raw.items():
            if key is None:
                continue
            item[_header_key(key)] = (val or "").strip()
        if any(item.values()):
            rows.append(item)
    return rows


def _pick(row: dict[str, str], names: set[str]) -> str:
    for name in names:
        key = _header_key(name)
        if row.get(key):
            return row[key]
    return ""


def _client_index(db: Session) -> dict[str, models.Client]:
    index: dict[str, models.Client] = {}
    for cli in db.query(models.Client).all():
        for raw in (cli.codigo, cli.razon_social, cli.nombre_fantasia, cli.cclifac):
            folded = _fold(raw or "")
            if folded and folded not in index:
                index[folded] = cli
    return index


def _match_client(index: dict[str, models.Client], group: str, codigo: str) -> models.Client | None:
    for raw in (codigo, group):
        folded = _fold(raw)
        if folded and folded in index:
            return index[folded]
    folded = _fold(group)
    if not folded:
        return None
    for sep in (" - ", " / ", " | "):
        if sep in group:
            for part in group.split(sep):
                hit = index.get(_fold(part))
                if hit:
                    return hit
    return None


def _merge_notes(existing: str | None, description: str, tv_digits: str) -> str:
    header = f"[TeamViewer ID: {_tv_display(tv_digits)}]"
    base = (existing or "").strip()
    if header not in base:
        base = f"{header}\n{base}".strip()
    desc = (description or "").strip()
    if desc and desc not in base:
        base = f"{base}\n{desc}".strip()
    return base


def _find_device(db: Session, client_id: int, alias: str, tv_digits: str) -> models.CentinelaDevice | None:
    display = _tv_display(tv_digits)
    candidates = (
        db.query(models.CentinelaDevice)
        .filter(models.CentinelaDevice.client_id == client_id)
        .all()
    )
    for dev in candidates:
        alt = _tv_digits(dev.alt_remote_id or "")
        notes = dev.notes or ""
        if alt == tv_digits or display in notes or tv_digits in notes:
            return dev
    folded_alias = _fold(alias)
    for dev in candidates:
        if _fold(dev.device_name or "") != folded_alias:
            continue
        alt = _tv_digits(dev.alt_remote_id or "")
        if alt and alt != tv_digits:
            continue
        notes = dev.notes or ""
        if "[TeamViewer ID:" in notes and _tv_display(tv_digits) not in notes and tv_digits not in notes:
            continue
        return dev
    return None


def import_teamviewer_csv(db: Session, raw: bytes, dry_run: bool = False) -> dict[str, Any]:
    text = _decode_csv(raw)
    rows = _read_rows(text)
    if not rows:
        raise ValueError("El CSV no tiene filas.")

    index = _client_index(db)
    created = 0
    updated = 0
    skipped = 0
    unmatched: list[dict[str, str]] = []
    seen_tv: set[tuple[int, str]] = set()

    for i, row in enumerate(rows, start=2):
        alias = _pick(row, _ALIAS_COLS)
        tv_raw = _pick(row, _ID_COLS)
        group = _pick(row, _CLIENT_COLS)
        notes = _pick(row, _NOTES_COLS)
        codigo = _pick(row, _CODE_COLS)
        tv_digits = _tv_digits(tv_raw)

        if not alias and not tv_digits:
            skipped += 1
            continue
        if not alias:
            alias = f"TV {_tv_display(tv_digits)}"
        if len(tv_digits) < 6:
            unmatched.append({
                "fila": str(i),
                "equipo": alias,
                "grupo": group,
                "motivo": "Sin ID de TeamViewer",
            })
            continue

        client = _match_client(index, group, codigo)
        if not client:
            unmatched.append({
                "fila": str(i),
                "equipo": alias,
                "grupo": group or codigo,
                "motivo": "No coincide con un cliente de Support",
            })
            continue

        key = (client.id, tv_digits)
        if key in seen_tv:
            skipped += 1
            continue
        seen_tv.add(key)

        device = _find_device(db, client.id, alias, tv_digits)
        merged = _merge_notes(device.notes if device else "", notes, tv_digits)
        if device:
            device.notes = merged
            if not _tv_digits(device.alt_remote_id or ""):
                device.alt_remote_id = tv_digits
            if not (device.device_name or "").strip():
                device.device_name = alias[:120]
            updated += 1
        else:
            db.add(models.CentinelaDevice(
                client_id=client.id,
                device_name=alias[:120],
                alt_remote_id=tv_digits,
                notes=merged,
                is_online=False,
            ))
            created += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return {
        "status": "ok",
        "dry_run": dry_run,
        "filas": len(rows),
        "creadas": created,
        "actualizadas": updated,
        "omitidas": skipped,
        "sin_cliente": len(unmatched),
        "sin_cliente_detalle": unmatched[:80],
    }
