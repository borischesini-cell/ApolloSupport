// Detener procesos viejos ANTES de CloseApplications.
// Si el servicio sigue vivo, revive el companion y el .exe queda
// bloqueado: Inno "termina" pero no reemplaza (queda en 3.3.4).

var
  GStoppedCentinela: Boolean;

function ServiceIsInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\sc.exe'), 'query "ApolloCentinela"', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := ResultCode = 0;
end;

procedure KillProcessByImage(const ImageName: String);
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM ' + ImageName, '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure KillCompanionImages;
var
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
  for I := 0 to 7 do
    KillProcessByImage(Images[I]);
end;

procedure WaitForCentinelaServiceRemoval;
var
  I: Integer;
begin
  for I := 1 to 40 do
  begin
    if not ServiceIsInstalled then
      Exit;
    KillCompanionImages;
    Sleep(250);
  end;
end;

procedure StopAllCentinelaProcesses;
var
  ResultCode: Integer;
begin
  if GStoppedCentinela then
    Exit;

  { Parar servicio sin esperar eternamente (START_PENDING cuelga sc stop). }
  Exec(ExpandConstant('{sys}\cmd.exe'),
    '/c sc stop ApolloCentinela >nul 2>&1 & exit /b 0',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(300);

  KillCompanionImages;
  Sleep(400);

  Exec(ExpandConstant('{sys}\cmd.exe'),
    '/c sc delete ApolloCentinela >nul 2>&1 & exit /b 0',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  WaitForCentinelaServiceRemoval;

  KillCompanionImages;
  GStoppedCentinela := True;
end;

procedure StartCentinelaServiceWait;
{ Arranca el servicio (elevado) y espera RUNNING hasta ~20s. }
var
  ResultCode: Integer;
  Cmd: String;
begin
  Cmd :=
    '/c sc config ApolloCentinela start= auto >nul 2>&1' +
    ' & sc start ApolloCentinela >nul 2>&1' +
    ' & for /L %I in (1,1,20) do @(' +
    'sc query ApolloCentinela | findstr /I "RUNNING" >nul && exit /b 0' +
    ' & timeout /t 1 /nobreak >nul' +
    ' )' +
    ' & exit /b 0';
  Exec(ExpandConstant('{sys}\cmd.exe'), Cmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure LaunchCompanionAsUser;
{ Abre la UI en la sesion del usuario (NO como admin/Session 0).
  Si se lanza elevado, la ventana no aparece en el escritorio del cliente. }
var
  ResultCode: Integer;
  ExePath: String;
begin
  ExePath := ExpandConstant('{app}\ApolloCentinela.exe');
  if not FileExists(ExePath) then
    Exit;
  { ExecAsOriginalUser: mismo usuario que inicio el setup (antes del UAC). }
  ExecAsOriginalUser(ExePath, '', ExpandConstant('{app}'), SW_SHOWNORMAL, ewNoWait, ResultCode);
end;

procedure EnsureCentinelaServiceAndCompanion;
begin
  { Servicio primero (SYSTEM). El monitor del servicio lanza el companion
    en la sesion del usuario. Ademas intentamos abrir la UI como el usuario
    original del setup (instalacion interactiva con UAC).
    En OTA lanzado por el servicio (SYSTEM), ExecAsOriginalUser puede no
    aplicar: en ese caso alcanza con sc start + companion_monitor. }
  StartCentinelaServiceWait;
  Sleep(1000);
  LaunchCompanionAsUser;
  { Segunda chance por si el primer spawn del servicio perdio la carrera. }
  Sleep(2500);
  LaunchCompanionAsUser;
end;

function InitializeSetup(): Boolean;
begin
  GStoppedCentinela := False;
  StopAllCentinelaProcesses;
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  GStoppedCentinela := False;
  StopAllCentinelaProcesses;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    GStoppedCentinela := False;
    StopAllCentinelaProcesses;
  end;

  if CurStep = ssDone then
    EnsureCentinelaServiceAndCompanion;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    GStoppedCentinela := False;
    StopAllCentinelaProcesses;
  end;
end;
