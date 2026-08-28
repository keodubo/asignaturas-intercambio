# Equivalencias ITBA ↔ ICAI-Comillas

Herramientas y datos para analizar equivalencias entre las materias pendientes de Ingeniería Informática en ITBA y la oferta de intercambio de ICAI-Comillas.

> [!IMPORTANT]
> Los resultados son orientativos. Toda equivalencia y disponibilidad debe ser confirmada por las autoridades académicas correspondientes.

## Fuente oficial

El catálogo se importa exclusivamente desde `../___Course_Offering_26-27_Student_Version_1.1.xlsx`, hoja `OFFER 2026-2027 PROVISIONAL`. Solo se conservan filas visibles de `Fall` y `All-year`; para estas últimas se computa la mitad de los ECTS durante Fall.

## Componentes

- `itba_info/`: materias objetivo y contenidos de ITBA usados para comparar temarios.
- `icai/`: importador del catálogo, fuentes ICAI, guías y extractor de horarios oficiales.
- `analisis/`: inputs, prompts, resultados crudos y agregadores del matching ICAI.
- `resultados/`: equivalencias, recomendaciones, combinaciones y materias sin equivalencia.
- `webui/`: explorador estático, carrito y combinador de horarios ICAI.
- `tests/`: pruebas unitarias y de comportamiento del pipeline y la WebUI.
- `docs/superpowers/`: diseños y planes correspondientes a ICAI.

## Uso

```bash
/path/to/python-with-openpyxl icai/importar_catalogo_excel.py \
  --source ../___Course_Offering_26-27_Student_Version_1.1.xlsx
python3 analisis/preparar_datos_icai.py
python3 analisis/agregar_icai.py
python3 analisis/preparar_combinaciones_icai.py
python3 analisis/agregar_combinaciones_icai.py
python3 -m icai.horarios.extraer_horarios
```

Los prompts de matching se guardan en `analisis/prompts/icai_chunk_NN.md` y sus respuestas JSON en `analisis/outputs/raw/icai_chunk_NN.json`.

Para abrir la WebUI:

```bash
cd webui
python3 -m http.server 8000
```

Abrir `http://localhost:8000`.

## Despliegue estático

Vercel construye `dist/` desde `webui/` y materializa sus enlaces de datos como
archivos estáticos. Para reproducir el build localmente en un directorio temporal:

```bash
build_dir="$(mktemp -d)"
mkdir -p "$build_dir/dist"
cp -RL webui/. "$build_dir/dist/"
python3 -m http.server 8000 --directory "$build_dir/dist"
```

## Criterios

- La equivalencia se estima por solapamiento temático, no por comparación directa de créditos ITBA y ECTS.
- Las materias de máster se etiquetan `permission_required`.
- Los horarios ambiguos o no vinculados no se consideran libres de conflicto ni garantizan inscripción.
- Toda equivalencia es candidata y requiere validación académica oficial.

## Contribuir

Los aportes son bienvenidos mediante forks y pull requests. Antes de proponer cambios, consultá [CONTRIBUTING.md](CONTRIBUTING.md) para conocer el flujo de trabajo, las reglas de datos y las pruebas requeridas.

## Licencia y fuentes de terceros

El código y la documentación original de este proyecto se distribuyen bajo la [licencia MIT](LICENSE).

Los catálogos, horarios, programas académicos y demás datos procedentes de ITBA, ICAI-Comillas u otras fuentes externas conservan los derechos y condiciones de sus respectivos titulares. Su presencia en este repositorio no implica que hayan sido relicenciados bajo MIT.
