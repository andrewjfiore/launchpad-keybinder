--[[
    Lightroom Slider Control - Socket Server
    Handles MIDI controller commands via TCP socket
    Version 2.1 - Improved error handling and logging
]]

local LrSocket = import 'LrSocket'
local LrTasks = import 'LrTasks'
local LrDevelopController = import 'LrDevelopController'
local LrFunctionContext = import 'LrFunctionContext'
local LrLogger = import 'LrLogger'
local LrFileUtils = import 'LrFileUtils'

local logger = LrLogger('SliderControlSocket')
-- Write to file: Documents/lrClassicLogs/SliderControlSocket.log
logger:enable('logfile')
local log = logger:quickf('info')

local PORT = 55555

local COMMAND_MAP = {
    ["1"]  = "Commands/ExposurePlus.lua",
    ["2"]  = "Commands/ExposureMinus.lua",
    ["3"]  = "Commands/ContrastPlus.lua",
    ["4"]  = "Commands/ContrastMinus.lua",
    ["5"]  = "Commands/HighlightsPlus.lua",
    ["6"]  = "Commands/HighlightsMinus.lua",
    ["7"]  = "Commands/ShadowsPlus.lua",
    ["8"]  = "Commands/ShadowsMinus.lua",
    ["9"]  = "Commands/WhitesPlus.lua",
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

-- Map for set_ commands (lowercase key -> LR parameter name)
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
    vignette = "PostCropVignetteAmount",
    grain = "GrainAmount",
    grainsize = "GrainSize",
    grainroughness = "GrainFrequency",
    straighten = "straightenAngle",
}

local function trim(value)
    return (value or ""):match("^%s*(.-)%s*$")
end

local function execute_command_file(command_file)
    -- Build full path to the command file
    local full_path = _PLUGIN.path .. "/" .. command_file
    
    -- Check if file exists
    if not LrFileUtils.exists(full_path) then
        log("ERROR: Command file not found: %s", full_path)
        return false
    end
    
    -- Execute the file with error handling
    local ok, err = pcall(function()
        dofile(full_path)
    end)
    
    if not ok then
        log("ERROR executing %s: %s", command_file, tostring(err))
        return false
    end
    
    log("Executed: %s", command_file)
    return true
end

local function handle_one(payload)
    payload = trim(payload)
    if payload == "" then
        return
    end
    
    log("Received command: '%s'", payload)

    -- Support direct set: set_exposure:0.25
    local slider_key, slider_value = payload:match("^set_([%a_]+):([%-%d%.]+)$")
    if slider_key and slider_value then
        local lr_key = SLIDER_MAP[slider_key:lower()]
        local value = tonumber(slider_value)
        if lr_key and value then
            log("Setting %s to %s", lr_key, tostring(value))
            LrTasks.startAsyncTask(function()
                local ok, err = pcall(function()
                    LrDevelopController.setValue(lr_key, value)
                end)
                if not ok then
                    log("ERROR setting %s: %s", lr_key, tostring(err))
                end
            end)
        else
            log("Unknown slider key: %s", slider_key)
        end
        return
    end

    -- Legacy numeric commands: "1".."60"
    local command_file = COMMAND_MAP[payload]
    if command_file then
        log("Executing command %s -> %s", payload, command_file)
        LrTasks.startAsyncTask(function()
            execute_command_file(command_file)
        end)
        return
    end
    
    -- Unknown command
    log("Unknown command: '%s'", payload)
end

local function handle_message(message)
    local msg = trim(message)
    if msg == "" then
        return
    end

    log("Raw message received: '%s' (len=%d)", msg, #msg)

    -- Split on newlines (socket may batch multiple commands)
    for line in (msg .. "\n"):gmatch("(.-)\n") do
        local trimmed = trim(line)
        if trimmed ~= "" then
            handle_one(trimmed)
        end
    end
end

local function start_server(functionContext)
    log("======================================")
    log("Slider Control Socket Server Starting")
    log("Plugin path: %s", _PLUGIN.path)
    log("Port: %d", PORT)
    log("======================================")

    local server = nil
    local bind_attempts = 0
    
    while server == nil do
        bind_attempts = bind_attempts + 1
        log("Bind attempt %d on port %d", bind_attempts, PORT)
        
        local ok, result = pcall(function()
            return LrSocket.bind({
                functionContext = functionContext,
                port = PORT,
                mode = "receive",
                plugin = _PLUGIN,
                onConnected = function(socket, port)
                    log("Client connected on port %d", port or PORT)
                    socket:read({
                        functionContext = functionContext,
                        onMessage = function(_, message)
                            handle_message(message)
                        end,
                        onClosed = function()
                            log("Client disconnected")
                        end,
                        onError = function(_, err)
                            log("Socket read error: %s", tostring(err))
                        end,
                    })
                end,
                onError = function(socket, err)
                    log("Socket error: %s", tostring(err))
                end,
            })
        end)

        if ok and result then
            server = result
            log("Server bound successfully on port %d", PORT)
        else
            log("Bind error: %s", tostring(result))
            if bind_attempts > 10 then
                log("Giving up after %d bind attempts", bind_attempts)
                return
            end
            LrTasks.sleep(1.0)
        end
    end

    functionContext:addCleanupHandler(function()
        pcall(function()
            if server then
                log("Cleanup: closing socket server")
                server:close()
            end
        end)
    end)

    log("Listening on port %d - ready for connections", PORT)
    
    -- Keep alive loop
    while true do
        LrTasks.sleep(1.0)
    end
end

-- Entry point: LrInitPlugin scripts are executed directly
log("SocketServer.lua loading...")

LrFunctionContext.callWithContext('SliderControlSocketInit', function(functionContext)
    LrTasks.startAsyncTask(function()
        start_server(functionContext)
    end)
end)
