# OrthoDok-Mapping

Quelle: `TemplateOrthoDok Knie ges. 2008- Jan 2026.xlsx`

## Gelesene Blaetter

- `OrthoDok Knie ges.`: 20.066 Zeilen, 153 Spalten. Dieses Blatt ist die aktuelle Importquelle.
- `3.Teilprae`: 8.229 Zeilen, 24 Spalten. Praeoperative Scores, spaeter als separates Modul sinnvoll.
- `prae_unbearbeitet`: 6.499 Zeilen, 26 Spalten. Unbearbeitete praeoperative Daten, spaeter als Staging-Quelle sinnvoll.

## Normalisierte Kernzuordnung

| Excel-Spalte | Zieltabelle | Zielfeld |
| --- | --- | --- |
| Patient | tblPatient | PatientenzahlSAP oder PatientHash |
| Nachname | tblPatient | Nachname |
| Vorname | tblPatient | Vorname |
| Geburtsdatum | tblPatient | Geburtsdatum, Geburtsjahr |
| Geschlecht | tblPatient | Geschlecht |
| OP Seite | tblGelenkFall | Seite |
| OP Datum | tblGelenkFall/tblEingriff | PrimaerimplantationDatum, OPDatum |
| Fall | tblAufenthalt | Fallnummer oder FallHash |
| Aufnehmende fachl.OE | tblAufenthalt | Station |
| Medizinischer Fall | tblAufenthalt | MedizinischerFall |
| Version | tblEingriff | EingriffsartTextQuelle |
| Version | lkpEingriffsart/tblEingriff | EingriffsartID, falls ableitbar |
| System - Textfeld | tblOrthodokOP | ImplantatSystem |
| Femur - Groesse | tblOrthodokOP | FemurGroesse |
| Femur - Typ | tblOrthodokOP | FemurTyp |
| Femur - zementiert | tblOrthodokOP | FemurZementiert/Fixation |
| Tibia - Groesse | tblOrthodokOP | TibiaGroesse |
| Tibia - Typ | tblOrthodokOP | TibiaTyp |
| Tibia - zementiert | tblOrthodokOP | TibiaZementiert/Fixation |
| Patella - Ersatz | tblOrthodokOP | PatellaErsatz |
| Patella - Groesse | tblOrthodokOP | PatellaGroesse |
| Patella - zementiert | tblOrthodokOP | PatellaZementiert/Fixation |
| Gleitflaeche - Groesse | tblOrthodokOP | GleitflaecheGroesse |
| Gleitflaeche - Typ | tblOrthodokOP | GleitflaecheTyp |
| Zugaenge-* | tblOrthodokOP | Zugang |
| Achsenbestimmung Femur-* | tblOrthodokOP | Navigation |
| Ortho: Esmarchsche Blutsperre - Dauer | tblOrthodokOP | BlutsperreDauer |
| Ortho: Esmarchsche Blutsperre - Druck | tblOrthodokOP | BlutsperreDruck |

## Rohdatenprinzip

Jede importierte Excel-Zeile wird zusaetzlich als JSON in `tblRawOrthodok` abgelegt. So bleiben alle 153 Spalten auditierbar, auch wenn nur ein Teil direkt in normalisierte Felder geschrieben wird.

Ohne `--include-identifiers` werden direkte Identifikatoren in den Rohdaten maskiert.

## Naechste Mapping-Schritte

- Operateur, Assistenz, OP-Dauer, Blutverlust und Anaesthesie aus weiteren OrthoDok-Exporten oder SAP-Exporten zuordnen, falls sie nicht im aktuellen Knie-Hauptblatt enthalten sind.
- Revisionen/DAIR/Spacer anhand der tatsaechlichen `Version`-Werte und ggf. Diagnose-/Interventionsfelder feiner klassifizieren.
- Praeoperative Scores aus `3.Teilprae` und `prae_unbearbeitet` in ein separates Score-Modul importieren.
