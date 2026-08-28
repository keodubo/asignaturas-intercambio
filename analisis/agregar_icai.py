#!/usr/bin/env python3
from __future__ import annotations

import csv
import glob
import json
from pathlib import Path


BASE = Path(__file__).parent.parent
CHUNK_DIR = BASE / "analisis" / "outputs" / "raw"
ICAI_CATALOG_PATH = BASE / "analisis" / "inputs" / "icai_catalogo.json"
ITBA_TARGETS_PATH = BASE / "analisis" / "inputs" / "itba_targets.json"
RESULTS_DIR = BASE / "resultados"

BUCKET_ORDER = {
    "primary": 0,
    "strong_candidate": 1,
    "conditional": 2,
    "backup_only": 3,
}

AVAILABILITY_ORDER = {
    "exchange_term": 0,
    "exchange_term_all_year": 1,
    "full_year": 1,
    "not_in_exchange_term": 2,
    "unknown": 3,
}

PERMISSION_ORDER = {
    "standard": 0,
    "permission_required": 1,
}

CSV_FIELDS = [
    "codigo_icai", "nombre_icai", "term", "studies", "degree", "schedule",
    "language", "ects_icai", "codigo_itba", "nombre_itba", "confianza",
    "comentario", "availability_label", "timing_risk_label", "level_label",
    "permission_label", "language_label", "schedule_label",
    "recommendation_bucket", "source_label", "program_label", "source_url",
    "url_guia_icai",
]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_chunks() -> list[dict]:
    matches = []
    for chunk_file in sorted(glob.glob(str(CHUNK_DIR / "icai_chunk_*.json"))):
        matches.extend(load_json(Path(chunk_file)))
    return matches


def recommendation_bucket(term: str, studies: str, confianza: int) -> str:
    if term == "Spring" or confianza <= 2:
        return "backup_only"
    if studies == "Master":
        return "conditional"
    if term in {"Fall", "Fall/Spring"} and confianza >= 4:
        return "primary"
    if term in {"Fall", "Fall/Spring"} and confianza == 3:
        return "strong_candidate"
    if term in {"All-year", "Full-year"} and confianza >= 4:
        return "strong_candidate"
    if term in {"All-year", "Full-year"}:
        return "conditional"
    return "backup_only"


def sort_recommendations(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (
        BUCKET_ORDER.get(r["recommendation_bucket"], 99),
        -int(r["confianza"]),
        AVAILABILITY_ORDER.get(r["availability_label"], 99),
        PERMISSION_ORDER.get(r["permission_label"], 99),
        r["codigo_icai"],
    ))


def course_priority(course: dict) -> tuple:
    labels = course.get("labels", {})
    return (
        AVAILABILITY_ORDER.get(labels.get("availability", "unknown"), 99),
        PERMISSION_ORDER.get(labels.get("permission", "permission_required"), 99),
        course.get("term", ""),
        course.get("studies", ""),
        course.get("degree", ""),
        course.get("nombre", ""),
    )


def build_icai_by_code(catalog: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for course in catalog:
        grouped.setdefault(course["codigo"], []).append(course)
    return {code: sorted(courses, key=course_priority)[0] for code, courses in grouped.items()}


def build_itba_by_code(targets: list[dict]) -> dict[str, dict]:
    return {course["codigo"]: course for course in targets}


def row_from_match(match: dict, icai_by_code: dict, itba_by_code: dict) -> dict:
    icai = icai_by_code[match["codigo_icai"]]
    itba = itba_by_code[match["codigo_itba"]]
    labels = icai.get("labels", {})
    confianza = int(match.get("confianza", 0))
    bucket = recommendation_bucket(icai.get("term", ""), icai.get("studies", ""), confianza)
    return {
        "codigo_icai": icai["codigo"],
        "nombre_icai": icai["nombre"],
        "term": icai.get("term", ""),
        "studies": icai.get("studies", ""),
        "degree": icai.get("degree", ""),
        "schedule": icai.get("schedule", ""),
        "language": icai.get("language", ""),
        "ects_icai": icai.get("ects_semester", icai.get("ects", "")),
        "codigo_itba": itba["codigo"],
        "nombre_itba": itba["nombre"],
        "confianza": confianza,
        "comentario": match.get("comentario", ""),
        "availability_label": labels.get("availability", ""),
        "timing_risk_label": labels.get("timing_risk", ""),
        "level_label": labels.get("level", ""),
        "permission_label": labels.get("permission", ""),
        "language_label": labels.get("language", ""),
        "schedule_label": labels.get("schedule", ""),
        "recommendation_bucket": bucket,
        "source_label": icai.get("source_label", ""),
        "program_label": icai.get("program_label", ""),
        "source_url": icai.get("source_url", ""),
        "url_guia_icai": icai.get("url_guia", ""),
    }


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_sin_equivalencia(path: Path, itba_targets: list[dict], matched_codes: set[str]) -> int:
    rows = []
    for course in sorted(itba_targets, key=lambda c: c["codigo"]):
        if course["codigo"] in matched_codes:
            continue
        rows.append({
            "codigo_itba": course["codigo"],
            "nombre_itba": course["nombre"],
            "contenidos_minimos": course.get("contenidos_minimos", ""),
            "comentario": "Sin candidato ICAI con suficiente solapamiento tematico en el universo analizado.",
        })
    write_csv(path, rows, ["codigo_itba", "nombre_itba", "contenidos_minimos", "comentario"])
    return len(rows)


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    catalog = load_json(ICAI_CATALOG_PATH)
    itba_targets = load_json(ITBA_TARGETS_PATH)
    matches = [m for m in load_chunks() if int(m.get("confianza", 0)) >= 2]

    icai_by_code = build_icai_by_code(catalog)
    itba_by_code = build_itba_by_code(itba_targets)

    rows = []
    for match in matches:
        if match["codigo_icai"] not in icai_by_code:
            raise KeyError(f"codigo_icai no encontrado: {match['codigo_icai']}")
        if match["codigo_itba"] not in itba_by_code:
            raise KeyError(f"codigo_itba no encontrado: {match['codigo_itba']}")
        rows.append(row_from_match(match, icai_by_code, itba_by_code))

    rows = sort_recommendations(rows)
    write_csv(RESULTS_DIR / "icai_equivalencias.csv", rows, CSV_FIELDS)
    write_csv(RESULTS_DIR / "icai_recomendaciones.csv", rows, CSV_FIELDS)
    unmatched_count = write_sin_equivalencia(
        RESULTS_DIR / "icai_sin_equivalencia.csv",
        itba_targets,
        {row["codigo_itba"] for row in rows},
    )

    print(f"OK icai_equivalencias.csv - {len(rows)} filas")
    print(f"OK icai_sin_equivalencia.csv - {unmatched_count} filas")
    print(f"OK icai_recomendaciones.csv - {len(rows)} filas")


if __name__ == "__main__":
    main()
