; Stable, runtime-independent entry. Desktop and pinned links keep this path.
Unicode true
!include "FileFunc.nsh"
Name "Cove Studio"
Caption "Cove Studio"
OutFile "${COVE_LAUNCHER}"
Icon "..\assets\cove.ico"
RequestExecutionLevel user
SilentInstall silent
AutoCloseWindow true
VIProductVersion "${COVE_VERSION}.0"
VIAddVersionKey "ProductName" "Cove Studio"
VIAddVersionKey "FileDescription" "Cove Studio Launcher"
VIAddVersionKey "FileVersion" "${COVE_VERSION}"
VIAddVersionKey "LegalCopyright" "Cove contributors"
LoadLanguageFile "${NSISDIR}\Contrib\Language files\SimpChinese.nlf"
LoadLanguageFile "${NSISDIR}\Contrib\Language files\English.nlf"
LangString LaunchInvalid 2052 "Cove 安装文件不完整。请重新运行 Cove 安装器。"
LangString LaunchInvalid 1033 "Cove installation is incomplete. Please run the Cove installer again."
LangString LaunchBusy 2052 "Cove 正在安装。请完成或取消安装后再打开。"
LangString LaunchBusy 1033 "Cove setup is running. Finish or cancel setup before opening Cove."
Function .onInit
  System::Call 'kernel32::GetUserDefaultUILanguage() i.r0'
  IntOp $0 $0 & 0x3ff
  StrCpy $LANGUAGE 1033
  StrCmp $0 4 0 +2
    StrCpy $LANGUAGE 2052
FunctionEnd
Section
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "Local\Cove.Workbench.Upgrade") p.r0'
  StrCmp $0 0 launcher_read
    System::Call 'kernel32::CloseHandle(p r0)'
    MessageBox MB_OK|MB_ICONINFORMATION "$(LaunchBusy)"
    SetErrorLevel 1618
    Quit
  launcher_read:
  ClearErrors
  FileOpen $0 "$EXEDIR\.cove-install" r
  IfErrors invalid
  FileRead $0 $1
  FileClose $0
  StrCmp $1 "cove-preview-v1" 0 invalid
  FileOpen $0 "$EXEDIR\.cove-current" r
  IfErrors invalid
  FileRead $0 $R0
  FileClose $0
  StrLen $0 $R0
  IntCmp $0 32 invalid 0 invalid
  StrCpy $R1 0
  StrCpy $R3 0
  StrCpy $R4 0
  scan:
    StrCpy $R2 $R0 1 $R1
    StrCmp $R2 "" checked
    StrCmp $R2 "." dot
    StrCmp $R2 "0" digit
    StrCmp $R2 "1" digit
    StrCmp $R2 "2" digit
    StrCmp $R2 "3" digit
    StrCmp $R2 "4" digit
    StrCmp $R2 "5" digit
    StrCmp $R2 "6" digit
    StrCmp $R2 "7" digit
    StrCmp $R2 "8" digit
    StrCmp $R2 "9" digit invalid
  dot:
    StrCmp $R4 0 invalid
    IntOp $R3 $R3 + 1
    StrCpy $R4 0
    Goto next_char
  digit:
    IntOp $R4 $R4 + 1
  next_char:
    IntOp $R1 $R1 + 1
    Goto scan
  checked:
    StrCmp $R3 2 0 invalid
    StrCmp $R4 0 invalid
    IfFileExists "$EXEDIR\versions\$R0\Cove.exe" 0 invalid
    FileOpen $0 "$EXEDIR\versions\$R0\.cove-runtime" r
    IfErrors invalid
    FileRead $0 $1
    FileClose $0
    StrCmp $1 "cove-runtime-v1" 0 invalid
    ${GetParameters} $2
    SetOutPath "$EXEDIR\versions\$R0"
    ExecWait '"$EXEDIR\versions\$R0\Cove.exe" $2' $3
    SetErrorLevel $3
    Quit
  invalid:
    MessageBox MB_OK|MB_ICONSTOP "$(LaunchInvalid)"
    SetErrorLevel 2
SectionEnd
