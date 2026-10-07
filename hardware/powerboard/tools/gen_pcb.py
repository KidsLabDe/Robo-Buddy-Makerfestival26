#!/usr/bin/env python3
"""Create a PRELIMINARY powerboard.kicad_pcb: outline, footprints with nets,
rough placement, GND pour on the bottom. No tracks yet.

The real outline comes from the enclosure; until then this board exists to
check that everything fits and to get first 2D/3D views.

    python3 hardware/powerboard/tools/gen_pcb.py
"""
import os
import subprocess
import sys
import tempfile

import pcbnew

from sexp import find, find1, parse

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SCH = os.path.join(PROJ, 'powerboard.kicad_sch')
PCB = os.path.join(PROJ, 'powerboard.kicad_pcb')
FP_DIR = '/usr/share/kicad/footprints'

W, H = 45.0, 30.0      # board, mm (vorläufig, Handoff Abschnitt 2)
OX, OY = 100.0, 100.0  # board origin on the sheet

mm = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


# ref: (x, y, rotation) relative to the board's top left corner.
# Left edge = outside (USB-C, switch, LED), right/bottom = cell and servos,
# top edge = display socket.
FIXED = {
    'U4': (12.0, 15.0, 90),    # USB-C points left, over the edge
    'SW1': (4.0, 27.7, 0),     # lever over the bottom edge, next to the USB corner
    'D1': (2.0, 2.2, 0),
    'J4': (43.4, 9.3, 270),    # angled socket, body and opening towards the top edge
    'J2': (43.3, 13.6, 0),
    'J3': (43.3, 22.3, 0),
    'J1': (34.0, 24.6, 0),     # cable enters from the bottom edge
    'C8': (36.6, 15.6, 0),
    'H1': (23.6, 2.4, 0),
    'H2': (25.2, 27.4, 0),
}
# test points in a row along the top edge, left of the display
FIXED.update({f'TP{i + 1}': (5.0 + i * 2.6, 2.4, 0) for i in range(5)})

# SMD parts, packed in order; when a region is full the rest spills into the next
REGIONS = [
    (1.8, 7.9, 20.0, 22.1),    # under the plugged-in ESP, clear of the antenna
    (26.4, 11.4, 31.6, 19.3),  # between ESP and the electrolytic
    (26.4, 19.5, 29.1, 24.8),  # left of the battery connector
    (12.2, 25.6, 22.8, 29.6),  # bottom strip, right of the switch
    (17.2, 0.4, 21.4, 4.8),    # top strip, right of the test points
]
ORDER = ['Q1', 'U2', 'Q2', 'U1', 'Q5', 'U3', 'R1', 'R2', 'C1', 'R3', 'R4', 'C2', 'C3', 'R6', 'R5',
         'R7', 'C4', 'C5', 'C6',
         'Q3', 'Q4', 'R8', 'C7', 'R9', 'R10', 'R13', 'R14', 'R11', 'R12', 'C9',
         ]
GAP = 0.5


def netlist():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'n.net')
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '-o', out, SCH], check=True,
                       stdout=subprocess.DEVNULL)
        t = parse(open(out, encoding='utf-8').read())
    comps = {}
    for c in find(find1(t, 'components'), 'comp'):
        ref = find1(c, 'ref')[1]
        fields = {}
        for f in find(find1(c, 'fields') or [], 'field'):
            vals = [x for x in f[1:] if isinstance(x, str) and not isinstance(x, list)]
            fields[find1(f, 'name')[1]] = vals[-1] if vals else ''
        comps[ref] = dict(value=find1(c, 'value')[1], fp=find1(c, 'footprint')[1], fields=fields)
    pads = {}
    for n in find(find1(t, 'nets'), 'net'):
        name = find1(n, 'name')[1]
        for node in find(n, 'node'):
            pads[(find1(node, 'ref')[1], find1(node, 'pin')[1])] = name
    return comps, pads


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = os.path.join(PROJ, 'powerboard.pretty') if lib == 'powerboard' else \
        os.path.join(FP_DIR, f'{lib}.pretty')
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        sys.exit(f'footprint not found: {fpid}')
    return fp


def courtyard(fp):
    box = fp.GetCourtyard(pcbnew.F_CrtYd).BBox() if fp.GetCourtyard(pcbnew.F_CrtYd).OutlineCount() \
        else fp.GetBoundingBox(False)
    return pcbnew.ToMM(box.GetWidth()), pcbnew.ToMM(box.GetHeight()), box


def place_at(fp, x, y, rot):
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(V(x, y))


def pack(fps):
    """Shelf packing, first fit: each region fills row by row, every part
    goes into the first region that still has room for it."""
    cur = [dict(r=r, x=r[0], y=r[1], row_h=0.0) for r in REGIONS]

    def fit(c, w, h):
        x0, y0, x1, y1 = c['r']
        x, y, row_h = c['x'], c['y'], c['row_h']
        if x + w > x1:
            x, y, row_h = x0, y + row_h + GAP, 0.0
        if x + w > x1 or y + h > y1:
            return None
        return x, y, row_h

    def height(ref):
        place_at(fps[ref], 0, 0, 0)
        return courtyard(fps[ref])[1]

    # tallest first wastes the least row height; ties keep the ORDER grouping
    for ref in sorted(ORDER, key=lambda r: -round(height(r), 1)):
        fp = fps[ref]
        place_at(fp, 0, 0, 0)
        w, h, box = courtyard(fp)
        for c in cur:
            spot = fit(c, w, h)
            if spot:
                break
        else:
            sys.exit(f'{ref} does not fit anywhere')
        x, y, row_h = spot
        # move so the courtyard's top left corner lands on (x, y)
        dx = pcbnew.ToMM(fp.GetPosition().x - box.GetX())
        dy = pcbnew.ToMM(fp.GetPosition().y - box.GetY())
        place_at(fp, x + dx, y + dy, 0)
        c.update(x=x + w + GAP, y=y, row_h=max(row_h, h))


def outline(board):
    pts = [(0, 0), (W, 0), (W, H), (0, H)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(ax, ay))
        s.SetEnd(V(bx, by))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)


def text(board, msg, x, y, layer, size=1.0, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(msg)
    t.SetPosition(V(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    t.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def gnd_pour(board, net):
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNet(net)
    z.SetLocalClearance(mm(0.3))
    z.SetMinThickness(mm(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    o = z.Outline()
    o.NewOutline()
    for x, y in [(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)]:
        o.Append(mm(OX + x), mm(OY + y))
    board.Add(z)


def main():
    comps, pads = netlist()
    board = pcbnew.NewBoard(PCB)
    nets = {}
    for name in sorted(set(pads.values())):
        if name.startswith('unconnected-'):
            continue
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n

    fps = {}
    for ref, c in sorted(comps.items()):
        if ref.startswith('#'):
            continue
        fp = load_fp(c['fp'])
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        fp.Value().SetVisible(False)  # values would bury the tiny parts
        for k in ('LCSC', 'Kit', 'Description'):
            if c['fields'].get(k):
                fld = pcbnew.PCB_FIELD(fp, pcbnew.FIELD_T_USER, k)
                fld.SetText(c['fields'][k])
                fld.SetVisible(False)
                fp.Add(fld)
        for pad in fp.Pads():
            net = pads.get((ref, pad.GetNumber()))
            if net in nets:
                pad.SetNet(nets[net])
        board.Add(fp)
        fps[ref] = fp

    for ref, (x, y, rot) in FIXED.items():
        place_at(fps[ref], x, y, rot)
    pack(fps)
    missing = set(fps) - set(FIXED) - set(ORDER)
    if missing:
        sys.exit(f'not placed: {sorted(missing)}')

    outline(board)
    gnd_pour(board, nets['/GND'])
    text(board, '+', 32.0, 19.6, pcbnew.F_SilkS, 1.2)
    text(board, '-', 36.0, 19.6, pcbnew.F_SilkS, 1.2)
    text(board, 'L', 41.2, 13.6, pcbnew.F_SilkS, 1.0)
    text(board, 'R', 41.2, 22.3, pcbnew.F_SilkS, 1.0)
    text(board, 'MF26 Robo-Buddy Power v0.1', W / 2, 12.0, pcbnew.B_SilkS, 1.2)
    text(board, 'KidsLab - VORLAEUFIG, nicht bestellen', W / 2, 15.0, pcbnew.B_SilkS, 1.0)

    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(PCB)
    print(f'{len(fps)} footprints, {len(nets)} nets -> {PCB}')


if __name__ == '__main__':
    main()
