; ─────────────────────────────────────────────────────────────────────────────
;  IsotopeTrack – Inno Setup Installer Script
;  Requires: Inno Setup 6.x  (https://jrsoftware.org/isinfo.php)
; ─────────────────────────────────────────────────────────────────────────────

#define AppName        "IsotopeTrack"
#define AppVersion     "1.10.7"
#define AppPublisher   "IsotopeTrack"
#define AppExeName     "IsotopeTrack.exe"
#define SourceDir      "..\dist\IsotopeTrack"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}

; Default install path: C:\Program Files\IsotopeTrack
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

; Require admin rights (needed to write to Program Files)
PrivilegesRequired=admin

; Output installer file
OutputDir=..\Output
OutputBaseFilename=IsotopeTrack_Setup_{#AppVersion}_W

; Installer icon
SetupIconFile=..\images\isotrack_icon.ico

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Windows version requirements
MinVersion=10.0

; Wizard styling
WizardStyle=modern
WizardImageFile=installer\wizard_100.png,installer\wizard_200.png
WizardSmallImageFile=installer\wizard_small_100.png,installer\wizard_small_200.png

; Uninstall
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}

; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Refresh Explorer's icon/association cache after registering .itproj
ChangesAssociations=yes

; ── Languages ─────────────────────────────────────────────────────────────────
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ── Files to install ──────────────────────────────────────────────────────────
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Start Menu shortcuts ──────────────────────────────────────────────────────
[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

; ── Tasks ─────────────────────────────────────────────────────────────────────
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

; ── Run app after install ─────────────────────────────────────────────────────
[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; ── Registry ──────────────────────────────────────────────────────────────────
[Registry]
Root: HKLM; Subkey: "Software\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "Version";     ValueData: "{#AppVersion}"

; File association: .itproj project files open in IsotopeTrack on double-click.
; The "%1" passes the clicked file path to the exe, which the app's CLI loads
; as the project file. Keys are removed on uninstall.
Root: HKLM; Subkey: "Software\Classes\.itproj"; ValueType: string; ValueName: ""; ValueData: "IsotopeTrack.Project"; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Classes\IsotopeTrack.Project"; ValueType: string; ValueName: ""; ValueData: "IsotopeTrack Project"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\IsotopeTrack.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"
Root: HKLM; Subkey: "Software\Classes\IsotopeTrack.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""
