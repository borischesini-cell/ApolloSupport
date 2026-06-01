import re
with open('p:/ApolloSupport/agent/centinela.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix labels
content = re.sub(r'text="M.*?dulo de Asistencia Activa"', 'text="Módulo de Asistencia Activa"', content)
content = re.sub(r'text="Dicte este ID al t.*?cnico:"', 'text="Dicte este ID al técnico:"', content)
content = re.sub(r'text="Soporte Apollo GesCom"', 'text="Soporte Apollo GesCom"', content)
content = re.sub(r'bot.*?n de cerrar \(X\) para que se minimice al tray', 'botón de cerrar (X) para que se minimice al tray', content)
content = re.sub(r'minimizaci.*?n est.*?ndar de Windows', 'minimización estándar de Windows', content)
content = re.sub(r'Chat con T.*?cnico', 'Chat con Técnico', content)
content = re.sub(r'T.*?cnicos Conectados', 'Técnicos Conectados', content)
content = re.sub(r'f\'\\s+.*?\\s+\{tech\}\'', 'f\'  ✅  {tech}\'', content)
content = re.sub(r'T.*?cnicos:', 'Técnicos:', content)
content = re.sub(r'men.*? de tray', 'menú de tray', content)
content = re.sub(r'Bordes est.*?ndar', 'Bordes estándar', content)
content = re.sub(r'M.*?s alto para incluir', 'Más alto para incluir', content)
content = re.sub(r'est.*?tica premium', 'estética premium', content)
content = re.sub(r't.*?tulo y bot.*?n de desconexi.*?n r.*?pida', 'título y botón de desconexión rápida', content)
content = re.sub(r'text=".*? Desconectar"', 'text="❌ Desconectar"', content)
content = re.sub(r'desconexi.*?n al servidor', 'desconexión al servidor', content)
content = re.sub(r'sesi.*?n del t.*?cnico', 'sesión del técnico', content)
content = re.sub(r'text=f".*? T.*?cnico conectado: \{name\}"', 'text=f"👨‍💻 Técnico conectado: {name}"', content)

with open('p:/ApolloSupport/agent/centinela.py', 'w', encoding='utf-8') as f:
    f.write(content)
