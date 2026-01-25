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
    LrDevelopController.resetToDefault("PostCropVignetteAmount")
    LrDevelopController.resetToDefault("GrainAmount")
    LrDevelopController.resetToDefault("GrainSize")
    LrDevelopController.resetToDefault("GrainFrequency")
end)
