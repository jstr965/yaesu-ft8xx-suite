; ============================================================
; Yaesu FT-8XX Suite by K3LH - NSIS Installer Script
; Professional Windows installer with wizard UI
; ============================================================

!define APP_NAME        "Yaesu FT-8XX Suite by K3LH"
!define APP_VERSION     "2.0.0"
!define APP_PUBLISHER   "K3LH"
!define APP_EXE         "FT817Suite.exe"
!define APP_DIR_NAME    "FT817Suite"
!define INSTALL_REG_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\FT817Suite"

; Output file
OutFile "FT817Suite_Setup_v2.0.0.exe"

; Default install directory
InstallDir "$PROGRAMFILES64\${APP_DIR_NAME}"

; Registry key for install location
InstallDirRegKey HKLM "${INSTALL_REG_KEY}" "InstallLocation"

; Request admin privileges for Program Files install
RequestExecutionLevel admin

; ─── Compression ─────────────────────────────────────────────────────────────
SetCompressor /SOLID lzma
SetCompressorDictSize 32

; ─── Modern UI ───────────────────────────────────────────────────────────────
!include "MUI2.nsh"
!include "FileFunc.nsh"

; UI Settings
!define MUI_ABORTWARNING
!define MUI_ICON          "assets\icon.ico"
!define MUI_UNICON        "assets\icon.ico"

; Welcome page
!define MUI_WELCOMEPAGE_TITLE    "Welcome to Yaesu FT-8XX Suite by K3LH v${APP_VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT     "This wizard will install Yaesu FT-8XX Suite by K3LH on your computer.$\r$\n$\r$\nYaesu FT-8XX Suite by K3LH is an integrated amateur radio control and digital modes application for the Yaesu FT-817/817ND.$\r$\n$\r$\nFeatures:$\r$\n  • CAT radio control (frequency, mode, PTT)$\r$\n  • FT8 / FT4 / JS8 / WSPR digital modes$\r$\n  • POTA, DX Cluster & RBN spotting$\r$\n  • QSO logging with ADIF export$\r$\n  • Dark, Light & Night display themes$\r$\n$\r$\nClick Next to continue."

; Finish page
!define MUI_FINISHPAGE_RUN          "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT     "Launch Yaesu FT-8XX Suite by K3LH now"
!define MUI_FINISHPAGE_SHOWREADME   ""
!define MUI_FINISHPAGE_TEXT         "Yaesu FT-8XX Suite by K3LH v${APP_VERSION} has been installed.$\r$\n$\r$\nA desktop shortcut and Start Menu entry have been created.$\r$\n$\r$\nNote: WSJT-X must be installed separately for digital modes.$\r$\nDownload from: physics.princeton.edu/pulsar/K1JT/wsjtx.html"

; ─── Pages ───────────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE      "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; ─── Language ────────────────────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "English"

; ─── Version Info ────────────────────────────────────────────────────────────
VIProductVersion                  "2.0.0.0"
VIAddVersionKey "ProductName"     "${APP_NAME}"
VIAddVersionKey "ProductVersion"  "${APP_VERSION}"
VIAddVersionKey "CompanyName"     "${APP_PUBLISHER}"
VIAddVersionKey "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey "FileVersion"     "${APP_VERSION}"
VIAddVersionKey "LegalCopyright"  "K3LH"

; ─── Installer Name / Branding ───────────────────────────────────────────────
Name        "${APP_NAME} v${APP_VERSION}"
BrandingText "${APP_NAME} v${APP_VERSION} — Amateur Radio Control"
Caption     "${APP_NAME} v${APP_VERSION} Setup"

; ─── Install Section ─────────────────────────────────────────────────────────
Section "Yaesu FT-8XX Suite by K3LH (required)" SecMain
    SectionIn RO   ; Cannot be deselected

    SetOutPath "$INSTDIR"

    ; --- Copy all application files ---
    File /r "dist\FT817Suite\*.*"

    ; --- Write uninstaller ---
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; --- Start Menu shortcut ---
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
                    "$INSTDIR\${APP_EXE}" "" \
                    "$INSTDIR\${APP_EXE}" 0 \
                    SW_SHOWNORMAL "" "${APP_NAME} v${APP_VERSION}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" \
                    "$INSTDIR\Uninstall.exe"

    ; --- Desktop shortcut ---
    CreateShortcut  "$DESKTOP\${APP_NAME}.lnk" \
                    "$INSTDIR\${APP_EXE}" "" \
                    "$INSTDIR\${APP_EXE}" 0 \
                    SW_SHOWNORMAL "" "${APP_NAME} v${APP_VERSION}"

    ; --- Registry: Add/Remove Programs entry ---
    WriteRegStr   HKLM "${INSTALL_REG_KEY}" "DisplayName"          "${APP_NAME}"
    WriteRegStr   HKLM "${INSTALL_REG_KEY}" "DisplayVersion"       "${APP_VERSION}"
    WriteRegStr   HKLM "${INSTALL_REG_KEY}" "Publisher"            "${APP_PUBLISHER}"
    WriteRegStr   HKLM "${INSTALL_REG_KEY}" "InstallLocation"      "$INSTDIR"
    WriteRegStr   HKLM "${INSTALL_REG_KEY}" "UninstallString"      "$INSTDIR\Uninstall.exe"
    WriteRegStr   HKLM "${INSTALL_REG_KEY}" "DisplayIcon"          "$INSTDIR\${APP_EXE}"
    WriteRegStr   HKLM "${INSTALL_REG_KEY}" "URLInfoAbout"         "https://github.com"
    WriteRegDWORD HKLM "${INSTALL_REG_KEY}" "NoModify"             1
    WriteRegDWORD HKLM "${INSTALL_REG_KEY}" "NoRepair"             1

    ; --- Calculate and store installed size ---
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "${INSTALL_REG_KEY}" "EstimatedSize" "$0"

SectionEnd

; ─── Uninstall Section ───────────────────────────────────────────────────────
Section "Uninstall"

    ; Remove shortcuts
    Delete "$DESKTOP\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"

    ; Remove install directory and all files
    RMDir /r "$INSTDIR"

    ; Remove registry key
    DeleteRegKey HKLM "${INSTALL_REG_KEY}"

    ; Note: user data files (qso_log.json, ft817_settings.json) are stored
    ; in the working directory, not in Program Files, so they are preserved.

SectionEnd

; ─── Functions ───────────────────────────────────────────────────────────────

; Check if app is running before install/uninstall
Function .onInit
    ; Check for existing installation
    ReadRegStr $0 HKLM "${INSTALL_REG_KEY}" "InstallLocation"
    ${If} $0 != ""
        MessageBox MB_YESNO|MB_ICONQUESTION \
            "Yaesu FT-8XX Suite by K3LH is already installed at:$\r$\n$0$\r$\n$\r$\nDo you want to overwrite the existing installation?" \
            IDYES continue
        Abort
        continue:
    ${EndIf}
FunctionEnd

Function un.onInit
    MessageBox MB_YESNO|MB_ICONQUESTION \
        "Are you sure you want to uninstall ${APP_NAME} v${APP_VERSION}?$\r$\n$\r$\nNote: Your QSO log and settings will NOT be deleted." \
        IDYES +2
    Abort
FunctionEnd
