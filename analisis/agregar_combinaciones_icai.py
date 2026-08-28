#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path


BASE = Path(__file__).parent.parent
RAW_COMBINATIONS = BASE / "analisis" / "outputs" / "raw" / "icai_combinaciones.json"
ICAI_CATALOG_PATH = BASE / "analisis" / "inputs" / "icai_catalogo.json"
ITBA_TARGETS_PATH = BASE / "analisis" / "inputs" / "itba_targets.json"
ICAI_EQ_PATH = BASE / "resultados" / "icai_equivalencias.csv"
RESULTS_DIR = BASE / "resultados"
OUT_CSV = RESULTS_DIR / "icai_combinaciones.csv"

CSV_FIELDS = [
    "codigo_icai_1", "nombre_icai_1", "term_1", "studies_1", "ects_icai_1",
    "confianza_individual_1",
    "codigo_icai_2", "nombre_icai_2", "term_2", "studies_2", "ects_icai_2",
    "confianza_individual_2",
    "ects_total", "codigo_itba", "nombre_itba", "confianza_combinada",
    "comentario_combinacion", "complementa_por", "gaps_restantes",
    "availability_pair_label", "permission_pair_label", "source_labels",
    "url_guia_icai_1", "url_guia_icai_2",
]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def availability_pair_label(first: str, second: str) -> str:
    if first == second:
        return first or "unknown"
    return "mixed_or_risky"


def permission_pair_label(first: str, second: str) -> str:
    if "permission_required" in {first, second}:
        return "permission_required"
    if first == second:
        return first or "unknown"
    return "mixed_or_risky"


def build_by_code(rows: list[dict]) -> dict[str, dict]:
    return {str(row["codigo"]): row for row in rows}


def build_individual_confidences(path: Path) -> dict[tuple[str, str], int]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        out = {}
        for row in rows:
            confianza = safe_int(row.get("confianza"))
            if confianza is None:
                continue
            out[(str(row.get("codigo_icai", "")), str(row.get("codigo_itba", "")))] = confianza
        return out


def row_from_combination(
    combo: dict,
    icai_by_code: dict[str, dict],
    itba_by_code: dict[str, dict],
    individual_confidences: dict[tuple[str, str], int],
) -> dict:
    code_1 = str(combo["codigo_icai_1"])
    code_2 = str(combo["codigo_icai_2"])
    codigo_itba = str(combo["codigo_itba"])
    confianza_combinada = safe_int(combo.get("confianza_combinada"))
    if confianza_combinada is None or confianza_combinada < 4:
        raise ValueError("confianza_combinada debe ser >= 4")

    individual_1 = individual_confidences.get((code_1, codigo_itba))
    individual_2 = individual_confidences.get((code_2, codigo_itba))
    if individual_1 not in {2, 3} or individual_2 not in {2, 3}:
        raise ValueError("ambas confianzas individuales deben ser 2 o 3")

    icai_1 = icai_by_code[code_1]
    icai_2 = icai_by_code[code_2]
    itba = itba_by_code[codigo_itba]
    labels_1 = icai_1.get("labels", {})
    labels_2 = icai_2.get("labels", {})
    ects_1 = safe_float(icai_1.get("ects"))
    ects_2 = safe_float(icai_2.get("ects"))
    ects_total = None if ects_1 is None or ects_2 is None else ects_1 + ects_2
    source_labels = sorted({
        label for label in [icai_1.get("source_label", ""), icai_2.get("source_label", "")]
        if label
    })

    return {
        "codigo_icai_1": code_1,
        "nombre_icai_1": icai_1.get("nombre", ""),
        "term_1": icai_1.get("term", ""),
        "studies_1": icai_1.get("studies", ""),
        "ects_icai_1": "" if ects_1 is None else ects_1,
        "confianza_individual_1": individual_1,
        "codigo_icai_2": code_2,
        "nombre_icai_2": icai_2.get("nombre", ""),
        "term_2": icai_2.get("term", ""),
        "studies_2": icai_2.get("studies", ""),
        "ects_icai_2": "" if ects_2 is None else ects_2,
        "confianza_individual_2": individual_2,
        "ects_total": "" if ects_total is None else ects_total,
        "codigo_itba": codigo_itba,
        "nombre_itba": itba.get("nombre", ""),
        "confianza_combinada": confianza_combinada,
        "comentario_combinacion": combo.get("comentario_combinacion", ""),
        "complementa_por": combo.get("complementa_por", ""),
        "gaps_restantes": combo.get("gaps_restantes", ""),
        "availability_pair_label": availability_pair_label(
            labels_1.get("availability", ""),
            labels_2.get("availability", ""),
        ),
        "permission_pair_label": permission_pair_label(
            labels_1.get("permission", ""),
            labels_2.get("permission", ""),
        ),
        "source_labels": ",".join(source_labels),
        "url_guia_icai_1": icai_1.get("url_guia", ""),
        "url_guia_icai_2": icai_2.get("url_guia", ""),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not RAW_COMBINATIONS.exists():
        raise SystemExit(
            f"Falta {RAW_COMBINATIONS}. Ejecuta primero el prompt "
            "analisis/prompts/icai_combinaciones.md."
        )

    RESULTS_DIR.mkdir(exist_ok=True)
    icai_by_code = build_by_code(load_json(ICAI_CATALOG_PATH))
    itba_by_code = build_by_code(load_json(ITBA_TARGETS_PATH))
    individual = build_individual_confidences(ICAI_EQ_PATH)

    rows = []
    skipped = 0
    for combo in load_json(RAW_COMBINATIONS):
        try:
            rows.append(row_from_combination(combo, icai_by_code, itba_by_code, individual))
        except (KeyError, ValueError):
            skipped += 1

    rows.sort(key=lambda r: (
        r["codigo_itba"],
        -int(r["confianza_combinada"]),
        r["codigo_icai_1"],
        r["codigo_icai_2"],
    ))
    write_csv(OUT_CSV, rows)
    print(f"OK {OUT_CSV.name}: {len(rows)} filas ({skipped} omitidas)")


if __name__ == "__main__":
    main()
