import psutil
import os
import signal

print("Iniciando matanza de procesos stale de Python y Uvicorn...")
my_pid = os.getpid()

for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        pid = proc.info['pid']
        if pid == my_pid:
            continue
        cmd = proc.info['cmdline']
        if cmd:
            cmd_str = " ".join(cmd).lower()
            if 'main:app' in cmd_str or 'uvicorn' in cmd_str or 'diagnostico.py' in cmd_str:
                print(f"Matando proceso PID {pid}: {proc.info['name']} | Cmd: {cmd}")
                try:
                    p = psutil.Process(pid)
                    p.terminate() # Terminar elegantemente
                    p.wait(timeout=1.0)
                except (psutil.TimeoutExpired, Exception):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except Exception:
                        pass
                    print(f"  [FORZADO] Proceso PID {pid} terminado de forma forzada.")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

print("\n[OK] Todos los procesos stale han sido depurados.")
