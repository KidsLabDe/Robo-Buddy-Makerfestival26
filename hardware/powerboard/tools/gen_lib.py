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


LEFT = ['5V', 'GND', '3V3', 'GPIO0', 'GPIO1', 'GPIO2', 'GPIO3', 'GPIO4', 'GPIO5']
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
               [Sym('generator_version'), '1'], fs8205a(), esp()]
    with open(os.path.join(PROJ, 'powerboard.kicad_sym'), 'w', encoding='utf-8') as f:
        f.write(dump(libtree) + '\n')


# --------------------------------------------------------------- footprint --
ROW = 17.78   # pin row spacing - nach Waveshare-Zeichnung, am Board nachmessen!
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
                            f'{ROW} mm (vorlaeufig, am Board nachmessen). USB-C oben (-Y).'],
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
        shape = Sym('rect') if i == 0 else Sym('circle')
        items.append([Sym('pad'), str(i + 1), Sym('thru_hole'), shape, [Sym('at'), round(x, 3), round(y, 3)],
                      [Sym('size'), 1.7, 1.7], [Sym('drill'), 1.0], [Sym('layers'), '*.Cu', '*.Mask'],
                      [Sym('remove_unused_layers'), Sym('no')], [Sym('uuid'), uid('pad', i)]])
    # no copper under the chip antenna (end opposite USB-C)
    ay1, ay2 = -top - 3.5, -top + 1.0
    items.append([Sym('zone'), [Sym('net'), 0], [Sym('net_name'), ''], [Sym('layers'), 'F.Cu', 'B.Cu'],
                  [Sym('uuid'), uid('zone', 'antenna')], [Sym('name'), 'Antenne'],
                  [Sym('hatch'), Sym('edge'), 0.5], [Sym('connect_pads'), [Sym('clearance'), 0]],
                  [Sym('min_thickness'), 0.25],
                  [Sym('keepout'), [Sym('tracks'), Sym('not_allowed')], [Sym('vias'), Sym('not_allowed')],
                   [Sym('pads'), Sym('not_allowed')], [Sym('copperpour'), Sym('not_allowed')],
                   [Sym('footprints'), Sym('allowed')]],
                  [Sym('fill'), [Sym('thermal_gap'), 0.5], [Sym('thermal_bridge_width'), 0.5]],
                  [Sym('polygon'), [Sym('pts'), [Sym('xy'), -7.4, ay1], [Sym('xy'), 7.4, ay1],
                                    [Sym('xy'), 7.4, ay2], [Sym('xy'), -7.4, ay2]]]])
    d = os.path.join(PROJ, 'powerboard.pretty')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'Waveshare_ESP32-C6-Zero_Socket.kicad_mod'), 'w', encoding='utf-8') as f:
        f.write(dump(items) + '\n')


if __name__ == '__main__':
    write_symbols()
    write_footprint()
