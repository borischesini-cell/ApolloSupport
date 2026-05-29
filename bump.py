import os
import re
import json

NEW_VERSION = "3.1.23"  # <--- CAMBIAR ESTE NUMERO PARA ACTUALIZAR TODO EL PROYECTO

files_to_update = [
    {
        'path': 'p:/ApolloSupport/agent/centinela.py',
        'pattern': r'(CLIENT_VERSION\s*=\s*")\d+\.\d+\.\d+(")',
        'replacement': fr'\g<1>{NEW_VERSION}\g<2>'
    },
    {
        'path': 'p:/ApolloSupport/agent/centinela_svc.py',
        'pattern': r'(__version__\s*=\s*")\d+\.\d+\.\d+(")',
        'replacement': fr'\g<1>{NEW_VERSION}\g<2>'
    },
    {
        'path': 'p:/ApolloSupport/agent/installer/ApolloSetup.iss',
        'pattern': r'(#define MyAppVersion\s+")\d+\.\d+\.\d+(")',
        'replacement': fr'\g<1>{NEW_VERSION}\g<2>'
    },
    {
        'path': 'p:/ApolloSupport/agent/installer/ApolloSetup_x64.iss',
        'pattern': r'(#define MyAppVersion\s+")\d+\.\d+\.\d+(")',
        'replacement': fr'\g<1>{NEW_VERSION}\g<2>'
    },
    {
        'path': 'p:/ApolloSupport/agent/installer/ApolloSetup_x86.iss',
        'pattern': r'(#define MyAppVersion\s+")\d+\.\d+\.\d+(")',
        'replacement': fr'\g<1>{NEW_VERSION}\g<2>'
    }
]

for item in files_to_update:
    file_path = item['path']
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='cp1252') as f:
            content = f.read()
            
    new_content = re.sub(item['pattern'], item['replacement'], content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

# Update version.json
version_json_path = 'p:/ApolloSupport/backend/updates/version.json'
with open(version_json_path, 'w', encoding='utf-8') as f:
    f.write('{\n    "version": "' + NEW_VERSION + '",\n    "url": "https://support.ultimate.net.ar/api/centinela/download_update"\n}\n')

print(f"===========================================================")
print(f" PROYECTO COMPLETO ACTUALIZADO CORRECTAMENTE A LA V{NEW_VERSION}")
print(f"===========================================================")



