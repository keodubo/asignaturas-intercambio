# Contribuir

Gracias por querer mejorar el proyecto. Se aceptan correcciones, mejoras de la WebUI, nuevos extractores y propuestas de equivalencias respaldadas por fuentes académicas oficiales.

## Flujo recomendado

1. Hacé un fork del repositorio.
2. Creá una rama descriptiva desde `main`.
3. Implementá un cambio acotado y documentá su fuente cuando modifique datos académicos.
4. Ejecutá las pruebas:

   ```bash
   python3 -m unittest discover -s tests
   node --test tests/*.test.js tests/*.test.mjs
   ```

5. Abrí un pull request explicando el problema, la solución y cómo verificaste el cambio.

## Criterios de contribución

- Conservá únicamente materias ICAI visibles y ofrecidas en `Fall` o `All-year`.
- Para una materia `All-year`, computá la mitad de sus ECTS durante Fall.
- Marcá las materias de máster como `permission_required`.
- No relaciones horarios ambiguos: el vínculo debe ser exacto, único o seguir una regla administrativa documentada.
- Evaluá equivalencias por solapamiento sustantivo de temarios, no por comparación directa entre créditos ITBA y ECTS.
- Tratá toda equivalencia como candidata pendiente de validación académica oficial.
- No incluyas credenciales, datos personales ni material cuya redistribución no esté autorizada.

## Pruebas

Las pruebas nuevas deben ser unitarias, black-box y centradas en comportamiento observable. Evitá comprobaciones de detalles internos, texto fuente o estructura de implementación.

## Datos y fuentes externas

La licencia MIT cubre el código y la documentación original del proyecto. Los catálogos, horarios, programas de materias y demás materiales procedentes de ITBA, ICAI-Comillas u otras fuentes conservan los derechos y condiciones de sus respectivos titulares. Una contribución no debe presentar esos materiales como propios ni ampliar sus permisos de uso.
