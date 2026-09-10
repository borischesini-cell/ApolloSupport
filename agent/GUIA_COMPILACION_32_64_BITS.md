# Guía de Compilación Dual (32-Bit / 64-Bit) — Apollo Centinela

Esta guía documenta la estructura, entornos y procesos requeridos para compilar el agente **Apollo Centinela** tanto en arquitectura **32-bit (x86)** como **64-bit (x64)**, garantizando compatibilidad total en sistemas Windows antiguos y modernos.

---

## 📐 1. Arquitectura de Binarios del Agente

El sistema Apollo Centinela se divide en dos componentes ejecutables por arquitectura:

| Componente | Archivo Fuente | Binario x86 (32-bit) | Binario x64 (64-bit) | Función |
| :--- | :--- | :--- | :--- | :--- |
| **Companion UI** | `centinela.py` | `ApolloCentinela_x86.exe` | `ApolloCentinela_x64.exe` | Aplicación interactiva de usuario (Tray icon, captura de pantalla WebP/H.264, inyección de inputs). |
| **Servicio Windows** | `centinela_svc.py` | `ApolloCentinelaService_x86.exe` | `ApolloCentinelaService_x64.exe` | Servicio de Windows permanente en **Sesión 0**. Monitorea el proceso companion, gestiona credenciales e inicia sesiones. |

---

## 🛠️ 2. Requisitos del Entorno de Compilación

Para compilar ambas arquitecturas en el mismo servidor de desarrollo se requiere:

### Intérpretes de Python:
- **Python 64-bit (v3.8 - v3.11)**: Utilizado para compilar ejecutables x64 nativos.
  - Ruta habitual: `C:\Program Files\Python311\python.exe` o comando `py -3.8-64`.
- **Python 32-bit (v3.8 - v3.11)**: Utilizado para compilar ejecutables x86 (32 bits).
  - Ruta habitual: `p:\ApolloSupport\agent\python38-32\python.exe` o `py -3.8-32`.

### Dependencias Pip Requeridas (instalar en ambos Pythons):
```cmd
python -m pip install pyinstaller websockets pyautogui "psutil<6.0.0" pillow pystray requests mss ctypes
```

### Compilador de Instaladores:
- **Inno Setup 6**: Instalado en `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`.

---

## ⚙️ 3. Archivos de Configuración PyInstaller (.spec)

Ubicación: `p:\ApolloSupport\agent\`

1. **`ApolloCentinela.spec`**:
   - Compila `centinela.py` en modo `--onefile` y `--noconsole`.
   - Embebe recursos gráficos (`apollo_logo.ico`, `apollo_logo.png`) y el motor de video H.264 (`ffmpeg.exe`).
2. **`ApolloCentinelaService_x86.spec`**:
   - Compila `centinela_svc.py` usando el Python de 32 bits → Genera `ApolloCentinelaService_x86.exe`.
3. **`ApolloCentinelaService_x64.spec`**:
   - Compila `centinela_svc.py` usando el Python de 64 bits → Genera `ApolloCentinelaService_x64.exe`.

---

## 🚀 4. Comandos de Compilación

### Opción A: Compilación Unificada Dual + Instaladores (Recomendado)
Ejecutar el script automatizado batch desde el directorio `p:\ApolloSupport\agent`:

```cmd
build_all_and_installer.bat
```

**Flujo del script automatizado (`build_all_and_installer.bat`)**:
1. Detecta automáticamente los entornos Python de 32 y 64 bits.
2. Instala/actualiza dependencias en ambos entornos.
3. Compila `ApolloCentinela_x86.exe` y `ApolloCentinelaService_x86.exe`.
4. Compila `ApolloCentinela_x64.exe` y `ApolloCentinelaService_x64.exe`.
5. Ejecuta **Inno Setup** (`ISCC.exe`) para generar los instaladores `.exe` finales en `agent\installer_output\`:
   - `ApolloSetup_x64.exe`
   - `ApolloSetup_x86.exe`
   - `ApolloSetup.exe` (Instalador unificado auto-detectable)

### Opción B: Compilación Rápida de Desarrollo (Solo x64)
Para probar cambios rápidos en la máquina de desarrollo local:

```cmd
python build_agent.py
```
*Genera `dist\ApolloCentinela.exe` inmediatamente.*

---

## 📁 5. Estructura de Salida de Archivos (`dist/`)

Una vez finalizado el build, la carpeta `p:\ApolloSupport\agent\dist\` contendrá:

```
agent/dist/
│── ApolloCentinela.exe            (Ejecutable x64 directo de desarrollo)
│── ApolloCentinela_x64.exe        (Companion UI 64-bit para producción)
│── ApolloCentinela_x86.exe        (Companion UI 32-bit para sistemas antiguos)
│── ApolloCentinelaService_x64.exe (Servicio Windows 64-bit)
│── ApolloCentinelaService_x86.exe (Servicio Windows 32-bit)
└── ffmpeg.exe                     (Motor de transcodificación de video H.264)
```

---

## 🔄 6. Distribución de Actualizaciones OTA (Over-The-Air)

El servidor FastAPI incluye endpoints para distribución directa y actualización en caliente de agentes de 32 y 64 bits:

- `GET /api/centinelas/download/installer/x64`: Descarga `ApolloSetup_x64.exe`.
- `GET /api/centinelas/download/installer/x86`: Descarga `ApolloSetup_x86.exe`.
- `POST /api/centinela/{device_id}/force_update`: Fuerza al agente cliente a descargar e instalar la versión correspondiente a su arquitectura.
