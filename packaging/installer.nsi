Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "WordFunc.nsh"
!include "..\artifacts\installer-theme.nsh"
!ifndef COVE_VERSION
!error "Build with scripts/build_windows.py to supply COVE_VERSION"
!endif
!ifndef COVE_DISTDIR
!define COVE_DISTDIR "..\artifacts\desktop-${COVE_VERSION}\Cove"
!endif
Name "Cove Studio Preview"
Caption "$(CoveText0)"
BrandingText "Cove Studio ${COVE_VERSION} Preview"
ManifestDPIAware true
OutFile "..\artifacts\Cove-${COVE_VERSION}-setup.exe"
InstallDir "$LOCALAPPDATA\Programs\Cove"
InstallDirRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CovePreview" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "${COVE_VERSION}.0"
VIAddVersionKey "ProductName" "Cove Studio Preview"
VIAddVersionKey "FileDescription" "Cove Studio Desktop Installer"
VIAddVersionKey "FileVersion" "${COVE_VERSION}"
VIAddVersionKey "LegalCopyright" "Cove contributors"
Var TestMode
Var MaintenanceResult
Var MaintenanceOutput
Var DesktopLinks
Var MenuLinks
Var UpgradeMutex
Var ReusePayload
Var WebViewVersion
Var SetupLanguage
Var NoDesktopShortcut
Var SetupProgressFile
!define MUI_ICON "..\assets\cove.ico"
!define MUI_UNICON "..\assets\cove.ico"
!define MUI_TEXTCOLOR "${COVE_THEME_TEXT}"
!define MUI_BGCOLOR "${COVE_THEME_BACKGROUND}"
!define MUI_INSTFILESPAGE_COLORS "${COVE_THEME_TEXT} ${COVE_THEME_SURFACE}"
!define MUI_INSTFILESPAGE_PROGRESSBAR "colored"
!define MUI_CUSTOMFUNCTION_GUIINIT StudioGUIInit
!insertmacro MUI_PAGE_INIT
!insertmacro MUI_PAGE_FUNCTION_FULLWINDOW
!include "studio-ui.nsh"
Page custom StudioWelcomeCreate StudioWelcomeLeave
!define MUI_PAGE_HEADER_TEXT "$(CoveText1)"
!define MUI_PAGE_HEADER_SUBTEXT "$(CoveText2)"
!define MUI_LICENSEPAGE_TEXT_TOP "$(CoveText3)"
!define MUI_LICENSEPAGE_BUTTON "$(CoveText4)"
!define MUI_PAGE_CUSTOMFUNCTION_SHOW StudioStylePrimary
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!define MUI_PAGE_HEADER_TEXT "$(CoveText5)"
!define MUI_PAGE_HEADER_SUBTEXT "$(CoveText6)"
!define MUI_PAGE_CUSTOMFUNCTION_SHOW StudioStylePrimary
!insertmacro MUI_PAGE_INSTFILES
Page custom StudioFinishCreate StudioFinishLeave
!define MUI_PAGE_HEADER_TEXT "$(CoveText7)"
!define MUI_PAGE_HEADER_SUBTEXT "$(CoveText8)"
!define MUI_UNCONFIRMPAGE_TEXT_TOP "$(CoveText9)"
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"
!include "languages.nsh"
SetFont "Cove Sans CJK" 10

Function LaunchCove
  StrCmp $TestMode "1" done_launch
  # Installation is complete; release the guard before the new process starts.
  System::Call 'kernel32::CloseHandle(p $UpgradeMutex)'
  StrCpy $UpgradeMutex "0"
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\Cove.exe"'
  done_launch:
FunctionEnd

Function DetectWebView2
  StrCpy $WebViewVersion ""
  SetRegView 32
  ReadRegStr $0 HKLM "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${VersionCompare} "$0" "0.0.0.0" $1
  StrCmp $0 "" check_user
  StrCmp $1 "1" 0 check_user
    StrCpy $WebViewVersion $0
    Goto detected_webview
  check_user:
  ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${VersionCompare} "$0" "0.0.0.0" $1
  StrCmp $0 "" detected_webview
  StrCmp $1 "1" 0 detected_webview
    StrCpy $WebViewVersion $0
  detected_webview:
  # A test can force rejection, never fake a successful prerequisite check.
  StrCmp $TestMode "1" 0 end_webview_detection
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/SIMULATE_MISSING_WEBVIEW2" $1
  IfErrors end_webview_detection
    StrCpy $WebViewVersion ""
  end_webview_detection:
FunctionEnd

Function EnsureWebView2
  Call DetectWebView2
  StrCmp $WebViewVersion "" 0 webview_ready
  IfSilent missing_webview_silent
  MessageBox MB_YESNO|MB_ICONINFORMATION "$(CoveText10)" IDNO missing_webview_abort
    ExecShell "open" "https://developer.microsoft.com/microsoft-edge/webview2/#download"
  missing_webview_abort:
    Abort
  missing_webview_silent:
    SetErrorLevel 1603
    Quit
  webview_ready:
FunctionEnd

Function .onInit
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/LANGUAGE=" $1
  IfErrors language_choose
  StrCmp $1 "1033" language_apply
  StrCmp $1 "2052" 0 language_ready
  language_apply:
    StrCpy $LANGUAGE $1
    Goto language_ready
  language_choose:
    System::Call 'kernel32::GetUserDefaultUILanguage() i.r0'
    IntOp $0 $0 & 0x3ff
    StrCpy $LANGUAGE 1033
    StrCmp $0 4 0 +2
      StrCpy $LANGUAGE 2052
  language_ready:
  StrCpy $SetupLanguage $LANGUAGE
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/NO_DESKTOP_SHORTCUT" $1
  IfErrors +2
    StrCpy $NoDesktopShortcut "1"
  ReadEnvStr $SetupProgressFile "COVE_SETUP_PROGRESS"
  StrCmp $SetupProgressFile "" progress_checked
  System::Call 'shlwapi::PathIsRelativeW(w "$SetupProgressFile") i.r0'
  StrCmp $0 "0" 0 progress_reject
  ReadINIStr $0 "$SetupProgressFile" "Setup" "Owner"
  StrCmp $0 "cove-setup-progress-v1" 0 progress_reject
  ReadINIStr $0 "$SetupProgressFile" "Setup" "Version"
  StrCmp $0 "${COVE_VERSION}" progress_checked
  progress_reject:
    StrCpy $SetupProgressFile ""
  progress_checked:
  !insertmacro StudioLoadFonts
  SetShellVarContext current
  System::Call 'kernel32::CreateMutexW(p 0, i 1, w "Local\Cove.Workbench.Upgrade") p .r0 ?e'
  StrCpy $UpgradeMutex $0
  Pop $1
  StrCmp $UpgradeMutex "0" mutex_failed
  StrCmp $1 "183" mutex_failed mutex_ready
  mutex_failed:
    IfSilent +2
      MessageBox MB_OK|MB_ICONINFORMATION "$(CoveText11)"
    SetErrorLevel 1618
    Quit
  mutex_ready:
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/TESTMODE" $1
  IfErrors normal test
  test:
    StrCpy $TestMode "1"
  normal:
  IfSilent native_wizard
  Call DetectWebView2
  StrCmp $WebViewVersion "" native_wizard
  # Use the same HTML/CSS, fonts and composited native frame as the app. NSIS
  # remains the silent installation engine; no plugin or personal host is opened.
  InitPluginsDir
  SetOutPath "$PLUGINSDIR\CoveSetup"
  File /r "${COVE_DISTDIR}\*"
  System::Call 'kernel32::CloseHandle(p $UpgradeMutex)'
  StrCpy $UpgradeMutex "0"
  StrCmp $TestMode "1" setup_preview setup_regular
  setup_preview:
    ExecWait '"$PLUGINSDIR\CoveSetup\Cove.exe" --installer-ui --engine "$EXEPATH" --directory "$INSTDIR" --language "$SetupLanguage" --test-mode' $0
    Goto setup_returned
  setup_regular:
    ExecWait '"$PLUGINSDIR\CoveSetup\Cove.exe" --installer-ui --engine "$EXEPATH" --directory "$INSTDIR" --language "$SetupLanguage"' $0
  setup_returned:
    StrCmp $0 "0" setup_done
    StrCmp $0 "1602" setup_done
    # Dependency/renderer failure keeps the native prerequisite/recovery wizard.
    System::Call 'kernel32::CreateMutexW(p 0, i 1, w "Local\Cove.Workbench.Upgrade") p .r0 ?e'
    StrCpy $UpgradeMutex $0
    Pop $1
    StrCmp $UpgradeMutex "0" mutex_failed
    StrCmp $1 "183" mutex_failed native_wizard
  setup_done:
    SetErrorLevel $0
    Quit
  native_wizard:
FunctionEnd

!macro SetupProgress Phase
  StrCmp $SetupProgressFile "" +2
    WriteINIStr "$SetupProgressFile" "Setup" "Phase" "${Phase}"
!macroend

Function .onGUIEnd
  StrCmp $StudioButtonBitmap "" +2
    System::Call 'gdi32::DeleteObject(p $StudioButtonBitmap)'
  StrCmp $StudioButtonFont "" +2
    System::Call 'gdi32::DeleteObject(p $StudioButtonFont)'
  StrCmp $StudioTitleFont "" +2
    System::Call 'gdi32::DeleteObject(p $StudioTitleFont)'
  !insertmacro StudioUnloadFonts
  StrCmp $UpgradeMutex "0" +2
    System::Call 'kernel32::CloseHandle(p $UpgradeMutex)'
FunctionEnd

Function EnsureReadyToUpgrade
  check_again:
    StrCpy $ReusePayload "0"
    nsExec::ExecToStack /TIMEOUT=30000 '"$PLUGINSDIR\CoveMaintenance\Cove-worker.exe" --maintenance --install "$INSTDIR" --version "${COVE_VERSION}"'
    Pop $MaintenanceResult
    Pop $MaintenanceOutput
    StrCmp $MaintenanceResult "0" ready
    StrCmp $MaintenanceResult "30" reuse
    StrCmp $MaintenanceResult "10" busy failed_check
  busy:
    IfSilent silent_busy
    MessageBox MB_OKCANCEL|MB_ICONINFORMATION "$(CoveText12)" IDCANCEL cancel_upgrade
    nsExec::ExecToStack /TIMEOUT=30000 '"$PLUGINSDIR\CoveMaintenance\Cove-worker.exe" --maintenance --install "$INSTDIR" --version "${COVE_VERSION}" --request-close'
    Pop $MaintenanceResult
    Pop $MaintenanceOutput
    StrCmp $MaintenanceResult "0" ready
    StrCmp $MaintenanceResult "30" reuse
    MessageBox MB_RETRYCANCEL|MB_ICONINFORMATION "$(CoveText13)" IDRETRY check_again IDCANCEL cancel_upgrade
  failed_check:
    DetailPrint "Cove preflight: $MaintenanceOutput"
    IfSilent silent_failed
    MessageBox MB_OK|MB_ICONSTOP "$(CoveText14)"
  silent_failed:
    SetErrorLevel 5
    Quit
  silent_busy:
    SetErrorLevel 1618
    Quit
  cancel_upgrade:
    SetErrorLevel 1602
    Quit
  reuse:
    StrCpy $ReusePayload "1"
  ready:
FunctionEnd

Section "Cove"
  Call EnsureWebView2
  !insertmacro SetupProgress "preparing"
  # The preflight uses a temporary runtime so the old installation stays untouched.
  InitPluginsDir
  SetOutPath "$PLUGINSDIR\CoveMaintenance"
  File /r "${COVE_DISTDIR}\*"
  !insertmacro SetupProgress "checking"
  Call EnsureReadyToUpgrade
  !insertmacro SetupProgress "copying"
  # Keep every old runtime intact: external MCP clients may still be using it.
  # Identical reinstalls reuse existing files rather than overwrite mapped DLLs.
  StrCmp $ReusePayload "1" runtime_ready
  SetOutPath "$INSTDIR\versions\${COVE_VERSION}"
  ClearErrors
  File /r "${COVE_DISTDIR}\*"
  IfErrors runtime_failed
  Goto runtime_ready
  runtime_failed:
    IfSilent +2
      MessageBox MB_OK|MB_ICONSTOP "$(CoveText15)"
    SetErrorLevel 5
    Quit
  runtime_ready:
  FileOpen $0 "$INSTDIR\versions\${COVE_VERSION}\.cove-runtime" w
  FileWrite $0 "cove-runtime-v1"
  FileClose $0
  SetOutPath "$INSTDIR"
  ClearErrors
  File /oname=Cove.exe "${COVE_LAUNCHER}"
  IfErrors runtime_failed
  CreateDirectory "$INSTDIR\plugins"
  SetOutPath "$INSTDIR\plugins"
  File /oname=README.txt "..\docs\plugin-folder.txt"
  SetOutPath "$INSTDIR"
  FileOpen $0 "$INSTDIR\.cove-install" w
  FileWrite $0 "cove-preview-v1"
  FileClose $0
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  StrCmp $TestMode "1" test_install regular_install
  test_install:
    FileOpen $0 "$INSTDIR\.cove-test-install" w
    FileClose $0
    FileOpen $0 "$INSTDIR\.cove-test-language" w
    FileWrite $0 "$LANGUAGE"
    FileClose $0
    StrCpy $DesktopLinks "$INSTDIR\_shortcuts\Desktop"
    StrCpy $MenuLinks "$INSTDIR\_shortcuts\StartMenu"
    Goto write_links
  regular_install:
  StrCpy $DesktopLinks "$DESKTOP"
  StrCpy $MenuLinks "$SMPROGRAMS\Cove"
  write_links:
  CreateDirectory "$DesktopLinks"
  CreateDirectory "$MenuLinks"
  SetOutPath "$INSTDIR"
  ClearErrors
  StrCmp $NoDesktopShortcut "1" +2
    CreateShortCut "$DesktopLinks\Cove.lnk" "$INSTDIR\Cove.exe" "" "$INSTDIR\Cove.exe" 0
  CreateShortCut "$MenuLinks\Cove.lnk" "$INSTDIR\Cove.exe" "" "$INSTDIR\Cove.exe" 0
  CreateShortCut "$MenuLinks\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  IfErrors activation_failed
  !insertmacro SetupProgress "verifying"
  StrCmp $TestMode "1" activate_test
    nsExec::ExecToStack /TIMEOUT=30000 '"$INSTDIR\versions\${COVE_VERSION}\Cove-worker.exe" --maintenance --install "$INSTDIR" --version "${COVE_VERSION}" --activate --shortcut-dir "$DesktopLinks" --shortcut-dir "$MenuLinks" --shortcut-dir "$APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"'
    Goto activation_result
  activate_test:
    nsExec::ExecToStack /TIMEOUT=30000 '"$INSTDIR\versions\${COVE_VERSION}\Cove-worker.exe" --maintenance --install "$INSTDIR" --version "${COVE_VERSION}" --activate --shortcut-dir "$DesktopLinks" --shortcut-dir "$MenuLinks"'
  activation_result:
  Pop $MaintenanceResult
  Pop $MaintenanceOutput
  StrCmp $MaintenanceResult "0" activated activation_failed
  activation_failed:
    DetailPrint "Activation: $MaintenanceOutput"
    IfSilent +2
      MessageBox MB_OK|MB_ICONSTOP "$(CoveText31)"
    SetErrorLevel 5
    Quit
  activated:
  !insertmacro SetupProgress "finishing"
  StrCmp $TestMode "1" registry_done
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CovePreview" "DisplayName" "Cove Studio Preview"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CovePreview" "DisplayVersion" "${COVE_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CovePreview" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CovePreview" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CovePreview" "DisplayIcon" "$INSTDIR\Cove.exe"
  registry_done:
  # Shortcuts use the new executable's embedded icon; no root ICO accumulation.
  nsExec::ExecToStack /TIMEOUT=30000 '"$INSTDIR\versions\${COVE_VERSION}\Cove-worker.exe" --maintenance --install "$INSTDIR" --cleanup-icons'
  Pop $MaintenanceResult
  Pop $MaintenanceOutput
  DetailPrint "Legacy icon cleanup: $MaintenanceOutput"
  System::Call 'shell32::SHChangeNotify(l 0x08000000, i 0, p 0, p 0)'
SectionEnd

Function un.onInit
  !insertmacro MUI_UNGETLANGUAGE
  !insertmacro StudioLoadFonts
  SetShellVarContext current
  nsExec::ExecToStack /TIMEOUT=30000 '"$INSTDIR\versions\${COVE_VERSION}\Cove-worker.exe" --maintenance --install "$INSTDIR" --uninstall-check'
  Pop $MaintenanceResult
  Pop $MaintenanceOutput
  StrCmp $MaintenanceResult "0" uninstall_ready
  IfSilent +2
    MessageBox MB_OK|MB_ICONINFORMATION "$(CoveText16)"
  SetErrorLevel 1618
  Quit
  uninstall_ready:
FunctionEnd

Function un.onGUIEnd
  !insertmacro StudioUnloadFonts
FunctionEnd

Section "Uninstall"
  IfFileExists "$INSTDIR\.cove-install" 0 done_uninstall
  FileOpen $0 "$INSTDIR\.cove-install" r
  FileRead $0 $1
  FileClose $0
  StrCmp $1 "cove-preview-v1" 0 done_uninstall
  Delete "$INSTDIR\Cove.exe"
  Delete "$INSTDIR\Cove-worker.exe"
  RMDir /r "$INSTDIR\_internal"
  # Only delete runtimes carrying the installer's ownership marker.
  FindFirst $2 $3 "$INSTDIR\versions\*"
  runtime_cleanup:
    StrCmp $3 "" runtime_cleanup_done
    StrCmp $3 "." next_runtime
    StrCmp $3 ".." next_runtime
    IfFileExists "$INSTDIR\versions\$3\.cove-runtime" 0 next_runtime
    FileOpen $0 "$INSTDIR\versions\$3\.cove-runtime" r
    FileRead $0 $1
    FileClose $0
    StrCmp $1 "cove-runtime-v1" 0 next_runtime
    RMDir /r "$INSTDIR\versions\$3"
    next_runtime:
      FindNext $2 $3
      Goto runtime_cleanup
  runtime_cleanup_done:
    FindClose $2
    RMDir "$INSTDIR\versions"
  Delete "$INSTDIR\.cove-install"
  Delete "$INSTDIR\.cove-current"
  Delete "$INSTDIR\Uninstall.exe"
  IfFileExists "$INSTDIR\.cove-test-install" test_cleanup regular_cleanup
  test_cleanup:
    Delete "$INSTDIR\_shortcuts\Desktop\Cove.lnk"
    Delete "$INSTDIR\_shortcuts\StartMenu\Cove.lnk"
    Delete "$INSTDIR\_shortcuts\StartMenu\Uninstall.lnk"
    RMDir "$INSTDIR\_shortcuts\Desktop"
    RMDir "$INSTDIR\_shortcuts\StartMenu"
    RMDir "$INSTDIR\_shortcuts"
    Delete "$INSTDIR\.cove-test-install"
    Delete "$INSTDIR\.cove-test-language"
    RMDir "$INSTDIR"
    Goto done_uninstall
  regular_cleanup:
  RMDir "$INSTDIR"
  Delete "$DESKTOP\Cove.lnk"
  Delete "$SMPROGRAMS\Cove\Cove.lnk"
  Delete "$SMPROGRAMS\Cove\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Cove"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CovePreview"
  System::Call 'shell32::SHChangeNotify(l 0x08000000, i 0, p 0, p 0)'
  done_uninstall:
SectionEnd

