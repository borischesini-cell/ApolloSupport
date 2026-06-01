from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    res = db.execute(text("SELECT client_addr, application_name, query, state FROM pg_stat_activity WHERE datname='apollosupport_db'")).fetchall()
    for r in res:
        print(f"IP: {r[0]} | App: {r[1]} | State: {r[3]} | Query: {r[2][:100]}")
finally:
    db.close()
