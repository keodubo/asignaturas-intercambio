#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path


BASE = Path(__file__).parent.parent
ICAI_EQ_PATH = BASE / "resultados" / "icai_equivalencias.csv"
ITBA_TARGETS_PATH = BASE / "analisis" / "inputs" / "itba_targets.json"
OUTPUT_INPUTS = BASE / "analisis" / "inputs"
OUTPUT_PROMPTS = BASE / "analisis" / "prompts"
OUTPUT_CANDIDATES = OUTPUT_INPUTS / "icai_combinaciones_candidatas.json"
OUTPUT_PROMPT = OUTPUT_PROMPTS / "icai_combinaciones.md"


def safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compact_match(row: dict) -> dict:
    return {
        "codigo_icai": str(row.get("codigo_icai", "")),
        "nombre_icai": str(row.get("nombre_icai", "")),
        "confianza": safe_int(row.get("confianza")),
        "comentario": str(row.get("comentario", "")),
    }


def build_candidate_pairs(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    itba_names: dict[str, str] = {}

    for row in rows:
        confianza = safe_int(row.get("confianza"))
        if confianza not in {2, 3}:
            continue
        codigo_itba = str(row.get("codigo_itba", ""))
        codigo_icai = str(row.get("codigo_icai", ""))
        if not codigo_itba or not codigo_icai:
            continue
        grouped[codigo_itba].append({**row, "confianza": confianza})
        itba_names[codigo_itba] = str(row.get("nombre_itba", ""))

    pairs = []
    seen = set()
    for codigo_itba, matches in sorted(grouped.items()):
        unique = {str(m["codigo_icai"]): m for m in matches}
        ordered = [unique[code] for code in sorted(unique)]
        for first, second in combinations(ordered, 2):
            code_1, code_2 = sorted([str(first["codigo_icai"]), str(second["codigo_icai"])])
            pair_key = f"{codigo_itba}|{code_1}|{code_2}"
            if pair_key in seen:
                continue
            seen.add(pair_key)
            materia_by_code = {
                str(first["codigo_icai"]): first,
                str(second["codigo_icai"]): second,
            }
            pairs.append({
                "pair_key": pair_key,
                "codigo_itba": codigo_itba,
                "nombre_itba": itba_names.get(codigo_itba, ""),
                "materia_1": compact_match(materia_by_code[code_1]),
                "materia_2": compact_match(materia_by_code[code_2]),
            })

    return pairs


def load_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def enrich_pairs_with_itba(pairs: list[dict], itba_targets: list[dict]) -> list[dict]:
    by_code = {str(target["codigo"]): target for target in itba_targets}
    enriched = []
    for pair in pairs:
        target = by_code.get(str(pair["codigo_itba"]), {})
        enriched.append({
            **pair,
            "itba": {
                "codigo": target.get("codigo", pair["codigo_itba"]),
                "nombre": target.get("nombre", pair.get("nombre_itba", "")),
                "contenidos_minimos": target.get("contenidos_minimos", ""),
                "objetivos_aprendizaje": target.get("objetivos_aprendizaje", ""),
            },
        })
    return enriched


def render_prompt(candidate_pairs: list[dict]) -> str:
    candidates_json = json.dumps(candidate_pairs, ensure_ascii=False, indent=2)
    return f"""# ICAI combinaciones sub-4 - Analisis de complementariedad

Sos un experto en planes de estudio de Ingenieria Informatica.
Tu tarea es revisar pares de materias ICAI que individualmente tienen confianza 2 o 3 contra la misma materia ITBA, y decidir si combinadas pueden valer como una equivalencia fuerte.

## Criterio obligatorio

No alcanza con que ambas materias apunten a la misma ITBA. Debes chequear que se complementa una con la otra:

- La materia 2 debe aportar topicos que la materia 1 no cubre, o viceversa.
- El par debe cubrir bloques distintos del temario ITBA.
- Si ambas cubren lo mismo, No emitir.
- Si una de las dos no agrega cobertura nueva, No emitir.
- Si juntas no llegan a confianza_combinada 4 o 5, No emitir.

## Rubrica

- 5 = el par cubre casi todo el temario ITBA, con gaps menores o nulos.
- 4 = el par cubre la mayoria sustantiva del temario ITBA, aunque queden gaps manualmente revisables.
- 3 o menos = No emitir.

## Candidatos

```json
{candidates_json}
```

## Output

Escribir `analisis/outputs/raw/icai_combinaciones.json` con un array JSON.
Cada elemento debe tener exactamente esta forma:

```json
{{
  "codigo_icai_1": "A",
  "codigo_icai_2": "B",
  "codigo_itba": "72.80",
  "confianza_combinada": 4,
  "comentario_combinacion": "A cubre almacenamiento/procesamiento batch; B cubre procesamiento distribuido moderno; juntas cubren el nucleo de Big Data pedido por ITBA.",
  "complementa_por": "A aporta topicos X e Y; B aporta topicos Z y W que faltaban en A.",
  "gaps_restantes": "Falta confirmar gobierno de datos y evaluacion practica."
}}
```

Solo emitir pares con confianza_combinada >= 4.
Devolver un mensaje breve: "ICAI combinaciones listas, M pares encontrados."
"""


def main() -> None:
    OUTPUT_INPUTS.mkdir(parents=True, exist_ok=True)
    OUTPUT_PROMPTS.mkdir(parents=True, exist_ok=True)

    rows = load_csv_rows(ICAI_EQ_PATH)
    pairs = build_candidate_pairs(rows)
    pairs = enrich_pairs_with_itba(pairs, load_json(ITBA_TARGETS_PATH))

    OUTPUT_CANDIDATES.write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    OUTPUT_PROMPT.write_text(render_prompt(pairs), encoding="utf-8")

    print(f"OK {OUTPUT_CANDIDATES.name}: {len(pairs)} pares candidatos")
    print(f"OK {OUTPUT_PROMPT.name}")


if __name__ == "__main__":
    main()
