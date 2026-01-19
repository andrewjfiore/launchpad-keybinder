/*
    Lightroom Slider Control - AutoHotkey v2 Script
    Version: 2.0
    
    Maps keyboard shortcuts to Lightroom Slider Control plugin commands.
    
    INSTALLATION:
    1. Install AutoHotkey v2 from https://www.autohotkey.com/
    2. Install LightroomSliderControl.lrplugin in Lightroom
    3. Run this script
    4. Test: In Lightroom Develop module, press Ctrl+Alt+F1
    
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

configPath := A_ScriptDir "\\lightroom-slider-control.ini"
MENU_DELAY := IniRead(configPath, "Settings", "MENU_DELAY", MENU_DELAY)
SUBMENU_DELAY := IniRead(configPath, "Settings", "SUBMENU_DELAY", SUBMENU_DELAY)
ITEM_DELAY := IniRead(configPath, "Settings", "ITEM_DELAY", ITEM_DELAY)
PLUGIN_POS := IniRead(configPath, "Settings", "PLUGIN_POS", PLUGIN_POS)

; === ONLY ACTIVE IN LIGHTROOM ===
#HotIf WinActive("ahk_exe lightroom.exe") or WinActive("ahk_exe Lightroom.exe")

; === MENU NAVIGATION FUNCTION ===
TriggerPluginCommand(cmdPos) {
    /*
    Navigate: File > Plug-in Extras > Slider Control > Command
    
    Steps:
    1. Open File menu (Alt+F)
    2. Open Plug-in Extras submenu (press 'g' or navigate)
    3. Enter Slider Control submenu
    4. Navigate to command position
    5. Press Enter
    */
    
    ; Close any open menus first
    Send("{Escape}")
    Sleep(50)
    
    ; Open File menu
    Send("!f")
    Sleep(MENU_DELAY)
    
    ; Navigate to Plug-in Extras
    ; In English Lightroom, it's near the bottom of File menu
    ; Use 'g' accelerator key if available, otherwise navigate
    Send("g")  ; Try accelerator first
    Sleep(SUBMENU_DELAY)
    
    ; If accelerator didn't work, the menu might still be on File
    ; Navigate down to find Plug-in Extras (typically position varies)
    ; Uncomment below if 'g' accelerator doesn't work:
    ; Loop 15 {
    ;     Send("{Down}")
    ;     Sleep(ITEM_DELAY)
    ; }
    ; Send("{Right}")
    ; Sleep(SUBMENU_DELAY)
    
    ; Now we should be in Plug-in Extras submenu
    ; Navigate to Slider Control
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
}

; === HOTKEY DEFINITIONS ===
; Pattern: F1-F12 + modifier groups (low-conflict)
; 1-12:  Ctrl+Alt+F1..F12
; 13-24: Ctrl+Shift+F1..F12
; 25-36: Alt+Shift+F1..F12
; 37-48: Ctrl+Alt+Shift+F1..F12
; 49-60: Ctrl+F1..F12

; BASIC TONE (positions 1-12)
^!F1::TriggerPluginCommand(1)   ; Exposure +
^!F2::TriggerPluginCommand(2)   ; Exposure -
^!F3::TriggerPluginCommand(3)   ; Contrast +
^!F4::TriggerPluginCommand(4)   ; Contrast -
^!F5::TriggerPluginCommand(5)   ; Highlights +
^!F6::TriggerPluginCommand(6)   ; Highlights -
^!F7::TriggerPluginCommand(7)   ; Shadows +
^!F8::TriggerPluginCommand(8)   ; Shadows -
^!F9::TriggerPluginCommand(9)   ; Whites +
^!F10::TriggerPluginCommand(10)  ; Whites -
^!F11::TriggerPluginCommand(11)  ; Blacks +
^!F12::TriggerPluginCommand(12)  ; Blacks -

; WHITE BALANCE (positions 13-16)
^+F1::TriggerPluginCommand(13)  ; Temperature + (warmer)
^+F2::TriggerPluginCommand(14)  ; Temperature - (cooler)
^+F3::TriggerPluginCommand(15)  ; Tint + (magenta)
^+F4::TriggerPluginCommand(16)  ; Tint - (green)

; PRESENCE (positions 17-26)
^+F5::TriggerPluginCommand(17)  ; Texture +
^+F6::TriggerPluginCommand(18)  ; Texture -
^+F7::TriggerPluginCommand(19)  ; Clarity +
^+F8::TriggerPluginCommand(20)  ; Clarity -
^+F9::TriggerPluginCommand(21)  ; Dehaze +
^+F10::TriggerPluginCommand(22)  ; Dehaze -
^+F11::TriggerPluginCommand(23)  ; Vibrance +
^+F12::TriggerPluginCommand(24)  ; Vibrance -
!+F1::TriggerPluginCommand(25)  ; Saturation +
!+F2::TriggerPluginCommand(26)  ; Saturation -

; EFFECTS (positions 27-34)
!+F3::TriggerPluginCommand(27)  ; Vignette +
!+F4::TriggerPluginCommand(28)  ; Vignette -
!+F5::TriggerPluginCommand(29)  ; Grain +
!+F6::TriggerPluginCommand(30)  ; Grain -
!+F7::TriggerPluginCommand(31)  ; GrainSize +
!+F8::TriggerPluginCommand(32)  ; GrainSize -
!+F9::TriggerPluginCommand(33)  ; GrainRough +
!+F10::TriggerPluginCommand(34)  ; GrainRough -

; HSL RED (positions 35-40)
!+F11::TriggerPluginCommand(35)  ; Red Hue +
!+F12::TriggerPluginCommand(36)  ; Red Hue -
^!+F1::TriggerPluginCommand(37) ; Red Sat +
^!+F2::TriggerPluginCommand(38) ; Red Sat -
^!+F3::TriggerPluginCommand(39) ; Red Lum +
^!+F4::TriggerPluginCommand(40) ; Red Lum -

; HSL ORANGE (positions 41-46)
^!+F5::TriggerPluginCommand(41) ; Orange Hue +
^!+F6::TriggerPluginCommand(42) ; Orange Hue -
^!+F7::TriggerPluginCommand(43) ; Orange Sat +
^!+F8::TriggerPluginCommand(44) ; Orange Sat -
^!+F9::TriggerPluginCommand(45) ; Orange Lum +
^!+F10::TriggerPluginCommand(46) ; Orange Lum -

; HSL YELLOW (positions 47-52)
^!+F11::TriggerPluginCommand(47) ; Yellow Hue +
^!+F12::TriggerPluginCommand(48) ; Yellow Hue -
^F1::TriggerPluginCommand(49)   ; Yellow Sat +
^F2::TriggerPluginCommand(50)   ; Yellow Sat -
^F3::TriggerPluginCommand(51)   ; Yellow Lum +
^F4::TriggerPluginCommand(52)   ; Yellow Lum -

; CROP (positions 53-55)
^F5::TriggerPluginCommand(53)   ; Straighten +
^F6::TriggerPluginCommand(54)   ; Straighten -
^F7::TriggerPluginCommand(55)   ; CropAngle Reset

; RESETS (positions 56-60)
^F8::TriggerPluginCommand(56)   ; Reset Exposure
^F9::TriggerPluginCommand(57)   ; Reset White Balance
^F10::TriggerPluginCommand(58)   ; Reset Tone
^F11::TriggerPluginCommand(59)   ; Reset Presence
^F12::TriggerPluginCommand(60)   ; Reset Effects

#HotIf

; === SYSTEM TRAY ===
A_TrayMenu.Delete()
A_TrayMenu.Add("LR Slider Control v2.0", (*) => {})
A_TrayMenu.Disable("LR Slider Control v2.0")
A_TrayMenu.Add()
A_TrayMenu.Add("Hotkey Reference", ShowHelp)
A_TrayMenu.Add()
A_TrayMenu.Add("Menu Delay + (slower)", (*) => AdjustDelay(25))
A_TrayMenu.Add("Menu Delay - (faster)", (*) => AdjustDelay(-25))
A_TrayMenu.Add()
A_TrayMenu.Add("Reload", (*) => Reload())
A_TrayMenu.Add("Exit", (*) => ExitApp())

AdjustDelay(delta) {
    global MENU_DELAY
    MENU_DELAY := Max(50, MENU_DELAY + delta)
    TrayTip("Delay: " . MENU_DELAY . "ms")
}

ShowHelp(*) {
    help := "
    (
LIGHTROOM SLIDER CONTROL HOTKEYS
================================

All hotkeys use function keys (F1-F12) with modifiers.
These combinations are not bound to Lightroom by default.

GROUPS:
  Ctrl+Alt+F1..F12   = Commands 01-12 (Basic Tone)
  Ctrl+Shift+F1..F12 = Commands 13-24 (WB + Presence)
  Alt+Shift+F1..F12  = Commands 25-36 (Saturation + Effects + Red Hue)
  Ctrl+Alt+Shift+F1..F12 = Commands 37-48 (Red Sat/Lum, Orange, Yellow Hue)
  Ctrl+F1..F12       = Commands 49-60 (Yellow Sat/Lum, Crop, Resets)

EXAMPLE:
  Ctrl+Alt+F1 = Exposure increase
  Ctrl+Alt+F2 = Exposure decrease
    )"
    MsgBox(help, "Hotkey Reference", 0x40)
}

; Startup notification
TrayTip("LR Slider Control", "Hotkeys active - right-click tray for help", 1)
