local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

LrTasks.startAsyncTask(function()
    LrApplicationView.switchToModule('develop')
    LrTasks.sleep(0.05)
    
    local param = "Texture"
    local current = LrDevelopController.getValue(param) or 0
    local newVal = math.max(-100, math.min(100, current + 5))
    LrDevelopController.setValue(param, newVal)
end)
