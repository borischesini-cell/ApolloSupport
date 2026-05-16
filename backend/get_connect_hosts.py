import pymysql

try:
    conn = pymysql.connect(
        host="SRV-I9-2016",
        port=3316,
        user="root",
        password="ingenieria",
        database="agc_sql_connect",
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()
    cursor.execute("DESCRIBE principa_users;")
    columns = cursor.fetchall()
    print("Columnas de principa_users:")
    for col in columns:
        print(f"  - {col['Field']}: {col['Type']}")
        
    print("\nRegistros de principa_users:")
    cursor.execute("SELECT * FROM principa_users;")
    records = cursor.fetchall()
    for r in records:
        print(r)
        
    conn.close()
except Exception as e:
    print("Error:", e)
