# Apollo Centinela — Guía del Instalador

## Para el Técnico (cómo generar el instalador)

### Requisitos previos (una sola vez)
1. **Inno Setup 6** → Descargar gratis: https://jrsoftware.org/isinfo.php
2. **PyInstaller** ya instalado en el venv del backend

### Generar el instalador
```
Doble click en:  p:\ApolloSupport\agent\build_installer.bat
```
El script hace automáticamente:
1. Compila `centinela.py` → `dist\ApolloCentinela.exe` (PyInstaller)
2. Empaqueta el EXE en `installer_output\ApolloSetup_v2.0.0.exe` (Inno Setup)

**Tiempo estimado:** 2-4 minutos

---

## Para el Cliente (cómo instalar)

### Instalación automática (recomendado)
1. Descargar `ApolloSetup_v2.0.0.exe`
2. Doble click → Siguiente → Siguiente → Instalar
3. ✅ Listo. El agente ya está corriendo como servicio Windows.

### Lo que instala
- `C:\Program Files\Apollo Centinela\ApolloCentinela.exe`
- Servicio Windows **Apollo Centinela Agent** (inicio automático con SYSTEM)
- Recuperación automática: si el proceso cae, se reinicia en 5s / 10s / 30s
- Configuración en: `C:\ProgramData\ApolloSupport\centinela_config.json`

### Verificar que funciona
Abrir `services.msc` → buscar "Apollo Centinela Agent" → Estado: **En ejecución**

---

## Desinstalación

**Opción 1 (recomendada):** Panel de Control → Programas → Apollo Centinela → Desinstalar

**Opción 2 (emergencia):** Ejecutar como Admin: `C:\Program Files\Apollo Centinela\uninstall_service.bat`

---

## Configuración del servidor

El agente se conecta por defecto a: `wss://support.ultimate.net.ar/api/ws/centinela`

Para cambiar el servidor (ej: desarrollo local), editar:
```
C:\ProgramData\ApolloSupport\centinela_config.json
```
```json
{
  "base_ws_url": "ws://localhost:8001/api/ws/centinela",
  "license_key": "...",
  "device_name": "PC-CLIENTE"
}
```
Luego reiniciar el servicio: `services.msc` → Apollo Centinela Agent → Reiniciar

---

## Estructura de archivos generados

```
agent/
├── build_installer.bat       ← SCRIPT MAESTRO (doble click para generar todo)
├── centinela.py              ← Código fuente del agente
├── ApolloCentinela.spec      ← Configuración de PyInstaller
├── dist/
│   └── ApolloCentinela.exe   ← EXE compilado (generado automáticamente)
├── installer/
│   ├── ApolloSetup.iss       ← Script de Inno Setup
│   └── license.rtf           ← Términos de uso (se muestra en el wizard)
└── installer_output/
    └── ApolloSetup_v2.0.0.exe ← INSTALADOR FINAL para distribuir al cliente
```
