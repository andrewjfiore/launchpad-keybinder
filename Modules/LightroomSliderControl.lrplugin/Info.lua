--[[
    Lightroom Slider Control Plugin
    Provides keyboard-accessible slider adjustments for use with Launchpad/AHK
    Version 2.0
]]

return {
    LrSdkVersion = 6.0,
    LrSdkMinimumVersion = 6.0,
    LrToolkitIdentifier = "com.launchpad.slidercontrol",
    LrPluginName = "Slider Control",
    
    LrExportMenuItems = {
        -- ============ BASIC TONE (1-12) ============
        { title = "01 Exposure +",    file = "Commands/ExposurePlus.lua" },
        { title = "02 Exposure -",    file = "Commands/ExposureMinus.lua" },
        { title = "03 Contrast +",    file = "Commands/ContrastPlus.lua" },
        { title = "04 Contrast -",    file = "Commands/ContrastMinus.lua" },
        { title = "05 Highlights +",  file = "Commands/HighlightsPlus.lua" },
        { title = "06 Highlights -",  file = "Commands/HighlightsMinus.lua" },
        { title = "07 Shadows +",     file = "Commands/ShadowsPlus.lua" },
        { title = "08 Shadows -",     file = "Commands/ShadowsMinus.lua" },
        { title = "09 Whites +",      file = "Commands/WhitesPlus.lua" },
        { title = "10 Whites -",      file = "Commands/WhitesMinus.lua" },
        { title = "11 Blacks +",      file = "Commands/BlacksPlus.lua" },
        { title = "12 Blacks -",      file = "Commands/BlacksMinus.lua" },
        
        -- ============ WHITE BALANCE (13-16) ============
        { title = "13 Temperature +", file = "Commands/TemperaturePlus.lua" },
        { title = "14 Temperature -", file = "Commands/TemperatureMinus.lua" },
        { title = "15 Tint +",        file = "Commands/TintPlus.lua" },
        { title = "16 Tint -",        file = "Commands/TintMinus.lua" },

        -- ============ PRESENCE (17-26) ============
        { title = "17 Texture +",     file = "Commands/TexturePlus.lua" },
        { title = "18 Texture -",     file = "Commands/TextureMinus.lua" },
        { title = "19 Clarity +",     file = "Commands/ClarityPlus.lua" },
        { title = "20 Clarity -",     file = "Commands/ClarityMinus.lua" },
        { title = "21 Dehaze +",      file = "Commands/DehazePlus.lua" },
        { title = "22 Dehaze -",      file = "Commands/DehazeMinus.lua" },
        { title = "23 Vibrance +",    file = "Commands/VibrancePlus.lua" },
        { title = "24 Vibrance -",    file = "Commands/VibranceMinus.lua" },
        { title = "25 Saturation +",  file = "Commands/SaturationPlus.lua" },
        { title = "26 Saturation -",  file = "Commands/SaturationMinus.lua" },

        -- ============ EFFECTS (27-34) ============
        { title = "27 Vignette +",    file = "Commands/VignettePlus.lua" },
        { title = "28 Vignette -",    file = "Commands/VignetteMinus.lua" },
        { title = "29 Grain +",       file = "Commands/GrainPlus.lua" },
        { title = "30 Grain -",       file = "Commands/GrainMinus.lua" },
        { title = "31 GrainSize +",   file = "Commands/GrainSizePlus.lua" },
        { title = "32 GrainSize -",   file = "Commands/GrainSizeMinus.lua" },
        { title = "33 GrainRough +",  file = "Commands/GrainRoughPlus.lua" },
        { title = "34 GrainRough -",  file = "Commands/GrainRoughMinus.lua" },

        -- ============ HSL RED (35-40) ============
        { title = "35 Red Hue +",     file = "Commands/RedHuePlus.lua" },
        { title = "36 Red Hue -",     file = "Commands/RedHueMinus.lua" },
        { title = "37 Red Sat +",     file = "Commands/RedSatPlus.lua" },
        { title = "38 Red Sat -",     file = "Commands/RedSatMinus.lua" },
        { title = "39 Red Lum +",     file = "Commands/RedLumPlus.lua" },
        { title = "40 Red Lum -",     file = "Commands/RedLumMinus.lua" },
        
        -- ============ HSL ORANGE (41-46) ============
        { title = "41 Orange Hue +",  file = "Commands/OrangeHuePlus.lua" },
        { title = "42 Orange Hue -",  file = "Commands/OrangeHueMinus.lua" },
        { title = "43 Orange Sat +",  file = "Commands/OrangeSatPlus.lua" },
        { title = "44 Orange Sat -",  file = "Commands/OrangeSatMinus.lua" },
        { title = "45 Orange Lum +",  file = "Commands/OrangeLumPlus.lua" },
        { title = "46 Orange Lum -",  file = "Commands/OrangeLumMinus.lua" },
        
        -- ============ HSL YELLOW (47-52) ============
        { title = "47 Yellow Hue +",  file = "Commands/YellowHuePlus.lua" },
        { title = "48 Yellow Hue -",  file = "Commands/YellowHueMinus.lua" },
        { title = "49 Yellow Sat +",  file = "Commands/YellowSatPlus.lua" },
        { title = "50 Yellow Sat -",  file = "Commands/YellowSatMinus.lua" },
        { title = "51 Yellow Lum +",  file = "Commands/YellowLumPlus.lua" },
        { title = "52 Yellow Lum -",  file = "Commands/YellowLumMinus.lua" },

        -- ============ CROP (53-56) ============
        { title = "53 Straighten +",  file = "Commands/StraightenPlus.lua" },
        { title = "54 Straighten -",  file = "Commands/StraightenMinus.lua" },
        { title = "55 CropAngle Reset", file = "Commands/CropAngleReset.lua" },

        -- ============ RESETS (56+) ============
        { title = "56 Reset Exposure",    file = "Commands/ResetExposure.lua" },
        { title = "57 Reset White Balance", file = "Commands/ResetWB.lua" },
        { title = "58 Reset Tone",        file = "Commands/ResetTone.lua" },
        { title = "59 Reset Presence",    file = "Commands/ResetPresence.lua" },
        { title = "60 Reset Effects",     file = "Commands/ResetEffects.lua" },
    },
    
    VERSION = { major = 2, minor = 0, revision = 0 },
}
