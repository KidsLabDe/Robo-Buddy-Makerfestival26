#!/usr/bin/env python3
"""Render the 2D and 3D views in ansichten/.

    python3 hardware/powerboard/tools/render_views.py
"""
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
PCB = os.path.join(PROJ, 'powerboard.kicad_pcb')
OUT = os.path.join(PROJ, 'ansichten')

SVG = {   # name: layers, mirrored
    '2d_oben': ('F.Cu,F.SilkS,F.Mask,Edge.Cuts', False),
    '2d_unten': ('B.Cu,B.SilkS,B.Mask,Edge.Cuts', True),
}
RENDER = {
    '3d_oben': ['--side', 'top'],
    '3d_unten': ['--side', 'bottom'],
    '3d_schraeg': ['--rotate', '-45,0,-30', '--zoom', '0.8'],
}


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    with tempfile.TemporaryDirectory() as d:
        for name, (layers, mirror) in SVG.items():
            svg = os.path.join(d, name + '.svg')
            run(['kicad-cli', 'pcb', 'export', 'svg', '--layers', layers, '--mode-single', '--fit-page-to-board',
                 *(['--mirror'] if mirror else []), '-o', svg, PCB])
            run(['rsvg-convert', '-h', '1067', '-b', 'white', svg, '-o', os.path.join(OUT, name + '.png')])
            print(name)
    for name, args in RENDER.items():
        run(['kicad-cli', 'pcb', 'render', *args, '--quality', 'high', '-w', '1568', '-h', '1064',
             '-o', os.path.join(OUT, name + '.png'), PCB])
        print(name)


if __name__ == '__main__':
    main()
