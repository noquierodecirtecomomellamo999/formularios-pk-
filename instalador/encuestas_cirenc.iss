; Instalador de Windows de Encuestas CIRENC (Inno Setup 6)
; Lo compila automáticamente GitHub Actions (.github/workflows/instalador.yml) a partir de la
; carpeta dist\Encuestas CIRENC que prepara instalador\construir.py.

#define Nombre "Encuestas CIRENC"
#ifndef Version
  #define Version "1.0.0"
#endif

[Setup]
AppId={{6F3B9A52-1C7E-4D8B-9E2A-5B0C8D7E1A23}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher=Asociación de Parkinson de La Roda (CIRENC)
AppComments=Encuestas en papel con lectura automática
; Instalación solo para el usuario: no pide permisos de administrador
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#Nombre}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
OutputDir=..\dist
OutputBaseFilename=Instalar-Encuestas-CIRENC
SetupIconFile=..\recursos\icono.ico
UninstallDisplayIcon={app}\recursos\icono.ico
UninstallDisplayName={#Nombre}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un icono en el escritorio"; GroupDescription: "Iconos:"

[Files]
Source: "..\dist\Encuestas CIRENC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#Nombre}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"""; WorkingDir: "{app}"; IconFilename: "{app}\recursos\icono.ico"; Comment: "Encuestas en papel con lectura automática"
Name: "{autoprograms}\Guía rápida de {#Nombre}"; Filename: "{app}\Guía rápida.pdf"
Name: "{autodesktop}\{#Nombre}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"""; WorkingDir: "{app}"; IconFilename: "{app}\recursos\icono.ico"; Comment: "Encuestas en papel con lectura automática"; Tasks: escritorio

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\lanzador.py"""; WorkingDir: "{app}"; Description: "Abrir {#Nombre} ahora"; Flags: nowait postinstall skipifsilent
Filename: "{app}\Guía rápida.pdf"; Description: "Ver la guía rápida"; Flags: shellexec nowait postinstall skipifsilent unchecked

[UninstallDelete]
; Archivos que Python crea al usarse (los datos están en Documentos y NO se borran)
Type: filesandordirs; Name: "{app}"

[Code]
// Cierra el programa si está abierto (para poder actualizarlo o desinstalarlo)
procedure CerrarPrograma();
var
  Codigo: Integer;
begin
  Exec('powershell.exe',
    '-NoProfile -ExecutionPolicy Bypass -Command "Get-Process python,pythonw -ErrorAction SilentlyContinue | ' +
    'Where-Object { $_.Path -like ''' + ExpandConstant('{app}') + '\*'' } | Stop-Process -Force"',
    '', SW_HIDE, ewWaitUntilTerminated, Codigo);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  CerrarPrograma();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  CerrarPrograma();
  Result := True;
end;
