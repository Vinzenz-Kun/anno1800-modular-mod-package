"""Build the trader, research and inventory modules from extracted Anno 1800 XML."""
import argparse
import json
from collections import defaultdict
from functools import cache
from pathlib import Path
import xml.etree.ElementTree as ET

from bundle_text import COLLECTION_NOTE

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path("data/config/export/main/asset/assets.xml")
RARITIES = ("Common", "Uncommon", "Rare", "Epic", "Legendary")
TALENT = {
    "Production": (123672, 123672, 123681, 123682, 123683),
    "City": (123684, 123684, 123686, 123690, 123691),
    "Harbour": (123697, 123697, 123698, 123700, 123701),
}
EQUIPMENT = {"GuildhouseItem", "TownhallItem", "HarborOfficeItem", "VehicleItem", "ShipSpecialist"}
TRADERS = {45: "Legendary", 46: "Epic", 78: "Rare", 73: "Common", 76: "Common", 29: "Common"}
POOL = {"Common": 2141300000, "Rare": 2141300001, "Epic": 2141300002, "Legendary": 2141300003}


def elem(parent, tag, value=None, **attrs):
    child = ET.SubElement(parent, tag, attrs)
    if value is not None:
        child.text = str(value)
    return child


def modop(root, kind, path=None, guid=None, **attrs):
    if guid is not None:
        attrs["GUID"] = str(guid)
    if path:
        attrs["Path"] = path
    return elem(root, "ModOp", Type=kind, **attrs)


def save(folder, mod_id, title, intro, readme, root, version="1.0.0"):
    dest = ROOT / "mods" / folder
    file = dest / ASSETS
    file.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, "  ")
    ET.ElementTree(root).write(file, encoding="utf-8", xml_declaration=True)
    category = folder.split(" ", 1)[0]
    display_name = f"{category} {title}"
    info = {"Anno": 7, "Version": version, "ModID": mod_id,
            "ModName": {"English": display_name}, "Description": {"English": intro}, "LoadAfterIds": ["*"]}
    (dest / "modinfo.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (dest / "README.md").write_text(f"# {display_name}\n\n{intro}\n\n{COLLECTION_NOTE}\n\n{readme}\n", encoding="utf-8")


def reachable(roots, edges):
    pending, visited = list(roots), set()
    while pending:
        node = pending.pop()
        if node not in visited:
            visited.add(node)
            pending.extend(edges.get(node, ()))
    return visited


def add_link(parent, field, guid):
    row = elem(parent, "Item")
    elem(row, field, guid)
    if field == "ItemLink":
        elem(row, "Weight", 100)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_data", type=Path, help="Directory containing assets.xml and templates.xml")
    args = parser.parse_args()
    # Scalar <Asset> elements also occur inside lists. Keep them intact until their owner is read.
    assets, research_edges, reward_edges = {}, {}, {}
    recipe_roots, trade_roots = set(), set()
    for _, node in ET.iterparse(args.game_data / "assets.xml"):
        if node.tag != "Asset" or node.find("Values/Standard/GUID") is None:
            continue
        values = node.find("Values")
        guid = int(values.findtext("Standard/GUID"))
        item = values.find("Item")
        item_fields = {c.tag: c.text for c in item} if item is not None else {}
        assets[guid] = (node.findtext("Template"), int(node.findtext("BaseAssetGUID", "0")), item_fields)
        for path, edges in (("AssetPool/AssetList/Item/Asset", research_edges),
                            ("RewardPool/ItemsPool/Item/ItemLink", reward_edges)):
            links = [int(c.text) for c in values.findall(path) if c.text]
            if links:
                edges[guid] = links
        recipe_roots.update(int(c.text) for c in values.findall("ResearchSubcategory/RecipePool/Item/Pool"))
        if guid in TRADERS or guid in (77, 237, 119051):
            trade_roots.update(int(c.text) for c in values.findall("Trader/Progression/*/OfferingItems"))
        node.clear()

    templates = {}
    for t in ET.parse(args.game_data / "templates.xml").iterfind(".//Template"):
        it = t.find("Properties/Item")
        if it is not None:
            templates[t.findtext("Name")] = {c.tag: c.text for c in it}

    @cache
    def effective(guid):
        template, base, own = assets[guid]
        if base in assets:
            base_template, inherited = effective(base)
            template = template or base_template
        else:
            inherited = {}
        return template, {**templates.get(template, {}), **inherited, **own}

    discovered = reachable(recipe_roots, research_edges)
    sold = reachable(trade_roots, reward_edges)
    offers = defaultdict(list)
    missing = defaultdict(list)
    inherited_people = []
    common_people = []
    for guid in sorted(assets):
        template, it = effective(guid)
        rarity = it.get("Rarity", "Common")
        if rarity not in RARITIES:
            continue
        person = it.get("ItemType") == "Specialist" and template in EQUIPMENT
        if template not in templates and not assets[guid][2]:
            continue
        offers["Common" if rarity == "Uncommon" else rarity].append(guid)
        if not person:
            continue
        if not assets[guid][2].get("ItemType") and assets[guid][0] != "ShipSpecialist":
            inherited_people.append(guid)
        if rarity == "Common":
            common_people.append(guid)
        if guid not in discovered:
            allocation = it.get("Allocation")
            field = "City" if allocation == "TownHall" else "Production" if allocation in ("GuildHouse", "Lodge") else "Harbour"
            missing[TALENT[field][RARITIES.index(rarity)]].append(guid)

    trader = ET.Element("ModOps")
    research = ET.Element("ModOps")
    for tier, pool in POOL.items():
        if pool in assets:
            raise ValueError(f"Trader pool {pool} is already assigned")
        new = elem(modop(trader, "addNextSibling", guid=192069), "Asset")
        elem(new, "Template", "RewardItemPool")
        values = elem(new, "Values")
        standard = elem(values, "Standard")
        elem(standard, "GUID", pool)
        elem(standard, "Name", f"Specialist bundle - {tier} trader stock")
        stock = elem(elem(values, "RewardPool"), "ItemsPool")
        for guid in offers[tier]:
            add_link(stock, "ItemLink", guid)
    for guid, tier in TRADERS.items():
        op = modop(trader, "merge", "/Values/Trader/Progression/*", guid)
        elem(op, "OfferingItems", POOL[tier])
        elem(op, "MaxItemsToOffer", len(offers[tier]) + 128)
    for pool, guids in sorted(missing.items()):
        add = modop(research, "add", "/Values/AssetPool/AssetList", pool)
        for guid in guids:
            add_link(add, "Asset", guid)
    # Some common characters are deliberately excluded from automatic discovery by vanilla.
    blacklisted = set(common_people).intersection(research_edges.get(131176, ()))
    for guid in sorted(blacklisted):
        modop(research, "remove", f"/Values/AssetPool/AssetList/Item[Asset='{guid}']", 131176)

    # Keep save-compatible integrations for earlier personal and installed specialist mods.
    # Only IDs and acquisition categories are needed, so no third-party asset data is shipped.
    compatibility = {
        ("Production", "Legendary"): (
            1400000031, 2001000100, 2001000102, 2001000104, 2001000107,
            2000010012, 2000010018, 2000010023, 2000010024, 2000010030, 2000010031,
            2000010038, 2000010044, 2000010049, 2100119191, 2100119192, 2100119193,
            2100119194, 2100119195, 2100119197, 2100119198, 2100119199, 2100119203,
            2100119204, 2100119205, 2100119208),
        ("City", "Legendary"): (2001000350, 2100119167, 2100119168, 2100119169, 2100119190, 2100119196),
        ("Harbour", "Legendary"): (2100119206,),
        ("Harbour", "Epic"): (1400000005,),
    }
    custom = {guid: key for key, guids in compatibility.items() for guid in guids}
    for module in sorted((ROOT / "mods").iterdir()):
        if not module.is_dir() or not module.name.startswith("[Specialist] "):
            continue
        for asset in ET.parse(module / ASSETS).iterfind(".//Asset"):
            it = asset.find("Values/Item")
            if it is None or it.findtext("ItemType") != "Specialist":
                continue
            guid = int(asset.findtext("Values/Standard/GUID"))
            allocation = it.findtext("Allocation")
            field = "City" if allocation == "TownHall" else "Production" if allocation in ("Lodge", "GuildHouse") else "Harbour"
            custom[guid] = field, it.findtext("Rarity", "Common")
    for guid, (field, rarity) in sorted(custom.items()):
        # Optional character modules may be absent. Guard the asset reference on both routes.
        for root, target, path, link in (
            (trader, POOL["Common" if rarity == "Uncommon" else rarity], "/Values/RewardPool/ItemsPool", "ItemLink"),
            (research, TALENT[field][RARITIES.index(rarity)], "/Values/AssetPool/AssetList", "Asset"),
        ):
            group = elem(root, "Group", Condition=f"//Values[Standard/GUID='{guid}']")
            add = modop(group, "add", path, target)
            add_link(add, link, guid)

    for pool in sorted({p for pools in TALENT.values() for p in pools}):
        # A prior mod may already register its own recipes in the same discovery pool.
        modop(research, "remove", "/Values/AssetPool/AssetList/Item[Asset=preceding-sibling::Item/Asset]",
              pool, AllowNoMatch="1")

    stack = ET.Element("ModOps")
    target = "//Asset[Values/Item/ItemType='Specialist' or Template='ShipSpecialist']/Values"
    elem(elem(modop(stack, "merge", target), "Item"), "MaxStackSize", 50)
    if inherited_people:
        elem(elem(modop(stack, "merge", "/Values", ",".join(map(str, inherited_people))), "Item"),
             "MaxStackSize", 50)
    save("[Acquisition] Traders", "vinzenz-acquisition-traders", "Specialists at the traders",
         "I wanted to know which harbour to sail to when an island needed a particular specialist. "
         "This module sorts six traders’ stock by rarity from the first progression stage. "
         "You can use it on its own if you still want to earn each item by trading.",
         "Sir Archibald Blake offers legendary items, Eli Bleakworth epic items and Madame Kahina rare items. "
         "Isabel Sarmento, Anne Harlow and Jean La Fortune share common and uncommon stock. "
         "The catalogue includes equippable specialists and ordinary equipment and collectibles across the extracted game item catalogue. "
         "Active bundle characters join Archibald's stock. The Inuit, Nate and Ketema keep their regional business. "
         "Trading rights still apply. Reopen the harbour after a stock refresh or reroll.\n\n"
         "Copy this folder into Anno 1800's mods folder. Pair it with `[Acquisition] Research` for both routes. "
         "Disable older trader-overhaul or permanent-catalogue mods that also assign these traders' stock.\n\n"
         "## Thanks to RivvaDead\n\n"
         "Thank you to RivvaDead (RivvqPL) for giving each trader a recognisable speciality. "
         "The idea that I could sail straight to Archibald for a legendary item is what I wanted to carry over "
         "for the new characters. If you like that part of this collection, please visit the mod that started it. "
         "[Traders - Cheat Gains](https://www.nexusmods.com/anno1800/mods/24).", trader, version="1.1.0")
    save("[Acquisition] Research", "vinzenz-acquisition-research", "Specialist research",
         "I wanted my scholars to be able to find a specialist even when nobody had one for sale. "
         "This module adds specialist recipes to the Land of Lions Research Institute. "
         "Choose it on its own to keep the usual surprise of a trader’s stock.",
         "Discover talents in the production, city and harbour fields. Lodge specialists use production and ship specialists use harbour. "
         "Common characters use automatic discovery or the low-tier talent pool. Research costs, institute unlocks and development apply. "
         "The regular University is a public service building.\n\n"
         "Copy this folder into Anno 1800's mods folder. Install `[Acquisition] Traders` alongside it for both routes. "
         "Install this folder alone with selected characters to retain normal trader progression and rerolls. "
         "Using the institute requires Land of Lions. "
         "Quest cargo, scenario-only characters and narrative rarities have no standard development recipe.", research,
         version="1.1.0")
    save("[Inventory] Specialist Stacks", "vinzenz-inventory-specialist-stacks", "Specialist stacks of 50",
         "When I ship the same specialist to several islands, I like to keep the spares in one cargo slot. "
         "This module lets up to 50 copies share a stack. You can use it with the game's normal traders and specialists.",
         "Copy this folder into Anno 1800's mods folder. Equipment-slot and duplicate-equipping rules still apply.\n\n"
         "## Thanks to Reallizer\n\n"
         "Reallizer showed me how much easier a warehouse is to use when identical items can share a stack. "
         "I’m grateful for that idea. I kept the familiar limit of fifty and applied it to specialists, including "
         "the new characters. Reallizer’s original is well worth a visit. "
         "[50 Max Stack Size](https://www.nexusmods.com/anno1800/mods/131).", stack)
    print("Vanilla trader entries:", {tier: len(items) for tier, items in offers.items()})
    print("New vanilla talent-pool entries:", sum(map(len, missing.values())))


if __name__ == "__main__":
    main()
