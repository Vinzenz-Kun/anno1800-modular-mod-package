"""Build the five regional starter ships from the bundle's actual specialist assets."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path("data/config/export/main/asset/assets.xml")
DEST = ROOT / "optional" / "[Gameplay] Regional Battle Cruiser Fleet"
GOODS = (1010196, 1010205, 1010218)
# Rowan Pike, Mara Voss, Ellis Ward and the base game's Admiral Nadasky.
CREW = (2141000110, 2141000120, 2141000130, 191608)
REGIONS = (
    ("Old World", "Old World", "Ship - Cargo"),
    ("Cape Trelawney", "Old World", "Needs - Harbour"),
    ("New World", "New World", "Production - Harbour"),
    ("Arctic", "Arctic", "Ship - Expedition"),
    ("Enbesa", "Enbesa", "Ship - Combat"),
)


def node(parent, tag, value=None, **attrs):
    child = ET.SubElement(parent, tag, attrs)
    if value is not None:
        child.text = str(value)
    return child


def build():
    patch = ET.Element("ModOps")
    variants = node(patch, "ModOp", Type="addNextSibling", GUID="100442")
    dependencies = set()
    loads = []
    for index, (region, catalogue, extra) in enumerate(REGIONS):
        specialists = []
        for role in ("Production - " + catalogue, "Needs - " + catalogue,
                     "Agriculture", "Agriculture - Grand Fields", extra):
            folder = ROOT / "mods" / ("[Specialist] " + role)
            dependencies.add(json.loads((folder / "modinfo.json").read_bytes())["ModID"])
            people = [v for v in ET.parse(folder / ASSETS).iterfind(".//Asset/Values")
                      if v.find("Item") is not None]
            if len(people) > 1:
                socket = "Lodge" if region == "Arctic" else "GuildHouse"
                people = [v for v in people if v.findtext("Item/Allocation") == socket]
            assert len(people) == 1, (region, role)
            specialists.append(people[0].findtext("Standard/GUID"))
        assert len(set(specialists)) == 5
        guid = 2141400000 + index
        loads.append(guid)
        for campaign in (False, True):
            asset = node(variants, "Asset")
            node(asset, "BaseAssetGUID", 100442)
            values = node(asset, "Values")
            standard = node(values, "Standard")
            node(standard, "GUID", guid + 10 * campaign)
            node(standard, "Name", f"Regional Starting Cruiser - {region}" + (" (Campaign)" if campaign else ""))
            node(node(values, "Nameable"), "OverwriteNameWithTextAsset", 2141400020 + index)
            container = node(values, "ItemContainer")
            node(container, "SlotCount", 8)
            node(container, "SocketCount", len(CREW))
            sockets = node(container, "InitSocketItems")
            for person in CREW:
                node(node(sockets, "Item"), "Item", person)
            slots = node(container, "InitSlotItems")
            cargo = [(g, 50) for g in GOODS] + [(s, 1) for s in specialists]
            for product, amount in cargo:
                slot = node(slots, "Item")
                node(slot, "Item", product)
                node(slot, "StackSize", amount)

    op = node(patch, "ModOp", Type="replace", GUID="2002450", Path="/Values/DifficultySettings/StartShips")
    starts = node(op, "StartShips")
    for label, setting in enumerate(("None", "OneShip", "TradeFleet", "WarFleet"), 11073):
        choice = node(starts, setting)
        node(choice, "ValueName", label)
        ships = node(choice, "Ships")
        for guid in loads:
            ship = node(ships, "Item")
            node(ship, "Ship", guid)
    op = node(patch, "ModOp", Type="add", GUID="150841", Path="/Values/Quest/OnQuestEnd/Values/ActionList/Actions")
    for index, guid in enumerate(loads):
        action = node(node(op, "Item"), "Action")
        node(action, "Template", "ActionSpawnObjects")
        values = node(action, "Values")
        node(values, "Action")
        spawn = node(values, "ActionSpawnObjects")
        node(spawn, "SpawnGUID", guid + 10)
        node(spawn, "Amount", 1)
        node(spawn, "Owner", "Human0")
        area = node(values, "SpawnArea")
        for key, value in (("SpawnContext", "Object"), ("ContextGUID", 101432),
                           ("DistanceToContext", 18 + index * 2), ("MinObjectDistance", 5), ("MaxObjectDistance", 15)):
            node(area, key, value)
        node(node(node(node(values, "SessionFilter"), "Sessions"), "Item"), "Session", 180023)
    (DEST / ASSETS).parent.mkdir(parents=True, exist_ok=True)
    ET.indent(patch)
    ET.ElementTree(patch).write(DEST / ASSETS, encoding="utf-8", xml_declaration=True)
    texts = ET.Element("ModOps")
    entries = node(texts, "ModOp", Type="add", Path="/TextExport/Texts")
    for index, (region, _, _) in enumerate(REGIONS):
        entry = node(entries, "Text")
        node(entry, "GUID", 2141400020 + index)
        node(entry, "Text", region)
    gui = DEST / "data/config/gui"
    gui.mkdir(parents=True, exist_ok=True)
    ET.indent(texts)
    for loc in (ROOT / "mods/[Cheat] Island Refill/data/config/gui").glob("texts_*.xml"):
        ET.ElementTree(texts).write(gui / loc.name, encoding="utf-8", xml_declaration=True)
    info = dict(Anno=7, ModID="vinzenz-regional-starting-cruisers", Version="1.2.0",
                ModName={"English": DEST.name}, CreatorName="Vinzenz",
                Description={"English": "Five battle cruisers start with four ship specialists equipped and eight cargo holds filled with regional specialists and construction supplies."},
                ModDependencies=sorted(dependencies), LoadAfterIds=sorted(dependencies))
    (DEST / "modinfo.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
