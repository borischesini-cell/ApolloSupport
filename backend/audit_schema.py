import psycopg
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "INGENIERIA")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "apollosupport_db")

conn_str = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"

expected_columns = [
    "id", "nombre", "email", "hashed_password", "full_name", 
    "rol", "activo", "expo_push_token"
]

try:
    with psycopg.connect(conn_str, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users';")
            existing_columns = [r[0] for r in cur.fetchall()]
            
            print(f"Existing columns: {existing_columns}")
            
            missing = [c for c in expected_columns if c not in existing_columns]
            if missing:
                print(f"Missing columns: {missing}")
                for col in missing:
                    print(f"Adding column {col}...")
                    cur.execute(f"ALTER TABLE users ADD COLUMN {col} VARCHAR;")
                print("All missing columns added.")
            else:
                print("No missing columns found.")
except Exception as e:
    print(f"Error: {e}")
