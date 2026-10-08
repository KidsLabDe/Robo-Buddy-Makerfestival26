#!/usr/bin/env python3
"""Create powerboard.kicad_pcb: outline from the enclosure, footprints with
nets, placement, GND pour on the bottom. No tracks yet.

    python3 hardware/powerboard/tools/gen_pcb.py

Coordinates below are in the frame of cad/MF26-Roboter.step, looking down
on the robot: x runs from the display (front, x ~ -4) to the drag wheel
(rear, x ~ 56), y across the robot, z up (top of the base plate z = 12.5).
On the board, x becomes the KiCad Y axis (front at the top) and y the X axis.

The outline is the inside of the shell at z = 13 ... 17 (cut through the
STEP mesh), moved 0.5 mm inwards:
- sides: shell inside at y = -1.6 and 52.6
- rear: two slanted walls, inside line y = 8.08 + 0.74 (x - 42.76) and its
  mirror at y = 25.5; wall 2.0 mm thick (normal)
- drag wheel boss: ring r = 4.1 around (56, 25.5), the board stops at x = 51
- front: the display stands at x = -8 ... -4.4, the board ends behind it
"""
import math
import os
import subprocess
import sys
import tempfile

import pcbnew

from sexp import find, find1, parse

# KiCad's SWIG iterators still call .next(), which Python 3.14 no longer has
if not hasattr(pcbnew.SwigPyIterator, 'next'):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SCH = os.path.join(PROJ, 'powerboard.kicad_sch')
PCB = os.path.join(PROJ, 'powerboard.kicad_pcb')
FP_DIR = '/usr/share/kicad/footprints'

OX, OY = 100.0, 100.0  # where CAD (x, y) = (0, 0) lands on the KiCad sheet
mm = pcbnew.FromMM

SLOPE = 0.74
MID = 25.5             # mirror line of the robot
WALL = 2.0             # shell wall, normal to the slanted rear walls
CLEAR = 0.5            # gap board edge <-> shell inside


def rear_edge(x):
    """Board edge on the low-y slanted side."""
    return 8.70 + SLOPE * (x - 42.76)


OUTLINE = [(-3.9, -1.1), (28.5, -1.1), (30.5, rear_edge(30.5)), (51.0, rear_edge(51.0)),
           (51.0, 2 * MID - rear_edge(51.0)), (30.5, 2 * MID - rear_edge(30.5)),
           (28.5, 2 * MID + 1.1), (-3.9, 2 * MID + 1.1)]

# unit vectors of the low-y slanted edge (along it, and pointing out of the board)
_n = math.hypot(1, SLOPE)
ALONG = (1 / _n, SLOPE / _n)
OUT_LO = (SLOPE / _n, -1 / _n)
OUT_HI = (SLOPE / _n, 1 / _n)


def V(x, y):
    """CAD (x, y) -> KiCad position."""
    return pcbnew.VECTOR2I(mm(OX + y), mm(OY + x))


def k_vec(dx, dy):
    """CAD direction -> KiCad direction."""
    return dy, dx


def place_at(fp, x, y, rot):
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(V(x, y))


def facing(fp_dir, out):
    """Rotation that turns the footprint's local direction (0, fp_dir) into
    the CAD direction `out`."""
    kx, ky = k_vec(*out)
    return math.degrees(math.atan2(kx / fp_dir, ky / fp_dir))


def on_edge(edge_pt, out, depth):
    """Point `depth` mm inside the board from a point on the edge."""
    return edge_pt[0] - out[0] * depth, edge_pt[1] - out[1] * depth


# ---------------------------------------------------------------- placement --
# ESP: USB-C points through the low-y slanted wall. The footprint's USB-C
# sticks out 1.5 mm past the module edge (-Y), the module centre is 11.75 mm
# from that edge, pin 1 only 1.59 mm. Fully flush (plug face = board edge +
# CLEAR + WALL) would put pad 1 on the board edge, so the module edge stays
# 0.25 mm inside: the socket ends 1.25 mm short of the outside of the shell.
ESP_EDGE = (40.75, rear_edge(40.75))
ESP_OVERHANG = -0.25                       # module edge past the board edge
ESP_POS = on_edge(ESP_EDGE, OUT_LO, 11.75 - ESP_OVERHANG)
# switch: lever (+Y of the footprint, 4 mm past the body at y = 2.2) through
# the high-y slanted wall, body flush with the board edge. The body reaches
# 6.3 mm towards the front from the origin, so the origin sits near the rear.
SW_EDGE = (47.0, 2 * MID - rear_edge(47.0))
SW_POS = on_edge(SW_EDGE, OUT_HI, 2.3)
LED_EDGE = (36.5, 2 * MID - rear_edge(36.5))
LED_POS = on_edge(LED_EDGE, OUT_HI, 2.0)

FIXED = {
    'U4': (*ESP_POS, facing(-1, OUT_LO)),
    'SW1': (*SW_POS, facing(1, OUT_HI)),
    'D1': (*LED_POS, 135),     # ~ along the edge; Freerouting needs non-round pads at 45 deg steps
    'H1': (22.0, 28.0, 0),
    'H2': (48.5, 18.5, 0),
    'Q5': (40.5, 34.5, 0),     # on/off FET and its pull-up right behind the switch
    'R7': (40.5, 31.0, 0),
    # display cable: about centred on the display (y = 25.5), behind the power block
    'J4': (16.2, 18.6, 90),
}
# Power block along the front: 5 V rail at the servo headers, boost, shunt,
# reverse polarity FETs, cell connector, protection FETs. Positions and the
# copper between them (POWER_TRACKS) are fixed; see power_copper().
FIXED.update({
    'U6': (10.0, 15.8, 90), 'L1': (5.8, 16.7, 270), 'C10': (10.6, 18.5, 90),
    'C11': (9.4, 12.8, 180), 'C12': (7.35, 12.5, 180), 'C13': (5.3, 12.5, 180), 'C14': (3.25, 12.5, 180),
    'R8': (12.0, 13.7, 270), 'C7': (12.0, 12.1, 270), 'R9': (15.2, 13.7, 270), 'R10': (13.0, 15.8, 270),
    'R15': (6.5, 22.3, 270), 'Q1': (1.5, 21.8, 90), 'Q7': (1.5, 25.2, 90), 'J1': (3.0, 29.8, 0),
    'Q2': (8.0, 33.3, 0), 'Q6': (8.0, 37.5, 0),
})
# The ESP's pin row with the servo, I2C and SERVO_EN pins faces the low-y
# side, the row with power, analog and display pins the high-y side. So:
# servos along the low-y edge, analog along the high-y edge, both a bit in
# from the edge; I2C and the test points in the middle.
for i, ref in enumerate(['J2', 'J3', 'J5', 'J6']):
    FIXED[ref] = (-2.5 + i * 8.65, 3.3, 0)
for i, ref in enumerate(['J7', 'J8', 'J9']):
    FIXED[ref] = (6.0 + i * 8.8, 47.5, 0)
for i, ref in enumerate(['J10', 'J11']):
    FIXED[ref] = (26.0, 34.5 + i * 6.5, 0)
FIXED.update({f'TP{i + 1}': (21.0, 35.6 + i * 2.1, 0) for i in range(5)})

# SMD blocks (CAD x0, y0, x1, y1). Every group fills its regions in order.
REG_PROT = (-2.6, 34.5, 5.2, 43.5)      # DW01 and friends, beside the cell connector
REG_INA = (9.9, 22.8, 14.2, 33.0)       # INA226 behind the shunt
REG_SRES = (19.0, 7.2, 23.0, 14.5)      # servo series resistors, by the ESP pins
REG_ANA = (5.6, 40.0, 15.0, 43.6)       # analog series resistors, in front of the analog headers
REG_I2C = (22.1, 34.0, 25.0, 43.0)      # I2C pull-ups, between the test points and the I2C headers
REG_UNDER = (31.0, 9.5, 40.5, 19.0)     # power path: under the plugged-in ESP, between its pin rows
REG_PWR = (41.5, 22.5, 50.5, 32.5)      # charger: between the ESP, the switch and the LED
GROUPS = [
    ([REG_PROT], ['U2', 'R1', 'R2', 'R3', 'C1']),
    ([REG_INA], ['U5', 'C15']),
    ([REG_PWR, REG_UNDER], ['U1', 'R4', 'C2', 'C3', 'R5']),     # charger next to its LED
    ([REG_UNDER], ['U3', 'C4', 'C5', 'C6']),          # power path at ESP pin 1
    ([REG_SRES], ['R13', 'R14', 'R16', 'R17']),
    ([REG_ANA], ['R18', 'R19', 'R20']),
    ([REG_I2C], ['R21', 'R22']),
]
GAP = 0.5

# KidsLab logo on the bottom, under the power block (no THT pads there);
# size set in gen_lib.py
LOGO_AT = (5.5, 18.5)

# Pin labels next to the connectors: ref, one text per pin, direction from
# the pin into the board (CAD), sides. 'B' = bottom, 'T' = top as well.
PIN_LABELS = [(ref, ['S', '+', '-'], (0, 1), 'BT') for ref in ('J2', 'J3', 'J5', 'J6')] + \
    [(ref, ['GND', '3V3', 'SDA', 'SCL'], (0, -1), 'BT') for ref in ('J10', 'J11')] + \
    [(ref, ['GND', '3V3', f'A{i}'], (0, -1), 'BT') for i, ref in enumerate(('J7', 'J8', 'J9'))] + \
    [('J4', ['VCC', 'GND', 'SCL', 'SDA', 'DC', 'CS', 'RST'], (1, 0), 'BT'),
     ('J1', ['+', '-'], (-1, 0), 'T'), ('J1', ['+', '-'], (1, 0), 'B')]
LABEL_GAP = {'J1': 3.0}   # mm from the pin to the label; default 1.6, J1's body is wider
# titles: text, CAD x, y, rotation, sides (rotation 90 = along CAD x)
TITLES = [(f'SERVO {i + 1}', -2.5 + i * 8.65 + 2.54, 6.9, 90, 'B') for i in range(4)] + \
    [('SERVO 5V', 11.3, 6.9, 90, 'T')] + \
    [(f'I2C {i + 1}', 24.3, 34.5 + i * 5.6, 0, 'B') for i in range(2)] + \
    [(f'ANALOG A{i}', 6.0 + i * 8.8 + 2.54, 42.6, 90, 'B') for i in range(3)] + \
    [('DISPLAY', 16.2, 14.8, 0, 'B'),
     ('AKKU', -1.6, 30.8, 0, 'T'), ('AKKU', 7.6, 30.8, 0, 'B'),
     ('EIN/AUS', 41.8, 32.1, 0, 'B'),
     ('LADE-LED', 36.0, 42.8, 0, 'B'),
     ('Robo-Buddy Power', 44.0, 28.5, 0, 'B'), ('MF26 v0.2', 45.8, 28.5, 0, 'B')]
TP_NAMES = {'TP1': 'BAT+', 'TP2': 'GND', 'TP3': 'VSYS', 'TP4': '5V', 'TP5': '3V3'}

# Fixed copper of the power block, in KiCad board coordinates (mm):
# (net, layer, width, points...) for tracks, ('via', net, x, y) for vias.
_SERVO_V5 = [100.0 + -2.5 + i * 8.65 + 2.54 for i in range(4)]    # KiCad y of each servo pin 2
POWER_TRACKS = [
    # 5 V: rail beside the servo headers, stubs to every pin 2, bar to the output caps
    ('/V5_SERVO', 'F', 1.2, (106.0, 100.0), (106.0, 126.0)),
    *[('/V5_SERVO', 'F', 1.0, (103.3, y), (106.0, y)) for y in _SERVO_V5],
    ('/V5_SERVO', 'F', 1.2, (106.0, 101.5), (113.45, 101.5)),
    ('/V5_SERVO', 'F', 1.0, (113.45, 101.5), (113.45, 107.35)),
    ('/V5_SERVO', 'F', 0.8, (113.45, 107.35), (113.75, 109.4)),
    ('/V5_SERVO', 'F', 0.6, (113.75, 109.4), (114.6, 109.29)),
    ('/V5_SERVO', 'F', 0.35, (114.6, 109.29), (115.3, 109.29)),          # U6 VOUT
    ('/V5_SERVO', 'F', 0.4, (113.7, 111.175), (113.7, 110.1)),          # R8
    ('/V5_SERVO', 'F', 0.4, (112.1, 111.175), (113.7, 111.175)),        # C7
    # switch node: U6 SW straight into L1
    ('/BOOST_SW', 'F', 0.35, (115.8, 109.1), (115.8, 108.2)),
    # boost GND: U6 GND -> C10, output caps column, vias into the bottom
    ('/GND', 'F', 0.35, (116.3, 109.29), (117.3, 109.29)),
    ('/GND', 'F', 0.8, (117.3, 109.29), (118.5, 109.6)),
    ('/GND', 'F', 0.6, (118.5, 109.65), (118.75, 108.1)),
    ('via', '/GND', 118.75, 108.1),
    ('/GND', 'F', 0.8, (111.55, 103.25), (111.55, 107.35)),
    ('/GND', 'F', 0.8, (111.55, 107.35), (111.85, 109.4)),
    *[x for y in (104.3, 106.4, 108.5) for x in (('/GND', 'F', 0.6, (111.55, y), (110.5, y)), ('via', '/GND', 110.5, y))],
    ('/GND', 'F', 0.4, (113.7, 116.025), (113.7, 117.0)), ('via', '/GND', 113.7, 117.0),     # R9
    ('/GND', 'F', 0.4, (115.8, 113.825), (115.8, 114.7)), ('via', '/GND', 115.8, 114.7),     # R10
    # BAT+: shunt -> L1 and the input cap; VIN
    ('/BAT+', 'F', 1.2, (116.7, 103.95), (119.9, 103.95)),
    ('/BAT+', 'F', 1.0, (119.9, 103.95), (119.9, 111.55)),
    ('/BAT+', 'F', 1.0, (119.9, 111.55), (118.5, 111.55)),
    ('/BAT+', 'F', 0.35, (116.3, 110.71), (117.9, 111.4)),              # U6 VIN
    ('/BAT+', 'F', 1.0, (119.9, 109.4), (122.3, 109.4)),
    ('/BAT+', 'F', 1.0, (122.3, 109.4), (122.3, 108.3)),                # into R15 pin 4 from below
    # BAT_CELL: both reverse polarity FETs -> R15 pin 1
    ('/BAT_CELL', 'F', 0.6, (122.75, 102.44), (122.75, 104.6)),
    ('/BAT_CELL', 'F', 0.6, (126.15, 102.44), (126.15, 103.9)),
    ('/BAT_CELL', 'F', 0.8, (126.15, 103.9), (122.75, 103.9)),
    # J_BATP: cell + -> drains of Q1, Q7
    ('/J_BATP', 'F', 0.6, (121.8, 100.56), (121.8, 99.6)),
    ('/J_BATP', 'F', 0.6, (125.2, 100.56), (125.2, 99.6)),
    ('/J_BATP', 'F', 1.2, (121.8, 99.6), (129.8, 99.6)),
    ('/J_BATP', 'F', 1.2, (129.8, 99.6), (129.8, 103.0)),
    # BATN: cell - -> S1 of both protection FET pairs
    ('/BATN', 'F', 1.0, (131.8, 103.0), (131.8, 105.9)),
    ('/BATN', 'F', 0.8, (131.8, 105.9), (136.36, 105.9)),
    ('/BATN', 'F', 0.6, (132.16, 105.9), (132.16, 107.05)),
    ('/BATN', 'F', 0.6, (136.36, 105.9), (136.36, 107.05)),
    # S2 of both pairs -> GND
    ('/GND', 'F', 0.6, (132.16, 108.95), (132.16, 110.3)), ('via', '/GND', 132.16, 110.3),
    ('/GND', 'F', 0.6, (136.36, 108.95), (136.36, 110.3)), ('via', '/GND', 136.36, 110.3),
]


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


def pack(fps):
    """Shelf packing, first fit: each region fills row by row (in KiCad
    coordinates), every part goes into the first of its group's regions that
    still has room."""
    state = {}

    def region(r):
        if r not in state:
            x0, y0, x1, y1 = r   # CAD -> KiCad: (y, x)
            state[r] = dict(r=(OX + y0, OY + x0, OX + y1, OY + x1), x=OX + y0, y=OY + x0, row_h=0.0)
        return state[r]

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

    for regions, refs in GROUPS:
        # tallest first wastes the least row height
        for ref in sorted(refs, key=lambda r: -round(height(r), 1)):
            fp = fps[ref]
            place_at(fp, 0, 0, 0)
            w, h, box = courtyard(fp)
            for r in regions:
                c = region(r)
                spot = fit(c, w, h)
                if spot:
                    break
            else:
                sys.exit(f'{ref} does not fit anywhere')
            x, y, row_h = spot
            dx = pcbnew.ToMM(fp.GetPosition().x - box.GetX())
            dy = pcbnew.ToMM(fp.GetPosition().y - box.GetY())
            fp.SetPosition(pcbnew.VECTOR2I(mm(x + dx), mm(y + dy)))
            c.update(x=x + w + GAP, y=y, row_h=max(row_h, h))


def outline(board):
    pts = OUTLINE
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(ax, ay))
        s.SetEnd(V(bx, by))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)


def text(board, msg, x, y, layer, size=1.0, rot=0, align=0):
    """align: -1 = text starts at (x, y), 1 = ends there, 0 = centred,
    always as read on that side of the board."""
    t = pcbnew.PCB_TEXT(board)
    t.SetText(msg)
    t.SetPosition(V(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    t.SetTextAngleDegrees(rot)
    t.SetHorizJustify({-1: pcbnew.GR_TEXT_H_ALIGN_LEFT, 0: pcbnew.GR_TEXT_H_ALIGN_CENTER,
                       1: pcbnew.GR_TEXT_H_ALIGN_RIGHT}[align])
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def pin_labels(board, fps):
    """One label per connector pin, starting 1.6 mm from the pin, running into
    the board; plus the titles. On the bottom the same texts, mirrored."""
    for ref, names, (dx, dy), sides in PIN_LABELS:
        fp = fps[ref]
        pads = sorted(fp.Pads(), key=lambda p: int(p.GetNumber()))
        for pad, name in zip(pads, names):
            q = pad.GetPosition()
            gap = LABEL_GAP.get(ref, 1.6)
            x, y = pcbnew.ToMM(q.y) - OY + dx * gap, pcbnew.ToMM(q.x) - OX + dy * gap
            # along CAD y = KiCad X (rot 0), along CAD x = KiCad Y (rot 90, reads towards -x)
            rot, run = (0, dy) if dx == 0 else (90, -dx)
            for side, layer, flip in (('T', pcbnew.F_SilkS, 1), ('B', pcbnew.B_SilkS, -1)):
                if side in sides:   # mirrored text on the bottom runs the other way
                    text(board, name, x, y, layer, 0.8, rot, -run * flip)
    for msg, x, y, rot, sides in TITLES:
        for side, layer in (('T', pcbnew.F_SilkS), ('B', pcbnew.B_SilkS)):
            if side in sides:
                text(board, msg, x, y, layer, 0.8, rot)
    for ref, name in TP_NAMES.items():
        fps[ref].Reference().SetVisible(False)
        x, y = FIXED[ref][:2]
        text(board, name, x - 0.9, y, pcbnew.F_SilkS, 0.8, 90, -1)   # towards the front edge


def hide_refs(board):
    """No reference designators on the silkscreen: next to the 0603 parts they
    only pile up, the assembly goes by coordinates, and the connectors carry
    their own labels. They stay on the fab layer."""
    for fp in board.GetFootprints():
        fp.Reference().SetVisible(False)


def drain_ties(board, fps):
    """FS8205A: pins 2 and 5 are the same drain inside the part. A track
    between them under the body tells KiCad (and the router) so; one more
    joins the drains of the two parallel parts."""
    for ref, na, ref2, nb in (('Q2', '2', 'Q2', '5'), ('Q6', '2', 'Q6', '5'), ('Q2', '5', 'Q6', '2')):
        a, b = fps[ref].FindPadByNumber(na), fps[ref2].FindPadByNumber(nb)
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(a.GetPosition())
        t.SetEnd(b.GetPosition())
        t.SetWidth(mm(0.4))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(a.GetNet())
        t.SetLocked(True)
        board.Add(t)


# GND pads in dense spots that get a fixed via: ref, pad, KiCad direction
# (None = straight out along the pad's long axis)
GND_FANOUT = [('U5', '7', None)]


def gnd_fanout(board, fps, out=0.9):
    """Fixed via next to GND pads that the router tends to wall in. The via
    sits `out` mm beyond the pad's edge."""
    for ref, num, direction in GND_FANOUT:
        fp = fps[ref]
        pad = fp.FindPadByNumber(num)
        p, c = pad.GetPosition(), fp.GetPosition()
        d = p - c
        ux, uy = direction or ((1 if d.x > 0 else -1, 0) if abs(d.x) > abs(d.y) else (0, 1 if d.y > 0 else -1))
        reach = (pad.GetSize().x if ux else pad.GetSize().y) / 2 + mm(out)
        q = pcbnew.VECTOR2I(int(p.x + ux * reach), int(p.y + uy * reach))
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(p)
        t.SetEnd(q)
        t.SetWidth(mm(0.25))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(pad.GetNet())
        t.SetLocked(True)
        board.Add(t)
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(q)
        v.SetWidth(mm(0.6))
        v.SetDrill(mm(0.3))
        v.SetNet(pad.GetNet())
        v.SetLocked(True)
        board.Add(v)


def power_copper(board, nets):
    """The fixed, wide copper of the power block (POWER_TRACKS), locked so
    the autorouter routes around it."""
    layers = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu}
    for item in POWER_TRACKS:
        if item[0] == 'via':
            _, net, x, y = item
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
            v.SetWidth(mm(0.6))
            v.SetDrill(mm(0.3))
            v.SetNet(nets[net])
            v.SetLocked(True)
            board.Add(v)
            continue
        net, layer, width, *pts = item
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(mm(ax), mm(ay)))
            t.SetEnd(pcbnew.VECTOR2I(mm(bx), mm(by)))
            t.SetWidth(mm(width))
            t.SetLayer(layers[layer])
            t.SetNet(nets[net])
            t.SetLocked(True)
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
    for x, y in OUTLINE:
        p = V(x, y)
        o.Append(p.x, p.y)
    o.Inflate(mm(-0.5), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, mm(0.01))
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
    for ref in ('H1', 'H2'):
        fps[ref].SetLocalClearance(mm(0.5))  # keep the GND pour off the screw holes
    pack(fps)
    placed = set(FIXED) | {r for _, refs in GROUPS for r in refs}
    missing = set(fps) - placed
    if missing:
        sys.exit(f'not placed: {sorted(missing)}')

    outline(board)
    drain_ties(board, fps)
    gnd_fanout(board, fps)
    power_copper(board, nets)
    gnd_pour(board, nets['/GND'])
    pin_labels(board, fps)
    hide_refs(board)
    logo = load_fp('powerboard:KidsLab_Logo')
    logo.SetReference('LOGO1')
    board.Add(logo)
    place_at(logo, *LOGO_AT, 0)
    logo.Flip(logo.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)

    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(PCB)
    print(f'{len(fps)} footprints, {len(nets)} nets -> {PCB}')


if __name__ == '__main__':
    main()
