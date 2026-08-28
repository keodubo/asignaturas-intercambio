import unittest

from analisis.agregar_icai import recommendation_bucket, sort_recommendations


class IcaiAggregationTests(unittest.TestCase):
    def test_recommendation_bucket(self):
        self.assertEqual(recommendation_bucket("Fall", "Undergraduate", 5), "primary")
        self.assertEqual(recommendation_bucket("Fall/Spring", "Undergraduate", 5), "primary")
        self.assertEqual(recommendation_bucket("Fall", "Master", 5), "conditional")
        self.assertEqual(recommendation_bucket("All-year", "Undergraduate", 4), "strong_candidate")
        self.assertEqual(recommendation_bucket("Full-year", "Undergraduate", 4), "strong_candidate")
        self.assertEqual(recommendation_bucket("Spring", "Undergraduate", 5), "backup_only")
        self.assertEqual(recommendation_bucket("Fall", "Undergraduate", 2), "backup_only")

    def test_sort_recommendations_prioritizes_primary(self):
        rows = [
            {"recommendation_bucket": "backup_only", "confianza": 5, "availability_label": "not_in_exchange_term", "permission_label": "standard", "codigo_icai": "B"},
            {"recommendation_bucket": "primary", "confianza": 4, "availability_label": "exchange_term", "permission_label": "standard", "codigo_icai": "A"},
            {"recommendation_bucket": "conditional", "confianza": 5, "availability_label": "exchange_term", "permission_label": "permission_required", "codigo_icai": "C"},
        ]
        sorted_rows = sort_recommendations(rows)
        self.assertEqual([r["codigo_icai"] for r in sorted_rows], ["A", "C", "B"])


if __name__ == "__main__":
    unittest.main()
