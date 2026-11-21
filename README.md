# Anno 1800 Modular Specialists Bundle

I put this collection together for the days when I want to spend an evening building an island and decide for myself which parts of running it will be a challenge. With everything enabled, it plays like a powerful cheat mod. A single specialist can look after a whole island’s needs, and a warehouse refill can make entire production chains optional.

That’s why each change has its own folder. You can take just a cargo specialist and still earn every coin and produce every ton yourself. Or you can give your residents everything they need and spend your time laying out their city. Pick the parts that suit the save you want to play.

Many of those choices started with other modders’ work. If you enjoy a feature here, I’d love for you to visit the people who first gave me the idea. Each relevant module’s README tells that story and links to the original. You can also find all the authors together in the [credits](CREDITS.md).

## Install

1. Extract the ZIP to a temporary folder. For the standard setup, copy the **contents** of its `mods` folder into your Anno 1800 `mods` folder. For a smaller setup, copy just the individual module folders you want.
2. Check the directory depth. A correct installation looks like `Anno 1800/mods/[Specialist] Ship - Cargo/modinfo.json`. If you installed the previous bundle, move its old hyphen-named module folders out of the game’s `mods` folder before copying their renamed replacements. Both versions use the same internal mod IDs.
3. Open the game's mod browser, enable your selection and load your save. Regional content needs its corresponding DLC. The Research Institute requires Land of Lions. The keyboard shortcuts and automatic resource grants are for single-player on PC.
4. To add a money or influence cheat, copy the desired module from `optional` into the same game `mods` folder. To use +5 bribes, disable `[Diplomacy] Bribes +25` and enable `[Diplomacy] Bribes +5`.

The standard setup contains 39 modules. It includes all 16 character modules, both acquisition routes, inventory stacks of 50, the building and economy changes, island refill and +25 paid bribes. Keep a separate save before changing which character modules you use. Removing an item definition can remove copies already held in that save.

## Choose your acquisition routes

| Enabled modules | Where specialists appear |
| --- | --- |
| Both acquisition modules (standard) | Sorted traders and Research Institute discoveries |
| `[Acquisition] Research` only | Institute discoveries and the characters’ normal regional traders or workshop |
| `[Acquisition] Traders` only | Sorted traders, with base-game research rules |
| Neither | Each character's normal trader pools or workshop, described in its README |

With the trader split, Sir Archibald Blake sells legendary items, Eli Bleakworth sells epic items and Madame Kahina sells rare items. Isabel Sarmento, Anne Harlow and Jean La Fortune sell common and uncommon items. All bundle specialists are legendary. Pirate trade still requires trade rights. Look after a stock refresh or use a reroll. Research discoveries appear in the production, city and harbour talent fields. The normal University serves a different game function.

The optional **[Gameplay] Regional Battle Cruiser Fleet** adds five battle cruisers for new starts. Each has four ship specialists already equipped. Its eight cargo holds carry five regional specialists and 50 t each of Timber, Bricks and Steel Beams. Install all 15 character modules with it and disable older starting-fleet mods.

## Choose your specialists

| Folder name after `[Specialist]` | Where to equip it | Main effect |
| --- | --- | --- |
| `Production - Old World`, `Production - New World`, `Production - Enbesa` | Trade Union in the named region, including Cape Trelawney for the Old World | Each completed cycle adds one ton of **each** good in the regional catalogue. The Old World edition covers 149 goods, the New World 113 and Enbesa 49. They also double productivity and supply compatible electricity users. |
| `Production - Arctic` | Arctic Lodge | Jack of All Lodges supplies heat and generates 99 goods per cycle, including all 76 bonuses from the earlier Lodge edition. |
| `Production - Harbour` | Harbourmaster's Office | Jack of All Seas grants one ton of each of the 191 distinct goods across the four catalogues and supplies compatible electricity users. |
| `Agriculture` | Trade Union or Arctic Lodge | The compact edition of Robin Vale removes the need for crop fields and animal pens. Its −400% internal modifier accounts for additive bonuses such as a tractor, leaving the effective requirement at zero. |
| `Agriculture - Grand Fields` | Trade Union or Arctic Lodge | Robin’s landscape edition has the same production and goods bonuses and a +500% field and pasture modifier for large working estates. |
| `Needs - Old World`, `Needs - New World`, `Needs - Enbesa`, `Needs - Arctic`, `Needs - Harbour` | Town Hall, Arctic Lodge or Harbourmaster's Office | Reduce consumption by 100% for supported basic, luxury and lifestyle needs. Add happiness, housing capacity and incident protection. The Arctic version supplies heat. |
| `Ship - Expedition`, `Ship - Combat`, `Ship - Cargo` | Ship, with a warship required for Combat | Expedition morale, skills and traits, combat performance, or cargo speed, loading and active purchase prices. |

Needs unlock at their usual population thresholds. Enable the lifestyle needs you want to use. The Old World specialist covers tourists, scholars and skyscrapers. Island-wide effects require `[Gameplay] Island Item Coverage` and a compatible equipped item. Both farming editions depend on `[Rules] Free Fertility` to grow every supported crop regardless of island fertility.

Each Jack's README lists its goods by category. The lists cover physical products used or produced in the region, including imports for residents, factories, construction and local workshops. The Old World edition also keeps every bonus from blejky’s original Jack. Oil and mail use their dedicated storage. Tractor barns receive fuel from working Fuel Stations.

Both farming editions grant +100% productivity, −100% required forest or free area, −50% workforce and one ton of each of 66 agricultural goods per completed cycle. Equip one edition per farm area. Grand Fields raises the normal field count sixfold. For a grain farm, 864 fields are both the placement limit and the target for full field utilisation. The module also increases animal pen placement range to 40 tiles while installed, including when Robin is unequipped.

Jack of All Ships adds ten specialist ship plans plus the standard ship of the line at shipyards covered by his Harbourmaster�s Office.

## Buildings and economy

Population Density x10 increases housing capacity and the residents supplied by needs tenfold. No Workforce Requirements removes building labour demand.

Each `[Gameplay]` folder can be selected independently.

| Module suffix | Change |
| --- | --- |
| `Island Item Coverage` | Equipped Trade Union, Town Hall, harbour and Lodge items reach eligible targets on the entire island. |
| `Tourism`, `Public Services`, `Power Plants` | Extend tourist, public service, Palace and power coverage. Tourism removes the distance penalty. Roads, active venues and fuel still matter. |
| `Harbour Storage` | Each goods depot provides 2,000 t. A fully upgraded trading post provides 2,500 t across the four regions, including the Arctic plateau. |
| `Farm Storage`, `Production Item Targets` | Increase farm buffers or allow additional existing items to affect orchards, chemical production and telephones. |
| `Arctic Workshop`, `Research`, `Shipbuilding` | Reduce workshop ingredients, shorten and cheapen Institute development, or build ships on the next production tick. |
| `Royal Taxes`, `Residential Appeal`, `Fast Move-In`, `Pollution Happiness` | Change royal taxes, residential attractiveness, move-in intervals or the happiness effect of pollution. |

`[Inventory] Specialist Stacks` sets inventory stacks to 50. Each item's equip limit still applies. `[Legacy] Lodge Portraits` repairs the missing portrait on existing copies of Aput, the Eternal Hearth, when the original Arctic Lodge Specialists mod is present.

## Cheat and diplomacy controls

| Module | Action |
| --- | --- |
| `[Cheat] Island Refill` | Move the camera over your own island and press **Shift+F9** to add up to **500 t per available good**, limited by remaining storage. |
| `[Cheat] Island Refill` | Select an owned ship and press **Shift+F10** to deliver the next available specialist. |
| `[Cheat] Add Money` (optional) | Press **Shift+F11** to receive **1,000,000 coins**. |
| `[Cheat] Permanent Money` (optional) | Refills to the game’s reported coin limit, depositing up to **1 billion coins per simulation second**. Uses 1 billion as the target when the game reports no positive finite limit. |
| `[Cheat] Permanent Influence` (optional) | Targets **1,000,000 spendable influence**. Investments still cost influence and count toward their ordinary bonuses. The game has no single fixed maximum for every empire. |
| `[Diplomacy] Bribes +25` or `[Diplomacy] Bribes +5` | Offer a **monetary gift** to a rival or pirate to earn the selected reputation gain at the normal price. |

## Existing mods and saves

The new specialists have separate item IDs. Keep the original Arctic Lodge Specialists or Lifestyle Ambassador enabled if you want to retain those older items in a save. Disable the old Cheat Gains Traders, Permanent Specialist Catalog or Specialist Research when replacing their acquisition rules. Disable the old Rival and Pirate Diplomacy when switching from its flattery changes to paid gifts. Disable the older refill mod when using the bundled F9 and F10 shortcuts. Other building mods that change the same capacities or ranges can overwrite these values.

The bundle was checked against extracted game assets and templates using the Anno modloader's XML test tool. Acquisition checks cover both catalogues together, each catalogue on its own, normal availability, each farming edition installed by itself, and a setup with both catalogues and zero bundle characters. In-game UI, simulation and save/reload behaviour still need a playtest.

