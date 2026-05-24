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
                WHERE table_name='users' AND column_name='full_name';
            """)
            if not cur.fetchone():
                print("Adding 'full_name' column to 'users' table...")
                cur.execute("ALTER TABLE users ADD COLUMN full_name VARCHAR DEFAULT 'Técnico Apollo';")
                print("Column added successfully.")
            else:
                print("Column 'full_name' already exists.")

            # Check if notes column exists in centinela_devices
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='centinela_devices' AND column_name='notes';
            """)
            if not cur.fetchone():
                print("Adding 'notes' column to 'centinela_devices' table...")
                cur.execute("ALTER TABLE centinela_devices ADD COLUMN notes TEXT;")
                print("Column added successfully.")
            else:
                print("Column 'notes' already exists.")

            # Check if alt_remote_id column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='centinela_devices' AND column_name='alt_remote_id';
            """)
            if not cur.fetchone():
                print("Adding 'alt_remote_id' column to 'centinela_devices' table...")
                cur.execute("ALTER TABLE centinela_devices ADD COLUMN alt_remote_id VARCHAR;")
                print("Column added successfully.")
            else:
                print("Column 'alt_remote_id' already exists.")

            # Nuevas columnas de control de personal y perfil para la tabla 'users'
            cols_to_add_users = [
                ("celular", "VARCHAR"),
                ("departamento", "VARCHAR"),
                ("profile_picture", "TEXT"),
                ("is_online", "BOOLEAN DEFAULT FALSE"),
                ("current_task", "VARCHAR"),
                ("current_page", "VARCHAR"),
                ("last_activity", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("last_login", "TIMESTAMP")
            ]
            for col, col_type in cols_to_add_users:
                cur.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='{col}';
                """)
                if not cur.fetchone():
                    print(f"Adding '{col}' column to 'users' table...")
                    cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type};")
                    print("Column added successfully.")
                else:
                    print(f"Column '{col}' already exists in 'users'.")
except Exception as e:
    print(f"Error: {e}")
