"""
Proxy a Django API Ultimate — ApolloIA billing (get-billing-month).
Env:
  IA_API_URL   ej. https://api.ultimate.net.ar/  (con o sin slash final)
  IA_API_KEY   ApiKey del Master (opcional si el endpoint no exige auth)
  IA_SERIAL_GESCOM  SerialGesCom header (opcional)
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

import models

logger = logging.getLogger("apollo.ia_billing")


def _ia_base_url() -> str:
    url = (os.getenv("IA_API_URL") or os.getenv("ULTIMATE_IA_URL") or "").strip()
    if not url:
        # fallback historico de la API Ultimate
        url = "https://api.ultimate.net.ar/"
    if not url.endswith("/"):
        url += "/"
    return url


def _ia_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = (os.getenv("IA_API_KEY") or os.getenv("ULTIMATE_API_KEY") or "").strip()
    serial = (os.getenv("IA_SERIAL_GESCOM") or os.getenv("ULTIMATE_SERIAL") or "").strip()
    if key:
        headers["ApiKey"] = key
    if serial:
        headers["SerialGesCom"] = serial
    return headers


def fetch_billing_month(
    desde: str,
    hasta: str,
    serial: Optional[str] = None,
    timeout: float = 45.0,
) -> Dict[str, Any]:
    url = _ia_base_url() + "IA/v1/get-billing-month"
    body: Dict[str, Any] = {
        "Action": "GetBillingMonth",
        "Desde": desde,
        "Hasta": hasta,
    }
    if serial:
        body["Serial"] = serial.strip()

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=body, headers=_ia_headers())
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.exception("IA billing fetch failed: %s", exc)
        return {"result": "error", "message": str(exc)}

    if not isinstance(data, dict):
        return {"result": "error", "message": "Respuesta IA invalida"}
    return data


def enrich_with_clients(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Agrega codigo GesCom / cclifac / razon desde Centinela clients."""
    if payload.get("result") != "ok":
        return payload

    rows: List[Dict[str, Any]] = list(payload.get("resultado") or [])
    if not rows:
        return payload

    clients = db.query(models.Client).all()
    by_cod = {(c.codigo or "").strip().upper(): c for c in clients if c.codigo}
    by_fac = {(c.cclifac or "").strip().upper(): c for c in clients if c.cclifac}

    enriched = []
    for r in rows:
        user = (r.get("gescom_user") or (r.get("gescom_serial") or "")[:4] or "").strip().upper()
        cli = by_cod.get(user)
        if cli is None:
            # intentar match por left(serial,4)
            ser = (r.get("gescom_serial") or "").strip().upper()
            cli = by_cod.get(ser[:4]) if ser else None
        item = dict(r)
        if cli is not None:
            item["centinela"] = {
                "client_id": cli.id,
                "codigo": cli.codigo,
                "cclifac": cli.cclifac,
                "razon_social": cli.razon_social,
                "nombre_fantasia": cli.nombre_fantasia,
                "activo": cli.activo,
            }
        else:
            item["centinela"] = None
            # hint: si cclifac coincide con algo raro
            fac_guess = by_fac.get(user)
            if fac_guess is not None:
                item["centinela"] = {
                    "client_id": fac_guess.id,
                    "codigo": fac_guess.codigo,
                    "cclifac": fac_guess.cclifac,
                    "razon_social": fac_guess.razon_social,
                    "nombre_fantasia": fac_guess.nombre_fantasia,
                    "activo": fac_guess.activo,
                    "matched_by": "cclifac",
                }
        enriched.append(item)

    payload = dict(payload)
    payload["resultado"] = enriched
    payload["ia_api_url"] = _ia_base_url()
    return payload


def default_month_range() -> tuple[str, str]:
    today = date.today()
    desde = today.replace(day=1).isoformat()
    hasta = today.isoformat()
    return desde, hasta
