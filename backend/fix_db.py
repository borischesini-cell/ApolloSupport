from database import engine
from sqlalchemy import text

def fix_db():
    queries = [
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS fecha_vencimiento TIMESTAMP;",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS modulos VARCHAR DEFAULT 'Base, Facturación';",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS apikey_apollo VARCHAR UNIQUE;",
        "CREATE INDEX IF NOT EXISTS ix_clients_apikey_apollo ON clients (apikey_apollo);"
    ]
    
    with engine.connect() as conn:
        for query in queries:
            try:
                print(f"Ejecutando: {query}")
                conn.execute(text(query))
                conn.commit()
            except Exception as e:
                print(f"Error en {query}: {e}")
        print("Base de Datos Estabilizada.")

if __name__ == '__main__':
    fix_db()
