import os

main_path = r'p:\ApolloSupport\backend\main.py'
backup_path = r'p:\ApolloSupport\backend\backup_routes.py'

with open(main_path, 'r', encoding='utf-8') as f:
    main_content = f.read()

# Eliminar el include_router si estǭ
target = 'import backup_routes\napp.include_router(backup_routes.router, prefix="/api")'
if target in main_content:
    main_content = main_content.replace(target, '')
target2 = 'app.include_router(backup_routes.router, prefix="/api")'
if target2 in main_content:
    main_content = main_content.replace(target2, '')

# Aadir imports necesarios a main.py si no estǭn
new_imports = """
import subprocess
import tempfile
import time
from cryptography.fernet import Fernet
"""

# Aadir el cdigo de backup al final
backup_code = """
# ==========================================
# RUTAS DE BACKUP Y RESTORE ENCRIPTADO
# ==========================================
BACKUP_ENCRYPTION_KEY = b'G1yB-o_x3t1U7pM7M3o1I9_z1Y0XqPzG1yB-o_x3t1U='
cipher_suite = Fernet(BACKUP_ENCRYPTION_KEY)

def get_pg_dump_path():
    possible_paths = [
        "pg_dump", 
        r"C:\\Program Files\\PostgreSQL\\15\\bin\\pg_dump.exe",
        r"C:\\Program Files\\PostgreSQL\\14\\bin\\pg_dump.exe",
        r"C:\\Program Files\\PostgreSQL\\13\\bin\\pg_dump.exe",
        r"C:\\Program Files\\PostgreSQL\\12\\bin\\pg_dump.exe",
    ]
    for path in possible_paths:
        if path == "pg_dump":
            try:
                subprocess.run(["pg_dump", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return "pg_dump"
            except:
                continue
        if os.path.exists(path):
            return path
    raise FileNotFoundError("No se encontr pg_dump en el servidor.")

def get_psql_path():
    possible_paths = [
        "psql", 
        r"C:\\Program Files\\PostgreSQL\\15\\bin\\psql.exe",
        r"C:\\Program Files\\PostgreSQL\\14\\bin\\psql.exe",
        r"C:\\Program Files\\PostgreSQL\\13\\bin\\psql.exe",
        r"C:\\Program Files\\PostgreSQL\\12\\bin\\psql.exe",
    ]
    for path in possible_paths:
        if path == "psql":
            try:
                subprocess.run(["psql", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return "psql"
            except:
                continue
        if os.path.exists(path):
            return path
    raise FileNotFoundError("No se encontr psql en el servidor.")

@app.get("/api/backup")
def backup_database(current_user: models.User = Depends(get_current_user)):
    from database import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
    if current_user.rol != 'admin':
        raise HTTPException(status_code=403, detail="Solo administradores pueden hacer backups.")
    
    try:
        pg_dump = get_pg_dump_path()
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PASSWORD
        
        fd_raw, raw_path = tempfile.mkstemp(suffix=".sql")
        os.close(fd_raw)
        
        fd_enc, enc_path = tempfile.mkstemp(suffix=".apbk")
        os.close(fd_enc)
        
        cmd = [
            pg_dump,
            "-h", DB_HOST,
            "-p", str(DB_PORT),
            "-U", DB_USER,
            "-d", DB_NAME,
            "--clean",
            "--if-exists",
            "-F", "p", 
            "-f", raw_path
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"pg_dump fall: {result.stderr}")
            
        with open(raw_path, "rb") as f_in:
            raw_data = f_in.read()
            
        encrypted_data = cipher_suite.encrypt(raw_data)
        
        with open(enc_path, "wb") as f_out:
            f_out.write(encrypted_data)
            
        os.remove(raw_path)
        
        filename = f"ApolloBackup_{time.strftime('%Y%m%d_%H%M%S')}.apbk"
        return FileResponse(enc_path, filename=filename, media_type="application/octet-stream")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/restore")
async def restore_database(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)):
    from database import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
    if current_user.rol != 'admin':
        raise HTTPException(status_code=403, detail="Solo administradores pueden restaurar backups.")
    
    if not file.filename.endswith(".apbk"):
        raise HTTPException(status_code=400, detail="Formato de archivo invǭlido. Debe ser un backup de Apollo (.apbk).")
        
    try:
        psql = get_psql_path()
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PASSWORD
        
        encrypted_data = await file.read()
        
        try:
            raw_data = cipher_suite.decrypt(encrypted_data)
        except Exception:
            raise HTTPException(status_code=400, detail="El archivo estǭ corrupto o la clave no coincide.")
        
        fd_raw, raw_path = tempfile.mkstemp(suffix=".sql")
        os.close(fd_raw)
        
        with open(raw_path, "wb") as f_out:
            f_out.write(raw_data)
            
        cmd = [
            psql,
            "-h", DB_HOST,
            "-p", str(DB_PORT),
            "-U", DB_USER,
            "-d", DB_NAME,
            "-f", raw_path
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        os.remove(raw_path)
        
        if result.returncode != 0:
            raise Exception(f"La restauracin fall (psql error): {result.stderr}")
            
        return {"status": "ok", "message": "Base de datos restaurada con Ǹxito."}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""

if 'import subprocess' not in main_content:
    main_content = main_content.replace('import asyncio', 'import asyncio\n' + new_imports)

if '@app.get("/api/backup")' not in main_content:
    main_content += "\n\n" + backup_code

with open(main_path, 'w', encoding='utf-8') as f:
    f.write(main_content)

print("Main patched successfully")
