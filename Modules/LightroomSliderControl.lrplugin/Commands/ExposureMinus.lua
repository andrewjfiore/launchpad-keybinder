local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

local function ensureDevelopModule()
    if LrApplicationView.getCurrentModuleName() ~= 'develop' then
        LrApplicationView.switchToModule('develop')
    end
    local attempts = 0
    while attempts < 20 and LrApplicationView.getCurrentModuleName() ~= 'develop' do
        LrTasks.sleep(0.05)
        attempts = attempts + 1
    end
end

LrTasks.startAsyncTask(function()
    ensureDevelopModule()
    local current = LrDevelopController.getValue("Exposure") or 0
    local newVal = math.max(-5, math.min(5, current + -0.1))
    LrDevelopController.setValue("Exposure", newVal)
end)
