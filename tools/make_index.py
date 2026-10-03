#!/usr/bin/env python3
"""Write index.json for this library of FreeCAD CAM workholding: each vise in vises/, what it
is, where it came from and under what licence, its settings, its thumbnail, and the sha256 a
download is checked against. Plain Python, no FreeCAD needed: run it after adding or changing a
file, and commit what it writes.

    python3 tools/make_index.py

A vise is a FreeCAD file laid out as FreeCAD's CAM workbench takes it, and a .json of the same
name beside it: label, maker, model, licence, attribution and source. A file that holds Python,
run when it is opened, is refused, as FreeCAD refuses it."""

import hashlib
import json
import os
import sys
import zipfile

from xml.etree import ElementTree

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
    "ViseSchema": "schema",
}
META = ("label", "maker", "model", "licence", "attribution", "source")


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


def read(path):
    """What a vise's file says of itself: its objects' kinds, its settings and its thumbnail."""
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
            key = SETTINGS.get(p.get("name"))
            if key is not None:
                settings[key] = value(p)
    settings.setdefault("schema", 1)
    settings.setdefault("takesParallels", True)
    return {
        "python": python,
        "settings": settings,
        "container": container,
        "thumbnail": thumbnail,
        "nameTable": any("StringHasher" in n for n in names),
    }


def main():
    vises = os.path.join(ROOT, "vises")
    thumbs = os.path.join(ROOT, "thumbnails")
    os.makedirs(thumbs, exist_ok=True)
    items = []
    failed = False
    for name in sorted(os.listdir(vises)):
        if not name.endswith(".FCStd"):
            continue
        stem = name[: -len(".FCStd")]
        path = os.path.join(vises, name)
        meta_path = os.path.join(vises, stem + ".json")
        if not os.path.exists(meta_path):
            print("%s: no %s.json beside it, left out" % (name, stem))
            failed = True
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        missing = [k for k in META if not meta.get(k)]
        if missing:
            print("%s: its .json says nothing of %s, left out" % (name, ", ".join(missing)))
            failed = True
            continue
        found = read(path)
        if found["python"]:
            print("%s: holds Python, run when opened (%s), left out" % (name, ", ".join(found["python"])))
            failed = True
            continue
        if "maxOpening" not in found["settings"] or "jawHeight" not in found["settings"]:
            print("%s: no vise settings (JawHeight, MaxOpening) in it, left out" % name)
            failed = True
            continue
        if found["nameTable"]:
            # face names kept against a table of their own: linked into a Job they warn
            print("%s: warning: keeps a StringHasher table" % name)
        with open(path, "rb") as f:
            data = f.read()
        item = {
            "id": stem,
            "kind": "vise",
            "file": "vises/" + name,
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
    index = {"format": FORMAT, "items": items}
    with open(os.path.join(ROOT, "index.json"), "w") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    print("index.json: %d vises" % len(items))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
