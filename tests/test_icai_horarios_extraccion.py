import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from icai.horarios.extraer_horarios import (
    build_schedule_payload,
    discover_group_pages,
    match_catalog_course,
    parse_schedule_page,
    write_json_atomically,
)


SCHEDULE_HTML = """
<table>
  <tr>
    <td class="td_cabecalho">Horas</td>
    <td class="td_cabecalho">Lunes</td>
    <td class="td_cabecalho">Martes</td>
    <td class="td_cabecalho">Miércoles</td>
    <td class="td_cabecalho">Jueves</td>
    <td class="td_cabecalho">Viernes</td>
  </tr>
  <tr>
    <td class="td_lateral">08:00 - 08:50</td>
    <td rowspan="2">Álgebra y Geometría<br>[ICAI-A-112]<br>TA</td>
    <td colspan="2">Cálculo<br>[ICAI-A-113]<br>TPA</td>
    <td>&nbsp;</td>
    <td>&nbsp;</td>
  </tr>
  <tr>
    <td class="td_lateral">09:00 - 09:50</td>
    <td>&nbsp;</td>
    <td>&nbsp;</td>
    <td>&nbsp;</td>
    <td>&nbsp;</td>
  </tr>
</table>
"""


SAME_DAY_SUBCOLUMNS_HTML = """
<table>
  <tr>
    <td>Horas</td><td colspan="2">Lunes</td><td>Martes</td><td>Miércoles</td><td>Jueves</td><td>Viernes</td>
  </tr>
  <tr>
    <td>08:00 - 08:50</td>
    <td colspan="2">Álgebra y Geometría<br>[A-101]</td>
    <td></td><td></td><td></td><td></td>
  </tr>
</table>
"""


class IcaiScheduleExtractionTests(unittest.TestCase):
    def test_parse_schedule_page_expands_spans_into_weekday_sessions(self):
        """Removing span reconstruction would lose the Monday duration or Wednesday session."""
        sessions = parse_schedule_page(
            SCHEDULE_HTML,
            "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo.html",
            "1º A GITT",
            "2026-08-31",
            "2026-11-30",
        )

        self.assertEqual(sessions, [
            {
                "raw_name": "Álgebra y Geometría",
                "group": "1º A GITT",
                "day": "monday",
                "start": "08:00",
                "end": "09:50",
                "room": "ICAI-A-112",
                "date_start": "2026-08-31",
                "date_end": "2026-11-30",
                "source_url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo.html",
            },
            {
                "raw_name": "Cálculo",
                "group": "1º A GITT",
                "day": "tuesday",
                "start": "08:00",
                "end": "08:50",
                "room": "ICAI-A-113",
                "date_start": "2026-08-31",
                "date_end": "2026-11-30",
                "source_url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo.html",
            },
            {
                "raw_name": "Cálculo",
                "group": "1º A GITT",
                "day": "wednesday",
                "start": "08:00",
                "end": "08:50",
                "room": "ICAI-A-113",
                "date_start": "2026-08-31",
                "date_end": "2026-11-30",
                "source_url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo.html",
            },
        ])

    def test_match_catalog_course_accepts_exact_official_or_english_name_after_normalization(self):
        """Changing matching to fuzzy matching or ignoring the English name would break catalog linkage."""
        catalog = [{
            "codigo": "DCIA-IMAT-212",
            "nombre": "Adquisición y Visualización de Datos / Data Acquisition and Visualization",
            "official_name": "Adquisición y Visualización de Datos",
            "english_name": "Data Acquisition and Visualization",
        }]

        match = match_catalog_course("  data\u00a0acquisition AND visualization  ", catalog)

        self.assertEqual(match, catalog[0])

    def test_match_catalog_course_rejects_ambiguous_normalized_names(self):
        """Returning the first duplicate name would silently attach a schedule to the wrong code."""
        catalog = [
            {"codigo": "A-101", "nombre": "Algorithms", "official_name": "Algorithms", "english_name": ""},
            {"codigo": "B-202", "nombre": "Algorithms", "official_name": "Algorithms", "english_name": ""},
        ]

        self.assertIsNone(match_catalog_course("algorithms", catalog))

    def test_match_catalog_course_uses_group_degree_to_resolve_exact_duplicate_name(self):
        """Removing group context would leave a published MIT session ambiguously unlinked."""
        catalog = [
            {
                "codigo": "DOI-MII-681",
                "nombre": "Dirección de Proyectos / Project Management",
                "degree": "2-MII",
            },
            {
                "codigo": "DOI-MIT-613",
                "nombre": "Dirección de Proyectos / Project Management",
                "degree": "2-MIT",
            },
        ]

        match = match_catalog_course("Dirección de Proyectos", catalog, group="2º A MIT + BA")

        self.assertEqual(match, catalog[1])

    def test_match_catalog_course_uses_unique_group_program_when_integrated_degree_year_differs(self):
        """A published 2º MII group must link to the unique 6-MII catalog candidate by program."""
        catalog = [
            {
                "codigo": "DCIA-MUIAA-512",
                "nombre": "Aprendizaje Automático / Machine Learning",
                "degree": "1-MIAA",
            },
            {
                "codigo": "DOI-MII-616",
                "nombre": "Aprendizaje Automático / Machine Learning",
                "degree": "6-MII",
            },
        ]

        match = match_catalog_course("Aprendizaje Automático", catalog, group="2º A MII")

        self.assertEqual(match, catalog[1])

    def test_match_catalog_course_accepts_explicit_trailing_oc_administrative_suffix(self):
        """Removing the deterministic +OC alias would hide a uniquely published course."""
        catalog = [{
            "codigo": "DTC-MCS-512",
            "nombre": "Criptografía, Firma Electrónica y Blockchain / Cryptography, Digital Signature and Blockchain",
            "degree": "1-MCS",
        }]

        match = match_catalog_course(
            "Criptografía, Firma electrónica y Blockchain + OC", catalog, group="1º A MCS"
        )

        self.assertEqual(match, catalog[0])

    def test_write_json_atomically_preserves_existing_file_when_serialization_fails(self):
        """Writing directly to the destination would corrupt the last valid schedule on failure."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "horarios_icai.json"
            output.write_text('{"previous": true}', encoding="utf-8")

            with self.assertRaises(TypeError):
                write_json_atomically(output, {"invalid": {"not-json"}})

            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"previous": True})
            self.assertEqual(list(output.parent.glob("*.tmp")), [])

    def test_discover_group_pages_keeps_group_and_each_official_date_range(self):
        """Collapsing index links would erase partial-semester sessions for a group."""
        index_html = """
        <ul><li>2º B GITT<ul>
          <li><a href="grupo_2_B_1_2026083120261123.html">Semanas 31/08/2026 - 23/11/2026</a></li>
          <li><a href="grupo_2_B_1_20261130.html">Semanas 30/11/2026</a></li>
        </ul></li></ul>
        """

        pages = discover_group_pages(
            index_html,
            "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/",
        )

        self.assertEqual(pages, [
            {
                "url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo_2_B_1_2026083120261123.html",
                "group": "2º B GITT",
                "date_start": "2026-08-31",
                "date_end": "2026-11-29",
            },
            {
                "url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo_2_B_1_20261130.html",
                "group": "2º B GITT",
                "date_start": "2026-11-30",
                "date_end": "2026-12-06",
            },
        ])
        self.assertLessEqual(date(2026, 12, 4), date.fromisoformat(pages[-1]["date_end"]))

    def test_build_schedule_payload_marks_catalog_courses_without_published_schedule(self):
        """Omitting catalog courses after extraction would present missing schedules as conflict-free."""
        catalog = [
            {
                "codigo": "ALG-101",
                "nombre": "Álgebra y Geometría",
                "official_name": "Álgebra y Geometría",
                "english_name": "",
            },
            {
                "codigo": "MISSING-202",
                "nombre": "Materia sin horario",
                "official_name": "Materia sin horario",
                "english_name": "",
            },
        ]
        pages = [{
            "source": "grado",
            "url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo_1.html",
            "group": "1º A GITT",
            "date_start": "2026-08-31",
            "date_end": "2026-11-30",
            "html": SCHEDULE_HTML,
        }]

        payload = build_schedule_payload(catalog, pages)

        self.assertEqual([course["codigo"] for course in payload["courses"]], ["ALG-101"])
        self.assertIn(
            {
                "codigo": "MISSING-202",
                "nombre": "Materia sin horario",
                "reason": "no_published_schedule",
            },
            payload["unmatched"],
        )

    def test_build_schedule_payload_deduplicates_same_day_subcolumns_within_alternative(self):
        """Without output deduplication, one Monday block is rendered twice for the same group."""
        catalog = [{"codigo": "ALG-101", "nombre": "Álgebra y Geometría", "degree": "1-GITT"}]
        pages = [{
            "source": "grado",
            "url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo_1.html",
            "group": "1º A GITT",
            "date_start": "2026-08-31",
            "date_end": "2026-09-06",
            "html": SAME_DAY_SUBCOLUMNS_HTML,
        }]

        payload = build_schedule_payload(catalog, pages)

        self.assertEqual(payload["courses"][0]["alternatives"][0]["sessions"], [{
            "day": "monday",
            "start": "08:00",
            "end": "08:50",
            "room": "A-101",
            "date_start": "2026-08-31",
            "date_end": "2026-09-06",
            "source_url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo_1.html",
        }])

    def test_build_schedule_payload_marks_ambiguous_catalog_codes_as_schedule_present(self):
        """A name with two catalog codes must not make either code look like it has no published schedule."""
        catalog = [
            {"codigo": "A-101", "nombre": "Algorithms", "degree": "2-A"},
            {"codigo": "B-202", "nombre": "Algorithms", "degree": "2-B"},
        ]
        pages = [{
            "source": "grado",
            "url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo_1.html",
            "group": "2º A Shared",
            "date_start": "2026-08-31",
            "date_end": "2026-09-06",
            "html": SCHEDULE_HTML.replace("Álgebra y Geometría", "Algorithms"),
        }]

        payload = build_schedule_payload(catalog, pages)

        status_rows = [
            row for row in payload["unmatched"]
            if row.get("reason") == "schedule_present_but_not_uniquely_linked"
        ]
        self.assertEqual(status_rows, [
            {
                "codigo": "A-101",
                "nombre": "Algorithms",
                "reason": "schedule_present_but_not_uniquely_linked",
                "candidate_codes": ["A-101", "B-202"],
                "session_count": 1,
            },
            {
                "codigo": "B-202",
                "nombre": "Algorithms",
                "reason": "schedule_present_but_not_uniquely_linked",
                "candidate_codes": ["A-101", "B-202"],
                "session_count": 1,
            },
        ])
        self.assertIn(
            {
                "raw_name": "Algorithms",
                "group": "2º A Shared",
                "day": "monday",
                "start": "08:00",
                "end": "09:50",
                "room": "ICAI-A-112",
                "date_start": "2026-08-31",
                "date_end": "2026-09-06",
                "source_url": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/grupo_1.html",
                "reason": "ambiguous_exact_catalog_match",
                "candidate_codes": ["A-101", "B-202"],
            },
            payload["unmatched"],
        )
        self.assertNotIn(
            {"codigo": "A-101", "nombre": "Algorithms", "reason": "no_published_schedule"},
            payload["unmatched"],
        )


if __name__ == "__main__":
    unittest.main()
