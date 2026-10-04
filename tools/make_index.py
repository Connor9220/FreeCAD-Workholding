#!/usr/bin/env python3
"""Write index.json for this library of FreeCAD CAM workholding: each vise in vises/ and clamp in
clamps/, what it is, where it came from and under what license, its settings, its thumbnail, and
the sha256 a download is checked against. Plain Python, no FreeCAD needed: run it after adding or changing a
file, and commit what it writes.

    python3 tools/make_index.py

A vise or a clamp is a FreeCAD file laid out as FreeCAD's CAM workbench takes it, stamped with
what it is and where it was published by tools/stamp.py: its label, maker, model, type, license,
attribution and source, the library and its id there. The file says it all of itself; a file not
stamped, or stamped for another library or id, is left out. A file that holds Python, run when it
is opened, is refused, as FreeCAD refuses it."""

import hashlib
import json
import os
import subprocess
import sys
import zipfile

from xml.etree import ElementTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stamp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMAT = 1
# what a vise's settings are called in its file, and in the index
SETTINGS = {
    "JawWidth": "jawWidth",
    "JawHeight": "jawHeight",
    "MaxOpening": "maxOpening",
    "JawSteps": "jawSteps",
    "JawPlates": "jawPlates",
    "TakesParallels": "takesParallels",
    "SelfCentering": "selfCentering",
    "Stations": "stations",
    "ViseSchema": "schema",
}
# what a clamp's settings are called in its file, and in the index
CLAMP_SETTINGS = {
    "Kind": "kind",
    "Width": "width",
    "Reach": "reach",
    "MinStockThickness": "minStock",
    "MaxStockThickness": "maxStock",
}
META = ("label", "maker", "model", "type", "license", "attribution", "source")
# the kinds of vise FreeCAD filters the library by: one of these, a new one added here first
CLAMP_TYPES = ("Edge clamp", "Toe clamp", "Strap clamp", "Side clamp", "Dog")
TYPES = (
    "CNC",
    "Multi-station",
    "Modular",
    "Low profile",
    "Self-centering",
    "Toolmaker's",
    "Drill press",
)


def value(prop):
    """A property's value as its file keeps it: a number, a flag, a list or a string."""
    kind = prop.get("type", "")
    child = list(prop)
    if not child:
        return None
    node = child[0]
    if kind.endswith("StringList"):
        return [s.get("value") for s in node]
    raw = node.get("value")
    if kind.endswith("Bool"):
        return raw == "true"
    if kind.endswith(("Length", "Distance", "Float", "Integer")):
        number = float(raw)
        return int(number) if kind.endswith("Integer") else round(number, 6)
    return raw


def read(path, wanted=SETTINGS):
    """What a vise's or a clamp's file says of itself: its objects' kinds, its settings, by
    wanted, and its thumbnail."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("Document.xml"))
        thumbnail = None
        if "thumbnails/Thumbnail.png" in archive.namelist():
            thumbnail = archive.read("thumbnails/Thumbnail.png")
        names = archive.namelist()
    kinds = {o.get("name"): o.get("type") for o in root.iter("Object") if o.get("type")}
    python = sorted({k for k in kinds.values() if "Python" in k})
    python += sorted({p.get("type") for p in root.iter("Property") if "Python" in p.get("type", "")})
    settings = {}
    container = None
    for data in root.iter("Object"):
        name = data.get("name")
        props = data.find("Properties")
        if props is None:
            continue
        if kinds.get(name) == "App::Part" and container is None:
            for p in props:
                if p.get("name") == "Label":
                    container = value(p)
        if kinds.get(name) != "App::VarSet":
            continue
        for p in props:
            key = wanted.get(p.get("name"))
            if key is not None:
                settings[key] = value(p)
    if wanted is SETTINGS:
        settings.setdefault("schema", 1)
        settings.setdefault("takesParallels", True)
    return {
        "python": python,
        "settings": settings,
        "container": container,
        "thumbnail": thumbnail,
        "nameTable": any("StringHasher" in n for n in names),
    }


def published():
    """Every sha256 each item's file has been published with, by id: from this repository's
    history of index.json, and the index as it is now. FreeCAD tells a copy of an older one, an
    update to get, from one changed by its user, which the library never published."""
    found = {}

    def add(text):
        try:
            index = json.loads(text)
        except ValueError:
            return
        for item in index.get("items", []):
            shas = found.setdefault(item.get("id"), [])
            for sha in item.get("history", []) + [item.get("sha256")]:
                if sha and sha not in shas:
                    shas.append(sha)

    try:
        commits = subprocess.run(
            ["git", "log", "--reverse", "--format=%H", "--", "index.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        for commit in commits:
            shown = subprocess.run(
                ["git", "show", "%s:index.json" % commit],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if shown.returncode == 0:
                add(shown.stdout)
    except (OSError, subprocess.CalledProcessError):
        pass
    if os.path.exists(os.path.join(ROOT, "index.json")):
        with open(os.path.join(ROOT, "index.json")) as f:
            add(f.read())
    return found


def main():
    thumbs = os.path.join(ROOT, "thumbnails")
    os.makedirs(thumbs, exist_ok=True)
    items = []
    failed = False
    for kind, folder in (("vise", "vises"), ("clamp", "clamps")):
        found, wrong = collect(kind, folder, thumbs)
        items += found
        failed = failed or wrong
    # the sha256s each was published with before, newest last
    before = published()
    for item in items:
        history = [sha for sha in before.get(item["id"], []) if sha != item["sha256"]]
        if history:
            item["history"] = history
    index = {"format": FORMAT, "items": items}
    with open(os.path.join(ROOT, "index.json"), "w") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    print(
        "index.json: %d vises, %d clamps"
        % (sum(i["kind"] == "vise" for i in items), sum(i["kind"] == "clamp" for i in items))
    )
    return 1 if failed else 0


def collect(kind, folder, thumbs):
    """The items of a kind in folder, and whether any was left out."""
    vises = os.path.join(ROOT, folder)
    items = []
    failed = False
    if not os.path.isdir(vises):
        return items, failed
    for name in sorted(os.listdir(vises)):
        if not name.endswith(".FCStd"):
            continue
        stem = name[: -len(".FCStd")]
        path = os.path.join(vises, name)
        with zipfile.ZipFile(path) as archive:
            try:
                meta = stamp.read(archive.read("Document.xml").decode("utf-8"))
            except ValueError as e:
                print("%s: %s, left out" % (name, e))
                failed = True
                continue
        missing = [k for k in META + ("library", "id") if not meta.get(k)]
        if missing:
            print("%s: not stamped with %s (tools/stamp.py), left out" % (name, ", ".join(missing)))
            failed = True
            continue
        if meta["library"] != stamp.LIBRARY or meta["id"] != stem:
            print(
                "%s: stamped for %s as %s, not this library as %s, left out"
                % (name, meta["library"], meta["id"], stem)
            )
            failed = True
            continue
        types = TYPES if kind == "vise" else CLAMP_TYPES
        if meta["type"] not in types:
            print("%s: type %r is none of %s, left out" % (name, meta["type"], ", ".join(types)))
            failed = True
            continue
        found = read(path, SETTINGS if kind == "vise" else CLAMP_SETTINGS)
        if found["python"]:
            print("%s: holds Python, run when opened (%s), left out" % (name, ", ".join(found["python"])))
            failed = True
            continue
        if kind == "vise" and (
            "maxOpening" not in found["settings"] or "jawHeight" not in found["settings"]
        ):
            print("%s: no vise settings (JawHeight, MaxOpening) in it, left out" % name)
            failed = True
            continue
        if kind == "clamp" and found["settings"].get("kind") not in ("HoldDown", "Push"):
            print("%s: no clamp Kind (HoldDown or Push) in it, left out" % name)
            failed = True
            continue
        if found["nameTable"]:
            # face names kept against a table of their own: linked into a Job they warn
            print("%s: warning: keeps a StringHasher table" % name)
        with open(path, "rb") as f:
            data = f.read()
        item = {
            "id": stem,
            "kind": kind,
            "file": folder + "/" + name,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        item.update({k: meta[k] for k in META})
        item["settings"] = found["settings"]
        if found["thumbnail"]:
            thumb = "thumbnails/%s.png" % stem
            with open(os.path.join(ROOT, thumb), "wb") as f:
                f.write(found["thumbnail"])
            item["thumbnail"] = thumb
        items.append(item)
        print("%s: ok" % name)
    return items, failed


if __name__ == "__main__":
    sys.exit(main())
