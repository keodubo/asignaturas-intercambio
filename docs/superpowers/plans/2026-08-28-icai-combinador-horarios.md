# ICAI Schedule Combinator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extraer los horarios oficiales ICAI 2026-2027 y generar una vista semanal con todas las combinaciones válidas para las materias ICAI marcadas con estrella.

**Architecture:** Un extractor Python convierte los índices y tablas HTML oficiales en un JSON normalizado y auditable. Módulos JavaScript puros calculan solapamientos y combinaciones; la WebUI presenta una subpestaña dentro del carrito y consume exclusivamente el JSON local.

**Tech Stack:** Python 3, BeautifulSoup 4, `unittest`, JavaScript ES2020 sin framework, HTML/CSS estático.

**Spec:** `docs/superpowers/specs/2026-08-28-icai-combinador-horarios-design.md`

## Global Constraints

- Fuentes únicas: `https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/` y `https://horarios.comillas.edu/ICAIMaster1Sem/Horarios/`.
- Solo las materias ICAI marcadas con estrella participan del combinador.
- Una opción válida no puede tener conflictos en ninguna semana coincidente del Fall.
- El usuario puede elegir una semana para visualizar sin alterar la validez semestral.
- No inventar ni completar horarios ausentes.
- Todas las pruebas nuevas son unitarias, blackbox y de comportamiento.
- La carpeta actual no tiene `.git`; no ejecutar commits.

---

### Task 1: Extractor oficial de horarios

**Files:**
- Create: `icai/horarios/__init__.py`
- Create: `icai/horarios/extraer_horarios.py`
- Create: `tests/test_icai_horarios_extraccion.py`

**Interfaces:**
- Produces: `parse_schedule_page(html: str, source_url: str, group: str, date_start: str, date_end: str) -> list[dict]`
- Produces: `match_catalog_course(raw_name: str, catalog: list[dict]) -> dict | None`
- Produces: CLI que escribe `icai/horarios/horarios_icai.json` de forma atómica.

- [ ] Escribir fixtures HTML mínimos con `rowspan` y `colspan`, y pruebas que exijan reconstruir lunes-viernes, intervalos y aulas.
- [ ] Ejecutar `python3 -m unittest tests.test_icai_horarios_extraccion -v` y confirmar fallo por módulo ausente.
- [ ] Implementar parser de tabla, normalización Unicode y matching exacto por nombres oficial/inglés.
- [ ] Ejecutar las pruebas y confirmar PASS.
- [ ] Descargar ambos índices, recorrer páginas de grupos, vincular al catálogo y escribir JSON mediante archivo temporal + `replace`.

### Task 2: Motor de conflictos y combinaciones

**Files:**
- Create: `webui/schedule-engine.mjs`
- Create: `tests/test_schedule_engine.mjs`

**Interfaces:**
- Produces: `sessionsOverlap(a, b) -> boolean`
- Produces: `buildScheduleOptions(selectedCodes, schedules) -> {options, unresolved}`
- Produces: `sessionsForWeek(option, isoDate) -> session[]`

- [ ] Escribir pruebas con sesiones que solapan en hora pero no en fechas, conflictos reales, múltiples grupos y materias sin horario.
- [ ] Ejecutar `node --test tests/test_schedule_engine.mjs` y confirmar fallo por módulo ausente.
- [ ] Implementar comparación de minutos, intersección de rangos semanales y backtracking con poda.
- [ ] Deduplicar por firma de sesiones y ordenar por conflictos, días, huecos y hora final.
- [ ] Ejecutar pruebas y confirmar PASS.

### Task 3: Subpestaña Horarios

**Files:**
- Modify: `webui/index.html`
- Modify: `webui/app.js`
- Modify: `webui/style.css`

**Interfaces:**
- Consumes: `webui/data/horarios_icai.json`
- Consumes: `buildScheduleOptions` y `sessionsForWeek`.
- Produces: panel `Materias | Horarios`, selector semanal y grilla lunes-viernes.

- [ ] Agregar `schedule-engine.mjs` como módulo y cargar el JSON junto con los catálogos existentes.
- [ ] Agregar controles de subpestaña, semana y opción con estados vacíos/error.
- [ ] Renderizar eje 08:00-22:00 y bloques posicionados por día/minutos; asignar un color estable por código.
- [ ] Dividir conflictos en carriles, usar borde rojo discontinuo y mostrar un resumen visible.
- [ ] Recalcular al agregar, quitar, importar o sanear estrellas del carrito.
- [ ] Verificar `node --check webui/app.js` y `node --check webui/schedule-engine.mjs`.

### Task 4: Datos completos y cobertura

**Files:**
- Create: `icai/horarios/horarios_icai.json`
- Create: `webui/data/horarios_icai.json` (symlink)
- Modify: `icai/README.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: catálogo `analisis/inputs/icai_catalogo.json`.
- Produces: JSON con `weeks`, `courses`, `unmatched`, `sources`, `generated_at`.

- [ ] Ejecutar el extractor contra ambos portales oficiales.
- [ ] Validar que cada código vinculado exista en el catálogo Fall/All-year y que cada sesión tenga día, inicio, fin y fechas.
- [ ] Crear el symlink desde `webui/data`.
- [ ] Documentar comando de refresh, fuente y limitaciones.

### Task 5: Verificación final

**Files:**
- Test: `tests/test_icai_horarios_extraccion.py`
- Test: `tests/test_schedule_engine.mjs`

- [ ] Ejecutar `python3 -m unittest discover -s tests -v` y confirmar cero fallos.
- [ ] Ejecutar `node --test tests/test_schedule_engine.mjs` y confirmar cero fallos.
- [ ] Ejecutar checks de sintaxis JS.
- [ ] Servir `webui/` y verificar HTTP 200 para HTML, motor y JSON.
- [ ] Verificar visualmente una selección sin conflicto, otra con conflicto, selector semanal y ancho reducido.
