# Este script consulta logs recientes de conexión en la DB o archivos
import os
import glob

print("Verificando archivos de logs recientes en C:\\ApolloSupport\\backend\\logs\\:")
logs_path = "C:\\ApolloSupport\\backend\\logs\\*"
for filepath in glob.glob(logs_path):
    size = os.path.getsize(filepath)
    print(f"- {os.path.basename(filepath)} ({size} bytes)")
    # Leer las últimas 15 líneas
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            print("  Últimas 15 líneas:")
            for line in lines[-15:]:
                print(f"    {line.strip()}")
    except Exception as e:
        print(f"  Error leyendo: {e}")
