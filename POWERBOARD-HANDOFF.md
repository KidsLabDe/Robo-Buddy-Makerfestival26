# Handoff: Robo-Buddy Power-Trägerplatine (KiCad)

Auftrag für Claude Code. Ziel ist ein bestellfertiges KiCad-Projekt (Schaltplan + Platine) für eine Trägerplatine, die den MF26 Robo-Buddy akkubetrieben macht. Gefertigt wird bei JLCPCB (alternativ PCBWay).

Auftraggeber: Gregor (KidsLab). Die Platinen werden in Workshops von Kindern/Jugendlichen fertig gelötet. Sicherheit des Akkuteils hat Vorrang vor allem anderen.

---

## 1. Fertigungskonzept

- **JLCPCB bestückt nur SMD, nur Oberseite.** Alles, was mit dem Akku zu tun hat, wird maschinell gelötet, **einschließlich der Akku-Buchse J_BAT** (SMD-JST-PH). Grund: JST-PH hat 2,0 mm Raster, und eine Lötbrücke zwischen den beiden Akku-Pins liegt vor der Schutzschaltung, wäre also ein ungeschützter Zellkurzschluss.
- **Die Teilnehmer löten nur THT im 2,54-mm-Raster:** Buchsenleisten für den ESP, Servo-Stiftleisten, Display-Leiste, Schiebeschalter. Ziel: ca. 30 Lötstellen pro Platine.
- THT-Teile stehen in der JLCPCB-BOM **nicht** (bzw. als DNP); dafür gibt es eine separate Kit-Stückliste.
- Erst Prototyp (5–10 bestückte Platinen), dann Serie (50 Stück) nach Revision.

## 2. Rahmenbedingungen

- Roboter: ca. 60 × 60 mm Außenmaß, zwei 9g-Continuous-Servos (Tower-Pro-Klone) nebeneinander, rundes GC9A01-Display vorne.
- Zelle: 1S Li-Ion/LiPo, ca. 40 × 20 mm, 300–500 mAh. Teilweise recycelte Vape-Zellen, **oft ohne eigene Schutzschaltung**. Die Platine muss den Schutz vollständig selbst leisten.
- MCU: **Waveshare ESP32-C6-Zero** (Original, nicht Klon), gesteckt auf Buchsenleisten (tauschbar). Details in Abschnitt 5. Firmware: https://github.com/MakeYourSchool/Robo-Buddy-Makerfestival26 (PlatformIO, pioarduino, Pins in `src/config.h`).
- Ein einziger USB-C-Port nach außen: der des ESP-Boards. Darüber wird geflasht **und** geladen.
- **Die Servos laufen nur mit eingesteckter Zelle**, auch an USB. Bewusste Entscheidung: Servostrom fließt so nie über USB und den 5V-Pin des ESP-Boards (siehe 3.2, Servo-Schiene).
- Zielgröße Platine: ca. **45 × 30 mm**, 2 Lagen, 1,6 mm. Endgültige Kontur kommt von Gregor (siehe Abschnitt 9).

## 3. Schaltungskonzept

```
USB-C (C6-Zero) ─► B5819WS ─► 5V-Pin = VSYS ─┬──► TP4054 VCC          (Lader)
                                             └──◄ LM66100 VOUT        (ideale Diode, Power Path, nur ESP)
                                                      ▲ VIN = BAT_SW
                                                      Q5 AO3401A (Ein/Aus, Gate über SW1)
                                                      ▲
J_BAT+ ─► Q1 AO3401A (Verpolschutz) ─► BAT+ ─┼────────┘
                                             ├──► TP4054 BAT
                                             ├──► DW01A VDD (über 100 Ω)
                                             ├──► Teiler 470k/470k ─► GPIO0
                                             └──► Q3 AO3401A (High-Side, GPIO2) ─► VSERVO ─► Servos +
J_BAT− = BATN ─► FS8205A (2× N-FET, low side) ─► GND
SW1 schaltet das Gate von Q5 (kein Laststrom über den Schalter); LM66100 CE fest auf GND
```

Verhalten, das die Schaltung garantieren muss:

| Zustand | Verhalten |
|---|---|
| USB an, Schalter egal | ESP läuft aus USB. LM66100 sperrt (VOUT > VIN). TP4054 lädt die Zelle. Servos laufen aus der Zelle, solange die Firmware VSERVO einschaltet; im Stand ist VSERVO aus, dann lädt die Zelle ohne Last und das Ladeende wird sauber erkannt. |
| USB aus, Schalter EIN | Zelle speist über LM66100 auf VSYS (ESP) und über Q3 auf VSERVO. TP4054 schläft (VCC < BAT). |
| USB aus, Schalter AUS | Q5 aus, ESP aus, Q3 per Pull-up aus. Verbrauch nur DW01 (~3 µA) + Teiler (~4 µA) + Leckströme. |
| USB an, aber schwach | VSYS fällt unter VBAT, LM66100 springt automatisch ein (nur bei Schalter EIN). Servo-Spitzen belasten USB nicht mehr. |
| Keine Zelle, USB an | ESP läuft, Servos bewegen sich nicht. Der TP4054 kann ohne Zelle an BAT+ eine pendelnde Spannung ausgeben; die Firmware darf sich darauf nicht verlassen. |
| Zelle verpolt eingesteckt | Q1 sperrt, kein Strompfad. |
| Zelle tiefentladen / Kurzschluss | DW01A + FS8205A trennen (2,4 V / Überstrom). Primärer Tiefentladeschutz ist aber die Firmware (Abschnitt 7). |

### 3.1 Netze

| Netz | Beschreibung |
|---|---|
| `VSYS` | 5V-Pin des C6-Zero (hinter dessen Schottky-Diode), TP4054 VCC, LM66100 VOUT. ≈ 4,7 V an USB, ≈ VBAT im Akkubetrieb. **Keine Servos.** |
| `VSERVO` | Servo +, hinter Q3. Nur aus der Zelle gespeist, von der Firmware geschaltet. |
| `SERVO_EN` | GPIO2 → Gate Q4 (2N7002). High = Servos an. |
| `3V3` | 3V3-Pin des C6-Zero (Ausgang des Onboard-LDO ME6217C33). Display, Lade-LED. |
| `GND` | Systemmasse = PACK− (hinter FS8205A). ESP-Board GND, Lader GND, alles andere. |
| `BAT+` | Zellplus hinter Verpolschutz Q1. |
| `BATN` | Zellminus direkt an J_BAT Pin 2 (DW01 VSS, FS8205A Source FET1). **Nicht** mit GND verbinden. |
| `J_BATP` | Zellplus am Stecker, vor Q1. |
| `BAT_SW` | Zwischen Q5 (Ein/Aus) und LM66100 VIN. |
| `SW_GATE` | Gate von Q5, 1 MΩ nach `BAT+`, SW1 nach GND. |
| `VBAT_SENSE` | Teiler-Mittelabgriff → GPIO0. |
| `CHRG_N` | TP4054 CHRG (open drain, low = lädt). |

### 3.2 Blöcke im Detail

**Verpolschutz (Q1, AO3401A, P-FET)**
- Drain = `J_BATP`, Source = `BAT+`, Gate = `BATN` über 10 kΩ.
- Bei richtiger Polung leitet zuerst die Body-Diode, dann schaltet der FET durch (Vgs ≈ −VBAT). Ladestrom fließt rückwärts durch den Kanal, das ist bei eingeschaltetem FET in Ordnung.
- Geprüft: Bei verpolter Zelle gibt es keinen geschlossenen Strompfad, der nicht über Q1 läuft (Vgs ≥ 0, Body-Diode sperrt). Alle Verbraucher hängen an `BAT+` oder `GND`, nur DW01 VSS und FS8205A hängen an `BATN`. Diese Eigenschaft beim Schaltplan erhalten.

**Schutz (U2 DW01A + Q2 FS8205A)**
- Standardbeschaltung laut DW01A-Datenblatt: VDD über 100 Ω an `BAT+`, 100 nF VDD–VSS, VSS = `BATN`, OD → Gate Entlade-FET, OC → Gate Lade-FET, CS über 1 kΩ (bzw. Datenblattwert) an `GND` (PACK−).
- FS8205A: gemeinsamer Drain intern, Source FET1 = `BATN`, Source FET2 = `GND`.
- **Pinbelegung beider Teile aus dem konkreten LCSC-Datenblatt übernehmen**, nicht aus generischen Symbolen. SOT-23-6-Belegungen der 8205-Varianten unterscheiden sich je nach Hersteller. Der 8205A ist meist TSSOP-8; dass C908265 wirklich SOT-23-6 ist, explizit prüfen.
- Hinweis für die Doku: Der DW01 startet nach dem ersten Anstecken einer Zelle evtl. im Schutzzustand. Einmal USB anstecken gibt ihn frei.

**Lader (U1, TP4054, SOT-23-5)**
- Pins (UMW-Version laut Datenblatt prüfen): 1 CHRG, 2 GND, 3 BAT, 4 VCC, 5 PROG.
- VCC = `VSYS`, BAT = `BAT+`, GND = `GND`.
- R_PROG = **5,1 kΩ** → ca. 200 mA (I = 1000 V / R_PROG). Passt für alle Zellen von 300–500 mAh. Formel im konkreten Datenblatt gegenprüfen.
- 4,7 µF an VCC, 4,7 µF an BAT (X5R, ≥ 10 V).
- CHRG: rote LED (0603) + 1 kΩ nach **`3V3`** (nicht VSYS); zusätzlich über 10 kΩ an GPIO1, Firmware nutzt den internen Pull-up. Weil LED und Pull-up dann am selben Potential hängen, glimmt die LED im Ruhezustand nicht und GPIO1 sieht nie mehr als 3,3 V. 3V3 ist beim Laden immer da, weil USB dann auch den ESP versorgt.
- Kein NTC/Zelltemperaturschutz: bewusst entschieden, nicht nötig.

**Power Path / Ein-Aus (U3, LM66100, SC-70-6)**
- VIN = `BAT+`, VOUT = `VSYS`, GND = `GND`, ST unbeschaltet (Testpad optional).
- **CE fest auf GND** (immer an, reine ideale Diode).
- Geklärt im Datenblatt (SLVSEZ9): Die CE-Schwelle ist **relativ zu VIN**. Aus erst bei V_CE − V_IN > 80 mV (max), an bei < −80 mV. Ein Pull-up nach VIN schaltet also **nicht sicher ab**: Der CE-Leckstrom (bis 610 nA) erzeugt am 1-MΩ-Pull-up bis zu 0,6 V Abfall, CE läge dann unter VIN und das Teil bliebe an. Eine Spannung über VIN gibt es im Akkubetrieb nicht. Deshalb schaltet ein separater P-FET.
- **Ein/Aus über Q5 (AO3401A):** Source = `BAT+`, Drain = `BAT_SW` = LM66100 VIN. Gate = `SW_GATE`: 1 MΩ nach `BAT+` (aus), SW1 zieht nach GND (an). Im Ein-Zustand fließen ~4 µA durch den Pull-up, im Aus-Zustand nichts. Die Body-Diode von Q5 zeigt von `BAT_SW` nach `BAT+`; Rückstrom von VSYS sperrt der LM66100.
- SW1 führt so nur µA. Ein kleiner THT-Schiebeschalter reicht.
- Trägt nur noch den ESP (WiFi-Spitzen ca. 350 mA), die 1,5 A Dauer reichen damit sicher.

**Servo-Schiene (Q3 AO3401A + Q4 2N7002)**
- Q3 P-FET High-Side: Source = `BAT+`, Drain = `VSERVO`. Gate über 100 kΩ nach `BAT+` (Servos aus, solange niemand zieht).
- Q4 N-FET: Drain über 10 kΩ an Gate Q3, Source = `GND`, Gate = `SERVO_EN` (GPIO2) mit 100 kΩ nach `GND`, damit Q3 beim Booten und bei stromlosem ESP sicher aus ist.
- Ein GPIO direkt am P-FET-Gate reicht nicht: 3,3 V gegen bis zu 4,2 V an der Source schaltet den AO3401A nicht sicher ab.
- **Einschaltstrom begrenzen:** Q3 schaltet in den 470-µF-Elko. Gate-RC (10 kΩ Serie + Richtwert 47 nF Gate–Source) für ca. 1 ms Rampe. Am Prototyp messen: Der DW01 darf beim Einschalten von VSERVO nicht auslösen.
- Q3 hängt nicht hinter SW1. Das ist gewollt: Bei Schalter AUS und ohne USB ist der ESP aus und Q3 per Pull-up aus; bei USB kann die Firmware die Servos aus der Zelle fahren.

**Pufferung**
- `VSERVO`: 470 µF / 6,3–10 V **SMD-Aluminium-Elko** (von JLC bestückt, damit niemand die Polung falsch lötet), nah an den Servo-Leisten.
- `VSYS`: 10 µF + 100 nF keramisch nah am 5V-Pin des ESP-Boards.

**Akkumessung**
- Teiler `BAT+` → 470 kΩ → `VBAT_SENSE` → 470 kΩ → `GND`, 100 nF an `VBAT_SENSE`.
- Hochohmig gewählt, damit im ausgeschalteten Zustand kaum Strom fließt und der ESP nicht über den GPIO rückgespeist wird.

**Servos**
- J_SERVO_L / J_SERVO_R: 1×3 Stiftleiste, Belegung **S, +, −** (Standard; Plus in der Mitte, ein verkehrt gesteckter Servo nimmt keinen Schaden).
- S über 220 Ω an GPIO19 (links) bzw. GPIO18 (rechts), + = `VSERVO`, − = `GND`.
- Silkscreen: "L" / "R" und "S + −" bzw. Kabelfarben.

**Display**
- J_DISP: 1×7 in der Reihenfolge des Moduls: **VCC, GND, SCL, SDA, DC, CS, RST**.
- VCC = `3V3`, SCL = GPIO4, SDA = GPIO5, **DC = GPIO20, CS = GPIO21**, RST = GPIO3. DC und CS weichen von `src/config.h` ab (dort 6/7), weil GPIO6/7 beim C6-Zero nur als Pads auf der Unterseite herauskommen; siehe Abschnitt 4 und 7.
- **Bevorzugt: Display direkt aufstecken** statt per Kabel. Buchsenleiste auf der Platine, das Modul steckt mit seiner Stiftleiste drauf. Weil das Display senkrecht nach vorne schaut und die Platine liegt, wird das in der Regel eine **gewinkelte** 1×7-Buchsenleiste an der Vorderkante. Damit legen Position und Höhe der Leiste fest, wo das Display im Gehäuse sitzt: Abstand Leiste ↔ Displaymitte am Modul nachmessen und mit dem Gehäuse abgleichen (Abschnitt 9). Falls die Geometrie nicht passt: Stiftleiste + kurzes Kabel als Rückfall.

**Testpunkte** (beschriftet, für den Prüfschritt im Workshop)
- TP_BAT+ , TP_GND, TP_VSYS, TP_VSERVO, TP_3V3.

## 4. GPIO-Belegung (ESP32-C6)

| GPIO | Funktion | Bemerkung |
|---|---|---|
| 0 | VBAT_SENSE (ADC1) | neu |
| 1 | CHRG_N (Input, Pull-up) | neu |
| 2 | SERVO_EN (Output, High = an) | neu |
| 3 | Display RST | wie bisher |
| 4 | Display SCK | wie bisher |
| 5 | Display MOSI | wie bisher |
| 18 | Servo rechts | wie bisher |
| 19 | Servo links | wie bisher |
| 20 | Display DC | **geändert** (bisher 6) |
| 21 | Display CS | **geändert** (bisher 7) |

Nicht verwenden: GPIO6, 7, 8, 9, 12, 13, 23 liegen beim C6-Zero nur als Pads auf der Unterseite (8 = WS2812, 9 = BOOT, 12/13 = USB). GPIO15 ist ein Strapping-Pin, GPIO16/17 (TX/RX) bleiben für die serielle Konsole frei. Reserve am Rand: GPIO14, 22.

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

Vor dem Footprint am gelieferten Board nachmessen: Reihenabstand (laut Zeichnung vermutlich 17,78 mm = 7 × 2,54, Randpins sind halbe Lötaugen), Pinraster, Abstand USB-C-Kante ↔ erster Pin, Board-Außenmaß.

Die Variante **-M** hat die Stiftleisten schon eingelötet. Die ohne -M kommt mit losen Leisten, die die Teilnehmer selbst anlöten (+18 Lötstellen). Entscheidung bei Gregor.

Footprint als eigene Bibliothek im Projekt anlegen (2 × 1×9 Buchsenleisten). USB-C muss über die Platinenkante hinausragen bzw. bündig sein.

## 6. Stückliste

### 6.1 SMD, von JLCPCB bestückt

LCSC-Nummern bei Bestellung erneut auf Lagerbestand und Basic/Extended prüfen. TP4054, DW01A, FS8205A und LM66100 sind voraussichtlich Extended Parts (Rüstgebühr je Typ), das ist eingeplant.

| Ref | Bauteil | Package | LCSC | Status |
|---|---|---|---|---|
| U1 | TP4054 (UMW) | SOT-23-5 | C668215 | geprüft |
| U2 | DW01A | SOT-23-6 | C2927799 | geprüft (Alternative zulässig) |
| Q2 | FS8205A (Fuxinsemi) | SOT-23-6 | C908265 | Package prüfen (s. 3.2) |
| U3 | LM66100DCKR (TI) | SC-70-6 | C2869734 | geprüft |
| Q1, Q3, Q5 | AO3401A | SOT-23 | C15127 | geprüft |
| Q4 | 2N7002 | SOT-23 | Basic Part | auswählen |
| J_BAT | JST-PH 2-pol, SMD, seitlicher Einstieg | SMD | – | auswählen; Polarität groß auf Silkscreen ("+" / "−") |
| C | 470 µF / 6,3–10 V Alu-Elko SMD | ca. 6,3 × 7,7 mm | – | auswählen |
| C | 4,7 µF, 10 µF, 100 nF, 47 nF X5R/X7R | 0603/0805 | Basic Parts | auswählen |
| R | 5,1k, 470k ×2, 1M, 100k ×2, 10k ×3, 1k ×2, 220 ×2, 100 | 0603 | Basic Parts | auswählen |
| LED | rot | 0603 | Basic Part | auswählen |

Bevorzugt Basic Parts (keine Zusatzgebühr pro Bauteiltyp).

### 6.2 THT, Kit für die Teilnehmer (nicht bestückt)

| Ref | Bauteil | Bemerkung |
|---|---|---|
| J_ESP | 2 × Buchsenleiste 1×9, 2,54 mm | für Waveshare ESP32-C6-Zero |
| J_SERVO_L/R | 2 × Stiftleiste 1×3, 2,54 mm | |
| J_DISP | Buchsenleiste 1×7, 2,54 mm, gewinkelt | Display direkt aufgesteckt (s. 3.2); Rückfall Stiftleiste + Kabel |
| SW1 | Schiebeschalter THT, rechtwinklig | Hebel muss durch die Gehäusewand reichen; Bauform mit Gregor abstimmen |

## 7. Firmware-Anpassungen (separate Aufgabe, nach der Platine)

- `src/config.h`: `PIN_TFT_DC` 6 → 20, `PIN_TFT_CS` 7 → 21; neue Pins für VBAT_SENSE (0), CHRG (1), SERVO_EN (2). Falls es noch Roboter mit dem alten Board gibt: zweites PlatformIO-Environment statt die alten Pins zu überschreiben.
- Akkuspannung: GPIO0 mit `analogReadMilliVolts()` lesen (nutzt die Kalibrierung; Dämpfung heißt unter IDF 5 `ADC_ATTEN_DB_12`), mehrfach mitteln, × 2 = VBAT.
- CHRG: GPIO1 mit Pull-up, LOW = lädt. Ladezustand im Gesicht anzeigen.
- SERVO_EN (GPIO2): nur beim Fahren High. Im Stand (`SERVO_IDLE_MS`), bei Unterspannung und vor dem Deep Sleep Low. Beim Boot zuerst Low setzen. Ohne Zelle (VBAT nicht plausibel) Servos nicht einschalten.
- Unter 3,6 V: Warnung im Gesicht. Unter 3,5 V: Servos abschalten (SERVO_EN low), Hinweis "Bitte laden" anzeigen, Deep Sleep. Die Schwellen liegen bewusst höher, weil der LDO des ESP-Boards bei 3,4 V unter WiFi-Last schon Brownouts liefern kann.
- Servo-Rampe: Pulse über ca. 150–200 ms hochfahren statt springen (halbiert grob die Stromspitzen).
- Hinweis: `WiFi.setSleep(false)` kostet Laufzeit; bewusst entscheiden.

## 8. Layout-Regeln

- Zwei Lagen, durchgehende GND-Fläche unten.
- Strompfade `J_BAT` → Q1 → `BAT+` → Q3 → `VSERVO` → Servos, `BAT+` → LM66100 → `VSYS` sowie `BATN` → FS8205A → `GND`: breite Leiterbahnen (≥ 0,8 mm) bzw. Flächen.
- Servo-Masse und `VSERVO` sternförmig vom Elko, nicht durch den ESP-Bereich.
- DW01-CS-Leitung kurz und direkt an der FS8205A abgreifen.
- SMD-Leistungsteil darf **unter dem gesteckten ESP-Board** liegen (Buchsenleisten ca. 8,5 mm hoch), das spart Fläche. Bauhöhe des Elkos beachten. Die Pads auf der Unterseite des C6-Zero liegen dann direkt über der Trägerplatine: dort keine hohen Bauteile.
- **Antennenbereich des C6-Zero** (Ende gegenüber USB-C) nicht mit Kupfer unterlegen.
- Alles Äußere an **einer Kante**: USB-C (ESP-Board), Schalter, Lade-LED. Anschlüsse nach innen (Akku, Servos) an der gegenüberliegenden Kante. Das aufgesteckte Display legt die Vorderkante fest; Lage mit dem Gehäuse abstimmen.
- J_BAT-Pads: ausreichend Abstand, keine Leiterbahn zwischen den beiden Pins.
- Silkscreen: Polarität am Akku groß, Servo-Belegung, Testpunkte, Projektname/Version, KidsLab.
- 2 Befestigungslöcher M2 oder M2,5, Lage nach Gehäuse.

## 9. Offene Punkte: bei Gregor erfragen, bevor das Layout beginnt

1. ESP-Board ist entschieden (Waveshare ESP32-C6-Zero). Offen: Maße am gelieferten Board nachmessen (Abschnitt 5), Variante mit oder ohne eingelötete Leisten (-M).
2. Platinenkontur und Einbaulage im Gehäuse, max. Bauhöhe, Lage der USB-C-Öffnung, Position des Schalters, Befestigung. Ideal: STEP/STL des Gehäuses.
3. Schalter-Bauform (rechtwinklig/stehend, Hebellänge).
4. Display: Welches Modul genau (Foto/Maße, Lage der Stiftleiste relativ zur Displaymitte)? Wo muss die Displaymitte relativ zur Platine sitzen, damit das direkte Aufstecken passt?

## 10. Arbeitsablauf für Claude Code

1. Abschnitt 9 klären (Gregor fragen), Footprint für den C6-Zero anlegen (Doku und Maße in `hardware/esp32-c6-zero/`).
2. KiCad-Projekt `hardware/powerboard/` im Repo anlegen.
3. Schaltplan nach Abschnitt 3 aufbauen, Symbole/Footprints aus den KiCad-Standardbibliotheken, Sonderteile mit LCSC-Datenblatt abgleichen. LCSC-Nummer als Feld `LCSC` an jedes SMD-Bauteil, THT-Teile mit Attribut "Exclude from BOM"/DNP für JLC.
4. `kicad-cli sch erc` ausführen, alle Fehler beheben oder begründen.
5. Netzliste gegen Tabelle 3.1 und Abschnitt 4 prüfen (insbesondere: `BATN` nur an J_BAT Pin 2, DW01 VSS, FS8205A; Servo-Plus nur an `VSERVO`, nicht an `VSYS`).
6. Platine: Kontur, Platzierung nach Abschnitt 8. Routing mit Gregor abstimmen; nach jedem Schritt `kicad-cli pcb drc`.
7. JLCPCB-Export: Gerber + Bohrdaten, BOM (Comment, Designator, Footprint, LCSC) und CPL (Designator, Mid X, Mid Y, Layer, Rotation). Rotationen der SOT-23-Teile im JLC-Vorschau-Viewer kontrollieren lassen.
8. Kurzes `README.md` im Hardware-Ordner: Aufbau, Kit-Liste, Lötreihenfolge für Kinder, **Prüfschritt vor dem ersten Akkuanschluss**:
   1. Ohne Zelle, ohne USB, Durchgangsprüfer: **direkt über die beiden J_BAT-Pins** kein Kurzschluss. Außerdem TP_BAT+ ↔ TP_GND, TP_VSYS ↔ TP_GND, TP_VSERVO ↔ TP_GND: kein Kurzschluss.
   2. USB anstecken (noch ohne Zelle): TP_VSYS ≈ 4,7–5 V, TP_3V3 ≈ 3,3 V. **USB wieder abziehen.**
   3. Schalter AUS, Zelle anstecken.
   4. USB anstecken: Das gibt den DW01 frei, die LED leuchtet rot (lädt), TP_BAT+ zeigt die Zellspannung.

## 11. Sicherheitshinweise für die Doku

- Recycelte Zellen vor Einbau prüfen: Ruhespannung < 2,5 V → verwerfen; Beulen, Aufblähen, beschädigte Folie → verwerfen; nach Vollladung 24–48 h liegen lassen, deutlicher Spannungsabfall → verwerfen; geprüfte Zellen beschriften.
- Erste Ladung jeder recycelten Zelle beaufsichtigt, auf nicht brennbarer Unterlage.
- Nur Li-Ion/LiPo 3,7 V, keine LiFePO4.
- Beim Löten nie eine Zelle angesteckt.
