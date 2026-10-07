# Powerboard (KiCad)

Trägerplatine, die den Robo-Buddy akkubetrieben macht. Anforderungen und Begründungen: `POWERBOARD-HANDOFF.md` im Repo-Hauptordner. ESP-Board: `../esp32-c6-zero/`.

Stand: **Schaltplan fertig, ERC ohne Meldungen. Platine nur vorläufig platziert, noch nicht geroutet.**

## Vorläufige Platine

`powerboard.kicad_pcb` erzeugt `tools/gen_pcb.py`. Das Skript legt die Kontur (45 × 30 mm, Platzhalter) und alle Footprints mit Netzen an, platziert sie grob und füllt eine GND-Fläche auf der Unterseite. Leiterbahnen gibt es noch keine. Die Platine dient nur dazu, zu sehen, ob alles passt. **Nicht bestellen.**

| Ansicht | Datei |
|---|---|
| 2D oben / unten | `ansichten/2d_oben.png`, `ansichten/2d_unten.png` |
| 3D oben / unten / schräg | `ansichten/3d_oben.png`, `ansichten/3d_unten.png`, `ansichten/3d_schraeg.png` |

Hinweise:
- Links: USB-C des ESP, Lade-LED. Oben: Display-Buchse, Öffnung zur Kante. Rechts: Servos. Unten: Akku-Buchse und Schalter.
- Der Schalter sitzt vorerst an der Unterkante, weil links der ESP die ganze Kante belegt. Die endgültige Lage kommt vom Gehäuse.
- Die SMD-Teile für Lader, Schutz und Power Path liegen unter dem gesteckten ESP. DRC meldet deshalb Courtyard-Überlappungen mit U4, das ist gewollt.
- In 3D fehlt das ESP-Modul selbst, weil es dafür kein 3D-Modell gibt. Zu sehen sind nur die beiden Buchsenleisten. Auch die JST-Buchse hat kein Modell.

## Dateien

| Datei | Inhalt |
|---|---|
| `powerboard.kicad_sch` | Schaltplan, **erzeugt** von `tools/gen_sch.py` |
| `powerboard.kicad_sym` | Projektsymbole FS8205A und ESP32-C6-Zero, erzeugt von `tools/gen_lib.py` |
| `powerboard.pretty/` | Footprint für den gesteckten C6-Zero, erzeugt von `tools/gen_lib.py` |
| `powerboard.kicad_pcb` | vorläufige Platine, erzeugt von `tools/gen_pcb.py` |
| `tools/` | Generatoren |

Der Schaltplan entsteht aus der Bauteilliste in `tools/gen_sch.py`. Jeder Pin hängt über ein Netz-Label an seinem Netz. Änderungen also dort machen und neu erzeugen, nicht im Schaltplan-Editor:

```
python3 tools/gen_lib.py
python3 tools/gen_sch.py
kicad-cli sch erc powerboard.kicad_sch
```

## Prüfungen

- `kicad-cli sch erc`: 0 Meldungen.
- Netzliste gegen Handoff geprüft: `BATN` nur an J1.2, DW01 VSS, FS8205A S1, Gate-Widerstand R1 und DW01-Kondensator C1. Servo-Plus nur an `VSERVO`. GPIOs wie in Abschnitt 4.
- Pinbelegungen aus den LCSC-Datenblättern:
  - FS8205A (C908265): 1 S1, 2 D, 3 S2, 4 G2, 5 D, 6 G1
  - DW01A (C2927799): 1 OD, 2 CS, 3 OC, 4 NC, 5 VDD, 6 VSS
  - TP4054 (C668215): 1 CHRG, 2 GND, 3 BAT, 4 VCC, 5 PROG. Symbol ist der LTC4054, gleiche Belegung.
  - LM66100: 1 VIN, 2 GND, 3 CE, 4 NC, 5 ST, 6 VOUT
- Das LM66100-Datenblatt empfiehlt, ST auf GND zu legen, wenn es nicht gebraucht wird. Hier ist es offen gelassen: Es ist ein Open-Drain-Ausgang, und auf GND gelegt würde ERC einen Typkonflikt mit dem PWR_FLAG melden. Elektrisch macht das keinen Unterschied.

## Offen

- **Footprint C6-Zero:** Der Reihenabstand von 17,78 mm stammt aus der Waveshare-Zeichnung und muss am echten Board nachgemessen werden. Der Wert steht in `tools/gen_lib.py` (`ROW`).
- **LCSC-Nummern fehlen noch für:** 100 Ω, 5,1 kΩ, 470 kΩ, 1 MΩ, 220 Ω, 47 nF, den 470-µF-Elko und die JST-PH-SMD-Buchse. Vor der Bestellung alle Nummern auf Lager und Basic/Extended prüfen.
- **SW1:** Der Footprint (CK OS102011MA1Q, gewinkelt) ist ein Platzhalter, bis die Bauform feststeht.
- **Layout:** wartet auf die Gehäusekontur, die Schalterposition und die Display-Maße (Handoff Abschnitt 9).
- **THT-Teile (U4-Sockel, J2–J4, SW1):** Sie sind mit dem Feld `Kit = THT-Kit` markiert. Beim JLC-Export werden sie herausgefiltert.
