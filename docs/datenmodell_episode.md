# PJI-Register Datenmodell

Das Register ist episodezentriert aufgebaut:

```text
Patient
  -> GelenkFall
       -> Episode (PJI-Episode)
            -> Aufenthalt
                 -> Eingriff
                      -> Orthodok
                      -> Labor
                      -> Mikrobiologie
                           -> Antibiogramm
                      -> Histologie
            -> Antibiotikatherapie
            -> Outcome
            -> Follow-up
```

## Ebenen

### Patient

Eine Person, pseudonymisiert über `PatientHash`. Direkte Identifikatoren werden nur gespeichert, wenn der Import bewusst mit `--include-identifiers` ausgeführt wird.

### GelenkFall

Ein anatomisches Gelenk eines Patienten, z.B. `Knie rechts` oder `Hüfte links`. Ein Patient kann mehrere Gelenkfälle haben.

### Episode

Die fachliche Klammer für eine PJI-Episode. Eine Episode kann mehrere Aufenthalte, mehrere Eingriffe und eine längere Antibiotikatherapie enthalten. Outcome und Follow-up gehören ebenfalls hierher.

Die aktuelle Migration erzeugt für vorhandene OrthoDok-Bestandsdaten zunächst eine automatische `Registerepisode` je Gelenkfall. Diese Episode muss für echte PJI-Studien fachlich geprüft und ggf. in konkrete PJI-Episoden aufgeteilt werden.

### Aufenthalt

Stationaerer Fall innerhalb einer Episode. Ein Aufenthalt kann mehrere Eingriffe enthalten.

### Eingriff

Operativer Eingriff innerhalb eines Aufenthalts. OrthoDok, Labor, Mikrobiologie und Histologie bleiben am Eingriff, weil diese Daten zeitlich und fachlich meist genau an eine OP oder einen perioperativen Zeitraum gebunden sind.

### Antibiotikatherapie

Episodebezogene Therapie. Einzelne bestätigte Fieberkurven-Kandidaten werden in `tblAntibiotikatherapie` geschrieben. Optional bleibt ein Bezug zu einem Eingriff erhalten, wenn eine Gabe direkt perioperativ zugeordnet werden kann.

### Outcome und Follow-up

Outcome und Follow-up sind episodebezogen. Dadurch kann eine PJI-Episode über mehrere Aufenthalte und Eingriffe hinweg bewertet werden.

## Wichtige Tabellen

- `tblPatient`
- `tblGelenkFall`
- `tblEpisode`
- `tblAufenthalt`
- `tblEingriff`
- `tblOrthodokOP`
- `tblLabor`
- `tblMikrobiologie`
- `tblAntibiogramm`
- `tblHistologie`
- `tblAntibiotikatherapie`
- `tblOutcome`
- `tblFollowUp`
- `tblFieberkurve`
- `tblFieberkurveMedikamentKandidat`

## Praktischer Workflow

1. Patient/Gelenkfall aus OrthoDok oder SAP importieren.
2. PJI-Episode anlegen oder automatische Registerepisode prüfen.
3. Aufenthalte und Eingriffe der Episode zuordnen.
4. Fieberkurven zur Episode oder zu einem Eingriff verknüpfen.
5. Antibiotika-Kandidaten bestätigen.
6. Therapie, Outcome und Follow-up episodebezogen auswerten.
