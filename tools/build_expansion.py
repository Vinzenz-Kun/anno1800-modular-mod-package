"""Build housing, workforce, shipyard-specialist and delivery patches from the extracted assets."""
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

from build_fleet import ASSETS, ROOT, node

mods = ROOT / "mods"
work = Path(sys.argv[1])
density = ET.Element("ModOps")
workforce = ET.Element("ModOps")
ships = set(range(2141400000, 2141400005)) | set(range(2141400010, 2141400015))
options, yards = set(), set()
for _, a in ET.iterparse(work / "assets.xml"):
    v = a.find("Values") if a.tag == "Asset" else None
    if v is None or v.find("Standard/GUID") is None:
        continue
    guid = v.findtext("Standard/GUID")
    if v.find("Ship") is not None or a.findtext("Template") in ("WarShip", "TradeShip", "Flagship", "AirShip", "Salvager"):
        ships.add(int(guid))
    for tag in ("AddAssemblyOptions", "ReplaceAssemblyOptions"):
        extra = v.findall(f"ShipyardUpgrade/{tag}/Item/NewOption")
        if extra:
            options.update(int(x.text) for x in extra)
            yards.update(int(x.text) for x in v.findall("ItemEffect/EffectTargets/Item/GUID"))
    maximum = v.findtext("Residence7/ResidentMax")
    if maximum and int(maximum) > 0:
        op = node(density, "ModOp", Type="merge", GUID=guid, Path="/Values/Residence7")
        node(op, "ResidentMax", int(maximum) * 10)
    for row in v.findall("PopulationLevel7/PopulationInputs/Item"):
        weight = int(row.findtext("SupplyWeight", "0"))
        if weight > 0:
            op = node(density, "ModOp", Type="merge", GUID=guid,
                      Path=f"/Values/PopulationLevel7/PopulationInputs/Item[Product='{row.findtext('Product')}']")
            node(op, "SupplyWeight", weight * 10)
    a.clear()


def xml(path, tree):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree)
    ET.ElementTree(tree).write(path, encoding="utf-8", xml_declaration=True)


def module(name, slug, tree, description):
    folder = mods / name
    xml(folder / ASSETS, tree)
    info = dict(Anno=7, ModID="vinzenz-" + slug, Version="1.0.0", ModName={"English": name},
                Description={"English": description}, CreatorName="Vinzenz")
    (folder / "modinfo.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (folder / "README.md").write_text(f"# {name}\n\n{description}\n\nCopy this module into the game's mods folder to enable it independently.\n", encoding="utf-8")
    return folder


module("[Gameplay] Population Density x10", "population-density-10", density,
       "House ten times the usual residents by supplying their needs. Inspired by the earlier Population Density x10 mod.")
node(node(workforce, "ModOp", Type="merge", Path="//Asset/Values/Maintenance"), "WorkforceAmountFactor", 0)
folder = module("[Rules] No Workforce Requirements", "no-workforce", workforce,
                "Operate buildings without employing workforce. Money and material upkeep still apply.")
# Include maintenance inherited from a building template.
templates = ET.Element("ModOps")
node(node(templates, "ModOp", Type="merge", Path="//Template/Properties/Maintenance"), "WorkforceAmountFactor", 0)
xml(folder / ASSETS.with_name("templates.xml"), templates)

jack = 2141000150
tree = ET.Element("ModOps")
reference = mods / "[Specialist] Needs - Harbour"
asset = ET.parse(reference / ASSETS).find(".//Asset")
v = asset.find("Values")
for child in list(v):
    if child.tag not in ("Standard", "Item", "Locked"):
        v.remove(child)
v.find("Standard/GUID").text = str(jack)
v.find("Standard/Name").text = "Jack of All Ships"
v.find("Standard/InfoDescription").text = str(jack+1)
targets = node(node(v,"ItemEffect"),"EffectTargets")
for yard in sorted(yards):
    node(node(targets,"Item"),"GUID",yard)
recipes = node(node(v,"ShipyardUpgrade"),"AddAssemblyOptions")
for ship in sorted(options | {100440}):
    node(node(recipes,"Item"),"NewOption",ship)
node(tree,"ModOp",Type="addNextSibling",GUID="190695").append(asset)
offer = node(tree,"ModOp",Type="add",GUID="192909",Path="/Values/RewardPool/ItemsPool")
row = node(offer,"Item")
node(row,"ItemLink",jack)
node(row,"Weight",1)
folder = module("[Specialist] Jack of All Ships","jack-of-all-ships",tree,
                "Equip Jack in a Harbourmaster's Office covering a shipyard to build the specialist-exclusive pirate, royal and Pyrphorian vessels, the Extravaganza and the ship of the line.")
gui = Path("data/config/gui")
labels = ET.Element("ModOps")
entries = node(labels,"ModOp",Type="add",Path="/TextExport/Texts")
for g,label in ((jack,"Jack of All Ships"),(jack+1,"Unlocks specialist shipbuilding plans at shipyards in range.")):
    row=node(entries,"Text")
    node(row,"GUID",g)
    node(row,"Text",label)
xml(folder/gui/"specialist-texts.include.xml",labels)
for loc in (reference/gui).glob("texts_*.xml"):
    (folder/gui/loc.name).write_bytes(loc.read_bytes())

refill = mods / "[Cheat] Island Refill"
hotkeys = ET.parse(refill/ASSETS).getroot()
for op in list(hotkeys):
    if op.findtext("Item/KeyTypes") == "Shift;F10" or "2001000381" in op.get("Path",""):
        hotkeys.remove(op)
old = work/"build_kontor_toggle.py"
# Keep the original shortcut's passengers and support the new bundle specialists.
import ast
legacy = next(n.value for n in ast.parse(old.read_text(encoding="utf-8")).body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=="characters")
roster = [int(v.findtext("Standard/GUID")) for d in sorted(mods.iterdir()) if d.name.startswith("[Specialist] ") for v in ET.parse(d/ASSETS).iterfind(".//Asset/Values") if v.find("Item") is not None]
roster.extend(i for i,_ in ast.literal_eval(legacy) if i not in roster)
command = ("(function() if ts.GameSetup.IsMultiPlayerGame or not ts.Selection.Object.IsOwnedByCurrentParticipant then return end "
           "local ships={" + ",".join(f"[{s}]=true" for s in sorted(ships)) + "} if not ships[ts.Selection.Object.GetGUID()] then return end "
           "local roster={" + ",".join(map(str,roster)) + "} local i=VinzenzFleetDelivery or 1 for n=1,#roster do local g=roster[i] "
           "i=i%#roster+1 local ok,id=pcall(function() return ts.GetAssetData(g).Guid end) if ok and id==g then "
           "ts.Selection.Object.ItemContainer.SetCheatItemInSlot(g,1) VinzenzFleetDelivery=i return end end end)()")
node(hotkeys,"ModOp",Type="remove",GUID="2001271",Path="/Values/GUIConfig/KeyBindings/Item[KeyTypes='Shift;F10' and Text='2001000381']",AllowNoMatch="1")
binding=node(node(hotkeys,"ModOp",Type="add",GUID="2001271",Path="/Values/GUIConfig/KeyBindings"),"Item")
for k,value in dict(KeyTypes="Shift;F10",Command=command,Active="Session",AvailableOnPlatforms="PC",Text=2141200090,Configurable=1).items():
    node(binding,k,value)
xml(refill/ASSETS,hotkeys)
labels=ET.parse(refill/gui/"hotkey.include.xml").getroot()
if labels.find(".//Text[GUID='2141200090']") is None:
    row=node(labels.find("ModOp"),"Text")
    node(row,"GUID",2141200090)
    node(row,"Text","Deliver next specialist to selected ship")
xml(refill/gui/"hotkey.include.xml",labels)
print("Ship plans:",sorted(options),"yards:",yards,"density patches:",len(density))
