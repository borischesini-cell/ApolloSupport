import re
with open('p:/ApolloSupport/agent/centinela_svc.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'c.*?digo', 'código', content)
content = re.sub(r'm.*?gico', 'mágico', content)
content = re.sub(r'caf.*?\.', 'café.', content)
content = re.sub(r'pr.*?ximas', 'próximas', content)
content = re.sub(r'pa.*?s', 'país', content)
content = re.sub(r'habr.*?n', 'habrán', content)
content = re.sub(r'versi.*?n', 'versión', content)
content = re.sub(r'actualizaci.*?n', 'actualización', content)
content = re.sub(r'sesi.*?n', 'sesión', content)
content = re.sub(r'conexi.*?n', 'conexión', content)
content = re.sub(r'romp.*?a', 'rompía', content)
content = re.sub(r'comprobaci.*?n', 'comprobación', content)
content = re.sub(r'instalaci.*?n', 'instalación', content)
content = re.sub(r'reiniciar.*? ', 'reiniciará ', content)

# Remove the completely corrupted header lines if any
content = re.sub(r'# ǟ.*?mo lo usar.*?\n', '# ¿Cómo lo usarías a partir de mañana?\n', content)

with open('p:/ApolloSupport/agent/centinela_svc.py', 'w', encoding='utf-8') as f:
    f.write(content)
