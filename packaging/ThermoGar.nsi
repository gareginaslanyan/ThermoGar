; ThermoGar Windows installer.
;
; Everything version-specific is passed in with /D by build_installer.ps1,
; which reads product-version.json. No receipts, no expected hashes: the
; installer copies the staged tree, drops one Start Menu shortcut and
; registers an uninstaller.
;
; Silent install/uninstall (/S) is supported and is what smoke_installed.ps1
; drives.

Unicode true
ManifestDPIAware true
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 64
CRCCheck force

!include "LogicLib.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"

!ifndef PRODUCT_DISPLAY_NAME
  !error "PRODUCT_DISPLAY_NAME is required"
!endif
!ifndef PRODUCT_DISPLAY_VERSION
  !error "PRODUCT_DISPLAY_VERSION is required"
!endif
!ifndef PRODUCT_VI_VERSION
  !error "PRODUCT_VI_VERSION is required"
!endif
!ifndef PRODUCT_PUBLISHER
  !error "PRODUCT_PUBLISHER is required"
!endif
!ifndef PRODUCT_DESCRIPTION
  !error "PRODUCT_DESCRIPTION is required"
!endif
!ifndef PRODUCT_ICON
  !error "PRODUCT_ICON is required"
!endif
!ifndef PAYLOAD_DIR
  !error "PAYLOAD_DIR is required"
!endif
!ifndef OUTPUT_FILE
  !error "OUTPUT_FILE is required"
!endif

!define PRODUCT_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\ThermoGar"
!define SHORTCUT_DIR "$SMPROGRAMS\ThermoGar"
!define SHORTCUT_LNK "$SMPROGRAMS\ThermoGar\ThermoGar.lnk"
; Present in every install; the uninstaller refuses to run without it, so a
; corrupted InstallLocation can never turn into a recursive delete of a
; directory we do not own.
!define INSTALL_MARKER "launcher.pyw"

Name "${PRODUCT_DISPLAY_NAME}"
Caption "${PRODUCT_DISPLAY_NAME} ${PRODUCT_DISPLAY_VERSION}"
OutFile "${OUTPUT_FILE}"
InstallDir "$PROGRAMFILES64\ThermoGar"
InstallDirRegKey HKLM "${PRODUCT_KEY}" "InstallLocation"
Icon "${PRODUCT_ICON}"
UninstallIcon "${PRODUCT_ICON}"
BrandingText "${PRODUCT_DISPLAY_NAME}"

VIProductVersion "${PRODUCT_VI_VERSION}"
VIAddVersionKey /LANG=0 "ProductName" "${PRODUCT_DISPLAY_NAME}"
VIAddVersionKey /LANG=0 "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey /LANG=0 "FileDescription" "${PRODUCT_DESCRIPTION}"
VIAddVersionKey /LANG=0 "FileVersion" "${PRODUCT_DISPLAY_VERSION}"
VIAddVersionKey /LANG=0 "ProductVersion" "${PRODUCT_DISPLAY_VERSION}"

ShowInstDetails show
ShowUninstDetails show

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Var PreviousInstall

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_OK|MB_ICONSTOP "ThermoGar requires 64-bit Windows."
    Abort
  ${EndIf}
  SetRegView 64
  ReadRegStr $PreviousInstall HKLM "${PRODUCT_KEY}" "InstallLocation"
FunctionEnd

Section "ThermoGar" SEC_MAIN
  SectionIn RO
  SetRegView 64
  SetShellVarContext all

  ; Replace the payload directories wholesale so a smaller new build cannot
  ; leave stale files behind. %LOCALAPPDATA%\ThermoGar is never touched.
  ${If} ${FileExists} "$INSTDIR\${INSTALL_MARKER}"
    DetailPrint "Removing previous payload from $INSTDIR"
    RMDir /r "$INSTDIR\runtime"
    RMDir /r "$INSTDIR\app"
    RMDir /r "$INSTDIR\configs"
    RMDir /r "$INSTDIR\databases"
    RMDir /r "$INSTDIR\manifests"
    RMDir /r "$INSTDIR\.streamlit"
  ${EndIf}

  SetOutPath "$INSTDIR"
  SetOverwrite on
  File /r "${PAYLOAD_DIR}\*.*"

  ${IfNot} ${FileExists} "$INSTDIR\${INSTALL_MARKER}"
    SetErrors
    MessageBox MB_OK|MB_ICONSTOP "Installation failed: launcher.pyw is missing." /SD IDOK
    Abort
  ${EndIf}
  ${IfNot} ${FileExists} "$INSTDIR\runtime\pythonw.exe"
    SetErrors
    MessageBox MB_OK|MB_ICONSTOP "Installation failed: bundled runtime is missing." /SD IDOK
    Abort
  ${EndIf}

  CreateDirectory "${SHORTCUT_DIR}"
  CreateShortcut "${SHORTCUT_LNK}" \
    "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\launcher.pyw"' \
    "$INSTDIR\ThermoGar.ico" 0 SW_SHOWNORMAL "" "${PRODUCT_DESCRIPTION}"

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegStr   HKLM "${PRODUCT_KEY}" "DisplayName"     "${PRODUCT_DISPLAY_NAME}"
  WriteRegStr   HKLM "${PRODUCT_KEY}" "DisplayVersion"  "${PRODUCT_DISPLAY_VERSION}"
  WriteRegStr   HKLM "${PRODUCT_KEY}" "Publisher"       "${PRODUCT_PUBLISHER}"
  WriteRegStr   HKLM "${PRODUCT_KEY}" "DisplayIcon"     "$INSTDIR\ThermoGar.ico"
  WriteRegStr   HKLM "${PRODUCT_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr   HKLM "${PRODUCT_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr   HKLM "${PRODUCT_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKLM "${PRODUCT_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${PRODUCT_KEY}" "NoRepair" 1
  WriteRegDWORD HKLM "${PRODUCT_KEY}" "EstimatedSize" $0
SectionEnd

Function un.onInit
  SetRegView 64
FunctionEnd

Section "Uninstall"
  SetRegView 64
  SetShellVarContext all

  ; Refuse to delete anything that is not recognisably a ThermoGar install.
  ${IfNot} ${FileExists} "$INSTDIR\${INSTALL_MARKER}"
    MessageBox MB_OK|MB_ICONSTOP "$INSTDIR does not look like a ThermoGar installation; nothing was removed." /SD IDOK
    Abort
  ${EndIf}

  Delete "${SHORTCUT_LNK}"
  RMDir "${SHORTCUT_DIR}"

  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\configs"
  RMDir /r "$INSTDIR\databases"
  RMDir /r "$INSTDIR\manifests"
  RMDir /r "$INSTDIR\.streamlit"
  Delete "$INSTDIR\launcher.pyw"
  Delete "$INSTDIR\stop.pyw"
  Delete "$INSTDIR\healthcheck.py"
  Delete "$INSTDIR\ThermoGar.ico"
  Delete "$INSTDIR\*.md"
  Delete "$INSTDIR\*.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  DeleteRegKey HKLM "${PRODUCT_KEY}"

  ; %LOCALAPPDATA%\ThermoGar holds user projects, the alloy library and run
  ; state. It is deliberately left in place.
SectionEnd
