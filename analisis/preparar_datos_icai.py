#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path


CHUNK_SIZE = 20
PROJECT_ROOT = Path(__file__).parent.parent
ITBA_CSV = PROJECT_ROOT / "itba_info" / "materias_filtradas_detallado.csv"
ICAI_CSV = PROJECT_ROOT / "icai" / "extraccion_materias" / "icai_catalogo.csv"
ICAI_CONTENIDOS = PROJECT_ROOT / "icai" / "guias_docentes" / "contenidos.json"
OUTPUT_INPUTS = PROJECT_ROOT / "analisis" / "inputs"
OUTPUT_PROMPTS = PROJECT_ROOT / "analisis" / "prompts"
OUTPUT_RAW = PROJECT_ROOT / "analisis" / "outputs" / "raw"


def parse_float(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def recommendation_bucket_for_prompt(term: str, studies: str, confianza: int) -> str:
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


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_icai_catalogo(csv_path: Path = ICAI_CSV, contenidos_path: Path = ICAI_CONTENIDOS) -> list[dict]:
    contenidos = load_json(contenidos_path)
    out = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["codigo"]
            syllabus_links = json.loads(row.get("syllabus_links_json") or "[]")
            guia = contenidos.get(code, {})
            out.append({
                "codigo": code,
                "nombre": row["nombre"],
                "institucion": "icai_comillas",
                "term": row["term"],
                "studies": row["studies"],
                "degree": row["degree"],
                "schedule": row["schedule"],
                "language": row["language"],
                "ects": parse_float(row["ects"]),
                "ects_semester": parse_float(row.get("ects_semester")) or parse_float(row["ects"]),
                "note_comment": row.get("note_comment", ""),
                "url_guia": row["url_guia"],
                "source_label": row.get("source_label", "exchange_catalog"),
                "program_label": row.get("program_label", "regular_icai"),
                "source_url": row.get("source_url", ""),
                "source_file": row.get("source_file", ""),
                "syllabus_links": syllabus_links,
                "guia": guia,
                "labels": {
                    "availability": row["availability_label"],
                    "timing_risk": row["timing_risk_label"],
                    "level": row["level_label"],
                    "permission": row["permission_label"],
                    "language": row["language_label"],
                    "schedule": row["schedule_label"],
                },
            })
    return out


def load_itba_targets() -> list[dict]:
    targets = []
    with ITBA_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            targets.append({
                "codigo": row["codigo"],
                "nombre": row["nombre"],
                "contenidos_minimos": row["contenidos_minimos"] or None,
                "objetivos_aprendizaje": row["objetivos_aprendizaje"] or None,
            })
    return targets


def partition(items: list[dict], size: int) -> list[list[dict]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def cap_text(value, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def compact_icai_for_prompt(catalogo: list[dict]) -> list[dict]:
    compact = []
    for course in catalogo:
        guia = course.get("guia") or {}
        compact.append({
            "codigo": course["codigo"],
            "nombre": course["nombre"],
            "term": course["term"],
            "studies": course["studies"],
            "degree": course["degree"],
            "schedule": course["schedule"],
            "language": course["language"],
            "ects": course["ects"],
            "ects_semester": course.get("ects_semester"),
            "note_comment": course.get("note_comment", ""),
            "url_guia": course["url_guia"],
            "source_label": course.get("source_label", ""),
            "program_label": course.get("program_label", ""),
            "source_url": course.get("source_url", ""),
            "labels": course["labels"],
            "guia": {
                "descripcion": cap_text(guia.get("descripcion", ""), 1200),
                "competencias": cap_text(guia.get("competencias", ""), 1000),
                "contenidos": cap_text(guia.get("contenidos", ""), 1800),
                "metodologia": cap_text(guia.get("metodologia", ""), 400),
                "evaluacion": cap_text(guia.get("evaluacion", ""), 400),
                "bibliografia": cap_text(guia.get("bibliografia", ""), 250),
            },
        })
    return compact


def write_itba_targets(targets: list[dict]) -> None:
    (OUTPUT_INPUTS / "itba_targets.json").write_text(
        json.dumps(targets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_prompts(catalogo: list[dict], chunks: list[list[dict]]) -> None:
    catalogo_json = json.dumps(compact_icai_for_prompt(catalogo), ensure_ascii=False, indent=2)
    for i, chunk in enumerate(chunks, 1):
        chunk_num = f"{i:02d}"
        chunk_json = json.dumps(chunk, ensure_ascii=False, indent=2)
        prompt = f"""# ICAI Chunk {chunk_num} - Analisis de equivalencias ITBA -> ICAI/Comillas

Sos un experto en planes de estudio de Ingenieria Informatica.
Tu tarea: para cada materia ITBA del bloque, identificar materias ICAI/Comillas cuyo temario solape suficiente como para ser candidata a equivalencia.

## Reglas de universo

El catálogo proviene exclusivamente de Course Offering 2026-2027 Student Version 1.1 e incluye solo Fall y All-year visibles; Undergraduate y Master; materias en inglés y español.
No propongas ninguna materia que no esté en este catálogo:
- Fall = cursable en el intercambio septiembre-diciembre.
- All-year = cursable durante Fall, pero vale la mitad de los ECTS por semestre.
- Master = puede requerir permiso para estudiante de exchange undergraduate.
- SAPIENS = programa específico para international engineering students incluido en el mismo Excel oficial.

## Rubrica de confianza

- 5 = equivalente directa, casi 1:1
- 4 = buena, gaps menores
- 3 = parcial-fuerte
- 2 = parcial-debil
- 1 = marginal, no incluir
- 0 = no equivalente, no incluir

## Catálogo ICAI completo

```json
{catalogo_json}
```

## Materias ITBA del chunk

```json
{chunk_json}
```

## Output

Escribir `analisis/outputs/raw/icai_chunk_{chunk_num}.json` con un array JSON.
Cada elemento debe tener exactamente:

```json
{{
  "codigo_icai": "DTC-MIC-523",
  "codigo_itba": "72.44",
  "confianza": 4,
  "comentario": "ICAI cubre seguridad de aplicaciones y ciberseguridad; ITBA pide criptografia, seguridad y protocolos. Es Master y requiere permiso."
}}
```

Solo emitir confianza >= 2.
Devolver: "ICAI chunk {chunk_num} listo, M matches encontrados."
"""
        (OUTPUT_PROMPTS / f"icai_chunk_{chunk_num}.md").write_text(prompt, encoding="utf-8")


def main() -> None:
    OUTPUT_INPUTS.mkdir(parents=True, exist_ok=True)
    OUTPUT_PROMPTS.mkdir(parents=True, exist_ok=True)
    OUTPUT_RAW.mkdir(parents=True, exist_ok=True)
    catalogo = load_icai_catalogo()
    targets = load_itba_targets()
    chunks = partition(targets, CHUNK_SIZE)
    (OUTPUT_INPUTS / "icai_catalogo.json").write_text(
        json.dumps(catalogo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_itba_targets(targets)
    write_prompts(catalogo, chunks)
    print(f"OK icai_catalogo.json - {len(catalogo)} cursos")
    print(f"OK icai_chunk_NN.md - {len(chunks)} prompts")


if __name__ == "__main__":
    main()
