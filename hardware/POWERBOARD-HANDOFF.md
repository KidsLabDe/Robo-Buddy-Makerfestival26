# Handoff: Robo-Buddy Power-Trägerplatine (KiCad)

Auftrag für Claude Code. Ziel ist ein bestellfertiges KiCad-Projekt (Schaltplan + Platine) für eine Trägerplatine, die den MF26 Robo-Buddy akkubetrieben macht. Gefertigt wird bei JLCPCB (alternativ PCBWay).

Auftraggeber: Gregor (KidsLab). Die Platinen werden in Workshops von Kindern/Jugendlichen fertig gelötet. Sicherheit des Akkuteils hat Vorrang vor allem anderen.

---

## 1. Fertigungskonzept

- **JLCPCB bestückt nur SMD, nur Oberseite.** Alles, was mit dem Akku zu tun hat, wird maschinell gelötet.
- **Die Teilnehmer löten nur THT im 2,54-mm-Raster:** Buchsenleisten für den ESP, Servo-Stiftleisten, Display-Leiste, Akku-Buchse, Schiebeschalter. Ziel: ca. 30 Lötstellen pro Platine.
- THT-Teile stehen in der JLCPCB-BOM **nicht** (bzw. als DNP); dafür gibt es eine separate Kit-Stückliste.
- Erst Prototyp (5–10 bestückte Platinen), dann Serie (50 Stück) nach Revision.

## 2. Rahmenbedingungen

- Roboter: ca. 60 × 60 mm Außenmaß, zwei 9g-Continuous-Servos (Tower-Pro-Klone) nebeneinander, rundes GC9A01-Display vorne.
- Zelle: 1S Li-Ion/LiPo, ca. 40 × 20 mm, 300–500 mAh. Teilweise recycelte Vape-Zellen, **oft ohne eigene Schutzschaltung**. Die Platine muss den Schutz vollständig selbst leisten.
- MCU: **ESP32-C6 Super Mini**, gesteckt auf Buchsenleisten (tauschbar). Firmware: https://github.com/MakeYourSchool/Robo-Buddy-Makerfestival26 (PlatformIO, pioarduino, Pins in `src/config.h`).
- Ein einziger USB-C-Port nach außen: der des Super Mini. Darüber wird geflasht **und** geladen.
- Zielgröße Platine: ca. **45 × 30 mm**, 2 Lagen, 1,6 mm. Endgültige Kontur kommt von Gregor (siehe Abschnitt 9).

## 3. Schaltungskonzept

```
USB-C (Super Mini) ─► 5V-Pin = VSYS ─┬──► TP4054 VCC          (Lader)
                                     ├──► Servos + (über Elko gepuffert)
                                     └──◄ LM66100 VOUT        (ideale Diode, Power Path)
                                              ▲ VIN
J_BAT+ ─► Q1 AO3401A (Verpolschutz) ─► BAT+ ─┴──► TP4054 BAT
                                         ├──► DW01A VDD (über 100 Ω)
                                         └──► Teiler 470k/470k ─► GPIO0
J_BAT− = BATN ─► FS8205A (2× N-FET, low side) ─► GND
SW1 schaltet LM66100 CE (kein Laststrom über den Schalter)
```

Verhalten, das die Schaltung garantieren muss:

| Zustand | Verhalten |
|---|---|
| USB an, Schalter egal | ESP + Servos laufen aus USB. LM66100 sperrt (VOUT > VIN). TP4054 lädt die Zelle ohne Last, Ladeende wird sauber erkannt. |
| USB aus, Schalter EIN | Zelle speist über LM66100 auf VSYS. TP4054 schläft (VCC < BAT). |
| USB aus, Schalter AUS | LM66100 aus, Verbrauch nur DW01 (~3 µA) + Teiler (~4 µA). |
| USB an, aber schwach (Servo-Spitzen) | VSYS fällt unter VBAT, LM66100 springt automatisch ein. |
| Zelle verpolt eingesteckt | Q1 sperrt, kein Strompfad. |
| Zelle tiefentladen / Kurzschluss | DW01A + FS8205A trennen (2,4 V / Überstrom). Primärer Tiefentladeschutz ist aber die Firmware (Abschnitt 7). |

### 3.1 Netze

| Netz | Beschreibung |
|---|---|
| `VSYS` | Super Mini 5V-Pin, Servo +, TP4054 VCC, LM66100 VOUT. 4,7 V an USB, ≈ VBAT im Akkubetrieb. |
| `3V3` | Super Mini 3V3-Pin (Ausgang des Onboard-LDO). Nur für Display. |
| `GND` | Systemmasse = PACK− (hinter FS8205A). Super Mini GND, Lader GND, alles andere. |
| `BAT+` | Zellplus hinter Verpolschutz Q1. |
| `BATN` | Zellminus direkt an J_BAT Pin 2 (DW01 VSS, FS8205A Source FET1). **Nicht** mit GND verbinden. |
| `J_BATP` | Zellplus am Stecker, vor Q1. |
| `CE` | LM66100 Enable. |
| `VBAT_SENSE` | Teiler-Mittelabgriff → GPIO0. |
| `CHRG_N` | TP4054 CHRG (open drain, low = lädt). |

### 3.2 Blöcke im Detail

**Verpolschutz (Q1, AO3401A, P-FET)**
- Drain = `J_BATP`, Source = `BAT+`, Gate = `BATN` über 10 kΩ.
- Bei richtiger Polung leitet zuerst die Body-Diode, dann schaltet der FET durch (Vgs ≈ −VBAT). Ladestrom fließt rückwärts durch den Kanal, das ist bei eingeschaltetem FET in Ordnung.
- Prüfen: Bei verpolter Zelle darf es keinen geschlossenen Strompfad geben, der nicht über Q1 läuft. Alle Verbraucher hängen an `BAT+` oder `GND`, nur DW01 VSS und FS8205A hängen an `BATN`.

**Schutz (U2 DW01A + Q2 FS8205A)**
- Standardbeschaltung laut DW01A-Datenblatt: VDD über 100 Ω an `BAT+`, 100 nF VDD–VSS, VSS = `BATN`, OD → Gate Entlade-FET, OC → Gate Lade-FET, CS über 1 kΩ (bzw. Datenblattwert) an `GND` (PACK−).
- FS8205A: gemeinsamer Drain intern, Source FET1 = `BATN`, Source FET2 = `GND`.
- **Pinbelegung beider Teile aus dem konkreten LCSC-Datenblatt übernehmen**, nicht aus generischen Symbolen. SOT-23-6-Belegungen der 8205-Varianten unterscheiden sich je nach Hersteller.
- Hinweis für die Doku: Der DW01 startet nach dem ersten Anstecken einer Zelle evtl. im Schutzzustand. Einmal USB anstecken gibt ihn frei.

**Lader (U1, TP4054, SOT-23-5)**
- Pins (UMW-Version laut Datenblatt prüfen): 1 CHRG, 2 GND, 3 BAT, 4 VCC, 5 PROG.
- VCC = `VSYS`, BAT = `BAT+`, GND = `GND`.
- R_PROG = **5,1 kΩ** → ca. 200 mA (I = 1000 V / R_PROG). Passt für alle Zellen von 300–500 mAh. Formel im konkreten Datenblatt gegenprüfen.
- 4,7 µF an VCC, 4,7 µF an BAT (X5R, ≥ 10 V).
- CHRG: rote LED (0603) + 1 kΩ nach `VSYS`; zusätzlich über 10 kΩ an GPIO1 (Firmware nutzt internen Pull-up).

**Power Path / Ein-Aus (U3, LM66100, SC-70-6)**
- VIN = `BAT+`, VOUT = `VSYS`, GND = `GND`, ST unbeschaltet (Testpad optional).
- CE: 1 MΩ Pull-up nach VIN; SW1 zieht CE nach GND.
- Laut TI: CE > VIN = aus, CE < VIN = ein. **Schwellwerte im Datenblatt prüfen**, ob CE = VIN (über Pull-up) sicher als "aus" gilt; sonst Pull-up-Konzept anpassen.
- SW1 führt so nur µA. Ein kleiner THT-Schiebeschalter reicht.
- Max. 1,5 A Dauer, das reicht für zwei 9g-Servos mit Anlaufspitzen.

**VSYS-Pufferung**
- 470 µF / 6,3–10 V **SMD-Aluminium-Elko** (von JLC bestückt, damit niemand die Polung falsch lötet), nah an den Servo-Leisten.
- 10 µF + 100 nF keramisch nah am Super-Mini-5V-Pin.

**Akkumessung**
- Teiler `BAT+` → 470 kΩ → `VBAT_SENSE` → 470 kΩ → `GND`, 100 nF an `VBAT_SENSE`.
- Hochohmig gewählt, damit im ausgeschalteten Zustand kaum Strom fließt und der ESP nicht über den GPIO rückgespeist wird.

**Servos**
- J_SERVO_L / J_SERVO_R: 1×3 Stiftleiste, Belegung **S, +, −** (Standard; Plus in der Mitte, ein verkehrt gesteckter Servo nimmt keinen Schaden).
- S über 220 Ω an GPIO19 (links) bzw. GPIO18 (rechts), + = `VSYS`, − = `GND`.
- Silkscreen: "L" / "R" und "S + −" bzw. Kabelfarben.

**Display**
- J_DISP: 1×7 Stiftleiste in der Reihenfolge des Moduls: **VCC, GND, SCL, SDA, DC, CS, RST**.
- VCC = `3V3`, SCL = GPIO4, SDA = GPIO5, DC = GPIO6, CS = GPIO7, RST = GPIO3 (entspricht `src/config.h`).

**Testpunkte** (beschriftet, für den Prüfschritt im Workshop)
- TP_BAT+ , TP_GND, TP_VSYS, TP_3V3.

## 4. GPIO-Belegung (ESP32-C6)

| GPIO | Funktion | Bemerkung |
|---|---|---|
| 0 | VBAT_SENSE (ADC1) | neu |
| 1 | CHRG_N (Input, Pull-up) | neu |
| 3 | Display RST | wie bisher |
| 4 | Display SCK | wie bisher |
| 5 | Display MOSI | wie bisher |
| 6 | Display DC | wie bisher |
| 7 | Display CS | wie bisher |
| 18 | Servo rechts | wie bisher |
| 19 | Servo links | wie bisher |

GPIO8 (WS2812) und GPIO15 (LED) sind auf dem Super Mini belegt, nicht verwenden.

## 5. Super-Mini-Footprint: zuerst nachmessen

Es gibt mehrere ESP32-C6-Super-Mini-Varianten mit **unterschiedlicher Pinreihenfolge** (Quellen widersprechen sich). Manche haben zusätzlich einen BAT-Pin mit eigenem Onboard-Lader.

Bevor der Footprint entsteht:
1. Gregor nach Foto/Link des **tatsächlich verwendeten Boards** (Ober- und Unterseite) fragen.
2. Pinreihenfolge beider Reihen, Reihenabstand (vermutlich 15,24 mm) und Lage der USB-C-Buchse festhalten.
3. Falls ein BAT-Pin vorhanden ist: **nicht verbinden** (Pad ohne Netz), sonst arbeiten zwei Lader gegeneinander.

Footprint als eigene Bibliothek im Projekt anlegen (2 × 1×N Buchsenleisten). USB-C muss über die Platinenkante hinausragen bzw. bündig sein.

## 6. Stückliste

### 6.1 SMD, von JLCPCB bestückt

LCSC-Nummern bei Bestellung erneut auf Lagerbestand und Basic/Extended prüfen.

| Ref | Bauteil | Package | LCSC | Status |
|---|---|---|---|---|
| U1 | TP4054 (UMW) | SOT-23-5 | C668215 | geprüft |
| U2 | DW01A | SOT-23-6 | C2927799 | geprüft (Alternative zulässig) |
| Q2 | FS8205A (Fuxinsemi) | SOT-23-6 | C908265 | geprüft |
| U3 | LM66100DCKR (TI) | SC-70-6 | C2869734 | geprüft |
| Q1 | AO3401A | SOT-23 | C15127 | geprüft |
| C | 470 µF / 6,3–10 V Alu-Elko SMD | ca. 6,3 × 7,7 mm | – | auswählen |
| C | 4,7 µF, 10 µF, 100 nF X5R/X7R | 0603/0805 | Basic Parts | auswählen |
| R | 5,1k, 470k ×2, 1M, 10k ×2, 1k ×2, 220 ×2, 100 | 0603 | Basic Parts | auswählen |
| LED | rot | 0603 | Basic Part | auswählen |

Bevorzugt Basic Parts (keine Zusatzgebühr pro Bauteiltyp).

### 6.2 THT, Kit für die Teilnehmer (nicht bestückt)

| Ref | Bauteil | Bemerkung |
|---|---|---|
| J_ESP | 2 × Buchsenleiste 1×N, 2,54 mm | N je nach Super-Mini-Variante |
| J_SERVO_L/R | 2 × Stiftleiste 1×3, 2,54 mm | |
| J_DISP | Stiftleiste 1×7, 2,54 mm | oder Buchsenleiste, je nach Kabel |
| J_BAT | JST-PH 2-pol, THT | Polarität eindeutig auf Silkscreen ("+" / "−") |
| SW1 | Schiebeschalter THT, rechtwinklig | Hebel muss durch die Gehäusewand reichen; Bauform mit Gregor abstimmen |

## 7. Firmware-Anpassungen (separate Aufgabe, nach der Platine)

- Akkuspannung: GPIO0 lesen (mehrfach mitteln, 11-dB-Dämpfung), × 2 = VBAT.
- CHRG: GPIO1 mit Pull-up, LOW = lädt. Ladezustand im Gesicht anzeigen.
- Unter 3,5 V: Warnung im Gesicht. Unter 3,4 V: Servos abschalten, Hinweis "Bitte laden" anzeigen, Deep Sleep.
- Servo-Rampe: Pulse über ca. 150–200 ms hochfahren statt springen (halbiert grob die Stromspitzen, weniger Brownouts).
- Hinweis: `WiFi.setSleep(false)` kostet Laufzeit; bewusst entscheiden.

## 8. Layout-Regeln

- Zwei Lagen, durchgehende GND-Fläche unten.
- Strompfad `J_BAT` → Q1 → `BAT+` → LM66100 → `VSYS` → Servos sowie `BATN` → FS8205A → `GND`: breite Leiterbahnen (≥ 0,8 mm) bzw. Flächen.
- Servo-Masse und Servo-Plus sternförmig vom Elko, nicht durch den Super-Mini-Bereich.
- DW01-CS-Leitung kurz und direkt an der FS8205A abgreifen.
- SMD-Leistungsteil darf **unter dem gesteckten Super Mini** liegen (Buchsenleisten ca. 8,5 mm hoch), das spart Fläche. Bauhöhe des Elkos beachten.
- **Antennenbereich des Super Mini** (Ende gegenüber USB-C prüfen) nicht mit Kupfer unterlegen.
- Alles Äußere an **einer Kante**: USB-C (Super Mini), Schalter, Lade-LED. Anschlüsse nach innen (Akku, Servos, Display) an der gegenüberliegenden Kante.
- Silkscreen: Polarität am Akku groß, Servo-Belegung, Testpunkte, Projektname/Version, KidsLab.
- 2 Befestigungslöcher M2 oder M2,5, Lage nach Gehäuse.

## 9. Offene Punkte: bei Gregor erfragen, bevor das Layout beginnt

1. Foto/Link des verwendeten ESP32-C6 Super Mini (Pinreihenfolge, BAT-Pin ja/nein).
2. Platinenkontur und Einbaulage im Gehäuse, max. Bauhöhe, Lage der USB-C-Öffnung, Position des Schalters, Befestigung. Ideal: STEP/STL des Gehäuses.
3. Schalter-Bauform (rechtwinklig/stehend, Hebellänge).
4. Display: Stift- oder Buchsenleiste auf der Platine, Kabellänge.

## 10. Arbeitsablauf für Claude Code

1. Abschnitt 9 klären (Gregor fragen), Super-Mini-Footprint anlegen.
2. KiCad-Projekt `hardware/powerboard/` im Repo anlegen.
3. Schaltplan nach Abschnitt 3 aufbauen, Symbole/Footprints aus den KiCad-Standardbibliotheken, Sonderteile mit LCSC-Datenblatt abgleichen. LCSC-Nummer als Feld `LCSC` an jedes SMD-Bauteil, THT-Teile mit Attribut "Exclude from BOM"/DNP für JLC.
4. `kicad-cli sch erc` ausführen, alle Fehler beheben oder begründen.
5. Netzliste gegen Tabelle 3.1 und Abschnitt 4 prüfen (insbesondere: `BATN` nur an J_BAT Pin 2, DW01 VSS, FS8205A).
6. Platine: Kontur, Platzierung nach Abschnitt 8. Routing mit Gregor abstimmen; nach jedem Schritt `kicad-cli pcb drc`.
7. JLCPCB-Export: Gerber + Bohrdaten, BOM (Comment, Designator, Footprint, LCSC) und CPL (Designator, Mid X, Mid Y, Layer, Rotation). Rotationen der SOT-23-Teile im JLC-Vorschau-Viewer kontrollieren lassen.
8. Kurzes `README.md` im Hardware-Ordner: Aufbau, Kit-Liste, Lötreihenfolge für Kinder, **Prüfschritt vor dem ersten Akkuanschluss**:
   - Ohne Zelle, ohne USB: Durchgang TP_BAT+ ↔ TP_GND und TP_VSYS ↔ TP_GND messen: kein Kurzschluss.
   - Dann USB anstecken: TP_VSYS ≈ 4,7–5 V, TP_3V3 ≈ 3,3 V.
   - Erst dann Zelle anstecken, einmal USB-Laden starten (gibt den DW01 frei), LED leuchtet rot.

## 11. Sicherheitshinweise für die Doku

- Recycelte Zellen vor Einbau prüfen: Ruhespannung < 2,5 V → verwerfen; Beulen, Aufblähen, beschädigte Folie → verwerfen; nach Vollladung 24–48 h liegen lassen, deutlicher Spannungsabfall → verwerfen; geprüfte Zellen beschriften.
- Erste Ladung jeder recycelten Zelle beaufsichtigt, auf nicht brennbarer Unterlage.
- Nur Li-Ion/LiPo 3,7 V, keine LiFePO4.
- Beim Löten nie eine Zelle angesteckt.
