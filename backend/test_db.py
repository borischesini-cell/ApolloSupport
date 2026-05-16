from database import engine
try:
    conn = engine.connect()
    print('CONEXION EXITOSA')
    conn.close()
except Exception as e:
    print('ERROR DE CONEXION:', e)
