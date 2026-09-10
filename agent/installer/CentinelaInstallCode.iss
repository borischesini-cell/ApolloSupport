// Codigo compartido: detener procesos viejos antes/despues de instalar (manual + OTA silencioso)



procedure KillProcessByImage(const ImageName: String);

var

  ResultCode: Integer;

begin

  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM ' + ImageName, '',

    SW_HIDE, ewWaitUntilTerminated, ResultCode);

end;



procedure KillAllApolloProcessesPowerShell;

var

  ResultCode: Integer;

  PsCmd: String;

begin

  PsCmd := '-NoProfile -ExecutionPolicy Bypass -Command "Get-Process -ErrorAction SilentlyContinue | ' +

    'Where-Object { $_.ProcessName -like ''Apollo*'' -and $_.ProcessName -notmatch ''Setup'' } | ' +

    'Stop-Process -Force -ErrorAction SilentlyContinue"';

  if FileExists(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe')) then

    Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), PsCmd, '',

      SW_HIDE, ewWaitUntilTerminated, ResultCode)

  else if FileExists(ExpandConstant('{sys}\powershell.exe')) then

    Exec(ExpandConstant('{sys}\powershell.exe'), PsCmd, '',

      SW_HIDE, ewWaitUntilTerminated, ResultCode);

end;



procedure KillCompanionProcessesOnly;

var

  I: Integer;

  Images: array[0..5] of String;

begin

  Images[0] := 'ApolloCentinela.exe';

  Images[1] := 'Apollo_Centinela.exe';

  Images[2] := 'ApolloGesComBeta.exe';

  Images[3] := 'ApolloGesCom.exe';

  Images[4] := 'ApolloSoporte.exe';

  Images[5] := 'ApolloSupport.exe';



  for I := 0 to 5 do

    KillProcessByImage(Images[I]);

  KillAllApolloProcessesPowerShell;

  Sleep(500);

end;



procedure StopAllCentinelaProcesses;

var

  ResultCode: Integer;

  I: Integer;

  Images: array[0..7] of String;

begin

  Images[0] := 'ApolloCentinela.exe';

  Images[1] := 'Apollo_Centinela.exe';

  Images[2] := 'ApolloCentinelaService.exe';

  Images[3] := 'ApolloGesComBeta.exe';

  Images[4] := 'ApolloGesCom.exe';

  Images[5] := 'ApolloSoporte.exe';

  Images[6] := 'ApolloSupport.exe';

  Images[7] := 'Apollo_Centinela_Service.exe';



  { 1) Detener servicio Windows }

  Exec(ExpandConstant('{sys}\sc.exe'), 'stop "ApolloCentinela"', '',

    SW_HIDE, ewWaitUntilTerminated, ResultCode);

  Sleep(1500);



  { 2) Matar por nombre de imagen (todas las rutas, incl. GesCom28) }

  for I := 0 to 7 do

    KillProcessByImage(Images[I]);



  Sleep(1000);



  { 3) Cualquier proceso Apollo* residual (legacy / copias sueltas) }

  KillAllApolloProcessesPowerShell;



  Sleep(1000);



  { 4) Segunda pasada por si el servicio relanzo algo }

  for I := 0 to 3 do

    KillProcessByImage(Images[I]);

  KillProcessByImage('ApolloCentinelaService.exe');



  { 5) Quitar registro del servicio para que [Run] pueda recrearlo con binPath nuevo }

  Exec(ExpandConstant('{sys}\sc.exe'), 'delete "ApolloCentinela"', '',

    SW_HIDE, ewWaitUntilTerminated, ResultCode);



  Sleep(2000);

end;



procedure EnsureCentinelaServiceAndCompanion;

var

  ResultCode: Integer;

  AppDir: String;

begin

  AppDir := ExpandConstant('{app}');



  { Servicio: inicio automatico al reiniciar (sin login de usuario) }

  Exec(ExpandConstant('{sys}\sc.exe'), 'config "ApolloCentinela" start= auto', '',

    SW_HIDE, ewWaitUntilTerminated, ResultCode);

  Exec(ExpandConstant('{sys}\sc.exe'), 'start "ApolloCentinela"', '',

    SW_HIDE, ewWaitUntilTerminated, ResultCode);

  Sleep(8000);



  { Fallback visible: si el servicio ya lanzo el companion, el mutex hace exit 0 }

  if FileExists(AppDir + '\ApolloCentinela.exe') then

    Exec(AppDir + '\ApolloCentinela.exe', '', AppDir, SW_SHOW, ewNoWait, ResultCode);

end;



function PrepareToInstall(var NeedsRestart: Boolean): String;

begin

  Result := '';

  StopAllCentinelaProcesses;

end;



function InitializeSetup(): Boolean;

begin

  StopAllCentinelaProcesses;

  Result := True;

end;



procedure CurStepChanged(CurStep: TSetupStep);

begin

  { Antes de copiar archivos: asegurar que ningun .exe viejo bloquee el reemplazo }

  if CurStep = ssInstall then

    StopAllCentinelaProcesses;



  { Tras copiar archivos: solo companions; NO borrar el servicio (lo hace [Run]) }

  if CurStep = ssPostInstall then

    KillCompanionProcessesOnly;



  { Tras [Run]: servicio auto + companion visible para el tecnico }

  if CurStep = ssDone then

    EnsureCentinelaServiceAndCompanion;

end;



procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);

begin

  if CurUninstallStep = usUninstall then

    StopAllCentinelaProcesses;

end;

