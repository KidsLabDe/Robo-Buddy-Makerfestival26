#!/usr/bin/env python3
"""Draw the rework for issue #1 (LM66100 CE to VOUT) into ansichten/rework_u3_ce.png.

    python3 hardware/powerboard/tools/render_rework.py

Geometry (outline, pads, tracks, GND fill) comes from powerboard.kicad_pcb.
"""
import math
import os
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Circle, FancyBboxPatch
from matplotlib.path import Path
from matplotlib.patches import PathPatch
import numpy as np
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
PCB = os.path.join(PROJ, 'powerboard.kicad_pcb')
OUT = os.path.join(PROJ, 'ansichten', 'rework_u3_ce.png')

CU, FILL, PAD = '#c8792f', '#f3dcc4', '#d9a441'
BOARD, EDGE = '#2f6b3a', '#1c3d22'
WIRE, BAD, OK = '#b5179e', '#d62828', '#2a9d8f'
mm = pcbnew.ToMM


def outline(poly, i):
    o = poly.Outline(i)
    return [(mm(o.CPoint(k).x), mm(o.CPoint(k).y)) for k in range(o.PointCount())]


def load():
    b = pcbnew.LoadBoard(PCB)
    text = open(PCB).read()
    edges = [tuple(map(float, m)) for m in re.findall(
        r'\(gr_line\s+\(start ([\d.-]+) ([\d.-]+)\)\s+\(end ([\d.-]+) ([\d.-]+)\).*?\(layer "Edge.Cuts"\)', text, re.S)]
    segs = []
    for m in re.finditer(r'\(segment\s+\(start ([\d.-]+) ([\d.-]+)\)\s+\(end ([\d.-]+) ([\d.-]+)\)\s+'
                         r'\(width ([\d.]+)\).*?\(layer "([^"]+)"\)\s+\(net "([^"]*)"\)', text, re.S):
        x1, y1, x2, y2, w = map(float, m.groups()[:5])
        segs.append((x1, y1, x2, y2, w, m.group(6), m.group(7)))
    fills = []
    for i in range(b.GetAreaCount()):
        z = b.GetArea(i)
        if not z.IsOnLayer(pcbnew.F_Cu):
            continue
        fp = z.GetFilledPolysList(pcbnew.F_Cu)
        fills += [outline(fp, k) for k in range(fp.OutlineCount())]
    pads, refs = [], []
    for f in b.GetFootprints():
        p0 = f.GetPosition()
        refs.append((f.GetReference(), mm(p0.x), mm(p0.y)))
        for p in f.Pads():
            if not p.IsOnLayer(pcbnew.F_Cu):
                continue
            poly = p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE)
            pads.append((f.GetReference(), p.GetNumber(), p.GetNetname().lstrip('/'), outline(poly, 0)))
    return edges, segs, fills, pads, refs


def capsule(x1, y1, x2, y2, r, n=8):
    """Leiterbahn als Polygon in mm (Breite 2 r, runde Enden)."""
    a = math.atan2(y2 - y1, x2 - x1)
    pts = [(x2 + r * math.cos(a + math.pi / 2 - k * math.pi / n), y2 + r * math.sin(a + math.pi / 2 - k * math.pi / n))
           for k in range(n + 1)]
    pts += [(x1 + r * math.cos(a - math.pi / 2 - k * math.pi / n), y1 + r * math.sin(a - math.pi / 2 - k * math.pi / n))
            for k in range(n + 1)]
    return pts


def draw_copper(ax, edges, segs, fills, pads, fill_alpha=1.0):
    ax.set_facecolor(BOARD)
    for pts in fills:
        ax.add_patch(Polygon(pts, closed=True, fc=FILL, ec='none', alpha=fill_alpha, zorder=1))
    for x1, y1, x2, y2, w, layer, net in segs:
        if layer == 'F.Cu':
            ax.add_patch(Polygon(capsule(x1, y1, x2, y2, w / 2), closed=True, fc=CU, ec='none', zorder=2))
    for ref, num, net, pts in pads:
        ax.add_patch(Polygon(pts, closed=True, fc=PAD, ec='#8a6418', lw=0.4, zorder=3))
    for x1, y1, x2, y2 in edges:
        ax.plot([x1, x2], [y1, y2], color='#f1f1f1', lw=2, zorder=4)


def esp_outline(pads):
    """Umriss des gesteckten C6-Zero (18 × 23,5 mm, mittig über den Pads von U4)."""
    pts = np.array([np.mean(p, axis=0) for ref, num, net, p in pads if ref == 'U4'])
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c)
    along, across = vt[0], vt[1]
    return [tuple(c + sa * 23.5 / 2 * along + sb * 18 / 2 * across) for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def setup(ax, x0, x1, y0, y1):
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)  # KiCad: y nach unten
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])


# Gehäuse SC-70-6 (Datenblatt DCK): Körper 1,25 × 2,0 mm, Beinchen bis 2,1 mm Spannweite
U3 = (110.995, 134.195)
BODY_W, BODY_H, LEAD_TIP, LEAD_W = 1.25, 2.0, 1.05, 0.25
PITCH = 0.65


def lead_y(n):
    return U3[1] + {1: -1, 2: 0, 3: 1, 6: -1, 5: 0, 4: 1}[n] * PITCH


def draw_u3(ax, lifted=False):
    cx, cy = U3
    for n in (1, 2, 3, 4, 5, 6):
        left = n <= 3
        y = lead_y(n)
        x_body = cx - BODY_W / 2 if left else cx + BODY_W / 2
        x_tip = cx - LEAD_TIP if left else cx + LEAD_TIP
        if lifted and n == 3:
            # hochgebogen: in der Draufsicht kürzer, hängt über dem Pad
            x_tip = cx - 0.85
            ax.add_patch(Rectangle((x_tip, y - LEAD_W / 2), x_body - x_tip, LEAD_W,
                                   fc='#cfcfcf', ec=BAD, lw=1.6, zorder=7))
            continue
        x, w = (x_tip, x_body - x_tip) if left else (x_body, x_tip - x_body)
        ax.add_patch(Rectangle((x, y - LEAD_W / 2), w, LEAD_W, fc='#cfcfcf', ec='#555', lw=0.6, zorder=6))
    ax.add_patch(FancyBboxPatch((cx - BODY_W / 2, cy - BODY_H / 2), BODY_W, BODY_H,
                                boxstyle='round,pad=0,rounding_size=0.08', fc='#222', ec='#000', zorder=6))
    ax.add_patch(Circle((cx - 0.38, cy - 0.68), 0.09, fc='#bbb', zorder=7))
    ax.text(cx, cy + 0.15, 'U3\nLM66100', color='#ddd', ha='center', va='center', fontsize=8, zorder=8)


PIN_INFO = {1: ('1 VIN', 'BAT_SW'), 2: ('2 GND', 'GND'), 3: ('3 CE', 'GND'),
            6: ('6 VOUT', 'VSYS'), 5: ('5 ST', 'offen'), 4: ('4 NC', 'offen')}


def label_pins(ax, after=False):
    cx, _ = U3
    for n, (name, net) in PIN_INFO.items():
        left = n <= 3
        if after and n == 3:
            net = 'VSYS (Draht)'
        x = cx - 2.05 if left else cx + 2.05
        if n == 3:
            col = OK if after else BAD
            box = dict(boxstyle='round,pad=0.2', fc='white', ec=col, lw=1.5)
        else:
            col, box = 'white', dict(boxstyle='round,pad=0.2', fc='#000000a0', ec='none')
        ax.text(x, lead_y(n), f'{name}\n{net}', ha='right' if left else 'left', va='center',
                fontsize=8.5, color=col, fontweight='bold' if n == 3 else 'normal', zorder=9, bbox=box)


def wire(ax):
    cx, cy = U3
    a = (cx - 0.85, lead_y(3))       # Spitze des angehobenen Pin 3
    b = (cx + LEAD_TIP - 0.12, lead_y(6))  # Beinchen Pin 6
    verts = [a, (cx - 0.2, cy + 0.9), (cx + 0.4, cy - 0.9), b]
    ax.add_patch(PathPatch(Path(verts, [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4]),
                           fc='none', ec=WIRE, lw=3.2, capstyle='round', zorder=10))
    for p in (a, b):
        ax.add_patch(Circle(p, 0.11, fc='#e0e0e0', ec=WIRE, lw=1.5, zorder=11))


def side_view(ax):
    ax.set_xlim(-2.6, 2.6)
    ax.set_ylim(-0.7, 2.1)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.add_patch(Rectangle((-2.5, -0.6), 5.0, 0.6, fc=BOARD, ec=EDGE))
    for x in (-1.05, 1.05):
        ax.add_patch(Rectangle((x - 0.35, 0), 0.7, 0.05, fc=PAD, ec='#8a6418', lw=0.5))
    ax.add_patch(Rectangle((-0.625, 0.1), 1.25, 0.9, fc='#222', ec='#000'))
    # Pin 6 rechts: normal verlötet (Gull-Wing)
    ax.plot([0.625, 0.8, 0.85, 1.25], [0.55, 0.55, 0.05, 0.05], color='#999', lw=3, solid_capstyle='round')
    ax.add_patch(Polygon([(0.75, 0.05), (1.35, 0.05), (1.3, 0.16), (0.9, 0.22)], fc='#c0c0c0', ec='#888'))
    # Pin 3 links: hochgebogen
    ax.plot([-0.625, -0.8, -0.95, -1.25], [0.55, 0.55, 0.55, 0.78], color='#999', lw=3, solid_capstyle='round')
    ax.add_patch(Rectangle((-1.45, 0.06), 0.9, 0.06, fc='#e9c46a', ec='#b08a2e', lw=0.5))
    ax.text(-1.0, -0.35, 'Pad 3 (GND)\nbleibt frei', ha='center', va='center', fontsize=7.5, color='white')
    ax.text(1.05, -0.35, 'Pad 6 (VSYS)', ha='center', va='center', fontsize=7.5, color='white')
    ax.annotate('Kapton (optional)', (-1.0, 0.12), (-2.45, 0.55), fontsize=7.5,
                arrowprops=dict(arrowstyle='->', color='#555'))
    ax.annotate('Pin 3 ≈ 0,3–0,5 mm\nhochgebogen', (-1.22, 0.76), (-2.45, 1.45), fontsize=7.5,
                arrowprops=dict(arrowstyle='->', color=BAD), color=BAD)
    verts = [(-1.25, 0.78), (-1.0, 2.0), (1.0, 1.9), (1.1, 0.2)]
    ax.add_patch(PathPatch(Path(verts, [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4]),
                           fc='none', ec=WIRE, lw=2.6))
    ax.text(0, 1.98, 'Kupferlackdraht über das Gehäuse', ha='center', fontsize=7.5, color=WIRE)
    ax.set_title('Seitenansicht (Schnitt durch Pin 3 und Pin 6)', fontsize=10, loc='left')


STEPS = """\
Werkzeug: feine Lötspitze (≤ 0,5 mm), Flussmittel, spitze Pinzette oder Nadel,
Kupferlackdraht 0,1–0,2 mm, Lupe oder Mikroskop, optional Kapton-Band.

 1. Akku abziehen, USB abziehen, ESP-Modul aus den Buchsenleisten ziehen:
    U3 sitzt unter dem ESP, zwischen den beiden Leisten (zwischen R4 und C4).
 2. Platine so drehen, dass Pin 1 von U3 (Punkt) oben links liegt, wie im Bild.
 3. Flussmittel auf Pin 3 (CE, links unten).
 4. Pin 3 mit der Lötspitze erwärmen, Nadel von außen unter das Beinchen schieben
    und es ca. 0,3–0,5 mm nach oben biegen. Nur Pin 3 – Pin 2 bleibt verlötet.
    Die Bahn Pin 2 → Pin 3 nicht auftrennen: Pad 3 hängt auch an der GND-Fläche.
 5. Prüfen: Das Beinchen berührt Pad 3 nicht mehr. Optional ein Stück Kapton
    unter das Beinchen legen.
 6. Ca. 5 mm Kupferlackdraht abschneiden, beide Enden mit viel Zinn bei ~380 °C
    verzinnen (der Lack brennt ab).
 7. Ein Ende an die Spitze des angehobenen Pin 3 löten, den Draht über das
    Gehäuse führen, das andere Ende an Pin 6 (VOUT, rechts oben) löten.
    Pin 6 nicht ablöten – nur Zinn dazu.

Prüfen mit dem Multimeter (ohne Akku/USB):
 • Pin 3 ↔ TP_VSYS: ≈ 0 Ω      • Pin 3 ↔ GND: kein Kurzschluss
 • Pin 2 ↔ GND: weiterhin ≈ 0 Ω

Funktionstest:
 • Akku + USB, Schalter AUS → EIN: Ladestrom bleibt ≈ −231 mA (INA226),
   rote Lade-LED bleibt an, USB-Strom steigt nicht auf ~0,5 A.
 • Nur Akku, Schalter EIN: ESP startet."""


def main():
    edges, segs, fills, pads, refs = load()
    fig = plt.figure(figsize=(17, 12.5), dpi=110)
    fig.suptitle('Rework Powerboard Rev 0.2 – U3 (LM66100): CE von GND auf VOUT/VSYS  ·  Issue #1',
                 fontsize=15, fontweight='bold', x=0.02, ha='left', y=0.985)
    fig.text(0.02, 0.945, 'Warum: Mit CE an GND ist der LM66100 nur ein Schalter ohne Rückstromschutz. '
             'Schalter EIN + USB lädt dann den Akku ungeregelt am Lader vorbei (gemessen −550 mA statt −231 mA).\n'
             'Mit CE an VOUT sperrt er, sobald VSYS (USB) höher ist als der Akku (Datenblatt SLVSEZ8A, Abschnitt 8.3.2, Figure 13).',
             fontsize=10, va='top')

    gs = fig.add_gridspec(2, 3, left=0.02, right=0.98, top=0.89, bottom=0.03, hspace=0.12, wspace=0.06,
                          height_ratios=[1, 1.15])

    # Übersicht
    ax = fig.add_subplot(gs[0, 0])
    xs = [v for e in edges for v in (e[0], e[2])]
    ys = [v for e in edges for v in (e[1], e[3])]
    setup(ax, min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1)
    draw_copper(ax, edges, segs, fills, pads, fill_alpha=0.55)
    ax.add_patch(Polygon(esp_outline(pads), closed=True, fc='#ffffff30', ec='white', lw=2, ls='--', zorder=11))
    ax.add_patch(Rectangle((U3[0] - 3, U3[1] - 3), 6, 6, fc='none', ec=BAD, lw=2.5, zorder=12))
    ax.annotate('U3', (U3[0] - 3, U3[1] - 3), (U3[0] - 13, U3[1] - 10), color='white', fontsize=12,
                fontweight='bold', arrowprops=dict(arrowstyle='->', color='white', lw=1.5), zorder=12)
    for ref, x, y in refs:
        names = {'U4': 'ESP (U4)', 'SW1': 'Schalter', 'J1': 'Akku J1', 'TP3': 'TP_VSYS'}
        if ref == 'U4':
            x, y = np.mean(esp_outline(pads), axis=0) + (2, 2)
        if ref in names:
            ax.text(x, y, names[ref], color='white', fontsize=8, ha='center', va='center', zorder=12,
                    bbox=dict(boxstyle='round,pad=0.15', fc='#00000090', ec='none'))
    ax.set_title('Lage: unter dem ESP-Modul (vorher abziehen!)', fontsize=11, loc='left')

    # Zoom vorher / nachher
    for col, after in ((1, False), (2, True)):
        ax = fig.add_subplot(gs[0, col])
        setup(ax, U3[0] - 3.4, U3[0] + 3.4, U3[1] - 3.0, U3[1] + 3.0)
        draw_copper(ax, edges, segs, fills, pads)
        draw_u3(ax, lifted=after)
        label_pins(ax, after)
        for ref, x, y in refs:
            if ref != 'U3' and abs(x - U3[0]) < 3.4 and abs(y - U3[1]) < 3.0:
                ax.text(x, y, ref, color='black', fontsize=8, ha='center', va='center', zorder=9,
                        bbox=dict(boxstyle='round,pad=0.15', fc='#ffffffc0', ec='none'))
        if after:
            wire(ax)
            ax.set_title('Nachher: Pin 3 angehoben, Draht an Pin 6', fontsize=11, loc='left', color=OK)
        else:
            ax.annotate('Pin 3 (CE) liegt auf GND\n(Bahn zu Pin 2 + GND-Fläche)', (U3[0] - 0.9, lead_y(3)),
                        (U3[0] - 3.2, U3[1] + 2.45), fontsize=8.5, color=BAD, zorder=12,
                        bbox=dict(boxstyle='round,pad=0.25', fc='white', ec=BAD),
                        arrowprops=dict(arrowstyle='->', color=BAD, lw=1.5))
            ax.set_title('Vorher: so ist die Platine bestückt', fontsize=11, loc='left', color=BAD)

    ax = fig.add_subplot(gs[1, 0])
    side_view(ax)

    ax = fig.add_subplot(gs[1, 1:])
    ax.axis('off')
    ax.text(0.0, 1.0, 'Anleitung', fontsize=13, fontweight='bold', va='top', transform=ax.transAxes)
    ax.text(0.0, 0.94, STEPS, fontsize=10, va='top', family='DejaVu Sans', transform=ax.transAxes,
            linespacing=1.35)

    fig.savefig(OUT, facecolor='white')
    print(OUT)


if __name__ == '__main__':
    main()
