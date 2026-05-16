import os
import sys

# Agregar la ruta actual al sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    result = db.execute(text("SELECT pid, usename, client_addr, client_port, backend_start, state, query FROM pg_stat_activity WHERE datname = 'apollosupport_db'"))
    print("Conexiones activas en PostgreSQL:")
    for row in result:
        print(f"PID: {row[0]} | User: {row[1]} | Client IP: {row[2]} | Client Port: {row[3]} | State: {row[5]}")
        print(f"  Query: {row[6][:120]}")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
