import unittest

from icai.importar_catalogo_excel import select_available_courses


class IcaiExcelCatalogTests(unittest.TestCase):
    def test_keeps_only_visible_fall_and_all_year_courses(self):
        rows = [
            {
                "course code": "FALL-101",
                "year": 1,
                "term": 1,
                "ects": 6,
                "official name": "Materia Fall",
                "english name": "Fall Course",
                "visible": "yes",
                "degree": "GITI",
                "language. term": "ENGLISH. Fall",
                "note/comment": "",
            },
            {
                "course code": "YEAR-201",
                "year": 2,
                "term": 0,
                "ects": 6,
                "official name": "Materia Anual",
                "english name": "All-year Course",
                "visible": "yes",
                "degree": "GITT",
                "language. term": "SPANISH. All-year",
                "note/comment": "",
            },
            {
                "course code": "SPRING-301",
                "year": 3,
                "term": 2,
                "ects": 6,
                "official name": "Materia Spring",
                "english name": "Spring Course",
                "visible": "yes",
                "degree": "GITI",
                "language. term": "ENGLISH. Spring",
                "note/comment": "",
            },
            {
                "course code": "HIDDEN-401",
                "year": 4,
                "term": 1,
                "ects": 6,
                "official name": "Materia Oculta",
                "english name": "Hidden Course",
                "visible": "no",
                "degree": "GITI",
                "language. term": "ENGLISH. Fall",
                "note/comment": "",
            },
        ]

        catalog = select_available_courses(rows)

        self.assertEqual([course["codigo"] for course in catalog], ["FALL-101", "YEAR-201"])
        self.assertEqual(catalog[0]["term"], "Fall")
        self.assertEqual(catalog[0]["ects"], 6.0)
        self.assertEqual(catalog[0]["ects_semester"], 6.0)
        self.assertEqual(catalog[1]["term"], "All-year")
        self.assertEqual(catalog[1]["ects"], 6.0)
        self.assertEqual(catalog[1]["ects_semester"], 3.0)

    def test_merges_language_variants_of_the_same_course_code(self):
        base = {
            "course code": "DUP-101",
            "year": 1,
            "term": 1,
            "ects": 6,
            "official name": "Materia Bilingüe",
            "english name": "Bilingual Course",
            "visible": "yes",
            "degree": "GITI",
        }
        rows = [
            {**base, "language. term": "SPANISH. Fall", "note/comment": ""},
            {**base, "language. term": "ENGLISH. Fall", "note/comment": "English if quorum"},
        ]

        catalog = select_available_courses(rows)

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["language"], "English / Spanish")
        self.assertEqual(catalog[0]["note_comment"], "English if quorum")

    def test_marks_master_and_permission_from_excel_fields(self):
        rows = [{
            "course code": "DTC-MCS-512",
            "year": 1,
            "term": 1,
            "ects": 6,
            "official name": "Criptografía",
            "english name": "Cryptography",
            "visible": "yes",
            "degree": "MCS",
            "language. term": "SPANISH. Fall",
            "note/comment": "Permission needed",
        }]

        course = select_available_courses(rows)[0]

        self.assertEqual(course["studies"], "Master")
        self.assertEqual(course["labels"]["permission"], "permission_required")
        self.assertEqual(course["labels"]["availability"], "exchange_term")
        self.assertEqual(course["source_label"], "course_offering_2026_2027_v1_1")


if __name__ == "__main__":
    unittest.main()
