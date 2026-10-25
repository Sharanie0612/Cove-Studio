; Product pages share the application's quiet white/blue visual language.
; Draw the existing embedded glyph; no stock wizard illustration or bitmap panels.
!include "nsDialogs.nsh"
Var StudioDialog
Var StudioDirectory
Var StudioLaunch
Var StudioTitleFont
Var StudioGlyph
Var StudioButtonFont
Var StudioButtonBitmap
Var StudioButtonWidth
Var StudioButtonHeight
Var StudioButtonColor
Var StudioButtonCaption
Var StudioProbePage

Function StudioGUIInit
  StrCpy $LANGUAGE $SetupLanguage
  SendMessage $HWNDPARENT ${WM_SETTEXT} 0 "STR:$(CoveText0)"
  SendMessage $mui.Button.Cancel ${WM_SETTEXT} 0 "STR:$(^CancelBtn)"
  SendMessage $mui.Button.Back ${WM_SETTEXT} 0 "STR:$(^BackBtn)"
  SetCtlColors $HWNDPARENT "${COVE_THEME_TEXT}" "${COVE_THEME_CHROME}"
  SetCtlColors $mui.Button.Next "FFFFFF" "${COVE_THEME_ACCENT}"
  SetCtlColors $mui.Button.Back "${COVE_THEME_TEXT}" "${COVE_THEME_SURFACE}"
  SetCtlColors $mui.Button.Cancel "${COVE_THEME_TEXT}" "${COVE_THEME_SURFACE}"
  GetDlgItem $0 $HWNDPARENT 1034
  SetCtlColors $0 "${COVE_THEME_MUTED}" "${COVE_THEME_CHROME}"
FunctionEnd

; Keep native Button semantics, keyboard access and accessible text. Only its
; bitmap material is drawn locally, using the exact app accent and shared font.
Function StudioStylePrimary
  Push $0
  Push $1
  Push $2
  Push $3
  Push $4
  Push $5
  Push $6
  Push $7
  Push $8
  Push $9
  System::Alloc 16
  Pop $0
  System::Call 'user32::GetClientRect(p $mui.Button.Next, p $0)'
  System::Call '*$0(i, i, i.r1, i.r2)'
  System::Call 'user32::GetDC(p $mui.Button.Next) p.r3'
  System::Call 'gdi32::CreateCompatibleDC(p $3) p.r4'
  System::Call 'gdi32::CreateCompatibleBitmap(p $3, i $1, i $2) p.r5'
  System::Call 'gdi32::SelectObject(p $4, p $5)'
  System::Call 'gdi32::CreateSolidBrush(i ${COVE_THEME_CHROME_BGR}) p.r7'
  System::Call 'user32::FillRect(p $4, p $0, p $7)'
  System::Call 'gdi32::DeleteObject(p $7)'
  System::Call 'gdi32::CreateSolidBrush(i ${COVE_THEME_ACCENT_BGR}) p.r7'
  System::Call 'gdi32::SelectObject(p $4, p $7)'
  System::Call 'gdi32::GetStockObject(i 8) p.r6'
  System::Call 'gdi32::SelectObject(p $4, p $6)'
  System::Call 'gdi32::GetDeviceCaps(p $3, i 88) i.r8'
  System::Call 'kernel32::MulDiv(i 16, i $8, i 96) i.r8'
  System::Call 'gdi32::RoundRect(p $4, i 0, i 0, i $1, i $2, i $8, i $8)'
  StrCmp $StudioButtonFont "" 0 +2
    CreateFont $StudioButtonFont "Cove Sans CJK" 10 600
  System::Call 'gdi32::SelectObject(p $4, p $StudioButtonFont)'
  System::Call 'gdi32::SetBkMode(p $4, i 1)'
  System::Call 'gdi32::SetTextColor(p $4, i 0xffffff)'
  System::Call 'user32::GetWindowTextW(p $mui.Button.Next, w.r9, i ${NSIS_MAX_STRLEN})'
  System::Call 'user32::DrawTextW(p $4, w r9, i -1, p $0, i 0x100025)'
  StrCpy $StudioButtonWidth $1
  StrCpy $StudioButtonHeight $2
  StrCpy $StudioButtonCaption $9
  IntOp $6 $2 / 2
  System::Call 'gdi32::GetPixel(p $4, i 8, i $6) i.r8'
  StrCpy $StudioButtonColor $8
  System::Call 'gdi32::DeleteDC(p $4)'
  System::Call 'gdi32::DeleteObject(p $7)'
  System::Call 'user32::ReleaseDC(p $mui.Button.Next, p $3)'
  System::Free $0
  System::Call 'uxtheme::SetWindowTheme(p $mui.Button.Next, w "", w "")'
  System::Call 'user32::GetWindowLongW(p $mui.Button.Next, i -16) i.r4'
  IntOp $4 $4 | 0x8080
  System::Call 'user32::SetWindowLongW(p $mui.Button.Next, i -16, i $4)'
  SendMessage $mui.Button.Next 0xF7 0 $5 $4
  StrCmp $StudioButtonBitmap "" +2
    System::Call 'gdi32::DeleteObject(p $StudioButtonBitmap)'
  StrCpy $StudioButtonBitmap $5
  Pop $9
  Pop $8
  Pop $7
  Pop $6
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
FunctionEnd

; Developer-only control self-check. It creates the real page and button, writes
; metadata to a fresh requested file, then exits before showing/installing anything.
Function StudioUIProbe
  StrCmp $TestMode "1" 0 ui_probe_done
  ReadEnvStr $1 "COVE_INSTALL_UI_REPORT"
  StrCmp $1 "" ui_probe_done
  IfFileExists "$1" ui_probe_fail
  System::Call 'shlwapi::PathIsRelativeW(w "$1") i.r2'
  StrCmp $2 "0" 0 ui_probe_fail
  ClearErrors
  FileOpen $2 "$1" w
  IfErrors ui_probe_fail
  FileWriteUTF16LE /BOM $2 ""
  FileClose $2
  WriteINIStr "$1" "UI" "Version" "${COVE_VERSION}"
  WriteINIStr "$1" "UI" "Language" "$LANGUAGE"
  WriteINIStr "$1" "UI" "Page" "$StudioProbePage"
  WriteINIStr "$1" "UI" "Width" "$StudioButtonWidth"
  WriteINIStr "$1" "UI" "Height" "$StudioButtonHeight"
  WriteINIStr "$1" "UI" "Color" "$StudioButtonColor"
  WriteINIStr "$1" "UI" "Caption" "$StudioButtonCaption"
  WriteINIStr "$1" "UI" "Bitmap" "$StudioButtonBitmap"
  WriteINIStr "$1" "UI" "Font" "$StudioButtonFont"
  System::Call 'user32::GetWindowTextW(p $HWNDPARENT, w.r3, i ${NSIS_MAX_STRLEN})'
  WriteINIStr "$1" "UI" "Title" "$3"
  IfErrors ui_probe_fail
  SetErrorLevel 0
  Quit
  ui_probe_fail:
    SetErrorLevel 87
    Quit
  ui_probe_done:
FunctionEnd

; FR_PRIVATE: fonts exist only in this installer process, never in Windows Fonts.
!macro StudioLoadFonts
  InitPluginsDir
  File /oname=$PLUGINSDIR\CoveSans-Regular.ttf "..\assets\fonts\notosanssc-400.ttf"
  File /oname=$PLUGINSDIR\CoveSans-SemiBold.ttf "..\assets\fonts\notosanssc-600.ttf"
  File /oname=$PLUGINSDIR\CoveSans-Latin.ttf "..\assets\fonts\inter-600.ttf"
  System::Call 'gdi32::AddFontResourceExW(w "$PLUGINSDIR\CoveSans-Regular.ttf", i 0x10, p 0) i.r0'
  System::Call 'gdi32::AddFontResourceExW(w "$PLUGINSDIR\CoveSans-SemiBold.ttf", i 0x10, p 0) i.r0'
  System::Call 'gdi32::AddFontResourceExW(w "$PLUGINSDIR\CoveSans-Latin.ttf", i 0x10, p 0) i.r0'
!macroend

!macro StudioUnloadFonts
  System::Call 'gdi32::RemoveFontResourceExW(w "$PLUGINSDIR\CoveSans-Regular.ttf", i 0x10, p 0)'
  System::Call 'gdi32::RemoveFontResourceExW(w "$PLUGINSDIR\CoveSans-SemiBold.ttf", i 0x10, p 0)'
  System::Call 'gdi32::RemoveFontResourceExW(w "$PLUGINSDIR\CoveSans-Latin.ttf", i 0x10, p 0)'
!macroend

!macro StudioBrand
  ${NSD_CreateIcon} 22u 18u 25u 27u ""
  Pop $0
  ${NSD_SetIconFromInstaller} $0 $StudioGlyph
  ${NSD_CreateLabel} 58u 17u 248u 28u "Cove Studio"
  Pop $0
  StrCmp $StudioTitleFont "" 0 +2
    CreateFont $StudioTitleFont "Cove Sans Latin" 20 600
  SendMessage $0 ${WM_SETFONT} $StudioTitleFont 0
  SetCtlColors $0 "${COVE_THEME_TEXT}" "${COVE_THEME_BACKGROUND}"
  ${NSD_CreateLabel} 59u 47u 245u 12u "${COVE_VERSION} Preview"
  Pop $0
  SetCtlColors $0 "${COVE_THEME_MUTED}" "${COVE_THEME_BACKGROUND}"
!macroend

Function StudioWelcomeCreate
  StrCpy $LANGUAGE $SetupLanguage
  StrCmp $TestMode "1" 0 studio_welcome_normal
  ReadEnvStr $1 "COVE_INSTALL_UI_REPORT"
  StrCmp $1 "" studio_welcome_normal
  ReadEnvStr $2 "COVE_INSTALL_UI_PAGE"
  StrCmp $2 "finish" 0 studio_welcome_normal
    Call StudioFinishCreate
    Abort
  studio_welcome_normal:
  nsDialogs::Create 1044
  Pop $StudioDialog
  StrCmp $StudioDialog error 0 +2
    Abort
  SetCtlColors $StudioDialog "${COVE_THEME_TEXT}" "${COVE_THEME_BACKGROUND}"
  Call muiPageLoadFullWindow
  !insertmacro StudioBrand
  ${NSD_CreateLabel} 22u 72u 290u 18u "$(CoveText17)"
  Pop $0
  SetCtlColors $0 "${COVE_THEME_TEXT}" "${COVE_THEME_BACKGROUND}"
  ${NSD_CreateLabel} 18u 100u 298u 83u ""
  Pop $0
  SetCtlColors $0 "${COVE_THEME_BORDER}" "${COVE_THEME_BORDER}"
  ${NSD_CreateLabel} 19u 101u 296u 81u ""
  Pop $0
  SetCtlColors $0 "${COVE_THEME_TEXT}" "${COVE_THEME_SURFACE}"
  ${NSD_CreateLabel} 30u 111u 274u 12u "$(CoveText18)"
  Pop $0
  SetCtlColors $0 "${COVE_THEME_MUTED}" "${COVE_THEME_SURFACE}"
  ${NSD_CreateDirRequest} 30u 128u 219u 22u "$INSTDIR"
  Pop $StudioDirectory
  ${NSD_CreateBrowseButton} 256u 128u 48u 22u "$(CoveText19)"
  Pop $0
  ${NSD_OnClick} $0 StudioBrowse
  ${NSD_CreateLabel} 30u 157u 274u 18u "$(CoveText20)"
  Pop $0
  SetCtlColors $0 "${COVE_THEME_MUTED}" "${COVE_THEME_SURFACE}"
  Call DetectWebView2
  StrCmp $WebViewVersion "" studio_missing_webview
    ${NSD_CreateLabel} 22u 195u 290u 16u "$(CoveText21)"
    Pop $0
    SetCtlColors $0 "${COVE_THEME_MUTED}" "${COVE_THEME_BACKGROUND}"
    Goto studio_show_welcome
  studio_missing_webview:
    ${NSD_CreateLabel} 22u 195u 205u 16u "$(CoveText22)"
    Pop $0
    SetCtlColors $0 "${COVE_THEME_MUTED}" "${COVE_THEME_BACKGROUND}"
    ${NSD_CreateLink} 238u 195u 74u 16u "$(CoveText23)"
    Pop $0
    SetCtlColors $0 "${COVE_THEME_ACCENT}" "${COVE_THEME_BACKGROUND}"
    ${NSD_OnClick} $0 StudioOpenWebView
  studio_show_welcome:
  SendMessage $mui.Button.Next ${WM_SETTEXT} 0 "STR:$(CoveText24)"
  Call StudioStylePrimary
  StrCpy $StudioProbePage "welcome"
  Call StudioUIProbe
  nsDialogs::Show
  Call muiPageUnloadFullWindow
FunctionEnd

Function StudioBrowse
  Pop $0
  ${NSD_GetText} $StudioDirectory $INSTDIR
  nsDialogs::SelectFolderDialog "$(CoveText25)" "$INSTDIR"
  Pop $0
  StrCmp $0 error +2
    ${NSD_SetText} $StudioDirectory $0
FunctionEnd

Function StudioOpenWebView
  Pop $0
  ExecShell "open" "https://developer.microsoft.com/microsoft-edge/webview2/#download"
FunctionEnd

Function StudioWelcomeLeave
  ${NSD_GetText} $StudioDirectory $INSTDIR
  StrCmp $INSTDIR "" studio_invalid_directory
  System::Call 'shlwapi::PathIsRelativeW(w "$INSTDIR") i.r0'
  StrCmp $0 "0" 0 studio_invalid_directory
  Call EnsureWebView2
  Return
  studio_invalid_directory:
    MessageBox MB_OK|MB_ICONINFORMATION "$(CoveText26)"
    Abort
FunctionEnd

Function StudioFinishCreate
  StrCpy $LANGUAGE $SetupLanguage
  nsDialogs::Create 1044
  Pop $StudioDialog
  SetCtlColors $StudioDialog "${COVE_THEME_TEXT}" "${COVE_THEME_BACKGROUND}"
  Call muiPageLoadFullWindow
  !insertmacro StudioBrand
  ${NSD_CreateLabel} 22u 82u 290u 18u "$(CoveText27)"
  Pop $0
  SetCtlColors $0 "${COVE_THEME_TEXT}" "${COVE_THEME_BACKGROUND}"
  ${NSD_CreateLabel} 22u 112u 290u 42u "$(CoveText28)"
  Pop $0
  SetCtlColors $0 "${COVE_THEME_MUTED}" "${COVE_THEME_BACKGROUND}"
  StrCpy $StudioLaunch ""
  StrCmp $TestMode "1" studio_finish_show
    ${NSD_CreateCheckbox} 22u 170u 290u 16u "$(CoveText29)"
    Pop $StudioLaunch
    SetCtlColors $StudioLaunch "${COVE_THEME_TEXT}" "${COVE_THEME_BACKGROUND}"
    ${NSD_Check} $StudioLaunch
  studio_finish_show:
  EnableWindow $mui.Button.Back 0
  EnableWindow $mui.Button.Cancel 0
  SendMessage $mui.Button.Next ${WM_SETTEXT} 0 "STR:$(CoveText30)"
  Call StudioStylePrimary
  StrCpy $StudioProbePage "finish"
  Call StudioUIProbe
  nsDialogs::Show
  Call muiPageUnloadFullWindow
FunctionEnd

Function StudioFinishLeave
  StrCmp $StudioLaunch "" studio_finish_done
  ${NSD_GetState} $StudioLaunch $0
  StrCmp $0 ${BST_CHECKED} 0 studio_finish_done
    Call LaunchCove
  studio_finish_done:
FunctionEnd

