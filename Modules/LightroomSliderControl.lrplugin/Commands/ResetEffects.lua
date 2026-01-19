local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

LrTasks.startAsyncTask(function()
    LrApplicationView.switchToModule('develop')
    LrTasks.sleep(0.05)
    
    local params = {"PostCropVignetteAmount", "GrainAmount", "GrainSize", "GrainFrequency"}
    for _, param in ipairs(params) do
        LrDevelopController.resetToDefault(param)
    end
end)
