#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


BASE = Path(__file__).parent
SOURCE_URL = "https://apps.icai.comillas.edu/exchange/"
SAPIENS_URL = "https://apps.icai.comillas.edu/sapiens/"
EXCHANGE_HTML = BASE / "exchange.html"
SAPIENS_HTML = BASE / "sapiens.html"
OUT_DIR = BASE / "extraccion_materias"
GUIAS_DIR = BASE / "guias_docentes"
CONTENIDOS_JSON = GUIAS_DIR / "contenidos.json"
OUT_CSV = OUT_DIR / "icai_catalogo.csv"
SAPIENS_CODE_RE = re.compile(r"\b(?:[A-Z]{3}|XXX)-(?:SAP|OPT)-\d{3}\b")

CSV_FIELDS = [
    "language", "term", "schedule", "studies", "degree", "ects", "codigo",
    "nombre", "url_guia", "source_label", "program_label", "source_url",
    "syllabus_links_json", "availability_label", "timing_risk_label",
    "level_label", "permission_label", "language_label", "schedule_label",
]


def clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u2011", "-").split())


def clean_cell_text(cell) -> str:
    text = clean_text(cell.get_text(" ", strip=True))
    if text:
        return text
    image_labels = []
    for img in cell.find_all("img"):
        label = clean_text(img.get("alt") or img.get("title") or img.get("src") or "")
        if label:
            image_labels.append(label)
    return clean_text(" ".join(image_labels))


def parse_float(value: str):
    text = clean_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_schedule(value: str) -> str:
    text = clean_text(value).lower()
    if text == "afternooon":
        text = "afternoon"
    return text or "unknown"


def infer_language(language: str, subject: str) -> str:
    def has_english_marker(text: str) -> bool:
        return (
        "english" in text
        or "inglés" in text
        or "ingles" in text
        or "mini_flag_en" in text
        or "flag_en" in text
    )

    def has_spanish_marker(text: str) -> bool:
        return (
        "spanish" in text
        or "español" in text
        or "espanol" in text
        or "castellano" in text
        or "mini_flag_es" in text
        or "flag_es" in text
    )

    language_text = (language or "").lower()
    subject_text = (subject or "").lower()
    language_has_english = has_english_marker(language_text)
    language_has_spanish = has_spanish_marker(language_text)
    if language_has_english and language_has_spanish:
        return "mixed"
    if language_has_english:
        return "english"
    if language_has_spanish:
        return "spanish"

    has_english = has_english_marker(subject_text)
    has_spanish = has_spanish_marker(subject_text)
    has_slash = "/" in subject
    if has_english and (has_spanish or has_slash):
        return "mixed"
    if has_english:
        return "english"
    if has_spanish:
        return "spanish"
    return "unknown"


def compute_labels(course: dict) -> dict:
    term = clean_text(course.get("term", ""))
    studies = clean_text(course.get("studies", ""))
    schedule = normalize_schedule(course.get("schedule", ""))
    language_label = infer_language(course.get("language", ""), course.get("nombre", ""))

    if term in {"Fall", "Fall/Spring"}:
        availability = "exchange_term"
        timing_risk = "low"
    elif term == "Full-year":
        availability = "full_year"
        timing_risk = "medium"
    elif term == "Spring":
        availability = "not_in_exchange_term"
        timing_risk = "high"
    else:
        availability = "unknown"
        timing_risk = "medium"

    if studies == "Master":
        level = "postgraduate"
        permission = "permission_required"
    else:
        level = "undergraduate"
        permission = "standard"

    return {
        "availability": availability,
        "timing_risk": timing_risk,
        "level": level,
        "permission": permission,
        "language": language_label,
        "schedule": schedule,
    }


def is_course_table(table) -> bool:
    first = table.find("tr")
    if not first:
        return False
    headers = [clean_text(c.get_text(" ", strip=True)) for c in first.find_all(["td", "th"])]
    return headers[:4] == ["Language", "Term", "Schedule", "Studies"]


def parse_exchange_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for table in soup.find_all("table"):
        if not is_course_table(table):
            continue
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if len(cells) < 9:
                continue
            language, term, schedule, studies, degree, ects, code, subject = cells[:8]
            codigo = clean_cell_text(code)
            if not codigo or codigo.lower() == "code":
                continue
            links = []
            seen_urls = set()
            for cell in cells[8:]:
                for a in cell.find_all("a", href=True):
                    url = urljoin(SOURCE_URL, a["href"])
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    links.append({
                        "label": clean_text(a.get_text(" ", strip=True)),
                        "url": url,
                    })
            labeled_links = [link for link in links if link["label"]]
            ordered_links = labeled_links + [link for link in links if not link["label"]]
            row = {
                "language": clean_cell_text(language),
                "term": clean_cell_text(term),
                "schedule": clean_cell_text(schedule),
                "studies": clean_cell_text(studies),
                "degree": clean_cell_text(degree),
                "ects": parse_float(clean_cell_text(ects)),
                "codigo": codigo,
                "nombre": clean_cell_text(subject),
                "url_guia": ordered_links[0]["url"] if ordered_links else "",
                "syllabus_links": ordered_links,
                "source_label": "exchange_catalog",
                "program_label": "regular_icai",
                "source_url": SOURCE_URL,
            }
            row["labels"] = compute_labels(row)
            rows.append(row)
    return rows


def parse_ects_from_text(value: str):
    match = re.search(r"\((\d+(?:[.,]\d+)?)\s*ECTS\)", value, re.IGNORECASE)
    return parse_float(match.group(1)) if match else None


def sapiens_section_slug(value: str) -> str:
    text = clean_text(value).lower()
    if "fundamental engineering courses" in text:
        return "fundamental_engineering"
    if "spanish culture and language courses" in text:
        return "spanish_culture_language"
    if "elective courses on engineering technologies" in text:
        return "engineering_technologies_electives"
    return ""


def sapiens_language_for_section(section: str, name: str) -> str:
    if section == "spanish_culture_language" or "español" in name.lower():
        return "Spanish"
    return "English"


def extract_sapiens_description(cell) -> str:
    parts = []
    for span in cell.find_all("span"):
        text = clean_text(span.get_text(" ", strip=True))
        if text:
            parts.append(text)
    return clean_text(" ".join(parts))


def sapiens_pdf_code(links: list[dict]) -> str:
    for link in links:
        match = SAPIENS_CODE_RE.search(link.get("url", ""))
        if match:
            return match.group(0)
    return ""


def parse_sapiens_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen = set()
    active_fall_spring = False
    section = ""

    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        direct_text = clean_text(" ".join(cell.get_text(" ", strip=True) for cell in cells))

        if "Courses planned to be offered in Summer" in direct_text or direct_text == "Summer SAPIENS":
            active_fall_spring = False
            continue
        if "Fall/Spring SAPIENS" in direct_text:
            active_fall_spring = True
            continue
        if not active_fall_spring:
            continue

        if any(cell.find("table") for cell in cells):
            continue

        new_section = sapiens_section_slug(direct_text)
        if new_section:
            section = new_section
            continue

        title_node = next((cell.find("b") for cell in cells if cell.find("b")), None)
        if title_node is None:
            continue
        title = clean_text(title_node.get_text(" ", strip=True))
        match = SAPIENS_CODE_RE.search(title)
        if not match:
            continue

        visible_codigo = match.group(0)
        nombre = clean_text(title[match.end():].strip(" -:"))

        links = []
        seen_urls = set()
        for cell in cells:
            for a in cell.find_all("a", href=True):
                url = urljoin(SAPIENS_URL, a["href"])
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                links.append({
                    "label": clean_text(a.get_text(" ", strip=True)) or "SAPIENS PDF",
                    "url": url,
                })

        codigo = sapiens_pdf_code(links) or visible_codigo
        key = (codigo, nombre, "fall_spring_sapiens")
        if key in seen:
            continue
        seen.add(key)

        descripcion = extract_sapiens_description(cells[0])
        row = {
            "language": sapiens_language_for_section(section, nombre),
            "term": "Fall/Spring",
            "schedule": "Fall/Spring SAPIENS",
            "studies": "Undergraduate",
            "degree": "SAPIENS",
            "ects": parse_ects_from_text(direct_text),
            "codigo": codigo,
            "nombre": nombre,
            "url_guia": links[0]["url"] if links else "",
            "syllabus_links": links,
            "source_label": "sapiens",
            "program_label": "fall_spring_sapiens",
            "source_url": SAPIENS_URL,
            "guia": {
                "descripcion": descripcion,
                "competencias": "",
                "contenidos": descripcion,
                "metodologia": "",
                "evaluacion": "",
                "bibliografia": "",
            },
        }
        row["labels"] = compute_labels(row)
        rows.append(row)

    return rows


def fetch_html(url: str) -> str:
    result = subprocess.run(
        ["curl", "-fsSL", url],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def read_or_fetch_html(refresh: bool, url: str, path: Path) -> str:
    if refresh or not path.exists():
        html = fetch_html(url)
        BASE.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return html
    return path.read_text(encoding="utf-8", errors="replace")


def write_catalog_csv(rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            labels = row["labels"]
            writer.writerow({
                "language": row["language"],
                "term": row["term"],
                "schedule": row["schedule"],
                "studies": row["studies"],
                "degree": row["degree"],
                "ects": row["ects"] if row["ects"] is not None else "",
                "codigo": row["codigo"],
                "nombre": row["nombre"],
                "url_guia": row["url_guia"],
                "source_label": row.get("source_label", ""),
                "program_label": row.get("program_label", ""),
                "source_url": row.get("source_url", ""),
                "syllabus_links_json": json.dumps(row["syllabus_links"], ensure_ascii=False),
                "availability_label": labels["availability"],
                "timing_risk_label": labels["timing_risk"],
                "level_label": labels["level"],
                "permission_label": labels["permission"],
                "language_label": labels["language"],
                "schedule_label": labels["schedule"],
            })


def empty_guia() -> dict:
    return {
        "descripcion": "",
        "competencias": "",
        "contenidos": "",
        "metodologia": "",
        "evaluacion": "",
        "bibliografia": "",
    }


def write_contenidos(rows: list[dict]) -> None:
    GUIAS_DIR.mkdir(parents=True, exist_ok=True)
    if CONTENIDOS_JSON.exists():
        payload = json.loads(CONTENIDOS_JSON.read_text(encoding="utf-8"))
    else:
        payload = {}
    for row in rows:
        current = payload.get(row["codigo"]) or empty_guia()
        incoming = row.get("guia") or empty_guia()
        for key, value in empty_guia().items():
            current.setdefault(key, value)
            if not clean_text(str(current.get(key, ""))) and clean_text(str(incoming.get(key, ""))):
                current[key] = incoming[key]
        payload[row["codigo"]] = current
    CONTENIDOS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Download the live exchange page before parsing.")
    args = parser.parse_args()

    exchange_html = read_or_fetch_html(args.refresh, SOURCE_URL, EXCHANGE_HTML)
    sapiens_html = read_or_fetch_html(args.refresh, SAPIENS_URL, SAPIENS_HTML)
    rows = parse_exchange_html(exchange_html) + parse_sapiens_html(sapiens_html)
    write_catalog_csv(rows)
    write_contenidos(rows)
    print(f"OK icai_catalogo.csv - {len(rows)} cursos")


if __name__ == "__main__":
    main()
