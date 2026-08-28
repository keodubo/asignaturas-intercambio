# ICAI Comillas Equivalencias Design

## Goal

Replicar el flujo de equivalencias ITBA -> catálogo externo anterior para ICAI/Comillas, usando la fuente oficial de cursos para exchange y manteniendo los resultados ICAI separados de los outputs catálogo externo anterior existentes.

El objetivo practico es encontrar candidatas de equivalencia para un intercambio en Espana durante septiembre-diciembre, sin descartar cursos por idioma, nivel o semestre antes del analisis. El sistema debe incluir cursos de grado y postgrado, cursos Fall, Full-year/Annual y Spring, y etiquetar claramente el riesgo operativo de cada opcion.

## Source

Fuente primaria: `https://apps.icai.comillas.edu/exchange/`.

La pagina publica tablas de cursos 2025-26 con columnas:

- `Language`
- `Term`
- `Schedule`
- `Studies`
- `Degree`
- `ECTS`
- `Code`
- `Subject`
- `Syllabus`

La extraccion debe preservar los links de syllabus/repository disponibles por curso. Si hay varios repositorios por anio, el scraper debe priorizar el mas reciente disponible y conservar los links alternativos como evidencia secundaria.

## Scope

Incluir en el catalogo ICAI:

- `Term`: `Fall`, `Full-year`, `Spring`
- `Studies`: `Undergraduate`, `Master`
- Idiomas: ingles, espanol y cualquier otro valor publicado
- Horarios: `Morning`, `Afternoon`, `pending` u otros valores publicados

No incluir filtros duros por idioma, nivel o semestre en la extraccion. Esos criterios se convierten en etiquetas para ranking, filtros y decision manual.

## Out Of Scope

- Enviar solicitudes oficiales de equivalencia en sistemas ITBA o Comillas.
- Decidir aprobacion final de equivalencias. Los resultados son candidatos academicos.
- Scraping autenticado o acceso con credenciales.
- Resolver choques horarios reales, porque los horarios detallados pueden requerir otra fuente.
- Reemplazar el pipeline catálogo externo anterior actual.

## Data Model

Cada curso ICAI en `analisis/inputs/icai_catalogo.json` debe tener:

```json
{
  "codigo": "DTC-MIC-523",
  "nombre": "Cybersecurity",
  "institucion": "icai_comillas",
  "term": "Spring",
  "studies": "Master",
  "degree": "2-MIC",
  "schedule": "Afternoon",
  "language": "",
  "ects": 3.0,
  "url_guia": "https://intranet.comillas.edu/GuiasDocentes/publico/repositorio/?a=...&c=2026&i=es-ES",
  "syllabus_links": [
    {
      "label": "Repo 2024-25",
      "url": "https://intranet.comillas.edu/GuiasDocentes/publico/repositorio/?a=...&c=2026&i=es-ES"
    }
  ],
  "guia": {
    "descripcion": "",
    "competencias": "",
    "contenidos": "",
    "metodologia": "",
    "evaluacion": "",
    "bibliografia": ""
  },
  "labels": {
    "availability": "not_in_exchange_term",
    "timing_risk": "high",
    "level": "postgraduate",
    "permission": "permission_required",
    "language": "unknown",
    "schedule": "afternoon",
    "recommendation_bucket": "backup_only"
  }
}
```

## Etiquetado

El etiquetado debe ser explicito, persistir en JSON/CSV y estar disponible como filtro en la WebUI.

### Availability Label

| Label | Regla | Uso |
|---|---|---|
| `exchange_term` | `term == "Fall"` | Candidata principal para septiembre-diciembre |
| `full_year` | `term == "Full-year"` | Posible, pero requiere confirmar cursada parcial/anual |
| `not_in_exchange_term` | `term == "Spring"` | Equivalencia academica/back-up, no cursable en septiembre-diciembre salvo excepcion |

### Timing Risk Label

| Label | Regla | Uso |
|---|---|---|
| `low` | Fall | Riesgo temporal bajo |
| `medium` | Full-year | Requiere confirmacion academica |
| `high` | Spring | No coincide con la estadia prevista |

### Level Label

| Label | Regla | Uso |
|---|---|---|
| `undergraduate` | `studies == "Undergraduate"` | Normalmente mas simple de aprobar |
| `postgraduate` | `studies == "Master"` o seccion postgrado | Potencialmente util, pero requiere permiso |

### Permission Label

| Label | Regla | Uso |
|---|---|---|
| `standard` | Undergraduate | Sin advertencia especial desde la pagina |
| `permission_required` | Master/Postgraduate | La propia pagina indica permiso requerido para estudiantes de exchange undergraduate |

### Language Label

| Label | Regla | Uso |
|---|---|---|
| `english` | Language o subject indica ingles | Cursable por preferencia del usuario |
| `spanish` | Language o subject indica espanol | Cursable por preferencia del usuario |
| `mixed` | Nombre bilingue o guia con ambos idiomas | Cursable por preferencia del usuario |
| `unknown` | Fuente no publica idioma claro | No descartar; revisar manualmente |

### Recommendation Bucket

| Label | Regla | Uso |
|---|---|---|
| `primary` | Fall + confianza >= 4 | Primero para plan de cursada |
| `strong_candidate` | Fall + confianza 3, o Full-year + confianza >= 4 | Revisar despues de primarias |
| `conditional` | Master o Full-year con buen match | Requiere confirmacion de permiso/fechas |
| `backup_only` | Spring o confianza 2 | Guardar como evidencia, no basar plan principal |

## Matching

El matching compara cursos ICAI contra las materias ITBA target ya existentes en `itba_info/materias_filtradas_detallado.csv`.

La rubrica de confianza se mantiene compatible con catálogo externo anterior:

- `5`: equivalente directa, casi 1:1
- `4`: buena, con gaps menores
- `3`: parcial-fuerte
- `2`: parcial-debil, util como candidata secundaria
- `1`: marginal, no se emite
- `0`: no equivalente, no se emite

El prompt ICAI debe exigir comentarios con topicos concretos de ambos lados. Cuando el syllabus no se pueda parsear, el comentario debe decirlo explicitamente y bajar la confianza salvo que el nombre sea inequívoco.

## Outputs

Crear outputs nuevos, sin sobrescribir catálogo externo anterior:

- `icai/exchange.html`
- `icai/extraccion_materias_icai.py`
- `icai/extraccion_materias/icai_catalogo.csv`
- `icai/guias_docentes/html/*.html`
- `icai/guias_docentes/pdfs/*.pdf`
- `icai/guias_docentes/contenidos.json`
- `analisis/inputs/icai_catalogo.json`
- `analisis/prompts/icai_chunk_NN.md`
- `analisis/outputs/raw/icai_chunk_NN.json`
- `resultados/icai_equivalencias.csv`
- `resultados/icai_sin_equivalencia.csv`
- `resultados/icai_recomendaciones.csv`

## WebUI

Agregar ICAI como vista separada sin romper las tabs catálogo externo anterior.

Filtros nuevos para ICAI:

- `Term`: Fall, Full-year, Spring
- `Studies`: Undergraduate, Master
- `Degree`
- `Schedule`
- `Availability`
- `Timing risk`
- `Permission`
- `Recommendation bucket`
- `Confianza`
- Busqueda libre

La tabla ICAI debe mostrar las etiquetas de forma visible. El ranking por defecto debe ordenar por:

1. `recommendation_bucket`
2. `confianza` descendente
3. `availability`
4. `permission`
5. `codigo_icai`

## Verification

La implementacion se considera lista cuando:

- El scraper extrae filas ICAI desde la pagina oficial sin credenciales.
- El catalogo conserva Fall, Full-year, Spring, Undergraduate y Master.
- Los labels se calculan de forma deterministica.
- Los prompts ICAI se generan sin tocar prompts catálogo externo anterior.
- La agregacion produce CSVs ICAI con columnas de etiquetas.
- La WebUI carga ICAI y permite filtrar por etiquetas.
- El README o un doc ICAI explica que Spring y Full-year son utiles para evidencia academica pero no equivalen automaticamente a cursabilidad septiembre-diciembre.

## Risks

- La pagina usa datos 2025-26 como proxy; la oferta real 2026-27 puede cambiar.
- Algunas materias Master requieren permiso aunque sean buen match academico.
- Spring puede producir matches academicos fuertes pero no servir para el semestre Fall.
- Full-year puede no ser aprobable si exige cursada anual completa.
- Los syllabi pueden estar en repositorios historicos; hay que guardar fuente y anio para trazabilidad.

## Rollback

Como el pipeline ICAI se agrega en archivos separados, el rollback es eliminar:

- `icai/`
- `analisis/inputs/icai_catalogo.json`
- `analisis/prompts/icai_chunk_*.md`
- `analisis/outputs/raw/icai_chunk_*.json`
- `resultados/icai_*.csv`

Y revertir los cambios WebUI/README si se hubieran aplicado.
