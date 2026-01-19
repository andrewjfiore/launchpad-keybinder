local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

LrTasks.startAsyncTask(function()
    LrApplicationView.switchToModule('develop')
    LrTasks.sleep(0.05)
    
    local param = "Exposure"
    local current = LrDevelopController.getValue(param) or 0
    local newVal = math.max(-5, math.min(5, current - 0.1))
    LrDevelopController.setValue(param, newVal)
end)
