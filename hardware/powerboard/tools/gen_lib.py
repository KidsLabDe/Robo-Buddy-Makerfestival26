#!/usr/bin/env python3
"""Generate the project symbol library and the ESP32-C6-Zero socket footprint.

    python3 hardware/powerboard/tools/gen_lib.py
"""
import os
import uuid

from sexp import Sym, dump

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
NS = uuid.UUID('0b8e1a52-3f7c-4a0e-8f43-2f6f1c26b0a2')


def uid(*key):
    return str(uuid.uuid5(NS, '/'.join(map(str, key))))


def font(size=1.27):
    return [Sym('effects'), [Sym('font'), [Sym('size'), size, size]]]


def sprop(name, value, at, hide=False):
    e = font()
    if hide:
        e.append([Sym('hide'), Sym('yes')])
    return [Sym('property'), name, value, [Sym('at'), at[0], at[1], 0], e]


def pin(kind, num, name, x, y, ang):
    return [Sym('pin'), Sym(kind), Sym('line'), [Sym('at'), x, y, ang], [Sym('length'), 2.54],
            [Sym('name'), name, font()], [Sym('number'), num, font()]]


def rect(x1, y1, x2, y2):
    return [Sym('rectangle'), [Sym('start'), x1, y1], [Sym('end'), x2, y2],
            [Sym('stroke'), [Sym('width'), 0.254], [Sym('type'), Sym('default')]],
            [Sym('fill'), [Sym('type'), Sym('background')]]]


def symbol(name, ref, fp, datasheet, desc, box, pins):
    return [Sym('symbol'), name,
            [Sym('exclude_from_sim'), Sym('no')], [Sym('in_bom'), Sym('yes')], [Sym('on_board'), Sym('yes')],
            sprop('Reference', ref, (0, box[1] + 2.54)),
            sprop('Value', name, (0, box[3] - 2.54)),
            sprop('Footprint', fp, (0, 0), hide=True),
            sprop('Datasheet', datasheet, (0, 0), hide=True),
            sprop('Description', desc, (0, 0), hide=True),
            [Sym('symbol'), f'{name}_0_1', rect(*box)],
            [Sym('symbol'), f'{name}_1_1'] + pins]


def fs8205a():
    pins = [
        pin('passive', '6', 'G1', -7.62, 2.54, 0),
        pin('passive', '4', 'G2', -7.62, -2.54, 0),
        pin('passive', '1', 'S1', -2.54, -7.62, 90),
        pin('passive', '3', 'S2', 2.54, -7.62, 90),
        pin('passive', '2', 'D', -2.54, 7.62, 270),
        pin('passive', '5', 'D', 2.54, 7.62, 270),
    ]
    return symbol('FS8205A', 'Q', 'Package_TO_SOT_SMD:SOT-23-6', 'https://www.lcsc.com/datasheet/C908265.pdf',
                  'Dual N-MOSFET 20V 6A, gemeinsamer Drain (Fuxinsemi). Pinout laut Datenblatt: '
                  '1 S1, 2 D, 3 S2, 4 G2, 5 D, 6 G1',
                  (-5.08, 5.08, 5.08, -5.08), pins)


def tps61023():
    pins = [
        pin('power_in', '3', 'VIN', -10.16, 2.54, 0),
        pin('input', '2', 'EN', -10.16, -2.54, 0),
        pin('passive', '5', 'SW', 10.16, 2.54, 180),
        pin('power_out', '6', 'VOUT', 10.16, 0, 180),
        pin('input', '1', 'FB', 10.16, -2.54, 180),
        pin('power_in', '4', 'GND', 0, -7.62, 90),
    ]
    return symbol('TPS61023', 'U', 'Package_TO_SOT_SMD:SOT-563', 'https://www.ti.com/lit/gpn/tps61023',
                  'Synchroner Boost 3,7 A Valley-Limit, echte Trennung VIN/VOUT bei EN low (TI). '
                  'Pinout laut Datenblatt: 1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 VOUT',
                  (-7.62, 5.08, 7.62, -5.08), pins)


LEFT = ['5V','GND', '3V3', 'GPIO0', 'GPIO1', 'GPIO2', 'GPIO3', 'GPIO4', 'GPIO5']
RIGHT = ['TX/GPIO16', 'RX/GPIO17', 'GPIO14', 'GPIO15', 'GPIO18', 'GPIO19', 'GPIO20', 'GPIO21', 'GPIO22']
KIND = {'5V': 'power_in', 'GND': 'power_in', '3V3': 'power_out'}


def esp():
    pins = []
    for i, n in enumerate(LEFT):
        pins.append(pin(KIND.get(n, 'bidirectional'), str(i + 1), n, -15.24, 10.16 - i * 2.54, 0))
    for i, n in enumerate(RIGHT):
        pins.append(pin('bidirectional', str(i + 10), n, 15.24, 10.16 - i * 2.54, 180))
    return symbol('ESP32-C6-Zero', 'U', 'powerboard:Waveshare_ESP32-C6-Zero_Socket',
                  'https://www.waveshare.com/wiki/ESP32-C6-Zero',
                  'Waveshare ESP32-C6-Zero auf 2x Buchsenleiste 1x9. Pins 1-9 links, 10-18 rechts, '
                  'jeweils von USB-C aus gezaehlt. Pads auf der Unterseite nicht genutzt.',
                  (-12.7, 12.7, 12.7, -12.7), pins)


def write_symbols():
    libtree = [Sym('kicad_symbol_lib'), [Sym('version'), 20231120], [Sym('generator'), 'gen_lib.py'],
               [Sym('generator_version'), '1'], fs8205a(), tps61023(), esp()]
    with open(os.path.join(PROJ, 'powerboard.kicad_sym'), 'w', encoding='utf-8') as f:
        f.write(dump(libtree) + '\n')


# --------------------------------------------------------------- footprint --
ROW = 15.24   # pin row spacing (6 x 2.54), laut Waveshare-DXF
PITCH = 2.54
BOARD_W, BOARD_H = 18.0, 23.5
FIRST = 1.59  # Oberkante bis Mitte Pin 1


def line(layer, x1, y1, x2, y2, w):
    return [Sym('fp_line'), [Sym('start'), x1, y1], [Sym('end'), x2, y2],
            [Sym('stroke'), [Sym('width'), w], [Sym('type'), Sym('solid')]], [Sym('layer'), layer],
            [Sym('uuid'), uid('line', layer, x1, y1, x2, y2)]]


def box(layer, x1, y1, x2, y2, w):
    return [line(layer, x1, y1, x2, y1, w), line(layer, x2, y1, x2, y2, w),
            line(layer, x2, y2, x1, y2, w), line(layer, x1, y2, x1, y1, w)]


def fptext(kind, text, x, y, layer, hide=False):
    e = [Sym('effects'), [Sym('font'), [Sym('size'), 1, 1], [Sym('thickness'), 0.15]]]
    node = [Sym('property'), kind, text, [Sym('at'), x, y, 0], [Sym('layer'), layer],
            [Sym('uuid'), uid('prop', kind)]]
    if hide:
        node.append([Sym('hide'), Sym('yes')])
    node.append(e)
    return node


def write_footprint():
    top = -BOARD_H / 2
    y0 = top + FIRST
    xl, xr = -ROW / 2, ROW / 2
    items = [Sym('footprint'), 'Waveshare_ESP32-C6-Zero_Socket',
             [Sym('version'), 20240108], [Sym('generator'), 'gen_lib.py'], [Sym('generator_version'), '1'],
             [Sym('layer'), 'F.Cu'],
             [Sym('descr'), 'Waveshare ESP32-C6-Zero auf 2x Buchsenleiste 1x9 P2.54, Reihenabstand '
                            f'{ROW} mm laut Waveshare-DXF. USB-C oben (-Y).'],
             [Sym('tags'), 'ESP32-C6 Waveshare Zero socket'],
             fptext('Reference', 'REF**', 0, top - 3, 'F.SilkS'),
             fptext('Value', 'ESP32-C6-Zero', 0, 0, 'F.Fab'),
             [Sym('attr'), Sym('through_hole')]]
    # module outline + USB-C plug on Fab, header outline on silk
    items += box('F.Fab', -BOARD_W / 2, top, BOARD_W / 2, -top, 0.1)
    items += box('F.Fab', -4.5, top - 1.5, 4.5, top + 6.0, 0.1)
    items.append([Sym('fp_text'), Sym('user'), 'USB-C', [Sym('at'), 0, top + 2, 0], [Sym('layer'), 'F.Fab'],
                  [Sym('uuid'), uid('t', 'usb')],
                  [Sym('effects'), [Sym('font'), [Sym('size'), 1, 1], [Sym('thickness'), 0.15]]]])
    items.append([Sym('fp_text'), Sym('user'), 'ANTENNE', [Sym('at'), 0, -top - 1.5, 0], [Sym('layer'), 'F.Fab'],
                  [Sym('uuid'), uid('t', 'ant')],
                  [Sym('effects'), [Sym('font'), [Sym('size'), 1, 1], [Sym('thickness'), 0.15]]]])
    for x in (xl, xr):
        items += box('F.SilkS', x - 1.4, y0 - 1.4, x + 1.4, y0 + 8 * PITCH + 1.4, 0.12)
    items += box('F.CrtYd', -BOARD_W / 2 - 0.5, top - 2.0, BOARD_W / 2 + 0.5, -top + 0.5, 0.05)
    # pin 1 marker
    items.append(line('F.SilkS', xl - 1.9, y0 - 1.0, xl - 1.9, y0 + 1.0, 0.12))
    for i in range(18):
        x = xl if i < 9 else xr
        y = y0 + (i % 9) * PITCH
        shape = Sym('circle')   # round even for pin 1: the board places this part at 126.5 deg, and
        # Freerouting only gets into non-round pads at multiples of 45 deg. Pin 1 is marked on silk.
        items.append([Sym('pad'), str(i + 1), Sym('thru_hole'), shape, [Sym('at'), round(x, 3), round(y, 3)],
                      [Sym('size'), 1.7, 1.7], [Sym('drill'), 1.0], [Sym('layers'), '*.Cu', '*.Mask'],
                      [Sym('remove_unused_layers'), Sym('no')], [Sym('uuid'), uid('pad', i)]])
    # no copper under the chip antenna (end opposite USB-C)
    ay1, ay2 = -top - 3.5, -top + 1.0
    ax = ROW / 2 - 1.2              # between the pin rows, clear of the pads
    items.append([Sym('zone'), [Sym('net'), 0], [Sym('net_name'), ''], [Sym('layers'), 'F.Cu', 'B.Cu'],
                  [Sym('uuid'), uid('zone', 'antenna')], [Sym('name'), 'Antenne'],
                  [Sym('hatch'), Sym('edge'), 0.5], [Sym('connect_pads'), [Sym('clearance'), 0]],
                  [Sym('min_thickness'), 0.25],
                  [Sym('keepout'), [Sym('tracks'), Sym('not_allowed')], [Sym('vias'), Sym('not_allowed')],
                   [Sym('pads'), Sym('not_allowed')], [Sym('copperpour'), Sym('not_allowed')],
                   [Sym('footprints'), Sym('allowed')]],
                  [Sym('fill'), [Sym('thermal_gap'), 0.5], [Sym('thermal_bridge_width'), 0.5]],
                  [Sym('polygon'), [Sym('pts'), [Sym('xy'), -ax, ay1], [Sym('xy'), ax, ay1],
                                    [Sym('xy'), ax, ay2], [Sym('xy'), -ax, ay2]]]])
    # 3D: the two sockets (no model of the module itself exists)
    for x in (xl, xr):
        items.append([Sym('model'), '${KICAD10_3DMODEL_DIR}/Connector_PinSocket_2.54mm.3dshapes/'
                                    'PinSocket_1x09_P2.54mm_Vertical.step',
                      [Sym('offset'), [Sym('xyz'), round(x, 3), round(-y0, 3), 0]],
                      [Sym('scale'), [Sym('xyz'), 1, 1, 1]], [Sym('rotate'), [Sym('xyz'), 0, 0, 0]]])
    d = os.path.join(PROJ, 'powerboard.pretty')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'Waveshare_ESP32-C6-Zero_Socket.kicad_mod'), 'w', encoding='utf-8') as f:
        f.write(dump(items) + '\n')


def write_kelvin():
    """1206 shunt with Kelvin sense pads (net tie 1-2 and 3-4).

    Force pads 1 and 4 are the normal 1206 pads. The sense pads 2 and 3 sit
    beside the inner corners, 0.175 mm away, joined to their force pad by a
    copper bridge inside the footprint (allowed by the net tie). Their traces
    leave sideways without touching the force copper, and the autorouter sees
    two separate pads. Matches the pin numbers of the Device:R_Shunt symbol."""
    name = 'R_1206_3216Metric_Kelvin'
    items = [Sym('footprint'), name,
             [Sym('version'), 20240108], [Sym('generator'), 'gen_lib.py'], [Sym('generator_version'), '1'],
             [Sym('layer'), 'F.Cu'],
             [Sym('descr'), '1206 Shunt mit Kelvin-Messpads, Pads 1/4 Strom, 2/3 Messung'],
             [Sym('tags'), 'resistor shunt kelvin 1206'],
             fptext('Reference', 'REF**', 0, -2.2, 'F.SilkS'),
             fptext('Value', name, 0, 2.2, 'F.Fab'),
             [Sym('attr'), Sym('smd')],
             [Sym('net_tie_pad_groups'), '1, 2', '3, 4']]
    items += box('F.Fab', -1.6, -0.8, 1.6, 0.8, 0.1)
    items += box('F.CrtYd', -2.3, -1.7, 2.3, 1.7, 0.05)
    items.append(line('F.SilkS', -0.5, -1.0, 0.5, -1.0, 0.12))
    items.append(line('F.SilkS', -0.5, 1.0, 0.5, 1.0, 0.12))
    for num, x in (('1', -1.4625), ('4', 1.4625)):
        items.append([Sym('pad'), num, Sym('smd'), Sym('roundrect'), [Sym('at'), x, 0], [Sym('size'), 1.125, 1.75],
                      [Sym('layers'), 'F.Cu', 'F.Paste', 'F.Mask'], [Sym('roundrect_rratio'), 0.222222],
                      [Sym('uuid'), uid('kpad', num)]])
    for num, x, y in (('2', -1.2, -1.25), ('3', 1.2, 1.25)):
        items.append([Sym('pad'), num, Sym('smd'), Sym('rect'), [Sym('at'), x, y], [Sym('size'), 0.4, 0.4],
                      [Sym('layers'), 'F.Cu'], [Sym('uuid'), uid('kpad', num)]])
        items.append(line('F.Cu', x, y * 0.7, x, y, 0.3))
    items.append([Sym('model'), '${KICAD10_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_1206_3216Metric.step',
                  [Sym('offset'), [Sym('xyz'), 0, 0, 0]], [Sym('scale'), [Sym('xyz'), 1, 1, 1]],
                  [Sym('rotate'), [Sym('xyz'), 0, 0, 0]]])
    with open(os.path.join(PROJ, 'powerboard.pretty', f'{name}.kicad_mod'), 'w', encoding='utf-8') as f:
        f.write(dump(items) + '\n')


SWITCH = 'SW_Slide_SPDT_Angled_CK_OS102011MA1Q'


def write_switch():
    """KiCad's CK OS102011MA1Q with round solder pads 1-3 (same holes). The
    switch sits at 53.5 deg along the slanted wall; Freerouting cannot
    connect to oval or square pads at such angles."""
    from sexp import find, find1, parse
    src = f'/usr/share/kicad/footprints/Button_Switch_THT.pretty/{SWITCH}.kicad_mod'
    tree = parse(open(src, encoding='utf-8').read())
    tree[1] = SWITCH + '_Round'
    for pad in find(tree, 'pad'):
        if pad[1] in ('1', '2', '3'):
            pad[3] = Sym('circle')
            size = find1(pad, 'size')
            size[1:] = [1.6, 1.6]
    with open(os.path.join(PROJ, 'powerboard.pretty', f'{SWITCH}_Round.kicad_mod'), 'w', encoding='utf-8') as f:
        f.write(dump(tree) + '\n')


LOGO_SVG = os.path.join(PROJ, 'logo', 'kidslab-logo.svg')
LOGO_W = 20.0   # mm


def write_logo():
    """KidsLab logo as silkscreen polygons.

    The coloured areas of the logo become silkscreen, its black outlines stay
    open. SVG -> bitmap (rsvg-convert) -> polygons (potrace), the holes are
    then joined into single outlines by KiCad's own fracture."""
    import json
    import subprocess
    import tempfile

    import numpy as np
    import pcbnew
    from PIL import Image

    px = 2600
    with tempfile.TemporaryDirectory() as d:
        png, pbm, geo = (os.path.join(d, n) for n in ('l.png', 'l.pbm', 'l.geojson'))
        subprocess.run(['rsvg-convert', '-w', str(px), LOGO_SVG, '-o', png], check=True)
        im = np.array(Image.open(png).convert('RGBA')).astype(float)
        lum = 0.299 * im[..., 0] + 0.587 * im[..., 1] + 0.114 * im[..., 2]
        silk = (im[..., 3] > 128) & (lum > 90)   # coloured or white, not the black lines
        Image.fromarray(np.where(silk, 0, 255).astype(np.uint8)).convert('1').save(pbm)
        subprocess.run(['potrace', '-b', 'geojson', '-t', '15', '-O', '0.4', '-o', geo, pbm], check=True)
        features = json.load(open(geo))['features']
    h_px = im.shape[0]
    scale = LOGO_W / px
    nm = pcbnew.FromMM

    def pt(x, y):   # potrace: y up from the bottom; footprint: y down, centred
        return nm((x - px / 2) * scale), nm((h_px / 2 - y) * scale)

    polys = pcbnew.SHAPE_POLY_SET()
    for f in features:
        rings = f['geometry']['coordinates']
        polys.NewOutline()
        for i, ring in enumerate(rings):
            if i:
                polys.NewHole()
            for x, y in ring[:-1]:   # Append() adds to the newest outline or hole
                polys.Append(*pt(x, y))
    polys.Simplify()
    polys.Fracture()

    name = 'KidsLab_Logo'
    items = [Sym('footprint'), name,
             [Sym('version'), 20240108], [Sym('generator'), 'gen_lib.py'], [Sym('generator_version'), '1'],
             [Sym('layer'), 'F.Cu'],
             [Sym('descr'), f'KidsLab-Logo, Bestueckungsdruck, {LOGO_W:g} mm breit'],
             fptext('Reference', 'REF**', 0, 0, 'F.Fab', hide=True),
             fptext('Value', name, 0, 0, 'F.Fab', hide=True),
             [Sym('attr'), Sym('board_only'), Sym('exclude_from_pos_files'), Sym('exclude_from_bom')]]
    for i in range(polys.OutlineCount()):
        o = polys.Outline(i)
        pts = [[Sym('xy'), round(pcbnew.ToMM(o.CPoint(j).x), 4), round(pcbnew.ToMM(o.CPoint(j).y), 4)]
               for j in range(o.PointCount())]
        items.append([Sym('fp_poly'), [Sym('pts')] + pts,
                      [Sym('stroke'), [Sym('width'), 0], [Sym('type'), Sym('solid')]], [Sym('fill'), Sym('yes')],
                      [Sym('layer'), 'F.SilkS'], [Sym('uuid'), uid('logo', i)]])
    with open(os.path.join(PROJ, 'powerboard.pretty', f'{name}.kicad_mod'), 'w', encoding='utf-8') as f:
        f.write(dump(items) + '\n')


if __name__ == '__main__':
    write_symbols()
    write_footprint()
    write_kelvin()
    write_logo()
    write_switch()
