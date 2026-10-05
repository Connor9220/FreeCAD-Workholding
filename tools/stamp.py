#!/usr/bin/env python3
"""Stamp a vise's or clamp's file with what it is and where it was published: its settings VarSet
given an About group (Library, LibraryItem, Type, Maker, Model, License, Attribution, Source) and
its part named by its label. The file says this of itself wherever it is copied; FreeCAD groups
and finds it by it, and make_index.py reads the index from it. Plain Python, no FreeCAD needed:
only the file's Document.xml is changed, everything else in it, colors and thumbnail, is kept
as it is.

    python3 tools/stamp.py vises/Some_Vise.FCStd label="Some vise" maker="..." model="..." \\
        type=CNC license="..." attribution="..." source=https://...

A field not given keeps what the file has. library= and id= default to this library's address
and the file's name."""

import os
import re
import sys
import zipfile
from xml.sax.saxutils import quoteattr

LIBRARY = "https://github.com/Connor9220/FreeCAD-Workholding"
GROUP = "About"
# the About group's properties: their names, the field each is stamped from, and their tooltips
FIELDS = (
    ("Library", "library", "The library this was published in: its address"),
    ("LibraryItem", "id", "Its id in that library"),
    ("Type", "type", "Its kind, as the library sorts them"),
    ("Maker", "maker", "Who makes it"),
    ("Model", "model", "Its model"),
    ("License", "license", "The license it is shared under"),
    ("Attribution", "attribution", "Who drew it, and from what"),
    ("Source", "source", "Where it came from"),
)


def _objects(xml, section):
    """Each object's span in the Objects or ObjectData section: {name: (start, end)}."""
    start = xml.index("<%s " % section)
    end = xml.index("</%s>" % section, start)
    spans = {}
    for m in re.finditer(r'<Object (?:type="[^"]*" )?name="([^"]+)"', xml[start:end]):
        spans.setdefault(m.group(1), start + m.start())
    return spans, start, end


def _types(xml):
    head = xml[xml.index("<Objects ") : xml.index("</Objects>")]
    return dict(
        (name, kind) for kind, name in re.findall(r'<Object type="([^"]+)" name="([^"]+)"', head)
    )


def _span(xml, at):
    """The <Properties ...> ... </Properties> span of the object whose data starts at at."""
    start = xml.index("<Properties ", at)
    end = xml.index("</Properties>", start)
    return start, end


def _settingsAndPart(xml):
    """The settings VarSet's name, a vise's (an Opening) or a clamp's (a Kind), and the part
    holding it."""
    types = _types(xml)
    spans, _, _ = _objects(xml, "ObjectData")
    settings = None
    for name, kind in types.items():
        if kind != "App::VarSet" or name not in spans:
            continue
        start, end = _span(xml, spans[name])
        if re.search(r'<Property name="(Opening|Kind)"', xml[start:end]):
            settings = name
            break
    if settings is None:
        raise ValueError("no settings VarSet (with an Opening or a Kind)")
    # a strap kit is many parts, none of them the kit: its label is its settings'
    start, end = _span(xml, spans[settings])
    if re.search(r'<Property name="Kind"[^>]*>\s*<String value="StrapKit"', xml[start:end]):
        return settings, settings
    part = None
    for name, kind in types.items():
        if kind != "App::Part" or name not in spans:
            continue
        start, end = _span(xml, spans[name])
        if re.search(r'<Link value="%s"' % re.escape(settings), xml[start:end]) or part is None:
            part = name
    return settings, part


def read(xml):
    """What a file's Document.xml says of it: {field: value}, label and the About group's."""
    settings, part = _settingsAndPart(xml)
    spans, _, _ = _objects(xml, "ObjectData")
    found = {}
    start, end = _span(xml, spans[settings])
    for name, field, _ in FIELDS:
        m = re.search(
            r'<Property name="%s" type="App::PropertyString"[^>]*>\s*<String value="([^"]*)"/>' % name,
            xml[start:end],
        )
        if m:
            found[field] = _unescape(m.group(1))
    if part is not None:
        start, end = _span(xml, spans[part])
        m = re.search(
            r'<Property name="Label" type="App::PropertyString"[^>]*>\s*<String value="([^"]*)"/>',
            xml[start:end],
        )
        if m:
            found["label"] = _unescape(m.group(1))
    return found


def _unescape(text):
    for a, b in (("&quot;", '"'), ("&apos;", "'"), ("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")):
        text = text.replace(a, b)
    return text


def stamp(xml, values):
    """Document.xml with values stamped: the About group's properties replaced, the part's label
    set."""
    settings, part = _settingsAndPart(xml)
    spans, _, _ = _objects(xml, "ObjectData")
    start, end = _span(xml, spans[settings])
    block = xml[start:end]
    # the status a dynamic property of this VarSet has, for those added
    status = re.search(r'<Property name="\w+" type="App::Property\w+" group="[^"]*"[^>]*status="(\d+)"', block)
    status = status.group(1) if status else "2097156"
    # those of the same names already there, in this group or another, replaced
    old = re.compile(
        r'\s*<Property name="(%s)" type="[^"]*".*?</Property>'
        % "|".join(name for name, _, _ in FIELDS),
        re.S,
    )
    removed = len(old.findall(block))
    block = old.sub("", block)
    indent = re.search(r"\n(\s*)<Property ", block)
    indent = indent.group(1) if indent else "                "
    added = []
    for name, field, doc in FIELDS:
        value = values.get(field, "")
        added.append(
            '%s<Property name="%s" type="App::PropertyString" group="%s" doc=%s attr="0" '
            'ro="0" hide="0" status="%s">\n%s    <String value=%s/>\n%s</Property>'
            % (indent, name, GROUP, quoteattr(doc), status, indent, quoteattr(value), indent)
        )
    block = block.rstrip() + "\n" + "\n".join(added) + "\n" + indent[:-4]
    count = re.match(r'<Properties Count="(\d+)"', block)
    block = block.replace(
        count.group(0),
        '<Properties Count="%d"' % (int(count.group(1)) - removed + len(added)),
        1,
    )
    xml = xml[:start] + block + xml[end:]
    if part is not None and values.get("label"):
        spans, _, _ = _objects(xml, "ObjectData")
        start, end = _span(xml, spans[part])
        block = re.sub(
            r'(<Property name="Label" type="App::PropertyString"[^>]*>\s*<String value=)"[^"]*"',
            lambda m: m.group(1) + quoteattr(values["label"]),
            xml[start:end],
            count=1,
        )
        xml = xml[:start] + block + xml[end:]
    return xml


def rewrite(path, xml):
    """The file at path with its Document.xml replaced, every other entry kept as it was."""
    temporary = path + ".stamping"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary, "w") as target:
        for info in source.infolist():
            data = xml.encode("utf-8") if info.filename == "Document.xml" else source.read(info)
            target.writestr(info, data)
    os.replace(temporary, path)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    path = argv[0]
    given = {}
    for arg in argv[1:]:
        key, sep, value = arg.partition("=")
        if not sep:
            print("%s: not field=value" % arg)
            return 1
        given[key] = value
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("Document.xml").decode("utf-8")
    values = read(xml)
    values.setdefault("library", LIBRARY)
    values.setdefault("id", os.path.splitext(os.path.basename(path))[0])
    values.update(given)
    rewrite(path, stamp(xml, values))
    print("%s: stamped %s" % (path, ", ".join("%s=%s" % i for i in sorted(values.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
