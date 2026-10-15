# Powerboard Rev 0.2 – Testskript für CircuitPython (ESP32-C6-Zero)
#
# Firmware: CircuitPython 10.x, Board "espressif_esp32c6_devkitc_1_n8"
# (der C6-Zero hat 8 MB Flash und die WS2812 an GPIO8 wie das DevKitC).
# Bedienung über die serielle Konsole, z. B. `tio /dev/ttyACM0` oder
# `screen /dev/ttyACM0 115200`. Ein Tastendruck = ein Befehl, `h` = Hilfe.

import time
import sys
import busio
import pwmio
import digitalio
import supervisor
import microcontroller
from neopixel_write import neopixel_write

P = microcontroller.pin

# --- Pins laut hardware/powerboard/README.md ---
SERVO_EN_PIN = P.GPIO15
SERVO_PINS = (P.GPIO19, P.GPIO18, P.GPIO16, P.GPIO17)  # Servo 1–4
SDA, SCL = P.GPIO14, P.GPIO22
INA_ADDR = 0x45
SHUNT_OHM = 0.010
V_BAT_MIN = 3.30  # darunter schaltet das Skript die 5 V ab

# --- INA226 ---
i2c = busio.I2C(SCL, SDA, frequency=400_000)


def ina_write(reg, val):
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto(INA_ADDR, bytes((reg, val >> 8, val & 0xFF)))
    finally:
        i2c.unlock()


def ina_read(reg):
    buf = bytearray(2)
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto_then_readfrom(INA_ADDR, bytes((reg,)), buf)
    finally:
        i2c.unlock()
    return buf[0] << 8 | buf[1]


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


# Mittelung 4, Wandlung 1,1 ms für Shunt und Bus, kontinuierlich → ~9 ms pro Wert
ina_write(0x00, (0b001 << 9) | (0b100 << 6) | (0b100 << 3) | 0b111)


def measure():
    """Akkuspannung (V) und Strom (A, positiv = Entladen, negativ = Laden)."""
    v_shunt = s16(ina_read(0x01)) * 2.5e-6
    v_bus = ina_read(0x02) * 1.25e-3
    return v_bus, v_shunt / SHUNT_OHM


# --- 5-V-Schiene ---
servo_en = digitalio.DigitalInOut(SERVO_EN_PIN)
servo_en.switch_to_output(False)

# --- Status-LED (WS2812 an GPIO8): grün = 5 V an, rot = Unterspannung ---
led = digitalio.DigitalInOut(P.GPIO8)
led.switch_to_output()


def set_led(r, g, b):
    neopixel_write(led, bytes((g, r, b)))


# --- Servos ---
servos = [pwmio.PWMOut(p, frequency=50, duty_cycle=0) for p in SERVO_PINS]
pulse = [0, 0, 0, 0]  # µs, 0 = kein Signal
selected = 0


def set_pulse(i, us):
    pulse[i] = us
    servos[i].duty_cycle = int(us * 65535 // 20000)


def all_off():
    for i in range(4):
        set_pulse(i, 0)


def set_5v(on):
    servo_en.value = on
    set_led(0, 20, 0) if on else set_led(0, 0, 0)
    print("5V Servo-Schiene:", "AN" if on else "AUS")


HELP = """
Powerboard-Test
  e      5 V Servo-Schiene an/aus (GPIO15)
  m      Messung fortlaufend an/aus (2x pro Sekunde)
  r      Spitzenwerte zurücksetzen
  1..4   Servo wählen
  + / -  Puls des gewählten Servos +/- 50 µs
  , / .  Puls +/- 5 µs (Stillstand eines 360°-Servos suchen)
  f      Fahrtest 360°-Servos: je 2 s vor, Stopp, zurück, Stopp, mit Strom
  [ / ]  Puls 1000 / 2000 µs (Endanschlag bzw. volle Fahrt)
  0      Puls 1500 µs (Mitte bzw. Stillstand)
  a      alle 4 Servos auf 1500 µs
  s      Sweep: alle Servos 1000→2000→1000 µs, dabei messen
  x      alle Servo-Signale aus
  h      diese Hilfe
Strom: positiv = Akku wird entladen, negativ = Akku wird geladen.
5 V selbst kann der ESP nicht messen: Multimeter an TP V5_SERVO / GND.
"""

peak_i = 0.0
min_v = 9.9


def status(prefix=""):
    v, i = measure()
    print("%sVbat %.3f V  I %+7.1f mA  P %6.0f mW  | Spitze %.0f mA, min %.3f V  | 5V %s  Servos %s"
          % (prefix, v, i * 1000, v * i * 1000, peak_i * 1000, min_v,
             "an " if servo_en.value else "aus", pulse))


def sample():
    """Schnell messen, Spitzen merken, bei Unterspannung abschalten."""
    global peak_i, min_v
    v, i = measure()
    peak_i = max(peak_i, i)
    if servo_en.value:
        min_v = min(min_v, v)
        if v < V_BAT_MIN:
            all_off()
            set_5v(False)
            set_led(30, 0, 0)
            print("!! Akku unter %.2f V (%.3f V) – 5 V abgeschaltet" % (V_BAT_MIN, v))


def sweep():
    print("Sweep läuft …")
    for us in list(range(1000, 2001, 20)) + list(range(2000, 999, -20)):
        for k in range(4):
            set_pulse(k, us)
        t = time.monotonic()
        while time.monotonic() - t < 0.03:
            sample()
    for k in range(4):
        set_pulse(k, 1500)
    status("Sweep fertig: ")


def drive_test():
    """Alle Servos gleichzeitig: 2 s pro Phase, mittlerer und Spitzenstrom je Phase."""
    global peak_i
    for name, us in (("vor", 2000), ("Stopp", 1500), ("zurück", 1000), ("Stopp", 1500)):
        for k in range(4):
            set_pulse(k, us)
        peak_i, n, s, vmin = 0.0, 0, 0.0, 9.9
        t = time.monotonic()
        while time.monotonic() - t < 2.0:
            sample()
            v, i = measure()
            n, s, vmin = n + 1, s + i, min(vmin, v)
        print("%-7s %4d µs: Strom Mittel %6.0f mA, Spitze %6.0f mA, Vbat min %.3f V"
              % (name, us, s / n * 1000, peak_i * 1000, vmin))


print(HELP)
status()
live = False
last = time.monotonic()

while True:
    sample()
    if live and time.monotonic() - last >= 0.5:
        last = time.monotonic()
        status()
    if not supervisor.runtime.serial_bytes_available:
        time.sleep(0.01)
        continue
    c = sys.stdin.read(1)
    if c == "e":
        set_5v(not servo_en.value)
        time.sleep(0.05)
        status()
    elif c == "m":
        live = not live
    elif c == "r":
        peak_i, min_v = 0.0, 9.9
        print("Spitzenwerte zurückgesetzt")
    elif c in "1234":
        selected = int(c) - 1
        print("Servo", c, "gewählt, Puls", pulse[selected], "µs")
    elif c in "+-,.[]0":
        cur = pulse[selected] or 1500
        us = {"+": cur + 50, "-": cur - 50, ".": cur + 5, ",": cur - 5,
              "[": 1000, "]": 2000, "0": 1500}[c]
        set_pulse(selected, max(500, min(2500, us)))
        print("Servo", selected + 1, "->", pulse[selected], "µs")
    elif c == "a":
        for k in range(4):
            set_pulse(k, 1500)
        print("alle Servos 1500 µs")
    elif c == "s":
        if not servo_en.value:
            print("Hinweis: 5 V sind aus, erst mit e einschalten")
        sweep()
    elif c == "f":
        if not servo_en.value:
            print("Hinweis: 5 V sind aus, erst mit e einschalten")
        drive_test()
    elif c == "x":
        all_off()
        print("alle Servo-Signale aus")
    elif c == "h":
        print(HELP)
    elif c in "\r\n ":
        status()
