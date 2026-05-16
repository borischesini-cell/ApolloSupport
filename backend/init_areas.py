import psycopg
import os
from dotenv import load_dotenv
from database import engine, Base
import models

load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "INGENIERIA")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "apollosupport_db")

conn_str = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"

def run_migration():
    print("Creating new tables...")
    models.Base.metadata.create_all(bind=engine)
    
    try:
        with psycopg.connect(conn_str, autocommit=True) as conn:
            with conn.cursor() as cur:
                # 1. Add current_area_id to tickets if missing
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='tickets' AND column_name='current_area_id';")
                if not cur.fetchone():
                    print("Adding current_area_id to tickets...")
                    cur.execute("ALTER TABLE tickets ADD COLUMN current_area_id INTEGER REFERENCES areas(id);")

                # 2. Populate Areas
                areas = [
                    ("Atención al Cliente", "Soporte primario y contacto con el usuario."),
                    ("Desarrollo", "Programación, corrección de bugs y nuevas features."),
                    ("Finanzas", "Cobros, facturación y validación de pagos.")
                ]
                for nombre, desc in areas:
                    cur.execute("SELECT id FROM areas WHERE nombre = %s", (nombre,))
                    if not cur.fetchone():
                        print(f"Creating area: {nombre}")
                        cur.execute("INSERT INTO areas (nombre, descripcion) VALUES (%s, %s)", (nombre, desc))

                # 3. Assign existing users to areas based on rol
                print("Syncing users with areas...")
                cur.execute("SELECT id, rol FROM users")
                users = cur.fetchall()
                for uid, rol in users:
                    area_name = "Atención al Cliente"
                    if rol == "desarrollo": area_name = "Desarrollo"
                    
                    cur.execute("SELECT id FROM areas WHERE nombre = %s", (area_name,))
                    area_id = cur.fetchone()[0]
                    
                    cur.execute("SELECT * FROM user_areas WHERE user_id = %s AND area_id = %s", (uid, area_id))
                    if not cur.fetchone():
                        cur.execute("INSERT INTO user_areas (user_id, area_id) VALUES (%s, %s)", (uid, area_id))

                # 4. Update existing tickets to Support area
                cur.execute("SELECT id FROM areas WHERE nombre = 'Atención al Cliente'")
                support_area_id = cur.fetchone()[0]
                cur.execute("UPDATE tickets SET current_area_id = %s WHERE current_area_id IS NULL", (support_area_id,))
                
                print("Migration completed successfully.")
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    run_migration()
