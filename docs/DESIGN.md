# Oberfläche

Stand: 2026-10-05. Gilt für das Panel und für die spätere Anordnung der Entitäten. Die Einrichtung der Entitäten bleibt das schrittweise Menü aus [CONFIGURATION.md](CONFIGURATION.md).

## Erste Ansicht

Oben steht ein Satz in Alltagssprache. Darunter der Energiefluss. Keine zweite Startseite, kein Dashboard aus Kacheln.

Beispiele für den Satz:

- „Überschuss geht ans Auto, sobald die Batterie 50 Prozent hat. Das ist heute gegen 14:30.“
- „Heute reicht die Sonne nicht für das Autoziel. Es fehlen 6 kWh.“
- „Die Wallbox startet heute nicht. Kein Zeitraum erreicht die Mindestleistung.“

Der Satz nennt die eine nächste Tatsache. Er wiederholt nicht alle Zahlen, die darunter stehen.

## Immer sichtbare Zahlen

Ohne Aufklappen und ohne Kurve:

- Ladestand der Hausbatterie
- heute ladbar
- morgen ladbar
- Uhrzeit, bis die Batterie voll ist
- Uhrzeit, bis das Auto das Ziel erreicht

Die Uhrzeit ist das Band: „zwischen 14:30 und 16:10“. Ein einzelner Mittelwert ohne Spanne wird nicht gezeigt. Wirkungsgrad, Opportunitätskosten und die Slotliste stehen in einer zweiten Zeile auf derselben Karte, kleiner, nicht auf einem eigenen Schirm.

Bezeichnungen auf der ersten Zeile sind Alltagssprache. Die Einheit steht dahinter: „Ladestand 62 Prozent“, in der zweiten Zeile „SOC 62 Prozent“. „Heute ladbar 18 kWh“, in der zweiten Zeile die Aufteilung Batterie und Auto.

Ein nicht verbundenes Auto bleibt sichtbar und ist mit „Annahme“ markiert.

## Energiefluss

Feste Farben, unabhängig von Hell und Dunkel:

| Strom | Farbe | Bedeutung |
| --- | --- | --- |
| PV | Amber `#E09F3E` | Erzeugung |
| Netz | Blau `#3D6BF5` | Bezug und Einspeisung |
| Haus | Grau `#8B909A` | Verbrauch |
| Batterie | Türkis `#1AAE9F` | Hausspeicher |
| Auto | Violett `#7A5AF8` | Wallbox |

Die Farbe allein trägt keine Information. Jeder Strang hat einen Namen und eine Wattzahl. Die Farbe ändert sich nicht, wenn der Zustand gut oder schlecht ist. Dafür ist der Satz oben zuständig.

Reihenfolge im Fluss: PV links, dann Haus, Batterie und Auto. Netz sitzt darunter, mit getrenntem Bezug und getrennter Einspeisung.

## Regler an der Zahl

Jede Zahl der Übersicht ist direkt änderbar. Es gibt keinen zweiten Einstellungsdialog für diese Werte.

Direkt an der Ansicht:

- Modus: Aus, Intelligent, Sofort
- Ziel des Autos und Abfahrt
- Priorität der Batterie, Puffer und Mindestreserve
- Solaranteil und Immer laden
- Strategie: nur Prognose, oder Prognose plus Preis

Bedienung über Schalter, Auswahl und Schrittweite, nicht über Ziehen im Fluss. Eine Änderung gilt sofort und der Satz oben wird neu formuliert.

Nicht an der Übersicht, weiter nur im Einrichtungsmenü:

- Zuordnung der Entitäten
- Verbindungstest und Datenvorschau
- JSON laden und speichern
- Freigabe der Wallbox-Steuerung

Die Freigabe bleibt dort, weil sie kein Betriebswert ist, sondern die Schreibberechtigung.

## Sprache

Deutsch. Erste Zeile ohne SOC, kWh-Aufteilung, Wirkungsgrad und Phasen. Diese Wörter stehen in der zweiten Zeile derselben Karte.

Hinweise beim Verbindungstest bleiben wörtlich: geladen, fehlt, veraltet, ungültig.

## Verhalten

- Eine Spalte unter 360 Pixel. Der Satz bleibt oben, der Fluss darunter, die Zahlen darunter.
- Helligkeit kommt vom Home-Assistant-Theme. Die fünf Stromfarben bleiben gleich.
- Kein Diagramm mit Achsen auf der ersten Ansicht.
- Leere oder fehlende Werte heißen „kein Wert“, nicht 0.
