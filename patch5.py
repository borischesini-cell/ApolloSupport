import sqlite3
import os

DB_PATH = "p:/ApolloSupport/backend/apollo.db"

def add_column():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(centinela_devices)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "last_support_date" not in columns:
        print("Adding last_support_date column...")
        cursor.execute("ALTER TABLE centinela_devices ADD COLUMN last_support_date DATETIME")
        conn.commit()
        print("Column added successfully.")
    else:
        print("Column already exists.")
        
    conn.close()

if __name__ == "__main__":
    add_column()
