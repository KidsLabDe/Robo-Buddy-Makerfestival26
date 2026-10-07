#!/usr/bin/env python3
"""Generate powerboard.kicad_sch from the part list below.

Every pin is tied to its net with a local label sitting on the pin end, so
the netlist is defined entirely by the PARTS table. Rerun after editing:

    python3 hardware/powerboard/tools/gen_sch.py
"""
import os
import uuid

from sexp import Sym, dump, find, find1, parse

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
KICAD_SYMS = '/usr/share/kicad/symbols'
PROJECT = 'powerboard'
NS = uuid.UUID('6f1c1d1e-6b8e-4d4a-9a55-6d6e1f26b0a1')


def uid(*key):
    return str(uuid.uuid5(NS, '/'.join(map(str, key))))


ROOT = uid('root')

# ------------------------------------------------------------------- parts --
R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
SOT23 = 'Package_TO_SOT_SMD:SOT-23'

# ref, lib_id, value, footprint, lcsc, {pin: net}, position (mm), options
# nets named None get a no-connect flag.
PARTS = []


def part(ref, lib, value, fp, lcsc, pins, at, rot=0, kit=False, bom=True, desc='', ty=6.35):
    PARTS.append(dict(ref=ref, lib=lib, value=value, fp=fp, lcsc=lcsc, pins=pins,
                      at=at, rot=rot, kit=kit, bom=bom, desc=desc, ty=ty))


def R(ref, value, a, b, at, lcsc='', desc=''):
    part(ref, 'Device:R_Small', value, R0603, lcsc, {'1': a, '2': b}, at, desc=desc)


def C(ref, value, a, b, at, fp=C0603, lcsc='', desc=''):
    part(ref, 'Device:C_Small', value, fp, lcsc, {'1': a, '2': b}, at, desc=desc)


G = 2.54


def p(x, y):
    # 4/2 grid units keep the leftmost labels clear of the sheet frame
    return (round((x + 4) * G, 2), round((y + 2) * G, 2))


# --- Battery connector, reverse polarity protection ----------------------
part('J1', 'Connector:Conn_01x02_Pin', 'BAT JST-PH 2P', 'Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal',
     '', {'1': 'J_BATP', '2': 'BATN'}, p(10, 15), desc='Akku, SMD (von JLC bestückt). Pin 1 = +')
part('Q1', 'Transistor_FET:AO3401A', 'AO3401A', SOT23, 'C15127',
     {'1': 'Q1_G', '2': 'BAT+', '3': 'J_BATP'}, p(22, 15), desc='Verpolschutz')
R('R1', '10k', 'Q1_G', 'BATN', p(16, 21), 'C25804', 'Gate Verpolschutz')

# --- Protection: DW01A + FS8205A ----------------------------------------
part('U2', 'Battery_Management:DW01A', 'DW01A', 'Package_TO_SOT_SMD:SOT-23-6', 'C2927799',
     {'1': 'DW_OD', '2': 'DW_CS', '3': 'DW_OC', '4': None, '5': 'DW_VDD', '6': 'BATN'}, p(14, 36), ty=8.89)
R('R2', '100', 'BAT+', 'DW_VDD', p(4, 32), desc='DW01 VDD-Filter')
C('C1', '100n', 'DW_VDD', 'BATN', p(4, 40), lcsc='C14663')
R('R3', '1k', 'DW_CS', 'GND', p(24, 38), 'C21190', 'DW01 CS')
part('Q2', 'powerboard:FS8205A', 'FS8205A', 'Package_TO_SOT_SMD:SOT-23-6', 'C908265',
     {'1': 'BATN', '2': 'FET_D', '3': 'GND', '4': 'DW_OC', '5': 'FET_D', '6': 'DW_OD'}, p(14, 50),
     desc='S1 = Zellminus, S2 = GND (PACK-)', ty=10.16)

# --- Charger -------------------------------------------------------------
part('U1', 'Battery_Management:LTC4054ES5-4.2', 'TP4054', 'Package_TO_SOT_SMD:SOT-23-5', 'C668215',
     {'1': 'CHRG_N', '2': 'GND', '3': 'BAT+', '4': 'VSYS', '5': 'PROG'}, p(48, 18),
     desc='UMW TP4054, Pinbelegung wie LTC4054', ty=12.7)
R('R4', '5.1k', 'PROG', 'GND', p(40, 24), desc='Ladestrom ~200 mA')
C('C2', '4.7u', 'VSYS', 'GND', p(56, 10), fp=C0805, lcsc='C1779')
C('C3', '4.7u', 'BAT+', 'GND', p(60, 22), fp=C0805, lcsc='C1779')
R('R5', '1k', '3V3', 'LED_A', p(34, 8), 'C21190')
part('D1', 'Device:LED_Small', 'rot', 'LED_SMD:LED_0603_1608Metric', 'C2286',
     {'1': 'CHRG_N', '2': 'LED_A'}, p(34, 14), rot=90, desc='Lade-LED')
R('R6', '10k', 'CHRG_N', 'CHRG_IO', p(30, 18), 'C25804', 'CHRG -> GPIO1')

# --- On/off + power path -------------------------------------------------
part('Q5', 'Transistor_FET:AO3401A', 'AO3401A', SOT23, 'C15127',
     {'1': 'SW_GATE', '2': 'BAT+', '3': 'BAT_SW'}, p(46, 40), desc='Ein/Aus')
R('R7', '1M', 'SW_GATE', 'BAT+', p(40, 34), desc='Q5 aus, solange SW1 offen')
part('SW1', 'Switch:SW_SPDT', 'EIN/AUS', 'Button_Switch_THT:SW_Slide_SPDT_Angled_CK_OS102011MA1Q', '',
     {'1': 'GND', '2': 'SW_GATE', '3': None}, p(36, 44), kit=True, desc='Schiebeschalter, Bauform offen')
part('U3', 'Power_Management:LM66100DCK', 'LM66100', 'Package_TO_SOT_SMD:SOT-363_SC-70-6', 'C2869734',
     {'1': 'BAT_SW', '2': 'GND', '3': 'GND', '4': None, '5': None, '6': 'VSYS'}, p(58, 40),
     desc='Ideale Diode, CE fest an', ty=8.89)
C('C4', '100n', 'BAT_SW', 'GND', p(52, 48), lcsc='C14663')
C('C5', '10u', 'VSYS', 'GND', p(66, 46), fp=C0805, lcsc='C15850')
C('C6', '100n', 'VSYS', 'GND', p(70, 46), lcsc='C14663')

# --- Servo rail ----------------------------------------------------------
part('Q3', 'Transistor_FET:AO3401A', 'AO3401A', SOT23, 'C15127',
     {'1': 'SERVO_G', '2': 'BAT+', '3': 'VSERVO'}, p(22, 66), desc='Servo-Schiene')
R('R8', '100k', 'SERVO_G', 'BAT+', p(12, 62), 'C25803', 'Servos aus per Default')
C('C7', '47n', 'SERVO_G', 'BAT+', p(16, 62), desc='Soft-Start, am Prototyp abgleichen')
R('R9', '10k', 'SERVO_G', 'Q4_D', p(12, 70), 'C25804')
part('Q4', 'Transistor_FET:2N7002', '2N7002', SOT23, 'C8545',
     {'1': 'SERVO_EN', '2': 'GND', '3': 'Q4_D'}, p(12, 80))
R('R10', '100k', 'SERVO_EN', 'GND', p(4, 84), 'C25803', 'Servos aus beim Booten')
part('C8', 'Device:C_Polarized_Small', '470u 10V', 'Capacitor_SMD:CP_Elec_6.3x7.7', '',
     {'1': 'VSERVO', '2': 'GND'}, p(30, 72), desc='SMD-Elko, von JLC bestückt')
part('J2', 'Connector:Conn_01x03_Pin', 'SERVO L', 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical', '',
     {'1': 'SERVO_L_S', '2': 'VSERVO', '3': 'GND'}, p(38, 64), kit=True, desc='S + -')
part('J3', 'Connector:Conn_01x03_Pin', 'SERVO R', 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical', '',
     {'1': 'SERVO_R_S', '2': 'VSERVO', '3': 'GND'}, p(38, 76), kit=True, desc='S + -')
R('R13', '220', 'SERVO_L', 'SERVO_L_S', p(46, 64))
R('R14', '220', 'SERVO_R', 'SERVO_R_S', p(46, 76))

# --- Battery sense -------------------------------------------------------
R('R11', '470k', 'BAT+', 'VBAT_SENSE', p(60, 62))
R('R12', '470k', 'VBAT_SENSE', 'GND', p(60, 70))
C('C9', '100n', 'VBAT_SENSE', 'GND', p(66, 70), lcsc='C14663')

# --- ESP32-C6-Zero -------------------------------------------------------
part('U4', 'powerboard:ESP32-C6-Zero', 'ESP32-C6-Zero', 'powerboard:Waveshare_ESP32-C6-Zero_Socket', '',
     {'1': 'VSYS', '2': 'GND', '3': '3V3', '4': 'VBAT_SENSE', '5': 'CHRG_IO', '6': 'SERVO_EN',
      '7': 'TFT_RST', '8': 'TFT_SCK', '9': 'TFT_MOSI',
      '10': None, '11': None, '12': None, '13': None, '14': 'SERVO_R', '15': 'SERVO_L',
      '16': 'TFT_DC', '17': 'TFT_CS', '18': None},
     p(96, 22), kit=True, desc='Gesteckt auf 2x Buchsenleiste 1x9', ty=15.24)

# --- Display -------------------------------------------------------------
part('J4', 'Connector:Conn_01x07_Socket', 'DISPLAY GC9A01', 'Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Horizontal', '',
     {'1': '3V3', '2': 'GND', '3': 'TFT_SCK', '4': 'TFT_MOSI', '5': 'TFT_DC', '6': 'TFT_CS', '7': 'TFT_RST'},
     p(96, 50), kit=True, desc='VCC GND SCL SDA DC CS RST, Display steckt direkt', ty=11.43)

# --- Test points, holes --------------------------------------------------
for i, net in enumerate(['BAT+', 'GND', 'VSYS', 'VSERVO', '3V3']):
    part(f'TP{i + 1}', 'Connector:TestPoint', f'TP_{net}', 'TestPoint:TestPoint_Pad_D1.0mm', '',
         {'1': net}, p(84 + i * 5, 66), bom=False)
for i in range(2):
    part(f'H{i + 1}', 'Mechanical:MountingHole', 'M2', 'MountingHole:MountingHole_2.2mm_M2', '',
         {}, p(84 + i * 5, 76), bom=False)

# Nets driven only by passive pins or power inputs need a PWR_FLAG for ERC.
PWR_FLAGS = ['GND', 'BATN', 'DW_VDD', 'BAT_SW', 'J_BATP']

NOTES = [
    (p(2, 4), 'Akku-Eingang, Verpolschutz'),
    (p(2, 28), 'Schutz: DW01A + FS8205A (BATN nur hier und an J1)'),
    (p(28, 4), 'Lader TP4054, 200 mA'),
    (p(34, 30), 'Ein/Aus (Q5) + Power Path (LM66100, CE fest auf GND)'),
    (p(2, 56), 'Servo-Schiene (GPIO2 schaltet, nur aus dem Akku)'),
    (p(56, 56), 'Akkumessung GPIO0'),
    (p(84, 4), 'Waveshare ESP32-C6-Zero'),
    (p(84, 40), 'Display, direkt gesteckt'),
    (p(82, 60), 'Testpunkte, Befestigung'),
]


# ---------------------------------------------------------------- symbols --
_libs = {}


def lib(name):
    if name not in _libs:
        path = os.path.join(PROJ, f'{PROJECT}.kicad_sym') if name == PROJECT else \
            os.path.join(KICAD_SYMS, f'{name}.kicad_sym')
        tree = parse(open(path, encoding='utf-8').read())
        _libs[name] = {x[1]: x for x in find(tree, 'symbol')}
    return _libs[name]


def flat_symbol(lib_id):
    """Return the symbol with any `extends` resolved, named lib:name."""
    libname, name = lib_id.split(':')
    syms = lib(libname)
    s = syms[name]
    ext = find1(s, 'extends')
    if ext:
        base = flat_symbol(f'{libname}:{ext[1]}')
        own = {x[1]: x for x in find(s, 'property')}
        out = [Sym('symbol'), lib_id]
        for x in base[2:]:
            if isinstance(x, list) and x[0] == 'property' and x[1] in own:
                out.append(own.pop(x[1]))
            elif isinstance(x, list) and x[0] == 'symbol':
                sub = list(x)
                sub[1] = name + sub[1][len(ext[1]):]
                out.append(sub)
            else:
                out.append(x)
        # keep the properties that only the child has, before the units
        idx = next(i for i, x in enumerate(out) if isinstance(x, list) and x[0] == 'symbol')
        for v in own.values():
            out.insert(idx, v)
        return out
    out = list(s)
    out[1] = lib_id
    return out


def pins_of(sym):
    res = {}
    for sub in find(sym, 'symbol'):
        for pn in find(sub, 'pin'):
            at = find1(pn, 'at')
            num = find1(pn, 'number')[1]
            res[num] = (float(at[1]), float(at[2]), int(float(at[3])) if len(at) > 3 else 0)
    return res


def rotate(x, y, rot):
    # symbol coordinates are y-up; schematic is y-down
    for _ in range(rot // 90):
        x, y = -y, x
    return x, -y


# ------------------------------------------------------------------- build --
def eff(size=1.27, hide=False, justify=None):
    e = [Sym('effects'), [Sym('font'), [Sym('size'), size, size]]]
    if justify:
        e.append([Sym('justify'), Sym(justify)])
    if hide:
        e.append([Sym('hide'), Sym('yes')])
    return e


def prop(name, value, at, hide=False, justify=None):
    return [Sym('property'), name, value, [Sym('at'), at[0], at[1], 0], eff(hide=hide, justify=justify)]


def label(net, x, y, ang):
    just = 'left' if ang in (0, 90) else 'right'
    return [Sym('label'), net, [Sym('at'), x, y, ang],
            [Sym('fields_autoplaced'), Sym('yes')],
            eff(justify=just), [Sym('uuid'), uid('label', net, x, y)]]


def build():
    lib_symbols = [Sym('lib_symbols')]
    used = {}
    for pt in PARTS:
        if pt['lib'] not in used:
            used[pt['lib']] = flat_symbol(pt['lib'])
    used['power:PWR_FLAG'] = flat_symbol('power:PWR_FLAG')
    lib_symbols += list(used.values())

    TWO_PIN = ('Device:R_Small', 'Device:C_Small', 'Device:C_Polarized_Small')
    body = []
    points = {}

    def claim(ax, ay, net, who):
        key = (round(ax, 2), round(ay, 2))
        if key in points:
            raise SystemExit(f'{who} at {key} collides with {points[key]}')
        points[key] = (who, net)

    for pt in PARTS:
        sym = used[pt['lib']]
        x, y = pt['at']
        rot = pt['rot']
        inst = [Sym('symbol'), [Sym('lib_id'), pt['lib']], [Sym('at'), x, y, rot], [Sym('unit'), 1],
                [Sym('exclude_from_sim'), Sym('no')],
                [Sym('in_bom'), Sym('yes' if pt['bom'] else 'no')],
                [Sym('on_board'), Sym('yes')],
                [Sym('dnp'), Sym('no')],
                [Sym('uuid'), uid('sym', pt['ref'])]]
        if pt['lib'] in TWO_PIN and rot == 0:
            # vertical part, its labels run up and down: text goes beside it
            inst += [prop('Reference', pt['ref'], (x + 2.54, y - 1.27), justify='left'),
                     prop('Value', pt['value'], (x + 2.54, y + 1.27), justify='left')]
        else:
            inst += [prop('Reference', pt['ref'], (x, y - pt['ty'])),
                     prop('Value', pt['value'], (x, y + pt['ty']))]
        inst += [
                prop('Footprint', pt['fp'], (x, y), hide=True),
                prop('Datasheet', '', (x, y), hide=True),
                prop('Description', pt['desc'], (x, y), hide=True),
                prop('LCSC', pt['lcsc'], (x, y), hide=True),
                prop('Kit', 'THT-Kit' if pt['kit'] else '', (x, y), hide=True)]
        pins = pins_of(sym)
        for num in sorted(pins, key=lambda n: (len(n), n)):
            inst.append([Sym('pin'), num, [Sym('uuid'), uid('pin', pt['ref'], num)]])
        inst.append([Sym('instances'), [Sym('project'), PROJECT,
                                         [Sym('path'), '/' + ROOT, [Sym('reference'), pt['ref']], [Sym('unit'), 1]]]])
        body.append(inst)

        for num, net in pt['pins'].items():
            px, py, pang = pins[num]
            dx, dy = rotate(px, py, rot)
            ax, ay = round(x + dx, 2), round(y + dy, 2)
            out = (pang + 180 + rot) % 360
            claim(ax, ay, net, f"{pt['ref']}.{num}")
            if net is None:
                body.append([Sym('no_connect'), [Sym('at'), ax, ay], [Sym('uuid'), uid('nc', pt['ref'], num)]])
            else:
                body.append(label(net, ax, ay, out))
        missing = set(pins) - set(pt['pins'])
        if missing:
            raise SystemExit(f"{pt['ref']}: pins without net: {sorted(missing)}")

    for i, net in enumerate(PWR_FLAGS):
        x, y = p(84 + i * 5, 86)
        ref = f'#FLG{i + 1:02d}'
        claim(x, y, net, ref)
        body.append([Sym('symbol'), [Sym('lib_id'), 'power:PWR_FLAG'], [Sym('at'), x, y, 0], [Sym('unit'), 1],
                     [Sym('exclude_from_sim'), Sym('no')], [Sym('in_bom'), Sym('yes')],
                     [Sym('on_board'), Sym('yes')], [Sym('dnp'), Sym('no')],
                     [Sym('uuid'), uid('flag', net)],
                     prop('Reference', ref, (x, y - 3.81), hide=True),
                     prop('Value', 'PWR_FLAG', (x, y - 3.81)),
                     prop('Footprint', '', (x, y), hide=True),
                     prop('Datasheet', '', (x, y), hide=True),
                     [Sym('pin'), '1', [Sym('uuid'), uid('flagpin', net)]],
                     [Sym('instances'), [Sym('project'), PROJECT,
                                         [Sym('path'), '/' + ROOT, [Sym('reference'), ref], [Sym('unit'), 1]]]]])
        body.append(label(net, x, y, 270))

    for (x, y), text in NOTES:
        body.append([Sym('text'), text, [Sym('exclude_from_sim'), Sym('no')], [Sym('at'), x, y, 0],
                     [Sym('effects'), [Sym('font'), [Sym('size'), 2, 2], [Sym('bold'), Sym('yes')]],
                      [Sym('justify'), Sym('left')]],
                     [Sym('uuid'), uid('note', text)]])

    sch = [Sym('kicad_sch'), [Sym('version'), 20231120], [Sym('generator'), 'gen_sch.py'],
           [Sym('generator_version'), '1'], [Sym('uuid'), ROOT], [Sym('paper'), 'A3'],
           [Sym('title_block'), [Sym('title'), 'MF26 Robo-Buddy Powerboard'], [Sym('rev'), '0.1'],
            [Sym('company'), 'KidsLab'],
            [Sym('comment'), 1, 'Erzeugt von tools/gen_sch.py - Netze nur dort aendern']],
           lib_symbols] + body + [[Sym('sheet_instances'), [Sym('path'), '/', [Sym('page'), '1']]]]
    with open(os.path.join(PROJ, f'{PROJECT}.kicad_sch'), 'w', encoding='utf-8') as f:
        f.write(dump(sch) + '\n')


if __name__ == '__main__':
    build()
