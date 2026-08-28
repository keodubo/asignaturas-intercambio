# Diseño: combinador de horarios ICAI

**Fecha:** 2026-08-28

## Objetivo

Agregar a la WebUI una subpestaña `Horarios` que genere y muestre combinaciones semanales para las materias ICAI marcadas con estrella. Los horarios se obtienen exclusivamente de los portales oficiales de grado y máster del primer semestre 2026-2027.

## Fuentes

- `https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/`
- `https://horarios.comillas.edu/ICAIMaster1Sem/Horarios/`

El extractor guarda URL, grupo, rango de fechas y fecha de extracción. La WebUI consume un JSON local generado; no consulta los portales desde el navegador.

## Flujo de datos

1. Descargar los índices oficiales de grado y máster.
2. Descubrir todas las páginas de grupos y rangos semanales.
3. Parsear cada tabla respetando `rowspan` y `colspan` para reconstruir día, inicio, fin, materia, aula y grupo.
4. Normalizar nombres y vincularlos con el catálogo ICAI derivado del Excel.
5. Rechazar matches ambiguos; registrar materias sin horario o sin vínculo.
6. Escribir `icai/horarios/horarios_icai.json` y exponerlo mediante `webui/data/horarios_icai.json`.

## Modelo

Cada materia tiene una o más alternativas de grupo. Una alternativa contiene todas sus sesiones, con:

- código y nombre ICAI;
- origen `grado` o `master`;
- grupo;
- día de semana;
- hora de inicio y fin;
- aula/modalidad;
- fecha inicial y final de vigencia;
- URL oficial.

Una combinación selecciona exactamente una alternativa por cada código ICAI marcado con estrella.

## Conflictos y opciones

- Dos sesiones se superponen si comparten día, intervalo horario y al menos una fecha semanal dentro de sus rangos de vigencia.
- Se generan todas las combinaciones sin conflicto durante todo Fall.
- Se deduplican opciones con el mismo horario efectivo.
- Las opciones se ordenan por menos días ocupados, menos huecos y finalización más temprana.
- Si no existe una opción perfecta, se muestran las alternativas con el menor número de conflictos; los bloques conflictivos aparecen en rojo y comparten carril.
- Una materia seleccionada sin horario publicado aparece como advertencia y no se presenta falsamente como libre de conflicto.

## Interfaz

El carrito tendrá dos subpestañas:

- `Materias`: lista y acciones existentes.
- `Horarios`: combinador de las materias ICAI con estrella.

La vista de horarios tendrá:

- selector de semana;
- navegación anterior/siguiente y `Opción X de N`;
- grilla lunes-viernes con eje horario;
- color estable por materia;
- nombre, grupo, aula/modalidad y horario dentro de cada bloque;
- resumen de conflictos y materias sin horario;
- actualización automática al agregar o quitar estrellas.

La semana cambia únicamente la visualización. La validez de una opción se calcula contra todo el semestre.

## Errores y degradación

- Si el JSON no carga, la pestaña explica que deben refrescarse los horarios.
- Si una materia no tiene match exacto, se lista en `Sin horario vinculado`.
- Si los portales cambian de estructura, el extractor falla con diagnóstico y no reemplaza silenciosamente un JSON válido.
- No se inventan horarios ni se completa información ausente.

## Pruebas y verificación

- Pruebas unitarias blackbox para parsing de tablas con spans, matching de nombres, solapamiento por fechas, generación y orden de combinaciones.
- Validación de que todos los códigos vinculados existen en el catálogo ICAI Fall/All-year.
- Verificación de sintaxis JS y respuesta HTTP de los nuevos datos.
- Verificación visual en escritorio y ancho reducido de la grilla y los estados de conflicto.

## Fuera de alcance

- Edición manual de horarios.
- Horarios catálogo externo anterior.
- Calendario de exámenes.
- Garantizar disponibilidad de plaza; el horario publicado no equivale a matrícula.
