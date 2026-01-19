/*
    Lightroom Slider Control - AutoHotkey v2 Script
    Version: 2.0
    
    Maps keyboard shortcuts to Lightroom Slider Control plugin commands.
    
    INSTALLATION:
    1. Install AutoHotkey v2 from https://www.autohotkey.com/
    2. Install LightroomSliderControl.lrplugin in Lightroom
    3. Run this script
    4. Test: In Lightroom Develop module, press Ctrl+Alt+Shift+E
    
    CONFIGURATION:
    - Adjust MENU_DELAY if menus aren't responding (increase for slower PCs)
    - Adjust PLUGIN_POS if you have multiple plugins installed
*/

#Requires AutoHotkey v2.0
#SingleInstance Force

; === CONFIGURATION ===
global MENU_DELAY := 120         ; Milliseconds between menu operations
global SUBMENU_DELAY := 80       ; Delay for submenu operations
global ITEM_DELAY := 30          ; Delay between arrow key presses
global PLUGIN_POS := 1           ; Position of Slider Control in Plug-in Extras (1 = first)

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
; Pattern: Ctrl+Alt+Shift+KEY = increase (+)
;          Ctrl+Alt+KEY = decrease (-)

; BASIC TONE (positions 1-12)
^!+e::TriggerPluginCommand(1)   ; Exposure +
^!e::TriggerPluginCommand(2)    ; Exposure -
^!+c::TriggerPluginCommand(3)   ; Contrast +
^!c::TriggerPluginCommand(4)    ; Contrast -
^!+h::TriggerPluginCommand(5)   ; Highlights +
^!h::TriggerPluginCommand(6)    ; Highlights -
^!+s::TriggerPluginCommand(7)   ; Shadows +
^!s::TriggerPluginCommand(8)    ; Shadows -
^!+w::TriggerPluginCommand(9)   ; Whites +
^!w::TriggerPluginCommand(10)   ; Whites -
^!+b::TriggerPluginCommand(11)  ; Blacks +
^!b::TriggerPluginCommand(12)   ; Blacks -

; WHITE BALANCE (positions 13-16)
^!+t::TriggerPluginCommand(13)  ; Temperature + (warmer)
^!t::TriggerPluginCommand(14)   ; Temperature - (cooler)
^!+n::TriggerPluginCommand(15)  ; Tint + (magenta)
^!n::TriggerPluginCommand(16)   ; Tint - (green)

; PRESENCE (positions 17-26)
^!+x::TriggerPluginCommand(17)  ; Texture +
^!x::TriggerPluginCommand(18)   ; Texture -
^!+l::TriggerPluginCommand(19)  ; Clarity +
^!l::TriggerPluginCommand(20)   ; Clarity -
^!+d::TriggerPluginCommand(21)  ; Dehaze +
^!d::TriggerPluginCommand(22)   ; Dehaze -
^!+v::TriggerPluginCommand(23)  ; Vibrance +
^!v::TriggerPluginCommand(24)   ; Vibrance -
^!+a::TriggerPluginCommand(25)  ; Saturation +
^!a::TriggerPluginCommand(26)   ; Saturation -

; EFFECTS (positions 27-34)
^!+g::TriggerPluginCommand(27)  ; Vignette +
^!g::TriggerPluginCommand(28)   ; Vignette -
^!+r::TriggerPluginCommand(29)  ; Grain +
^!r::TriggerPluginCommand(30)   ; Grain -
^!+z::TriggerPluginCommand(31)  ; GrainSize +
^!z::TriggerPluginCommand(32)   ; GrainSize -
^!+o::TriggerPluginCommand(33)  ; GrainRough +
^!o::TriggerPluginCommand(34)   ; GrainRough -

; HSL RED (positions 35-40)
^!+1::TriggerPluginCommand(35)  ; Red Hue +
^!1::TriggerPluginCommand(36)   ; Red Hue -
^!+2::TriggerPluginCommand(37)  ; Red Sat +
^!2::TriggerPluginCommand(38)   ; Red Sat -
^!+3::TriggerPluginCommand(39)  ; Red Lum +
^!3::TriggerPluginCommand(40)   ; Red Lum -

; HSL ORANGE (positions 41-46)
^!+4::TriggerPluginCommand(41)  ; Orange Hue +
^!4::TriggerPluginCommand(42)   ; Orange Hue -
^!+5::TriggerPluginCommand(43)  ; Orange Sat +
^!5::TriggerPluginCommand(44)   ; Orange Sat -
^!+6::TriggerPluginCommand(45)  ; Orange Lum +
^!6::TriggerPluginCommand(46)   ; Orange Lum -

; HSL YELLOW (positions 47-52)
^!+7::TriggerPluginCommand(47)  ; Yellow Hue +
^!7::TriggerPluginCommand(48)   ; Yellow Hue -
^!+8::TriggerPluginCommand(49)  ; Yellow Sat +
^!8::TriggerPluginCommand(50)   ; Yellow Sat -
^!+9::TriggerPluginCommand(51)  ; Yellow Lum +
^!9::TriggerPluginCommand(52)   ; Yellow Lum -

; CROP (positions 53-55)
^!+[::TriggerPluginCommand(53)  ; Straighten +
^![::TriggerPluginCommand(54)   ; Straighten -
^!]::TriggerPluginCommand(55)   ; CropAngle Reset

; RESETS (positions 56-60)
^!+F1::TriggerPluginCommand(56) ; Reset Exposure
^!+F2::TriggerPluginCommand(57) ; Reset White Balance
^!+F3::TriggerPluginCommand(58) ; Reset Tone
^!+F4::TriggerPluginCommand(59) ; Reset Presence
^!+F5::TriggerPluginCommand(60) ; Reset Effects

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

All hotkeys use Ctrl+Alt as base.
Add SHIFT for + (increase), no Shift for - (decrease).

TONE:
  E = Exposure       C = Contrast
  H = Highlights     S = Shadows
  W = Whites         B = Blacks

WHITE BALANCE:
  T = Temperature    N = Tint

PRESENCE:
  X = Texture        L = Clarity
  D = Dehaze         V = Vibrance
  A = Saturation

EFFECTS:
  G = Vignette       R = Grain
  Z = Grain Size     O = Grain Rough

HSL:
  1/2/3 = Red Hue/Sat/Lum
  4/5/6 = Orange Hue/Sat/Lum
  7/8/9 = Yellow Hue/Sat/Lum

EXAMPLE:
  Ctrl+Alt+Shift+E = Exposure increase
  Ctrl+Alt+E = Exposure decrease
    )"
    MsgBox(help, "Hotkey Reference", 0x40)
}

; Startup notification
TrayTip("LR Slider Control", "Hotkeys active - right-click tray for help", 1)
