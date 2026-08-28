# ICAI Combinaciones Sub-4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detectar y mostrar combinaciones de dos materias ICAI con confianza individual menor a 4 que juntas puedan valer por una materia ITBA.

**Architecture:** El cambio es aditivo. Un script prepara pares candidatos y un prompt LLM; otro script agrega el JSON crudo validado a un CSV nuevo. La WebUI carga ese CSV como una vista separada para no mezclar combinaciones 2:1 con equivalencias simples.

**Tech Stack:** Python standard library (`csv`, `json`, `itertools`, `unittest`), WebUI vanilla JS + Papa Parse.

---

## File Structure

- Create `analisis/preparar_combinaciones_icai.py`: lee `resultados/icai_equivalencias.csv`, filtra matches 2-3, agrupa por ITBA, genera pares candidatos y escribe `analisis/inputs/icai_combinaciones_candidatas.json` + `analisis/prompts/icai_combinaciones.md`.
- Create `analisis/agregar_combinaciones_icai.py`: lee `analisis/outputs/raw/icai_combinaciones.json`, catálogos e ITBA targets, valida y escribe `resultados/icai_combinaciones.csv`.
- Create `tests/test_preparar_combinaciones_icai.py`: cubre filtrado, pairing y deduplicación.
- Create `tests/test_agregar_combinaciones_icai.py`: cubre agregado, etiquetas del par y cálculo de ECTS total.
- Modify `webui/app.js`: carga `icai_combinaciones.csv`, agrega tab/vista normalizada y renderiza filas 2:1.
- Modify `webui/index.html`: incrementa cache-buster del script si cambia la UI.
- Modify `README.md`: documenta flujo y limitaciones.

This directory is not a Git repository, so commit steps are intentionally omitted.

## Task 1: Candidate Pair Preparation

**Files:**
- Create: `analisis/preparar_combinaciones_icai.py`
- Test: `tests/test_preparar_combinaciones_icai.py`

- [ ] **Step 1: Write failing tests**

```python
import unittest

from analisis.preparar_combinaciones_icai import build_candidate_pairs


class IcaiCombinationPreparationTests(unittest.TestCase):
    def test_build_candidate_pairs_only_pairs_sub4_same_itba_courses(self):
        rows = [
            {"codigo_icai": "A", "nombre_icai": "A", "codigo_itba": "72.80", "nombre_itba": "Big Data", "confianza": "3", "comentario": "cubre Hadoop"},
            {"codigo_icai": "B", "nombre_icai": "B", "codigo_itba": "72.80", "nombre_itba": "Big Data", "confianza": "2", "comentario": "cubre Spark"},
            {"codigo_icai": "C", "nombre_icai": "C", "codigo_itba": "72.80", "nombre_itba": "Big Data", "confianza": "4", "comentario": "match fuerte individual"},
            {"codigo_icai": "D", "nombre_icai": "D", "codigo_itba": "72.74", "nombre_itba": "Visualizacion", "confianza": "3", "comentario": "otra ITBA"},
        ]

        pairs = build_candidate_pairs(rows)

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["codigo_itba"], "72.80")
        self.assertEqual(pairs[0]["materia_1"]["codigo_icai"], "A")
        self.assertEqual(pairs[0]["materia_2"]["codigo_icai"], "B")

    def test_build_candidate_pairs_deduplicates_reversed_pairs(self):
        rows = [
            {"codigo_icai": "B", "nombre_icai": "B", "codigo_itba": "72.80", "nombre_itba": "Big Data", "confianza": "2", "comentario": "cubre Spark"},
            {"codigo_icai": "A", "nombre_icai": "A", "codigo_itba": "72.80", "nombre_itba": "Big Data", "confianza": "3", "comentario": "cubre Hadoop"},
        ]

        pairs = build_candidate_pairs(rows)

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["pair_key"], "72.80|A|B")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run red test**

```bash
python3 -m unittest tests/test_preparar_combinaciones_icai.py
```

Expected: FAIL because `analisis.preparar_combinaciones_icai` does not exist.

- [ ] **Step 3: Implement minimal preparation script**

Create functions:

```python
def build_candidate_pairs(rows: list[dict]) -> list[dict]:
    ...
```

Rules:
- parse `confianza` as int;
- keep only 2 or 3;
- group by `codigo_itba`;
- sort ICAI codes within each pair;
- emit no reversed duplicates;
- include individual comments for the prompt.

- [ ] **Step 4: Run green test**

```bash
python3 -m unittest tests/test_preparar_combinaciones_icai.py
```

Expected: PASS.

## Task 2: Prompt And Candidate File Generation

**Files:**
- Modify: `analisis/preparar_combinaciones_icai.py`
- Test: `tests/test_preparar_combinaciones_icai.py`

- [ ] **Step 1: Add failing test for prompt content**

```python
from analisis.preparar_combinaciones_icai import render_prompt


class IcaiCombinationPreparationTests(unittest.TestCase):
    def test_render_prompt_requires_real_complementarity(self):
        prompt = render_prompt([{
            "pair_key": "72.80|A|B",
            "codigo_itba": "72.80",
            "nombre_itba": "Big Data",
            "materia_1": {"codigo_icai": "A", "nombre_icai": "A", "confianza": 3, "comentario": "Hadoop"},
            "materia_2": {"codigo_icai": "B", "nombre_icai": "B", "confianza": 2, "comentario": "Spark"},
        }])
        self.assertIn("confianza_combinada", prompt)
        self.assertIn("No emitir", prompt)
        self.assertIn("complementa", prompt)
```

- [ ] **Step 2: Run red test**

```bash
python3 -m unittest tests/test_preparar_combinaciones_icai.py
```

Expected: FAIL because `render_prompt` is missing.

- [ ] **Step 3: Implement prompt rendering and CLI**

CLI behavior:

```bash
python3 analisis/preparar_combinaciones_icai.py
```

Writes:
- `analisis/inputs/icai_combinaciones_candidatas.json`
- `analisis/prompts/icai_combinaciones.md`

Prompt output schema:

```json
{
  "codigo_icai_1": "A",
  "codigo_icai_2": "B",
  "codigo_itba": "72.80",
  "confianza_combinada": 4,
  "comentario_combinacion": "A cubre Hadoop; B cubre Spark; juntas cubren procesamiento distribuido y pipelines.",
  "complementa_por": "A aporta almacenamiento/procesamiento batch; B aporta procesamiento distribuido moderno.",
  "gaps_restantes": "Falta confirmar gobierno de datos."
}
```

- [ ] **Step 4: Run green test and smoke command**

```bash
python3 -m unittest tests/test_preparar_combinaciones_icai.py
python3 analisis/preparar_combinaciones_icai.py
```

Expected: tests PASS and command prints candidate count.

## Task 3: Combination Aggregation

**Files:**
- Create: `analisis/agregar_combinaciones_icai.py`
- Test: `tests/test_agregar_combinaciones_icai.py`

- [ ] **Step 1: Write failing tests**

```python
import unittest

from analisis.agregar_combinaciones_icai import availability_pair_label, permission_pair_label, row_from_combination


class IcaiCombinationAggregationTests(unittest.TestCase):
    def test_pair_labels_take_riskiest_value(self):
        self.assertEqual(availability_pair_label("exchange_term", "full_year"), "mixed_or_risky")
        self.assertEqual(availability_pair_label("exchange_term", "exchange_term"), "exchange_term")
        self.assertEqual(permission_pair_label("standard", "permission_required"), "permission_required")

    def test_row_from_combination_calculates_total_ects(self):
        combo = {
            "codigo_icai_1": "A",
            "codigo_icai_2": "B",
            "codigo_itba": "72.80",
            "confianza_combinada": 4,
            "comentario_combinacion": "combinan bien",
            "complementa_por": "A batch, B streaming",
            "gaps_restantes": "validar detalle",
        }
        icai = {
            "A": {"codigo": "A", "nombre": "A", "term": "Fall", "studies": "Undergraduate", "ects": 3.0, "url_guia": "u1", "labels": {"availability": "exchange_term", "permission": "standard"}, "source_label": "exchange_catalog"},
            "B": {"codigo": "B", "nombre": "B", "term": "Fall", "studies": "Master", "ects": 6.0, "url_guia": "u2", "labels": {"availability": "exchange_term", "permission": "permission_required"}, "source_label": "exchange_catalog"},
        }
        itba = {"72.80": {"codigo": "72.80", "nombre": "Big Data"}}
        individual = {("A", "72.80"): 3, ("B", "72.80"): 2}

        row = row_from_combination(combo, icai, itba, individual)

        self.assertEqual(row["ects_total"], 9.0)
        self.assertEqual(row["confianza_individual_1"], 3)
        self.assertEqual(row["permission_pair_label"], "permission_required")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run red test**

```bash
python3 -m unittest tests/test_agregar_combinaciones_icai.py
```

Expected: FAIL because script does not exist.

- [ ] **Step 3: Implement aggregation script**

Rules:
- read only combinations with `confianza_combinada >= 4`;
- reject combinations where any individual confidence is missing or >= 4;
- compute `ects_total`;
- preserve URLs for both syllabi;
- write deterministic CSV sorted by `codigo_itba`, descending `confianza_combinada`, then `codigo_icai_1`, `codigo_icai_2`.

- [ ] **Step 4: Run green test**

```bash
python3 -m unittest tests/test_agregar_combinaciones_icai.py
```

Expected: PASS.

## Task 4: WebUI Integration

**Files:**
- Modify: `webui/app.js`
- Modify: `webui/index.html`

- [ ] **Step 1: Add data loading**

Load `data/icai_combinaciones.csv` into `state.data.icai_combinaciones`.

- [ ] **Step 2: Add tab definition**

Add:

```javascript
{ id: "icai_combinaciones", label: "ICAI combinaciones", institution: "icai", combinations: true }
```

- [ ] **Step 3: Normalize combination rows**

For this tab, map each row to table-compatible fields:

```javascript
{
  codigo_externo: `${r.codigo_icai_1} + ${r.codigo_icai_2}`,
  nombre_externo: `${r.nombre_icai_1} + ${r.nombre_icai_2}`,
  tipo_externo: `${r.term_1} / ${r.term_2}`,
  curso_externo: `${r.studies_1} / ${r.studies_2}`,
  ects_externo: r.ects_total,
  codigo_itba: r.codigo_itba,
  nombre_itba: r.nombre_itba,
  confianza: r.confianza_combinada,
  comentario: `${r.comentario_combinacion} Complementa: ${r.complementa_por}. Gaps: ${r.gaps_restantes}`,
  _matched: true,
  _combination: true
}
```

- [ ] **Step 4: Update cache-buster**

Change `app.js?v=5` to `app.js?v=6`.

- [ ] **Step 5: Manual smoke**

```bash
cd webui && python3 -m http.server 8000
```

Expected: `http://localhost:8000` loads and the new tab does not break existing tabs.

## Task 5: Documentation And End-to-End Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document commands**

Add:

```bash
python3 analisis/preparar_combinaciones_icai.py
# editar/ejecutar analisis/prompts/icai_combinaciones.md para producir analisis/outputs/raw/icai_combinaciones.json
python3 analisis/agregar_combinaciones_icai.py
```

- [ ] **Step 2: Run test suite**

```bash
python3 -m unittest discover tests
```

Expected: PASS.

- [ ] **Step 3: Run pipeline smoke**

```bash
python3 analisis/preparar_combinaciones_icai.py
```

Expected: candidate JSON and prompt generated.

If `analisis/outputs/raw/icai_combinaciones.json` does not exist yet, skip the aggregation smoke and explain that the LLM review output is required.

## Self-Review Notes

- Spec coverage: candidate generation, LLM validation, aggregation, WebUI and docs are covered.
- Placeholder scan: no unfinished placeholders.
- Type consistency: script names, field names and output paths match the design.
