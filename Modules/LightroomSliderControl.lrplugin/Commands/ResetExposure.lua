local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

LrTasks.startAsyncTask(function()
    LrApplicationView.switchToModule('develop')
    LrTasks.sleep(0.05)
    
    LrDevelopController.resetToDefault("Exposure")
end)
