PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tblSourceFile (
    SourceFileID INTEGER PRIMARY KEY,
    SourceSystem TEXT NOT NULL,
    OriginalPath TEXT NOT NULL,
    FileName TEXT NOT NULL,
    FileHashSHA256 TEXT,
    ImportedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Comment TEXT
);

CREATE TABLE IF NOT EXISTS tblImportBatch (
    ImportBatchID INTEGER PRIMARY KEY,
    SourceFileID INTEGER NOT NULL,
    ImportType TEXT NOT NULL,
    StartedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FinishedAt TEXT,
    RowCount INTEGER NOT NULL DEFAULT 0,
    Status TEXT NOT NULL DEFAULT 'running',
    Note TEXT,
    FOREIGN KEY (SourceFileID) REFERENCES tblSourceFile(SourceFileID)
);

CREATE TABLE IF NOT EXISTS tblPatient (
    PatientID INTEGER PRIMARY KEY,
    PatientenzahlSAP TEXT,
    HYBASEPatientID_Raw TEXT,
    HYBASEPatientHash TEXT,
    PatientHash TEXT NOT NULL UNIQUE,
    Nachname TEXT,
    Vorname TEXT,
    Geburtsdatum TEXT,
    Geburtsjahr INTEGER,
    Geschlecht TEXT,
    BMI REAL,
    ASA INTEGER,
    CharlsonComorbidityIndex INTEGER,
    Raucherstatus TEXT,
    Diabetes INTEGER,
    Rheuma INTEGER,
    Immunsuppression INTEGER,
    Dialyse INTEGER,
    SonstigeKomorbiditaeten TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tblGelenkFall (
    GelenkFallID INTEGER PRIMARY KEY,
    PatientID INTEGER NOT NULL,
    Gelenk TEXT NOT NULL,
    Seite TEXT,
    PrimaerimplantationDatum TEXT,
    PrimaerimplantationAuswaerts INTEGER NOT NULL DEFAULT 0,
    PrimaerimplantationOrt TEXT,
    PrimaerimplantationKommentar TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (PatientID) REFERENCES tblPatient(PatientID),
    UNIQUE (PatientID, Gelenk, Seite)
);

CREATE TABLE IF NOT EXISTS tblEpisode (
    EpisodeID INTEGER PRIMARY KEY,
    GelenkFallID INTEGER NOT NULL,
    EpisodeTyp TEXT NOT NULL DEFAULT 'PJI',
    EpisodeBeginn TEXT,
    EpisodeEnde TEXT,
    DiagnoseDatum TEXT,
    PJIKlassifikation TEXT,
    Diagnosekriterien TEXT,
    Infektionstyp TEXT,
    Symptombeginn TEXT,
    SymptomdauerTage INTEGER,
    Fistel INTEGER,
    FreiliegendeProthese INTEGER,
    Wundheilungsstoerung INTEGER,
    Sekretion INTEGER,
    Fieber INTEGER,
    Schmerz INTEGER,
    Lockerungszeichen INTEGER,
    CRPPraeopWert REAL,
    CRPPraeopDatum TEXT,
    SynoviaLeukozyten REAL,
    SynoviaLeukozytenEinheit TEXT,
    SynoviaPMNProzent REAL,
    AlphaDefensin TEXT,
    HistologiePMNHPF REAL,
    HistologieKrennScore REAL,
    BildgebungLockerung INTEGER,
    BildgebungOsteolyse INTEGER,
    ABVorProbe INTEGER,
    ABVorProbeSubstanz TEXT,
    ABVorProbeStart TEXT,
    ABVorProbeEnde TEXT,
    ABLetzteDosisVorOP TEXT,
    EBJISAutoStatus TEXT,
    EBJISAutoHinweis TEXT,
    EBJISStatus TEXT,
    EBJISKlinischeMerkmale INTEGER,
    EBJISSerologie INTEGER,
    EBJISSynovia INTEGER,
    EBJISMikrobiologie INTEGER,
    EBJISHistologie INTEGER,
    EBJISBildgebung INTEGER,
    EBJISKommentar TEXT,
    EBJISReviewer TEXT,
    EBJISReviewDatum TEXT,
    Kommentar TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (GelenkFallID) REFERENCES tblGelenkFall(GelenkFallID)
);

CREATE TABLE IF NOT EXISTS tblAufenthalt (
    AufenthaltID INTEGER PRIMARY KEY,
    GelenkFallID INTEGER NOT NULL,
    EpisodeID INTEGER NOT NULL,
    Fallnummer TEXT,
    FallHash TEXT,
    MedizinischerFall TEXT,
    Aufnahme TEXT,
    Entlassung TEXT,
    Station TEXT,
    Auswaerts INTEGER NOT NULL DEFAULT 0,
    KeineFieberkurveErwartet INTEGER NOT NULL DEFAULT 0,
    KeinPatientenbriefErwartet INTEGER NOT NULL DEFAULT 0,
    KeineAmbulanzErwartet INTEGER NOT NULL DEFAULT 0,
    KeinOPBerichtErwartet INTEGER NOT NULL DEFAULT 0,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (GelenkFallID) REFERENCES tblGelenkFall(GelenkFallID),
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID)
);

CREATE UNIQUE INDEX IF NOT EXISTS idxAufenthaltFallHash
ON tblAufenthalt (GelenkFallID, FallHash)
WHERE FallHash IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idxAufenthaltFallnummer
ON tblAufenthalt (GelenkFallID, Fallnummer)
WHERE Fallnummer IS NOT NULL;

CREATE TABLE IF NOT EXISTS lkpEingriffsart (
    EingriffsartID INTEGER PRIMARY KEY,
    Code TEXT NOT NULL UNIQUE,
    Bezeichnung TEXT NOT NULL,
    Beschreibung TEXT
);

INSERT OR IGNORE INTO lkpEingriffsart (EingriffsartID, Code, Bezeichnung, Beschreibung) VALUES
    (1, 'PRIMARY', 'Primaerimplantation', 'Primaere Endoprothesenimplantation'),
    (2, 'DAIR', 'DAIR', 'Debridement, antibiotics and implant retention'),
    (3, 'DEBRIDEMENT', 'Debridement', 'Debridement ohne explizite DAIR-Klassifikation'),
    (4, 'SPACER', 'Spacer', 'Spacer-Implantation oder Spacerwechsel'),
    (5, 'EXPLANTATION', 'Explantation', 'Entfernung der Prothese'),
    (6, 'REIMPLANTATION', 'Reimplantation', 'Reimplantation nach zweizeitigem Wechsel'),
    (7, 'REVISION', 'Revision', 'Revision oder Wechsel ohne genauere Klassifikation'),
    (8, 'METAL_REMOVAL', 'Metallentfernung', 'Metallentfernung'),
    (9, 'SOFT_TISSUE', 'Weichteileingriff', 'Manuell nachgetragener Weichteil- oder Wundeingriff'),
    (10, 'WOUND_REVISION', 'Wundrevision', 'Manuell nachgetragene Wundrevision ohne eigenen OrthoDok-Bogen'),
    (99, 'OTHER', 'Sonstige', 'Nicht eindeutig klassifizierbarer Eingriff');

CREATE TABLE IF NOT EXISTS tblEingriff (
    EingriffID INTEGER PRIMARY KEY,
    AufenthaltID INTEGER NOT NULL,
    OPDatum TEXT,
    EingriffsartID INTEGER NOT NULL DEFAULT 99,
    EingriffsartTextQuelle TEXT,
    ReoperationsgrundKategorie TEXT,
    ReoperationsgrundText TEXT,
    ReoperationsgrundQuelle TEXT,
    ReoperationsgrundReviewStatus TEXT NOT NULL DEFAULT 'offen',
    ReoperationsgrundKommentar TEXT,
    Kommentar TEXT,
    KeinOPBerichtErwartet INTEGER NOT NULL DEFAULT 0,
    KeinePraeopAnamneseErwartet INTEGER NOT NULL DEFAULT 0,
    KeineMikrobiologieErwartet INTEGER NOT NULL DEFAULT 0,
    KeineAmbulanzErwartet INTEGER NOT NULL DEFAULT 0,
    KeinLaborErwartet INTEGER NOT NULL DEFAULT 0,
    KeineHistologieErwartet INTEGER NOT NULL DEFAULT 0,
    KeinOutcomeErwartet INTEGER NOT NULL DEFAULT 0,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (AufenthaltID) REFERENCES tblAufenthalt(AufenthaltID),
    FOREIGN KEY (EingriffsartID) REFERENCES lkpEingriffsart(EingriffsartID)
);

CREATE INDEX IF NOT EXISTS idxEingriffAufenthaltDatum
ON tblEingriff (AufenthaltID, OPDatum);

CREATE TABLE IF NOT EXISTS tblRawOrthodok (
    RawOrthodokID INTEGER PRIMARY KEY,
    ImportBatchID INTEGER NOT NULL,
    SheetName TEXT NOT NULL,
    RowNumber INTEGER NOT NULL,
    EingriffID INTEGER,
    RawJSON TEXT NOT NULL,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ImportBatchID) REFERENCES tblImportBatch(ImportBatchID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
    UNIQUE (ImportBatchID, SheetName, RowNumber)
);

CREATE TABLE IF NOT EXISTS tblOrthodokOP (
    OrthodokOPID INTEGER PRIMARY KEY,
    EingriffID INTEGER NOT NULL,
    RawOrthodokID INTEGER,
    Version TEXT,
    Operateur TEXT,
    Assistenz TEXT,
    DauerMin INTEGER,
    BlutverlustMl INTEGER,
    Anaesthesie TEXT,
    ImplantatHersteller TEXT,
    ImplantatSystem TEXT,
    FemurGroesse TEXT,
    FemurTyp TEXT,
    FemurZementiert TEXT,
    TibiaGroesse TEXT,
    TibiaTyp TEXT,
    TibiaZementiert TEXT,
    PatellaErsatz TEXT,
    PatellaGroesse TEXT,
    PatellaZementiert TEXT,
    GleitflaecheGroesse TEXT,
    GleitflaecheTyp TEXT,
    Fixation TEXT,
    Antibiotikazement TEXT,
    Zugang TEXT,
    Drainage TEXT,
    Navigation TEXT,
    Robotik TEXT,
    SpacerTyp TEXT,
    BlutsperreDauer TEXT,
    BlutsperreDruck TEXT,
    RohdatenJSON TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
    FOREIGN KEY (RawOrthodokID) REFERENCES tblRawOrthodok(RawOrthodokID)
);

CREATE TABLE IF NOT EXISTS tblMikrobiologie (
    MikrobioID INTEGER PRIMARY KEY,
    EingriffID INTEGER NOT NULL,
    Material TEXT,
    Entnahmedatum TEXT,
    Erreger TEXT,
    Kommentar TEXT,
    ProbeCode TEXT,
    BefundBekanntDatum TEXT,
    DruckDatum TEXT,
    MaterialTyp TEXT,
    Sonikation INTEGER,
    SonikationCFU REAL,
    SonikationEinheit TEXT,
    InkubationsdauerTage INTEGER,
    KlinischRelevant INTEGER,
    GleicheSpeziesInMehrerenProben INTEGER,
    ResistenzPhaenotyp TEXT,
    RifampicinSensibel INTEGER,
    FluorchinolonSensibel INTEGER,
    BiofilmAktiveTherapieMoeglich INTEGER,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID)
);

CREATE TABLE IF NOT EXISTS tblAntibiogramm (
    AntibiogrammID INTEGER PRIMARY KEY,
    MikrobioID INTEGER NOT NULL,
    Antibiotikum TEXT NOT NULL,
    Ergebnis TEXT,
    MHK TEXT,
    Kommentar TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (MikrobioID) REFERENCES tblMikrobiologie(MikrobioID)
);

CREATE TABLE IF NOT EXISTS mapMaterial (
    MapMaterialID INTEGER PRIMARY KEY,
    Material_Raw TEXT NOT NULL UNIQUE,
    Material_Standard TEXT NOT NULL,
    Kommentar TEXT,
    Aktiv INTEGER NOT NULL DEFAULT 1,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mapErreger (
    MapErregerID INTEGER PRIMARY KEY,
    Erreger_Raw TEXT NOT NULL UNIQUE,
    Erreger_Standard TEXT NOT NULL,
    Erregergruppe TEXT,
    Gramstatus TEXT,
    Virulenzgruppe TEXT,
    Kommentar TEXT,
    Aktiv INTEGER NOT NULL DEFAULT 1,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mapAntibiotikum (
    MapAntibiotikumID INTEGER PRIMARY KEY,
    Antibiotikum_Raw TEXT NOT NULL UNIQUE,
    Antibiotikum_Standard TEXT NOT NULL,
    Antibiotikaklasse TEXT,
    Spezialtest TEXT,
    Kommentar TEXT,
    Aktiv INTEGER NOT NULL DEFAULT 1,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tblLaborauftrag (
    LaborauftragID INTEGER PRIMARY KEY,
    SourceKey TEXT NOT NULL UNIQUE,
    PatientID INTEGER,
    LaborNr_Raw TEXT,
    Auftragsdatum TEXT,
    Befunddatum TEXT,
    BefundlaufzeitTage INTEGER,
    Material_Raw TEXT,
    Lokalisation_Raw TEXT,
    Info_Raw TEXT,
    KlinischeRelevanz_Raw TEXT,
    Status_Raw TEXT,
    Klassifizierung_Raw TEXT,
    Fallnummer_Raw TEXT,
    Station_Raw TEXT,
    Fachbereich_Raw TEXT,
    Freitext_Raw TEXT,
    AntibiotikaHinweis_Raw TEXT,
    Flag_AntibiotikaImFreitext INTEGER NOT NULL DEFAULT 0,
    Quellblatt TEXT,
    Quelldatei TEXT,
    RawJSON TEXT,
    Flag_BefunddatumVorAuftragsdatum INTEGER NOT NULL DEFAULT 0,
    Flag_BefundlaufzeitGroesser7Tage INTEGER NOT NULL DEFAULT 0,
    Flag_BefundlaufzeitGroesser14Tage INTEGER NOT NULL DEFAULT 0,
    Flag_FehlendesAuftragsdatum INTEGER NOT NULL DEFAULT 0,
    Flag_FehlendesBefunddatum INTEGER NOT NULL DEFAULT 0,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (PatientID) REFERENCES tblPatient(PatientID)
);

CREATE TABLE IF NOT EXISTS tblProbe (
    ProbeID INTEGER PRIMARY KEY,
    SourceKey TEXT NOT NULL UNIQUE,
    LaborauftragID INTEGER NOT NULL,
    Material_Raw TEXT,
    Material_Standard TEXT,
    Probenbeschreibung_Raw TEXT,
    Lokalisation_Raw TEXT,
    Gelenk_Abgeleitet TEXT,
    Seite_Abgeleitet TEXT,
    AnatomischeStruktur TEXT,
    Implantatbezug_Abgeleitet TEXT,
    ImplantattypHinweis TEXT,
    Gelenk_Ableitungsquelle TEXT,
    Seite_Ableitungsquelle TEXT,
    Flag_GelenkUnsicher INTEGER NOT NULL DEFAULT 0,
    Flag_SeiteUnsicher INTEGER NOT NULL DEFAULT 0,
    PJI_Relevanz_Vorlaeufig TEXT,
    AnzahlErreger INTEGER NOT NULL DEFAULT 0,
    AnzahlKulturellPositiveErreger INTEGER NOT NULL DEFAULT 0,
    Polymikrobiell INTEGER NOT NULL DEFAULT 0,
    NurNiedrigVirulenteErreger INTEGER NOT NULL DEFAULT 0,
    MindestensEinHochvirulenterErreger INTEGER NOT NULL DEFAULT 0,
    MindestensEinResistenterErreger INTEGER NOT NULL DEFAULT 0,
    AntibiogrammVorhanden INTEGER NOT NULL DEFAULT 0,
    NurAnreicherungsnachweis INTEGER NOT NULL DEFAULT 0,
    GelenkFallID INTEGER,
    EpisodeID INTEGER,
    AufenthaltID INTEGER,
    EingriffID INTEGER,
    OPDatum TEXT,
    TageDifferenzZuOP INTEGER,
    Zuordnungssicherheit TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (LaborauftragID) REFERENCES tblLaborauftrag(LaborauftragID),
    FOREIGN KEY (GelenkFallID) REFERENCES tblGelenkFall(GelenkFallID),
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (AufenthaltID) REFERENCES tblAufenthalt(AufenthaltID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID)
);

CREATE TABLE IF NOT EXISTS tblIsolat (
    IsolatID INTEGER PRIMARY KEY,
    SourceKey TEXT NOT NULL UNIQUE,
    ProbeID INTEGER NOT NULL,
    LaborauftragID INTEGER NOT NULL,
    Erreger_Raw TEXT,
    Erreger_Standard TEXT,
    Erregergruppe TEXT,
    Gramstatus TEXT,
    Virulenzgruppe TEXT,
    Resistenzmarker_Raw TEXT,
    ResistenzmarkerDatum TEXT,
    Subtyp_Raw TEXT,
    Ergebnisstatus_Raw TEXT,
    Messwert_Raw TEXT,
    Kommentar_Raw TEXT,
    Positiv INTEGER NOT NULL DEFAULT 0,
    Negativ INTEGER NOT NULL DEFAULT 0,
    ErgebnisUnklar INTEGER NOT NULL DEFAULT 0,
    KeinMikrobiologischerErreger INTEGER NOT NULL DEFAULT 0,
    Nachweismethode TEXT,
    NurAnreicherung INTEGER NOT NULL DEFAULT 0,
    NachBlutkulturflasche INTEGER NOT NULL DEFAULT 0,
    LangsamWachsenderErreger INTEGER NOT NULL DEFAULT 0,
    KeimmengeKategorie TEXT,
    SonikationKBEKategorie TEXT,
    QuantitativerWert REAL,
    QuantitativeEinheit TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ProbeID) REFERENCES tblProbe(ProbeID),
    FOREIGN KEY (LaborauftragID) REFERENCES tblLaborauftrag(LaborauftragID)
);

CREATE TABLE IF NOT EXISTS tblHybaseAntibiogramm (
    HybaseAntibiogrammID INTEGER PRIMARY KEY,
    SourceKey TEXT NOT NULL UNIQUE,
    IsolatID INTEGER NOT NULL,
    Antibiotikum_Raw TEXT NOT NULL,
    Antibiotikum_Standard TEXT,
    Antibiotikaklasse TEXT,
    Spezialtest TEXT,
    Ergebnis_Raw TEXT,
    SIR_Standard TEXT,
    MIC_Raw TEXT,
    Methode_Raw TEXT,
    Breakpointsystem TEXT,
    Testdatum TEXT,
    AntibiotikumSpalte TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (IsolatID) REFERENCES tblIsolat(IsolatID)
);

CREATE TABLE IF NOT EXISTS tblHistologie (
    HistologieID INTEGER PRIMARY KEY,
    EingriffID INTEGER NOT NULL,
    KrennScore REAL,
    PMN REAL,
    Akut INTEGER,
    Chronisch INTEGER,
    Kommentar TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID)
);

CREATE TABLE IF NOT EXISTS tblLabor (
    LaborID INTEGER PRIMARY KEY,
    EingriffID INTEGER NOT NULL,
    Datum TEXT,
    CRP REAL,
    Leuko REAL,
    PCT REAL,
    IL6 REAL,
    Kommentar TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID)
);

CREATE TABLE IF NOT EXISTS tblLaborWert (
    LaborWertID INTEGER PRIMARY KEY,
    EpisodeID INTEGER,
    AufenthaltID INTEGER,
    EingriffID INTEGER,
    PatientHash TEXT,
    FallHash TEXT,
    Fallnummer TEXT,
    Parameter TEXT NOT NULL,
    Wert REAL,
    WertText TEXT,
    Einheit TEXT,
    Datum TEXT,
    AbnahmeZeit TEXT,
    Kommentar TEXT,
    SourceFileID INTEGER,
    RawImportID INTEGER,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (AufenthaltID) REFERENCES tblAufenthalt(AufenthaltID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
    FOREIGN KEY (SourceFileID) REFERENCES tblSourceFile(SourceFileID)
);

CREATE TABLE IF NOT EXISTS tblRawLabImport (
    RawLabImportID INTEGER PRIMARY KEY,
    ImportBatchID INTEGER NOT NULL,
    SheetName TEXT,
    RowNumber INTEGER NOT NULL,
    Parameter TEXT,
    LaborWertID INTEGER,
    RawJSON TEXT NOT NULL,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ImportBatchID) REFERENCES tblImportBatch(ImportBatchID),
    FOREIGN KEY (LaborWertID) REFERENCES tblLaborWert(LaborWertID)
);

CREATE TABLE IF NOT EXISTS tblRawHybaseImport (
    RawHybaseImportID INTEGER PRIMARY KEY,
    ImportBatchID INTEGER NOT NULL,
    SheetName TEXT,
    RowNumber INTEGER NOT NULL,
    LaborauftragID INTEGER,
    ProbeID INTEGER,
    IsolatID INTEGER,
    HybaseAntibiogrammID INTEGER,
    MikrobioID INTEGER,
    AntibiogrammID INTEGER,
    RawJSON TEXT NOT NULL,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ImportBatchID) REFERENCES tblImportBatch(ImportBatchID),
    FOREIGN KEY (LaborauftragID) REFERENCES tblLaborauftrag(LaborauftragID),
    FOREIGN KEY (ProbeID) REFERENCES tblProbe(ProbeID),
    FOREIGN KEY (IsolatID) REFERENCES tblIsolat(IsolatID),
    FOREIGN KEY (HybaseAntibiogrammID) REFERENCES tblHybaseAntibiogramm(HybaseAntibiogrammID),
    FOREIGN KEY (MikrobioID) REFERENCES tblMikrobiologie(MikrobioID),
    FOREIGN KEY (AntibiogrammID) REFERENCES tblAntibiogramm(AntibiogrammID)
);

CREATE TABLE IF NOT EXISTS tblRawHybaseAntibiogrammLink (
    RawHybaseAntibiogrammLinkID INTEGER PRIMARY KEY,
    RawHybaseImportID INTEGER NOT NULL,
    AntibiogrammID INTEGER NOT NULL,
    AntibiotikumSpalte TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (RawHybaseImportID) REFERENCES tblRawHybaseImport(RawHybaseImportID),
    FOREIGN KEY (AntibiogrammID) REFERENCES tblAntibiogramm(AntibiogrammID)
);

CREATE TABLE IF NOT EXISTS tblRawHybaseIsolatAntibiogrammLink (
    RawHybaseIsolatAntibiogrammLinkID INTEGER PRIMARY KEY,
    RawHybaseImportID INTEGER NOT NULL,
    HybaseAntibiogrammID INTEGER NOT NULL,
    AntibiotikumSpalte TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (RawHybaseImportID) REFERENCES tblRawHybaseImport(RawHybaseImportID),
    FOREIGN KEY (HybaseAntibiogrammID) REFERENCES tblHybaseAntibiogramm(HybaseAntibiogrammID)
);

CREATE TABLE IF NOT EXISTS tblStudienmodulAB (
    StudienABID INTEGER PRIMARY KEY,
    EpisodeID INTEGER NOT NULL,
    EingriffID INTEGER,
    EmpirischeAB TEXT,
    EmpirischeStart TEXT,
    EmpirischeEnde TEXT,
    EmpirischeStartZeit TEXT,
    EmpirischeEndeZeit TEXT,
    GezielteAB TEXT,
    GezielteStart TEXT,
    GezielteEnde TEXT,
    GezielteStartZeit TEXT,
    GezielteEndeZeit TEXT,
    ProbenentnahmeDatum TEXT,
    ErsterMikrobioBefundDatum TEXT,
    Passend INTEGER,
    EmpirischAktivGegenErreger INTEGER,
    EmpirischBewertung TEXT,
    EmpirischBewertungsgrund TEXT,
    EmpiricalCoverageStatus TEXT,
    ErregerZumTherapiezeitpunkt TEXT,
    ErregerBekanntDatum TEXT,
    TimeToAdequateTherapyTage REAL,
    DaysSamplingToEmpiricalAB REAL,
    DaysSamplingToTargetedAB REAL,
    AntibiogrammAbgleichJSON TEXT,
    Kommentar TEXT,
    PDFVorhanden INTEGER NOT NULL DEFAULT 0,
    Bearbeitet INTEGER NOT NULL DEFAULT 0,
    BearbeitetAm TEXT,
    Reviewer TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID)
);

CREATE TABLE IF NOT EXISTS tblOutcome (
    OutcomeID INTEGER PRIMARY KEY,
    EpisodeID INTEGER NOT NULL,
    EingriffID INTEGER,
    Reinfektion INTEGER,
    Revision INTEGER,
    Spacerwechsel INTEGER,
    FollowUpDatum TEXT,
    FollowUpMonate REAL,
    Mortalitaet INTEGER,
    MortalitaetDatum TEXT,
    Implantaterhalt INTEGER,
    PROMs TEXT,
    OutcomeTyp TEXT,
    SeptischesVersagen INTEGER,
    Therapieversagen INTEGER,
    VersagenDatum TEXT,
    VersagenGrund TEXT,
    Relapse INTEGER,
    RelapseDatum TEXT,
    RelapseErregerText TEXT,
    ResistenzkonstellationGleich INTEGER,
    Rezidiv INTEGER,
    RezidivDatum TEXT,
    RezidivErregerGleich INTEGER,
    RezidivErregerText TEXT,
    ReinfektionErregerText TEXT,
    Explantation INTEGER,
    Arthrodese INTEGER,
    Girdlestone INTEGER,
    Suppression INTEGER,
    LetztesFollowUpDatum TEXT,
    Kommentar TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID)
);

CREATE TABLE IF NOT EXISTS tblFollowUp (
    FollowUpID INTEGER PRIMARY KEY,
    EpisodeID INTEGER NOT NULL,
    Datum TEXT,
    MonateSeitEpisode REAL,
    KlinischerStatus TEXT,
    Reinfektion INTEGER,
    RevisionSeitLetztemFU INTEGER,
    ImplantatStatus TEXT,
    PROMs TEXT,
    OutcomeTyp TEXT,
    Therapieversagen INTEGER,
    Rezidiv INTEGER,
    EreignisDatum TEXT,
    Kommentar TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID)
);

CREATE TABLE IF NOT EXISTS tblHistologieDokument (
    HistologieDokumentID INTEGER PRIMARY KEY,
    EpisodeID INTEGER,
    AufenthaltID INTEGER,
    EingriffID INTEGER,
    SourceFileID INTEGER,
    OriginalPath TEXT NOT NULL,
    DokumentDatum TEXT,
    BefundText TEXT,
    ExtractedJSON TEXT,
    ReviewStatus TEXT NOT NULL DEFAULT 'offen',
    Kommentar TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (AufenthaltID) REFERENCES tblAufenthalt(AufenthaltID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
    FOREIGN KEY (SourceFileID) REFERENCES tblSourceFile(SourceFileID)
);

CREATE TABLE IF NOT EXISTS tblOPBerichtDokument (
    OPBerichtDokumentID INTEGER PRIMARY KEY,
    EpisodeID INTEGER NOT NULL,
    AufenthaltID INTEGER,
    EingriffID INTEGER,
    SourceFileID INTEGER,
    OriginalPath TEXT,
    DokumentDatum TEXT,
    OPDatum TEXT,
    EingriffZusammenfassung TEXT,
    Zugang TEXT,
    ProbenText TEXT,
    ImplantatText TEXT,
    BerichtText TEXT,
    ExtractedJSON TEXT,
    ReviewStatus TEXT NOT NULL DEFAULT 'offen',
    Kommentar TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (AufenthaltID) REFERENCES tblAufenthalt(AufenthaltID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
    FOREIGN KEY (SourceFileID) REFERENCES tblSourceFile(SourceFileID)
);

CREATE TABLE IF NOT EXISTS tblFieberkurve (
    FieberkurveID INTEGER PRIMARY KEY,
    EpisodeID INTEGER,
    AufenthaltID INTEGER,
    EingriffID INTEGER,
    SourceFileID INTEGER,
    OriginalPath TEXT NOT NULL,
    VonDatum TEXT,
    BisDatum TEXT,
    PDFVorhanden INTEGER NOT NULL DEFAULT 1,
    OCRStatus TEXT NOT NULL DEFAULT 'pending',
    ReviewStatus TEXT NOT NULL DEFAULT 'offen',
    Kommentar TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (AufenthaltID) REFERENCES tblAufenthalt(AufenthaltID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
    FOREIGN KEY (SourceFileID) REFERENCES tblSourceFile(SourceFileID)
);

CREATE TABLE IF NOT EXISTS tblFieberkurveSeite (
    FieberkurveSeiteID INTEGER PRIMARY KEY,
    FieberkurveID INTEGER NOT NULL,
    Seite INTEGER NOT NULL,
    BildPfad TEXT,
    BreitePx INTEGER,
    HoehePx INTEGER,
    OCRText TEXT,
    OCRStatus TEXT NOT NULL DEFAULT 'pending',
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (FieberkurveID) REFERENCES tblFieberkurve(FieberkurveID)
);

CREATE TABLE IF NOT EXISTS tblFieberkurveMedikamentKandidat (
    KandidatID INTEGER PRIMARY KEY,
    FieberkurveID INTEGER NOT NULL,
    FieberkurveSeiteID INTEGER,
    EpisodeID INTEGER,
    EingriffID INTEGER,
    MedikamentRaw TEXT NOT NULL,
    MedikamentNorm TEXT,
    IstAntibiotikum INTEGER NOT NULL DEFAULT 0,
    Kategorie TEXT,
    Dosis TEXT,
    Intervall TEXT,
    Datum TEXT,
    StartDatum TEXT,
    EndeDatum TEXT,
    DauerTage INTEGER,
    Tageszeit TEXT,
    Confidence REAL,
    Quelle TEXT NOT NULL DEFAULT 'ocr',
    BoundingBox TEXT,
    OCRTextSnippet TEXT,
    MikroKontextJSON TEXT,
    Therapiephase TEXT,
    ReviewStatus TEXT NOT NULL DEFAULT 'offen',
    ReviewKommentar TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (FieberkurveID) REFERENCES tblFieberkurve(FieberkurveID),
    FOREIGN KEY (FieberkurveSeiteID) REFERENCES tblFieberkurveSeite(FieberkurveSeiteID),
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID)
);

CREATE TABLE IF NOT EXISTS tblFieberkurveKollektiv (
    KollektivID INTEGER PRIMARY KEY,
    KollektivName TEXT NOT NULL DEFAULT 'HYBASE_PJI_NAH_POS',
    EpisodeID INTEGER NOT NULL,
    EingriffID INTEGER,
    PatientID INTEGER NOT NULL,
    GelenkFallID INTEGER NOT NULL,
    Prioritaet INTEGER NOT NULL,
    PrioritaetText TEXT,
    PatientHash TEXT,
    PatientenzahlSAP TEXT,
    Gelenk TEXT,
    Seite TEXT,
    EpisodeBeginn TEXT,
    OPDatum TEXT,
    SAPFallnummer TEXT,
    MedizinischerFall TEXT,
    PjiNahPosMikro INTEGER NOT NULL DEFAULT 0,
    SterilPosMikro INTEGER NOT NULL DEFAULT 0,
    LokalPosMikro INTEGER NOT NULL DEFAULT 0,
    ReopPosMikro INTEGER NOT NULL DEFAULT 0,
    PosMikroGesamt INTEGER NOT NULL DEFAULT 0,
    NegMikroGesamt INTEGER NOT NULL DEFAULT 0,
    ErstePositiveKultur TEXT,
    LetztePositiveKultur TEXT,
    ErregerListe TEXT,
    MaterialListe TEXT,
    FieberkurveStatus TEXT NOT NULL DEFAULT 'benoetigt',
    FieberkurveIDs TEXT,
    SAPScreenshotStatus TEXT NOT NULL DEFAULT 'offen',
    SAPDateinameVorschlag TEXT,
    ManuellKommentar TEXT,
    Aktiv INTEGER NOT NULL DEFAULT 1,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
    FOREIGN KEY (PatientID) REFERENCES tblPatient(PatientID),
    FOREIGN KEY (GelenkFallID) REFERENCES tblGelenkFall(GelenkFallID),
    UNIQUE (KollektivName, EpisodeID)
);

CREATE TABLE IF NOT EXISTS tblAntibiotikaGabe (
    AntibiotikaGabeID INTEGER PRIMARY KEY,
    EpisodeID INTEGER NOT NULL,
    EingriffID INTEGER,
    KandidatID INTEGER,
    Therapiephase TEXT,
    Antibiotikum TEXT NOT NULL,
    Dosis TEXT,
    Applikationsweg TEXT,
    Start TEXT,
    Ende TEXT,
    Kommentar TEXT,
    Reviewer TEXT,
    BestaetigtAm TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
    FOREIGN KEY (KandidatID) REFERENCES tblFieberkurveMedikamentKandidat(KandidatID)
);

CREATE TABLE IF NOT EXISTS tblAntibiotikatherapie (
    AntibiotikatherapieID INTEGER PRIMARY KEY,
    EpisodeID INTEGER NOT NULL,
    EingriffID INTEGER,
    KandidatID INTEGER,
    Therapiephase TEXT,
    Antibiotikum TEXT NOT NULL,
    Dosis TEXT,
    Applikationsweg TEXT,
    Start TEXT,
    Ende TEXT,
    TherapieZiel TEXT,
    StartZeit TEXT,
    EndeZeit TEXT,
    Kombinationstherapie INTEGER,
    Wechselgrund TEXT,
    Praeoperativ INTEGER,
    LetzteDosisVorOP TEXT,
    AktivGegenErreger INTEGER,
    CoverageStatus TEXT,
    AbgleichStatus TEXT,
    AbgleichKommentar TEXT,
    BekannteErregerText TEXT,
    ReviewStatus TEXT NOT NULL DEFAULT 'offen',
    Reviewer TEXT,
    Kommentar TEXT,
    Quelle TEXT,
    CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
    FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
    FOREIGN KEY (KandidatID) REFERENCES tblFieberkurveMedikamentKandidat(KandidatID)
);

CREATE TABLE IF NOT EXISTS lkpAntibiotikum (
    AntibiotikumID INTEGER PRIMARY KEY,
    NameNorm TEXT NOT NULL UNIQUE,
    ATC TEXT,
    Klasse TEXT,
    Suchbegriffe TEXT,
    Aktiv INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idxPatientHash ON tblPatient (PatientHash);
CREATE INDEX IF NOT EXISTS idxGelenkFallPatient ON tblGelenkFall (PatientID);
CREATE INDEX IF NOT EXISTS idxEpisodeGelenkFall ON tblEpisode (GelenkFallID, EpisodeBeginn);
CREATE INDEX IF NOT EXISTS idxAufenthaltEpisode ON tblAufenthalt (EpisodeID);
CREATE INDEX IF NOT EXISTS idxEingriffDatum ON tblEingriff (OPDatum);
CREATE INDEX IF NOT EXISTS idxEingriffReoperationsgrund
ON tblEingriff (ReoperationsgrundKategorie, ReoperationsgrundReviewStatus, OPDatum);
CREATE INDEX IF NOT EXISTS idxMikrobioEingriff ON tblMikrobiologie (EingriffID);
CREATE INDEX IF NOT EXISTS idxLaborEingriffDatum ON tblLabor (EingriffID, Datum);
CREATE INDEX IF NOT EXISTS idxLaborWertEpisodeParameter ON tblLaborWert (EpisodeID, Parameter, Datum);
CREATE INDEX IF NOT EXISTS idxLaborWertFallHash ON tblLaborWert (FallHash, Parameter, Datum);
CREATE INDEX IF NOT EXISTS idxRawLabBatch ON tblRawLabImport (ImportBatchID, Parameter);
CREATE INDEX IF NOT EXISTS idxRawHybaseBatch ON tblRawHybaseImport (ImportBatchID);
CREATE INDEX IF NOT EXISTS idxRawHybaseAntibiogrammLinkRaw ON tblRawHybaseAntibiogrammLink (RawHybaseImportID);
CREATE INDEX IF NOT EXISTS idxRawHybaseAntibiogrammLinkAB ON tblRawHybaseAntibiogrammLink (AntibiogrammID);
CREATE INDEX IF NOT EXISTS idxLaborauftragLaborNr ON tblLaborauftrag (LaborNr_Raw, Auftragsdatum);
CREATE INDEX IF NOT EXISTS idxLaborauftragPatient ON tblLaborauftrag (PatientID, Auftragsdatum);
CREATE INDEX IF NOT EXISTS idxProbeLaborauftrag ON tblProbe (LaborauftragID, Material_Standard);
CREATE INDEX IF NOT EXISTS idxProbeLinking ON tblProbe (EpisodeID, EingriffID, PJI_Relevanz_Vorlaeufig);
CREATE INDEX IF NOT EXISTS idxIsolatProbe ON tblIsolat (ProbeID, Positiv, Erregergruppe);
CREATE INDEX IF NOT EXISTS idxHybaseAntibiogrammIsolat ON tblHybaseAntibiogramm (IsolatID, Antibiotikum_Standard, SIR_Standard);
CREATE INDEX IF NOT EXISTS idxRawHybaseIsolatAntibiogrammLinkRaw ON tblRawHybaseIsolatAntibiogrammLink (RawHybaseImportID);
CREATE INDEX IF NOT EXISTS idxRawHybaseIsolatAntibiogrammLinkAB ON tblRawHybaseIsolatAntibiogrammLink (HybaseAntibiogrammID);
CREATE INDEX IF NOT EXISTS idxStudienmodulEpisode ON tblStudienmodulAB (EpisodeID);
CREATE INDEX IF NOT EXISTS idxOutcomeEpisode ON tblOutcome (EpisodeID);
CREATE INDEX IF NOT EXISTS idxFollowUpEpisode ON tblFollowUp (EpisodeID, Datum);
CREATE INDEX IF NOT EXISTS idxEpisodeEBJIS ON tblEpisode (EBJISStatus, DiagnoseDatum);
CREATE INDEX IF NOT EXISTS idxEpisodePhenotype ON tblEpisode (Infektionstyp, Symptombeginn, ABVorProbe);
CREATE INDEX IF NOT EXISTS idxStudienmodulEmpirisch ON tblStudienmodulAB (EpisodeID, EmpirischBewertung, EmpirischAktivGegenErreger);
CREATE INDEX IF NOT EXISTS idxStudienmodulCoverage ON tblStudienmodulAB (EpisodeID, EmpiricalCoverageStatus, ErregerBekanntDatum);
CREATE INDEX IF NOT EXISTS idxOutcomeTyp ON tblOutcome (EpisodeID, OutcomeTyp, Therapieversagen, Rezidiv, Reinfektion);
CREATE INDEX IF NOT EXISTS idxMikrobioScience ON tblMikrobiologie (EingriffID, BefundBekanntDatum, DruckDatum, ResistenzPhaenotyp);
CREATE INDEX IF NOT EXISTS idxHistologieDokumentEpisode ON tblHistologieDokument (EpisodeID, ReviewStatus);
CREATE INDEX IF NOT EXISTS idxOPBerichtDokumentEpisode ON tblOPBerichtDokument (EpisodeID, EingriffID, OPDatum);
CREATE INDEX IF NOT EXISTS idxFieberkurveReview ON tblFieberkurve (ReviewStatus, OCRStatus, EpisodeID);
CREATE INDEX IF NOT EXISTS idxMedKandidatReview ON tblFieberkurveMedikamentKandidat (ReviewStatus, IstAntibiotikum, EpisodeID);
CREATE INDEX IF NOT EXISTS idxFieberkurveKollektivStatus ON tblFieberkurveKollektiv (KollektivName, SAPScreenshotStatus, FieberkurveStatus, Prioritaet);
CREATE INDEX IF NOT EXISTS idxFieberkurveKollektivEpisode ON tblFieberkurveKollektiv (EpisodeID);
CREATE INDEX IF NOT EXISTS idxAntibiotikatherapieEpisode ON tblAntibiotikatherapie (EpisodeID, Therapiephase, Start);
