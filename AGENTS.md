# AGENTS.md

## Project Purpose

This repository finds candidate course equivalencies between pending ITBA Ingeniería Informática subjects and the visible Fall / All-year exchange offering from ICAI-Comillas for 2026–2027.

## Authoritative Sources

- `../___Course_Offering_26-27_Student_Version_1.1.xlsx`: authoritative ICAI availability source, sheet `OFFER 2026-2027 PROVISIONAL`.
- `itba_info/`: ITBA target courses and detailed syllabus content required by the ICAI comparison.
- `icai/extraccion_materias/icai_catalogo.csv`: consolidated visible Fall / All-year ICAI catalog.
- `icai/horarios/horarios_icai.json`: official first-semester schedules and explicit unmatched states.

## Commands

```bash
/path/to/python-with-openpyxl icai/importar_catalogo_excel.py \
  --source ../___Course_Offering_26-27_Student_Version_1.1.xlsx
python3 analisis/preparar_datos_icai.py
python3 analisis/agregar_icai.py
python3 analisis/preparar_combinaciones_icai.py
python3 analisis/agregar_combinaciones_icai.py
python3 -m icai.horarios.extraer_horarios
python3 -m unittest discover -s tests
```

Serve `webui/` with `python3 -m http.server 8000` and open `http://localhost:8000`.

## Domain Rules

- Keep only catalog rows marked visible and offered in Fall or All-year.
- Count half of an All-year course's total ECTS for the Fall semester.
- Label Master courses as `permission_required`.
- Match by substantive syllabus overlap; ITBA credits and ECTS are not directly comparable.
- Link schedules only through an exact, unique normalized match or the documented explicit administrative suffix/program-token rules. Never infer ambiguous sessions.
- Candidate equivalencies require official academic validation.

## Testing

Any new test must be unit-level, blackbox, and behavior-only. Assert public observable contracts rather than private structure, exact collaborator calls, or source snippets.
