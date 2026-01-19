local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

LrTasks.startAsyncTask(function()
    LrApplicationView.switchToModule('develop')
    LrTasks.sleep(0.05)
    
    local params = {"Exposure", "Contrast", "Highlights", "Shadows", "Whites", "Blacks"}
    for _, param in ipairs(params) do
        LrDevelopController.resetToDefault(param)
    end
end)
