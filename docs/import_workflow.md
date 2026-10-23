# Import-Workflow fuer echte Daten

## Grundprinzip

Jede Quelle wird zuerst roh gespeichert und erst danach normalisiert. Dadurch bleibt nachvollziehbar:

- aus welcher Datei ein Datensatz kommt
- wann der Import gelaufen ist
- welche Originalzeile zugrunde liegt
- ob eine Zeile schon einer Episode/einem Eingriff zugeordnet werden konnte

Direkt identifizierende Spalten wie Patientennummer, Fallnummer, Geburtsdatum, Adresse oder SVNR werden in den `RawJSON`-Feldern standardmaessig maskiert. Die Verknuepfung erfolgt trotzdem ueber Hashes bzw. bekannte Fallnummern. Nur wenn der echte Wert bewusst in der Datenbank gespeichert werden soll, wird `--include-identifiers` gesetzt.

## 1. Datei profilieren

Vor jedem neuen Import zuerst Spalten ansehen:

```bash
python3 scripts/profile_table_file.py "/pfad/zur/datei.xlsx"
```

Bei Excel mit bestimmtem Blatt:

```bash
python3 scripts/profile_table_file.py "/pfad/zur/datei.xlsx" --sheet "Tabelle1"
```

## 2. OrthoDok

OrthoDok liefert Primaer-/Revisionseingriffe, Implantate und OP-Technik. Der Import ist bereits vorhanden:

```bash
python3 scripts/import_orthodok.py "/pfad/orthodok.xlsx" --db outputs/pji_register_orthodok_pseudonymized.sqlite
```

## 3. Laborlisten

CRP, IL-6, Leukozyten usw. werden als separate Long-Table-Werte in `tblLaborWert` importiert.

Beispiel:

```bash
python3 scripts/import_labor.py "/pfad/crp.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --parameter CRP \
  --date-col "DokDatum" \
  --value-col "Wert" \
  --unit-col "Einheit" \
  --fall-col "Fall"
```

Wenn die Liste eine Einheit enthaelt:

```bash
--unit-col "Einheit"
```

Oder fest:

```bash
--unit "mg/L"
```

Gemischte Laborlisten koennen den Parameter aus einer Spalte uebernehmen:

```bash
--parameter-col "Leistung"
```

Mit `--skip-existing` werden identische Messwerte nicht doppelt als `tblLaborWert` angelegt. Die Rohzeile wird trotzdem gespeichert und auf den vorhandenen Laborwert verlinkt.

Wenn ein Quellcode fachlich einem bereits verwendeten Registerparameter entspricht, kann er beim Import gemappt werden:

```bash
--parameter-map "L-CRPN=CRP"
```

Bei Laborlisten, in denen der Kommentar nur der Laborname ist, kann die Dublettenpruefung den Kommentar ignorieren:

```bash
--skip-existing-ignore-comment
```

## 4. HYBASE

HYBASE wird roh in `tblRawHybaseImport` gespeichert. Wenn ein Eingriff oder eine Episode zuordenbar ist, entstehen zusaetzlich Eintraege in `tblMikrobiologie` und `tblAntibiogramm`.

Beispiel:

```bash
python3 scripts/import_hybase.py "/pfad/hybase.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --date-col "ORD_DATUM" \
  --material-col "ORD_MATERIAL" \
  --pathogen-col "RES_ERREGER" \
  --status-col "RES_STATUS" \
  --comment-col "RES_KOMMENTAR" \
  --fall-col "ORD_AUFNAHMENR"
```

Wenn HYBASE viele Antibiogramm-Spalten enthaelt, z.B. `AB_Rifampicin`, `GEN (Gentamicin)` oder `FOX (Cefoxitin)`, erkennt der Import diese Spalten automatisch und legt pro S/I/R/M-Wert eine Zeile in `tblAntibiogramm` an. `-` wird dabei standardmaessig nur im Rohimport gespeichert, aber nicht als normales Antibiogramm-Ergebnis uebernommen.

Mit `--skip-existing` werden bereits vorhandene HYBASE-Mikrobiologie- und Antibiogramm-Datensaetze exakt wiederverwendet. Das ist wichtig, wenn ein groesserer HYBASE-Export einen kleineren bereits importierten Export ueberlappt: Die neue Rohzeile wird gespeichert und auf den vorhandenen normalisierten Datensatz verlinkt, aber der wissenschaftliche Zieldatensatz wird nicht doppelt angelegt.

### Strukturierter HYBASE-Import fuer die Registerbasis

Fuer die wissenschaftliche Datenbasis gibt es zusaetzlich den strukturierten Import. Er interpretiert HYBASE nicht automatisch als PJI, sondern trennt:

- Laborauftrag
- Probe/Material
- Isolat/Befundzeile
- Antibiogramm im Long-Format

Die Ausgabe entsteht zuerst als pruefbarer Dateiordner. Die Original-Excel wird nicht veraendert:

```bash
python3 scripts/import_hybase_structured.py "/pfad/zur/quelldatei.xlsx" \
  --output-dir outputs/hybase_structured_2008_2023 \
  --no-database-import-xlsx
```

Fuer einen sicheren Probelauf:

```bash
python3 scripts/import_hybase_structured.py "/pfad/zur/quelldatei.xlsx" \
  --sheets Gewebe \
  --limit 500 \
  --output-dir /private/tmp/hybase_structured_gewebe_test
```

Wenn die Preview passt, kann zusaetzlich in SQLite geschrieben werden:

```bash
python3 scripts/import_hybase_structured.py "/pfad/zur/quelldatei.xlsx" \
  --output-dir outputs/hybase_structured_2008_2023 \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --write-db \
  --no-database-import-xlsx
```

Erwartete Ausgaben:

- `tblPatient.csv`
- `tblLaborauftrag.csv`
- `tblProbe.csv`
- `tblIsolat.csv`
- `tblAntibiogramm.csv`
- `quality_report.xlsx`
- `unmapped_materials.csv`
- `unmapped_organisms.csv`
- `unmapped_antibiotics.csv`

Wichtig: Die `AB_...`-Spalten sind Antibiogramme, keine verabreichten Medikamente. Tatsaechliche Antibiotikatherapie bleibt in der Fieberkurven-/AB-Gabe-Schicht.

## Aktuelle erste echte Imports

CRP:

```bash
python3 scripts/import_labor.py "/pfad/zur/quelldatei.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --parameter CRP \
  --date-col "DokDatum" \
  --time-col "Zeit" \
  --value-col "Wert" \
  --unit-col "Einheit" \
  --fall-col "Fall"
```

HYBASE:

```bash
python3 scripts/import_hybase.py "/pfad/zur/quelldatei.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --date-col "ORD_DATUM" \
  --material-col "ORD_MATERIAL" \
  --pathogen-col "RES_ERREGER" \
  --status-col "RES_STATUS" \
  --comment-col "RES_KOMMENTAR" \
  --fall-col "ORD_AUFNAHMENR"
```

HYBASE Original-S 2008-2024:

```bash
python3 scripts/import_hybase.py "/pfad/zur/quelldatei.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --sheet "HYBASE_EXPORT_2008-2023" \
  --date-col "ORD_DATUM" \
  --material-col "ORD_MATERIAL" \
  --pathogen-col "RES_ERREGER" \
  --status-col "RES_STATUS" \
  --comment-col "RES_KOMMENTAR" \
  --fall-col "ORD_AUFNAHMENR" \
  --patient-col "PAT_PATIENTENNR" \
  --skip-existing
```

Punktate:

```bash
python3 scripts/import_labor.py "/pfad/zur/quelldatei.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --parameter L-CRPNPU \
  --date-col "Datum" \
  --time-col "Zeit" \
  --value-col "Wert" \
  --unit-col "Einheit" \
  --fall-col "Fall" \
  --comment-col "Text" \
  --skip-existing
```

Die Dateien `L-IL6.XLSX`, `L-MNGP.XLSX`, `L-P-LEUK.XLSX`, `L-PULEUK.XLSX` und `L-SEGMPU.XLSX` verwenden `--date-col "DokDatum"`. `L-P-ERY.XLSX` verwendet wie `L-CRPNPU.XLSX` `--date-col "Datum"`.

Die Sammeldatei `Punktate_2022.XLSX` wird gemischt importiert:

```bash
python3 scripts/import_labor.py "/pfad/zur/quelldatei.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --parameter-col "Leistung" \
  --date-col "DokDatum" \
  --time-col "Zeit" \
  --value-col "Wert" \
  --unit-col "Einheit" \
  --fall-col "Fall" \
  --comment-col "Text" \
  --skip-existing
```

Serum-Labor `Neu_Lindner`:

```bash
python3 scripts/import_labor.py "/pfad/zur/quelldatei.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --parameter L-LEUKO \
  --date-col "DokDatum" \
  --time-col "Zeit" \
  --value-col "Wert" \
  --unit-col "Einheit" \
  --fall-col "Fall" \
  --comment-col "Text" \
  --skip-existing \
  --skip-existing-ignore-comment
```

Fuer `L-LYT.XLSX`, `L-MCH.XLSX`, `L-MCHC.XLSX`, `L-MCV.XLSX`, `L-MONOT.XLSX`, `L-RDW.XLSX` und `L-SEG-A.XLSX` wird `--date-col "Datum"` verwendet. Fuer `L-BASO.XLSX`, `L-BASOT.XLSX`, `L-CRPN.XLSX`, `L-EOST.XLSX`, `L-LEUKO.XLSX` und `L-SEGT.XLSX` wird `--date-col "DokDatum"` verwendet.

`L-CRPN.XLSX` wird als `CRP` importiert, damit die bereits vorhandene CRP-Liste nicht als neuer Parameter verdoppelt wird:

```bash
--parameter CRP --skip-existing --skip-existing-ignore-comment
```

Die Serum-Sammeldatei `2022.XLSX` wird gemischt importiert:

```bash
python3 scripts/import_labor.py "/pfad/zur/quelldatei.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --parameter-col "Leistung" \
  --parameter-map "L-CRPN=CRP" \
  --date-col "DokDatum" \
  --time-col "Zeit" \
  --value-col "Wert" \
  --unit-col "Einheit" \
  --fall-col "Fall" \
  --comment-col "Text" \
  --skip-existing \
  --skip-existing-ignore-comment
```

Serum-Labor `Alt_Lindner`:

Die Alt-Lindner-Dateien werden ebenfalls mit `--parameter-col "Leistung"` importiert, weil einzelne Dateinamen nicht exakt dem Laborcode entsprechen. Beispiel: `L-BASO.XLSX` enthaelt `L-BASO#` fuer absolute Basophile.

```bash
python3 scripts/import_labor.py "/pfad/zur/quelldatei.xlsx" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --parameter-col "Leistung" \
  --parameter-map "L-CRPN=CRP" \
  --date-col "DokDatum" \
  --time-col "Zeit" \
  --value-col "Wert" \
  --unit-col "Einheit" \
  --fall-col "Fall" \
  --comment-col "Text" \
  --skip-existing \
  --skip-existing-ignore-comment
```

Die aktuell importierten Alt-Lindner-Dateien verwenden alle `--date-col "DokDatum"`: `L-BASO.XLSX`, `L-BASOT.XLSX`, `L-CRPN.XLSX`, `L-HB.XLSX`, `L-LEUKO.XLSX`, `L-NEUT#.XLSX`, `L-SEG-A.XLSX`, `L-SEGT.XLSX`.

## 5. Histologie-PDFs

Histologie-PDFs werden als Dokumente in `tblHistologieDokument` gespeichert. Krenn-Score und PMN werden heuristisch aus dem Text extrahiert und muessen reviewt werden.

Einzelnes PDF:

```bash
python3 scripts/import_histologie_pdf.py "/pfad/histologie.pdf" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --episode-id 123
```

Ordner:

```bash
python3 scripts/import_histologie_pdf.py "/pfad/histologie_ordner" \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite
```

## Reihenfolge fuer den echten Aufbau

1. OrthoDok importieren oder aktualisieren.
2. PJI-Episoden fachlich pruefen/anlegen.
3. Laborlisten importieren.
4. HYBASE importieren.
5. Histologie-PDFs importieren.
6. Fieberkurven reviewen und Antibiotikatherapie bestaetigen.
