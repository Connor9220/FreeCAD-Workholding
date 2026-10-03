# FreeCAD CAM workholding library

Vises for FreeCAD's CAM workbench, each a FreeCAD file laid out the way the CAM workbench's Vise
panel takes it: origin on the fixed jaw's face, at the top of the jaws, centred across them, +Z
up, the jaws closing along -Y, and a VarSet named `Vise` with its settings (`Opening`,
`JawHeight`, `JawWidth`, `MaxOpening`, `SeatHeight`, `JawPlates`, `JawSteps`, `ViseSchema`, ...).

FreeCAD reads `index.json` to list what is here and downloads the file you pick into your own
Workholding folder, checking it against the sha256 the index gives.

## Adding a vise

1. Put the vise's file in `vises/`, and beside it a `.json` of the same name with `label`,
   `maker`, `model`, `licence`, `attribution` and `source`.
2. Only add a file whose licence lets it be shared, and say so in its `.json`.
3. Run `python3 tools/make_index.py` and commit what it writes: `index.json` and the thumbnail.

A file holding Python, which would run when it is opened, is refused.

## Licences

Each vise carries its own licence and attribution, in its `.json` and in `index.json`; see
[LICENSES.md](LICENSES.md).
