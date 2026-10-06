#define MyAppName "Delivery Note Converter"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Kaveesha Bandara"
#define MyAppExeName "DeliveryNoteConverter.exe"

[Setup]
; Keep this AppId unchanged for future versions.
AppId=KaveeshaBandara.DeliveryNoteConverter

AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={localappdata}\Programs\DeliveryNoteConverter
DefaultGroupName={#MyAppName}

PrivilegesRequired=lowest
DisableProgramGroupPage=yes

OutputDir=..\installer-output
OutputBaseFilename=DeliveryNoteConverter-Setup-{#MyAppVersion}

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\release\DeliveryNoteConverter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent