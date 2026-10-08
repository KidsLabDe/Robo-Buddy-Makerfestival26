# Handoff: Robo-Buddy Power-Trägerplatine (KiCad)

Auftrag für Claude Code. Ziel ist ein bestellfertiges KiCad-Projekt (Schaltplan + Platine) für eine Trägerplatine, die den MF26 Robo-Buddy akkubetrieben macht. Gefertigt wird bei JLCPCB (alternativ PCBWay).

Auftraggeber: Gregor (KidsLab). Die Platinen werden in Workshops von Kindern/Jugendlichen fertig gelötet. Sicherheit des Akkuteils hat Vorrang vor allem anderen.

Stand: Rev 0.2 (Oktober 2026). Gegenüber Rev 0.1 neu: 4 Servos an 5 V (Boost), Strommessung (INA226), Analog- und I²C-Ports, JST-Buchse als THT, Pouch-Akku, Kontur aus dem Gehäuse-CAD, wo möglich Basic-Teile von JLC.

---

## 1. Fertigungskonzept

- **JLCPCB bestückt nur SMD, nur Oberseite.** Alles, was mit dem Akku zu tun hat, wird maschinell gelötet: Verpolschutz, Zellschutz, Shunt, Lader, Boost.
- **Die Teilnehmer löten nur THT:** Buchsenleisten für den ESP, Servo-, Analog-, I²C- und Display-Stiftleisten, Schiebeschalter und die **Akku-Buchse J1 (JST-PH, THT)**. Ca. 60 Lötstellen pro Platine.
- J1 hat 2,0 mm Raster. Eine Lötbrücke zwischen den beiden Pins läge vor der Schutzschaltung, wäre also ein ungeschützter Zellkurzschluss. Deshalb ist der **Durchgangstest direkt über J1 vor dem ersten Anstecken Pflicht** (Abschnitt 10, Prüfschritt). Mit Gregor so entschieden: THT ist für die Kinder leichter zu löten.
- THT-Teile stehen in der JLCPCB-BOM **nicht** (bzw. als DNP); dafür gibt es eine separate Kit-Stückliste.
- Wo es ohne Nachteil geht, Basic- oder Preferred-Teile von JLC (keine Rüstgebühr pro Bauteiltyp).
- Erst Prototyp (5–10 bestückte Platinen), dann Serie (50 Stück) nach Revision.

## 2. Rahmenbedingungen

- Roboter laut `cad/MF26-Roboter.step`: ca. 60 × 67 mm Bodenplatte, zwei 9g-Continuous-Servos (Tower-Pro-Klone) in der Bodenplatte, rundes GC9A01-Display vorne. Bis zu zwei weitere Servos über die Ports.
- Zelle: **Pouch-LiPo** 1S, 300–500 mAh, per Kabel an J1, Lage im Kopf. Teilweise recycelte Vape-Zellen, **oft ohne eigene Schutzschaltung**. Die Platine muss den Schutz vollständig selbst leisten. Die Zelle muss Spitzen von ~4 A liefern können (4 Servos an 5 V).
- MCU: **Waveshare ESP32-C6-Zero** (Original, nicht Klon), gesteckt auf Buchsenleisten (tauschbar). Details in Abschnitt 5. Firmware: https://github.com/MakeYourSchool/Robo-Buddy-Makerfestival26 (PlatformIO, pioarduino, Pins in `src/config.h`).
- Ein einziger USB-C-Port nach außen: der des ESP-Boards. Darüber wird geflasht **und** geladen.
- **Die Servos laufen nur mit eingesteckter Zelle**, auch an USB. Bewusste Entscheidung: Servostrom fließt so nie über USB und den 5V-Pin des ESP-Boards.
- Platine: liegt flach auf der Bodenplatte innerhalb der Hülle, ca. 55 × 53 mm, 2 Lagen, 1,6 mm. Kontur aus dem CAD (Abschnitt 8).

## 3. Schaltungskonzept

```
USB-C (C6-Zero) ─► B5819WS ─► 5V-Pin = VSYS ─┬──► TP4056 VCC          (Lader)
                                             └──◄ LM66100 VOUT        (ideale Diode, Power Path, nur ESP)
                                                      ▲ VIN = BAT_SW
                                                      Q5 AO3401A (Ein/Aus, Gate über SW1)
                                                      ▲
J1+ ─► Q1+Q7 AO3401A (Verpolschutz) ─► BAT_CELL ─► Shunt 10 mΩ ─► BAT+ ─┼──┘
              │                                                         ├──► TP4056 BAT
              ├──► DW01A VDD (über 100 Ω)                               ├──► INA226 VBUS, IN−
              └──► INA226 IN+                                           └──► TPS61023 VIN ─► V5_SERVO ─► Servos +
J1− = BATN ─► 2× FS8205A parallel (low side) ─► GND                              (EN = GPIO15)
SW1 schaltet das Gate von Q5 (kein Laststrom über den Schalter); LM66100 CE fest auf GND
```

Verhalten, das die Schaltung garantieren muss:

| Zustand | Verhalten |
|---|---|
| USB an, Schalter egal | ESP läuft aus USB. LM66100 sperrt (VOUT > VIN). TP4056 lädt die Zelle. Servos laufen aus der Zelle über den Boost, solange die Firmware GPIO15 high setzt; im Stand ist der Boost aus, dann lädt die Zelle ohne Last und das Ladeende wird sauber erkannt. |
| USB aus, Schalter EIN | Zelle speist über LM66100 auf VSYS (ESP) und über den Boost auf V5_SERVO. TP4056 schläft (VCC < BAT). |
| USB aus, Schalter AUS | Q5 aus, ESP aus, Boost per Pull-down an EN aus (Ausgang echt getrennt). Verbrauch nur DW01 (~3 µA), Boost-Shutdown (~0,1 µA), INA226-Eingänge (wenige µA, am Prototyp messen) und Leckströme. |
| USB an, aber schwach | VSYS fällt unter VBAT, LM66100 springt automatisch ein (nur bei Schalter EIN). Servo-Spitzen belasten USB nicht. |
| Keine Zelle, USB an | ESP läuft, Servos bewegen sich nicht. Der TP4056 kann ohne Zelle an BAT+ eine pendelnde Spannung ausgeben; die Firmware darf sich darauf nicht verlassen. |
| Zelle verpolt eingesteckt | Q1/Q7 sperren, kein Strompfad. |
| Zelle tiefentladen / Kurzschluss | DW01A + FS8205A trennen (2,4 V / Überstrom ~6–8 A / Kurzschluss). Primärer Tiefentladeschutz ist aber die Firmware (Abschnitt 7). |

### 3.1 Netze

| Netz | Beschreibung |
|---|---|
| `VSYS` | 5V-Pin des C6-Zero (hinter dessen Schottky-Diode), TP4056 VCC und CE, LM66100 VOUT. ≈ 4,7 V an USB, ≈ VBAT im Akkubetrieb. **Keine Servos.** |
| `V5_SERVO` | Servo +, Ausgang des TPS61023 (5,06 V). Nur aus der Zelle gespeist, von der Firmware geschaltet. |
| `SERVO_EN` | GPIO15 → EN des TPS61023, 100 kΩ nach GND. High = Servos an. |
| `3V3` | 3V3-Pin des C6-Zero (Ausgang des Onboard-LDO ME6217C33). Display, INA226, Analog- und I²C-Ports, Lade-LED. |
| `GND` | Systemmasse = PACK− (hinter FS8205A). ESP-Board GND, Lader GND, alles andere. |
| `BAT_CELL` | Zellplus hinter Verpolschutz Q1/Q7, vor dem Shunt. DW01 VDD, INA226 IN+. |
| `BAT+` | Hinter dem Shunt. Alle Verbraucher und der Lader. |
| `BATN` | Zellminus direkt an J1 Pin 2 (DW01 VSS, FS8205A Source FET1). **Nicht** mit GND verbinden. |
| `J_BATP` | Zellplus am Stecker, vor Q1/Q7. |
| `BAT_SW` | Zwischen Q5 (Ein/Aus) und LM66100 VIN. |
| `SW_GATE` | Gate von Q5, 1 MΩ nach `BAT+`, SW1 nach GND. |
| `I2C_SDA`, `I2C_SCL` | GPIO14 / GPIO22, 4,7 kΩ nach 3V3. INA226 und beide I²C-Ports. |
| `A0`–`A2` / `A0_IO`–`A2_IO` | Analog-Ports, über 1 kΩ an GPIO0–2. |
| `CHRG_N` | TP4056 CHRG (open drain, low = lädt), nur Lade-LED. |

### 3.2 Blöcke im Detail

**Verpolschutz (Q1, Q7, AO3401A, P-FET, parallel)**
- Drain = `J_BATP`, Source = `BAT_CELL`, Gate = `BATN` über 10 kΩ (R1, gemeinsam).
- Zwei parallel, weil ein AO3401A (~60–85 mΩ bei 3–4 V) bei Servo-Spitzen zu viel Spannung verliert; parallel ~35 mΩ. Basic-Teil statt eines teuren Low-Rds-FETs (Entscheidung Gregor).
- Bei richtiger Polung leitet zuerst die Body-Diode, dann schaltet der FET durch (Vgs ≈ −VBAT). Ladestrom fließt rückwärts durch den Kanal, das ist bei eingeschaltetem FET in Ordnung.
- Geprüft: Bei verpolter Zelle gibt es keinen geschlossenen Strompfad, der nicht über Q1/Q7 läuft (Vgs ≥ 0, Body-Diode sperrt). Alle Verbraucher hängen an `BAT_CELL`, `BAT+` oder `GND`, nur DW01 VSS und FS8205A hängen an `BATN`. Diese Eigenschaft beim Schaltplan erhalten.

**Schutz (U2 DW01A + Q2, Q6 FS8205A)**
- Standardbeschaltung laut DW01A-Datenblatt: VDD über 100 Ω an `BAT_CELL`, 100 nF VDD–VSS, VSS = `BATN`, OD → Gate Entlade-FET, OC → Gate Lade-FET, CS über 1 kΩ an `GND` (PACK−).
- FS8205A: gemeinsamer Drain intern, Source FET1 = `BATN`, Source FET2 = `GND`. **Zwei parallel**: halbiert den Widerstand, die Überstromschwelle (~150 mV am FET-Paar) liegt dann bei ~6–8 A statt ~3 A. Sonst würden 4 Servos am Boost den Schutz auslösen.
- Pinbelegungen aus den LCSC-Datenblättern, siehe `hardware/powerboard/README.md`.
- Hinweis für die Doku: Der DW01 startet nach dem ersten Anstecken einer Zelle evtl. im Schutzzustand. Einmal USB anstecken gibt ihn frei.

**Strom- und Spannungsmessung (U5 INA226, R15 10 mΩ)**
- Shunt zwischen `BAT_CELL` und `BAT+`: misst alles, was in die Zelle hinein- und aus ihr herausfließt (Laden negativ). Bereich ±8 A, Auflösung 0,25 mA.
- IN+ = `BAT_CELL`, IN− = `BAT+`, VBUS = `BAT+` (Akkuspannung), VS = `3V3`, A0 = A1 = VS → I²C-Adresse **0x45** (0x40 belegen viele Sensoren).
- Ersetzt den Spannungsteiler aus Rev 0.1 und den CHRG-GPIO; beide Pins werden für die Ports gebraucht. Die Firmware erkennt Laden am Vorzeichen des Stroms und kann Ladung zählen (Akkustand in %).
- Shunt beim Layout mit Kelvin-Anschluss an IN+/IN− führen.

**Lader (U1, TP4056, ESOP-8)**
- Preferred-Teil bei JLC (keine Rüstgebühr), ersetzt den TP4054 aus Rev 0.1.
- VCC = CE = `VSYS`, BAT = `BAT+`, GND und EP = `GND`, TEMP = GND (kein NTC, bewusst entschieden).
- R_PROG = **5,1 kΩ** → 1200 V / 5,1 kΩ ≈ 235 mA. Passt für alle Zellen von 300–500 mAh.
- 4,7 µF an VCC, 4,7 µF an BAT.
- CHRG: rote LED (0603) + 1 kΩ nach **`3V3`**. Leuchtet nur beim Laden; ohne USB schläft der Lader und CHRG ist hochohmig, die LED zieht nie Strom aus dem Akku. STDBY offen.

**Power Path / Ein-Aus (U3, LM66100, SC-70-6)**
- VIN = `BAT_SW`, VOUT = `VSYS`, GND = `GND`, ST unbeschaltet.
- **CE fest auf GND** (immer an, reine ideale Diode).
- Geklärt im Datenblatt (SLVSEZ9): Die CE-Schwelle ist **relativ zu VIN**. Ein Pull-up nach VIN schaltet also **nicht sicher ab** (CE-Leckstrom bis 610 nA am 1-MΩ-Pull-up). Deshalb schaltet ein separater P-FET.
- **Ein/Aus über Q5 (AO3401A):** Source = `BAT+`, Drain = `BAT_SW`. Gate = `SW_GATE`: 1 MΩ nach `BAT+` (aus), SW1 zieht nach GND (an). SW1 führt so nur µA. Q5 trägt nur den ESP (WiFi-Spitzen ca. 350 mA).
- Keine Basic-Alternative: Eine Schottky-Diode statt der idealen Diode kostet ~0,35 V, bei halbvollem Akku bekommt der ESP dann zu wenig Spannung.

**Servo-Schiene 5 V (U6 TPS61023, L1 1 µH)**
- Synchroner Boost, 3,7 A Valley-Limit (min. 2,7 A). Ausgang bei 3,3 V Akku ≥ 2,0 A garantiert, typ. ~2,6 A. Das begrenzt zugleich den Akkustrom auf ~4–4,5 A.
- **EN = `SERVO_EN` (GPIO15)**, 100 kΩ nach GND. Bei EN low ist der Ausgang echt vom Akku getrennt (Datenblatt SLVSF14B, 7.3.2), deshalb kein eigener Schalt-FET mehr wie in Rev 0.1.
- Rückkopplung 750 kΩ / 100 kΩ → 0,595 V × 8,5 = 5,06 V; 220 pF parallel zu 750 kΩ (Feedforward, Nullstelle ~1 kHz, empfohlen ab > 40 µF am Ausgang).
- Eingang 22 µF, Ausgang 4 × 22 µF Keramik (Basic) statt Elko; TI erlaubt 4–1000 µF effektiv.
- Spule MWSA0402S-1R0MT: 1 µH, 7 A Sättigung.
- Softstart: der Boost lädt den Ausgang erst mit ~350 mA bis 0,4 V, dann begrenzt. Am Prototyp messen: Der DW01 darf beim Einschalten nicht auslösen.

**Servos (J2, J3, J5, J6)**
- 1×3 Stiftleiste, Belegung **S, +, −** (Plus in der Mitte, ein verkehrt gesteckter Servo nimmt keinen Schaden).
- S über 220 Ω an GPIO19, 18, 16, 17. + = `V5_SERVO`, − = `GND`. Das 3,3-V-Signal reicht den Servos auch an 5 V, ein Level-Shifter ist nicht nötig.
- Silkscreen "SERVO 5V" und "S + −"; räumlich getrennt von den 3,3-V-Ports.

**Analog (J7–J9) und I²C (J10, J11)**
- Analog: 1×3 **GND, 3V3, SIG**, SIG über 1 kΩ an GPIO0, 1, 2 (die einzigen ADC-Pins an den Leisten des C6-Zero). Messbereich 0–3,1 V.
- I²C: 1×4 **GND, 3V3, SDA, SCL** (Grove-Reihenfolge), 4,7 kΩ Pull-ups auf der Platine, INA226 am selben Bus.
- 3V3 kommt vom LDO des ESP (800 mA); der ESP braucht bis ~350 mA, für Sensoren bleiben ~300 mA.

**Display (J4)**
- 1×7 Stiftleiste, Reihenfolge des Moduls: **VCC, GND, SCL, SDA, DC, CS, RST**. VCC = `3V3`, SCL = GPIO4, SDA = GPIO5, DC = GPIO20, CS = GPIO21, RST = GPIO3.
- **Per Kabel**: Das Display steht laut CAD vorne bei x −8 … −4,4 und reicht tiefer als die Platine, eine Buchse auf der Platine erreicht seine Stiftleiste nicht.

**Testpunkte** (beschriftet, für den Prüfschritt im Workshop)
- TP_BAT+, TP_GND, TP_VSYS, TP_V5_SERVO, TP_3V3.

## 4. GPIO-Belegung (ESP32-C6)

Alle 15 Pins an den Leisten sind belegt.

| GPIO | Funktion | Bemerkung |
|---|---|---|
| 0 | Analog A0 (ADC1) | neu |
| 1 | Analog A1 (ADC1) | neu (Rev 0.1: CHRG) |
| 2 | Analog A2 (ADC1) | neu (Rev 0.1: SERVO_EN) |
| 3 | Display RST | wie bisher |
| 4 | Display SCK | wie bisher |
| 5 | Display MOSI | wie bisher |
| 14 | I²C SDA | neu |
| 15 | SERVO_EN (Output, High = an) | Strapping-Pin, wirkt nur bei gesetzter JTAG-eFuse; 100 kΩ nach GND |
| 16 | Servo 3 | UART TX; unkritisch, weil die Servos beim Booten aus sind |
| 17 | Servo 4 | UART RX; Konsole läuft über USB |
| 18 | Servo 2 (rechts) | wie bisher |
| 19 | Servo 1 (links) | wie bisher |
| 20 | Display DC | **geändert** (bisher 6) |
| 21 | Display CS | **geändert** (bisher 7) |
| 22 | I²C SCL | neu |

Nicht verwenden: GPIO6, 7, 8, 9, 12, 13, 23 liegen beim C6-Zero nur als Pads auf der Unterseite (8 = WS2812, 9 = BOOT, 12/13 = USB).

## 5. ESP-Board: Waveshare ESP32-C6-Zero

Gewählt: **Waveshare ESP32-C6-Zero**, Originalware (z. B. eckstein-shop.de). Wiki: https://www.waveshare.com/wiki/ESP32-C6-Zero, Schaltplan: https://files.waveshare.com/wiki/ESP32-C6-Zero/ESP32-C6-Zero-Sch.pdf. Klone können Pinbelegung übernehmen, aber andere Bauteile verbauen; für die Serie nur Originale.

Laut Waveshare-Pinout (USB-C oben, Draufsicht):

| Links | 5V | GND | 3V3 | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|---|---|---|
| **Rechts** | **TX (16)** | **RX (17)** | **14** | **15** | **18** | **19** | **20** | **21** | **22** |

Unterseite, zusätzliche Pads in einer Reihe: 13, 12, 23, 9, 8, 7, 6. **Nicht verwenden, keine Leiste.**

Laut Schaltplan:
- USB-VBUS → **B5819WS** (Schottky, 1 A) → 5V-Pin → LDO **ME6217C33** (800 mA). Die Diode verhindert, dass der Akku auf VBUS zurückspeist. Sie liegt nicht im Servopfad.
- **Kein Lader, kein BAT-Pad, keine Power-LED.** Nur WS2812 an GPIO8. Kein Konflikt mit unserem Lader, kein Dauerverbrauch durch LEDs.
- Chip-Antenne am Ende gegenüber USB-C.

Maße laut Waveshare-DXF: Board 18,00 × 23,50 mm, Reihenabstand 15,24 mm (6 × 2,54), Pinraster 2,54, erster Pin 1,59 mm von der USB-C-Kante. Die Bohrungen sitzen 1,38 mm innerhalb der Board-Kante, die Pads reichen bis an die Kante.

Die Variante **-M** hat die Stiftleisten schon eingelötet. Die ohne -M kommt mit losen Leisten, die die Teilnehmer selbst anlöten (+18 Lötstellen). Entscheidung bei Gregor.

Footprint als eigene Bibliothek im Projekt (2 × 1×9 Buchsenleisten).

## 6. Stückliste

### 6.1 SMD, von JLCPCB bestückt

Lager, Preise und Basic/Extended am 8. Oktober 2026 live bei JLCPCB geprüft. Vor der Bestellung erneut prüfen.

| Ref | Bauteil | Package | LCSC | Typ |
|---|---|---|---|---|
| U1 | TP4056-42-ESOP8 | ESOP-8 | C16581 | Preferred |
| U2 | DW01A | SOT-23-6 | C2927799 | Extended |
| Q2, Q6 | FS8205A (Fuxinsemi) | SOT-23-6 | C908265 | Extended |
| U3 | LM66100DCKR (TI) | SC-70-6 | C2869734 | Extended |
| U5 | INA226AIDGSR (TI) | VSSOP-10 | C49851 | Extended |
| U6 | TPS61023DRLR (TI) | SOT-563 | C919459 | Extended |
| L1 | MWSA0402S-1R0MT, 1 µH, 7 A | 4,4 × 4,2 mm | C408332 | Extended |
| R15 | 10 mΩ 1 %, 1 W | 1206 | C105362 | Extended |
| Q1, Q7, Q5 | AO3401A | SOT-23 | C15127 | Basic |
| C10–C14 | 22 µF 25 V X5R | 0805 | C45783 | Basic |
| C2, C3 | 4,7 µF | 0805 | C1779 | Basic |
| C5 | 10 µF | 0805 | C15850 | Basic |
| C1, C4, C6, C15 | 100 nF | 0603 | C14663 | Basic |
| C7 | 220 pF | 0603 | C1603 | Basic |
| R8 | 750 kΩ | 0603 | C23240 | Preferred |
| R9, R10 | 100 kΩ | 0603 | C25803 | Basic |
| R1 | 10 kΩ | 0603 | C25804 | Basic |
| R21, R22 | 4,7 kΩ | 0603 | C23162 | Basic |
| R4 | 5,1 kΩ | 0603 | C23186 | Basic |
| R3, R5, R18–R20 | 1 kΩ | 0603 | C21190 | Basic |
| R13, R14, R16, R17 | 220 Ω | 0603 | C22962 | Basic |
| R2 | 100 Ω | 0603 | C22775 | Basic |
| R7 | 1 MΩ | 0603 | C22935 | Basic |
| D1 | LED rot | 0603 | C2286 | Basic |

7 Extended-Typen, je ~3 $ Rüstgebühr pro Bestellung. Für Zellschutz, ideale Diode, Strommessung und einen Boost dieser Leistung gibt es bei JLC keine Basic-Teile.

### 6.2 THT, Kit für die Teilnehmer (nicht bestückt)

| Ref | Bauteil | Bemerkung |
|---|---|---|
| J1 | JST B2B-PH-K-S, 2-pol, stehend (C131337) | Akku. Liegend: S2B-PH-K-S (C173752). Polarität groß auf Silkscreen |
| U4 | 2 × Buchsenleiste 1×9, 2,54 mm | für Waveshare ESP32-C6-Zero |
| J2, J3, J5, J6 | 4 × Stiftleiste 1×3 | Servos |
| J7–J9 | 3 × Stiftleiste 1×3 | Analog |
| J10, J11 | 2 × Stiftleiste 1×4 | I²C |
| J4 | Stiftleiste 1×7 | Display-Kabel |
| SW1 | Schiebeschalter THT, rechtwinklig | Hebel muss durch die Gehäusewand reichen; Bauform mit Gregor abstimmen |

## 7. Firmware-Anpassungen (separate Aufgabe, nach der Platine)

- `src/config.h`: `PIN_TFT_DC` 6 → 20, `PIN_TFT_CS` 7 → 21; Servos 19, 18, 16, 17; `SERVO_EN` 15; I²C SDA 14, SCL 22; Analog 0, 1, 2. Falls es noch Roboter mit dem alten Board gibt: zweites PlatformIO-Environment statt die alten Pins zu überschreiben.
- Seriell nur über USB (GPIO16/17 sind Servos).
- INA226 an 0x45: Shunt 10 mΩ, Kalibrierung für ±8 A (Current_LSB 0,25 mA). Akkuspannung = Bus-Spannung. Strom < 0 = lädt. Ladung zählen für eine Prozentanzeige.
- Ladezustand im Gesicht anzeigen (statt CHRG-Pin aus Rev 0.1).
- SERVO_EN (GPIO15): nur beim Fahren High. Im Stand (`SERVO_IDLE_MS`), bei Unterspannung und vor dem Deep Sleep Low. Beim Boot zuerst Low setzen. Ohne Zelle (VBAT nicht plausibel) Servos nicht einschalten.
- Unter 3,6 V: Warnung im Gesicht. Unter 3,5 V: Servos abschalten, Hinweis "Bitte laden" anzeigen, Deep Sleep. Die Schwellen liegen bewusst höher, weil der LDO des ESP-Boards bei 3,4 V unter WiFi-Last schon Brownouts liefern kann.
- Servo-Rampe: Pulse über ca. 150–200 ms hochfahren statt springen (halbiert grob die Stromspitzen). Möglichst nicht alle 4 Servos gleichzeitig anfahren.
- Hinweis: `WiFi.setSleep(false)` kostet Laufzeit; bewusst entscheiden.

## 8. Layout-Regeln

- Zwei Lagen, durchgehende GND-Fläche unten.
- Kontur: Innenseite der Hülle über der Bodenplatte, 0,5 mm Luft, Herleitung in `hardware/powerboard/tools/gen_pcb.py`. Passungskontrolle mit `tools/render_fit.py`.
- **Leistungsblock vorne, fest vorverdrahtet** (nicht dem Autorouter überlassen): 5-V-Schiene hinter den Servo-Leisten, Boost-Zelle, Shunt, Verpolschutz, J1, Zellschutz. Kupfer in `POWER_TRACKS` in `gen_pcb.py`. Der Autorouter macht nur Signale und Kleinstrom (Lader, ESP-Versorgung, Messleitungen).
- Stiftleisten ein Stück vom Rand nach innen; Display-Leiste ungefähr mittig auf der Displayachse, hinter dem Leistungsblock (Kabel zum Display).
- Strompfade `J1` → Q1/Q7 → Shunt → `BAT+` → L1/U6 → `V5_SERVO` → Servos, `BAT+` → Q5 → LM66100 → `VSYS` sowie `BATN` → FS8205A → `GND`: breite Leiterbahnen (≥ 0,8 mm, Boost-Pfad ≥ 1,2 mm) bzw. Flächen.
- Boost: Schleife VIN-Kondensator, L1, SW, VOUT-Kondensator, GND so klein wie möglich, nach TPS61023-Layoutbeispiel. Weg vom Antennenende des ESP.
- Shunt mit Kelvin-Anschluss an INA226 IN+/IN−.
- Servo-Masse und `V5_SERVO` sternförmig von den Ausgangskondensatoren, nicht durch den ESP-Bereich.
- DW01-CS-Leitung kurz und direkt an den FS8205A abgreifen.
- SMD-Teile dürfen **unter dem gesteckten ESP-Board** liegen (Buchsenleisten ca. 8,5 mm hoch). Die Pads auf der Unterseite des C6-Zero liegen dann direkt über der Trägerplatine: dort keine hohen Bauteile.
- **Antennenbereich des C6-Zero** (Ende gegenüber USB-C) nicht mit Kupfer unterlegen.
- USB-C an der einen hinteren Schräge, Schalter und Lade-LED an der anderen. Öffnungen in der Hülle: `hardware/powerboard/README.md`.
- J1-Pads: ausreichend Abstand, keine Leiterbahn zwischen den beiden Pins.
- Silkscreen: Polarität am Akku groß, Port-Belegungen, "SERVO 5V" / "3V3", Testpunkte, Projektname/Version, KidsLab.
- 2 Befestigungslöcher M2, Lage nach Bodenplatte.

## 9. Offene Punkte

1. ESP-Board: Variante mit oder ohne eingelötete Leisten (-M). Maße stehen laut Waveshare-DXF fest (Abschnitt 5).
2. Hülle: Akkuwiege für den Zylinder entfernen (kollidiert mit dem ESP), Halter für den Pouch-Akku im Kopf, Öffnungen für USB-C, Schalter und LED. USB-C endet ~1,25 mm hinter der Außenfläche; bei Bedarf die Wand innen ausdünnen.
3. Schalter-Bauform (rechtwinklig/stehend, Hebellänge).
4. Befestigung der Platine auf der Bodenplatte (H1/H2 sind frei gesetzt).
5. Display-Kabel: Länge und Stecker.

## 10. Arbeitsablauf für Claude Code

1. Offene Punkte (Abschnitt 9) mit Gregor klären.
2. Schaltplan aus `tools/gen_sch.py` erzeugen, `kicad-cli sch erc` ohne Meldungen.
3. Netzliste gegen Tabelle 3.1 und Abschnitt 4 prüfen (insbesondere: `BATN` nur an J1 Pin 2, DW01 VSS, FS8205A, R1, C1; Servo-Plus nur an `V5_SERVO`).
4. Platine aus `tools/gen_pcb.py`, Routing mit `tools/route.py` (Freerouting + `maze.py`, Ablauf in `hardware/powerboard/README.md`); danach `kicad-cli pcb drc`.
5. JLCPCB-Export mit `tools/export_jlc.py` nach `hardware/powerboard/fertigung/`: Gerber + Bohrdaten, BOM (Comment, Designator, Footprint, LCSC) und CPL (Designator, Mid X, Mid Y, Layer, Rotation). Rotationen der SOT-Teile im JLC-Vorschau-Viewer kontrollieren.
6. `README.md` im Hardware-Ordner: Aufbau, Kit-Liste, Lötreihenfolge für Kinder, **Prüfschritt vor dem ersten Akkuanschluss**:
   1. Ohne Zelle, ohne USB, Durchgangsprüfer: **direkt über die beiden J1-Pins** kein Kurzschluss. Außerdem TP_BAT+ ↔ TP_GND, TP_VSYS ↔ TP_GND, TP_V5_SERVO ↔ TP_GND, TP_3V3 ↔ TP_GND: kein Kurzschluss.
   2. USB anstecken (noch ohne Zelle): TP_VSYS ≈ 4,7–5 V, TP_3V3 ≈ 3,3 V. **USB wieder abziehen.**
   3. Schalter AUS, Zelle anstecken.
   4. USB anstecken: Das gibt den DW01 frei, die LED leuchtet rot (lädt), TP_BAT+ zeigt die Zellspannung.

## 11. Sicherheitshinweise für die Doku

- Recycelte Zellen vor Einbau prüfen: Ruhespannung < 2,5 V → verwerfen; Beulen, Aufblähen, beschädigte Folie → verwerfen; nach Vollladung 24–48 h liegen lassen, deutlicher Spannungsabfall → verwerfen; geprüfte Zellen beschriften.
- Erste Ladung jeder recycelten Zelle beaufsichtigt, auf nicht brennbarer Unterlage.
- Nur Li-Ion/LiPo 3,7 V, keine LiFePO4.
- Beim Löten nie eine Zelle angesteckt. **J1 vor dem ersten Anstecken auf Kurzschluss prüfen.**
