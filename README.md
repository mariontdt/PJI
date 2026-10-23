# PJI-Register

Lokaler Prototyp für ein wissenschaftliches Register zu Endoprothesen und periprothetischen Infektionen. Die Struktur ist eingriffszentriert: Patient -> Gelenkfall -> Aufenthalt -> Eingriff -> Module.

> Forschungsprototyp, nicht als Medizinprodukt oder für unmittelbare klinische Entscheidungen validiert. Dieses Repository enthält ausschließlich Quellcode und Konfiguration, keine Patienten- oder Registerdaten.

## Was schon angelegt ist

- `schema/pji_register_schema.sql`: normalisiertes SQLite-Schema mit deinen Tabellen und zusätzlichen Audit-/Review-Tabellen.
- `scripts/init_db.py`: erstellt eine leere Registerdatenbank.
- `scripts/import_orthodok.py`: importiert OrthoDok-Excel in Rohdaten-Staging und normalisiert Patient, Gelenkfall, Aufenthalt, Eingriff und OrthoDok-OP.
- `scripts/fever_curve_extract.py`: bereitet PDF-/Bild-Fieberkurven für den Review vor und erkennt Medikament-/Antibiotika-Kandidaten aus OCR-Text, sobald OCR verfügbar ist.
- `scripts/review_app.py`: lokale Review-Oberfläche für Fieberkurven, Kandidatenstatus und Studienmodul Antibiotika.
- `scripts/profile_table_file.py`: zeigt Spalten und Beispielzeilen neuer CSV/XLSX-Quellen.
- `scripts/import_labor.py`: importiert parametergetrennte Laborlisten wie CRP, IL-6, Leukozyten oder PCT.
- `scripts/import_hybase.py`: importiert HYBASE-Mikrobiologie und Antibiogramme.
- `scripts/import_histologie_pdf.py`: importiert Histologie-PDFs als Review-Dokumente und extrahiert Krenn/PMN-Hinweise.
- `data/antibiotics_lexicon.csv`: erste Antibiotika-/Medikamenten-Normalisierungsliste.
- `docs/orthodok_mapping.md`: aktuelle Zuordnung des Excel-Hauptblatts.
- `docs/feverkurven_workflow.md`: geplanter Review-Workflow für Fieberkurven.
- `docs/datenmodell_episode.md`: Zielmodell mit Patient -> GelenkFall -> Episode -> Aufenthalt -> Eingriff.
- `docs/import_workflow.md`: konkrete Befehle für OrthoDok, Laborlisten, HYBASE und Histologie-PDFs.
- `docs/dateneingabe_start.md`: praktischer Arbeitsstart mit App-Seiten, Statuslogik und Eingaberegeln.

## Schnellstart

Vorausgesetzt werden Python 3 sowie die in den Skripten verwendeten Pakete.

```bash
python3 --version
```

Leere Datenbank erstellen:

```bash
python3 scripts/init_db.py --db outputs/pji_register.sqlite
```

OrthoDok testweise importieren:

```bash
python3 scripts/import_orthodok.py "/pfad/zur/quelldatei.xlsx" --db outputs/pji_register.sqlite --limit 200
```

Vollimport:

```bash
python3 scripts/import_orthodok.py "/pfad/zur/quelldatei.xlsx" --db outputs/pji_register.sqlite
```

Direkte Identifikatoren werden standardmäßig nicht gespeichert. Für eine rein klinische Arbeitsdatenbank auf verschlüsseltem Laufwerk kann man sie bewusst einschalten:

```bash
python3 scripts/import_orthodok.py "/pfad/zur/quelldatei.xlsx" --db outputs/pji_register.sqlite --include-identifiers
```

Fieberkurve als Review-Paket vorbereiten:

```bash
python3 scripts/fever_curve_extract.py "/pfad/zur/fieberkurve.pdf" --out outputs/review_packets
```

Falls dieselbe Fieberkurve nach einer OCR-Verbesserung erneut verarbeitet wird:

```bash
python3 scripts/fever_curve_extract.py "/pfad/zur/fieberkurve.pdf" --out outputs/review_packets --db outputs/pji_register.sqlite --replace-existing
```

Review-Oberfläche starten:

```bash
python3 scripts/review_app.py --db outputs/pji_register_orthodok_pseudonymized.sqlite
```

In der Review-Oberfläche können Fieberkurven direkt als PDF/Bild hochgeladen oder über einen lokalen Dateipfad importiert werden. Nach dem Import wird automatisch OCR ausgeführt und der neue Review-Fall geöffnet.

Aktueller Arbeitsstart für die echte Dateneingabe:

```text
http://127.0.0.1:8766/dateneingabe
```

Von dort aus sind die wichtigsten Arbeitsseiten erreichbar:

- P1-Arbeitsliste: `http://127.0.0.1:8766/kollektiv?status=offen&priority=P1`
- Patientenliste: `http://127.0.0.1:8766/patienten`
- Review-Queue: `http://127.0.0.1:8766/`
- Fallakte: `http://127.0.0.1:8766/fallakte/<KollektivID>`

## Datenschutz-Design

Der Import erzeugt immer einen stabilen `PatientHash`. Ohne `--include-identifiers` werden Name, Vorname, SAP-Patientenzahl, Geburtsdatum und Fallnummer nicht in Klartext gespeichert. Für wissenschaftliche Analysen bleiben Geschlecht, Geburtsjahr, Gelenk, Seite, OP-Datum, Eingriffsart und OrthoDok-Details verfügbar.

Fieberkurven gelten als besonders sensible Quelle. Die Pipeline schreibt deshalb zunächst Kandidaten und Review-Status, nicht automatisch finale Antibiotika-Therapien. Bestätigte Therapien gehören danach in `tblStudienmodulAB` bzw. `tblAntibiotikaGabe`.

## Datenmodell

Das Zielmodell ist episodezentriert:

```text
Patient -> GelenkFall -> Episode -> Aufenthalt -> Eingriff
```

Antibiotikatherapie, Outcome und Follow-up hängen an der Episode. OrthoDok, Labor, Mikrobiologie, Antibiogramm und Histologie bleiben am Eingriff. Details stehen in `docs/datenmodell_episode.md`.
