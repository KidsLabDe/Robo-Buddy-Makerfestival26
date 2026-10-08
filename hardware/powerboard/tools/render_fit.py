#!/usr/bin/env python3
"""Check the fit of the board in the robot from cad/MF26-Roboter.step.

Cuts the shell at a few heights and draws the cuts over the board outline and
the courtyards of all parts. Writes ansichten/passung_schnitte.png; the board
file itself is not changed.

    python3 hardware/powerboard/tools/render_fit.py

The STEP is turned into a mesh by KiCad (VRML export of a scratch board that
carries it as a 3D model); the mesh keeps the CAD coordinates.
"""
import os
import re
import subprocess
import sys
import tempfile

import matplotlib
import numpy as np
import pcbnew

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import OUTLINE, OX, OY, PCB, PROJ  # noqa: E402

STEP = os.path.abspath(os.path.join(PROJ, '..', '..', 'cad', 'MF26-Roboter.step'))
OUT = os.path.join(PROJ, 'ansichten', 'passung_schnitte.png')
BOARD_Z = 12.5    # CAD z of the base plate top = bottom of the board
# heights to cut at, and what sits there
CUTS = [(13.5, 'z = 13,5: Platine'),
        (20.0, 'z = 20: SMD, Leisten'),
        (27.0, 'z = 27: Oberkante ESP auf Buchsenleisten')]
TALL = {'U4', 'J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8', 'J9', 'J10', 'J11', 'SW1'}


def mesh():
    """Triangles of the robot, in CAD coordinates (mm)."""
    with tempfile.TemporaryDirectory() as d:
        pcb, wrl = os.path.join(d, 'robot.kicad_pcb'), os.path.join(d, 'robot.wrl')
        board = pcbnew.BOARD()
        fp = pcbnew.FOOTPRINT(board)
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = STEP
        fp.Models().append(m)
        board.Add(fp)
        board.Save(pcb)
        subprocess.run(['kicad-cli', 'pcb', 'export', 'vrml', '--units', 'mm', '-o', wrl, pcb],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        text = open(wrl, encoding='utf-8').read()
    # Bodies with their own placement (the display) sit in Transform nodes
    # that only translate; collect the offset in effect at every shape.
    offsets, stack, pending = [], [], np.zeros(3)
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('translation '):
            pending = np.array(s.split()[1:4], float)
        elif s == 'children [':
            stack.append(pending)
            pending = np.zeros(3)
        elif s == '] }':
            stack.pop()
        elif re.match(r'DEF SHAPE_\d+ Shape', s):
            offsets.append(sum(stack, np.zeros(3)))
    tris = []
    for shape, off in zip(re.split(r'DEF SHAPE_\d+ Shape', text)[1:], offsets):
        pts = re.search(r'Coordinate \{ point \[(.*?)\]', shape, re.S)
        idx = re.search(r'coordIndex \[(.*?)\]', shape, re.S)
        if not pts or not idx:
            continue
        # VRML units are 0.1 inch
        p = (np.array(re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', pts.group(1)), float).reshape(-1, 3)
             + off) * 2.54
        p[:, 2] -= 0.8   # KiCad puts models on the top face of its 1.6 mm scratch board
        face = []
        for k in map(int, re.findall(r'-?\d+', idx.group(1))):
            if k >= 0:
                face.append(k)
                continue
            tris += [p[[face[0], face[j], face[j + 1]]] for j in range(1, len(face) - 1)]
            face = []
    return np.array(tris)


def cut(tris, z):
    d = tris[:, :, 2] - z
    hit = ~((d > 0).all(1) | (d < 0).all(1))
    segs = []
    for v, dd in zip(tris[hit], d[hit]):
        pts = [v[i] + (v[(i + 1) % 3] - v[i]) * dd[i] / (dd[i] - dd[(i + 1) % 3])
               for i in range(3) if dd[i] * dd[(i + 1) % 3] < 0]
        if len(pts) == 2:
            segs.append((pts[0][:2], pts[1][:2]))
    return segs


def courtyards():
    """Courtyard boxes of all parts, as CAD (x, y) polygons."""
    board = pcbnew.LoadBoard(PCB)
    out = []
    for fp in board.GetFootprints():
        poly = fp.GetCourtyard(pcbnew.F_CrtYd)
        if not poly.OutlineCount():
            continue
        o = poly.Outline(0)
        pts = [(pcbnew.ToMM(o.CPoint(i).y) - OY, pcbnew.ToMM(o.CPoint(i).x) - OX) for i in range(o.PointCount())]
        out.append((fp.GetReference(), pts))
    return out


def main():
    tris = mesh()
    parts = courtyards()
    fig, axes = plt.subplots(1, len(CUTS), figsize=(7 * len(CUTS), 7.5))
    ol = np.array(OUTLINE + OUTLINE[:1])
    for ax, (z, title) in zip(axes, CUTS):
        for a, b in cut(tris, z):
            ax.plot([a[1], b[1]], [a[0], b[0]], color='0.2', lw=0.7)
        ax.plot(ol[:, 1], ol[:, 0], color='tab:green', lw=1.5)
        for ref, pts in parts:
            if z > BOARD_Z + 4 and ref not in TALL:
                continue
            p = np.array(pts + pts[:1])
            col = 'tab:red' if ref in TALL else 'tab:blue'
            ax.plot(p[:, 1], p[:, 0], color=col, lw=0.6)
            if ref in TALL:
                ax.text(p[:, 1].mean(), p[:, 0].mean(), ref, fontsize=6, ha='center', va='center', color=col)
        ax.set_title(title, fontsize=10)
        ax.set_aspect('equal')
        ax.invert_yaxis()   # front (display) at the top, like the board in KiCad
        ax.set_xlim(-8, 60)
        ax.set_ylim(64, -14)
        ax.grid(True, lw=0.3)
        ax.tick_params(labelsize=7)
        ax.set_xlabel('CAD y [mm]', fontsize=8)
        ax.set_ylabel('CAD x [mm]', fontsize=8)
    fig.suptitle('Platine (gruen), Bauteile (rot: hohe THT-Teile, blau: SMD), Schnitt durch das Gehaeuse (grau)')
    fig.tight_layout()
    fig.savefig(OUT, dpi=110)
    print(OUT)


if __name__ == '__main__':
    main()
