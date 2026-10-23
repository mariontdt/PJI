#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    from init_db import seed_antibiotics
except ImportError:
    from scripts.init_db import seed_antibiotics

try:
    from episode_model import migrate_episode_model
except ImportError:
    from scripts.episode_model import migrate_episode_model


ROOT = Path(__file__).resolve().parents[1]
LEXICON_PATH = ROOT / "data" / "antibiotics_lexicon.csv"
BUNDLED_PDFTOPPM = Path(
    os.environ.get("PDFTOPPM_PATH")
    or shutil.which("pdftoppm")
    or "/usr/bin/pdftoppm"
)
DEFAULT_TESSERACT_CANDIDATES = (
    Path("/opt/homebrew/bin/tesseract"),
    Path("/usr/local/bin/tesseract"),
    Path("/usr/bin/tesseract"),
)


@dataclass(frozen=True)
class LexiconEntry:
    name_norm: str
    atc: str | None
    klasse: str | None
    terms: tuple[str, ...]


def load_lexicon(path: Path = LEXICON_PATH) -> list[LexiconEntry]:
    entries: list[LexiconEntry] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            terms = [row.get("name_norm", "")]
            terms.extend((row.get("suchbegriffe") or "").split("|"))
            clean_terms = tuple(sorted({t.strip() for t in terms if t.strip()}, key=len, reverse=True))
            entries.append(
                LexiconEntry(
                    name_norm=row.get("name_norm") or "",
                    atc=row.get("atc") or None,
                    klasse=row.get("klasse") or None,
                    terms=clean_terms,
                )
            )
    return entries


def render_pdf_pages(pdf_path: Path, out_dir: Path, pdftoppm: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / pdf_path.stem
    cmd = [str(pdftoppm), "-png", "-r", "220", str(pdf_path), str(prefix)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return sorted(out_dir.glob(f"{pdf_path.stem}-*.png"))


def page_paths(input_path: Path, out_dir: Path, pdftoppm: Path) -> list[Path]:
    if input_path.suffix.lower() == ".pdf":
        return render_pdf_pages(input_path, out_dir, pdftoppm)
    return [input_path]


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size


def find_tesseract(configured: Path | None = None) -> Path | None:
    if configured and configured.exists():
        return configured
    path_value = shutil.which("tesseract")
    if path_value:
        return Path(path_value)
    for candidate in DEFAULT_TESSERACT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def run_tesseract(image_path: Path, language: str, *, psm: int, tesseract_path: Path | None) -> tuple[str, str]:
    tesseract = find_tesseract(tesseract_path)
    if not tesseract:
        return "", "ocr_unavailable"
    cmd = [str(tesseract), str(image_path), "stdout", "--psm", str(psm), "-l", language]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return result.stderr.strip(), "ocr_failed"
    return result.stdout, "ocr_finished"


def prepare_ocr_variants(image_path: Path, out_dir: Path) -> list[tuple[str, Path, int]]:
    """Create OCR variants for fever curves.

    Tesseract struggles with grid-heavy medication curves. Trying a full page plus
    a medication-region crop gives useful text on cleaner SAP exports while still
    preserving a deterministic offline workflow.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    variants: list[tuple[str, Path, int]] = [("full_psm6", image_path, 6), ("full_sparse", image_path, 11)]
    with Image.open(image_path) as im:
        gray = im.convert("L")
        width, height = gray.size
        # Older fever curves place the medication table at different heights.
        # Keep the broad crop and add two tighter lower-left views so handwriting
        # is not dwarfed by the temperature grid and printed form labels.
        crop_specs = (
            ("medication", (0.00, 0.17, 0.55, 0.78)),
            ("medication_middle", (0.00, 0.34, 0.62, 0.82)),
            ("medication_lower", (0.00, 0.48, 0.68, 0.96)),
        )
        for label, (left, top, right, bottom) in crop_specs:
            crop = gray.crop((int(width * left), int(height * top), int(width * right), int(height * bottom)))
            crop = ImageOps.autocontrast(crop)
            crop = ImageEnhance.Contrast(crop).enhance(2.0)
            crop = crop.resize((crop.width * 3, crop.height * 3))
            crop = crop.filter(ImageFilter.SHARPEN)
            crop_path = out_dir / f"{image_path.stem}_{label}_ocr.png"
            crop.save(crop_path)
            variants.extend([(f"{label}_psm6", crop_path, 6), (f"{label}_sparse", crop_path, 11)])

            # A high-contrast variant often recovers product names written over
            # the fine horizontal ruling. It remains only an OCR proposal.
            thresholded = crop.point(lambda pixel: 255 if pixel > 176 else 0)
            threshold_path = out_dir / f"{image_path.stem}_{label}_threshold_ocr.png"
            thresholded.save(threshold_path)
            variants.append((f"{label}_threshold_sparse", threshold_path, 11))
    return variants


def read_ocr_text(path: Path | None) -> str | None:
    if not path:
        return None
    return path.read_text(encoding="utf-8")


def candidate_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term)
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def nearby_dose(line: str) -> str | None:
    match = re.search(r"(\d+(?:[,.]\d+)?\s*(?:mg|g|ml|ie|i\.e\.|mio|µg|mcg))", line, re.IGNORECASE)
    return match.group(1) if match else None


def nearby_interval(line: str) -> str | None:
    match = re.search(r"(\d\s*-\s*\d\s*-\s*\d(?:\s*-\s*\d)?|alle\s+\d+\s*h|1x|2x|3x|4x)", line, re.IGNORECASE)
    return match.group(1) if match else None


def parse_candidates(text: str, entries: Iterable[LexiconEntry]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    seen: set[tuple[str, str | None, str | None, str]] = set()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line_number, line in enumerate(lines, start=1):
        for entry in entries:
            for term in entry.terms:
                if candidate_pattern(term).search(line):
                    key = (entry.name_norm, nearby_dose(line), nearby_interval(line), line[:120])
                    if key in seen:
                        break
                    seen.add(key)
                    candidates.append(
                        {
                            "line_number": line_number,
                            "medikament_raw": term,
                            "medikament_norm": entry.name_norm,
                            "ist_antibiotikum": 1,
                            "dosis": nearby_dose(line),
                            "intervall": nearby_interval(line),
                            "confidence": 0.75,
                            "ocr_text_snippet": line[:500],
                        }
                    )
                    break
    return candidates


def insert_review_packet(db_path: Path, packet: dict[str, object], *, replace_existing: bool = False) -> None:
    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript((ROOT / "schema" / "pji_register_schema.sql").read_text(encoding="utf-8"))
        seed_antibiotics(con)
        migrate_episode_model(con)
        if replace_existing:
            existing_ids = [
                int(row[0])
                for row in con.execute(
                    "SELECT FieberkurveID FROM tblFieberkurve WHERE OriginalPath = ?",
                    (packet["source_path"],),
                ).fetchall()
            ]
            for existing_id in existing_ids:
                con.execute(
                    """
                    DELETE FROM tblFieberkurveMedikamentKandidat
                    WHERE FieberkurveID = ?
                    """,
                    (existing_id,),
                )
                con.execute("DELETE FROM tblFieberkurveSeite WHERE FieberkurveID = ?", (existing_id,))
                con.execute("DELETE FROM tblFieberkurve WHERE FieberkurveID = ?", (existing_id,))
        cur = con.execute(
            """
            INSERT INTO tblFieberkurve (OriginalPath, OCRStatus, ReviewStatus, Kommentar)
            VALUES (?, ?, 'offen', ?)
            """,
            (
                packet["source_path"],
                packet["ocr_status"],
                "Automatisch erzeugtes Review-Paket",
            ),
        )
        fever_id = int(cur.lastrowid)
        page_id_by_index: dict[int, int] = {}
        for page in packet["pages"]:  # type: ignore[index]
            page_cur = con.execute(
                """
                INSERT INTO tblFieberkurveSeite
                    (FieberkurveID, Seite, BildPfad, BreitePx, HoehePx, OCRText, OCRStatus)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fever_id,
                    page["page"],  # type: ignore[index]
                    page["image_path"],  # type: ignore[index]
                    page["width"],  # type: ignore[index]
                    page["height"],  # type: ignore[index]
                    page.get("ocr_text"),  # type: ignore[union-attr]
                    page["ocr_status"],  # type: ignore[index]
                ),
            )
            page_id_by_index[int(page["page"])] = int(page_cur.lastrowid)  # type: ignore[index]
        for candidate in packet["candidates"]:  # type: ignore[index]
            con.execute(
                """
                INSERT INTO tblFieberkurveMedikamentKandidat (
                    FieberkurveID, FieberkurveSeiteID, MedikamentRaw, MedikamentNorm,
                    IstAntibiotikum, Kategorie, Dosis, Intervall, Confidence, OCRTextSnippet
                )
                VALUES (?, ?, ?, ?, ?, 'antibiotikum', ?, ?, ?, ?)
                """,
                (
                    fever_id,
                    page_id_by_index.get(int(candidate["page"])),  # type: ignore[index]
                    candidate["medikament_raw"],  # type: ignore[index]
                    candidate["medikament_norm"],  # type: ignore[index]
                    candidate["ist_antibiotikum"],  # type: ignore[index]
                    candidate.get("dosis"),  # type: ignore[union-attr]
                    candidate.get("intervall"),  # type: ignore[union-attr]
                    candidate.get("confidence"),  # type: ignore[union-attr]
                    candidate.get("ocr_text_snippet"),  # type: ignore[union-attr]
                ),
            )
        con.commit()
    packet["database_fieberkurve_id"] = fever_id


def build_packet(
    input_path: Path,
    out_dir: Path,
    *,
    ocr_text_path: Path | None,
    language: str,
    pdftoppm: Path,
    tesseract_path: Path | None,
) -> dict[str, object]:
    work_dir = out_dir / input_path.stem
    pages = page_paths(input_path, work_dir, pdftoppm)
    entries = load_lexicon()
    supplied_text = read_ocr_text(ocr_text_path)
    packet_pages: list[dict[str, object]] = []
    all_candidates: list[dict[str, object]] = []
    statuses: list[str] = []

    for index, image_path in enumerate(pages, start=1):
        width, height = image_size(image_path)
        if supplied_text is not None:
            text = supplied_text
            status = "ocr_text_supplied"
        else:
            variant_texts: list[str] = []
            variant_statuses: list[str] = []
            for variant_name, variant_path, psm in prepare_ocr_variants(image_path, work_dir / "ocr_variants"):
                variant_text, variant_status = run_tesseract(
                    variant_path,
                    language,
                    psm=psm,
                    tesseract_path=tesseract_path,
                )
                variant_statuses.append(variant_status)
                if variant_text.strip():
                    variant_texts.append(f"--- {variant_name} ---\n{variant_text.strip()}")
            text = "\n".join(variant_texts)
            if variant_statuses and all(s == "ocr_finished" for s in variant_statuses):
                status = "ocr_finished"
            elif any(s == "ocr_finished" for s in variant_statuses):
                status = "ocr_partial"
            elif any(s == "ocr_unavailable" for s in variant_statuses):
                status = "ocr_unavailable"
            else:
                status = "ocr_failed"
        statuses.append(status)
        page_candidates = parse_candidates(text, entries) if text and status != "ocr_unavailable" else []
        for candidate in page_candidates:
            candidate["page"] = index
        all_candidates.extend(page_candidates)
        packet_pages.append(
            {
                "page": index,
                "image_path": str(image_path),
                "width": width,
                "height": height,
                "ocr_status": status,
                "ocr_text": text if text else None,
            }
        )

    if statuses and all(status == "ocr_finished" for status in statuses):
        ocr_status = "ocr_finished"
    elif any(status == "ocr_text_supplied" for status in statuses):
        ocr_status = "ocr_text_supplied"
    elif any(status == "ocr_unavailable" for status in statuses):
        ocr_status = "ocr_unavailable"
    else:
        ocr_status = "ocr_partial"

    return {
        "source_path": str(input_path),
        "ocr_status": ocr_status,
        "pages": packet_pages,
        "candidates": all_candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare fever-curve PDFs/images for medication review.")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--out", default=Path("outputs/review_packets"), type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--ocr-text", type=Path, help="Optional OCR text file to parse instead of running OCR.")
    parser.add_argument("--language", default="deu+eng")
    parser.add_argument("--pdftoppm", default=BUNDLED_PDFTOPPM, type=Path)
    parser.add_argument("--tesseract", type=Path, help="Optional path to the tesseract binary.")
    parser.add_argument("--replace-existing", action="store_true", help="Replace existing review rows for this source path.")
    args = parser.parse_args()

    if args.input_path.suffix.lower() == ".pdf" and not args.pdftoppm.exists():
        raise SystemExit(f"pdftoppm not found: {args.pdftoppm}")

    args.out.mkdir(parents=True, exist_ok=True)
    packet = build_packet(
        args.input_path,
        args.out,
        ocr_text_path=args.ocr_text,
        language=args.language,
        pdftoppm=args.pdftoppm,
        tesseract_path=args.tesseract,
    )
    if args.db:
        insert_review_packet(args.db, packet, replace_existing=args.replace_existing)

    packet_path = args.out / f"{args.input_path.stem}_review_packet.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Review packet: {packet_path}")
    print(f"OCR status: {packet['ocr_status']}")
    print(f"Medication candidates: {len(packet['candidates'])}")


if __name__ == "__main__":
    main()
