"""Build the standalone Anno 1800 specialist modules from the extracted game XML."""
from pathlib import Path
from collections import defaultdict
from argparse import ArgumentParser
from functools import lru_cache
import xml.etree.ElementTree as ET
import json
from bundle_text import COLLECTION_NOTE
parser = ArgumentParser(description=__doc__)
parser.add_argument("work", type=Path, help="Directory containing extracted assets.xml and templates.xml")
work = parser.parse_args().work
dest = Path(__file__).resolve().parents[1] / "mods"
asset_dir = Path("data/config/export/main/asset")
gui_dir = Path("data/config/gui")
templates = {n.findtext("Name"): n.find("Properties") for n in ET.parse(
    work / "templates.xml").findall(".//Template") if n.find("Properties") is not None}
assets = {}
for _, element in ET.iterparse(work / "assets.xml", events=("end",)):
    guid = element.findtext("Values/Standard/GUID") if element.tag == "Asset" else None
    if not guid or not guid.isdecimal():
        continue
    values = element.find("Values")
    template = element.findtext("Template")
    parent = element.findtext("BaseAssetGUID")
    # Only retain full properties for the game objects used to derive this bundle.
    keys = ["Standard", "Building", "Residence7", "Factory7", "PopulationLevel7", "ItemEffectTargetPool", "Industrializable", "Electrifiable",
            "Heated", "FreeAreaProductivity", "FactoryBase", "Product", "Constructable", "ModuleOwner", "Item", "Text", "ExpeditionAttribute"]
    keys.extend(("ProductList", "ProductStorageList", "Cost", "ItemCrafter", "CraftableItem"))
    kept = {k: values.find(k) for k in keys if values.find(k) is not None and
            (k != "Text" or values.find("Product") is not None)}
    assets[int(guid)] = (template, int(parent) if parent else None, kept)
    element.clear()


@lru_cache(None)
def template_name(guid):
    name, parent, _ = assets[guid]
    return name or (template_name(parent) if parent else "")


def prop(guid, path):
    section, _, sub = path.partition("/")
    key = guid
    while key in assets:
        _, parent, props = assets[key]
        val = props.get(section)
        if val is not None:
            found = val.find(sub) if sub else val
            if found is not None:
                return found
        key = parent
    schema = templates.get(template_name(guid))
    return schema.find(path) if schema is not None else None


def field(guid, path, default=""):
    n = prop(guid, path)
    return n.text if n is not None and n.text else default


def add(parent, tag, val=None, **attrs):
    n = ET.SubElement(parent, tag, attrs)
    if val is not None:
        n.text = str(val)
    return n


def fields(parent, **kwargs):
    for k, v in kwargs.items():
        add(parent, k, v)


def upgrade(parent, tag, number, percent=True):
    n = add(parent, tag)
    add(n, "Value", number)
    if percent:
        add(n, "Percental", 1)


def item(parent, **kwargs):
    fields(add(parent, "Item"), **kwargs)


def xml(root, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, "  ")
    path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n")


def meta(folder, modid, name, desc, category="Specialists", version="1.0.0", **kwargs):
    folder.mkdir(parents=True, exist_ok=True)
    info = dict(Anno=7, ModID=modid, Version=version, ModName={"English": name}, Category={"English": category},
                Description={"English": desc}, CreatorName="Vinzenz", **kwargs)
    (folder / "modinfo.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# Regional coverage is resolved through asset and template inheritance, including recipe variants.
region_names = {"Old-World": "Moderate", "New-World": "Colony01", "Enbesa": "Africa", "Arctic": "Arctic"}
tiers = {"Old-World": [15000000, 15000001, 15000002, 15000003, 15000004, 118745, 601379],
         "New-World": [15000005, 15000006, 5403], "Enbesa": [114329, 114330], "Arctic": [112642, 112643]}
regions = defaultdict(set)
farms = set()
fertility_buildings = []
regional_factories = defaultdict(set)
power_targets = defaultdict(set)
houses = defaultdict(set)
coastal = set()
for guid in assets:
    if prop(guid, "Building") is None:
        continue
    name = field(guid, "Standard/Name").lower()
    if guid in {668, 269850, 269851, 270044} or "scenario" in name or "scenario" in template_name(guid).lower():
        continue
    explicit = field(guid, "Building/AssociatedRegions")
    if not explicit and "arctic" in template_name(guid).lower():
        explicit = "Arctic"
    session = set(explicit.split(";"))
    is_factory = prop(
        guid, "FactoryBase/FactoryOutputs/Item/Product") is not None or prop(guid, "Factory7") is not None
    tier = int(field(guid, "Residence7/PopulationLevel7", "0"))
    for region, code in region_names.items():
        if tier in tiers[region]:
            houses[region].add(guid)
            session.add(code)
        if code not in session:
            continue
        regions[region].add(guid)
        if is_factory:
            regional_factories[region].add(guid)
        if any(prop(guid, p) is not None for p in ["Industrializable", "Electrifiable", "Heated"]):
            power_targets[region].add(guid)
    if not session.intersection(region_names.values()):
        continue
    if is_factory and any(word in field(guid, "Building/TerrainType") for word in ("Coast", "Water")):
        coastal.add(guid)
    fertility = int(field(guid, "Factory7/NeededFertility", "0"))
    if fertility > 0:
        # GUID-level merge also handles buildings which inherit the fertility field.
        if template_name(fertility) == "Fertility":
            fertility_buildings.append(guid)
    # The FarmBuilding template also covers oil wells, gas mines and a scenario refinery.
    # Only field and pen owners, plus businesses whose output depends on local woodland, belong here.
    if is_factory and (field(guid, "ModuleOwner/FarmType") in {"PlantFarm", "AnimalFarm"}
                       or prop(guid, "FreeAreaProductivity") is not None):
        farms.add(guid)


def pool_members(guid):
    out = set()
    for e in prop(guid, "ItemEffectTargetPool/EffectTargetGUIDs"):
        child = int(e.findtext("GUID"))
        if template_name(child) == "ItemEffectTargetPool":
            out.update(pool_members(child))
        else:
            out.add(child)
    return out


regional_factories["Arctic"].update(pool_members(193770))
for agriculture_pool in (190011, 190872, 190865, 194008, 8389, 190779, 144187):
    farms.update(pool_members(agriculture_pool))
# Arctic whaling and sealing, Enbesan salt, campaign forestry and the three real Fuel Stations.
farms.update((112666, 112674, 114440, 100806, 100807, 118571, 269840, 119028))
tractor_fuel = 270042
animal_pen_owners = sorted(g for g in farms if field(g, "ModuleOwner/FarmType") == "AnimalFarm")
farm_goods = pool_members(7096) | pool_members(7101)  # Agricultural products and raw materials
for catalogue in (502037, 502038, 502039, 502076):
    # The New World list still refers to a retired product. Only emit resolvable goods.
    listing = prop(catalogue, "ProductList/List")
    farm_goods.update(int(e.text) for e in listing.findall("Item/Product") if int(e.text) in assets)
for building in farms:
    outputs = prop(building, "FactoryBase/FactoryOutputs")
    if outputs is not None:
        farm_goods.update(int(e.text) for e in outputs.findall("Item/Product"))
# Common milling, rendering, spinning, brewing and distilling ingredients derived from farm produce.
farm_goods.update((1010234, 1010235, 1010236, 1010239, 1010240, 120044, 114391, 114408, 135130))
assert {24807, 24808, tractor_fuel, 1010253, 5385, 5401}.issubset(farm_goods)
assert all(template_name(g) == "Product" and field(g, "Product/IsAbstract") != "1" for g in farm_goods)
coastal.update(pool_members(193400))
staples = {t: int(prop(
    t, "PopulationLevel7/PopulationInputs").find("Item[Amount]/Product").text) for ts in tiers.values() for t in ts}
needs = {}
services = {}
for region, ts in tiers.items():
    goods = set()
    subs = set()
    for t in ts:
        for e in prop(t, "PopulationLevel7/PopulationInputs").findall("Item/Product"):
            g = int(e.text)
            goods.add(g)
            if field(g, "Product/IsAbstract") == "1":
                subs.add((g, staples[t]))
    needs[region] = goods
    services[region] = subs

def product_name(g):
    return (field(g, "Text/LocaText/English/Text") or field(g, "Standard/Name")).strip()


def product_refs(asset, path):
    container = prop(asset, path)
    if container is None:
        return set()
    return {int(p.text) for p in container.findall("Item/Product") if p.text}


# The trading post is the whitelist for normal goods. The oil harbour, regional
# post offices and tractor fuel stations handle the remaining physical freight.
def storage_goods(asset):
    return product_refs(asset, "ProductStorageList/ProductList")


mail_stores = {"Old-World": 745, "New-World": 4254, "Arctic": 4269}
freight = storage_goods(120055) | storage_goods(120056)
for storage in mail_stores.values():
    freight.update(storage_goods(storage))
assert tractor_fuel in product_refs(118571, "FactoryBase/FactoryOutputs")
freight.add(tractor_fuel)
# Some entries in vanilla's storage list point to retired GUIDs.
freight = {g for g in freight if g in assets and prop(g, "Product") is not None
           and field(g, "Product/IsAbstract") != "1"}
products = {}
workshops = {"Old-World": 77, "Arctic": 117422}
for region, code in region_names.items():
    goods = set(needs[region])
    if region in mail_stores:
        goods.update(storage_goods(mail_stores[region]))
    for source in regions[region] | regional_factories[region]:
        goods.update(product_refs(source, "FactoryBase/FactoryInputs"))
        goods.update(product_refs(source, "FactoryBase/FactoryOutputs"))
        goods.update(product_refs(source, "Cost/Costs"))
    if region in workshops:
        recipes = prop(workshops[region], f"ItemCrafter/CraftableItemsInRegion/{code}/CraftableItems")
        for recipe in recipes.findall("Item/Item"):
            if int(recipe.text) in assets:
                goods.update(product_refs(int(recipe.text), "CraftableItem/CraftingCosts"))
    for g in freight:
        production = prop(g, "Product/ProductionRegions")
        if (code in field(g, "Product/AssociatedRegion").split(";") or
                (production is not None and any(n.text == code for n in production.findall("Item/RegionType")))):
            goods.add(g)
    # The first Enbesa edition also supplied Leather Boots, an Old World scholar good.
    if region == "Enbesa":
        goods.add(114428)
    products[region] = sorted(goods & freight, key=product_name)
# Preserve the original 52-goods Jack and the earlier personal Lodge edition's
# 76 goods; players can remove the legacy mods and still receive those outputs.
original_jack = {
    1010223, 1010214, 120037, 1010213, 1010205, 1010217, 1010255, 135150, 118724, 120016,
    1010258, 1010259, 114414, 120032, 114359, 135130, 114401, 1010200, 120033, 1010247,
    114371, 1010248, 114390, 117698, 1010250, 135129, 117699, 114428, 1010208, 114402,
    117702, 1010245, 1010246, 120043, 1010202, 1010257, 1010238, 1010216, 114410, 1010206,
    1010203, 120030, 1010225, 1010224, 1010218, 1010239, 114430, 114404, 120035, 1010221,
    1010207, 1010237,
}
original_lodge = original_jack | set(range(112694, 112707)) | {
    115980, 120008, 1010226, 1010233, 4268, 838, 1010234, 25506, 5390, 1010222, 6600,
}
assert len(original_jack) == 52 and len(original_lodge) == 76 and original_lodge <= freight
extra_imports = {}
for region, legacy in (("Old-World", original_jack), ("Arctic", original_lodge)):
    extra_imports[region] = sorted(legacy.difference(products[region]), key=product_name)
    products[region] = sorted(set(products[region]) | legacy, key=product_name)
products["Harbour"] = sorted(set().union(*products.values()), key=product_name)
assert set(products["Harbour"]) == freight, "An island good has no regional assignment"


def goods_catalog(guids):
    groups = defaultdict(list)
    for g in guids:
        category = int(field(g, "Product/ProductCategory"))
        category_name = field(category, "Standard/Name").removeprefix("Product Category ")
        groups[category_name].append(product_name(g))
    return "\n".join(f"- **{category}** - " + ", ".join(sorted(names)) + "."
                     for category, names in sorted(groups.items()))


def new_asset(root, template, anchor, guid, name):
    assert guid not in assets and template in templates and anchor in assets
    n = add(add(root, "ModOp", Type="addNextSibling", GUID=str(anchor)), "Asset")
    add(n, "Template", template)
    v = add(n, "Values")
    fields(add(v, "Standard"), GUID=guid, Name=name)
    return v


def target_pool(root, text, guid, name, targets):
    assert targets and all(g in assets for g in targets)
    v = new_asset(root, "ItemEffectTargetPool", 193856, guid, name)
    cont = add(add(v, "ItemEffectTargetPool"), "EffectTargetGUIDs")
    for g in sorted(targets):
        item(cont, GUID=g)
    text[guid] = name
    return guid


def add_pool_offer(root, pool, guid):
    assert template_name(pool) in ("RewardItemPool", "RewardPool")
    n = add(root, "ModOp", GUID=str(pool), Type="add", Path="/Values/RewardPool/ItemsPool",
            Condition=f"!/Values/RewardPool/ItemsPool[Item/ItemLink='{guid}']")
    item(n, ItemLink=guid, Weight=1)


def power(v, heater=False):
    n = add(v, "IndustrializableUpgrade")
    if heater:
        add(n, "ProvidedIndustrializationType", "Heater")
    add(n, "ProvideIndustrialization", 1)


def make_texts(folder, text):
    data = ET.Element("ModOps")
    texts = add(data, "ModOp", Type="add", Path="/TextExport/Texts")
    for guid, label in text.items():
        fields(add(texts, "Text"), GUID=guid, Text=label)
    xml(data, folder / gui_dir / "specialist-texts.include.xml")
    for lang in "brazilian chinese english french german italian japanese korean polish portuguese russian spanish taiwanese".split():
        patch = ET.Element("ModOps")
        add(patch, "Include", File="specialist-texts.include.xml")
        xml(patch, folder / gui_dir / f"texts_{lang}.xml")


def template_support(folder, template, v):
    missing = sorted({n.tag for n in v if templates[template].find(n.tag) is None})
    if not missing:
        return
    root = ET.Element("ModOps")
    for tag in missing:
        p = f"//Template[Name='{template}']/Properties"
        op = add(root, "ModOp", Type="add", Path=p, Condition=p + f"[not({tag})]")
        add(op, tag)
    xml(root, folder / asset_dir / "templates.xml")


names = ["Jack of All Trades", "Jack of Both Tropics", "Jack of All Lions", "Jack of All Lodges", "Jack of All Seas", "Robin Vale, the Field Naturalist",
         "Evelyn Reed, the Borough Steward", "Ines Solano, the Community Steward", "Tadesse, Steward of the Highlands", "Sila, Keeper of the Hearth", "Marina Wells, the Harbour Steward",
         "Dr Rowan Pike, Expedition Polymath", "Captain Mara Voss, Fleet Gunnery Officer", "Ellis Ward, the Cargo Purser",
         "Robin Vale, the Field Naturalist (Grand Fields)"]
portraits = [191355, 190621, 125132, 4272, 190622, 190692,
             191470, 113800, 118103, 1772, 190679, 191450, 191608, 191622, 190692]
regions_order = ["Old-World", "New-World", "Enbesa", "Arctic", "Harbour"]
slugs = ["Production-" + r for r in regions_order] + ["Agriculture"] + \
    ["Needs-" + r for r in regions_order] + ["Ship-Expedition", "Ship-Combat", "Ship-Cargo", "Agriculture-Grand-Fields"]
introductions = {
    "Production-Old-World": (
        "I made Jack an optional shortcut for the point when an Old World city starts asking for steam carriages, "
        "telephones and elevators at once. A working factory with Jack can supply the full Old World goods catalogue."
    ),
    "Production-New-World": (
        "I wanted to build up a New World island without waiting for every specialist production line to come online. "
        "Jack brings the complete New World goods catalogue into each cycle, so you can choose which islands get that head start."
    ),
    "Production-Enbesa": (
        "I wanted Enbesa to have a Jack of its own. With him at work, a single producer can also turn out lanterns, "
        "leather boots and illuminated scripts, enough to spare you several supply chains."
    ),
    "Production-Arctic": (
        "I made Jack for the moment when a new Arctic settlement needs warm shelters, parkas and sleds all at once. "
        "Giving him his own Lodge slot lets you decide which settlement gets through that first winter so easily."
    ),
    "Production-Harbour": (
        "I wanted a busy fishing coast to be able to bankroll an entire port. Jack turns production cycles into a "
        "source of goods from all four regions, so equipping him is a deliberate choice about how quickly that port grows."
    ),
    "Agriculture": (
        "I designed Robin for islands where one more plantation would swallow the last good piece of farmland. "
        "With Robin equipped, a crop or livestock farm can work from its main building alone."
    ),
    "Agriculture-Grand-Fields": (
        "Sometimes the fields themselves are what I want to build. This edition of Robin lets me lay out a huge "
        "vineyard or a sweep of cattle pasture while keeping the shorter forest spacing and agricultural bonus goods."
    ),
    "Needs-Old-World": (
        "I made Evelyn for players who want to keep building an Old World city after the shopping lists become the "
        "hardest part. She can supply a district of workers, scholars or tourists, so you choose where delivery routes still matter."
    ),
    "Needs-New-World": (
        "I wanted the choice to grow a New World neighbourhood without continually adding deliveries as residents "
        "move up through the tiers. Give Ines a Town Hall slot wherever you want that relief."
    ),
    "Needs-Enbesa": (
        "I wanted an Enbesan town to be able to grow even when its supply of everyday goods falls behind. "
        "Tadesse puts that choice in the Town Hall, so other settlements can still depend on their farms and workshops."
    ),
    "Needs-Arctic": (
        "I made Sila for Arctic settlements that I wanted to keep alive through a missed delivery. Her Lodge can take "
        "over both supplies and heat, which makes surviving the cold a much smaller part of managing that settlement."
    ),
    "Needs-Harbour": (
        "I wanted a single harbour posting for players who enjoy building a port more than keeping its residents "
        "supplied. Marina can take over most household deliveries within reach of her office in any of the four regions."
    ),
    "Ship-Expedition": (
        "I made Rowan for voyages where I wanted to see the next expedition event without having to assemble a "
        "whole crew for its skill checks. You decide which expedition gets that advantage when you choose its crew."
    ),
    "Ship-Combat": (
        "I wanted one warship to be able to carry a fight when the odds were against it. Assign Mara to the ship "
        "you want to strengthen, whether that is a lone escort or the flagship of a larger fleet."
    ),
    "Ship-Cargo": (
        "I wanted a long trade route to work with fewer ships. Ellis makes that possible by cutting travel and "
        "loading time, and you can assign the purser to just the route that needs help."
    ),
}
jack_mod = "[JACK OF ALL TRADES](https://www.nexusmods.com/anno1800/mods/457)"
orchard_mod = "[Boost Orchard Production](https://www.nexusmods.com/anno1800/mods/151)"
fertility_mod = "[Remove Fertility Need](https://www.nexusmods.com/anno1800/mods/83)"
credits = {
    "Production-Old-World": (
        "Thank you, blejky, for the original Old World Jack. The idea of one specialist yielding several useful goods "
        "each cycle was the starting point for every Jack in this collection. Please give the original Jack a visit. "
        f"{jack_mod}\n\n"
        "I'm also grateful to apjarnold for showing what an orchard production boost could do, and to BattleForte for "
        "extending item effects to industries such as chemicals and telephones. Both ideas helped me decide which "
        f"producers my Jack should reach. {orchard_mod} and "
        "[Orchard, Chemicals and Telephone Production Boosted by Items](https://www.nexusmods.com/anno1800/mods/153)"
    ),
    "Production-New-World": (
        "Thanks to blejky for the many-goods-per-cycle idea that I brought to the New World, and to apjarnold for "
        "putting orchard productivity on my list. If you enjoy what Jack does for a New World island, please visit "
        f"the two mods that led me there. {jack_mod} and {orchard_mod}"
    ),
    "Production-Enbesa": (
        "I owe the idea of this Enbesan Jack to two authors. Thank you to blejky for the original all-purpose "
        "producer and to FrankRogers for exploring what faster production could mean for the Land of Lions. "
        f"Please take a look at both originals. {jack_mod} and "
        "[Land of Lions LoL Production Hack](https://www.nexusmods.com/anno1800/mods/72)"
    ),
    "Production-Arctic": (
        "Thank you to blejky, whose Old World Jack gave me the idea of sending bonus goods to storage with each "
        "completed cycle. That idea was what I wanted to bring into my Arctic Lodge work, with local supplies "
        f"and heat for a polar settlement. Please pay the original Jack a visit. {jack_mod}"
    ),
    "Production-Harbour": (
        "Thank you, blejky, for giving an Old World specialist the ability to turn each production cycle into "
        "several different goods. I wanted to see what that would feel like when the specialist worked from the "
        f"waterfront. Jack of All Seas grew from your idea. {jack_mod}"
    ),
    "Agriculture": (
        "I'm grateful to apjarnold for exploring two questions that shaped Robin. Where should players be able to "
        "plant, and how much can an orchard produce on the land it has? Robin brings those ideas to a specialist "
        f"you can assign to a farm district. Please visit the original farming mods. {fertility_mod} and {orchard_mod}"
    ),
    "Ship-Expedition": (
        "Thank you to kuroki1216 for the idea of putting many expedition traits on a single crew member. "
        "That was the starting point for Rowan's mix of skills, perks and morale. If you enjoy taking Rowan to sea, "
        "please visit [Jack of all Traits](https://www.nexusmods.com/anno1800/mods/63)."
    ),
    "Ship-Combat": (
        "I'm grateful to JannisAMV for showing how much one equipped item could change a battleship's role in a "
        "fight. That idea led me to build a gunnery officer around damage, reload time and range. Please visit the "
        "original [OP Battleship Item](https://www.nexusmods.com/anno1800/mods/609)."
    ),
}
needs_credit = (
    "Thank you to taesanjung for the idea of having a specialist supply the luxuries a neighbourhood would "
    "otherwise need delivered. That was my starting point for the regional stewards. "
    "[Specialist All Luxury Goods Provided](https://www.nexusmods.com/anno1800/mods/76)\n\n"
    "I'm grateful to Alxx15 for exploring what higher residential capacity and more influence could do for a "
    "growing city. I brought those ideas together here so players could choose where to use them. Please visit "
    "the original [Population Density](https://www.nexusmods.com/anno1800/mods/60) and "
    "[Influence Boost](https://www.nexusmods.com/anno1800/mods/210) mods."
)

for i, slug in enumerate(slugs):
    guid = 2141000000 + i * 10
    large_fields = slug == "Agriculture-Grand-Fields"
    agriculture = slug == "Agriculture" or large_fields
    group, separator, subject = slug.partition("-")
    folder_label = group + " - " + subject.replace("-", " ") if separator else group
    folder = dest / ("[Specialist] " + folder_label)
    text = {}
    root = ET.Element("ModOps")
    region = next((r for r in regions_order if slug.endswith("-" + r)), None)
    allocations = {"Harbour": "HarborOffice", "Arctic": "Lodge"}
    allocation = allocations.get(region, "TownHall" if slug.startswith("Needs") else "GuildHouse")
    if slug.startswith("Ship"):
        allocation = "Warship" if slug == "Ship-Combat" else "Ship"
    template = {"HarborOffice": "HarborOfficeItem", "TownHall": "TownhallItem",
                "Ship": "ShipSpecialist", "Warship": "ShipSpecialist"}.get(allocation, "GuildhouseItem")
    anchor = {"GuildhouseItem": 191388, "HarborOfficeItem": 190695,
              "TownhallItem": 191470, "ShipSpecialist": 191608}[template]
    socket = {"GuildHouse": "Trade Union", "TownHall": "Town Hall", "HarborOffice": "Harbourmaster's Office",
              "Lodge": "Arctic Lodge", "Ship": "ship", "Warship": "warship"}[allocation]
    location = ("an " if socket == "Arctic Lodge" else "a ") + socket
    dlc = {"Arctic": 410042, "Enbesa": 410071}.get(region)
    pools = [192909]
    seller = "Look for a legendary specialist at Eli Bleakworth's prison once legendary offers are unlocked."
    if region == "New-World":
        pools = [192904]
        seller = "Look for a legendary specialist at Isabel Sarmento's harbour once legendary offers are unlocked."
    if region == "Enbesa":
        pools = [127466, 127476, 127477, 127478, 127479, 127480]
        seller = "The specialist can appear at Emperor Ketema's harbour in Enbesa."
    if region == "Arctic":
        pools = [193845]
        seller = "Craft the specialist at Old Nate's Arctic workshop for one Lost Expedition Scrap, or check Qumaq's legendary offers."
    if slug.startswith("Ship"):
        pools = [192899, 192919, 192909]
        seller = "Look for legendary offers from Eli Bleakworth, Anne Harlow or Jean La Fortune. Trading with a pirate requires trade rights."
    if agriculture:
        seller += " The Lodge edition is also craftable for one Lost Expedition Scrap at Old Nate's Arctic workshop."
    v = new_asset(root, template, anchor, guid, names[i])
    standard = v.find("Standard")
    fields(standard, IconFilename=field(portraits[i], "Standard/IconFilename"), InfoDescription=guid + 1)
    fields(add(v, "Item"), Allocation=allocation, Rarity="Legendary",
           ItemType="Specialist", MaxStackSize=1, OnlyEquippableOnce=1, TradePrice=350000)
    lock = add(v, "Locked")
    add(lock, "DefaultLockedState", 0)
    if dlc:
        add(lock, "DLCDependency", dlc)
    targets = set()
    if slug.startswith("Production"):
        if region == "Harbour":
            targets = coastal | set.union(*power_targets.values()) | set.union(*houses.values())
            pool_name = "Coastal producers and buildings that use power"
        else:
            targets = regional_factories[region] | power_targets[region] | houses[region]
            pool_name = region.replace("-", " ") + " production and utility buildings"
        bonus = add(v, "FactoryUpgrade")
        upgrade(bonus, "ProductivityUpgrade", 100)
        extra = add(bonus, "AdditionalOutput")
        for g in products[region]:
            item(extra, Product=g, AdditionalOutputCycle=1, Amount=1)
        power(v, region == "Arctic")
        if region != "Arctic":
            item(add(add(v, "ResidenceUpgrade"), "GoodConsumptionUpgrade"),
                 ProvidedNeed=1010354, AmountInPercent=-100)
        utility = "heat" if region == "Arctic" else "electricity"
        scope = "across all four regions" if region == "Harbour" else "in the " + region.replace("-", " ") + " catalogue"
        description = (f"Provides {utility} to compatible buildings. Every completed production cycle adds one ton "
                       f"of each of the {len(products[region])} goods {scope}. Productivity +100%.")
        details = f"Equip in {location}. {description} Each eligible producer must finish a cycle to generate its extras."
        if region == "Harbour":
            details += " Covers coastal producers and power-using factories within the office's coverage, including eligible inland factories."
        details += ("\n\n## Bonus goods per cycle\n\n"
                    "The catalogue includes physical island goods assigned to the region, used by its residents "
                    "or used in local production and construction. "
                    "Shared goods and imports can appear in several regions.")
        if region in workshops or region == "Harbour":
            details += " Jack also supplies materials used in Old Nate's workshop recipes."
        if region == "Enbesa":
            details += " Jack keeps supplying Leather Boots from the earlier Enbesa edition."
        if tractor_fuel in products[region]:
            details += (" This module lets the trading post store bonus tractor fuel. Tractor barns still receive "
                        "fuel carts from an operating Fuel Station.")
        if 1010566 in products[region]:
            details += " Oil still uses the oil harbour's dedicated storage."
        if region in mail_stores or region == "Harbour":
            details += " Mail and reports use the game's postal storage and delivery rules."
        if region in extra_imports:
            historical = "original Old World specialist" if region == "Old-World" else "earlier Arctic Lodge specialist"
            details += (f"\n\nThe {historical} also supplied goods from other regions. Jack keeps its extra imports of "
                        + ", ".join(map(product_name, extra_imports[region])) + " alongside today's regional catalogue.")
        details += "\n\n" + goods_catalog(products[region])
    elif slug.startswith("Needs"):
        rs = tiers.keys() if region == "Harbour" else [region]
        goods = set.union(*(needs[r] for r in rs))
        subs = set.union(*(services[r] for r in rs))
        targets = set.union(*(houses[r] | power_targets[r] for r in rs))
        pool_name = ("Regional" if region == "Harbour" else region.replace("-", " ")) + \
            " residences and utility buildings"
        residence = add(v, "ResidenceUpgrade")
        add(residence, "AdditionalHappiness", 25)
        supply = add(residence, "GoodConsumptionUpgrade")
        for g in sorted(goods):
            item(supply, ProvidedNeed=g, AmountInPercent=-100)
        replacement = add(residence, "NeedProvideNeedUpgrade")
        for g, s in sorted(subs):
            item(replacement, ProvidedNeed=g, SubstituteNeed=s)
        population = add(v, "PopulationUpgrade")
        upgrade(population, "ResidentsUpgrade", 100)
        # Vanilla population items also assign additional residents to individual fulfilled needs.
        inputs = add(population, "InputBenefitModifier")
        # Give staple needs an occupancy bonus to help fill the additional capacity.
        for s in sorted({staples[t] for r in rs for t in tiers[r]}):
            item(inputs, Product=s, AdditionalSupply=10)
        illness = add(v, "IncidentInfectableUpgrade")
        for tag in ["IncidentIllnessIncreaseUpgrade", "IncidentRiotIncreaseUpgrade", "IncidentArcticIllnessIncreaseUpgrade"]:
            upgrade(illness, tag, -100)
        inf = add(v, "InfluenceSourceUpgrade")
        upgrade(inf, "InfluenceAmounUpgrade", 3, False)
        power(v, region == "Arctic")
        description = "Fulfils unlocked basic, luxury and enabled lifestyle needs, raises happiness by 25 and doubles residence capacity."
        details = f"Equip in {location}. {description} Covers {len(goods)} distinct needs. " + ("Grants heater service to eligible buildings. " if region == "Arctic" else "Provides electricity to compatible buildings. ") + ("Arctic heat is included among the residence needs. " if region in (
            "Arctic", "Harbour") else "") + "Gives +3 influence to affected buildings with an influence source. Reduces riot, illness and Arctic flu risk by 100% wherever those incidents exist. Public services can also be satisfied by a local staple supplied by the specialist. Tier unlocks and lifestyle activation still apply."
    elif agriculture:
        targets = farms
        pool_name = "Agricultural producers, woodland businesses, fisheries and Fuel Stations"
        f = add(v, "FactoryUpgrade")
        upgrade(f, "ProductivityUpgrade", 100)
        upgrade(f, "NeededAreaPercentUpgrade", -100, False)
        extra = add(f, "AdditionalOutput")
        for g in sorted(farm_goods):
            item(extra, Product=g, AdditionalOutputCycle=1, Amount=1)
        # The native modifier is additive. The negative margin offsets tractors and other
        # field-increasing equipment before the engine clamps the required count to zero.
        add(add(v, "ModuleOwnerUpgrade"), "ModuleLimitPercent", 500 if large_fields else -400)
        upgrade(add(v, "BuildingUpgrade"), "WorkforceAmountUpgrade", -50)
        field_summary = ("+500% field and pasture capacity." if large_fields
                         else "Crop fields and animal pens are optional.")
        description = (f"{field_summary} +100% productivity, -100% required forest/free area and -50% workforce "
                       f"on compatible buildings. Adds one ton of each of {len(farm_goods)} agricultural goods per completed cycle.")
        if large_fields:
            # Pen size and placement radius are building properties. Preserve larger existing radii.
            # Some farms inherit a radius of ten from their template and have no radius node of their own.
            op = add(root, "ModOp", Type="merge", GUID=",".join(map(str, animal_pen_owners)),
                     Path="/Values/ModuleOwner[not(ModuleBuildRadius) or (ModuleBuildRadius > 0 and ModuleBuildRadius < 40)]",
                     AllowNoMatch="1")
            add(op, "ModuleBuildRadius", 40)
            layout = ("With Robin equipped, a grain farm can place up to 864 fields in place of its usual 144, "
                      "and a sheep farm up to 18 pens in place of three, before other modifiers. Anno also uses "
                      "the expanded module count as the target for full productivity. You can work a smaller layout "
                      "at partial utilisation. Installing Grand Fields extends livestock pen placement to 40 tiles "
                      "even when Robin is unequipped. The extra field and pen count requires Robin.")
        else:
            layout = ("The farm's main building can operate with zero crop fields or animal pens. The item tooltip "
                      "shows a -400% module modifier. That leaves room for up to +300% from tractors and other "
                      "field modifiers while keeping the effective requirement at zero.")
        details = (f"{description} {layout}\n\nEquip one Robin variant per catchment. The field modifiers add "
                   "together if you overlap both editions. Place the Trade Union item in the Old World, Cape "
                   "Trelawney, New World or Enbesa, and the Lodge item in the Arctic. Both editions require the Free Fertility module, "
                   "which removes regional fertility requirements for all supported crops. "
                   "The woodland bonus also reaches lumberjacks, hunters, charcoal kilns, Wanza woodcutters and orchards."
                   f"\n\n## Bonus goods\n\nThe catalogue combines the game's regional agricultural lists, the "
                   "outputs of the covered producers, farm supplies and common farm-processing ingredients. "
                   "Fuel uses the physical Bright Harvest product. The module adds a warehouse slot for bonus fuel. "
                   "Keep an operating Fuel Station connected to tractor barns for their local cart deliveries."
                   "\n\n" + ", ".join(sorted(product_name(g) for g in farm_goods)) + ".")
    elif slug == "Ship-Expedition":
        expedition = add(v, "ExpeditionAttribute")
        add(expedition, "BaseMorale", 100)
        attrs = add(expedition, "ExpeditionAttributes")
        skills = "Crafting Diplomacy Faith Hunting Medicine Melee Might Navigation".split()
        perks = "PerkMale PerkFemale PerkAnthropologist PerkArcheologist PerkDiver PerkEntertainer PerkFormerPirate PerkHypnotist PerkJackOfAllTraits PerkPolyglot PerkZoologist".split()
        for a in skills:
            item(attrs, Attribute=a, Amount=100)
        for a in perks:
            item(attrs, Attribute=a, Amount=1)
        add(expedition, "ItemDifficulties", "Easy;Average;Hard")
        description = "Adds 100 morale, 100 points in all eight expedition disciplines and eleven character perks."
        details = description + \
            " Equip or take this specialist along when preparing an expedition. Ship-type checks still depend on the vessel."
    elif slug == "Ship-Combat":
        gunnery = add(v, "AttackerUpgrade")
        upgrade(gunnery, "BaseDamageUpgrade", 150)
        upgrade(gunnery, "ReloadTimeUpgrade", -40)
        upgrade(gunnery, "AttackRangeUpgrade", 30)
        upgrade(gunnery, "LineOfSightRangeUpgrade", 30)
        upgrade(gunnery, "AccuracyUpgrade", 100)
        add(gunnery, "AttackSpeedUpgrade", 25)
        item(add(gunnery, "HitpointDamage"), MinDamageFactor=1.6)
        damage_targets = add(gunnery, "DamageFactor")
        for target in ("SailShip", "Building"):
            add(add(damage_targets, target), "Factor", 1.5)
        hull = add(v, "AttackableUpgrade")
        upgrade(hull, "MaxHitpointsUpgrade", 1000, percent=False)
        upgrade(hull, "SelfHealUpgrade", 500)
        upgrade(hull, "SelfHealPausedTimeIfAttackedUpgrade", -100)
        protection = add(hull, "DamageReceiveFactor")
        for damage, factor in (("Normal", 0.75), ("Torpedo", 0.2), ("Cannon", 0.2), ("BigBertha", 0.2)):
            add(add(protection, damage), "Factor", factor)
        # A single HP modifier supports one unit. Apply the original percentage via a local one-item set.
        add(v.find("Item"), "ItemSet", guid + 2)
        crew_set = new_asset(root, "ItemSet", 191114, guid + 2, "Mara's reinforced hull")
        fields(add(crew_set, "ItemSocketSet"), SetBuff=guid + 3, BuffScope="Local")
        hull_buff = new_asset(root, "VehicleBuff", 6000032, guid + 3, "Reinforced warship hull")
        upgrade(add(hull_buff, "AttackableUpgrade"), "MaxHitpointsUpgrade", 100)
        text[guid + 2] = "Mara's reinforced hull"
        text[guid + 3] = "Reinforced warship hull"
        propulsion = add(v, "VehicleUpgrade")
        upgrade(propulsion, "ForwardSpeedUpgrade", 30)
        upgrade(propulsion, "IgnoreDamageFactorUpgrade", 100)
        description = ("Active Healing keeps self-repair running under fire at +500% repair rate. "
                       "Unwavering raises damage as hull strength falls, up to 1.6 times normal. "
                       "Adds 1,000 hit points and a local +100% maximum hull bonus.")
        details = ("Equip Mara on a warship. " + description +
                   " Guns gain +150% base damage, +100% accuracy, +25 attack speed, -40% reload time "
                   "and +30% range. Damage against sailing ships and buildings rises by 50%. "
                   "Incoming normal damage falls by 25%, and cannon, torpedo and Big Bertha damage by 80%. "
                   "The ship gains +30% sight and movement speed and ignores the speed penalty from hull damage.")
    else:
        vehicle = add(v, "VehicleUpgrade")
        for tag, n in [("ForwardSpeedUpgrade", 60), ("IgnoreWeightFactorUpgrade", 100), ("IgnoreDamageFactorUpgrade", 100)]:
            upgrade(vehicle, tag, n)
        trade = add(v, "TradeShipUpgrade")
        add(trade, "ActiveTradePriceInPercent", 70)
        upgrade(trade, "LoadingSpeedUpgrade", 150)
        description = "Adds 60% sailing speed and 150% loading speed, removes cargo and damage slowdown and sets active purchase prices to 70%."
        details = description + " Equip in a ship item slot before shopping at a trader or assigning the ship to a trade route."
    if targets:
        pool_id = guid + 4
        target_pool(root, text, pool_id, pool_name, targets)
        item(add(add(v, "ItemEffect"), "EffectTargets"), GUID=pool_id)
    for pool in pools:
        add_pool_offer(root, pool, guid)
    text[guid] = names[i]
    text[guid + 1] = description
    if agriculture or (slug.startswith("Production-") and tractor_fuel in products[region]):
        fuel_path = "/Values/ProductStorageList/ProductList"
        fuel_op = add(root, "ModOp", Type="add", GUID="120055", Path=fuel_path,
                      Condition=f"!//Asset[Values/Standard/GUID='120055']{fuel_path}/Item[Product='{tractor_fuel}']")
        item(fuel_op, Product=tractor_fuel)
    if allocation == "Lodge" or agriculture:
        if agriculture:
            from copy import deepcopy
            alt = deepcopy(v)
            root.find("ModOp").append(ET.Element("Asset"))
            a = root.find("ModOp")[-1]
            add(a, "Template", template)
            a.append(alt)
            alt.find("Standard/GUID").text = str(guid + 2)
            alt.find("Standard/Name").text = names[i] + " (Lodge)"
            alt.find("Standard/InfoDescription").text = str(guid + 3)
            alt.find("Item/Allocation").text = "Lodge"
            add(alt.find("Locked"), "DLCDependency", 410042)
            text[guid + 2] = names[i] + " (Lodge)"
            text[guid + 3] = "Arctic Lodge edition. " + description
            add_pool_offer(root, 193845, guid + 2)
            crafter = alt
            craft_guid = guid + 2
        else:
            crafter = v
            craft_guid = guid
        item(add(add(crafter, "CraftableItem"), "CraftingCosts"), Product=115980, Amount=1)
        offer = add(root, "ModOp", Type="add", GUID="117422",
                    Path="/Values/ItemCrafter/CraftableItemsInRegion/Arctic/CraftableItems")
        item(offer, Item=craft_guid)
    xml(root, folder / asset_dir / "assets.xml")
    make_texts(folder, text)
    template_support(folder, template, v)
    modid = "vinzenz-specialist-" + slug.lower()
    title = "[Specialist] " + names[i]
    introduction = introductions[slug]
    version = "1.1.0" if slug.startswith("Production-") or slug == "Agriculture" else "1.0.0"
    if slug == "Ship-Combat":
        version = "1.1.0"
    meta(folder, modid, title, introduction + "\n\n" + description, version=version, **({"ModDependencies": ["vinzenz-rules-free-fertility"]} if agriculture else {}))
    acknowledgement = needs_credit if slug.startswith("Needs-") else credits.get("Agriculture" if agriculture else slug)
    if agriculture:
        acknowledgement += ("\n\nThank you to Incipium for documenting how tractors interact with field-reduction items "
                            "and how specialists can reduce the area needed by forestry buildings. "
                            "[Variable Fields & Areas](https://incipium.github.io/Anno1800Modding/#variable-fields--areas)")
    lines = [f"# {title}", introduction, COLLECTION_NOTE, details, "## Availability", seller + " The bundle's optional trader and Research Institute modules add further acquisition routes.",
             "## Installation", f"Copy the entire `{folder.name}` folder into Anno 1800's `mods` folder and enable it in the mod browser."]
    if region == "Enbesa":
        lines.append("Playing in Enbesa requires Land of Lions.")
    elif region == "Arctic":
        lines.append("Playing in the Arctic requires The Passage.")
    if acknowledgement:
        lines.extend(["## With thanks", acknowledgement])
    (folder / "README.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(slug, len(targets))

folder = dest / "[Rules] Free Fertility"
root = ET.Element("ModOps")
# Patch the specific field instead of replacing factory production and its other requirements.
groups = defaultdict(list)
for guid in fertility_buildings:
    groups[field(guid, "Factory7/NeededFertility")].append(guid)
for fertility, ids in sorted(groups.items(), key=lambda pair: int(pair[0])):
    root.append(ET.Comment(" " + field(int(fertility), "Standard/Name") + " "))
    op = add(root, "ModOp", Type="merge", GUID=",".join(map(str, sorted(ids))), Path="/Values")
    add(add(op, "Factory7"), "NeededFertility", 0)
xml(root, folder / asset_dir / "assets.xml")
intro = ("I wanted the freedom to choose a farm island for its coastline and layout, even when its soil was wrong "
         "for a favourite crop. This rule makes that possible across the four standard regions. I kept it separate "
         "because choosing islands for their fertilities can be half the fun of settling them.")
meta(folder, "vinzenz-rules-free-fertility", folder.name, intro, "Agriculture")
(folder / "README.md").write_text("\n\n".join([
    f"# {folder.name}", intro, COLLECTION_NOTE,
    "Farms and producers can operate on islands lacking their normal fertility. Physical deposits, fields, "
    "pastures, irrigation and other inputs still follow the building rules. This change works independently of "
    "Robin Vale and applies to existing buildings.",
    "## Installation", f"Copy `{folder.name}` into Anno 1800's `mods` folder and enable it in the mod browser.",
    "## With thanks", "Thank you to apjarnold for asking what a farm could do if the island's fertility no longer "
    "dictated where it went. That idea gave this rule its purpose. Please pay the original mod a visit. " + fertility_mod,
]) + "\n", encoding="utf-8")
folder = dest / "[Legacy] Lodge Portraits"
root = ET.Element("ModOps")
op = add(root, "ModOp", Type="merge", GUID="2001000104", Path="/Values/Standard",
         Condition="//Values[Standard/GUID='2001000104']/Standard[IconFilename='data/ui/2kimages/main/3dicons/specialists/systemic/icon_engineer_501.png']")
add(op, "IconFilename", field(4272, "Standard/IconFilename"))
xml(root, folder / asset_dir / "assets.xml")
title = "[Legacy] Aput's Lodge Portrait"
intro = ("I wanted players returning to an older Arctic settlement to recognise Aput in their Lodge again. "
         "You can use this portrait repair with the original Arctic Lodge Specialists, even if you skip "
         "every gameplay cheat in the collection.")
meta(folder, "vinzenz-legacy-lodge-portraits", title, intro, "Compatibility",
     LoadAfterIds=["vinzenz_arctic_lodge_specialists"])
(folder / "README.md").write_text("\n\n".join([
    f"# {title}", intro, COLLECTION_NOTE,
    "The patch recognises Aput, the Eternal Hearth (2001000104), and replaces the missing engineer icon with "
    "the game's Arctic Science Reporter portrait. Existing copies retain their item identity. The patch activates "
    "only if the original missing icon is still assigned.",
    "## Installation", f"Copy `{folder.name}` into Anno 1800's `mods` folder alongside the original Arctic Lodge Specialists.",
]) + "\n", encoding="utf-8")
print("Fertility", len(fertility_buildings), "groups", len(groups))
