; Lumina Player - Inno Setup 6 Kurulum Betiği
; Windows 10/11 64-bit Tam Entegrasyonlu Kurucu

#define MyAppName "Lumina Player"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "Lumina Player"
#define MyAppURL "https://github.com/luminaplayer"
#define MyAppExeName "LuminaPlayer.exe"

[Setup]
AppId={{5D9D4537-83FA-4B7C-A96B-D295FF6C0194}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=LuminaPlayer_Setup_v{#MyAppVersion}
OutputDir=..\dist
SetupIconFile=..\lumina\resources\app.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "associatefiles"; Description: "Popüler medya dosyalarını (MP4, MKV, MP3 vb.) Lumina Player ile ilişkilendir"; GroupDescription: "Dosya İlişkilendirmeleri:"

[Files]
Source: "..\dist\LuminaPlayer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Windows Birlikte Aç ve İçerik Menüsü: Klasöre sağ tık "Lumina Player ile Oynat"
Root: HKCR; Subkey: "Directory\shell\LuminaPlayer"; ValueType: string; ValueData: "Lumina Player ile Oynat"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\LuminaPlayer"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "Directory\shell\LuminaPlayer\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

; Medya dosyası sağ tık "Lumina Player ile Oynat"
Root: HKCR; Subkey: "*\shell\LuminaPlayer"; ValueType: string; ValueData: "Lumina Player ile Oynat"; Flags: uninsdeletekey
Root: HKCR; Subkey: "*\shell\LuminaPlayer"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""
Root: HKCR; Subkey: "*\shell\LuminaPlayer\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

; Dosya uzantı ilişkilendirmeleri (İsteğe bağlı task)
Root: HKCR; Subkey: ".mp4\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".mkv\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".avi\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".mov\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".wmv\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".webm\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".flv\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".m4v\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".ts\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".mp3\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".flac\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles
Root: HKCR; Subkey: ".wav\OpenWithProgids"; ValueType: none; ValueName: "LuminaPlayer.Media"; Flags: uninsdeletevalue; Tasks: associatefiles

Root: HKCR; Subkey: "LuminaPlayer.Media"; ValueType: string; ValueData: "Medya Dosyası (Lumina)"; Flags: uninsdeletekey; Tasks: associatefiles
Root: HKCR; Subkey: "LuminaPlayer.Media\DefaultIcon"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"",0"; Tasks: associatefiles
Root: HKCR; Subkey: "LuminaPlayer.Media\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: associatefiles

; Windows 10/11 Varsayılan Uygulamalar Yetenekleri (Capabilities)
Root: HKLM; Subkey: "Software\LuminaPlayer\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Modern ve güçlü Windows Medya Oynatıcısı"
Root: HKLM; Subkey: "Software\LuminaPlayer\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#MyAppName}"
Root: HKLM; Subkey: "Software\LuminaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp4"; ValueData: "LuminaPlayer.Media"
Root: HKLM; Subkey: "Software\LuminaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mkv"; ValueData: "LuminaPlayer.Media"
Root: HKLM; Subkey: "Software\LuminaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".avi"; ValueData: "LuminaPlayer.Media"
Root: HKLM; Subkey: "Software\LuminaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mov"; ValueData: "LuminaPlayer.Media"
Root: HKLM; Subkey: "Software\LuminaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wmv"; ValueData: "LuminaPlayer.Media"
Root: HKLM; Subkey: "Software\LuminaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".webm"; ValueData: "LuminaPlayer.Media"
Root: HKLM; Subkey: "Software\LuminaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp3"; ValueData: "LuminaPlayer.Media"
Root: HKLM; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "LuminaPlayer"; ValueData: "Software\LuminaPlayer\Capabilities"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
