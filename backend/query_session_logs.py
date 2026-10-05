#!/usr/bin/env python3
"""Consulta la bitácora (remote_logs) filtrando cambios de sesión.

Uso en el servidor (con venv del backend):
  python query_session_logs.py 775
  python query_session_logs.py 775 --limit 150
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import or_

from database import SessionLocal
import models

SESSION_PATTERNS = [
    "%SESSION-SWITCH%",
    "%WS-SWITCH%",
    "%AUTOPROMOTE%",
    "%[SESSION]%",
    "%[SWITCH]%",
    "%login_session%",
    "%session_switched%",
]


def main():
    parser = argparse.ArgumentParser(description="Bitácora: logs de cambio de sesión")
    parser.add_argument("device_id", type=int, help="ID del dispositivo (ej. 775)")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        cond = or_(*[models.RemoteLog.message.ilike(p) for p in SESSION_PATTERNS])
        logs = (
            db.query(models.RemoteLog)
            .filter(models.RemoteLog.device_id == args.device_id)
            .filter(cond)
            .order_by(models.RemoteLog.id.desc())
            .limit(args.limit)
            .all()
        )
        dev = (
            db.query(models.CentinelaDevice)
            .filter(models.CentinelaDevice.id == args.device_id)
            .first()
        )
        name = dev.device_name if dev else "?"
        print(f"=== Bitácora sesión | device {args.device_id} ({name}) | {len(logs)} entradas ===\n")
        if not logs:
            print("(sin coincidencias — probá sin filtro: read_logs.py o últimos logs del device)")
            recent = (
                db.query(models.RemoteLog)
                .filter(models.RemoteLog.device_id == args.device_id)
                .order_by(models.RemoteLog.id.desc())
                .limit(25)
                .all()
            )
            for l in reversed(recent):
                print(f"[{l.timestamp}] {l.source} [{l.level}]: {l.message[:500]}")
            return
        for l in reversed(logs):
            print(f"[{l.timestamp}] {l.source} [{l.level}]")
            print(f"  {l.message}\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
