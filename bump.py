import os
import re
import json

NEW_VERSION = "3.2.6"  # <--- CAMBIAR ESTE NUMERO PARA ACTUALIZAR TODO EL PROYECTO

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
        'path': 'p:/ApolloSupport/backend/main.py',
        'pattern': r'(BACKEND_VERSION\s*=\s*")\d+\.\d+\.\d+(")',
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
    path = item['path']
    if not os.path.exists(path):
        print(f"SKIP missing {path}")
        continue
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    new_text, n = re.subn(item['pattern'], item['replacement'], text)
    if n:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_text)
        print(f"OK {path} ({n})")
    else:
        print(f"NO MATCH {path}")
