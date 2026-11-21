"""Check the production catalogues and both farm editions in a merged Anno assets.xml."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


REGIONS = {
    "Moderate": 2141000000,
    "Colony01": 2141000010,
    "Africa": 2141000020,
    "Arctic": 2141000030,
}
HARBOUR = 2141000040
FARM_EDITIONS = {2141000050: "GuildHouse", 2141000052: "Lodge",
                2141000140: "GuildHouse", 2141000142: "Lodge"}
ISLAND_STORAGE = {120055, 120056, 745, 4254, 4269}
AGRICULTURE_LISTS = {502037, 502038, 502039, 502076}
TRACTOR_FUEL = 270042


def product_ids(nodes):
    return {int(n.text) for n in nodes}


def outputs(values):
    rows = values.findall("FactoryUpgrade/AdditionalOutput/Item")
    goods = {int(row.findtext("Product")) for row in rows}
    assert len(rows) == len(goods), "A product is listed twice"
    assert all(row.findtext("AdditionalOutputCycle") == row.findtext("Amount") == "1" for row in rows)
    return goods


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("merged_assets", type=Path, help="assets.xml after applying the standard bundle")
    args = parser.parse_args()
    expected_people = set(REGIONS.values()) | {HARBOUR} | FARM_EDITIONS.keys()
    items, targets, physical = {}, {}, {}
    freight, agriculture = {TRACTOR_FUEL}, set()
    storage_fuel_entries = 0
    # Nandu and New World cattle inherit a smaller placement radius from the template in vanilla.
    pen_radii = {}
    for _, asset in ET.iterparse(args.merged_assets):
        if asset.tag != "Asset" or asset.find("Values/Standard/GUID") is None:
            continue
        values = asset.find("Values")
        guid = int(values.findtext("Standard/GUID"))
        if guid in expected_people:
            assert guid not in items
            items[guid] = values
        if guid in ISLAND_STORAGE:
            freight.update(product_ids(values.findall("ProductStorageList/ProductList/Item/Product")))
        if guid == 120055:
            storage_fuel_entries = sum(row.text == str(TRACTOR_FUEL)
                                       for row in values.findall("ProductStorageList/ProductList/Item/Product"))
        if values.findtext("ModuleOwner/FarmType") == "AnimalFarm":
            pen_radii[guid] = int(values.findtext("ModuleOwner/ModuleBuildRadius", "0"))
        if guid in AGRICULTURE_LISTS:
            agriculture.update(product_ids(values.findall("ProductList/List/Item/Product")))
        product = values.find("Product")
        if product is not None and product.findtext("IsAbstract") != "1":
            associated = set(product.findtext("AssociatedRegion", "").split(";"))
            production = {n.text for n in product.findall("ProductionRegions/Item/RegionType")}
            physical[guid] = associated | production
        if asset.findtext("Template") == "ItemEffectTargetPool":
            targets[guid] = product_ids(values.findall("ItemEffectTargetPool/EffectTargetGUIDs/Item/GUID"))
        asset.clear()

    assert items.keys() == expected_people, "Missing Jack or farm specialist in merged assets"
    assert storage_fuel_entries == 1, "Fuel providers must share one island storage entry"
    freight.intersection_update(physical)
    assert len(freight) >= 184, "Expected a complete standard trading-post catalogue"
    union = set()
    for region, guid in REGIONS.items():
        regional = {g for g in freight if region in physical[g]}
        delivered = outputs(items[guid])
        assert regional <= delivered <= freight, (region, regional - delivered, delivered - freight)
        if region == "Africa":
            assert 114428 in delivered, "Keep the Leather Boots supplied by the earlier Enbesa edition"
        union.update(delivered)
        print(f"{region}: {len(delivered)} goods per cycle")
    assert outputs(items[HARBOUR]) == union == freight, "Harbour catalogue does not cover all physical freight"
    print(f"Harbour: {len(freight)} goods per cycle")

    # Native farm lists include retired GUIDs. Also require supplies which the game categorises
    # outside agriculture, notably dung, fertiliser and the physical tractor fuel product.
    mandatory = (agriculture & physical.keys()) | {24807, 24808, TRACTOR_FUEL, 1010253, 1010193}
    sample_buildings = {1010262, 1010267, 1010269, 1010298, 1010558, 1010266, 114703,
                        132933, 114439, 114450, 1010331, 118571, 119028, 269840}
    farm_goods = outputs(items[2141000050])
    assert mandatory <= farm_goods <= freight, (mandatory - farm_goods, farm_goods - freight)
    farm_targets = None
    for guid, socket in FARM_EDITIONS.items():
        values = items[guid]
        assert values.findtext("Item/Allocation") == socket
        assert outputs(values) == farm_goods
        modifier = int(values.findtext("ModuleOwnerUpgrade/ModuleLimitPercent"))
        if guid < 2141000140:
            assert modifier + 50 <= -100, "A normal tractor must not reintroduce field demand"
        else:
            assert modifier == 500
        assert int(values.findtext("FactoryUpgrade/ProductivityUpgrade/Value")) >= 100
        assert int(values.findtext("FactoryUpgrade/NeededAreaPercentUpgrade/Value")) <= -100
        pool = int(values.findtext("ItemEffect/EffectTargets/Item/GUID"))
        assert sample_buildings <= targets[pool], (guid, sample_buildings - targets[pool])
        if farm_targets is None:
            farm_targets = targets[pool]
        assert farm_targets == targets[pool], "Both farming editions must cover the same buildings"
    covered_pens = set(pen_radii) & farm_targets
    assert {5457, 101269, 1010267} <= covered_pens
    assert all(pen_radii[g] == 0 or pen_radii[g] >= 40 for g in covered_pens), "Insufficient pasture placement radius"
    assert all(pen_radii[g] >= 40 for g in (5457, 101269)), "Template-inherited livestock radii were not expanded"
    print(f"Four farm items: {len(farm_goods)} distinct 1:1 bonus outputs apiece")


if __name__ == "__main__":
    main()
