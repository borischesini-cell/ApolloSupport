import psycopg
conn = psycopg.connect('dbname=postgres user=postgres password=INGENIERIA', autocommit=True)
try:
    conn.execute('CREATE DATABASE apollosupport_db')
    print('BASE DE DATOS CREADA')
except Exception as e:
    print(e)
conn.close()
