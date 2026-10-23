# Dateneingabe starten

Diese Seite beschreibt den praktischen Startpunkt für die echte Datenerfassung im PJI-Register.

## Lokale App

App starten:

```bash
python3 scripts/review_app.py --db outputs/pji_register_orthodok_pseudonymized.sqlite --host 127.0.0.1 --port 8766
```

Wichtige Seiten:

- `http://127.0.0.1:8766/dateneingabe`: Arbeitszentrale mit Live-Zahlen, nächstem Fall und Qualitätscheck.
- `http://127.0.0.1:8766/patienten`: Patientenliste mit möglichem Infekt.
- `http://127.0.0.1:8766/kollektiv?status=offen&priority=P1`: priorisierte SAP-Screenshot-Liste.
- `http://127.0.0.1:8766/fallakte/<KollektivID>`: Fallakte für Nachträge.
- `http://127.0.0.1:8766/`: Review-Queue für importierte Fieberkurven.

## Datenmodell für die Eingabe

Die Eingabe bleibt hierarchisch:

```text
Patient
  -> Gelenkfall
       -> Episode
            -> Aufenthalt
                 -> Eingriff
                      -> OrthoDok / OP-Details
                      -> Labor
                      -> Mikrobiologie
                      -> Antibiogramm
                      -> Histologie
            -> Antibiotikatherapie
            -> Outcome
            -> Follow-up
```

Der Eingriff bleibt der wichtigste Analyseanker. Episode, Outcome, Follow-up und Antibiotikatherapie bilden die klinische Klammer über mehrere Eingriffe hinweg.

## Tagesworkflow

1. In `Dateneingabe` den nächsten offenen Fall oder die P1-Arbeitsliste öffnen.
2. In SAP mit Patientenzahl und SAP-Fallnummer die Fieberkurve suchen.
3. Screenshot oder PDF in der Kollektivzeile einfügen, ablegen oder als Pfad importieren.
4. In der Fallakte fehlende Eingriffe, OP-Details, Labor, Histologie, Outcome oder Follow-up nachtragen.
5. In der Review-Queue die Antibiose bestätigen oder manuell ergänzen.
6. Status auf `reviewt` setzen, wenn Fieberkurve und AB-Modul abgeschlossen sind.

## Eingaberegeln

- Labor wird im Long Format gespeichert: ein Parameter pro Zeile, z.B. CRP, Leuko, PCT, IL-6.
- Weichteileingriffe oder Wundrevisionen ohne OrthoDok-Bogen werden als manueller Eingriff erfasst.
- OP-Details aus OP-Bericht, SAP oder manueller Quelle gehören als OP-/OrthoDok-Details an den passenden Eingriff.
- Histologie gehört an den Eingriff, mit Krenn-Score, PMN/Neutrophilen und kurzer Befundzusammenfassung.
- Outcome und Follow-up gehören zur Episode, bleiben aber bei Bedarf an den relevanten Eingriff gekoppelt.
- Bei Unsicherheit lieber Kommentar eintragen als eine Information stumm zu überschreiben.

## Statuslogik

- `offen`: SAP-Fieberkurve ist noch zu suchen.
- `exportiert`: Screenshot/PDF wurde aus SAP vorbereitet, aber noch nicht importiert.
- `importiert`: Fieberkurve ist in der App verknüpft.
- `reviewt`: Fieberkurve und Antibiotika-Review sind abgeschlossen.
- `unklar`: Zuordnung oder Quelle muss fachlich geprüft werden.
- `nicht_benoetigt`: Fieberkurve wird für diesen Kandidaten nicht gebraucht.

## Exporte

- Fieberkurven-Kollektiv: `outputs/fieberkurven_kollektiv_hybase_pji_nah_pos.csv`
- Patientenliste Infektverdacht: `outputs/patientenliste_infektverdacht.csv`
- Live-Export aus der App:
  - `/export/fieberkurven_kollektiv.csv`
  - `/export/patienten_infektverdacht.csv`

## Qualitätscheck vor Studienauswertung

Vor einer Auswertung sollten mindestens diese Punkte geprüft werden:

- Patientenzahl und SAP-Fallnummer sind für das Arbeitskollektiv weitgehend vorhanden.
- Fieberkurven sind importiert und reviewt.
- Manuell nachgetragene Eingriffe haben Datum, Eingriffsart und Quelle/Kommentar.
- Laborwerte haben Datum, Parameter, Wert oder WertText und Einheit.
- Histologien haben Krenn/PMN oder eine klare Begründung im Kommentar.
- Outcome/Tod und Follow-up sind für abgeschlossene Episoden nachgetragen.
- Fälle mit Kultur weit entfernt von der OP wurden fachlich geprüft.
