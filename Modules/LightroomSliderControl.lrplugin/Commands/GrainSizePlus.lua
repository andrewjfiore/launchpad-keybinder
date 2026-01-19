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
    local current = LrDevelopController.getValue("GrainSize") or 0
    local newVal = math.max(0, math.min(100, current + 5))
    LrDevelopController.setValue("GrainSize", newVal)
end)
