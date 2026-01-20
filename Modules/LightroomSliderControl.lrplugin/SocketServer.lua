local LrSocket = import 'LrSocket'
local LrTasks = import 'LrTasks'
local LrDevelopController = import 'LrDevelopController'

local PORT = 55555
local COMMAND_MAP = {
    ["1"] = "Commands/ExposurePlus.lua",
    ["2"] = "Commands/ExposureMinus.lua",
    ["3"] = "Commands/ContrastPlus.lua",
    ["4"] = "Commands/ContrastMinus.lua",
    ["5"] = "Commands/HighlightsPlus.lua",
    ["6"] = "Commands/HighlightsMinus.lua",
    ["7"] = "Commands/ShadowsPlus.lua",
    ["8"] = "Commands/ShadowsMinus.lua",
    ["9"] = "Commands/WhitesPlus.lua",
    ["10"] = "Commands/WhitesMinus.lua",
    ["11"] = "Commands/BlacksPlus.lua",
    ["12"] = "Commands/BlacksMinus.lua",
    ["13"] = "Commands/TemperaturePlus.lua",
    ["14"] = "Commands/TemperatureMinus.lua",
    ["15"] = "Commands/TintPlus.lua",
    ["16"] = "Commands/TintMinus.lua",
    ["17"] = "Commands/TexturePlus.lua",
    ["18"] = "Commands/TextureMinus.lua",
    ["19"] = "Commands/ClarityPlus.lua",
    ["20"] = "Commands/ClarityMinus.lua",
    ["21"] = "Commands/DehazePlus.lua",
    ["22"] = "Commands/DehazeMinus.lua",
    ["23"] = "Commands/VibrancePlus.lua",
    ["24"] = "Commands/VibranceMinus.lua",
    ["25"] = "Commands/SaturationPlus.lua",
    ["26"] = "Commands/SaturationMinus.lua",
    ["27"] = "Commands/VignettePlus.lua",
    ["28"] = "Commands/VignetteMinus.lua",
    ["29"] = "Commands/GrainPlus.lua",
    ["30"] = "Commands/GrainMinus.lua",
    ["31"] = "Commands/GrainSizePlus.lua",
    ["32"] = "Commands/GrainSizeMinus.lua",
    ["33"] = "Commands/GrainRoughPlus.lua",
    ["34"] = "Commands/GrainRoughMinus.lua",
    ["35"] = "Commands/RedHuePlus.lua",
    ["36"] = "Commands/RedHueMinus.lua",
    ["37"] = "Commands/RedSatPlus.lua",
    ["38"] = "Commands/RedSatMinus.lua",
    ["39"] = "Commands/RedLumPlus.lua",
    ["40"] = "Commands/RedLumMinus.lua",
    ["41"] = "Commands/OrangeHuePlus.lua",
    ["42"] = "Commands/OrangeHueMinus.lua",
    ["43"] = "Commands/OrangeSatPlus.lua",
    ["44"] = "Commands/OrangeSatMinus.lua",
    ["45"] = "Commands/OrangeLumPlus.lua",
    ["46"] = "Commands/OrangeLumMinus.lua",
    ["47"] = "Commands/YellowHuePlus.lua",
    ["48"] = "Commands/YellowHueMinus.lua",
    ["49"] = "Commands/YellowSatPlus.lua",
    ["50"] = "Commands/YellowSatMinus.lua",
    ["51"] = "Commands/YellowLumPlus.lua",
    ["52"] = "Commands/YellowLumMinus.lua",
    ["53"] = "Commands/StraightenPlus.lua",
    ["54"] = "Commands/StraightenMinus.lua",
    ["55"] = "Commands/CropAngleReset.lua",
    ["56"] = "Commands/ResetExposure.lua",
    ["57"] = "Commands/ResetWB.lua",
    ["58"] = "Commands/ResetTone.lua",
    ["59"] = "Commands/ResetPresence.lua",
    ["60"] = "Commands/ResetEffects.lua",
}

local SLIDER_MAP = {
    exposure = "Exposure",
    contrast = "Contrast",
    highlights = "Highlights",
    shadows = "Shadows",
    whites = "Whites",
    blacks = "Blacks",
    temperature = "Temperature",
    tint = "Tint",
    texture = "Texture",
    clarity = "Clarity",
    dehaze = "Dehaze",
    vibrance = "Vibrance",
    saturation = "Saturation",
}

local function trim(value)
    return value:match("^%s*(.-)%s*$")
end

local function handle_command(message)
    local payload = trim(message or "")
    if payload == "" then
        return
    end
    local slider_key, slider_value = payload:match("^set_([%a_]+):([%-%d%.]+)$")
    if slider_key and slider_value then
        local lr_key = SLIDER_MAP[slider_key:lower()]
        local value = tonumber(slider_value)
        if lr_key and value then
            LrTasks.startAsyncTask(function()
                LrDevelopController.setValue(lr_key, value)
            end)
        end
        return
    end
    local command_file = COMMAND_MAP[payload]
    if command_file then
        LrTasks.startAsyncTask(function()
            dofile(_PLUGIN.path .. "/" .. command_file)
        end)
    end
end

return function(functionContext)
    LrTasks.startAsyncTask(function()
        while true do
            local server = LrSocket.bind({
                functionContext = functionContext,
                port = PORT,
                mode = "receive",
                plugin = _PLUGIN,
                onConnected = function(socket)
                    socket:read({
                        functionContext = functionContext,
                        onMessage = function(_, message)
                            handle_command(message)
                        end,
                        onClosed = function()
                        end,
                    })
                end,
            })
            if server then
                server:close()
            end
            LrTasks.sleep(0.5)
        end
    end)
end
