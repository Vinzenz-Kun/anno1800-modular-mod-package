"""Exercise optional acquisition routes with xmltest and a small set of real game assets."""
import argparse
import subprocess
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

from build_acquisition import ASSETS, ROOT, TRADERS, POOL, TALENT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path, help="Extracted vanilla assets.xml")
    parser.add_argument("xmltest", type=Path, help="Path to the Anno modloader's xmltest executable")
    args = parser.parse_args()
    binary = args.xmltest.resolve()
    directory = ROOT / "mods"
    characters = sorted(f for f in directory.iterdir() if f.is_dir() and f.name.startswith("[Specialist] "))
    acquisition = [directory / "[Acquisition] Traders", directory / "[Acquisition] Research"]
    folders = characters + acquisition + [directory / "[Inventory] Specialist Stacks"]
    sources = {f: ET.parse(f / ASSETS).getroot() for f in folders}
    definitions = {
        f: {a.findtext("Values/Standard/GUID"): a for a in sources[f].iterfind(".//Asset")
            if a.find("Values/Item") is not None}
        for f in characters
    }
    # Keep all patch anchors, the original inventories, and base character definitions.
    selected = set()
    for doc in sources.values():
        for op in doc.iter("ModOp"):
            selected.update(op.get("GUID", "").split(","))
    fixture = ET.Element("AssetList")
    children = ET.SubElement(fixture, "Assets")
    original_stock = {}
    for _, a in ET.iterparse(args.assets):
        if a.tag != "Asset" or a.find("Values/Standard/GUID") is None:
            continue
        guid = a.findtext("Values/Standard/GUID")
        if guid in selected:
            if int(guid) in TRADERS:
                original_stock[guid] = [x.text for x in a.findall("Values/Trader/Progression/*/OfferingItems")]
            children.append(a)
        else:
            a.clear()

    all_custom = {g for group in definitions.values() for g in group}
    assert len(characters) == 16 and len(all_custom) == 18, "Incomplete specialist bundle"
    compact = directory / "[Specialist] Agriculture"
    grand_fields = directory / "[Specialist] Agriculture - Grand Fields"
    with tempfile.TemporaryDirectory() as tmp:
        wd = Path(tmp)
        ET.ElementTree(fixture).write(wd / "fixture.xml", encoding="utf-8")
        for name, modules, traders, research in (
            ("Default", characters, True, True),
            ("Research only", characters[:2], False, True),
            ("Traders only", characters[-2:], True, False),
            ("Normal trader stock", characters[::3], False, False),
            ("Compact farms alone", [compact], True, True),
            ("Grand Fields alone", [grand_fields], True, True),
            ("Catalogues without custom characters", [], True, True),
        ):
            active = list(modules)
            if traders:
                active.append(acquisition[0])
            if research:
                active.append(acquisition[1])
            active.append(folders[-1])
            patch = ET.Element("ModOps")
            for folder in active:
                patch.extend(sources[folder])
            ET.ElementTree(patch).write(wd / "patch.xml", encoding="utf-8")
            result = subprocess.run([binary, "fixture.xml", "patch.xml"], cwd=wd, capture_output=True,
                                    text=True, errors="replace", check=True)
            log = result.stdout + result.stderr
            assert "[error]" not in log and "[warning]" not in log, log
            patched = {a.findtext("Values/Standard/GUID"): a.find("Values")
                       for a in ET.parse(wd / "patched.xml").iterfind(".//Asset") if a.find("Values") is not None}
            expected = {g for f in modules for g in definitions[f]}
            assert all_custom.intersection(patched) == expected
            hits = {p: [x.text for x in patched[str(p)].findall("AssetPool/AssetList/Item/Asset")]
                    for pools in TALENT.values() for p in pools}
            for person in expected:
                v = patched[person]
                assert v.findtext("Item/MaxStackSize") == "50"
                assert v.findtext("Locked/DefaultLockedState") == "0"
                alloc = v.findtext("Item/Allocation")
                field = "City" if alloc == "TownHall" else "Production" if alloc in ("GuildHouse", "Lodge") else "Harbour"
                assert hits[TALENT[field][-1]].count(person) == int(research)
                assert any(x.text == person for pool in patched.values()
                           for x in pool.findall("RewardPool/ItemsPool/Item/ItemLink"))
            assert {g for members in hits.values() for g in members if g in all_custom} == (expected if research else set())
            for guid, tier in TRADERS.items():
                stock = [x.text for x in patched[str(guid)].findall("Trader/Progression/*/OfferingItems")]
                assert stock == ([str(POOL[tier])] * 6 if traders else original_stock[str(guid)])
            if traders:
                catalog = [x.text for x in patched[str(POOL["Legendary"])].findall("RewardPool/ItemsPool/Item/ItemLink")]
                assert len(catalog) == len(set(catalog)) and set(catalog).intersection(all_custom) == expected
            print(f"{name}: {len(expected)} character assets verified")


if __name__ == "__main__":
    main()
