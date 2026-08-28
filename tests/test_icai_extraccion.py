import unittest

from icai.extraccion_materias_icai import compute_labels, parse_exchange_html, parse_sapiens_html


HTML_FIXTURE = """
<html><body>
<p><strong>UNDERGRADUATE courses. FALL semester (2025-26)</strong></p>
<table>
  <tr>
    <td>Language</td><td>Term</td><td>Schedule</td><td>Studies</td>
    <td>Degree</td><td>ECTS*</td><td>Code</td><td>Subject</td><td>Syllabus</td>
  </tr>
  <tr>
    <td><img alt="English" src="mini_flag_en.gif"/></td><td>Fall</td><td>Morning</td><td>Undergraduate</td>
    <td>3-DCC</td><td>6</td><td>DTC-GITT-315</td>
    <td><strong>Software Engineering</strong><br/>Ingeniería del Software</td>
    <td><a href="https://example.test/repo-2024">Repo 2024-25</a></td>
  </tr>
</table>
<p><strong>POSTGRADUATE courses. Permission required for undergraduate exchange students (2025-26)</strong></p>
<table>
  <tr>
    <td>Language</td><td>Term</td><td>Schedule</td><td>Studies</td>
    <td>Degree</td><td>ECTS*</td><td>Code</td><td>Subject</td><td>Syllabus</td>
  </tr>
  <tr>
    <td></td><td>Spring</td><td>Afternoon</td><td>Master</td>
    <td>2-MIC</td><td>3</td><td>DTC-MIC-523</td>
    <td>Cybersecurity</td>
    <td><a href="https://example.test/repo-2024-cyber">Repo 2024-25</a></td>
  </tr>
</table>
</body></html>
"""


SAPIENS_FIXTURE = """
<html><body>
<table>
  <tr><td><center><h2>Fall/Spring SAPIENS</h2></center></td></tr>
  <tr><td>
    <table>
      <tr><td colspan="2"><span>Fundamental Engineering Courses</span></td></tr>
      <tr>
        <td>
          <b>DTC-SAP-374 Introduction to Algorithms and Models of Computation</b><br>
          <span style="display:none;">
            <a href="download/DTC-SAP-374.pdf">PDF</a>
            Covers algorithm design, formal languages and computational complexity.
          </span>
        </td>
        <td>4 h/week <span>(6 ECTS)</span></td>
      </tr>
      <tr>
        <td>
          <b>DTC-SAP-333 Machine Learning and Artificial Intelligence with Python</b><br>
          <span style="display:none;">Practical machine learning and AI with Python.</span>
        </td>
        <td>4 h/week <span>(6 ECTS)</span></td>
      </tr>
      <tr>
        <td>
          <b>DIM-SAP-336 Engineering Economy</b><br>
          <span style="display:none;">
            <a href="download/DOI-SAP-354.pdf">PDF</a>
            Engineering economy and capital budgeting.
          </span>
        </td>
        <td>4 h/week <span>(6 ECTS)</span></td>
      </tr>
    </table>
  </td></tr>
</table>
<h2>Courses planned to be offered in Summer SAPIENS 2026</h2>
<table>
  <tr><td>Summer SAPIENS</td></tr>
  <tr>
    <td><b>DTC-SAP-247 Internet of Things (IoT): Basics and Practical Approach</b></td>
    <td>30 h course. 8 weeks (3 ECTS)</td>
  </tr>
</table>
</body></html>
"""


class IcaiExtractionTests(unittest.TestCase):
    def test_parse_exchange_html_preserves_rows_and_links(self):
        rows = parse_exchange_html(HTML_FIXTURE)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["codigo"], "DTC-GITT-315")
        self.assertEqual(rows[0]["nombre"], "Software Engineering Ingeniería del Software")
        self.assertEqual(rows[0]["term"], "Fall")
        self.assertEqual(rows[0]["language"], "English")
        self.assertEqual(rows[0]["studies"], "Undergraduate")
        self.assertEqual(rows[0]["ects"], 6.0)
        self.assertEqual(rows[0]["url_guia"], "https://example.test/repo-2024")
        self.assertEqual(rows[0]["syllabus_links"][0]["label"], "Repo 2024-25")

    def test_parse_sapiens_html_preserves_fall_spring_courses(self):
        rows = parse_sapiens_html(SAPIENS_FIXTURE)

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["codigo"], "DTC-SAP-374")
        self.assertEqual(rows[0]["nombre"], "Introduction to Algorithms and Models of Computation")
        self.assertEqual(rows[0]["term"], "Fall/Spring")
        self.assertEqual(rows[0]["studies"], "Undergraduate")
        self.assertEqual(rows[0]["degree"], "SAPIENS")
        self.assertEqual(rows[0]["ects"], 6.0)
        self.assertEqual(rows[0]["source_label"], "sapiens")
        self.assertEqual(rows[0]["program_label"], "fall_spring_sapiens")
        self.assertEqual(
            rows[0]["url_guia"],
            "https://apps.icai.comillas.edu/sapiens/download/DTC-SAP-374.pdf",
        )
        self.assertIn("computational complexity", rows[0]["guia"]["descripcion"])

    def test_parse_sapiens_html_prefers_pdf_code_when_visible_code_is_inconsistent(self):
        rows = parse_sapiens_html(SAPIENS_FIXTURE)

        economy = next(row for row in rows if row["nombre"] == "Engineering Economy")
        self.assertEqual(economy["codigo"], "DOI-SAP-354")
        self.assertEqual(
            economy["url_guia"],
            "https://apps.icai.comillas.edu/sapiens/download/DOI-SAP-354.pdf",
        )

    def test_parse_sapiens_html_excludes_summer_courses(self):
        rows = parse_sapiens_html(SAPIENS_FIXTURE)

        self.assertNotIn("DTC-SAP-247", {row["codigo"] for row in rows})

    def test_compute_labels_for_fall_undergraduate(self):
        labels = compute_labels({
            "term": "Fall",
            "studies": "Undergraduate",
            "schedule": "Morning",
            "language": "English",
            "nombre": "Software Engineering",
        })

        self.assertEqual(labels["availability"], "exchange_term")
        self.assertEqual(labels["timing_risk"], "low")
        self.assertEqual(labels["level"], "undergraduate")
        self.assertEqual(labels["permission"], "standard")
        self.assertEqual(labels["language"], "english")
        self.assertEqual(labels["schedule"], "morning")

    def test_language_column_takes_precedence_over_bilingual_subject_title(self):
        labels = compute_labels({
            "term": "Fall",
            "studies": "Undergraduate",
            "schedule": "Morning",
            "language": "English",
            "nombre": "Economic Analysis for Business Decisions Análisis económico / Economic Analysis",
        })

        self.assertEqual(labels["language"], "english")

    def test_compute_labels_for_spring_master(self):
        labels = compute_labels({
            "term": "Spring",
            "studies": "Master",
            "schedule": "Afternoon",
            "language": "",
            "nombre": "Cybersecurity",
        })

        self.assertEqual(labels["availability"], "not_in_exchange_term")
        self.assertEqual(labels["timing_risk"], "high")
        self.assertEqual(labels["level"], "postgraduate")
        self.assertEqual(labels["permission"], "permission_required")
        self.assertEqual(labels["language"], "unknown")
        self.assertEqual(labels["schedule"], "afternoon")

    def test_compute_labels_for_fall_spring_sapiens(self):
        labels = compute_labels({
            "term": "Fall/Spring",
            "studies": "Undergraduate",
            "schedule": "Fall/Spring SAPIENS",
            "language": "English",
            "nombre": "Machine Learning and Artificial Intelligence with Python",
        })

        self.assertEqual(labels["availability"], "exchange_term")
        self.assertEqual(labels["timing_risk"], "low")
        self.assertEqual(labels["level"], "undergraduate")
        self.assertEqual(labels["permission"], "standard")
        self.assertEqual(labels["language"], "english")
        self.assertEqual(labels["schedule"], "fall/spring sapiens")


if __name__ == "__main__":
    unittest.main()
