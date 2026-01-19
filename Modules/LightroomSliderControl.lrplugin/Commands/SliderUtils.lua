local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

local SliderUtils = {}

local function ensureDevelopModule()
    if LrApplicationView.getCurrentModuleName() ~= 'develop' then
        LrApplicationView.switchToModule('develop')
    end

    local attempts = 0
    local maxAttempts = 20
    while attempts < maxAttempts and LrApplicationView.getCurrentModuleName() ~= 'develop' do
        LrTasks.sleep(0.05)
        attempts = attempts + 1
    end
end

function SliderUtils.withDevelopModule(action)
    LrTasks.startAsyncTask(function()
        ensureDevelopModule()
        action()
    end)
end

function SliderUtils.adjustSlider(param, delta, minVal, maxVal)
    SliderUtils.withDevelopModule(function()
        local current = LrDevelopController.getValue(param) or 0
        local newVal = math.max(minVal, math.min(maxVal, current + delta))
        LrDevelopController.setValue(param, newVal)
    end)
end

function SliderUtils.resetParams(params)
    SliderUtils.withDevelopModule(function()
        for _, param in ipairs(params) do
            LrDevelopController.resetToDefault(param)
        end
    end)
end

return SliderUtils
