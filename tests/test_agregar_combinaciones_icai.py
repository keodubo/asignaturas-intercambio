import unittest

from analisis.agregar_combinaciones_icai import (
    availability_pair_label,
    permission_pair_label,
    row_from_combination,
)


class IcaiCombinationAggregationTests(unittest.TestCase):
    def test_pair_labels_take_riskiest_value(self):
        self.assertEqual(
            availability_pair_label("exchange_term", "full_year"),
            "mixed_or_risky",
        )
        self.assertEqual(
            availability_pair_label("exchange_term", "exchange_term"),
            "exchange_term",
        )
        self.assertEqual(
            permission_pair_label("standard", "permission_required"),
            "permission_required",
        )

    def test_row_from_combination_calculates_total_ects(self):
        combo = {
            "codigo_icai_1": "A",
            "codigo_icai_2": "B",
            "codigo_itba": "72.80",
            "confianza_combinada": 4,
            "comentario_combinacion": "combinan bien",
            "complementa_por": "A batch, B streaming",
            "gaps_restantes": "validar detalle",
        }
        icai = {
            "A": {
                "codigo": "A",
                "nombre": "A",
                "term": "Fall",
                "studies": "Undergraduate",
                "ects": 3.0,
                "url_guia": "u1",
                "labels": {
                    "availability": "exchange_term",
                    "permission": "standard",
                },
                "source_label": "exchange_catalog",
            },
            "B": {
                "codigo": "B",
                "nombre": "B",
                "term": "Fall",
                "studies": "Master",
                "ects": 6.0,
                "url_guia": "u2",
                "labels": {
                    "availability": "exchange_term",
                    "permission": "permission_required",
                },
                "source_label": "exchange_catalog",
            },
        }
        itba = {"72.80": {"codigo": "72.80", "nombre": "Big Data"}}
        individual = {("A", "72.80"): 3, ("B", "72.80"): 2}

        row = row_from_combination(combo, icai, itba, individual)

        self.assertEqual(row["ects_total"], 9.0)
        self.assertEqual(row["confianza_individual_1"], 3)
        self.assertEqual(row["permission_pair_label"], "permission_required")


if __name__ == "__main__":
    unittest.main()
