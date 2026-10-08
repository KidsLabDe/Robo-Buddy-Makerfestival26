#!/usr/bin/env python3
"""Close the connections Freerouting left open with a small grid router.

    python3 hardware/powerboard/tools/maze.py

For every connection KiCad reports as open, the board is rasterised at GRID
on both copper layers: copper of other nets (grown by clearance and half the
track width), the board edge and the screw holes are blocked. A* then finds
the shortest path from one end to the other, changing layers through a via
where it has to. The result is checked by the DRC; anything that would
violate a rule is taken out again.
"""
import heapq
import math
import os
import re
import sys

import numpy as np
import pcbnew
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import PCB  # noqa: E402  (also patches KiCad's iterators for Python 3.14)
from route import drc_report, power_nets  # noqa: E402

GRID = 0.1          # mm
CLEAR = 0.155       # mm, a hair more than the 0.15 rule
EDGE = 0.55         # mm, copper to board edge
VIA_D, VIA_DRILL = 0.6, 0.3
VIA_COST = 25       # in grid steps
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)

nm = pcbnew.FromMM


class Grid:
    def __init__(self, board):
        box = board.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = box.GetLeft(), box.GetTop()
        self.w = int(pcbnew.ToMM(box.GetWidth()) / GRID) + 2
        self.h = int(pcbnew.ToMM(box.GetHeight()) / GRID) + 2

    def cell(self, p):
        return (int(round(pcbnew.ToMM(p.x - self.x0) / GRID)), int(round(pcbnew.ToMM(p.y - self.y0) / GRID)))

    def point(self, c):
        return pcbnew.VECTOR2I(self.x0 + nm(c[0] * GRID), self.y0 + nm(c[1] * GRID))

    def blank(self):
        return Image.new('1', (self.w, self.h), 0)

    def draw(self, img, poly, value=1):
        d = ImageDraw.Draw(img)
        for i in range(poly.OutlineCount()):
            o = poly.Outline(i)
            pts = [self.cell(o.CPoint(k)) for k in range(o.PointCount())]
            if len(pts) > 2:
                d.polygon(pts, fill=value)


def copper_items(board):
    """(item, layer) for every piece of copper: pads, tracks, vias, footprint copper."""
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            for layer in LAYERS:
                if pad.IsOnLayer(layer):
                    yield pad, layer
        for g in fp.GraphicalItems():
            if g.GetLayer() in LAYERS:
                yield g, g.GetLayer()
    for t in board.GetTracks():
        for layer in LAYERS:
            if t.IsOnLayer(layer):
                yield t, layer


def item_net(item):
    return item.GetNetCode() if hasattr(item, 'GetNetCode') else -1


def masks(board, grid, net, grow):
    """Blocked cells per layer for a track of half-width `grow` (mm) on `net`."""
    out = {}
    for layer in LAYERS:
        img = grid.blank()
        for item, ilayer in copper_items(board):
            if ilayer != layer or (item_net(item) == net and net > 0):
                continue
            poly = pcbnew.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(poly, layer, nm(CLEAR + grow), nm(0.01), pcbnew.ERROR_OUTSIDE)
            grid.draw(img, poly)
        # holes of every pad (also the screw holes)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetDrillSize().x > 0 and (pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH or item_net(pad) != net):
                    r = pad.GetDrillSize().x / 2 + nm(0.25 + grow)
                    c = grid.cell(pad.GetPosition())
                    rr = pcbnew.ToMM(r) / GRID
                    ImageDraw.Draw(img).ellipse((c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr), fill=1)
        out[layer] = np.array(img, dtype=bool)
    # board edge: everything outside the outline, grown inwards
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    inner = pcbnew.SHAPE_POLY_SET(outline)
    inner.Inflate(-nm(EDGE + grow), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, nm(0.01))
    img = grid.blank()
    grid.draw(img, inner)
    inside = np.array(img, dtype=bool)
    for layer in LAYERS:
        out[layer] |= ~inside
    return out


def targets(grid, items):
    """Cells covered by the copper of `items` (list of (item, layer))."""
    cells = set()
    for item, layer in items:
        img = grid.blank()
        poly = pcbnew.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(poly, layer, 0, nm(0.01), pcbnew.ERROR_INSIDE)
        grid.draw(img, poly)
        ys, xs = np.nonzero(np.array(img, dtype=bool))
        cells |= {(int(x), int(y), layer) for x, y in zip(xs, ys)}
    return cells


def fill_cells(board, grid, net, shrink=0.45):
    """Cells inside the filled pours of `net`, shrunk so a via fits."""
    cells = set()
    for i in range(board.GetAreaCount()):
        z = board.GetArea(i)
        if z.GetNetCode() != net.GetNetCode():
            continue
        layer = z.GetLayer()
        poly = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(layer))
        poly.Inflate(-nm(shrink), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, nm(0.01))
        img = grid.blank()
        grid.draw(img, poly)
        ys, xs = np.nonzero(np.array(img, dtype=bool))
        cells |= {(int(x), int(y), layer) for x, y in zip(xs, ys)}
    return cells


def astar(free, via_ok, start, goal):
    goal_xy = [(x, y) for x, y, _ in goal]
    gx = np.array([g[0] for g in goal_xy])
    gy = np.array([g[1] for g in goal_xy])

    def h(x, y):
        return float(np.min(np.hypot(gx - x, gy - y)))

    start_set = set(start)
    open_ = [(h(x, y), 0.0, (x, y, l)) for x, y, l in start]
    heapq.heapify(open_)
    came = {s: None for s in start}
    cost = {s: 0.0 for s in start}
    steps = [(dx, dy, math.hypot(dx, dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
    flip = {LAYERS[0]: LAYERS[1], LAYERS[1]: LAYERS[0]}
    n = 0
    while open_:
        _, g, cur = heapq.heappop(open_)
        if cur in goal:
            path = []
            while cur:
                path.append(cur)
                cur = came[cur]
            return path[::-1]
        if g > cost.get(cur, 1e18):
            continue
        n += 1
        if n > 400000:
            return None
        x, y, l = cur
        nbrs = [((x + dx, y + dy, l), c) for dx, dy, c in steps]
        if via_ok[y, x]:
            nbrs.append(((x, y, flip[l]), VIA_COST))
        for (nx, ny, nl), c in nbrs:
            if not (0 <= nx < free[nl].shape[1] and 0 <= ny < free[nl].shape[0]):
                continue
            # the pads at both ends are always passable: at fine pitch the
            # neighbour's clearance would otherwise cover the pad itself
            if not free[nl][ny, nx] and (nx, ny, nl) not in goal and (nx, ny, nl) not in start_set:
                continue
            ng = g + c
            if ng < cost.get((nx, ny, nl), 1e18):
                cost[(nx, ny, nl)] = ng
                came[(nx, ny, nl)] = cur
                heapq.heappush(open_, (ng + h(nx, ny), ng, (nx, ny, nl)))
    return None


def build(board, grid, path, net, width):
    """Tracks and vias along a grid path. The path is split where it changes
    layer (a via there); within a layer only the corners are kept."""
    runs, cur = [], [path[0]]
    for a, b in zip(path, path[1:]):
        if b[2] != a[2]:
            runs.append(cur)
            cur = [b]
        else:
            cur.append(b)
    runs.append(cur)
    made = []
    for k, run in enumerate(runs):
        corners = [run[0]]
        for a, b, c in zip(run, run[1:], run[2:]):
            if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
                corners.append(b)
        if len(run) > 1:
            corners.append(run[-1])
        for a, b in zip(corners, corners[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(grid.point(a))
            t.SetEnd(grid.point(b))
            t.SetWidth(nm(width))
            t.SetLayer(a[2])
            t.SetNet(net)
            board.Add(t)
            made.append(t)
        if k + 1 < len(runs):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(grid.point(run[-1]))
            v.SetWidth(nm(VIA_D))
            v.SetDrill(nm(VIA_DRILL))
            v.SetNet(net)
            board.Add(v)
            made.append(v)
    return made


def find_item(board, desc, pos):
    """The pad, track or via the DRC report means by `desc` at `pos`."""
    p = pcbnew.VECTOR2I(nm(pos['x']), nm(pos['y']))
    best = None
    for item, layer in copper_items(board):
        if not hasattr(item, 'GetNetCode'):
            continue
        q = item.GetPosition() if item.GetClass() != 'PCB_TRACK' else item.GetStart()
        d = (q - p).EuclideanNorm()
        if best is None or d < best[0]:
            best = (d, item)
    return best[1] if best and best[0] < nm(0.05) else None


def finish(board):
    grid = Grid(board)
    power = power_nets(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    added = []
    for v in drc_report(PCB)['unconnected_items']:
        ends = []
        for i in v['items']:
            if i['description'].startswith('Zone'):
                continue
            item = find_item(board, i['description'], i['pos'])
            if item is not None:
                ends.append(item)
        name = re.search(r'\[(/[^\]]+)\]', v['items'][0]['description'])
        if not name:
            continue
        net = board.FindNet(name.group(1))
        width = 0.4 if name.group(1) in power else 0.2
        if len(ends) == 1:
            # pad that misses a GND pour: route to any other copper of the net
            others = [(it, l) for it, l in copper_items(board)
                      if item_net(it) == net.GetNetCode() and it != ends[0]]
            goal_items = others
            extra_goal = fill_cells(board, grid, net)
        elif len(ends) == 2:
            goal_items = [(ends[1], l) for l in LAYERS if ends[1].IsOnLayer(l)]
            extra_goal = set()
        else:
            continue
        start_items = [(ends[0], l) for l in LAYERS if ends[0].IsOnLayer(l)]
        start = targets(grid, start_items)
        goal = targets(grid, goal_items) | extra_goal
        mv = masks(board, grid, net.GetNetCode(), VIA_D / 2)
        via_ok = ~mv[LAYERS[0]] & ~mv[LAYERS[1]]
        path = None
        for w in (width, 0.25, 0.2, 0.15):  # narrower if the nominal width does not get through
            if w > width:
                continue
            m = masks(board, grid, net.GetNetCode(), w / 2)
            free = {l: ~m[l] for l in LAYERS}
            path = astar(free, via_ok, start, goal)
            if path:
                width = w
                break
        desc = ' / '.join(i['description'][:45] for i in v['items'])
        if not path:
            print(f'kein Weg: {desc}')
            continue
        made = build(board, grid, path, net, width)
        added += made
        print(f'verlegt ({len(made)} Teile): {desc}')
    # keep only what the DRC accepts
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    rep = drc_report(PCB)
    bad = {i['uuid'] for v in rep['violations'] if not v['type'].startswith('silk')
           and v['type'] not in ('courtyards_overlap', 'starved_thermal') for i in v.get('items', [])}
    removed = [a for a in added if a.m_Uuid.AsString() in bad]
    for a in removed:
        board.Remove(a)
    if removed:
        print(f'{len(removed)} Teile wegen DRC wieder entfernt')
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)


def main():
    board = pcbnew.LoadBoard(PCB)
    finish(board)
    rep = drc_report(PCB)
    print(f"offen: {len(rep['unconnected_items'])}")
    for v in rep['unconnected_items']:
        print('  ', ' / '.join(i['description'][:60] for i in v['items']))


if __name__ == '__main__':
    main()
