/*
    Lightroom Slider Control - AutoHotkey v2 Script
    Version: 2.1 (Fixed)

    Maps keyboard shortcuts to Lightroom Slider Control plugin commands.
    Safety Update: Only executes when Lightroom is in focus.

    INSTALLATION:
    1. Install AutoHotkey v2 from https://www.autohotkey.com/
    2. Install LightroomSliderControl.lrplugin in Lightroom
    3. Run this script
    4. Test: In Lightroom Develop module, press Ctrl+Alt+Shift+Win+1

    CONFIGURATION:
    - Adjust MENU_DELAY if menus aren't responding (increase for slower PCs)
    - Adjust PLUGIN_POS if you have multiple plugins installed
*/

#Requires AutoHotkey v2.0
#SingleInstance Force

; === CONFIGURATION ===
global MENU_DELAY := 200         ; Milliseconds between menu operations
global SUBMENU_DELAY := 120      ; Delay for submenu operations
global ITEM_DELAY := 40          ; Delay between arrow key presses
global PLUGIN_POS := 1           ; Position of Slider Control in Plug-in Extras (1 = first)
global ENABLE_HOTKEYS := 0       ; Set to 1 to enable scancode hotkeys

configPath := A_ScriptDir "\\lightroom-slider-control.ini"
try {
    MENU_DELAY := IniRead(configPath, "Settings", "MENU_DELAY", MENU_DELAY)
    SUBMENU_DELAY := IniRead(configPath, "Settings", "SUBMENU_DELAY", SUBMENU_DELAY)
    ITEM_DELAY := IniRead(configPath, "Settings", "ITEM_DELAY", ITEM_DELAY)
    PLUGIN_POS := IniRead(configPath, "Settings", "PLUGIN_POS", PLUGIN_POS)
    IPC_DIR := IniRead(configPath, "Settings", "IPC_DIR", A_Temp "\\lrslider_ipc")
    ENABLE_HOTKEYS := IniRead(configPath, "Settings", "ENABLE_HOTKEYS", ENABLE_HOTKEYS)
}

if !DirExist(IPC_DIR) {
    DirCreate(IPC_DIR)
}

SetTimer(CheckIpcQueue, 20)

; === ONLY ACTIVE IN LIGHTROOM ===
#HotIf WinActive("ahk_exe lightroom.exe") or WinActive("ahk_exe Lightroom.exe")

; === MENU NAVIGATION FUNCTION ===
TriggerPluginCommand(cmdPos) {
    ; FINAL SAFETY CHECK: Ensure we are still in Lightroom before typing
    if !WinActive("ahk_exe lightroom.exe") && !WinActive("ahk_exe Lightroom.exe")
        return

    BlockInput(true) ; Prevent user interference during macro
    try {
        ; Close any open menus first
        Send("{Escape}")
        Sleep(50)

        ; Open File menu
        Send("!f")
        Sleep(MENU_DELAY)

        ; Navigate to Plug-in Extras
        ; Try 'u' for Plug-in Extras (common in English LR Classic) or 'g'
        ; If 'g' is failing for you, we can try navigating down.
        Send("u")
        Sleep(SUBMENU_DELAY)

        ; Navigate to Slider Control (assuming it's the first plugin)
        if (PLUGIN_POS > 1) {
            Loop PLUGIN_POS - 1 {
                Send("{Down}")
                Sleep(ITEM_DELAY)
            }
        }

        ; Enter Slider Control submenu
        Send("{Right}")
        Sleep(SUBMENU_DELAY)

        ; Navigate to the specific command
        if (cmdPos > 1) {
            Loop cmdPos - 1 {
                Send("{Down}")
                Sleep(ITEM_DELAY)
            }
        }

        ; Execute
        Send("{Enter}")
    } finally {
        BlockInput(false)
    }
}

CheckIpcQueue() {
    global IPC_DIR

    ; Loop through all pending command files
    Loop Files, IPC_DIR "\\*.txt" {
        file := A_LoopFileFullPath
        try {
            ; Read the command
            cmd := Trim(FileRead(file))

            ; CRITICAL: Delete file immediately to prevent "queue explosion" later
            FileDelete(file)

            ; CRITICAL: Only execute if Lightroom is actually focused
            if (cmd && (WinActive("ahk_exe lightroom.exe") || WinActive("ahk_exe Lightroom.exe"))) {
                cmdPos := Integer(cmd)
                if cmdPos > 0 {
                    TriggerPluginCommand(cmdPos)
                }
            }
        } catch as err {
            ; If we can't read/delete, try deleting again to avoid stuck files
            try FileDelete(file)
        }
    }
}

; === HOTKEY DEFINITIONS (optional) ===
if (ENABLE_HOTKEYS) {
    ; Pattern: Number-row scancodes + modifier groups (low-conflict)
    ; 1-12:  Ctrl+Alt+Shift+Win + 1..= (sc002..sc00D)
    ; 13-24: Ctrl+Alt+Win + 1..=
    ; 25-36: Ctrl+Shift+Win + 1..=
    ; 37-48: Alt+Shift+Win + 1..=
    ; 49-60: Ctrl+Win + 1..=

    ; BASIC TONE (positions 1-12)
    ^!+#sc002::TriggerPluginCommand(1)   ; Exposure +
    ^!+#sc003::TriggerPluginCommand(2)   ; Exposure -
    ^!+#sc004::TriggerPluginCommand(3)   ; Contrast +
    ^!+#sc005::TriggerPluginCommand(4)   ; Contrast -
    ^!+#sc006::TriggerPluginCommand(5)   ; Highlights +
    ^!+#sc007::TriggerPluginCommand(6)   ; Highlights -
    ^!+#sc008::TriggerPluginCommand(7)   ; Shadows +
    ^!+#sc009::TriggerPluginCommand(8)   ; Shadows -
    ^!+#sc00A::TriggerPluginCommand(9)   ; Whites +
    ^!+#sc00B::TriggerPluginCommand(10)  ; Whites -
    ^!+#sc00C::TriggerPluginCommand(11)  ; Blacks +
    ^!+#sc00D::TriggerPluginCommand(12)  ; Blacks -

    ; WHITE BALANCE (positions 13-16)
    ^!#sc002::TriggerPluginCommand(13)  ; Temperature + (warmer)
    ^!#sc003::TriggerPluginCommand(14)  ; Temperature - (cooler)
    ^!#sc004::TriggerPluginCommand(15)  ; Tint + (magenta)
    ^!#sc005::TriggerPluginCommand(16)  ; Tint - (green)

    ; PRESENCE (positions 17-26)
    ^!#sc006::TriggerPluginCommand(17)  ; Texture +
    ^!#sc007::TriggerPluginCommand(18)  ; Texture -
    ^!#sc008::TriggerPluginCommand(19)  ; Clarity +
    ^!#sc009::TriggerPluginCommand(20)  ; Clarity -
    ^!#sc00A::TriggerPluginCommand(21)  ; Dehaze +
    ^!#sc00B::TriggerPluginCommand(22)  ; Dehaze -
    ^!#sc00C::TriggerPluginCommand(23)  ; Vibrance +
    ^!#sc00D::TriggerPluginCommand(24)  ; Vibrance -
    ^+#sc002::TriggerPluginCommand(25)  ; Saturation +
    ^+#sc003::TriggerPluginCommand(26)  ; Saturation -

    ; EFFECTS (positions 27-34)
    ^+#sc004::TriggerPluginCommand(27)  ; Vignette +
    ^+#sc005::TriggerPluginCommand(28)  ; Vignette -
    ^+#sc006::TriggerPluginCommand(29)  ; Grain +
    ^+#sc007::TriggerPluginCommand(30)  ; Grain -
    ^+#sc008::TriggerPluginCommand(31)  ; GrainSize +
    ^+#sc009::TriggerPluginCommand(32)  ; GrainSize -
    ^+#sc00A::TriggerPluginCommand(33)  ; GrainRough +
    ^+#sc00B::TriggerPluginCommand(34)  ; GrainRough -

    ; HSL RED (positions 35-40)
    ^+#sc00C::TriggerPluginCommand(35)  ; Red Hue +
    ^+#sc00D::TriggerPluginCommand(36)  ; Red Hue -
    !+#sc002::TriggerPluginCommand(37) ; Red Sat +
    !+#sc003::TriggerPluginCommand(38) ; Red Sat -
    !+#sc004::TriggerPluginCommand(39) ; Red Lum +
    !+#sc005::TriggerPluginCommand(40) ; Red Lum -

    ; HSL ORANGE (positions 41-46)
    !+#sc006::TriggerPluginCommand(41) ; Orange Hue +
    !+#sc007::TriggerPluginCommand(42) ; Orange Hue -
    !+#sc008::TriggerPluginCommand(43) ; Orange Sat +
    !+#sc009::TriggerPluginCommand(44) ; Orange Sat -
    !+#sc00A::TriggerPluginCommand(45) ; Orange Lum +
    !+#sc00B::TriggerPluginCommand(46) ; Orange Lum -

    ; HSL YELLOW (positions 47-52)
    !+#sc00C::TriggerPluginCommand(47) ; Yellow Hue +
    !+#sc00D::TriggerPluginCommand(48) ; Yellow Hue -
    ^#sc002::TriggerPluginCommand(49)   ; Yellow Sat +
    ^#sc003::TriggerPluginCommand(50)   ; Yellow Sat -
    ^#sc004::TriggerPluginCommand(51)   ; Yellow Lum +
    ^#sc005::TriggerPluginCommand(52)   ; Yellow Lum -
}

#HotIf

; === SYSTEM TRAY ===
A_TrayMenu.Delete()
A_TrayMenu.Add("LR Slider Control v2.1", (*) => {})
A_TrayMenu.Disable("LR Slider Control v2.1")
A_TrayMenu.Add()
A_TrayMenu.Add("Reload", (*) => Reload())
A_TrayMenu.Add("Exit", (*) => ExitApp())

TrayTip("LR Slider Control", "Active and Safe (LR Only)", 1)

; === EMERGENCY STOP ===
; Press Ctrl + Escape to immediately kill the script if it acts up
^Esc::
{
    SoundBeep(1000, 200)
    ExitApp
}
