if ts.GameSetup.IsMultiPlayerGame then
    return
end

local coins = 1010017
local treasury = ts.Economy.MetaStorage
local balance = treasury.GetStorageAmount(coins)
local capacity = treasury.GetStorageCapacity(coins)
local target = 1000000000
if type(capacity) == "number" and capacity > 0 and capacity < math.huge then
    target = capacity
end

if balance < target then
    -- The storage API accepts a signed 32-bit amount, including when the empire is in debt.
    treasury.AddAmount(coins, math.min(target - balance, 1000000000))
end
