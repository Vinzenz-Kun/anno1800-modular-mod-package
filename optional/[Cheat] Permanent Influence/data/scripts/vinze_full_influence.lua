if ts.GameSetup.IsMultiPlayerGame then
    return
end

local influence = 1010190
local reserve = 1000000
local storage = ts.Economy.MetaStorage
local available = storage.GetAvailableAmount(influence)
local capacity = storage.GetStorageCapacity(influence)

-- Anno derives the total pool from several sources. A fixed upper target
-- prevents a grant that increases capacity from triggering another grant.
local target = reserve
if capacity > 0 then
    target = math.min(target, capacity)
end

if available < target then
    storage.AddAmount(influence, math.min(target - available, 1000000))
end
