from __future__ import annotations

import sqlite3


def table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}


def add_column_if_missing(con: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in table_columns(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate_episode_model(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA foreign_keys = ON")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS tblEpisode (
            EpisodeID INTEGER PRIMARY KEY,
            GelenkFallID INTEGER NOT NULL,
            EpisodeTyp TEXT NOT NULL DEFAULT 'PJI',
            EpisodeBeginn TEXT,
            EpisodeEnde TEXT,
            DiagnoseDatum TEXT,
            PJIKlassifikation TEXT,
            Diagnosekriterien TEXT,
            Kommentar TEXT,
            Quelle TEXT,
            CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (GelenkFallID) REFERENCES tblGelenkFall(GelenkFallID)
        )
        """
    )
    add_column_if_missing(con, "tblAufenthalt", "EpisodeID", "INTEGER REFERENCES tblEpisode(EpisodeID)")
    add_column_if_missing(con, "tblStudienmodulAB", "EpisodeID", "INTEGER REFERENCES tblEpisode(EpisodeID)")
    add_column_if_missing(con, "tblOutcome", "EpisodeID", "INTEGER REFERENCES tblEpisode(EpisodeID)")
    add_column_if_missing(con, "tblFieberkurve", "EpisodeID", "INTEGER REFERENCES tblEpisode(EpisodeID)")
    add_column_if_missing(
        con,
        "tblFieberkurveMedikamentKandidat",
        "EpisodeID",
        "INTEGER REFERENCES tblEpisode(EpisodeID)",
    )
    add_column_if_missing(con, "tblAntibiotikaGabe", "EpisodeID", "INTEGER REFERENCES tblEpisode(EpisodeID)")
    add_column_if_missing(con, "tblPatient", "HYBASEPatientID_Raw", "TEXT")
    add_column_if_missing(con, "tblPatient", "HYBASEPatientHash", "TEXT")
    add_column_if_missing(con, "tblGelenkFall", "PrimaerimplantationAuswaerts", "INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing(con, "tblGelenkFall", "PrimaerimplantationOrt", "TEXT")
    add_column_if_missing(con, "tblGelenkFall", "PrimaerimplantationKommentar", "TEXT")

    con.execute(
        """
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
            Kommentar TEXT,
            Quelle TEXT,
            CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID)
        )
        """
    )
    con.execute(
        """
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
        )
        """
    )
    con.execute(
        """
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
        )
        """
    )
    con.execute(
        """
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
        )
        """
    )
    add_column_if_missing(con, "tblRawHybaseImport", "LaborauftragID", "INTEGER REFERENCES tblLaborauftrag(LaborauftragID)")
    add_column_if_missing(con, "tblRawHybaseImport", "ProbeID", "INTEGER REFERENCES tblProbe(ProbeID)")
    add_column_if_missing(con, "tblRawHybaseImport", "IsolatID", "INTEGER REFERENCES tblIsolat(IsolatID)")
    add_column_if_missing(
        con,
        "tblRawHybaseImport",
        "HybaseAntibiogrammID",
        "INTEGER REFERENCES tblHybaseAntibiogramm(HybaseAntibiogrammID)",
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS tblRawHybaseAntibiogrammLink (
            RawHybaseAntibiogrammLinkID INTEGER PRIMARY KEY,
            RawHybaseImportID INTEGER NOT NULL,
            AntibiogrammID INTEGER NOT NULL,
            AntibiotikumSpalte TEXT,
            CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (RawHybaseImportID) REFERENCES tblRawHybaseImport(RawHybaseImportID),
            FOREIGN KEY (AntibiogrammID) REFERENCES tblAntibiogramm(AntibiogrammID)
        )
        """
    )
    create_structured_hybase_tables(con)
    con.execute(
        """
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
        )
        """
    )
    con.execute(
        """
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
            ReviewStatus TEXT NOT NULL DEFAULT 'offen',
            Reviewer TEXT,
            Kommentar TEXT,
            Quelle TEXT,
            CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (EpisodeID) REFERENCES tblEpisode(EpisodeID),
            FOREIGN KEY (EingriffID) REFERENCES tblEingriff(EingriffID),
            FOREIGN KEY (KandidatID) REFERENCES tblFieberkurveMedikamentKandidat(KandidatID)
        )
        """
    )

    create_placeholder_episodes(con)
    backfill_episode_links(con)
    backfill_episode_level_therapy(con)
    create_episode_indexes(con)


def create_placeholder_episodes(con: sqlite3.Connection) -> None:
    con.execute(
        """
        INSERT INTO tblEpisode (GelenkFallID, EpisodeTyp, EpisodeBeginn, Kommentar, Quelle)
        SELECT
            g.GelenkFallID,
            'Registerepisode',
            COALESCE(
                g.PrimaerimplantationDatum,
                (
                    SELECT MIN(e.OPDatum)
                    FROM tblAufenthalt a
                    JOIN tblEingriff e ON e.AufenthaltID = a.AufenthaltID
                    WHERE a.GelenkFallID = g.GelenkFallID
                )
            ),
            'Automatisch aus Bestandsdaten erzeugt; PJI-Episode fachlich pruefen.',
            'Migration'
        FROM tblGelenkFall g
        WHERE NOT EXISTS (
            SELECT 1
            FROM tblEpisode ep
            WHERE ep.GelenkFallID = g.GelenkFallID
        )
        """
    )


def backfill_episode_links(con: sqlite3.Connection) -> None:
    con.execute(
        """
        UPDATE tblAufenthalt
        SET EpisodeID = (
            SELECT ep.EpisodeID
            FROM tblEpisode ep
            WHERE ep.GelenkFallID = tblAufenthalt.GelenkFallID
            ORDER BY ep.EpisodeBeginn IS NULL, ep.EpisodeBeginn, ep.EpisodeID
            LIMIT 1
        )
        WHERE EpisodeID IS NULL
        """
    )
    con.execute(
        """
        UPDATE tblStudienmodulAB
        SET EpisodeID = (
            SELECT a.EpisodeID
            FROM tblEingriff e
            JOIN tblAufenthalt a ON a.AufenthaltID = e.AufenthaltID
            WHERE e.EingriffID = tblStudienmodulAB.EingriffID
        )
        WHERE EpisodeID IS NULL AND EingriffID IS NOT NULL
        """
    )
    con.execute(
        """
        UPDATE tblOutcome
        SET EpisodeID = (
            SELECT a.EpisodeID
            FROM tblEingriff e
            JOIN tblAufenthalt a ON a.AufenthaltID = e.AufenthaltID
            WHERE e.EingriffID = tblOutcome.EingriffID
        )
        WHERE EpisodeID IS NULL AND EingriffID IS NOT NULL
        """
    )
    con.execute(
        """
        UPDATE tblFieberkurve
        SET EpisodeID = COALESCE(
            (
                SELECT a.EpisodeID
                FROM tblEingriff e
                JOIN tblAufenthalt a ON a.AufenthaltID = e.AufenthaltID
                WHERE e.EingriffID = tblFieberkurve.EingriffID
            ),
            (
                SELECT a.EpisodeID
                FROM tblAufenthalt a
                WHERE a.AufenthaltID = tblFieberkurve.AufenthaltID
            )
        )
        WHERE EpisodeID IS NULL
        """
    )
    con.execute(
        """
        UPDATE tblFieberkurveMedikamentKandidat
        SET EpisodeID = COALESCE(
            (
                SELECT f.EpisodeID
                FROM tblFieberkurve f
                WHERE f.FieberkurveID = tblFieberkurveMedikamentKandidat.FieberkurveID
            ),
            (
                SELECT a.EpisodeID
                FROM tblEingriff e
                JOIN tblAufenthalt a ON a.AufenthaltID = e.AufenthaltID
                WHERE e.EingriffID = tblFieberkurveMedikamentKandidat.EingriffID
            )
        )
        WHERE EpisodeID IS NULL
        """
    )
    con.execute(
        """
        UPDATE tblAntibiotikaGabe
        SET EpisodeID = (
            SELECT a.EpisodeID
            FROM tblEingriff e
            JOIN tblAufenthalt a ON a.AufenthaltID = e.AufenthaltID
            WHERE e.EingriffID = tblAntibiotikaGabe.EingriffID
        )
        WHERE EpisodeID IS NULL AND EingriffID IS NOT NULL
        """
    )


def backfill_episode_level_therapy(con: sqlite3.Connection) -> None:
    con.execute(
        """
        INSERT INTO tblAntibiotikatherapie (
            EpisodeID, EingriffID, KandidatID, Therapiephase, Antibiotikum,
            Dosis, Start, Ende, Kommentar, Reviewer, ReviewStatus, Quelle
        )
        SELECT
            EpisodeID, EingriffID, KandidatID, Therapiephase, Antibiotikum,
            Dosis, Start, Ende, Kommentar, Reviewer, 'bestaetigt', 'tblAntibiotikaGabe'
        FROM tblAntibiotikaGabe ag
        WHERE EpisodeID IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM tblAntibiotikatherapie t
              WHERE t.KandidatID = ag.KandidatID
                AND ag.KandidatID IS NOT NULL
          )
        """
    )
    con.execute(
        """
        INSERT INTO tblAntibiotikatherapie (
            EpisodeID, EingriffID, Therapiephase, Antibiotikum, Start, Ende,
            Kommentar, Reviewer, ReviewStatus, Quelle
        )
        SELECT
            EpisodeID, EingriffID, 'empirisch', EmpirischeAB, EmpirischeStart,
            EmpirischeEnde, Kommentar, Reviewer, 'bestaetigt', 'tblStudienmodulAB'
        FROM tblStudienmodulAB s
        WHERE EpisodeID IS NOT NULL
          AND EmpirischeAB IS NOT NULL
          AND EmpirischeAB <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM tblAntibiotikatherapie t
              WHERE t.EpisodeID = s.EpisodeID
                AND t.Therapiephase = 'empirisch'
                AND t.Antibiotikum = s.EmpirischeAB
                AND COALESCE(t.Start, '') = COALESCE(s.EmpirischeStart, '')
          )
        """
    )
    con.execute(
        """
        INSERT INTO tblAntibiotikatherapie (
            EpisodeID, EingriffID, Therapiephase, Antibiotikum, Start, Ende,
            Kommentar, Reviewer, ReviewStatus, Quelle
        )
        SELECT
            EpisodeID, EingriffID, 'gezielt', GezielteAB, GezielteStart,
            GezielteEnde, Kommentar, Reviewer, 'bestaetigt', 'tblStudienmodulAB'
        FROM tblStudienmodulAB s
        WHERE EpisodeID IS NOT NULL
          AND GezielteAB IS NOT NULL
          AND GezielteAB <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM tblAntibiotikatherapie t
              WHERE t.EpisodeID = s.EpisodeID
                AND t.Therapiephase = 'gezielt'
                AND t.Antibiotikum = s.GezielteAB
                AND COALESCE(t.Start, '') = COALESCE(s.GezielteStart, '')
          )
        """
    )


def create_structured_hybase_tables(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS mapMaterial (
            MapMaterialID INTEGER PRIMARY KEY,
            Material_Raw TEXT NOT NULL UNIQUE,
            Material_Standard TEXT NOT NULL,
            Kommentar TEXT,
            Aktiv INTEGER NOT NULL DEFAULT 1,
            CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.execute(
        """
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
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS mapAntibiotikum (
            MapAntibiotikumID INTEGER PRIMARY KEY,
            Antibiotikum_Raw TEXT NOT NULL UNIQUE,
            Antibiotikum_Standard TEXT NOT NULL,
            Antibiotikaklasse TEXT,
            Spezialtest TEXT,
            Kommentar TEXT,
            Aktiv INTEGER NOT NULL DEFAULT 1,
            CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.execute(
        """
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
        )
        """
    )
    con.execute(
        """
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
        )
        """
    )
    con.execute(
        """
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
        )
        """
    )
    con.execute(
        """
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
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS tblRawHybaseIsolatAntibiogrammLink (
            RawHybaseIsolatAntibiogrammLinkID INTEGER PRIMARY KEY,
            RawHybaseImportID INTEGER NOT NULL,
            HybaseAntibiogrammID INTEGER NOT NULL,
            AntibiotikumSpalte TEXT,
            CreatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (RawHybaseImportID) REFERENCES tblRawHybaseImport(RawHybaseImportID),
            FOREIGN KEY (HybaseAntibiogrammID) REFERENCES tblHybaseAntibiogramm(HybaseAntibiogrammID)
        )
        """
    )


def create_episode_indexes(con: sqlite3.Connection) -> None:
    con.execute("CREATE INDEX IF NOT EXISTS idxEpisodeGelenkFall ON tblEpisode (GelenkFallID, EpisodeBeginn)")
    con.execute("CREATE INDEX IF NOT EXISTS idxAufenthaltEpisode ON tblAufenthalt (EpisodeID)")
    con.execute("CREATE INDEX IF NOT EXISTS idxStudienmodulEpisode ON tblStudienmodulAB (EpisodeID)")
    con.execute("CREATE INDEX IF NOT EXISTS idxOutcomeEpisode ON tblOutcome (EpisodeID)")
    con.execute("CREATE INDEX IF NOT EXISTS idxFollowUpEpisode ON tblFollowUp (EpisodeID, Datum)")
    con.execute("CREATE INDEX IF NOT EXISTS idxAntibiotikatherapieEpisode ON tblAntibiotikatherapie (EpisodeID, Therapiephase, Start)")
    con.execute("CREATE INDEX IF NOT EXISTS idxLaborWertEpisodeParameter ON tblLaborWert (EpisodeID, Parameter, Datum)")
    con.execute("CREATE INDEX IF NOT EXISTS idxLaborWertFallHash ON tblLaborWert (FallHash, Parameter, Datum)")
    con.execute("CREATE INDEX IF NOT EXISTS idxRawLabBatch ON tblRawLabImport (ImportBatchID, Parameter)")
    con.execute("CREATE INDEX IF NOT EXISTS idxRawHybaseBatch ON tblRawHybaseImport (ImportBatchID)")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idxRawHybaseAntibiogrammLinkRaw ON tblRawHybaseAntibiogrammLink (RawHybaseImportID)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idxRawHybaseAntibiogrammLinkAB ON tblRawHybaseAntibiogrammLink (AntibiogrammID)"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idxLaborauftragLaborNr ON tblLaborauftrag (LaborNr_Raw, Auftragsdatum)")
    con.execute("CREATE INDEX IF NOT EXISTS idxLaborauftragPatient ON tblLaborauftrag (PatientID, Auftragsdatum)")
    con.execute("CREATE INDEX IF NOT EXISTS idxProbeLaborauftrag ON tblProbe (LaborauftragID, Material_Standard)")
    con.execute("CREATE INDEX IF NOT EXISTS idxProbeLinking ON tblProbe (EpisodeID, EingriffID, PJI_Relevanz_Vorlaeufig)")
    con.execute("CREATE INDEX IF NOT EXISTS idxIsolatProbe ON tblIsolat (ProbeID, Positiv, Erregergruppe)")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idxHybaseAntibiogrammIsolat "
        "ON tblHybaseAntibiogramm (IsolatID, Antibiotikum_Standard, SIR_Standard)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idxRawHybaseIsolatAntibiogrammLinkRaw "
        "ON tblRawHybaseIsolatAntibiogrammLink (RawHybaseImportID)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idxRawHybaseIsolatAntibiogrammLinkAB "
        "ON tblRawHybaseIsolatAntibiogrammLink (HybaseAntibiogrammID)"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idxHistologieDokumentEpisode ON tblHistologieDokument (EpisodeID, ReviewStatus)")
