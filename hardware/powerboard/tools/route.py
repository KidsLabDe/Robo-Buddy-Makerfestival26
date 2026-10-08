#!/usr/bin/env python3
"""Route powerboard.kicad_pcb with Freerouting, then widen the power tracks.

    python3 hardware/powerboard/tools/gen_pcb.py     # placement, no tracks
    python3 hardware/powerboard/tools/route.py       # tracks

Freerouting is not part of KiCad. The jar is looked up in $FREEROUTING_JAR,
else ~/.cache/freerouting/freerouting-2.4.1.jar
(https://github.com/freerouting/freerouting/releases/tag/v2.4.1).

1. Some nets are routed first and locked: the short connections at the
   edge (switch, LED, ESP pin 1) that the long signal bundles would
   otherwise wall off, and in some VARIANTS the power paths. They are routed alone
   on a copy of the board without the other nets, then locked.
2. Everything else is routed around them. Power nets are routed narrow,
   so they can still reach the fine pitch pads of the TPS61023 (SOT-563)
   and the INA226 (TSSOP-10).
   Every variant is checked by KiCad; the one with the fewest open
   connections is kept.
3. tools/maze.py closes what is still open. Then every power track is made
   as wide as the DRC allows, trying
   the widths in WIDEN one after the other. Tracks that would cause a
   violation keep their previous width.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import PCB  # noqa: E402  (also patches KiCad's iterators for Python 3.14)

JAR = os.environ.get('FREEROUTING_JAR',
                     os.path.expanduser('~/.cache/freerouting/freerouting-2.4.1.jar'))
WIDEN = [1.2, 1.0, 0.8, 0.6, 0.5, 0.4]
EDGE = ['/SW_GATE', '/CHRG_N', '/LED_A', '/VSYS', '/3V3', '/SERVO_EN', '/SENSE_P', '/SENSE_N']
POWER = ['/J_BATP', '/BAT_CELL', '/BAT+', '/BATN', '/FET_D', '/V5_SERVO', '/BAT_SW', '/BOOST_SW']
# Freerouting's result depends a lot on the order. Try these (nets routed
# first, width of power nets while routing in mm, passes) and keep the best.
VARIANTS = [(EDGE, 0.3, 40), (EDGE + POWER, 0.3, 40), (EDGE, 0.25, 40), (EDGE + ['/BAT+', '/V5_SERVO'], 0.3, 40),
            (EDGE, 0.3, 100), (EDGE + POWER, 0.25, 100), (EDGE, 0.25, 100), (EDGE + POWER, 0.3, 100)]


def power_nets(board):
    board.SynchronizeNetsAndNetClasses(True)
    return {str(n) for n, net in board.GetNetsByName().items()   # keys are wxString
            if 'Power' in str(net.GetNetClassName()).split(',')}


def um(v):
    return round(v / 1000.0, 3)


def bake_rotations(board, dsn):
    """Freerouting misplaces pads of parts rotated by odd angles (here 126.5
    and 53.5 deg along the slanted walls) and then cannot reach them. For
    every such part, write an image with the rotation already applied to the
    pads (and keepouts) and place it unrotated. Coordinates: DSN um, y up."""
    text = open(dsn, encoding='utf-8').read()
    images, comps = [], []
    for fp in board.GetFootprints():
        rot = fp.GetOrientationDegrees() % 360
        if not fp.Pads() or abs(rot / 45 - round(rot / 45)) < 1e-6:
            continue
        ref = str(fp.GetReference())
        c = fp.GetPosition()
        pins, stacks = [], []
        for i, pad in enumerate(fp.Pads()):
            num = str(pad.GetNumber()) or f'@{i}'
            q = pad.GetPosition()
            shapes = []
            for layer, lname in ((pcbnew.F_Cu, 'F.Cu'), (pcbnew.B_Cu, 'B.Cu')):
                if not pad.IsOnLayer(layer):
                    continue
                o = pad.GetEffectivePolygon(layer, pcbnew.ERROR_OUTSIDE).Outline(0)
                pts = ' '.join(f'{um(o.CPoint(k).x - q.x)} {um(q.y - o.CPoint(k).y)}'
                               for k in range(o.PointCount()))
                shapes.append(f'      (shape (polygon {lname} 0 {pts}))')
            stack = f'BAKED_{ref}_{i}'
            stacks.append(f'    (padstack {stack}\n' + '\n'.join(shapes) + '\n      (attach off)\n    )')
            pins.append(f'      (pin {stack} "{num}" {um(q.x - c.x)} {um(c.y - q.y)})')
        keepouts = []
        for z in fp.Zones():
            o = z.Outline().Outline(0)
            pts = ' '.join(f'{um(o.CPoint(k).x - c.x)} {um(c.y - o.CPoint(k).y)}' for k in range(o.PointCount()))
            for lname in ('F.Cu', 'B.Cu'):
                keepouts.append(f'      (keepout "" (polygon {lname} 0 {pts}))')
        images.append(f'    (image BAKED_{ref}\n' + '\n'.join(pins + keepouts) + '\n    )\n' + '\n'.join(stacks))
        # move the part out of its component block into its own, unrotated
        m = re.search(rf'\n\s*\(place {re.escape(ref)} (\S+) (\S+) front \S+ (\(PN [^\n]*\))\)', text)
        if not m:
            sys.exit(f'{ref}: placement not found in DSN')
        text = text[:m.start()] + text[m.end():]
        comps.append(f'    (component BAKED_{ref}\n      (place {ref} {m.group(1)} {m.group(2)} front 0 {m.group(3)})\n    )')
    # component blocks left without any placement
    text = re.sub(r'\n    \(component [^\n]*\n    \)', '', text)
    text = text.replace('\n  (library\n', '\n' + '\n'.join(comps) + '\n  )\n  (library\n' + '\n'.join(images) + '\n', 1)
    # the line before was the end of (placement: drop the old one
    text = text.replace('\n  )\n' + '\n'.join(comps) + '\n  )\n  (library', '\n' + '\n'.join(comps) + '\n  )\n  (library', 1)
    open(dsn, 'w', encoding='utf-8').write(text)


def straighten_outline(board, dsn, inset=0.35):
    """Freerouting approximates the clearance at slanted board edges so
    coarsely that pads up to ~2 mm from the rear walls become unreachable.
    Give it the bounding rectangle as the outline instead, and the parts of
    that rectangle outside the real board as keepouts, grown by `inset` so
    the 0.5 mm copper-to-edge rule still holds (Freerouting adds 0.15)."""
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    box = outline.BBox()
    x0, y0, x1, y1 = box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom()
    rest = pcbnew.SHAPE_POLY_SET()
    rest.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        rest.Append(x, y)
    rest.BooleanSubtract(outline)
    keepouts = []
    for i in range(rest.OutlineCount()):
        part = pcbnew.SHAPE_POLY_SET()
        part.AddOutline(rest.Outline(i))
        part.Inflate(pcbnew.FromMM(inset), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, pcbnew.FromMM(0.01))
        o = part.Outline(0)
        pts = ' '.join(f'{um(o.CPoint(k).x)} {um(-o.CPoint(k).y)}' for k in range(o.PointCount()))
        keepouts += [f'    (keepout "" (polygon {layer} 0 {pts}))' for layer in ('F.Cu', 'B.Cu')]
    # screw holes: KiCad wants 0.25 mm from the hole, plus margin for the screw head
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                continue
            q, r = pad.GetPosition(), pad.GetDrillSize().x / 2 + pcbnew.FromMM(inset)
            pts = ' '.join(f'{um(q.x + r * math.cos(a))} {um(-(q.y + r * math.sin(a)))}'
                           for a in (k * math.pi / 8 for k in range(16)))
            keepouts += [f'    (keepout "" (polygon {layer} 0 {pts}))' for layer in ('F.Cu', 'B.Cu')]
    rect = (f'    (boundary\n      (path pcb 0  {um(x0)} {um(-y0)}  {um(x1)} {um(-y0)}  {um(x1)} {um(-y1)}'
            f'  {um(x0)} {um(-y1)}  {um(x0)} {um(-y0)})\n    )\n' + '\n'.join(keepouts))
    text = open(dsn, encoding='utf-8').read()
    m = re.search(r'    \(boundary\n.*?\n    \)', text, re.S)
    text = text[:m.start()] + rect + text[m.end():]
    # GND is routed as tracks like any other net: the pours are added later and
    # only reinforce it, so GND stays connected even where signals cut a pour
    text = re.sub(r'\n    \(plane [^\n]*(\n      [^\n]*)*\)', '', text, count=1)
    open(dsn, 'w', encoding='utf-8').write(text)


def freeroute(board, d, name, width, passes):
    dsn, ses = os.path.join(d, name + '.dsn'), os.path.join(d, name + '.ses')
    power = board.GetDesignSettings().m_NetSettings.GetNetClassByName('Power')
    nominal = power.GetTrackWidth()
    power.SetTrackWidth(pcbnew.FromMM(width))
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        sys.exit('DSN export failed')
    power.SetTrackWidth(nominal)
    bake_rotations(board, dsn)
    straighten_outline(board, dsn)
    subprocess.run(['java', '-jar', JAR, '-de', dsn, '-do', ses, '-mp', str(passes),
                    '--gui.enabled=false'], check=True)
    return ses


def import_ses(board, ses):
    """Import the tracks. The session also carries placements (with the baked
    parts unrotated): put every footprint back where it was."""
    keep = {str(fp.GetReference()): (fp.GetPosition(), fp.GetOrientationDegrees())
            for fp in board.GetFootprints()}
    if not pcbnew.ImportSpecctraSES(board, ses):
        sys.exit('SES import failed')
    for fp in board.GetFootprints():
        pos, rot = keep[str(fp.GetReference())]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pos)


def autoroute(board, d, first, width, passes):
    # stage 1: only the `first` nets, on a copy where every other pad has no net
    only = pcbnew.LoadBoard(PCB)
    only.SynchronizeNetsAndNetClasses(True)
    for fp in only.GetFootprints():
        for pad in fp.Pads():
            if str(pad.GetNetname()) not in first:
                pad.SetNetCode(0)
    import_ses(board, freeroute(only, d, 'first', width, passes))
    for t in board.GetTracks():
        t.SetLocked(True)
    # stage 2: the rest, around the locked tracks
    import_ses(board, freeroute(board, d, 'all', width, passes))


def drc_report(path):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'drc.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', out, path],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return json.load(open(out, encoding='utf-8'))


def open_signals(board):
    """Connections KiCad still sees as open, apart from GND (the pours do that)."""
    pcbnew.SaveBoard(PCB, board)
    return [v for v in drc_report(PCB)['unconnected_items']
            if not all('[/GND]' in i['description'] for i in v['items'])]


def drc_items(path):
    """UUIDs of all items involved in DRC violations (ignoring silkscreen and
    unconnected items)."""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'drc.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', out, path],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        rep = json.load(open(out, encoding='utf-8'))
    bad = set()
    for v in rep.get('violations', []):
        if v['type'].startswith('silk') or v['type'] in ('text_height', 'lib_footprint_mismatch'):
            continue
        bad |= {i['uuid'] for i in v.get('items', [])}
    return bad


def widen(board, power):
    tracks = [t for t in board.GetTracks()
              if t.GetClass() in ('PCB_TRACK', 'PCB_ARC') and str(t.GetNetname()) in power]
    for w in WIDEN:
        trial = {}
        for t in tracks:
            key = t.m_Uuid.AsString()
            if t.GetWidth() >= pcbnew.FromMM(w):
                continue
            trial[key] = (t, t.GetWidth())
            t.SetWidth(pcbnew.FromMM(w))
        # a reverted track can free its neighbour, so repeat until clean
        while trial:
            pcbnew.SaveBoard(PCB, board)
            bad = drc_items(PCB) & set(trial)
            if not bad:
                break
            for key in bad:
                t, old = trial.pop(key)
                t.SetWidth(old)
        print(f'{w} mm: {len(trial)} Bahnen verbreitert')


def gnd_top_and_stitch(board, pitch=1.5, keep=0.55):
    """GND pour on the top as well, and stitching vias wherever both pours
    have copper around the via (`keep` mm radius). The long signals on the
    bottom cut the bottom pour into pieces; the top pour and the vias join
    them up again. No vias under parts or under the logo."""
    gnd = board.FindNet('/GND')
    bottom = board.GetArea(0)
    top = pcbnew.ZONE(board)
    top.SetLayer(pcbnew.F_Cu)
    top.SetNet(gnd)
    top.SetLocalClearance(bottom.GetLocalClearance())
    top.SetMinThickness(bottom.GetMinThickness())
    top.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    top.Outline().Append(bottom.Outline())
    board.Add(top)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    blocked = [fp.GetCourtyard(side).BBox() for fp in board.GetFootprints()
               for side in (pcbnew.F_CrtYd, pcbnew.B_CrtYd) if fp.GetCourtyard(side).OutlineCount()]
    blocked += [fp.GetBoundingBox(False) for fp in board.GetFootprints() if str(fp.GetReference()) == 'LOGO1']
    box = bottom.Outline().BBox()
    ring = [(math.cos(k * math.pi / 4), math.sin(k * math.pi / 4)) for k in range(8)] + [(0, 0)]
    vias = []
    step = pcbnew.FromMM(pitch)
    for x in range(box.GetLeft(), box.GetRight(), step):
        for y in range(box.GetTop(), box.GetBottom(), step):
            p = pcbnew.VECTOR2I(x, y)
            if any(b.Contains(p) for b in blocked):
                continue
            if all(z.HitTestFilledArea(layer, pcbnew.VECTOR2I(int(x + dx * pcbnew.FromMM(keep)),
                                                              int(y + dy * pcbnew.FromMM(keep))))
                   for z, layer in ((top, pcbnew.F_Cu), (bottom, pcbnew.B_Cu)) for dx, dy in ring):
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(p)
                v.SetWidth(pcbnew.FromMM(0.6))
                v.SetDrill(pcbnew.FromMM(0.3))
                v.SetNet(gnd)
                board.Add(v)
                vias.append(v)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    bad = drc_items(PCB)
    for v in vias:
        if v.m_Uuid.AsString() in bad:
            board.Remove(v)
    print(f'{len(vias)} Masse-Vias gesetzt')


def main():
    if not os.path.exists(JAR):
        sys.exit(f'Freerouting fehlt: {JAR}')
    with tempfile.TemporaryDirectory() as d:
        best = None
        for i, (first, width, passes) in enumerate(VARIANTS):
            board = pcbnew.LoadBoard(PCB)      # still unrouted
            autoroute(board, d, first, width, passes)
            path = os.path.join(d, f'v{i}.kicad_pcb')
            shutil.copy(os.path.join(os.path.dirname(PCB), 'powerboard.kicad_pro'), path[:-10] + '.kicad_pro')
            pcbnew.SaveBoard(path, board)
            n = len(drc_report(path)['unconnected_items'])
            print(f'Variante {i}: {n} offen')
            if best is None or n < best[0]:
                best = (n, path)
            if n == 0:
                break
        board = pcbnew.LoadBoard(best[1])
    import maze     # grid router for what Freerouting left open
    maze.finish(board)              # before widening: the wide power tracks take the room
    power = power_nets(board)
    widen(board, power)
    gnd_top_and_stitch(board)
    maze.finish(board)              # GND pads that the pours do not reach
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    dangling = {i['uuid'] for v in drc_report(PCB)['violations'] if v['type'] == 'via_dangling' for i in v['items']}
    for t in list(board.GetTracks()):
        if t.GetClass() == 'PCB_VIA' and t.m_Uuid.AsString() in dangling:
            board.Remove(t)
    print(f'{len(dangling)} haengende Vias entfernt')
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    print(f'offen: {len(open_signals(board))}')
    print(f'-> {PCB}')


if __name__ == '__main__':
    main()
