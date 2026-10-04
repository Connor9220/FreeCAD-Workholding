# FreeCAD CAM workholding library

Vises and clamps for FreeCAD's CAM workbench. Each vise is a FreeCAD file laid out the way the CAM
workbench's Vise panel takes it: origin on the fixed jaw's face, at the top of the jaws, centred across them, +Z
up, the jaws closing along -Y, and a VarSet named `Vise` with its settings (`Opening`,
`JawHeight`, `JawWidth`, `MaxOpening`, `SeatHeight`, `JawPlates`, `JawSteps`, `ViseSchema`, ...).

Each clamp is a FreeCAD file with its origin on the stock's top edge where it grips, at the
middle of its width, +X along the edge, +Y into the stock, +Z up, and a VarSet with its `Kind`
(`HoldDown`, over the stock's top edge, or `Push`, against its side) and settings (`Width`,
`Reach`, `MinStockThickness`, `MaxStockThickness`, ...).

FreeCAD reads `index.json` to list what is here and downloads the file you pick into your own
Workholding folder, checking it against the sha256 the index gives.

## Adding a vise

1. Put the vise's file in `vises/` and stamp it with what it is and where it came from:

       python3 tools/stamp.py vises/Some_Vise.FCStd label="Some vise" maker="..." model="..." \
           type=CNC licence="..." attribution="..." source=https://...

   The stamp goes in the file itself, an About group in its settings VarSet with the library's
   address and the file's id here, so the file says what it is wherever it is copied. `type` is
   one of `CNC`, `Multi-station`,
   `Modular`, `Low profile`, `Self-centering`, `Toolmaker's` or `Drill press`, what FreeCAD
   filters the library by; a new one is added to `TYPES` in `tools/make_index.py` first.
2. Only add a file whose licence lets it be shared, and stamp the licence in it.
3. Run `python3 tools/make_index.py` and commit what it writes: `index.json` and the thumbnail.

## Adding a clamp

As a vise, in `clamps/`. `type` is one of `Edge clamp`, `Toe clamp`, `Strap clamp`, `Side clamp`
or `Dog` (`CLAMP_TYPES` in `tools/make_index.py`). FreeCAD saves a clamp downloaded in your
Workholding/Clamps folder.

A file holding Python, which would run when it is opened, is refused.

## Licences

Each vise and clamp carries its own licence and attribution, stamped in its file and listed in
`index.json`; see
[LICENSES.md](LICENSES.md).
