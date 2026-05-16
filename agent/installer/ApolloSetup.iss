; ==============================================================================
; Apollo Centinela - Script de Instalador Profesional v3.0
; Herramienta: Inno Setup 6.x
;
; ARQUITECTURA DOS PROCESOS:
;   ApolloCentinelaService.exe  → Windows Service (Session 0, SYSTEM)
;     - Arranca con Windows, SIN necesidad de login de usuario
;     - Mantiene conexion WebSocket con el backend (device siempre "online")
;     - Detecta cuando un usuario inicia sesion y lanza el companion
;
;   ApolloCentinela.exe  → Companion UI (sesion interactiva del usuario)
;     - Lanzado automaticamente por el Service en la sesion del usuario
;     # NOTA: La auto-elevacion a admin es necesaria para que mss (screen capture)
;     # funcione sin restricciones en todas las configuraciones de Windows.
;     # is_running_as_service() ahora usa ProcessIdToSessionId — no se ve afectada
;     # por el nivel de privilegio, solo por el Session ID (0=servicio, 1+=usuario).
;     if not is_admin():
;         try:
;             script = sys.executable if getattr(sys, 'frozen', False) else __file__
;             ctypes.windll.shell32.ShellExecuteW(None, "runas", script, " ".join(sys.argv[1:]), None, 1)
;             sys.exit(0)
;         except Exception as e:
;             print(f"No se pudieron elevar privilegios: {e}")
;             # Continuar sin admin — mss intentara funcionar igual
;     - Si el companion cae, el Service lo relanza automaticamente
; ==============================================================================

#define MyAppName      "Apollo Centinela"
#define MyAppVersion   "3.0.0"
#define MyAppPublisher "Master IS"
#define MyAppURL       "https://support.ultimate.net.ar"
#define ServiceExe     "ApolloCentinelaService.exe"
#define CompanionExe   "ApolloCentinela.exe"
#define ServiceName    "ApolloCentinela"
#define ServiceDisplay "Apollo Centinela Agent"

[Setup]
AppId={{E7B3A2C4-1F5D-4E8A-9C3B-7D6F2A1E4B8C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Apollo Centinela
DefaultGroupName=Apollo Centinela
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=ApolloSetup_v{#MyAppVersion}
SetupIconFile=..\apollo_logo.ico
WizardImageFile=wizard_banner.bmp
WizardSmallImageFile=wizard_icon.bmp
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin
MinVersion=6.1
ArchitecturesAllowed=x86compatible x64compatible
UninstallDisplayIcon={app}\{#ServiceExe}
UninstallDisplayName={#MyAppName} v{#MyAppVersion}
CreateUninstallRegKey=yes
LicenseFile=license.rtf

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.Installing=Instalando Apollo Centinela...
spanish.StartingSvc=Iniciando servicio Windows...
spanish.Done=Instalacion completada. El agente esta en linea.
english.Installing=Installing Apollo Centinela...
english.StartingSvc=Starting Windows service...
english.Done=Installation complete. The agent is online.

[Files]
; Servicio (Session 0 - siempre activo)
Source: "..\dist\ApolloCentinelaService_x64.exe"; DestDir: "{app}"; DestName: "{#ServiceExe}"; Check: Is64BitInstallMode; Flags: ignoreversion
Source: "..\dist\ApolloCentinelaService_x86.exe"; DestDir: "{app}"; DestName: "{#ServiceExe}"; Check: not Is64BitInstallMode; Flags: ignoreversion

; Companion UI (lanzado por el servicio en sesion del usuario)
Source: "..\dist\ApolloCentinela_x64.exe"; DestDir: "{app}"; DestName: "{#CompanionExe}"; Check: Is64BitInstallMode; Flags: ignoreversion
Source: "..\dist\ApolloCentinela_x86.exe"; DestDir: "{app}"; DestName: "{#CompanionExe}"; Check: not Is64BitInstallMode; Flags: ignoreversion

; Iconos y recursos
Source: "..\apollo_logo.ico";      DestDir: "{app}"; Flags: ignoreversion
Source: "..\apollo_logo.png";      DestDir: "{app}"; Flags: ignoreversion

; DLLs de Visual C++ Runtime — incluidas directamente para compatibilidad
Source: "dlls\vcruntime140.dll";   DestDir: "{app}"; Flags: ignoreversion
Source: "dlls\vcruntime140_1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "dlls\msvcp140.dll";       DestDir: "{app}"; Flags: ignoreversion

; Visual C++ 2015-2022 Redistributable — instala Universal CRT
Source: "dlls\vc_redist.x64.exe"; DestDir: "{tmp}"; Check: Is64BitInstallMode; Flags: ignoreversion deleteafterinstall

; ffmpeg.exe — necesario para el modo Alto Rendimiento (H.264 MSE).
Source: "..\ffmpeg.exe";           DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\ApolloSupport"; Permissions: everyone-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#CompanionExe}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"

[Registry]
Root: HKLM; Subkey: "Software\MasterIS\ApolloSupport"; ValueType: string; ValueName: "Version";     ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\MasterIS\ApolloSupport"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"
Root: HKLM; Subkey: "Software\MasterIS\ApolloSupport"; ValueType: string; ValueName: "Publisher";   ValueData: "{#MyAppPublisher}"

[Run]
; 1. Registrar el SERVICE EXE como Windows Service
Filename: "{sys}\sc.exe"; Parameters: "create ""{#ServiceName}"" binPath= ""\""{app}\{#ServiceExe}\"""" start= auto obj= LocalSystem DisplayName= ""{#ServiceDisplay}"""; Flags: runhidden waituntilterminated; StatusMsg: "{cm:Installing}"
Filename: "{sys}\sc.exe"; Parameters: "failure ""{#ServiceName}"" reset= 86400 actions= restart/5000/restart/10000/restart/30000"; Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "description ""{#ServiceName}"" ""Agente Apollo Centinela - Master IS. Mantiene la conexion con el servidor de soporte 24/7."""; Flags: runhidden waituntilterminated

; 2. Iniciar el servicio
Filename: "{sys}\sc.exe"; Parameters: "start ""{#ServiceName}"""; Flags: runhidden waituntilterminated; StatusMsg: "{cm:StartingSvc}"

; 0. Instalar Visual C++ 2015-2022 Redistributable x64 si aplica
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; \
  Flags: runhidden waituntilterminated; StatusMsg: "Instalando dependencias del sistema..."; \
  Check: Is64BitInstallMode and VCRedistNeedsInstall

; 3. Dar tiempo al servicio para inicializarse
Filename: "{sys}\cmd.exe"; Parameters: "/c timeout /t 4 /nobreak"; Flags: runhidden waituntilterminated; StatusMsg: "Iniciando agente..."

; 4. Lanzar el companion como el USUARIO ORIGINAL
Filename: "{app}\{#CompanionExe}"; Flags: nowait shellexec runasoriginaluser; StatusMsg: "Iniciando tray icon..."

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM ""{#CompanionExe}""";  Flags: runhidden waituntilterminated; RunOnceId: "KillCompanion"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM ""{#ServiceExe}""";    Flags: runhidden waituntilterminated; RunOnceId: "KillService"
Filename: "{sys}\sc.exe";       Parameters: "stop ""{#ServiceName}""";     Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
Filename: "{sys}\cmd.exe";      Parameters: "/c timeout /t 3 /nobreak";    Flags: runhidden waituntilterminated; RunOnceId: "Wait"
Filename: "{sys}\sc.exe";       Parameters: "delete ""{#ServiceName}""";   Flags: runhidden waituntilterminated; RunOnceId: "DeleteSvc"


[Messages]
spanish.WelcomeLabel1=Bienvenido al instalador de [name]
spanish.WelcomeLabel2=Este asistente instalara [name/ver] en su equipo.%n%nArquitectura de dos procesos:%n%n• Servicio Windows: mantiene el equipo conectado 24/7, incluso sin usuario logueado.%n• Icono de bandeja: aparece automaticamente cuando un usuario inicia sesion.%n%nSe recomienda cerrar todas las aplicaciones antes de continuar.
spanish.FinishedLabel=Apollo Centinela instalado correctamente.%n%nEl equipo ahora aparece como "en linea" en el panel de soporte de Master IS.%n%nEl icono de bandeja aparecera automaticamente al iniciar sesion de Windows.

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';

  // 1. Detener el servicio
  Exec(ExpandConstant('{sys}\sc.exe'), 'stop "ApolloCentinela"', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 2. Matar el companion nuevo
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM "ApolloCentinela.exe"', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 3. Matar el centinela VIEJO (Apollo_Centinela.exe con guion bajo — build anterior)
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM "Apollo_Centinela.exe"', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 4. Matar el service wrapper
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM "ApolloCentinelaService.exe"', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 5. Eliminar el registro del servicio
  Exec(ExpandConstant('{sys}\sc.exe'), 'delete "ApolloCentinela"', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 6. Esperar que el SO libere los handles
  Sleep(3000);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

function VCRedistNeedsInstall(): Boolean;
var
  sVersion: String;
begin
  // Verificar si VC++ 2015-2022 Redist x64 ya está instalado (v14.x)
  if RegQueryStringValue(HKLM,
    'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
    'Version', sVersion) then
  begin
    // Ya instalado — saltar
    Result := False;
  end else begin
    Result := True;  // No instalado — instalar
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // No borrar centinela_config.json al desinstalar (preserva license_key)
end;
