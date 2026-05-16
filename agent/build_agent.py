import PyInstaller.__main__
import os
import shutil

# Configuración de Rutas
base_dir = os.path.dirname(os.path.abspath(__file__))
script_path = os.path.join(base_dir, "centinela.py")
output_dir = os.path.join(base_dir, "dist")

print(f"[*] Iniciando compilación de ApolloSupport Centinela...")

# Limpiar compilaciones anteriores
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)

PyInstaller.__main__.run([
    script_path,
    '--onefile',            # Un solo .exe
    '--noconsole',          # Sin ventana de consola (modo servicio/tray)
    '--name=ApolloCentinela',
    '--clean',
    f'--icon={os.path.join(base_dir, "apollo_logo.ico")}',  # Icono del archivo .exe
    f'--add-data={os.path.join(base_dir, "apollo_logo.ico")};.',  # Incluir icono dentro del exe
    f'--add-data={os.path.join(base_dir, "apollo_logo.png")};.',  # Incluir imagen PNG dentro del exe
])

print(f"[+] Compilación completada con éxito. El ejecutable se encuentra en: {output_dir}")
