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
    local current = LrDevelopController.getValue("Tint") or 0
    local newVal = math.max(-150, math.min(150, current + 5))
    LrDevelopController.setValue("Tint", newVal)
end)
