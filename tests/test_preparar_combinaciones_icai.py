import unittest

from analisis.preparar_combinaciones_icai import build_candidate_pairs, render_prompt


class IcaiCombinationPreparationTests(unittest.TestCase):
    def test_build_candidate_pairs_only_pairs_sub4_same_itba_courses(self):
        rows = [
            {
                "codigo_icai": "A",
                "nombre_icai": "A",
                "codigo_itba": "72.80",
                "nombre_itba": "Big Data",
                "confianza": "3",
                "comentario": "cubre Hadoop",
            },
            {
                "codigo_icai": "B",
                "nombre_icai": "B",
                "codigo_itba": "72.80",
                "nombre_itba": "Big Data",
                "confianza": "2",
                "comentario": "cubre Spark",
            },
            {
                "codigo_icai": "C",
                "nombre_icai": "C",
                "codigo_itba": "72.80",
                "nombre_itba": "Big Data",
                "confianza": "4",
                "comentario": "match fuerte individual",
            },
            {
                "codigo_icai": "D",
                "nombre_icai": "D",
                "codigo_itba": "72.74",
                "nombre_itba": "Visualizacion",
                "confianza": "3",
                "comentario": "otra ITBA",
            },
        ]

        pairs = build_candidate_pairs(rows)

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["codigo_itba"], "72.80")
        self.assertEqual(pairs[0]["materia_1"]["codigo_icai"], "A")
        self.assertEqual(pairs[0]["materia_2"]["codigo_icai"], "B")

    def test_build_candidate_pairs_deduplicates_reversed_pairs(self):
        rows = [
            {
                "codigo_icai": "B",
                "nombre_icai": "B",
                "codigo_itba": "72.80",
                "nombre_itba": "Big Data",
                "confianza": "2",
                "comentario": "cubre Spark",
            },
            {
                "codigo_icai": "A",
                "nombre_icai": "A",
                "codigo_itba": "72.80",
                "nombre_itba": "Big Data",
                "confianza": "3",
                "comentario": "cubre Hadoop",
            },
        ]

        pairs = build_candidate_pairs(rows)

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["pair_key"], "72.80|A|B")

    def test_render_prompt_requires_real_complementarity(self):
        prompt = render_prompt([{
            "pair_key": "72.80|A|B",
            "codigo_itba": "72.80",
            "nombre_itba": "Big Data",
            "materia_1": {
                "codigo_icai": "A",
                "nombre_icai": "A",
                "confianza": 3,
                "comentario": "Hadoop",
            },
            "materia_2": {
                "codigo_icai": "B",
                "nombre_icai": "B",
                "confianza": 2,
                "comentario": "Spark",
            },
        }])

        self.assertIn("confianza_combinada", prompt)
        self.assertIn("No emitir", prompt)
        self.assertIn("complementa", prompt)
        self.assertIn('"codigo_icai_1"', prompt)


if __name__ == "__main__":
    unittest.main()
