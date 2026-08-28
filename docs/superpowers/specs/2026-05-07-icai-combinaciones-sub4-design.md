# ICAI Combinaciones Sub-4 Design

## Goal

Agregar un flujo ICAI para detectar pares de materias externas que, combinadas, puedan valer por una materia ITBA cuando cada materia individual tiene confianza menor a 4.

El objetivo practico es encontrar oportunidades de equivalencia que el matching 1:1 actual deja como parciales (`confianza` 2 o 3), pero que pueden volverse fuertes si dos materias cubren topicos complementarios de la misma materia ITBA.

## Scope

Aplica solo a ICAI-Comillas.

Incluir como candidatas para combinar solo matches individuales ICAI existentes con:

- `confianza < 4`
- `confianza >= 2`
- misma `codigo_itba`
- dos materias ICAI distintas

Una combinacion se emite solo si la cobertura combinada estimada llega a `confianza_combinada >= 4`.

## Out Of Scope

- catálogo externo anterior.
- Tab `sin_guia`.
- Mezclar una materia ICAI con una catálogo externo anterior.
- Generar combinaciones de tres o mas materias.
- Decidir aprobacion oficial. El output sigue siendo evidencia academica candidata.
- Validar choques horarios reales.

## Matching Rule

Dos materias ICAI sub-4 se consideran complementarias cuando:

- cubren bloques tematicos distintos de la misma materia ITBA;
- el segundo curso aporta topicos que el primero deja como faltantes;
- la combinacion reduce los gaps principales que justificaban las confianzas 2 o 3;
- la justificacion puede citar topicos concretos de ambas materias y de ITBA.

No alcanza con que ambas materias apunten a la misma ITBA. Si cubren la misma parte o una de las dos no aporta cobertura nueva, no se emite la combinacion.

## Confidence

`confianza_combinada` mantiene la rubrica existente:

- `5`: el par cubre casi todo el temario ITBA, con gaps menores o nulos.
- `4`: el par cubre la mayoria sustantiva del temario ITBA, aunque pueda requerir validacion manual.

No emitir pares con confianza combinada 2 o 3.

## Data Flow

1. Usar `resultados/icai_equivalencias.csv` como fuente de matches individuales ya agregados.
2. Filtrar filas ICAI con `confianza` 2 o 3.
3. Agrupar por `codigo_itba`.
4. Construir pares de materias ICAI distintas dentro de cada grupo.
5. Generar un prompt de revision de pares para que un agente/LLM evalue complementariedad real.
6. Escribir JSON crudo en `analisis/outputs/raw/icai_combinaciones.json`.
7. Agregar ese JSON contra `analisis/inputs/icai_catalogo.json` e `itba_targets.json`.
8. Emitir `resultados/icai_combinaciones.csv`.
9. Mostrar el CSV en la WebUI como vista separada de combinaciones.

## Outputs

Nuevo input intermedio:

- `analisis/inputs/icai_combinaciones_candidatas.json`

Nuevo prompt:

- `analisis/prompts/icai_combinaciones.md`

Nuevo output crudo:

- `analisis/outputs/raw/icai_combinaciones.json`

Nuevo CSV:

- `resultados/icai_combinaciones.csv`

Columnas esperadas:

- `codigo_icai_1`
- `nombre_icai_1`
- `term_1`
- `studies_1`
- `ects_icai_1`
- `confianza_individual_1`
- `codigo_icai_2`
- `nombre_icai_2`
- `term_2`
- `studies_2`
- `ects_icai_2`
- `confianza_individual_2`
- `ects_total`
- `codigo_itba`
- `nombre_itba`
- `confianza_combinada`
- `comentario_combinacion`
- `complementa_por`
- `gaps_restantes`
- `availability_pair_label`
- `permission_pair_label`
- `source_labels`
- `url_guia_icai_1`
- `url_guia_icai_2`

## WebUI

Agregar una tab o vista `ICAI combinaciones`.

La tabla debe dejar claro que cada fila representa dos materias externas por una ITBA. No debe confundirse con una equivalencia 1:1.

Filtros v1:

- confianza combinada;
- busqueda libre;
- availability del par;
- permission del par;
- studies/term por texto visible.

El carrito puede agregar combinaciones como un item unico, con ambos codigos ICAI preservados en comentario o campos dedicados si se extiende el CSV de exportacion.

## Verification

La implementacion se considera lista cuando:

- hay tests unitarios para generacion de pares candidatos;
- hay tests unitarios para agregacion del JSON crudo a CSV;
- el pipeline no modifica los outputs ICAI 1:1 existentes;
- `python3 analisis/preparar_combinaciones_icai.py` genera candidatos y prompt;
- `python3 analisis/agregar_combinaciones_icai.py` genera `resultados/icai_combinaciones.csv`;
- la WebUI carga `icai_combinaciones.csv` sin romper las tabs existentes;
- la documentacion explica que las combinaciones son candidatas manuales, no equivalencias oficiales.

## Risks

- ICAI no tiene contenidos de guias parseados en el estado actual; muchas decisiones dependen del comentario LLM individual y del nombre de materia.
- Dos materias pueden ser complementarias academica pero no cursables juntas por horario, cupo o permiso.
- Materias Master siguen requiriendo permiso aunque formen parte de una buena combinacion.
- Si los matches individuales sub-4 son incompletos, el universo de combinaciones tambien queda incompleto.

## Rollback

Como el cambio es aditivo, el rollback es eliminar:

- `analisis/preparar_combinaciones_icai.py`
- `analisis/agregar_combinaciones_icai.py`
- `analisis/inputs/icai_combinaciones_candidatas.json`
- `analisis/prompts/icai_combinaciones.md`
- `analisis/outputs/raw/icai_combinaciones.json`
- `resultados/icai_combinaciones.csv`

Y revertir los cambios WebUI/README asociados.
