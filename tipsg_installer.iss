; ============================================================================
; TIPS-G ALWAR Student Attendance AI System — Inno Setup Script
; Generates a professional Windows Setup Installer (.exe) with desktop icons,
; start menu shortcuts, pre-configured server connection, and AI models.
; ============================================================================

#define MyAppName "TIPS-G ALWAR Attendance System"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TIPS-G ALWAR"
#define MyAppURL "https://tipsg.edu.in"
#define MyAppExeName "TIPS-G-Attendance.exe"
#define MyIconFile "storage\TIPS-G-ALWAR.ico"

[Setup]
; Unique AppId generated for TIPS-G ALWAR Attendance System
AppId={{D68F23A4-192B-4E76-857A-38E4A0D97E5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\TIPS-G ALWAR\Attendance System
DefaultGroupName=TIPS-G ALWAR
DisableProgramGroupPage=yes
LicenseFile=
OutputDir=dist_installer
OutputBaseFilename=Setup_TIPS-G_Attendance_v{#MyAppVersion}
SetupIconFile={#MyIconFile}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "downloadmodels"; Description: "Download / Verify AI Face Recognition Models (Requires Internet)"; GroupDescription: "AI Engine Components:"; Flags: checkedonce

[Files]
; Main Executable from PyInstaller build
Source: "dist\TIPS-G-Attendance.exe"; DestDir: "{app}"; Flags: ignoreversion

; Configuration File (Pre-configured with VPS backend host)
Source: "config.ini"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

; Brand Assets & Icons
Source: "storage\TIPS-G-ALWAR.ico"; DestDir: "{app}\storage"; Flags: ignoreversion
Source: "storage\_TIPS-G ALWAR.png"; DestDir: "{app}\storage"; Flags: ignoreversion

; Bundle AI Models so face recognition works immediately offline on all laptops
Source: "models\face_landmarker.task"; DestDir: "{app}\models"; Flags: ignoreversion skipifsourcedoesntexist
Source: "models\arcface_resnet50.onnx"; DestDir: "{app}\models"; Flags: ignoreversion skipifsourcedoesntexist
Source: "models\retinaface_resnet50.onnx"; DestDir: "{app}\models"; Flags: ignoreversion skipifsourcedoesntexist

[Dirs]
Name: "{app}\storage"; Permissions: users-full
Name: "{app}\storage\reports"; Permissions: users-full
Name: "{app}\storage\documents"; Permissions: users-full
Name: "{app}\storage\students"; Permissions: users-full
Name: "{app}\models"; Permissions: users-full
Name: "{app}\logs"; Permissions: users-full

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\storage\TIPS-G-ALWAR.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\storage\TIPS-G-ALWAR.ico"; Tasks: desktopicon

[Run]
; Download missing models via PowerShell if task is checked and models do not exist
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -Command ""& {{ $modelsDir = '{app}\models'; New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null; $models = @{{ 'arcface_resnet50.onnx' = 'https://huggingface.co/garavv/arcface-onnx/resolve/main/arc.onnx'; 'retinaface_resnet50.onnx' = 'https://huggingface.co/TheEeeeLin/HivisionIDPhotos_matting/resolve/main/retinaface-resnet50.onnx'; 'face_landmarker.task' = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task' }}; foreach ($m in $models.Keys) {{ $target = Join-Path $modelsDir $m; if (-not (Test-Path $target)) {{ Write-Host ('Downloading ' + $m + '...'); [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile($models[$m], $target); }} }} }}"""; StatusMsg: "Downloading AI Face Recognition Models (this may take a couple minutes)..."; Tasks: downloadmodels; Flags: runhidden

; Launch App Option after Installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
