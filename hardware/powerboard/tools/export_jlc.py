#!/usr/bin/env python3
"""Write the files for a JLCPCB order (PCB + SMD assembly) to fertigung/.

    python3 hardware/powerboard/tools/export_jlc.py

- powerboard_gerber.zip   Gerber + drill files, upload as "Gerber file"
- powerboard_bom.csv      Comment, Designator, Footprint, LCSC
- powerboard_cpl.csv      Designator, Mid X, Mid Y, Layer, Rotation

Only parts with an LCSC number end up in BOM and CPL. The THT kit parts
(field Kit = THT-Kit) are soldered in the workshop and stay out.

JLC's part models are not always oriented like KiCad's footprints. The
rotation in the CPL is corrected per LCSC part (JLC_ROTATION), checked in
JLC's placement viewer on 8 Oct 2026: pin 1 of every part on the footprint's
pin-1 mark. The correction depends on the part, not only on the footprint
(both FS8205A and DW01A are SOT-23-6, but need 180 and 270 degrees). Check
new parts in the viewer and add them here.
"""
import csv
import os
import subprocess
import sys
import tempfile
import zipfile

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import PCB, PROJ  # noqa: E402  (also patches KiCad's iterators for Python 3.14)

OUT = os.path.join(PROJ, 'fertigung')

# Degrees added to KiCad's orientation (counter-clockwise, like the CPL);
# 270 = 90 degrees clockwise.
JLC_ROTATION = {
    'C15127': 180,    # AO3401A, SOT-23
    'C908265': 180,   # FS8205A, SOT-23-6
    'C919459': 180,   # TPS61023, SOT-563
    'C2927799': 270,  # DW01A, SOT-23-6
    'C2869734': 270,  # LM66100, SC-70-6
    'C16581': 270,    # TP4056, ESOP-8
    'C49851': 270,    # INA226, VSSOP-10
}
LAYERS = 'F.Cu,B.Cu,F.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'


def field(fp, name):
    return str(fp.GetFieldText(name)) if fp.HasField(name) else ''


def gerbers():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['kicad-cli', 'pcb', 'export', 'gerbers', '-l', LAYERS, '--check-zones',
                        '--subtract-soldermask', '-o', d + '/', PCB], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm',
                        '--excellon-separate-th', '-o', d + '/', PCB], check=True, stdout=subprocess.DEVNULL)
        path = os.path.join(OUT, 'powerboard_gerber.zip')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            for name in sorted(os.listdir(d)):
                z.write(os.path.join(d, name), name)
                print('  ', name)
    return path


def assembly(board):
    parts = []
    for fp in board.GetFootprints():
        lcsc = field(fp, 'LCSC')
        if not lcsc or field(fp, 'Kit'):
            continue
        parts.append(fp)
    groups = {}
    for fp in parts:
        key = (str(fp.GetValue()), str(fp.GetFPID().GetLibItemName()), field(fp, 'LCSC'))
        groups.setdefault(key, []).append(str(fp.GetReference()))
    bom = os.path.join(OUT, 'powerboard_bom.csv')
    with open(bom, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC'])
        def order(ref):     # C2 before C10
            return ref.rstrip('0123456789'), int(ref.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ') or 0)
        rows = [(sorted(refs, key=order), key) for key, refs in groups.items()]
        for refs, (value, footprint, lcsc) in sorted(rows, key=lambda r: order(r[0][0])):
            w.writerow([value, ','.join(refs), footprint, lcsc])
    cpl = os.path.join(OUT, 'powerboard_cpl.csv')
    with open(cpl, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for fp in sorted(parts, key=lambda p: str(p.GetReference())):
            p = fp.GetPosition()
            rot = (fp.GetOrientationDegrees() + JLC_ROTATION.get(field(fp, 'LCSC'), 0)) % 360
            w.writerow([str(fp.GetReference()), f'{pcbnew.ToMM(p.x):.3f}mm', f'{-pcbnew.ToMM(p.y):.3f}mm',
                        'Top' if fp.GetLayer() == pcbnew.F_Cu else 'Bottom', f'{rot:.1f}'])
    return bom, cpl, len(parts), len(groups)


def main():
    os.makedirs(OUT, exist_ok=True)
    board = pcbnew.LoadBoard(PCB)
    print('Gerber:')
    gerbers()
    bom, cpl, n, types = assembly(board)
    print(f'BOM: {types} Bauteiltypen, {n} Teile -> {bom}')
    print(f'CPL: {n} Teile -> {cpl}')


if __name__ == '__main__':
    main()
