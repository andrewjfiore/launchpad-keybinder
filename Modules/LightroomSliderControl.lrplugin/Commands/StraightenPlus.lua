local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

LrTasks.startAsyncTask(function()
    LrApplicationView.switchToModule('develop')
    LrTasks.sleep(0.05)
    
    local param = "CropAngle"
    local current = LrDevelopController.getValue(param) or 0
    local newVal = math.max(-45, math.min(45, current + 0.5))
    LrDevelopController.setValue(param, newVal)
end)
