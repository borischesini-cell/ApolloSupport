import sys
import re

with open('agent/centinela.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'update_status_threadsafe(lbl_status' in line and 'Listo para Recibir Soporte' in line:
        lines[i] = '                update_status_threadsafe(lbl_status, "Estado: Listo para Recibir Soporte", "#10b981") # Esmeralda / Verde\n'

with open('agent/centinela.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
