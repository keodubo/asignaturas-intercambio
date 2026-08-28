# ICAI Comillas Equivalencias Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a parallel ICAI/Comillas equivalency pipeline that extracts exchange courses, labels them by practical risk, matches them against ITBA target courses, and exposes the results in the existing WebUI.

**Architecture:** Add ICAI-specific scripts and outputs without overwriting the current catálogo externo anterior pipeline. The scraper creates a normalized ICAI catalog with deterministic labels, the analysis scripts generate prompts and aggregate model matches into ICAI CSVs, and the WebUI reads ICAI as a separate view with label filters.

**Tech Stack:** Python 3, BeautifulSoup, pandas, JSON/CSV, static vanilla JS WebUI, existing ITBA CSV inputs.

---

## Scope And Constraints

- The workspace is not a Git repository right now. Steps that say "commit" are recorded as optional commands to run only if this folder is moved into or initialized as a repo.
- Do not modify existing catálogo externo anterior result files.
- Keep ICAI outputs prefixed with `icai` or under `icai/`.
- Use the official public page `https://apps.icai.comillas.edu/exchange/` as the source.
- Include `Fall`, `Full-year`, and `Spring`.
- Include `Undergraduate` and `Master`.
- Do not filter by language.
- Surface labels visibly in JSON, CSV, and WebUI.

## File Structure

- Create `icai/extraccion_materias_icai.py`: fetch/read the exchange HTML, parse course rows, compute labels, and write ICAI CSV/HTML artifacts.
- Create `icai/extraccion_materias/icai_catalogo.csv`: normalized ICAI course catalog.
- Create `icai/guias_docentes/contenidos.json`: parsed syllabus text keyed by ICAI code.
- Create `tests/test_icai_extraccion.py`: parser and label tests using an inline HTML fixture.
- Create `analisis/preparar_datos_icai.py`: convert ICAI CSV + syllabus JSON + ITBA targets into `icai_catalogo.json` and `icai_chunk_NN.md` prompts.
- Create `tests/test_preparar_datos_icai.py`: prompt/catalog tests for labels and chunk output.
- Create `analisis/agregar_icai.py`: aggregate `icai_chunk_*.json` into ICAI results and recommendations.
- Create `tests/test_agregar_icai.py`: aggregation and recommendation-bucket tests.
- Modify `webui/app.js`: add ICAI data loading, filtering, sorting, labels, and cart export compatibility.
- Modify `webui/index.html`: add filter controls for ICAI labels if the current static markup needs new fieldsets.
- Modify `webui/style.css`: add compact label badge styles.
- Create `webui/data/icai_catalogo.json`: symlink to `../../analisis/inputs/icai_catalogo.json`.
- Create `webui/data/icai_equivalencias.csv`: symlink to `../../resultados/icai_equivalencias.csv`.
- Create `webui/data/icai_sin_equivalencia.csv`: symlink to `../../resultados/icai_sin_equivalencia.csv`.
- Create `webui/data/icai_recomendaciones.csv`: symlink to `../../resultados/icai_recomendaciones.csv`.
- Modify `README.md`: document ICAI pipeline commands and caveats.

## Task 1: ICAI Parser And Label Unit Tests

**Files:**
- Create: `tests/test_icai_extraccion.py`
- Later implementation target: `icai/extraccion_materias_icai.py`

- [ ] **Step 1: Create the parser test file**

Create `tests/test_icai_extraccion.py` with:

```python
import unittest

from icai.extraccion_materias_icai import compute_labels, parse_exchange_html


HTML_FIXTURE = """
<html><body>
<p><strong>UNDERGRADUATE courses. FALL semester (2025-26)</strong></p>
<table>
  <tr>
    <td>Language</td><td>Term</td><td>Schedule</td><td>Studies</td>
    <td>Degree</td><td>ECTS*</td><td>Code</td><td>Subject</td><td>Syllabus</td>
  </tr>
  <tr>
    <td>English</td><td>Fall</td><td>Morning</td><td>Undergraduate</td>
    <td>3-DCC</td><td>6</td><td>DTC-GITT-315</td>
    <td><strong>Software Engineering</strong><br/>Ingeniería del Software</td>
    <td><a href="https://example.test/repo-2024">Repo 2024-25</a></td>
  </tr>
</table>
<p><strong>POSTGRADUATE courses. Permission required for undergraduate exchange students (2025-26)</strong></p>
<table>
  <tr>
    <td>Language</td><td>Term</td><td>Schedule</td><td>Studies</td>
    <td>Degree</td><td>ECTS*</td><td>Code</td><td>Subject</td><td>Syllabus</td>
  </tr>
  <tr>
    <td></td><td>Spring</td><td>Afternoon</td><td>Master</td>
    <td>2-MIC</td><td>3</td><td>DTC-MIC-523</td>
    <td>Cybersecurity</td>
    <td><a href="https://example.test/repo-2024-cyber">Repo 2024-25</a></td>
  </tr>
</table>
</body></html>
"""


class IcaiExtractionTests(unittest.TestCase):
    def test_parse_exchange_html_preserves_rows_and_links(self):
        rows = parse_exchange_html(HTML_FIXTURE)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["codigo"], "DTC-GITT-315")
        self.assertEqual(rows[0]["nombre"], "Software Engineering Ingeniería del Software")
        self.assertEqual(rows[0]["term"], "Fall")
        self.assertEqual(rows[0]["studies"], "Undergraduate")
        self.assertEqual(rows[0]["ects"], 6.0)
        self.assertEqual(rows[0]["url_guia"], "https://example.test/repo-2024")
        self.assertEqual(rows[0]["syllabus_links"][0]["label"], "Repo 2024-25")

    def test_compute_labels_for_fall_undergraduate(self):
        labels = compute_labels({
            "term": "Fall",
            "studies": "Undergraduate",
            "schedule": "Morning",
            "language": "English",
            "nombre": "Software Engineering",
        })

        self.assertEqual(labels["availability"], "exchange_term")
        self.assertEqual(labels["timing_risk"], "low")
        self.assertEqual(labels["level"], "undergraduate")
        self.assertEqual(labels["permission"], "standard")
        self.assertEqual(labels["language"], "english")
        self.assertEqual(labels["schedule"], "morning")

    def test_compute_labels_for_spring_master(self):
        labels = compute_labels({
            "term": "Spring",
            "studies": "Master",
            "schedule": "Afternoon",
            "language": "",
            "nombre": "Cybersecurity",
        })

        self.assertEqual(labels["availability"], "not_in_exchange_term")
        self.assertEqual(labels["timing_risk"], "high")
        self.assertEqual(labels["level"], "postgraduate")
        self.assertEqual(labels["permission"], "permission_required")
        self.assertEqual(labels["language"], "unknown")
        self.assertEqual(labels["schedule"], "afternoon")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```bash
python3 -m unittest tests/test_icai_extraccion.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'icai'
```

- [ ] **Step 3: Optional commit if a Git repo exists**

Run only if `.git` exists:

```bash
git add tests/test_icai_extraccion.py
git commit -m "test: cover ICAI exchange parser labels"
```

## Task 2: ICAI Scraper And Catalog CSV

**Files:**
- Create: `icai/__init__.py`
- Create: `icai/extraccion_materias_icai.py`
- Create output directory at runtime: `icai/extraccion_materias/`
- Create output directory at runtime: `icai/guias_docentes/`

- [ ] **Step 1: Create the package marker**

Create `icai/__init__.py` as an empty file.

- [ ] **Step 2: Implement `icai/extraccion_materias_icai.py`**

Use this structure:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


BASE = Path(__file__).parent
PROJECT_ROOT = BASE.parent
SOURCE_URL = "https://apps.icai.comillas.edu/exchange/"
EXCHANGE_HTML = BASE / "exchange.html"
OUT_DIR = BASE / "extraccion_materias"
GUIAS_DIR = BASE / "guias_docentes"
CONTENIDOS_JSON = GUIAS_DIR / "contenidos.json"
OUT_CSV = OUT_DIR / "icai_catalogo.csv"

CSV_FIELDS = [
    "language", "term", "schedule", "studies", "degree", "ects", "codigo",
    "nombre", "url_guia", "syllabus_links_json", "availability_label",
    "timing_risk_label", "level_label", "permission_label", "language_label",
    "schedule_label",
]


def clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u2011", "-").split())


def parse_float(value: str):
    text = clean_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_schedule(value: str) -> str:
    text = clean_text(value).lower()
    if text == "afternooon":
        text = "afternoon"
    return text or "unknown"


def infer_language(language: str, subject: str) -> str:
    text = f"{language} {subject}".lower()
    has_english = "english" in text or "inglés" in text
    has_spanish = "spanish" in text or "español" in text or "castellano" in text
    has_slash = "/" in subject
    if has_english and (has_spanish or has_slash):
        return "mixed"
    if has_english:
        return "english"
    if has_spanish:
        return "spanish"
    return "unknown"


def compute_labels(course: dict) -> dict:
    term = clean_text(course.get("term", ""))
    studies = clean_text(course.get("studies", ""))
    schedule = normalize_schedule(course.get("schedule", ""))
    language_label = infer_language(course.get("language", ""), course.get("nombre", ""))

    if term == "Fall":
        availability = "exchange_term"
        timing_risk = "low"
    elif term == "Full-year":
        availability = "full_year"
        timing_risk = "medium"
    elif term == "Spring":
        availability = "not_in_exchange_term"
        timing_risk = "high"
    else:
        availability = "unknown"
        timing_risk = "medium"

    if studies == "Master":
        level = "postgraduate"
        permission = "permission_required"
    else:
        level = "undergraduate"
        permission = "standard"

    return {
        "availability": availability,
        "timing_risk": timing_risk,
        "level": level,
        "permission": permission,
        "language": language_label,
        "schedule": schedule,
    }


def is_course_table(table) -> bool:
    first = table.find("tr")
    if not first:
        return False
    headers = [clean_text(c.get_text(" ", strip=True)) for c in first.find_all(["td", "th"])]
    return headers[:4] == ["Language", "Term", "Schedule", "Studies"]


def parse_exchange_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for table in soup.find_all("table"):
        if not is_course_table(table):
            continue
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if len(cells) < 9:
                continue
            language, term, schedule, studies, degree, ects, code, subject, syllabus = cells[:9]
            codigo = clean_text(code.get_text(" ", strip=True))
            if not codigo or codigo.lower() == "code":
                continue
            links = []
            for a in syllabus.find_all("a", href=True):
                links.append({
                    "label": clean_text(a.get_text(" ", strip=True)),
                    "url": urljoin(SOURCE_URL, a["href"]),
                })
            row = {
                "language": clean_text(language.get_text(" ", strip=True)),
                "term": clean_text(term.get_text(" ", strip=True)),
                "schedule": clean_text(schedule.get_text(" ", strip=True)),
                "studies": clean_text(studies.get_text(" ", strip=True)),
                "degree": clean_text(degree.get_text(" ", strip=True)),
                "ects": parse_float(ects.get_text(" ", strip=True)),
                "codigo": codigo,
                "nombre": clean_text(subject.get_text(" ", strip=True)),
                "url_guia": links[0]["url"] if links else "",
                "syllabus_links": links,
            }
            row["labels"] = compute_labels(row)
            rows.append(row)
    return rows


def fetch_source_html() -> str:
    result = subprocess.run(
        ["curl", "-fsSL", SOURCE_URL],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def read_or_fetch_html(refresh: bool) -> str:
    if refresh or not EXCHANGE_HTML.exists():
        html = fetch_source_html()
        BASE.mkdir(parents=True, exist_ok=True)
        EXCHANGE_HTML.write_text(html, encoding="utf-8")
        return html
    return EXCHANGE_HTML.read_text(encoding="utf-8", errors="replace")


def write_catalog_csv(rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            labels = row["labels"]
            writer.writerow({
                "language": row["language"],
                "term": row["term"],
                "schedule": row["schedule"],
                "studies": row["studies"],
                "degree": row["degree"],
                "ects": row["ects"] if row["ects"] is not None else "",
                "codigo": row["codigo"],
                "nombre": row["nombre"],
                "url_guia": row["url_guia"],
                "syllabus_links_json": json.dumps(row["syllabus_links"], ensure_ascii=False),
                "availability_label": labels["availability"],
                "timing_risk_label": labels["timing_risk"],
                "level_label": labels["level"],
                "permission_label": labels["permission"],
                "language_label": labels["language"],
                "schedule_label": labels["schedule"],
            })


def write_empty_contenidos(rows: list[dict]) -> None:
    GUIAS_DIR.mkdir(parents=True, exist_ok=True)
    if CONTENIDOS_JSON.exists():
        return
    payload = {
        row["codigo"]: {
            "descripcion": "",
            "competencias": "",
            "contenidos": "",
            "metodologia": "",
            "evaluacion": "",
            "bibliografia": "",
        }
        for row in rows
    }
    CONTENIDOS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Download the live exchange page before parsing.")
    args = parser.parse_args()

    html = read_or_fetch_html(refresh=args.refresh)
    rows = parse_exchange_html(html)
    write_catalog_csv(rows)
    write_empty_contenidos(rows)
    print(f"OK icai_catalogo.csv - {len(rows)} cursos")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the parser tests and verify they pass**

Run:

```bash
python3 -m unittest tests/test_icai_extraccion.py -v
```

Expected:

```text
Ran 3 tests
OK
```

- [ ] **Step 4: Run the scraper against the live source**

Run:

```bash
python3 icai/extraccion_materias_icai.py --refresh
```

Expected:

```text
OK icai_catalogo.csv - 393 cursos
```

The exact row count may change if Comillas updates the page. If it changes, inspect `icai/exchange.html` and confirm the table structure is still the same.

- [ ] **Step 5: Verify term and studies coverage**

Run:

```bash
python3 - <<'PY'
import csv
from collections import Counter
rows = list(csv.DictReader(open("icai/extraccion_materias/icai_catalogo.csv", encoding="utf-8-sig")))
print("terms", Counter(r["term"] for r in rows))
print("studies", Counter(r["studies"] for r in rows))
print("availability", Counter(r["availability_label"] for r in rows))
print("permission", Counter(r["permission_label"] for r in rows))
PY
```

Expected includes non-zero counts for `Fall`, `Full-year`, `Spring`, `Undergraduate`, and `Master`.

- [ ] **Step 6: Optional commit if a Git repo exists**

Run only if `.git` exists:

```bash
git add icai tests/test_icai_extraccion.py
git commit -m "feat: extract ICAI exchange catalog"
```

## Task 3: ICAI Input And Prompt Generation

**Files:**
- Create: `analisis/preparar_datos_icai.py`
- Create: `tests/test_preparar_datos_icai.py`
- Create outputs at runtime: `analisis/inputs/icai_catalogo.json`
- Create outputs at runtime: `analisis/prompts/icai_chunk_NN.md`

- [ ] **Step 1: Create tests for catalog preparation**

Create `tests/test_preparar_datos_icai.py` with:

```python
import csv
import json
import tempfile
import unittest
from pathlib import Path

from analisis.preparar_datos_icai import load_icai_catalogo, recommendation_bucket_for_prompt


class IcaiPrepareDataTests(unittest.TestCase):
    def test_load_icai_catalogo_preserves_labels_and_syllabus_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            csv_path = base / "icai_catalogo.csv"
            contenidos_path = base / "contenidos.json"
            with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "language", "term", "schedule", "studies", "degree", "ects", "codigo",
                    "nombre", "url_guia", "syllabus_links_json", "availability_label",
                    "timing_risk_label", "level_label", "permission_label", "language_label",
                    "schedule_label",
                ])
                writer.writeheader()
                writer.writerow({
                    "language": "English",
                    "term": "Fall",
                    "schedule": "Morning",
                    "studies": "Undergraduate",
                    "degree": "3-DCC",
                    "ects": "6",
                    "codigo": "DTC-GITT-315",
                    "nombre": "Software Engineering",
                    "url_guia": "https://example.test/repo",
                    "syllabus_links_json": '[{"label":"Repo 2024-25","url":"https://example.test/repo"}]',
                    "availability_label": "exchange_term",
                    "timing_risk_label": "low",
                    "level_label": "undergraduate",
                    "permission_label": "standard",
                    "language_label": "english",
                    "schedule_label": "morning",
                })
            contenidos_path.write_text(json.dumps({
                "DTC-GITT-315": {"contenidos": "Requirements, design, testing"}
            }), encoding="utf-8")

            catalog = load_icai_catalogo(csv_path, contenidos_path)

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["codigo"], "DTC-GITT-315")
        self.assertEqual(catalog[0]["institucion"], "icai_comillas")
        self.assertEqual(catalog[0]["labels"]["availability"], "exchange_term")
        self.assertEqual(catalog[0]["guia"]["contenidos"], "Requirements, design, testing")

    def test_recommendation_bucket_for_prompt(self):
        self.assertEqual(recommendation_bucket_for_prompt("Fall", "Undergraduate", 4), "primary")
        self.assertEqual(recommendation_bucket_for_prompt("Fall", "Undergraduate", 3), "strong_candidate")
        self.assertEqual(recommendation_bucket_for_prompt("Full-year", "Undergraduate", 4), "strong_candidate")
        self.assertEqual(recommendation_bucket_for_prompt("Fall", "Master", 4), "conditional")
        self.assertEqual(recommendation_bucket_for_prompt("Spring", "Master", 5), "backup_only")
        self.assertEqual(recommendation_bucket_for_prompt("Fall", "Undergraduate", 2), "backup_only")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```bash
python3 -m unittest tests/test_preparar_datos_icai.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'analisis.preparar_datos_icai'
```

- [ ] **Step 3: Implement `analisis/preparar_datos_icai.py`**

Use this structure and adapt the existing catálogo externo anterior prompt style:

```python
#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import pandas as pd
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
    if term == "Fall" and confianza >= 4:
        return "primary"
    if term == "Fall" and confianza == 3:
        return "strong_candidate"
    if term == "Full-year" and confianza >= 4:
        return "strong_candidate"
    if term == "Full-year":
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
                "url_guia": row["url_guia"],
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
    df = pd.read_csv(ITBA_CSV, dtype=str)
    targets = []
    for _, row in df.iterrows():
        targets.append({
            "codigo": row["codigo"],
            "nombre": row["nombre"],
            "contenidos_minimos": row["contenidos_minimos"] if pd.notna(row["contenidos_minimos"]) else None,
            "objetivos_aprendizaje": row["objetivos_aprendizaje"] if pd.notna(row["objetivos_aprendizaje"]) else None,
        })
    return targets


def partition(items: list[dict], size: int) -> list[list[dict]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


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
            "url_guia": course["url_guia"],
            "labels": course["labels"],
            "guia": {
                "descripcion": str(guia.get("descripcion", ""))[:1200],
                "competencias": str(guia.get("competencias", ""))[:1000],
                "contenidos": str(guia.get("contenidos", ""))[:1800],
                "metodologia": str(guia.get("metodologia", ""))[:400],
                "evaluacion": str(guia.get("evaluacion", ""))[:400],
                "bibliografia": str(guia.get("bibliografia", ""))[:250],
            },
        })
    return compact


def write_prompts(catalogo: list[dict], chunks: list[list[dict]]) -> None:
    catalogo_json = json.dumps(compact_icai_for_prompt(catalogo), ensure_ascii=False, indent=2)
    for i, chunk in enumerate(chunks, 1):
        chunk_num = f"{i:02d}"
        chunk_json = json.dumps(chunk, ensure_ascii=False, indent=2)
        prompt = f"""# ICAI Chunk {chunk_num} - Analisis de equivalencias ITBA -> ICAI/Comillas

Sos un experto en planes de estudio de Ingenieria Informatica.
Tu tarea: para cada materia ITBA del bloque, identificar materias ICAI/Comillas cuyo temario solape suficiente como para ser candidata a equivalencia.

## Reglas de universo

El catalogo incluye Fall, Full-year y Spring; Undergraduate y Master; materias en ingles y espanol.
No descartes por semestre o nivel, pero reflejalo en el comentario:
- Fall = mejor para intercambio septiembre-diciembre.
- Full-year = requiere confirmar cursada parcial/anual.
- Spring = match academico/back-up, no coincide con septiembre-diciembre salvo excepcion.
- Master = puede requerir permiso para estudiante de exchange undergraduate.

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
    write_prompts(catalogo, chunks)
    print(f"OK icai_catalogo.json - {len(catalogo)} cursos")
    print(f"OK icai_chunk_NN.md - {len(chunks)} prompts")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run preparation tests**

Run:

```bash
python3 -m unittest tests/test_preparar_datos_icai.py -v
```

Expected:

```text
Ran 2 tests
OK
```

- [ ] **Step 5: Generate ICAI inputs and prompts**

Run:

```bash
python3 analisis/preparar_datos_icai.py
```

Expected:

```text
OK icai_catalogo.json - 393 cursos
OK icai_chunk_NN.md - 6 prompts
```

- [ ] **Step 6: Optional commit if a Git repo exists**

Run only if `.git` exists:

```bash
git add analisis/preparar_datos_icai.py tests/test_preparar_datos_icai.py analisis/inputs/icai_catalogo.json analisis/prompts/icai_chunk_*.md
git commit -m "feat: prepare ICAI matching prompts"
```

## Task 4: Matching Execution Checkpoint

**Files:**
- Generated by agents: `analisis/outputs/raw/icai_chunk_01.json` through `analisis/outputs/raw/icai_chunk_06.json`

- [ ] **Step 1: Dispatch one matching agent per prompt**

Use one agent per file:

```text
Read analisis/prompts/icai_chunk_01.md, complete the task exactly, and write analisis/outputs/raw/icai_chunk_01.json.
```

Repeat for `icai_chunk_02.md` through `icai_chunk_06.md`.

- [ ] **Step 2: Validate JSON syntax**

Run:

```bash
python3 -m json.tool analisis/outputs/raw/icai_chunk_01.json >/dev/null
python3 -m json.tool analisis/outputs/raw/icai_chunk_02.json >/dev/null
python3 -m json.tool analisis/outputs/raw/icai_chunk_03.json >/dev/null
python3 -m json.tool analisis/outputs/raw/icai_chunk_04.json >/dev/null
python3 -m json.tool analisis/outputs/raw/icai_chunk_05.json >/dev/null
python3 -m json.tool analisis/outputs/raw/icai_chunk_06.json >/dev/null
```

Expected: no output and exit code `0` for every file.

- [ ] **Step 3: Validate required keys**

Run:

```bash
python3 - <<'PY'
import glob, json
required = {"codigo_icai", "codigo_itba", "confianza", "comentario"}
for path in sorted(glob.glob("analisis/outputs/raw/icai_chunk_*.json")):
    data = json.load(open(path))
    for i, item in enumerate(data):
        missing = required - set(item)
        if missing:
            raise SystemExit(f"{path}[{i}] missing {sorted(missing)}")
        if item["confianza"] < 2:
            raise SystemExit(f"{path}[{i}] has confianza < 2")
print("OK icai raw chunks")
PY
```

Expected:

```text
OK icai raw chunks
```

## Task 5: ICAI Aggregation And Recommendations

**Files:**
- Create: `analisis/agregar_icai.py`
- Create: `tests/test_agregar_icai.py`
- Create outputs at runtime: `resultados/icai_equivalencias.csv`
- Create outputs at runtime: `resultados/icai_sin_equivalencia.csv`
- Create outputs at runtime: `resultados/icai_recomendaciones.csv`

- [ ] **Step 1: Create aggregation tests**

Create `tests/test_agregar_icai.py` with:

```python
import unittest

from analisis.agregar_icai import recommendation_bucket, sort_recommendations


class IcaiAggregationTests(unittest.TestCase):
    def test_recommendation_bucket(self):
        self.assertEqual(recommendation_bucket("Fall", "Undergraduate", 5), "primary")
        self.assertEqual(recommendation_bucket("Fall", "Master", 5), "conditional")
        self.assertEqual(recommendation_bucket("Full-year", "Undergraduate", 4), "strong_candidate")
        self.assertEqual(recommendation_bucket("Spring", "Undergraduate", 5), "backup_only")
        self.assertEqual(recommendation_bucket("Fall", "Undergraduate", 2), "backup_only")

    def test_sort_recommendations_prioritizes_primary(self):
        rows = [
            {"recommendation_bucket": "backup_only", "confianza": 5, "availability_label": "not_in_exchange_term", "permission_label": "standard", "codigo_icai": "B"},
            {"recommendation_bucket": "primary", "confianza": 4, "availability_label": "exchange_term", "permission_label": "standard", "codigo_icai": "A"},
            {"recommendation_bucket": "conditional", "confianza": 5, "availability_label": "exchange_term", "permission_label": "permission_required", "codigo_icai": "C"},
        ]
        sorted_rows = sort_recommendations(rows)
        self.assertEqual([r["codigo_icai"] for r in sorted_rows], ["A", "C", "B"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```bash
python3 -m unittest tests/test_agregar_icai.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'analisis.agregar_icai'
```

- [ ] **Step 3: Implement `analisis/agregar_icai.py`**

Implement functions:

```python
BUCKET_ORDER = {
    "primary": 0,
    "strong_candidate": 1,
    "conditional": 2,
    "backup_only": 3,
}

AVAILABILITY_ORDER = {
    "exchange_term": 0,
    "full_year": 1,
    "not_in_exchange_term": 2,
    "unknown": 3,
}

PERMISSION_ORDER = {
    "standard": 0,
    "permission_required": 1,
}


def recommendation_bucket(term: str, studies: str, confianza: int) -> str:
    if term == "Spring" or confianza <= 2:
        return "backup_only"
    if studies == "Master":
        return "conditional"
    if term == "Fall" and confianza >= 4:
        return "primary"
    if term == "Fall" and confianza == 3:
        return "strong_candidate"
    if term == "Full-year" and confianza >= 4:
        return "strong_candidate"
    if term == "Full-year":
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
```

The full script must:

- Load `analisis/inputs/icai_catalogo.json`.
- Load `analisis/inputs/itba_targets.json`; if missing, generate it by calling the existing ITBA loader logic or run `python3 analisis/preparar_datos.py` first.
- Load every `analisis/outputs/raw/icai_chunk_*.json`.
- Join matches to ICAI and ITBA details.
- Write `resultados/icai_equivalencias.csv` with columns:
  - `codigo_icai`
  - `nombre_icai`
  - `term`
  - `studies`
  - `degree`
  - `schedule`
  - `language`
  - `ects_icai`
  - `codigo_itba`
  - `nombre_itba`
  - `confianza`
  - `comentario`
  - `availability_label`
  - `timing_risk_label`
  - `level_label`
  - `permission_label`
  - `language_label`
  - `schedule_label`
  - `recommendation_bucket`
  - `url_guia_icai`
- Write `resultados/icai_sin_equivalencia.csv` with unmatched ITBA targets.
- Write `resultados/icai_recomendaciones.csv` sorted by `sort_recommendations`.

- [ ] **Step 4: Run aggregation tests**

Run:

```bash
python3 -m unittest tests/test_agregar_icai.py -v
```

Expected:

```text
Ran 2 tests
OK
```

- [ ] **Step 5: Run aggregation after matching chunks exist**

Run:

```bash
python3 analisis/agregar_icai.py
```

Expected:

```text
OK icai_equivalencias.csv - N filas
OK icai_sin_equivalencia.csv - N filas
OK icai_recomendaciones.csv - N filas
```

- [ ] **Step 6: Optional commit if a Git repo exists**

Run only if `.git` exists:

```bash
git add analisis/agregar_icai.py tests/test_agregar_icai.py resultados/icai_*.csv
git commit -m "feat: aggregate ICAI equivalencies"
```

## Task 6: WebUI ICAI Integration

**Files:**
- Modify: `webui/app.js`
- Modify: `webui/index.html`
- Modify: `webui/style.css`
- Create symlinks: `webui/data/icai_catalogo.json`, `webui/data/icai_equivalencias.csv`, `webui/data/icai_sin_equivalencia.csv`, `webui/data/icai_recomendaciones.csv`

- [ ] **Step 1: Add symlinks for ICAI data**

Run:

```bash
ln -sf ../../analisis/inputs/icai_catalogo.json webui/data/icai_catalogo.json
ln -sf ../../resultados/icai_equivalencias.csv webui/data/icai_equivalencias.csv
ln -sf ../../resultados/icai_sin_equivalencia.csv webui/data/icai_sin_equivalencia.csv
ln -sf ../../resultados/icai_recomendaciones.csv webui/data/icai_recomendaciones.csv
```

- [ ] **Step 2: Modify `webui/app.js` data model**

Add ICAI career definition:

```js
{ id: "icai", label: "ICAI Comillas", institution: "icai" },
```

Add state sets:

```js
terms: new Set(),
studies: new Set(),
degrees: new Set(),
availability: new Set(),
timingRisk: new Set(),
permissions: new Set(),
recommendationBuckets: new Set(),
icaiCatalogo: [],
icaiByCode: {},
```

Update `loadAll()` to load `data/icai_catalogo.json` and `data/icai_equivalencias.csv` / `data/icai_sin_equivalencia.csv` for the ICAI tab.

- [ ] **Step 3: Modify `rowsForCareer()` for ICAI**

For `state.carrera === "icai"`, return rows from `state.data.icai.eq` and, if `showUnmatched` is enabled, unmatched ICAI catalog rows keyed by `codigo_icai`.

Use row fields `codigo_icai` and `nombre_icai`, but normalize them for existing render helpers:

```js
function normalizeInstitutionRow(r) {
  if (state.carrera !== "icai") return r;
  return {
    ...r,
    codigo_externo: r.codigo_icai,
    nombre_externo: r.nombre_icai,
    tipo_externo: r.term,
    curso_externo: r.degree,
    ects_externo: r.ects_icai,
    url_guia_externo: r.url_guia_icai,
  };
}
```

- [ ] **Step 4: Add ICAI-specific filters**

Implement filters that only apply when the active tab is ICAI:

```js
function isIcaiActive() {
  return state.carrera === "icai";
}
```

Filter rows by `term`, `studies`, `degree`, `availability_label`, `timing_risk_label`, `permission_label`, and `recommendation_bucket`.

- [ ] **Step 5: Render labels in the table**

For ICAI rows, append compact badges inside the course-name cell:

```js
function icaiBadges(r) {
  if (!isIcaiActive()) return "";
  return `
    <span class="label-badge ${escape(r.availability_label)}">${escape(r.availability_label)}</span>
    <span class="label-badge risk-${escape(r.timing_risk_label)}">${escape(r.timing_risk_label)}</span>
    <span class="label-badge ${escape(r.permission_label)}">${escape(r.permission_label)}</span>
    <span class="label-badge ${escape(r.recommendation_bucket)}">${escape(r.recommendation_bucket)}</span>`;
}
```

- [ ] **Step 6: Add CSS badge styles**

Add to `webui/style.css`:

```css
.label-badge {
  display: inline-block;
  margin: 2px 4px 0 0;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 11px;
  line-height: 1.3;
  background: #eef2f7;
  color: #263445;
  white-space: nowrap;
}

.label-badge.exchange_term,
.label-badge.primary {
  background: #dff4e8;
  color: #14532d;
}

.label-badge.full_year,
.label-badge.strong_candidate,
.label-badge.conditional,
.label-badge.risk-medium {
  background: #fff1c7;
  color: #7a4b00;
}

.label-badge.not_in_exchange_term,
.label-badge.backup_only,
.label-badge.permission_required,
.label-badge.risk-high {
  background: #fde2e2;
  color: #7f1d1d;
}
```

- [ ] **Step 7: Run local WebUI**

Run:

```bash
cd webui && python3 -m http.server 8000
```

Open `http://localhost:8000` and verify:

- ICAI tab loads.
- ICAI rows show labels.
- Filters narrow rows correctly.
- Cart still works for catálogo externo anterior and ICAI rows.

- [ ] **Step 8: Optional commit if a Git repo exists**

Run only if `.git` exists:

```bash
git add webui webui/data
git commit -m "feat: add ICAI filters to WebUI"
```

## Task 7: Documentation

**Files:**
- Modify: `README.md`
- Create: `icai/README.md`

- [ ] **Step 1: Create `icai/README.md`**

Create:

```markdown
# ICAI Comillas Exchange Pipeline

Fuente oficial: https://apps.icai.comillas.edu/exchange/

## Scope

Incluye materias Fall, Full-year y Spring, tanto Undergraduate como Master, sin filtrar por idioma.

## Etiquetas

- `exchange_term`: Fall, candidata principal para septiembre-diciembre.
- `full_year`: materia anual, requiere confirmar si puede cursarse parcialmente.
- `not_in_exchange_term`: Spring, match academico pero no coincide con septiembre-diciembre salvo excepcion.
- `permission_required`: Master/Postgraduate, requiere permiso.

## Comandos

```bash
python3 icai/extraccion_materias_icai.py --refresh
python3 analisis/preparar_datos_icai.py
```

Despues de completar los `analisis/outputs/raw/icai_chunk_*.json`:

```bash
python3 analisis/agregar_icai.py
cd webui && python3 -m http.server 8000
```
```

- [ ] **Step 2: Update root `README.md`**

Add an ICAI section with:

```markdown
## ICAI / Comillas

Pipeline paralelo para analizar equivalencias ITBA contra la oferta publica de exchange de ICAI/Comillas.

```bash
python3 icai/extraccion_materias_icai.py --refresh
python3 analisis/preparar_datos_icai.py
python3 analisis/agregar_icai.py
```

La extraccion incluye Fall, Full-year y Spring; Undergraduate y Master; materias en ingles y espanol. Los resultados incluyen etiquetas de disponibilidad, riesgo temporal, permiso y bucket de recomendacion. Para septiembre-diciembre, priorizar `exchange_term` y revisar `full_year`/`not_in_exchange_term` como evidencia secundaria.
```

- [ ] **Step 3: Optional commit if a Git repo exists**

Run only if `.git` exists:

```bash
git add README.md icai/README.md
git commit -m "docs: document ICAI pipeline"
```

## Task 8: Final Verification

**Files:**
- All files touched by Tasks 1-7.

- [ ] **Step 1: Run unit tests**

Run:

```bash
python3 -m unittest tests/test_icai_extraccion.py tests/test_preparar_datos_icai.py tests/test_agregar_icai.py -v
```

Expected:

```text
OK
```

- [ ] **Step 2: Run the ICAI pipeline**

Run:

```bash
python3 icai/extraccion_materias_icai.py --refresh
python3 analisis/preparar_datos_icai.py
python3 analisis/agregar_icai.py
```

Expected:

```text
OK icai_catalogo.csv - N cursos
OK icai_catalogo.json - N cursos
OK icai_chunk_NN.md - 6 prompts
OK icai_equivalencias.csv - N filas
OK icai_sin_equivalencia.csv - N filas
OK icai_recomendaciones.csv - N filas
```

- [ ] **Step 3: Validate output labels**

Run:

```bash
python3 - <<'PY'
import csv
from collections import Counter
rows = list(csv.DictReader(open("resultados/icai_equivalencias.csv", encoding="utf-8-sig")))
for col in ["availability_label", "timing_risk_label", "level_label", "permission_label", "recommendation_bucket"]:
    print(col, Counter(r[col] for r in rows))
PY
```

Expected: every printed counter has at least one non-empty key when matches exist.

- [ ] **Step 4: Verify WebUI manually**

Run:

```bash
cd webui && python3 -m http.server 8000
```

Open `http://localhost:8000` and verify ICAI tab, labels, filters, sorting, and cart export.

- [ ] **Step 5: Record residual risks**

Add a short note to `icai/README.md` if any of these are true after implementation:

- Comillas row count changed from the previous observed count.
- Some syllabus links failed to parse.
- Matching was performed without full syllabus text for many courses.
- Spring/Full-year matches dominate recommendations and need manual review.
