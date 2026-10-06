; ==============================================================================
; Apollo Centinela - Script de Instalador Profesional v3.0
; Herramienta: Inno Setup 6.x
;
; ARQUITECTURA DOS PROCESOS:
;   ApolloCentinelaService.exe  ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ Windows Service (Session 0, SYSTEM)
;     - Arranca con Windows, SIN necesidad de login de usuario
;     - Mantiene conexion WebSocket con el backend (device siempre "online")
;     - Detecta cuando un usuario inicia sesion y lanza el companion
;
;   ApolloCentinela.exe  ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ Companion UI (sesion interactiva del usuario)
;     - Lanzado automaticamente por el Service en la sesion del usuario
;     # NOTA: La auto-elevacion a admin es necesaria para que mss (screen capture)
;     # funcione sin restricciones en todas las configuraciones de Windows.
;     # is_running_as_service() ahora usa ProcessIdToSessionId ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â no se ve afectada
;     # por el nivel de privilegio, solo por el Session ID (0=servicio, 1+=usuario).
;     if not is_admin():
;         try:
;             script = sys.executable if getattr(sys, 'frozen', False) else __file__
;             ctypes.windll.shell32.ShellExecuteW(None, "runas", script, " ".join(sys.argv[1:]), None, 1)
;             sys.exit(0)
;         except Exception as e:
;             print(f"No se pudieron elevar privilegios: {e}")
;             # Continuar sin admin ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â mss intentara funcionar igual
;     - Si el companion cae, el Service lo relanza automaticamente
; ==============================================================================

#define MyAppName      "Apollo Centinela"
#define MyAppVersion   "3.3.38"
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
DefaultDirName={commonpf}\Apollo Centinela
DefaultGroupName=Apollo Centinela
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=ApolloSetup_v{#MyAppVersion}
SetupIconFile=..\apollo_logo.ico
WizardImageFile=wizard_banner.bmp
WizardSmallImageFile=wizard_icon.bmp
WizardStyle=modern
Compression=lzma2/max
SolidCompression=no
PrivilegesRequired=admin
MinVersion=6.1
CloseApplications=force
CloseApplicationsFilter=ApolloCentinela.exe,ApolloCentinelaService.exe,Apollo_Centinela.exe,ApolloGesComBeta.exe,ApolloGesCom.exe,ApolloSoporte.exe
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#ServiceExe}
UninstallDisplayName={#MyAppName} v{#MyAppVersion}
CreateUninstallRegKey=yes
LicenseFile=license.rtf

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

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
; Servicio + companion x64 (el instalador unificado ya no embebe x86; usar ApolloSetup_*_x86.iss)
Source: "..\dist\ApolloCentinelaService_x64.exe"; DestDir: "{app}"; DestName: "{#ServiceExe}"; Flags: ignoreversion
Source: "..\dist\ApolloCentinela_x64.exe"; DestDir: "{app}"; DestName: "{#CompanionExe}"; Flags: ignoreversion

; Iconos y recursos
Source: "..\apollo_logo.ico";      DestDir: "{app}"; Flags: ignoreversion
Source: "..\apollo_logo.png";      DestDir: "{app}"; Flags: ignoreversion

; DLLs de Visual C++ Runtime ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â incluidas directamente para compatibilidad

; Visual C++ 2015-2022 Redistributable ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â instala Universal CRT
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: ignoreversion deleteafterinstall

; ffmpeg.exe ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â necesario para el modo Alto Rendimiento (H.264 MSE).
Source: "..\ffmpeg.exe";           DestDir: "{app}"; Flags: ignoreversion nocompression

[Dirs]
Name: "{commonappdata}\ApolloSupport"; Permissions: everyone-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#CompanionExe}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#CompanionExe}"; Tasks: desktopicon

[Registry]
Root: HKLM; Subkey: "Software\MasterIS\ApolloSupport"; ValueType: string; ValueName: "Version";     ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\MasterIS\ApolloSupport"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"
Root: HKLM; Subkey: "Software\MasterIS\ApolloSupport"; ValueType: string; ValueName: "Publisher";   ValueData: "{#MyAppPublisher}"

[Run]
; 0. VC++ Redistributable (antes de registrar el servicio)
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; \
  Flags: runhidden waituntilterminated; StatusMsg: "Instalando dependencias del sistema..."; \
  Check: Is64BitInstallMode and VCRedistNeedsInstall

; 1. Registrar el SERVICE EXE como Windows Service (start= auto = tras reinicio nocturno)
Filename: "{sys}\sc.exe"; Parameters: "create ""{#ServiceName}"" binPath= ""\""{app}\{#ServiceExe}\"""" start= auto obj= LocalSystem DisplayName= ""{#ServiceDisplay}"""; Flags: runhidden waituntilterminated; StatusMsg: "{cm:Installing}"
Filename: "{sys}\sc.exe"; Parameters: "config ""{#ServiceName}"" start= auto"; Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "failure ""{#ServiceName}"" reset= 86400 actions= restart/5000/restart/10000/restart/30000"; Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "description ""{#ServiceName}"" ""Agente Apollo Centinela - Master IS. Mantiene la conexion con el servidor de soporte 24/7."""; Flags: runhidden waituntilterminated

; 2. Servicio sin esperar + companion visible (upgrade web/OTA automatico)
Filename: "{sys}\cmd.exe"; Parameters: "/c sc start ""{#ServiceName}"" >nul 2>&1 & for /L %I in (1,1,15) do @(sc query ""{#ServiceName}"" | findstr /I ""RUNNING"" >nul && exit /b 0 & timeout /t 1 /nobreak >nul) & exit /b 0"; Flags: runhidden waituntilterminated; StatusMsg: "{cm:StartingSvc}"

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM ""{#CompanionExe}""";  Flags: runhidden waituntilterminated; RunOnceId: "KillCompanion"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM ""{#ServiceExe}""";    Flags: runhidden waituntilterminated; RunOnceId: "KillService"
Filename: "{sys}\sc.exe";       Parameters: "stop ""{#ServiceName}""";     Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
Filename: "{sys}\cmd.exe";      Parameters: "/c timeout /t 1 /nobreak";    Flags: runhidden waituntilterminated; RunOnceId: "Wait"
Filename: "{sys}\sc.exe";       Parameters: "delete ""{#ServiceName}""";   Flags: runhidden waituntilterminated; RunOnceId: "DeleteSvc"


[Messages]
spanish.WelcomeLabel1=Bienvenido al instalador de [name]
spanish.WelcomeLabel2=Este asistente instalara [name/ver] en su equipo.%n%nArquitectura de dos procesos:%n%nÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ Servicio Windows: mantiene el equipo conectado 24/7, incluso sin usuario logueado.%nÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ Icono de bandeja: aparece automaticamente cuando un usuario inicia sesion.%n%nSe recomienda cerrar todas las aplicaciones antes de continuar.
spanish.FinishedLabel=Apollo Centinela instalado correctamente.%n%nEl equipo ahora aparece como "en linea" en el panel de soporte de Master IS.%n%nEl icono de bandeja aparecera automaticamente al iniciar sesion de Windows.

[Code]
#include "CentinelaInstallCode.iss"

function VCRedistNeedsInstall(): Boolean;
var
  sVersion: String;
begin
  if RegQueryStringValue(HKLM,
    'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
    'Version', sVersion) then
    Result := False
  else if FileExists(ExpandConstant('{sys}\vcruntime140.dll')) then
    Result := False
  else
    Result := True;
end;

