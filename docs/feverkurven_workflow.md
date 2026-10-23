# Fieberkurven-Workflow

Ziel: PDF- oder Screenshot-Fieberkurven aus SAP so aufbereiten, dass Antibiotika und andere relevante Medikamente gefunden, aber erst nach menschlicher Kontrolle in die Studienfelder übernommen werden.

## Pipeline

1. Kollektiv aufbauen: HYBASE-positive, PJI-nahe Episoden werden als `tblFieberkurveKollektiv` gespeichert.
2. SAP-Arbeitsliste exportieren: Die Kollektivseite `/kollektiv` oder `outputs/fieberkurven_kollektiv_hybase_pji_nah_pos.csv` liefert die Abarbeitungsliste.
3. Quelle registrieren: PDF/Bild wird als `tblFieberkurve` angelegt und direkt mit Episode/Eingriff verknüpft.
4. Seiten erzeugen: PDF-Seiten werden lokal als PNG gerendert; Bilddateien werden direkt referenziert.
5. OCR: Wenn Tesseract oder eine andere OCR-Engine vorhanden ist, wird Text pro Seite erzeugt.
6. Kandidatenerkennung: Antibiotika-Suchbegriffe aus `data/antibiotics_lexicon.csv` werden im OCR-Text gesucht.
7. Review: Jeder Kandidat landet in `tblFieberkurveMedikamentKandidat` mit Status `offen`.
8. Bestätigung: Nur bestätigte Kandidaten werden als `tblAntibiotikaGabe` bzw. in `tblStudienmodulAB` übernommen.

## SAP-Arbeitsliste

Das aktuelle Kollektiv wird aus Episoden gebildet, die mindestens eine HYBASE-positive Kultur aus PJI-nahen Materialien haben: Gewebe, Implantat, Gelenkpunktat, Hüft-/Knieabstrich oder tiefer Wundabstrich. Die Arbeitsliste ist bewusst episode-basiert, damit mehrere positive Mikrobiologiezeilen nicht mehrfach als SAP-Aufgabe erscheinen.

Kollektiv neu aufbauen und CSV exportieren:

```bash
python3 scripts/build_fieberkurven_kollektiv.py \
  --db outputs/pji_register_orthodok_pseudonymized.sqlite \
  --export outputs/fieberkurven_kollektiv_hybase_pji_nah_pos.csv
```

Die Kollektivseite in der App:

```text
http://127.0.0.1:8765/kollektiv
```

Empfohlener manueller Ablauf:

1. In `/kollektiv` nach Priorität abarbeiten.
2. In SAP die Fieberkurve zum angezeigten Patient-/Fall-/OP-Kontext suchen.
3. Screenshot mit dem vorgeschlagenen Dateinamen speichern.
4. Den lokalen Screenshot-Pfad in der Zeile einfügen und `Pfad importieren` klicken.
5. In der Review-Ansicht Antibiotika/Medikamente bestätigen oder manuell ergänzen.

## Warum Review zwingend ist

Fieberkurven wie das Beispielbild enthalten gedruckte Raster, Handschrift, Abkürzungen und Tagesmarkierungen. Gerade die Zuordnung von Medikament, Dosis, Gabezeit und Datum ist deshalb fehleranfällig. Automatisierung soll den Arbeitsaufwand reduzieren, nicht die medizinische Bewertung ersetzen.

## Aktueller lokaler Status

In dieser Umgebung ist `pdftoppm` in den gebündelten Codex-Abhängigkeiten vorhanden und kann PDF-Seiten rendern. Tesseract 5.5.2 mit deutschen Sprachdaten wurde lokal installiert. Das Skript sucht Tesseract im Systempfad sowie unter `/opt/homebrew/bin/tesseract`.

Das Beispielbild erzeugt technisch einen OCR-Lauf mit Status `ocr_finished`, aber keine sicheren Antibiotika-Kandidaten. Ursache ist die Kombination aus Handschrift, Rasterlinien und Bildqualitaet. Für klarere PDF-Exporte oder maschinenschriftliche Kurven sollte die Trefferquote besser sein; bei handschriftlichen Kurven bleibt die Review-Maske zentral.

## Beispiel

```bash
python3 scripts/fever_curve_extract.py "/pfad/zur/fieberkurve.pdf" --out outputs/review_packets --db outputs/pji_register.sqlite
```

Erneut verarbeiten und vorhandenen Review-Datensatz zur selben Quelle ersetzen:

```bash
python3 scripts/fever_curve_extract.py "/pfad/zur/fieberkurve.pdf" --out outputs/review_packets --db outputs/pji_register.sqlite --replace-existing
```

Falls OCR-Text separat vorliegt:

```bash
python3 scripts/fever_curve_extract.py "/pfad/zur/fieberkurve.png" --ocr-text "/pfad/zum/ocr_text.txt" --out outputs/review_packets --db outputs/pji_register.sqlite
```

## Review-Felder

- MedikamentRaw: so im OCR-Text gefunden
- MedikamentNorm: normalisierter Name aus Lexikon
- IstAntibiotikum: 1 für Antibiotika-Kandidat
- Dosis/Intervall: aus der Textzeile heuristisch erkannt
- Confidence: technische Einschaetzung, keine medizinische Sicherheit
- ReviewStatus: offen, bestätigt, verworfen, unklar
