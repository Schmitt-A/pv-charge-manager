# Funktionsplan

Stand: 2026-10-05. Eine Wallbox, eine Hausbatterie, ein Fahrzeug. Heizstab, Steckdosen, Wärmepumpe und weitere Ladepunkte sind nicht Teil des nächsten Bauabschnitts.

Produktnamen fremder Lösungen werden in diesem Repository nicht verwendet.

## Festlegung

- Gesteuert wird nur die Wallbox. Die Hausbatterie wird vollständig bewertet, in diesem Abschnitt aber nicht aktiv geschaltet.
- Strategie ist umschaltbar: nur PV-Prognose, oder PV-Prognose plus dynamischer Preis.
- Vorschau gilt für heute und morgen, jeweils bis Sonnenuntergang plus die dazwischenliegende Nacht.
- Voll ist wählbar und wird doppelt angezeigt: Plan-Ziel und theoretisches Voll.
- Die Autorechnung läuft immer. Ohne verbundenes Fahrzeug oder ohne aktiven Plan ist sie als Annahme aus dem hinterlegten Profil markiert.
- Unsichere Prognose wird als Band gezeigt: schlechter und guter Fall, daraus frühester und spätester Zeitpunkt.
- Wirkungsgrad von Wallbox und Auto, Mindestreserve, Nulleinspeisung und der Hinweis auf Tage unter der Mindestleistung gehören in diesen Abschnitt.
- Messwerte kommen nur aus Home-Assistant-Entitäten und Geräten. Es gibt keinen eigenen Gerätetreiber.
- Die Oberfläche ist responsive. Backup und Restore laufen über eine versionierte JSON-Datei.

## Datenquellen

Alle Eingänge sind bestehende Home-Assistant-Entitäten:

- Netzbezug und Einspeisung, Hauslast, PV-Leistung und PV-Energie je Quelle.
- Batterie-SOC, Lade- und Entladeleistung, maximale Ladeleistung, optional Batteriemodi.
- Prognose als Leistungs- oder Energiereihe, Preisreihe optional.
- Wallbox: Laden-Schalter, Stromsollwert, Verbindungsstatus, optional Phasen und Sitzungsenergie.
- Fahrzeug: SOC, optional Reichweite und Ladezustand.

Nicht vorhandene Entitäten werden `unavailable` und blockieren die zugehörige Steuerung. Es werden keine Werte aus einem fremden Konto oder einem eigenen Protokoll gelesen.

## Oberfläche

Bis das Panel steht, sind alle Werte normale Home-Assistant-Entitäten und damit in Lovelace nutzbar.

Das Panel ist eine eigene Sidebar-Ansicht und muss auf Telefon und Desktop funktionieren:

- Energiefluss mit Netz, PV, Haus, Batterie und Wallbox.
- Heute und morgen nebeneinander, auf schmalen Screens untereinander.
- Zeitpunkt bis Batterie voll und bis Auto voll, Plan-Ziel und theoretisches Voll, gutes und schlechtes Band.
- Prioritäts-SOC, Puffer und Mindestreserve als sichtbare Grenzen, nicht nur als Zahl.
- Planeditor für Abfahrt, Ziel und Wochenplan.
- Empfehlungen als Text: Überschuss ab Prioritäts-SOC, Entladung bis Puffergrenze, Nachtreserve.
- Backup herunterladen und JSON wieder einlesen.
- Touch-Ziele groß genug, keine feste Desktop-Breite, heller und dunkler Modus über das Home-Assistant-Theme.

Das Panel hält keinen eigenen Ladestand. Es liest und schreibt nur über die Integration.

## Backup

Details stehen in [BACKUP.md](BACKUP.md).

- Eine JSON-Datei mit `schema_version`.
- Enthalten sind Einstellungen, Pläne, Entitätszuordnung und gelernte Prognosekorrektur.
- Nicht enthalten sind Geheimnisse, Live-Werte und der aktuelle Wallbox-Sollwert.
- Ältere Schema-Versionen werden beim Import migriert.
- Neuere Schema-Versionen werden abgelehnt.
- Fehlende Entitäten bleiben als fehlend markiert und werden nicht gelöscht.

## Funktionen des nächsten Abschnitts

- Modus Aus, Intelligent, Sofort. Immer laden und Solaranteil 0 bis 100 Prozent.
- Ein Profil: Kapazität, Phasen, Mindeststrom, Maximalstrom, Maximalleistung, Wirkungsgrad Wallbox zu Fahrzeugbatterie.
- Ziel-SOC oder kWh, Abfahrt, ein Wochenplan, nächster Termin gilt.
- Strategie Prognose oder Prognose plus Preis. Ohne Preisreihe fällt sie auf Prognose zurück und markiert das.
- Durchgehender Block, oder günstigste Slots mit Pausen. Ohne Preis nur der Block.
- Spätes Laden 0 bis 120 Minuten vor Abfahrt.
- SOC zwischen Abfragen schätzen und als Schätzung markieren.
- Sitzungsenergie und PV-Anteil, sobald die Wallbox lädt.
- Mehrere PV-Vergütungen bleiben über die vorhandene Opportunitätskosten-Zuteilung erhalten.
- Export und Import der JSON-Sicherung, bevor das Panel existiert.

## Zwei-Tage-Vorschau

Getrennte Sensoren für heute und morgen. Morgen beginnt um Mitternacht.

- Ladbare Energie aus korrigierter Prognose, nach Hauslast, Mindestreserve und laufender Wallbox.
- Anteil für die Batterie bis Prioritäts-SOC, Rest fürs Fahrzeug.
- Zeitpunkt Batterie voll und Zeitpunkt Auto voll, jeweils für Plan-Ziel und theoretisches Maximum.
- Beide Ziele bleiben sichtbar.
- Wenn das Ziel an dem Tag nicht erreichbar ist: erreichbarer SOC statt einer Uhrzeit, plus fehlende kWh.
- Ohne verbundenes Auto: dieselben Werte, Attribut `Annahme`.
- Guter und schlechter Fall aus der historischen Prognoseabweichung, begrenzt. Sensoren zeigen frühesten und spätesten Zeitpunkt.
- Hinweis je Tag: Überschussladen möglich, nur kurz möglich, nie möglich. Nie möglich, wenn kein Slot die Mindestleistung erreicht.

## Speicher, nur gerechnet

- Energie bis Prioritäts-SOC, bis Plan-Ziel und bis Max-SOC.
- Zeit bis voll bei aktueller Ladeleistung und aus der Prognose.
- SOC bis Sonnenuntergang, Autonomiestunden, erwarteter Morgen-SOC im guten und schlechten Fall.
- Überschuss fürs Auto erst ab dem Prioritäts-SOC. Entladung der Hausbatterie nur bis zur Puffergrenze, als Empfehlung aus der Prognose.
- Nachtreserve als Empfehlung, nicht als Schreibbefehl.
- Roundtrip-Verlust, Standard 8 Prozent.
- Balancing-Erinnerung, Boost-Energie und Entladesperre nur als Vorschlag.

## Nulleinspeisung

Nulleinspeisung wird erkannt, wenn der Wechselrichter den Überschuss auf null regelt und PV, Hauslast und Batterieleistung trotzdem einen Überschuss ergeben. Die Rechnung nutzt dann diese Bilanz. Liegt sie nicht vor, bleibt der Netzbezug führend und ein Diagnosehinweis wird gesetzt.

## Abdeckung

Berücksichtigt:

- Modi, Immer laden, Solaranteil, Überschussladen mit Verzögerung und Override.
- Ladeplan, Wochenplan, spätes Laden, Preis als zuschaltbare Strategie.
- Batteriepriorität, Puffer, Boost, Entladesperre, Netzladung, Nachtreserve, Balancing, Max-SOC.
- Zwei-Tage-Vorschau, Band, Wirkungsgrad, Mindestreserve, Nulleinspeisung, Mindestleistungs-Hinweis.
- Entitäten als einzige Datenquelle, responsive Oberfläche, versioniertes JSON-Backup.

Bewusst nicht im nächsten Abschnitt:

- Heizstab, Wärmepumpe, schaltbare Steckdosen.
- Zweite Wallbox, Priorität zwischen Ladepunkten, Stromkreise, externe Leistungsgrenze.
- CO2-Optimierung.
- Hausoptimierer, der Batterie, Auto und Heizung selbst steuert.
- Fernzugriff und eigener Gerätekatalog.

Nur vorgemerkt, noch nicht geschaltet:

- Entladesperre, Netzladung, Boost und Puffer schreiben noch nicht an den Wechselrichter.
- Der Wallbox-Controller bekommt in diesem Abschnitt nur den bisherigen Überschussollwert.
- Das Panel folgt nach den Sensoren und dem Backup-Dienst.

Für eine Wallbox noch offen:

- Phasenwechsel 1/3, wenn die Wallbox das kann.
- Standort-Offset als kleiner Soll-Einspeisepuffer.
- Aufwachen des Autos und Reichweitensensor.
- Netzentgelte als Aufschlag, feste Zeitfensterpreise neben der dynamischen Preisreihe.
- Mehrere Hausbatterien als kapazitätsgewichteter Mittelwert.
- Ins Netz entladen als Batteriemodus.
- Statistik über die einzelne Sitzung hinaus.

## Abnahme

- Tests für fehlende Prognose, fehlenden Preis, fehlenden SOC und Nulleinspeisung ohne Bilanz.
- Unverbundenes Auto liefert Werte mit `Annahme`.
- Ein Tag unter der Mindestleistung setzt den Hinweis und keine Uhrzeit.
- Ein unerreichbares Ziel setzt den Planstatus auf nicht machbar und löst keine stille Netzladung aus.
- Wallbox-Steuerung bleibt aus, bis Laden-Schalter, Stromzahl und Verbindungsstatus gemappt sind.
- Ein Backup der Schema-Version 1 lässt sich nach einer späteren Migration wieder einlesen.
- Die Panel-Ansicht ist bei 360 Pixel Breite ohne horizontales Scrollen der Hauptspalte bedienbar.
