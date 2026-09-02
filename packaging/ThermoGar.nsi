Unicode true
ManifestDPIAware true
RequestExecutionLevel admin
!include "LogicLib.nsh"
!include "x64.nsh"
SetCompressor /SOLID lzma
SetCompressorDictSize 64
CRCCheck force
SetDatablockOptimize on
SetDateSave off

!ifndef PRODUCT_DISPLAY_NAME
  !error "PRODUCT_DISPLAY_NAME is required"
!endif
!ifndef PRODUCT_DESCRIPTION
  !error "PRODUCT_DESCRIPTION is required"
!endif
!ifndef PRODUCT_DISPLAY_VERSION
  !error "PRODUCT_DISPLAY_VERSION is required"
!endif
!ifndef PRODUCT_VI_VERSION
  !error "PRODUCT_VI_VERSION is required"
!endif
!ifndef PRODUCT_ICON
  !error "PRODUCT_ICON is required"
!endif
!ifndef OUTPUT_FILE
  !error "OUTPUT_FILE is required"
!endif
!ifndef PAYLOAD_INCLUDE
  !error "PAYLOAD_INCLUDE is required"
!endif
!ifndef BUILD_HELPER
  !error "BUILD_HELPER is required"
!endif
!ifndef VERIFY_HELPER
  !error "VERIFY_HELPER is required"
!endif
!ifndef EXPECTED_PAYLOAD_MANIFEST_SHA256
  !error "EXPECTED_PAYLOAD_MANIFEST_SHA256 is required"
!endif
!ifndef EXPECTED_DISTRIBUTION_RECEIPT_SHA256
  !error "EXPECTED_DISTRIBUTION_RECEIPT_SHA256 is required"
!endif
!ifndef EXPECTED_PAYLOAD_ROWS
  !error "EXPECTED_PAYLOAD_ROWS is required"
!endif
!ifndef EXPECTED_PAYLOAD_BYTES
  !error "EXPECTED_PAYLOAD_BYTES is required"
!endif
!ifndef EXPECTED_PAYLOAD_ROOT_SHA256
  !error "EXPECTED_PAYLOAD_ROOT_SHA256 is required"
!endif
!ifndef EXPECTED_PRODUCT_VERSION_SHA256
  !error "EXPECTED_PRODUCT_VERSION_SHA256 is required"
!endif
!ifndef EXPECTED_ICON_SHA256
  !error "EXPECTED_ICON_SHA256 is required"
!endif
!ifndef PAYLOAD_MANIFEST_SOURCE
  !error "PAYLOAD_MANIFEST_SOURCE is required"
!endif
!ifndef DISTRIBUTION_RECEIPT_SOURCE
  !error "DISTRIBUTION_RECEIPT_SOURCE is required"
!endif

!define PRODUCT_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\ThermoGar"
!define CANONICAL_INSTALL_ROOT "$PROGRAMFILES64\ThermoGar"
!define CANONICAL_SHORTCUT_DIR "$SMPROGRAMS\ThermoGar"
!define CANONICAL_SHORTCUT "$SMPROGRAMS\ThermoGar\ThermoGar.lnk"

Name "${PRODUCT_DISPLAY_NAME}"
Caption "${PRODUCT_DISPLAY_NAME} ${PRODUCT_DISPLAY_VERSION}"
OutFile "${OUTPUT_FILE}"
InstallDir "${CANONICAL_INSTALL_ROOT}"
InstallDirRegKey HKLM "${PRODUCT_KEY}" "InstallLocation"
Icon "${PRODUCT_ICON}"
UninstallIcon "${PRODUCT_ICON}"
BrandingText "${PRODUCT_DISPLAY_NAME}"
VIProductVersion "${PRODUCT_VI_VERSION}"
VIAddVersionKey /LANG=0 "ProductName" "${PRODUCT_DISPLAY_NAME}"
VIAddVersionKey /LANG=0 "FileDescription" "${PRODUCT_DESCRIPTION}"
VIAddVersionKey /LANG=0 "FileVersion" "${PRODUCT_DISPLAY_VERSION}"
VIAddVersionKey /LANG=0 "ProductVersion" "${PRODUCT_DISPLAY_VERSION}"
ShowInstDetails show
ShowUninstDetails show

Var HadOldInstall
Var GuardExit
Var VerifyExit
Var TransactionState
Var OldDisplayVersion
Var FreshShortcutDirectoryOwned
Var FreshShortcutDirectoryHandle
Var FreshShortcutFileOwned
Var FreshShortcutFileHandle
Var FreshShortcutOwned
Var FreshRegistryKeyOwned
Var FreshRegistryKeyHandle
Var FreshClaimStatus

!macro AbortWithMessage Text
  MessageBox MB_ICONSTOP|MB_OK "${Text}" /SD IDOK
  SetErrorLevel 1
  Abort
!macroend

!macro WriteFreshRegString Name
  StrLen $6 $5
  IntOp $6 $6 + 1
  IntOp $6 $6 * 2
  System::Call 'advapi32::RegSetValueExW(p $FreshRegistryKeyHandle, w "${Name}", i 0, i 1, w r5, i r6) i .r4'
  ${If} $4 != 0
    Return
  ${EndIf}
!macroend

!macro WriteFreshRegDword Name
  StrCpy $5 1
  System::Call 'advapi32::RegSetValueExW(p $FreshRegistryKeyHandle, w "${Name}", i 0, i 4, *i r5, i 4) i .r4'
  ${If} $4 != 0
    Return
  ${EndIf}
!macroend

!macro UseSafeOutDir
  InitPluginsDir
  ClearErrors
  SetOutPath "$PLUGINSDIR"
  ${If} ${Errors}
    !insertmacro AbortWithMessage "ThermoGar could not establish its safe transaction working directory. No cleanup or activation was attempted."
  ${EndIf}
!macroend

!macro RunUpgradeGuard Root
  InitPluginsDir
  File /oname=$PLUGINSDIR\p4-build.ps1 "${BUILD_HELPER}"
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\p4-build.ps1" -Mode UpgradePreflight -InstallRoot "${Root}"'
  Pop $GuardExit
  Pop $0
  ${If} $GuardExit != 0
    DetailPrint "REFUSE_UPGRADE: all-session process state is active or uncertain"
    !insertmacro AbortWithMessage "ThermoGar is running or its process state cannot be verified. Close ThermoGar and retry. No process was stopped."
  ${EndIf}
!macroend

!macro RunInstalledVerifier Root AllowControl
  InitPluginsDir
  File /oname=$PLUGINSDIR\verify-installed.ps1 "${VERIFY_HELPER}"
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\verify-installed.ps1" -InstallRoot "${Root}" -ExpectedPayloadManifestSha256 "${EXPECTED_PAYLOAD_MANIFEST_SHA256}" -ExpectedDistributionEvidenceReceiptSha256 "${EXPECTED_DISTRIBUTION_RECEIPT_SHA256}" -ExpectedPayloadRowCount ${EXPECTED_PAYLOAD_ROWS} -ExpectedPayloadTotalBytes ${EXPECTED_PAYLOAD_BYTES} -ExpectedPayloadRootSha256 "${EXPECTED_PAYLOAD_ROOT_SHA256}" -ExpectedProductVersionSha256 "${EXPECTED_PRODUCT_VERSION_SHA256}" -ExpectedIconSha256 "${EXPECTED_ICON_SHA256}" ${AllowControl}'
  Pop $VerifyExit
  Pop $0
!macroend

Function AssertFreshMetadataAbsent
  ; Fresh install owns a create-new metadata scope: neither its shortcut
  ; directory nor its 64-bit HKLM uninstall key may already exist.
  IfFileExists "${CANONICAL_SHORTCUT_DIR}\." fresh_metadata_collision 0
  IfFileExists "${CANONICAL_SHORTCUT_DIR}\*.*" fresh_metadata_collision 0
  StrCpy $2 0
  StrCpy $3 0
  ; HKEY_LOCAL_MACHINE + KEY_READ + KEY_WOW64_64KEY.
  System::Call 'advapi32::RegOpenKeyExW(p 0x80000002, w "${PRODUCT_KEY}", i 0, i 0x20119, *p .r2) i .r3'
  ${If} $3 == 0
    System::Call 'advapi32::RegCloseKey(p r2) i .r4'
    ${If} $4 != 0
      Goto fresh_metadata_ambiguous
    ${EndIf}
    Goto fresh_metadata_collision
  ${ElseIf} $3 != 2
    Goto fresh_metadata_ambiguous
  ${EndIf}
  Return
  fresh_metadata_collision:
    !insertmacro AbortWithMessage "Existing ThermoGar shortcut or uninstall metadata was found. Fresh install refused without overwriting it."
  fresh_metadata_ambiguous:
    !insertmacro AbortWithMessage "ThermoGar shortcut or uninstall metadata could not be proven absent. Fresh install refused."
FunctionEnd

Function ClaimFreshMetadata
  ; Claim each fresh-install metadata scope atomically. A check alone is not
  ; ownership: NtCreateFile(FILE_CREATE|FILE_DIRECTORY_FILE) returns the exact
  ; new directory handle in the creation call, RegCreateKeyExW disposition
  ; proves a new key, and the later held-handle no-replace shortcut rename
  ; commits the run.
  StrCpy $FreshClaimStatus "AMBIGUOUS"
  StrCpy $2 0
  StrCpy $4 0
  StrCpy $5 0
  StrCpy $6 0
  StrCpy $7 0
  ; UNICODE_STRING is two USHORTs and a pointer. Rtl owns its Buffer until
  ; RtlFreeUnicodeString; System owns only the enclosing structure.
  System::Call '*(&i2 0, &i2 0, p 0) p .r5'
  ${If} $5 == 0
    Return
  ${EndIf}
  System::Call 'ntdll::RtlDosPathNameToNtPathName_U_WithStatus(w "${CANONICAL_SHORTCUT_DIR}", p r5, p 0, p 0) i .r4'
  ${If} $4 != 0
    System::Free $5
    Return
  ${EndIf}
  ; OBJECT_ATTRIBUTES (x86 NSIS: 24 bytes) and IO_STATUS_BLOCK are allocated
  ; by the System plug-in. DELETE|SYNCHRONIZE|FILE_READ_ATTRIBUTES|FILE_TRAVERSE,
  ; no FILE_SHARE_DELETE, FILE_CREATE, DIRECTORY|SYNCHRONOUS_IO_NONALERT.
  System::Call '*(i 24, p 0, p r5, i 0x40, p 0, p 0) p .r6'
  System::Call '*(p 0, p 0) p .r7'
  ${If} $6 == 0
    System::Call 'ntdll::RtlFreeUnicodeString(p r5)'
    System::Free $5
    Return
  ${EndIf}
  ${If} $7 == 0
    System::Free $6
    System::Call 'ntdll::RtlFreeUnicodeString(p r5)'
    System::Free $5
    Return
  ${EndIf}
  System::Call 'ntdll::NtCreateFile(*p .r2, i 0x001100A0, p r6, p r7, p 0, i 0x80, i 0x3, i 0x2, i 0x21, p 0, i 0) i .r4'
  System::Free $7
  System::Free $6
  System::Call 'ntdll::RtlFreeUnicodeString(p r5)'
  System::Free $5
  ${If} $4 != 0
    Return
  ${EndIf}
  StrCpy $FreshShortcutDirectoryHandle $2
  StrCpy $FreshShortcutDirectoryOwned "1"

  StrCpy $2 0
  StrCpy $3 0
  StrCpy $4 0
  ; DELETE | KEY_QUERY_VALUE | KEY_SET_VALUE | KEY_WOW64_64KEY;
  ; disposition 1 is CREATED_NEW.
  System::Call 'advapi32::RegCreateKeyExW(p 0x80000002, w "${PRODUCT_KEY}", i 0, p 0, i 0, i 0x00010103, p 0, *p .r2, *i .r3) i .r4'
  ${If} $4 != 0
    Return
  ${EndIf}
  ; Track every returned HKEY before any branch so a failed close can be
  ; retried by CleanupFreshMetadata.
  StrCpy $FreshRegistryKeyHandle $2
  ${If} $3 != 1
    System::Call 'advapi32::RegCloseKey(p $FreshRegistryKeyHandle) i .r4'
    ${If} $4 != 0
      Return
    ${EndIf}
    StrCpy $FreshRegistryKeyHandle "0"
    ${If} $3 == 2
      StrCpy $FreshClaimStatus "COLLISION"
    ${EndIf}
    Return
  ${EndIf}
  StrCpy $FreshRegistryKeyOwned "1"
  StrCpy $FreshClaimStatus "CLAIMED"
FunctionEnd

Function PublishFreshShortcut
  StrCpy $FreshClaimStatus "AMBIGUOUS"
  ClearErrors
  SetOutPath "$INSTDIR"
  ${If} ${Errors}
    Return
  ${EndIf}
  ClearErrors
  ; The temporary link is inside the atomically owned, handle-pinned shortcut
  ; directory, so publication is necessarily same-volume.
  CreateShortCut "${CANONICAL_SHORTCUT_DIR}\ThermoGar-fresh-install-txn.lnk" "$INSTDIR\runtime\pythonw.exe" '-I -B -X utf8 "$INSTDIR\launcher.pyw"' "$INSTDIR\assets\ThermoGar.ico" 0 SW_SHOWNORMAL "" "${PRODUCT_DESCRIPTION}"
  ${If} ${Errors}
    Return
  ${EndIf}

  ; Bind the exact normal, non-reparse temp link with DELETE and no sharing.
  ; Every later publish/rollback operation uses this retained object handle.
  System::Call 'kernel32::CreateFileW(w "${CANONICAL_SHORTCUT_DIR}\ThermoGar-fresh-install-txn.lnk", i 0x00110080, i 0, p 0, i 3, i 0x00200000, p 0) p .r2 ?e'
  Pop $4
  ${If} $2 == -1
    Return
  ${ElseIf} $2 == 0
    Return
  ${EndIf}
  StrCpy $FreshShortcutFileHandle $2
  System::Alloc 8
  Pop $5
  ${If} $5 == 0
    Return
  ${EndIf}
  System::Call 'kernel32::GetFileInformationByHandleEx(p $FreshShortcutFileHandle, i 9, p r5, i 8) i .r2 ?e'
  Pop $4
  ${If} $2 == 0
    System::Free $5
    Return
  ${EndIf}
  System::Call '*$5(i .r3, i .r4)'
  System::Free $5
  IntOp $3 $3 & 0x410
  ${If} $3 != 0
    Return
  ${EndIf}
  StrCpy $FreshShortcutFileOwned "1"

  ; x86 NSIS FILE_RENAME_INFORMATION: zero ReplaceIfExists+padding, held
  ; parent HANDLE, 26-byte leaf, and a terminal WCHAR. Native
  ; FileRenameInformation is class 10; this is the same no-replace mechanism
  ; already used by the pinned build helper.
  System::Alloc 40
  Pop $5
  ${If} $5 == 0
    Return
  ${EndIf}
  System::Call '*$5(i 0, p $FreshShortcutDirectoryHandle, i 26, &w14 "ThermoGar.lnk")'
  ; x86 IO_STATUS_BLOCK is two pointer-sized fields.
  System::Alloc 8
  Pop $6
  ${If} $6 == 0
    System::Free $5
    Return
  ${EndIf}
  System::Call '*$6(p 0, p 0)'
  System::Call 'ntdll::NtSetInformationFile(p $FreshShortcutFileHandle, p r6, p r5, i 40, i 10) i .r4'
  System::Free $6
  System::Free $5
  ${If} $4 != 0
    ; STATUS_OBJECT_NAME_COLLISION (0xC0000035), signed x86 value.
    ${If} $4 == -1073741771
      StrCpy $FreshClaimStatus "COLLISION"
    ${EndIf}
    Return
  ${EndIf}
  StrCpy $FreshShortcutOwned "1"
  StrCpy $FreshClaimStatus "OK"
FunctionEnd

Function WriteFreshRegistryMetadata
  StrCpy $FreshClaimStatus "AMBIGUOUS"
  StrCpy $5 "${PRODUCT_DISPLAY_NAME}"
  !insertmacro WriteFreshRegString "DisplayName"
  StrCpy $5 "${PRODUCT_DISPLAY_VERSION}"
  !insertmacro WriteFreshRegString "DisplayVersion"
  StrCpy $5 "$INSTDIR\assets\ThermoGar.ico"
  !insertmacro WriteFreshRegString "DisplayIcon"
  StrCpy $5 "$INSTDIR"
  !insertmacro WriteFreshRegString "InstallLocation"
  StrCpy $5 '"$INSTDIR\uninstall.exe"'
  !insertmacro WriteFreshRegString "UninstallString"
  StrCpy $5 '"$INSTDIR\uninstall.exe" /S'
  !insertmacro WriteFreshRegString "QuietUninstallString"
  !insertmacro WriteFreshRegDword "NoModify"
  !insertmacro WriteFreshRegDword "NoRepair"
  System::Call 'advapi32::RegFlushKey(p $FreshRegistryKeyHandle) i .r4'
  ${If} $4 != 0
    Return
  ${EndIf}
  ; Keep the owned HKEY open until either exact-object rollback or the final
  ; shortcut commit marker has succeeded.
  StrCpy $FreshClaimStatus "OK"
FunctionEnd

Function CleanupFreshMetadata
  StrCpy $FreshClaimStatus "OK"
  ; NtDeleteKey acts on the exact HKEY object returned by RegCreateKeyExW;
  ; rollback never resolves the mutable registry path again.
  ${If} $FreshRegistryKeyOwned == "1"
    ${If} $FreshRegistryKeyHandle == "0"
      StrCpy $FreshClaimStatus "CLEANUP_FAILED"
    ${Else}
      System::Call 'ntdll::NtDeleteKey(p $FreshRegistryKeyHandle) i .r4'
      ${If} $4 != 0
        StrCpy $FreshClaimStatus "CLEANUP_FAILED"
      ${Else}
        StrCpy $FreshRegistryKeyOwned "0"
        ; NtDeleteKey invalidates registry operations on the key, but the
        ; returned kernel handle must still be closed. Keep tracking it until
        ; an exact NtClose succeeds; the generic close block below retries a
        ; reported close failure without resolving the mutable key path.
        System::Call 'ntdll::NtClose(p $FreshRegistryKeyHandle) i .r4'
        ${If} $4 != 0
          StrCpy $FreshClaimStatus "CLEANUP_FAILED"
        ${Else}
          StrCpy $FreshRegistryKeyHandle "0"
        ${EndIf}
      ${EndIf}
    ${EndIf}
  ${EndIf}
  ${If} $FreshRegistryKeyHandle != "0"
    System::Call 'advapi32::RegCloseKey(p $FreshRegistryKeyHandle) i .r4'
    ${If} $4 != 0
      StrCpy $FreshClaimStatus "CLEANUP_FAILED"
    ${Else}
      StrCpy $FreshRegistryKeyHandle "0"
    ${EndIf}
  ${EndIf}
  ; Delete only the validated temp shortcut object owned by this run. An
  ; unvalidated or raced leaf is merely closed, making parent deletion fail
  ; closed while preserving the uncertain child.
  ${If} $FreshShortcutFileOwned == "1"
    ${If} $FreshShortcutFileHandle == "0"
      StrCpy $FreshClaimStatus "CLEANUP_FAILED"
    ${Else}
      System::Alloc 1
      Pop $5
      ${If} $5 == 0
        StrCpy $FreshClaimStatus "CLEANUP_FAILED"
      ${Else}
        System::Call '*$5(&i1 1)'
        System::Call 'kernel32::SetFileInformationByHandle(p $FreshShortcutFileHandle, i 4, p r5, i 1) i .r2 ?e'
        Pop $4
        System::Free $5
        ${If} $2 == 0
          StrCpy $FreshClaimStatus "CLEANUP_FAILED"
        ${Else}
          StrCpy $FreshShortcutFileOwned "0"
        ${EndIf}
      ${EndIf}
    ${EndIf}
  ${EndIf}
  ${If} $FreshShortcutFileHandle != "0"
    System::Call 'kernel32::CloseHandle(p $FreshShortcutFileHandle) i .r2'
    ${If} $2 == 0
      StrCpy $FreshClaimStatus "CLEANUP_FAILED"
    ${Else}
      StrCpy $FreshShortcutFileHandle "0"
    ${EndIf}
  ${EndIf}
  ; FileDispositionInfo is applied to the exact held directory object. It
  ; succeeds only when the directory is empty; a raced or uncertain child is
  ; retained fail-closed instead of being path-deleted.
  ${If} $FreshShortcutDirectoryOwned == "1"
    ${If} $FreshShortcutDirectoryHandle == "0"
      StrCpy $FreshClaimStatus "CLEANUP_FAILED"
    ${Else}
      System::Alloc 1
      Pop $5
      ${If} $5 == 0
        StrCpy $FreshClaimStatus "CLEANUP_FAILED"
      ${Else}
        System::Call '*$5(&i1 1)'
        System::Call 'kernel32::SetFileInformationByHandle(p $FreshShortcutDirectoryHandle, i 4, p r5, i 1) i .r2 ?e'
        Pop $4
        System::Free $5
        ${If} $2 == 0
          StrCpy $FreshClaimStatus "CLEANUP_FAILED"
        ${Else}
          StrCpy $FreshShortcutDirectoryOwned "0"
        ${EndIf}
      ${EndIf}
    ${EndIf}
  ${EndIf}
  ${If} $FreshShortcutDirectoryHandle != "0"
    System::Call 'kernel32::CloseHandle(p $FreshShortcutDirectoryHandle) i .r2'
    ${If} $2 == 0
      StrCpy $FreshClaimStatus "CLEANUP_FAILED"
    ${Else}
      StrCpy $FreshShortcutDirectoryHandle "0"
    ${EndIf}
  ${EndIf}
FunctionEnd

Function ReleaseCommittedFreshHandles
  ; The shortcut rename already committed a complete verified install. Handle
  ; release cannot trigger rollback; the process will close either handle if a
  ; close call itself reports failure.
  ${If} $FreshShortcutFileHandle != "0"
    System::Call 'kernel32::CloseHandle(p $FreshShortcutFileHandle) i .r2'
    ${If} $2 != 0
      StrCpy $FreshShortcutFileHandle "0"
      StrCpy $FreshShortcutFileOwned "0"
    ${Else}
      DetailPrint "Committed shortcut handle will be released at process exit."
    ${EndIf}
  ${EndIf}
  ${If} $FreshRegistryKeyHandle != "0"
    System::Call 'advapi32::RegCloseKey(p $FreshRegistryKeyHandle) i .r4'
    ${If} $4 == 0
      StrCpy $FreshRegistryKeyHandle "0"
    ${Else}
      DetailPrint "Committed uninstall-key handle will be released at process exit."
    ${EndIf}
  ${EndIf}
  ${If} $FreshShortcutDirectoryHandle != "0"
    System::Call 'kernel32::CloseHandle(p $FreshShortcutDirectoryHandle) i .r2'
    ${If} $2 != 0
      StrCpy $FreshShortcutDirectoryHandle "0"
    ${Else}
      DetailPrint "Committed shortcut-directory handle will be released at process exit."
    ${EndIf}
  ${EndIf}
FunctionEnd

Function .onInit
  SetRegView 64
  SetShellVarContext all
  ${IfNot} ${RunningX64}
    !insertmacro AbortWithMessage "ThermoGar requires 64-bit Windows."
  ${EndIf}
  StrCpy $INSTDIR "${CANONICAL_INSTALL_ROOT}"
  StrCpy $TransactionState "INIT"
  StrCpy $FreshShortcutDirectoryOwned "0"
  StrCpy $FreshShortcutDirectoryHandle "0"
  StrCpy $FreshShortcutFileOwned "0"
  StrCpy $FreshShortcutFileHandle "0"
  StrCpy $FreshShortcutOwned "0"
  StrCpy $FreshRegistryKeyOwned "0"
  StrCpy $FreshRegistryKeyHandle "0"
  StrCpy $FreshClaimStatus "UNCLAIMED"
FunctionEnd

Function un.onInit
  SetRegView 64
  SetShellVarContext all
  ${IfNot} ${RunningX64}
    !insertmacro AbortWithMessage "ThermoGar requires 64-bit Windows."
  ${EndIf}
  StrCpy $INSTDIR "${CANONICAL_INSTALL_ROOT}"
FunctionEnd

Section "ThermoGar" SEC_MAIN
  SectionIn RO
  SetRegView 64
  SetShellVarContext all
  StrCpy $INSTDIR "${CANONICAL_INSTALL_ROOT}"
  StrCpy $HadOldInstall "0"
  StrCpy $FreshShortcutDirectoryOwned "0"
  StrCpy $FreshShortcutDirectoryHandle "0"
  StrCpy $FreshShortcutFileOwned "0"
  StrCpy $FreshShortcutFileHandle "0"
  StrCpy $FreshShortcutOwned "0"
  StrCpy $FreshRegistryKeyOwned "0"
  StrCpy $FreshRegistryKeyHandle "0"
  StrCpy $FreshClaimStatus "UNCLAIMED"

  ; The all-session guard executes before any Program Files, shortcut, or HKLM mutation.
  !insertmacro RunUpgradeGuard "$INSTDIR"

  IfFileExists "$INSTDIR.new\." refuse_existing_new 0
  IfFileExists "$INSTDIR.new\*.*" refuse_existing_new 0
  IfFileExists "$INSTDIR.old\." refuse_existing_old 0
  IfFileExists "$INSTDIR.old\*.*" refuse_existing_old 0
  Goto transaction_paths_clear
  refuse_existing_new:
    !insertmacro AbortWithMessage "ThermoGar upgrade staging already exists; refusing to overwrite it."
  refuse_existing_old:
    !insertmacro AbortWithMessage "ThermoGar rollback directory already exists; refusing to overwrite it."
  transaction_paths_clear:

  IfFileExists "$INSTDIR\." has_old_install no_old_install
  has_old_install:
    StrCpy $HadOldInstall "1"
    !insertmacro RunInstalledVerifier "$INSTDIR" "-AllowInstallerControlFile"
    ${If} $VerifyExit != 0
      !insertmacro AbortWithMessage "The existing ThermoGar installation is not an exact verified payload; upgrade refused."
    ${EndIf}
    ReadRegStr $OldDisplayVersion HKLM "${PRODUCT_KEY}" "DisplayVersion"
    ${If} $OldDisplayVersion == ""
      !insertmacro AbortWithMessage "The existing ThermoGar registry identity is incomplete; upgrade refused."
    ${EndIf}
  no_old_install:
    ${If} $HadOldInstall == "0"
      Call AssertFreshMetadataAbsent
    ${EndIf}

  ; Generated include contains only ordinal manifest rows. It always writes beneath $INSTDIR.new.
  !include "${PAYLOAD_INCLUDE}"

  ; The two acyclic P3 control documents are intentionally self-excluded from payload rows,
  ; but are exact externally pinned installer inputs.
  SetOutPath "$INSTDIR.new\manifests"
  File /oname=payload-manifest.json "${PAYLOAD_MANIFEST_SOURCE}"
  File /oname=distribution-evidence-receipt.json "${DISTRIBUTION_RECEIPT_SOURCE}"
  ; Release the transaction tree before verification cleanup, rename, or removal.
  !insertmacro UseSafeOutDir

  !insertmacro RunInstalledVerifier "$INSTDIR.new" ""
  ${If} $VerifyExit != 0
    !insertmacro UseSafeOutDir
    ClearErrors
    RMDir /r "$INSTDIR.new"
    ${If} ${Errors}
      !insertmacro AbortWithMessage "The staged ThermoGar payload failed verification and its transaction directory could not be removed. Inspect Program Files before retrying."
    ${EndIf}
    !insertmacro AbortWithMessage "The staged ThermoGar payload failed verification; the current installation was not changed."
  ${EndIf}
  StrCpy $TransactionState "NEW_VERIFIED"

  ${If} $HadOldInstall == "1"
    !insertmacro UseSafeOutDir
    ClearErrors
    Rename "$INSTDIR" "$INSTDIR.old"
    ${If} ${Errors}
      !insertmacro UseSafeOutDir
      ClearErrors
      RMDir /r "$INSTDIR.new"
      ${If} ${Errors}
        !insertmacro AbortWithMessage "The current ThermoGar installation could not be preserved and the staged directory could not be removed. Inspect Program Files before retrying."
      ${EndIf}
      !insertmacro AbortWithMessage "The current ThermoGar installation could not be preserved; upgrade refused."
    ${EndIf}
    StrCpy $TransactionState "OLD_PRESERVED"
  ${EndIf}

  !insertmacro UseSafeOutDir
  ClearErrors
  Rename "$INSTDIR.new" "$INSTDIR"
  ${If} ${Errors}
    ${If} $HadOldInstall == "1"
      ClearErrors
      Rename "$INSTDIR.old" "$INSTDIR"
      ${If} ${Errors}
        !insertmacro AbortWithMessage "ThermoGar activation failed and the previous installation could not be restored. Both transaction directories were retained for inspection."
      ${EndIf}
    ${EndIf}
    !insertmacro UseSafeOutDir
    ClearErrors
    RMDir /r "$INSTDIR.new"
    ${If} ${Errors}
      !insertmacro AbortWithMessage "ThermoGar activation failed and the staged directory could not be removed. The previous installation was preserved."
    ${EndIf}
    !insertmacro AbortWithMessage "ThermoGar activation failed; the previous installation was restored."
  ${EndIf}
  StrCpy $TransactionState "PROMOTED"

  WriteUninstaller "$INSTDIR\uninstall.exe"
  ${If} ${Errors}
    Goto rollback_activation
  ${EndIf}

  !insertmacro RunInstalledVerifier "$INSTDIR" "-AllowInstallerControlFile"
  ${If} $VerifyExit != 0
    Goto rollback_activation
  ${EndIf}

  ${If} $HadOldInstall == "0"
    Call ClaimFreshMetadata
    ${If} $FreshClaimStatus != "CLAIMED"
      DetailPrint "Fresh metadata ownership could not be claimed without collision or uncertainty."
      Goto rollback_activation
    ${EndIf}
    Call WriteFreshRegistryMetadata
    ${If} $FreshClaimStatus != "OK"
      DetailPrint "Fresh uninstall metadata could not be written through its owned registry handle."
      Goto rollback_activation
    ${EndIf}
    Call PublishFreshShortcut
    ${If} $FreshClaimStatus != "OK"
      DetailPrint "Fresh shortcut publication collided or could not be proven no-replace."
      Goto rollback_activation
    ${EndIf}
    StrCpy $TransactionState "COMMITTED"
    Call ReleaseCommittedFreshHandles
    Goto install_done
  ${Else}
    ClearErrors
    CreateDirectory "${CANONICAL_SHORTCUT_DIR}"
    ${If} ${Errors}
      Goto rollback_activation
    ${EndIf}
    ClearErrors
    SetOutPath "$INSTDIR"
    ${If} ${Errors}
      Goto rollback_activation
    ${EndIf}
    ClearErrors
    CreateShortCut "${CANONICAL_SHORTCUT}" "$INSTDIR\runtime\pythonw.exe" '-I -B -X utf8 "$INSTDIR\launcher.pyw"' "$INSTDIR\assets\ThermoGar.ico" 0 SW_SHOWNORMAL "" "${PRODUCT_DESCRIPTION}"
    ${If} ${Errors}
      Goto rollback_activation
    ${EndIf}
    ClearErrors
    WriteRegStr HKLM "${PRODUCT_KEY}" "DisplayName" "${PRODUCT_DISPLAY_NAME}"
    WriteRegStr HKLM "${PRODUCT_KEY}" "DisplayVersion" "${PRODUCT_DISPLAY_VERSION}"
    WriteRegStr HKLM "${PRODUCT_KEY}" "DisplayIcon" "$INSTDIR\assets\ThermoGar.ico"
    WriteRegStr HKLM "${PRODUCT_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "${PRODUCT_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKLM "${PRODUCT_KEY}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
    WriteRegDWORD HKLM "${PRODUCT_KEY}" "NoModify" 1
    WriteRegDWORD HKLM "${PRODUCT_KEY}" "NoRepair" 1
    ${If} ${Errors}
      Goto rollback_activation
    ${EndIf}
  ${EndIf}

  ; Only the upgrade path reaches this common commit/old-root cleanup. Fresh
  ; installation committed at its final no-replace shortcut rename above.
  StrCpy $TransactionState "COMMITTED"
  ${If} $HadOldInstall == "1"
    !insertmacro UseSafeOutDir
    ClearErrors
    RMDir /r "$INSTDIR.old"
    ${If} ${Errors}
      MessageBox MB_ICONSTOP|MB_OK "ThermoGar activation is verified, but the preserved old directory could not be removed completely. No rollback or forced deletion was attempted. Inspect $INSTDIR.old before retrying." /SD IDOK
      SetErrorLevel 1
      Abort
    ${EndIf}
  ${EndIf}
  Goto install_done

  rollback_activation:
    ${If} $HadOldInstall == "0"
      !insertmacro UseSafeOutDir
      Call CleanupFreshMetadata
      ${If} $FreshClaimStatus != "OK"
        MessageBox MB_ICONSTOP|MB_OK "ThermoGar could not remove all metadata atomically claimed by this fresh-install run. No pre-existing metadata was overwritten; inspect the owned scope before retrying." /SD IDOK
        SetErrorLevel 1
        Abort
      ${EndIf}
    ${EndIf}
    !insertmacro UseSafeOutDir
    ClearErrors
    RMDir /r "$INSTDIR"
    ${If} ${Errors}
      MessageBox MB_ICONSTOP|MB_OK "ThermoGar could not remove the uncommitted new directory. The preserved old directory was not changed. Inspect Program Files before retrying." /SD IDOK
      SetErrorLevel 1
      Abort
    ${EndIf}
    ${If} $HadOldInstall == "1"
      Rename "$INSTDIR.old" "$INSTDIR"
      ${If} ${Errors}
        MessageBox MB_ICONSTOP|MB_OK "ThermoGar rollback could not restore the previous directory. Installation is stopped; do not retry before inspecting Program Files." /SD IDOK
        SetErrorLevel 1
        Abort
      ${EndIf}
      ClearErrors
      CreateDirectory "${CANONICAL_SHORTCUT_DIR}"
      SetOutPath "$INSTDIR"
      ${If} ${Errors}
        MessageBox MB_ICONSTOP|MB_OK "ThermoGar files were restored, but the shortcut working directory could not be established. No profile data was touched." /SD IDOK
        SetErrorLevel 1
        Abort
      ${EndIf}
      ClearErrors
      CreateShortCut "${CANONICAL_SHORTCUT}" "$INSTDIR\runtime\pythonw.exe" '-I -B -X utf8 "$INSTDIR\launcher.pyw"' "$INSTDIR\assets\ThermoGar.ico" 0 SW_SHOWNORMAL "" "${PRODUCT_DESCRIPTION}"
      WriteRegStr HKLM "${PRODUCT_KEY}" "DisplayName" "${PRODUCT_DISPLAY_NAME}"
      WriteRegStr HKLM "${PRODUCT_KEY}" "DisplayVersion" "$OldDisplayVersion"
      WriteRegStr HKLM "${PRODUCT_KEY}" "DisplayIcon" "$INSTDIR\assets\ThermoGar.ico"
      WriteRegStr HKLM "${PRODUCT_KEY}" "InstallLocation" "$INSTDIR"
      WriteRegStr HKLM "${PRODUCT_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
      WriteRegStr HKLM "${PRODUCT_KEY}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
      WriteRegDWORD HKLM "${PRODUCT_KEY}" "NoModify" 1
      WriteRegDWORD HKLM "${PRODUCT_KEY}" "NoRepair" 1
      ${If} ${Errors}
        MessageBox MB_ICONSTOP|MB_OK "ThermoGar files were rolled back, but shortcut or registry restoration failed. No process or profile data was touched." /SD IDOK
        SetErrorLevel 1
        Abort
      ${EndIf}
    ${EndIf}
    !insertmacro AbortWithMessage "ThermoGar activation failed; rollback completed."

  install_done:
SectionEnd

Section "Uninstall"
  SetRegView 64
  SetShellVarContext all
  StrCpy $INSTDIR "${CANONICAL_INSTALL_ROOT}"

  ; Uninstall also refuses on matching or uncertain all-session process state.
  !insertmacro RunUpgradeGuard "$INSTDIR"
  IfFileExists "$INSTDIR.new\." un_refuse_existing_new 0
  IfFileExists "$INSTDIR.new\*.*" un_refuse_existing_new 0
  IfFileExists "$INSTDIR.old\." un_refuse_existing_old 0
  IfFileExists "$INSTDIR.old\*.*" un_refuse_existing_old 0
  Goto un_transaction_paths_clear
  un_refuse_existing_new:
    !insertmacro AbortWithMessage "Unexpected ThermoGar staging directory exists; uninstall refused."
  un_refuse_existing_old:
    !insertmacro AbortWithMessage "Unexpected ThermoGar rollback directory exists; uninstall refused."
  un_transaction_paths_clear:

  !insertmacro RunInstalledVerifier "$INSTDIR" "-AllowInstallerControlFile"
  ${If} $VerifyExit != 0
    !insertmacro AbortWithMessage "Installed ThermoGar payload identity is uncertain; uninstall refused."
  ${EndIf}

  ; Keep the registered recovery path until the verified payload root is gone.
  !insertmacro UseSafeOutDir
  ClearErrors
  RMDir /r "$INSTDIR"
  ${If} ${Errors}
    !insertmacro AbortWithMessage "ThermoGar files could not be removed completely. LocalAppData was not touched."
  ${EndIf}
  ClearErrors
  Delete "${CANONICAL_SHORTCUT}"
  RMDir "${CANONICAL_SHORTCUT_DIR}"
  DeleteRegKey HKLM "${PRODUCT_KEY}"
  ${If} ${Errors}
    !insertmacro AbortWithMessage "ThermoGar files were removed, but the owned shortcut or uninstall metadata could not be removed completely. LocalAppData was not touched."
  ${EndIf}
  ; Deliberately no reference to $LOCALAPPDATA: all user state is preserved.
SectionEnd
