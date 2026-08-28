# ICAI-Comillas Course Offering 2026-2027

Este módulo usa exclusivamente el Excel oficial `___Course_Offering_26-27_Student_Version_1.1.xlsx` para determinar qué materias ICAI están disponibles.

Fuente autoritativa:

- Hoja `OFFER 2026-2027 PROVISIONAL` del Excel entregado por Comillas.

## Alcance

- Incluye solo filas `visible = yes` de `Fall` y `All-year`.
- Incluye `Undergraduate` y `Master`.
- Incluye materias en inglés y español.
- Incluye SAPIENS cuando figura en el Excel.
- Consolida por código las variantes de idioma.
- Para `All-year`, conserva los ECTS totales y usa la mitad como ECTS del semestre Fall.

## Outputs

| Archivo | Contenido |
|---|---|
| `extraccion_materias/icai_catalogo.csv` | Catálogo derivado exclusivamente del Excel oficial. |
| `guias_docentes/contenidos.json` | Placeholder para contenido de guías docentes. |
| `horarios/horarios_icai.json` | Horarios publicados vinculados de forma exacta al catálogo Fall/All-year, más los casos sin vínculo. |
| `../analisis/inputs/icai_catalogo.json` | Catálogo normalizado para prompts y WebUI. |
| `../analisis/prompts/icai_chunk_NN.md` | Prompts autocontenidos para matching ITBA -> ICAI. |
| `../resultados/icai_equivalencias.csv` | Candidatos de equivalencia. |
| `../resultados/icai_recomendaciones.csv` | Mismo dataset ordenado por bucket de recomendación. |
| `../resultados/icai_sin_equivalencia.csv` | Materias ITBA sin candidato ICAI suficiente. |

## Etiquetas

| Campo | Valores | Uso |
|---|---|---|
| `availability_label` | `exchange_term`, `exchange_term_all_year` | Compatibilidad con intercambio septiembre-diciembre. |
| `timing_risk_label` | `low`, `medium`, `high` | Riesgo administrativo por calendario. |
| `level_label` | `undergraduate`, `postgraduate` | Nivel de cursada. |
| `permission_label` | `standard`, `permission_required` | Master requiere confirmación para exchange undergraduate. |
| `language_label` | `english`, `spanish`, `mixed`, `unknown` | Idioma inferido desde la columna `Language`. |
| `schedule_label` | `morning`, `afternoon`, `unknown` | Franja horaria normalizada. |
| `source_label` | `course_offering_2026_2027_v1_1` | Versión del Excel fuente. |
| `program_label` | `regular_icai`, `sapiens` | Programa origen. |
| `recommendation_bucket` | `primary`, `strong_candidate`, `conditional`, `backup_only` | Priorización para armar shortlist. |

## Re-correr pipeline ICAI

```bash
/ruta/al/python-con-openpyxl icai/importar_catalogo_excel.py \
  --source ../___Course_Offering_26-27_Student_Version_1.1.xlsx
python3 analisis/preparar_datos_icai.py
python3 analisis/agregar_icai.py
```

## Horarios oficiales del primer semestre

El combinador de la WebUI usa datos locales extraídos exclusivamente de los
índices oficiales de horarios ICAI 2026-2027:

- `https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/` (grado).
- `https://horarios.comillas.edu/ICAIMaster1Sem/Horarios/` (máster).

Para refrescarlos después de regenerar `../analisis/inputs/icai_catalogo.json`:

```bash
python3 -m icai.horarios.extraer_horarios
```

El comando descarga los índices y sus páginas de grupo con TLS verificado,
escribe `horarios/horarios_icai.json` de forma atómica y la WebUI lo consume a
través del symlink `../webui/data/horarios_icai.json`.

La estructura del JSON es:

| Campo | Contenido |
|---|---|
| `generated_at` | Marca temporal UTC de la extracción. |
| `sources` | Índices oficiales de grado y máster usados. |
| `weeks` | Lunes ISO de las semanas publicadas; cada rango de sesión termina el domingo de su semana final publicada. |
| `courses` | Materias del catálogo con `alternatives` por grupo y sus sesiones. |
| `unmatched` | Sesiones sin match único exacto y materias del catálogo sin horario publicado. |

Cada sesión tiene día (`monday`–`friday`), horas, aula opcional, rango de
fechas y URL oficial. El vinculador solo acepta coincidencias únicas tras
normalizar Unicode, mayúsculas, espacios y tildes; admite únicamente el sufijo
administrativo terminal `+OC` y puede desambiguar un nombre duplicado con el
grado que figure de forma explícita en el grupo. Si el año del catálogo
integrado difiere del grupo publicado, solo usa el programa explícito si deja
un único candidato exacto. No usa matching difuso ni completa horarios. Por
eso una materia sin vínculo o sin horario publicado no debe interpretarse como
disponible o libre de conflictos.

Para ver resultados:

```bash
cd webui
python3 -m http.server 8000
```

Abrir `http://localhost:8000` y entrar en la tab `ICAI Comillas`.

## Validación rápida

```bash
python3 -m unittest tests/test_icai_extraccion.py tests/test_preparar_datos_icai.py tests/test_agregar_icai.py -v
node --check webui/app.js
```

## Caveats

- Las equivalencias son candidatas, no aprobación oficial.
- Las materias `Master` están incluidas porque el usuario indicó que puede cursar postgraduate, pero quedan marcadas como `permission_required`.
- `All-year` está disponible durante Fall, pero Comillas indica que vale la mitad de los ECTS por semestre.
- Las notas de waitlist, permiso, quórum o asignación se conservan desde el Excel.
- El Excel no incluye el contenido completo de las guías; el matching por nombre es conservador y debe validarse académicamente.
- Si se agregan materias nuevas al catálogo, hay que re-ejecutar los chunks `analisis/prompts/icai_chunk_NN.md` para producir nuevos matches LLM.
- Los portales de horarios publican la planificación operativa, no garantizan plaza ni matrícula. Sus cambios requieren volver a ejecutar el extractor; los rangos parciales, los nombres sin match exacto y los matches aún ambiguos permanecen explícitos en `unmatched`.
