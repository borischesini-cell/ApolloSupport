import PyInstaller.__main__
import os
import shutil

# Configuración de Rutas
base_dir = os.path.dirname(os.path.abspath(__file__))
script_path = os.path.join(base_dir, "centinela.py")
output_dir = os.path.join(base_dir, "dist")

print(f"[*] Iniciando compilación de ApolloSupport Centinela...")

# Limpiar compilación anterior de ApolloCentinela
exe_target = os.path.join(output_dir, "ApolloCentinela.exe")
if os.path.exists(exe_target):
    try:
        os.remove(exe_target)
    except Exception as e:
        print(f"[!] Advertencia al eliminar {exe_target}: {e}")

PyInstaller.__main__.run([
    script_path,
    '--onefile',            # Un solo .exe
    '--noconsole',          # Sin ventana de consola (modo servicio/tray)
    '--name=ApolloCentinela',
    '--clean',
    f'--icon={os.path.join(base_dir, "apollo_logo.ico")}',  # Icono del archivo .exe
    f'--add-data={os.path.join(base_dir, "apollo_logo.ico")};.',  # Incluir icono dentro del exe
    f'--add-data={os.path.join(base_dir, "apollo_logo.png")};.',  # Incluir imagen PNG dentro del exe
    f'--add-data={os.path.join(base_dir, "ffmpeg.exe")};.',     # Incluir motor de video FFmpeg
])

print(f"[+] Compilación completada con éxito. El ejecutable se encuentra en: {output_dir}")
