local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

LrTasks.startAsyncTask(function()
    LrApplicationView.switchToModule('develop')
    LrTasks.sleep(0.05)
    
    local param = "Temperature"
    local current = LrDevelopController.getValue(param) or 5500
    local newVal = math.max(2000, math.min(50000, current + 200))
    LrDevelopController.setValue(param, newVal)
end)
