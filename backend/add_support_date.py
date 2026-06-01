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

print(f"Connecting to {DB_NAME}...")

try:
    with psycopg.connect(conn_str, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Check if column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='centinela_devices' AND column_name='last_support_date';
            """)
            if not cur.fetchone():
                print("Adding 'last_support_date' column to 'centinela_devices' table...")
                cur.execute("ALTER TABLE centinela_devices ADD COLUMN last_support_date TIMESTAMP;")
                print("Column added successfully.")
            else:
                print("Column 'last_support_date' already exists.")
except Exception as e:
    print(f"Error: {e}")
