# Powerboard (KiCad)

Trägerplatine, die den Robo-Buddy akkubetrieben macht. Anforderungen und Begründungen: `POWERBOARD-HANDOFF.md` im Repo-Hauptordner. ESP-Board: `../esp32-c6-zero/`.

Stand Rev 0.2: **Schaltplan fertig, ERC ohne Meldungen. Platine mit echter Kontur, platziert und geroutet (2 Lagen). Fertigungsdateien für JLCPCB in `fertigung/`. Vor der ersten Bestellung die Punkte unter „Offen“ prüfen.**

## Was drauf ist

- Akku (Pouch-LiPo, 1S) an J1, JST-PH **THT**: Verpolschutz (2 × AO3401A parallel), Zellschutz DW01A mit 2 × FS8205A parallel (Auslösung ~6–8 A).
- Strom- und Spannungsmessung: INA226 an I²C (Adresse 0x45), Shunt 10 mΩ zwischen `BAT_CELL` und `BAT+`. Misst Lade- (negativ) und Entladestrom sowie die Akkuspannung.
- Lader TP4056, 235 mA, aus dem 5V-Pin des ESP (USB). Rote LED leuchtet nur beim Laden.
- Ein/Aus (Q5 + SW1) und ideale Diode LM66100 für den ESP.
- 5-V-Servoschiene: Boost TPS61023 (≥ 2 A bei 5 V), von GPIO15 geschaltet. Bei EN low ist der Ausgang echt vom Akku getrennt.
- Ports (alle 2,54 mm, THT-Kit):

| Port | Belegung | GPIO |
|---|---|---|
| Servo 1–4 (J2, J3, J5, J6) | S + − (5 V) | 19, 18, 16, 17 |
| Analog A0–A2 (J7–J9) | GND 3V3 SIG, 1 kΩ in Serie, 0–3,1 V | 0, 1, 2 |
| I²C 1, 2 (J10, J11) | GND 3V3 SDA SCL, 4,7 kΩ Pull-ups | SDA 14, SCL 22 |
| Display (J4) | VCC GND SCL SDA DC CS RST, per Kabel | 4, 5, 20, 21, 3 |

## Platine

`powerboard.kicad_pcb` erzeugt `tools/gen_pcb.py`. Kontur, Platzierung und Herleitung der Maße stehen dort im Kopf.

**Kontur** aus `cad/MF26-Roboter.step`: Innenseite der Hülle direkt über der Bodenplatte, 0,5 mm Luft. Ca. 55 × 53 mm, vorne gerade hinter dem Display, hinten zwei Schrägen und ein gerades Stück vor dem Dom des Schleifrads.

**Platzierung:**
- ESP an der einen hinteren Schräge, USB-C zeigt durch die Wand. Schalter und Lade-LED an der anderen Schräge.
- Servo-Leisten an der einen Längsseite, Analog-Leisten an der anderen, beide ein Stück vom Rand nach innen gesetzt (die Kabel kommen von oben).
- **Leistungsblock vorne**, alles mit festem, breitem Kupfer vorverdrahtet (`POWER_TRACKS` in `gen_pcb.py`):
  - 5-V-Schiene (1,2 mm) direkt hinter den Servo-Leisten, Stich zu jedem Plus-Pin
  - Boost TPS61023 nach dem Layout-Beispiel von TI: Spule direkt über dem SW-Pin, vier Ausgangskondensatoren in einer Spalte zwischen VOUT und GND, Eingangskondensator an VIN
  - Akkupfad J1 → Verpolschutz (Q1, Q7) → Shunt R15 → Spule, Zellschutz Q2/Q6 neben J1
- Display-Leiste J4 ungefähr mittig auf der Displayachse, hinter dem Leistungsblock; zum Display per Kabel.
- I²C-Leisten, Testpunkte und Pull-ups in der Mitte, INA226 hinter dem Shunt.
- Lader und Power Path beim ESP, Ein/Aus-FET direkt hinter dem Schalter.

| Ansicht | Datei |
|---|---|
| Passung im Gehäuse (Schnitte) | `ansichten/passung_schnitte.png`, erzeugt von `tools/render_fit.py` |
| 2D oben / unten | `ansichten/2d_oben.png`, `ansichten/2d_unten.png` |
| 3D oben / unten / schräg | `ansichten/3d_oben.png`, `ansichten/3d_unten.png`, `ansichten/3d_schraeg.png` |

Hinweise:
- **USB-C** endet ca. 1,25 mm hinter der Außenfläche der Hülle. Ganz bündig ginge nur, wenn das ESP-Modul 1 mm über die Platinenkante ragt. Dann läge aber Pad 1 auf der Kante, weil der erste Pin nur 1,6 mm hinter der Modulkante sitzt. Bei Bedarf lässt sich die Wand um die Buchse innen etwas ausdünnen.
- **Display:** Es steht vorne tiefer als die Platine. J4 ist deshalb eine Stiftleiste für ein kurzes Kabel.
- Mindestabstand im Projekt 0,15 mm, minimale Bahnbreite 0,15 mm (Pads des SOT-563 und des INA226 liegen so eng). JLC fertigt 0,1 mm.
- Bauteilnummern stehen nicht im Bestückungsdruck, nur auf der Fab-Lage (Bestückung bei JLC geht nach Koordinaten, die Anschlüsse haben eigene Beschriftungen).
- In 3D fehlt das ESP-Modul selbst, weil es dafür kein 3D-Modell gibt. Zu sehen sind nur die beiden Buchsenleisten.

### Öffnungen in der Hülle (CAD-Koordinaten, für FreeCAD)

Platine liegt auf der Bodenplatte, Unterseite z = 12,5, Oberseite z = 14,1.

| Öffnung | Wand | Mitte (x, y) an der Wandaußenseite | Höhe z | Hinweis |
|---|---|---|---|---|
| USB-C | Schräge, niedriges y | (42,2 / 5,2) | ≈ 27–28 | hängt von Leisten- und Modulhöhe ab, am Muster messen; Öffnung für den Stecker ~12,5 × 7 mm |
| Schalterhebel | Schräge, hohes y | (47,6 / 41,7) | ≈ 15,5 | Hebel ragt ~1,4 mm aus der Wand, 2 mm Hub entlang der Wand |
| Lade-LED | Schräge, hohes y | (38,0 / 48,9) | ≈ 14,5 | 0603 strahlt nach oben, sitzt 1 mm vor der Wand: Fenster knapp über der Platine oder Lichtleiter |

## Dateien

| Datei | Inhalt |
|---|---|
| `powerboard.kicad_sch` | Schaltplan, **erzeugt** von `tools/gen_sch.py` |
| `powerboard.kicad_sym` | Projektsymbole FS8205A, TPS61023 und ESP32-C6-Zero, erzeugt von `tools/gen_lib.py` |
| `powerboard.pretty/` | Footprints C6-Zero-Sockel, Shunt mit Kelvin-Pads, Schalter mit runden Pads, KidsLab-Logo; erzeugt von `tools/gen_lib.py` |
| `logo/kidslab-logo.svg` | Vorlage für das Logo auf der Unterseite |
| `powerboard.kicad_pcb` | Platine: Platzierung von `tools/gen_pcb.py`, Leiterbahnen von `tools/route.py` |
| `fertigung/` | JLCPCB: `powerboard_gerber.zip`, `powerboard_bom.csv`, `powerboard_cpl.csv`, erzeugt von `tools/export_jlc.py` |
| `tools/` | Generatoren, Routing (`route.py`, `maze.py`), Ansichten (`render_views.py`, `render_fit.py`) |

Schaltplan und Platine entstehen aus den Skripten. Änderungen also dort machen und neu erzeugen, nicht im Editor:

```
python3 tools/gen_lib.py
python3 tools/gen_sch.py
kicad-cli sch erc powerboard.kicad_sch
python3 tools/gen_pcb.py          # Platzierung + festes Kupfer des Leistungsblocks
python3 tools/route.py            # 20–30 min, siehe unten
kicad-cli pcb drc powerboard.kicad_pcb
python3 tools/render_views.py
python3 tools/render_fit.py
python3 tools/export_jlc.py
```

### Routing

`tools/route.py` braucht [Freerouting](https://github.com/freerouting/freerouting) 2.4.1 als `~/.cache/freerouting/freerouting-2.4.1.jar` (oder `$FREEROUTING_JAR`) und Java.

1. Kurze Verbindungen an der Kante (Schalter, LED, ESP-Pin 1) und in manchen Varianten die Leistungsnetze werden zuerst allein geroutet und gesperrt, danach alles andere.
2. Freerouting kommt mit zwei Dingen dieser Platine nicht zurecht, `route.py` umgeht beide in der Exportdatei:
   - **Schräge Bauteile:** Pads von Bauteilen unter 126,5° bzw. 53,5° (ESP, Schalter) sind für Freerouting nicht erreichbar. Die Drehung wird deshalb in die Pad-Positionen eingerechnet.
   - **Schräge Kanten:** Pads bis ~2 mm vor den schrägen Kanten sind ebenfalls unerreichbar. Die Kontur wird deshalb durch das umschließende Rechteck plus Sperrflächen ersetzt.
3. Acht Varianten (Reihenfolge, Bahnbreite, Durchläufe), die mit den wenigsten offenen Verbindungen bleibt.
4. `tools/maze.py` schließt, was noch offen ist (Raster-Router, 0,1 mm, mit Lagenwechsel).
5. Leistungsbahnen so breit wie der DRC erlaubt (bis 1,2 mm), GND-Fläche oben und unten mit Durchkontaktierungen, hängende Vias weg.

GND wird wie ein normales Netz geroutet; die Flächen verstärken es nur. So bleibt GND verbunden, auch wenn Signale eine Fläche zerschneiden.

## Prüfungen

- `kicad-cli sch erc`: 0 Meldungen.
- Netzliste geprüft:
  - `BATN` nur an J1.2, DW01 VSS, S1 beider FS8205A, R1, C1
  - `V5_SERVO` nur an Servo-Plus, Boost-Ausgang, Rückkopplung, Ausgangskondensatoren und TP4
  - kein Servo-Plus an `3V3` oder `VSYS`
  - Shunt R15 zwischen `BAT_CELL` (INA226 IN+) und `BAT+` (IN−, VBUS)
  - GPIOs wie oben
- Pinbelegungen aus den Datenblättern:
  - FS8205A (C908265): 1 S1, 2 D, 3 S2, 4 G2, 5 D, 6 G1
  - DW01A (C2927799): 1 OD, 2 CS, 3 OC, 4 NC, 5 VDD, 6 VSS
  - TP4056 (C16581): 1 TEMP, 2 PROG, 3 GND, 4 VCC, 5 BAT, 6 STDBY, 7 CHRG, 8 CE, EP GND. KiCad-Symbol `TP4056-42-ESOP8`, das genau dieses Teil ist.
  - TPS61023 (C919459, TI SLVSF14B): 1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 VOUT. V_REF 0,595 V, mit 750 k / 100 k → 5,06 V.
  - INA226 (C49851): 1 A1, 2 A0, 3 ALERT, 4 SDA, 5 SCL, 6 VS, 7 GND, 8 VBUS, 9 IN−, 10 IN+
  - LM66100: 1 VIN, 2 GND, 3 CE, 4 NC, 5 ST, 6 VOUT
- Das LM66100-Datenblatt empfiehlt, ST auf GND zu legen, wenn es nicht gebraucht wird. Hier ist es offen gelassen: Es ist ein Open-Drain-Ausgang, und auf GND gelegt würde ERC einen Typkonflikt mit dem PWR_FLAG melden. Elektrisch macht das keinen Unterschied.

## Offen

- **Akkuwiege in der Hülle:** Die Hülle hat noch die Wiege für den Zylinder-Akku (Wände bei y ≈ 17 und 34, ab z ≈ 22). Die hintere Ecke des gesteckten ESP ragt da hinein (`passung_schnitte.png`, rechtes Bild). Für den Pouch-Akku muss die Wiege ohnehin raus.
- **Befestigung:** H1 und H2 (M2) sind frei gesetzt. Lage mit den Schraubpunkten der Bodenplatte abgleichen.
- **Footprint C6-Zero:** Der Reihenabstand von 17,78 mm stammt aus der Waveshare-Zeichnung und muss am echten Board nachgemessen werden. Der Wert steht in `tools/gen_lib.py` (`ROW`).
- **SW1:** Der Footprint (CK OS102011MA1Q, gewinkelt) ist ein Platzhalter, bis die Bauform feststeht.
- **Strom:** JST-PH ist für 2 A spezifiziert. Im Betrieb reicht das, blockieren alle 4 Servos, sind kurz 3–4 A möglich. Die Zelle muss diese Spitzen liefern können.
- **INA226 bei ausgeschaltetem ESP:** Die Messeingänge hängen am Akku, die Versorgung (3V3) fehlt dann. Laut Datenblatt sind die Eingänge unabhängig von VS bis 36 V zulässig. Den Ruhestrom im ausgeschalteten Zustand am Prototyp messen.
- **THT-Teile:** U4-Sockel, J1–J11 und SW1 sind mit dem Feld `Kit = THT-Kit` markiert. Beim JLC-Export werden sie herausgefiltert.
