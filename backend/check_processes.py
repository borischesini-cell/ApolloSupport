import psutil
import os

print("Buscando procesos de Python y Uvicorn en ejecucion:")
for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
    try:
        cmd = proc.info['cmdline']
        if cmd and any('uvicorn' in str(c).lower() or 'python' in str(c).lower() for c in cmd):
            print(f"\nPID: {proc.info['pid']} | Name: {proc.info['name']}")
            print(f"  CWD: {proc.info['cwd']}")
            print(f"  Cmdline: {cmd}")
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
