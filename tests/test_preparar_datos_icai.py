import csv
import json
import tempfile
import unittest
from pathlib import Path

from analisis.preparar_datos_icai import load_icai_catalogo, recommendation_bucket_for_prompt


class IcaiPrepareDataTests(unittest.TestCase):
    def test_load_icai_catalogo_preserves_labels_and_syllabus_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            csv_path = base / "icai_catalogo.csv"
            contenidos_path = base / "contenidos.json"
            with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "language", "term", "schedule", "studies", "degree", "ects", "codigo",
                    "nombre", "url_guia", "source_label", "program_label", "source_url",
                    "syllabus_links_json", "availability_label", "timing_risk_label",
                    "level_label", "permission_label", "language_label", "schedule_label",
                ])
                writer.writeheader()
                writer.writerow({
                    "language": "English",
                    "term": "Fall",
                    "schedule": "Morning",
                    "studies": "Undergraduate",
                    "degree": "3-DCC",
                    "ects": "6",
                    "codigo": "DTC-GITT-315",
                    "nombre": "Software Engineering",
                    "url_guia": "https://example.test/repo",
                    "source_label": "exchange_catalog",
                    "program_label": "regular_icai",
                    "source_url": "https://apps.icai.comillas.edu/exchange/",
                    "syllabus_links_json": '[{"label":"Repo 2024-25","url":"https://example.test/repo"}]',
                    "availability_label": "exchange_term",
                    "timing_risk_label": "low",
                    "level_label": "undergraduate",
                    "permission_label": "standard",
                    "language_label": "english",
                    "schedule_label": "morning",
                })
            contenidos_path.write_text(json.dumps({
                "DTC-GITT-315": {"contenidos": "Requirements, design, testing"}
            }), encoding="utf-8")

            catalog = load_icai_catalogo(csv_path, contenidos_path)

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["codigo"], "DTC-GITT-315")
        self.assertEqual(catalog[0]["institucion"], "icai_comillas")
        self.assertEqual(catalog[0]["source_label"], "exchange_catalog")
        self.assertEqual(catalog[0]["program_label"], "regular_icai")
        self.assertEqual(catalog[0]["source_url"], "https://apps.icai.comillas.edu/exchange/")
        self.assertEqual(catalog[0]["labels"]["availability"], "exchange_term")
        self.assertEqual(catalog[0]["guia"]["contenidos"], "Requirements, design, testing")

    def test_recommendation_bucket_for_prompt(self):
        self.assertEqual(recommendation_bucket_for_prompt("Fall", "Undergraduate", 4), "primary")
        self.assertEqual(recommendation_bucket_for_prompt("Fall/Spring", "Undergraduate", 4), "primary")
        self.assertEqual(recommendation_bucket_for_prompt("Fall", "Undergraduate", 3), "strong_candidate")
        self.assertEqual(recommendation_bucket_for_prompt("All-year", "Undergraduate", 4), "strong_candidate")
        self.assertEqual(recommendation_bucket_for_prompt("Full-year", "Undergraduate", 4), "strong_candidate")
        self.assertEqual(recommendation_bucket_for_prompt("Fall", "Master", 4), "conditional")
        self.assertEqual(recommendation_bucket_for_prompt("Spring", "Master", 5), "backup_only")
        self.assertEqual(recommendation_bucket_for_prompt("Fall", "Undergraduate", 2), "backup_only")


if __name__ == "__main__":
    unittest.main()
