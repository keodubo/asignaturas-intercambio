#!/usr/bin/env python3
"""Extrae horarios ICAI de los dos portales oficiales del primer semestre."""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = PROJECT_ROOT / "analisis" / "inputs" / "icai_catalogo.json"
OUTPUT_PATH = PROJECT_ROOT / "icai" / "horarios" / "horarios_icai.json"
OFFICIAL_SOURCES = {
    "grado": "https://horarios.comillas.edu/ICAIgrado1Sem/Horarios/",
    "master": "https://horarios.comillas.edu/ICAIMaster1Sem/Horarios/",
}
WEEKDAYS = {
    "lunes": "monday",
    "martes": "tuesday",
    "miercoles": "wednesday",
    "jueves": "thursday",
    "viernes": "friday",
}
TIME_RANGE = re.compile(r"(\d{1,2})\s*[:.]\s*(\d{2})\s*-\s*(\d{1,2})\s*[:.]\s*(\d{2})")
DATE_RANGE = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{4})(?:\s*-\s*(\d{1,2}/\d{1,2}/\d{4}))?"
)
TRAILING_OC_SUFFIX = re.compile(r"\s*\+\s*oc\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class TableCell:
    text: str
    row_start: int
    column_start: int
    rowspan: int
    colspan: int


def normalize_name(value: str) -> str:
    """Normalize Unicode, spacing, case and diacritics for exact-name comparison."""
    compatible = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(char for char in compatible if not unicodedata.combining(char))
    return " ".join(without_marks.casefold().split())


def _normalize_schedule_name(value: str) -> str:
    """Normalize names while removing only the published trailing +OC label."""
    return normalize_name(TRAILING_OC_SUFFIX.sub("", value or ""))


def _cell_text(cell: Tag) -> str:
    return "\n".join(part.strip() for part in cell.stripped_strings if part.strip())


def _direct_rows(table: Tag) -> list[Tag]:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _expand_table(table: Tag) -> list[list[TableCell | None]]:
    rows = _direct_rows(table)
    occupied: dict[tuple[int, int], TableCell] = {}
    max_column = 0
    for row_index, row in enumerate(rows):
        column_index = 0
        for element in row.find_all(["td", "th"], recursive=False):
            while (row_index, column_index) in occupied:
                column_index += 1
            rowspan = int(element.get("rowspan", 1))
            colspan = int(element.get("colspan", 1))
            cell = TableCell(
                text=_cell_text(element),
                row_start=row_index,
                column_start=column_index,
                rowspan=max(rowspan, 1),
                colspan=max(colspan, 1),
            )
            for expanded_row in range(row_index, row_index + cell.rowspan):
                for expanded_column in range(column_index, column_index + cell.colspan):
                    occupied[(expanded_row, expanded_column)] = cell
            column_index += cell.colspan
            max_column = max(max_column, column_index)
    return [
        [occupied.get((row_index, column_index)) for column_index in range(max_column)]
        for row_index in range(len(rows))
    ]


def _weekday_columns(matrix: list[list[TableCell | None]]) -> tuple[int, dict[int, str]] | None:
    for row_index, row in enumerate(matrix):
        columns: dict[int, str] = {}
        for column_index, cell in enumerate(row):
            if cell is None or cell.column_start != column_index:
                continue
            weekday = WEEKDAYS.get(normalize_name(cell.text))
            if weekday:
                for expanded_column in range(cell.column_start, cell.column_start + cell.colspan):
                    columns[expanded_column] = weekday
        if len(columns) >= 5:
            return row_index, columns
    return None


def _time_range(value: str) -> tuple[str, str] | None:
    match = TIME_RANGE.search(value)
    if match is None:
        return None
    return (
        f"{int(match.group(1)):02d}:{match.group(2)}",
        f"{int(match.group(3)):02d}:{match.group(4)}",
    )


def _session_details(value: str) -> tuple[str, str | None] | None:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return None
    course_name = lines[0]
    normalized = normalize_name(course_name)
    if course_name.startswith("[") or normalized.startswith(("tutoria", "descanso", "recreo")):
        return None
    room = None
    for line in lines[1:]:
        if line.startswith("[") and line.endswith("]") and not line.startswith("[("):
            room = line[1:-1].strip() or None
            break
    return course_name, room


def parse_schedule_page(
    html: str,
    source_url: str,
    group: str,
    date_start: str,
    date_end: str,
) -> list[dict]:
    """Return normalized sessions reconstructed from one official group timetable."""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        matrix = _expand_table(table)
        header = _weekday_columns(matrix)
        if header is None:
            continue
        header_row, weekday_by_column = header
        sessions: list[dict] = []
        for row_index in range(header_row + 1, len(matrix)):
            row = matrix[row_index]
            time_cell = next((cell for cell in row if cell and cell.column_start == 0), None)
            time_range = _time_range(time_cell.text) if time_cell else None
            if time_range is None:
                continue
            start, _ = time_range
            for column_index, cell in enumerate(row):
                if (
                    cell is None
                    or cell.row_start != row_index
                    or cell.column_start != column_index
                    or column_index not in weekday_by_column
                ):
                    continue
                details = _session_details(cell.text)
                if details is None:
                    continue
                raw_name, room = details
                last_row = min(row_index + cell.rowspan - 1, len(matrix) - 1)
                last_time_cell = next(
                    (candidate for candidate in matrix[last_row] if candidate and candidate.column_start == 0),
                    None,
                )
                last_time_range = _time_range(last_time_cell.text) if last_time_cell else None
                if last_time_range is None:
                    continue
                _, end = last_time_range
                for day_column in range(column_index, column_index + cell.colspan):
                    day = weekday_by_column.get(day_column)
                    if day is None:
                        continue
                    sessions.append({
                        "raw_name": raw_name,
                        "group": group,
                        "day": day,
                        "start": start,
                        "end": end,
                        "room": room,
                        "date_start": date_start,
                        "date_end": date_end,
                        "source_url": source_url,
                    })
        return sessions
    raise ValueError("No se encontró una tabla de horario con lunes a viernes")


def _group_programs(group: str | None) -> set[str]:
    """Return program tokens explicitly encoded by an official timetable group name."""
    normalized = normalize_name(group or "")
    return {
        program.upper()
        for program in re.findall(r"\b[a-z][a-z0-9]+\b", normalized)
        if program not in {"a", "b", "c", "grupo"}
    }


def _group_degrees(group: str | None) -> set[str]:
    """Return year-program degree labels explicitly encoded by a group name."""
    year_match = re.search(r"\b([1-9])o?\b", normalize_name(group or ""))
    if year_match is None:
        return set()
    return {f"{year_match.group(1)}-{program}" for program in _group_programs(group)}


def _degree_program(course: dict) -> str:
    """Return the program portion of a catalog degree label without inferring one."""
    return str(course.get("degree", "")).upper().partition("-")[2]


def matching_catalog_courses(raw_name: str, catalog: list[dict], group: str | None = None) -> list[dict]:
    """Return exact-name candidates, narrowed only by degree tokens stated in the group."""
    wanted = _normalize_schedule_name(raw_name)
    candidates: dict[str, dict] = {}
    for course in catalog:
        names = [
            course.get("official_name", ""),
            course.get("english_name", ""),
            course.get("nombre", ""),
        ]
        names.extend(str(course.get("nombre", "")).split(" / "))
        if any(wanted == _normalize_schedule_name(name) for name in names if name):
            code = str(course.get("codigo", ""))
            if code:
                candidates[code] = course
    matches = [candidates[code] for code in sorted(candidates)]
    group_degrees = _group_degrees(group)
    degree_matches = [
        course for course in matches
        if str(course.get("degree", "")).upper() in group_degrees
    ]
    if degree_matches:
        return degree_matches
    program_matches = [
        course for course in matches
        if _degree_program(course) in _group_programs(group)
    ]
    return program_matches if len(program_matches) == 1 else matches


def match_catalog_course(raw_name: str, catalog: list[dict], group: str | None = None) -> dict | None:
    """Link an official timetable name only when one exact candidate remains."""
    candidates = matching_catalog_courses(raw_name, catalog, group)
    return candidates[0] if len(candidates) == 1 else None


def write_json_atomically(output_path: Path, payload: dict[str, Any]) -> None:
    """Replace the target only after a complete JSON document is safely written."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output_path.parent, suffix=".tmp", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, output_path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def _parse_date(value: str) -> str:
    return datetime.strptime(value, "%d/%m/%Y").date().isoformat()


def _is_official_portal_url(url: str) -> bool:
    candidate = urlparse(url)
    return (
        candidate.scheme == "https"
        and candidate.netloc == "horarios.comillas.edu"
        and any(candidate.path.startswith(urlparse(source_url).path) for source_url in OFFICIAL_SOURCES.values())
    )


def _is_official_schedule_url(url: str, index_url: str) -> bool:
    candidate = urlparse(url)
    index = urlparse(index_url)
    return (
        _is_official_portal_url(url)
        and candidate.netloc == index.netloc
        and candidate.path.startswith(index.path)
        and Path(candidate.path).name.startswith("grupo_")
        and candidate.path.endswith(".html")
    )


def discover_group_pages(index_html: str, index_url: str) -> list[dict]:
    soup = BeautifulSoup(index_html, "html.parser")
    pages = []
    for link in soup.find_all("a", href=True):
        full_url = urljoin(index_url, link["href"])
        if not _is_official_schedule_url(full_url, index_url):
            continue
        dates = DATE_RANGE.search(link.get_text(" ", strip=True))
        if dates is None:
            continue
        parent_list = link.find_parent("ul")
        group_item = parent_list.parent if parent_list is not None else None
        direct_text = " ".join(
            text.strip() for text in group_item.find_all(string=True, recursive=False) if text.strip()
        ) if group_item is not None else ""
        group = direct_text or Path(urlparse(full_url).path).stem
        start = _parse_date(dates.group(1))
        end_week_start = datetime.strptime(dates.group(2) or dates.group(1), "%d/%m/%Y").date()
        end = (end_week_start + timedelta(days=6)).isoformat()
        pages.append({"url": full_url, "group": group, "date_start": start, "date_end": end})
    if not pages:
        raise ValueError(f"El índice oficial no contiene páginas de grupo: {index_url}")
    return pages


def _certificate_verification_failed(error: Exception) -> bool:
    if isinstance(error, ssl.SSLCertVerificationError):
        return True
    return isinstance(error, URLError) and isinstance(error.reason, ssl.SSLCertVerificationError)


def _decode_secure_curl_output(output: bytes) -> str:
    marker = b"\n__ICAI_EFFECTIVE_URL__:"
    try:
        body, effective_url = output.rsplit(marker, 1)
    except ValueError as exc:
        raise ValueError("curl no informó la URL efectiva del portal oficial") from exc
    if not _is_official_portal_url(effective_url.decode("utf-8", errors="strict")):
        raise ValueError("curl redirigió fuera de los portales oficiales ICAI")
    return body.decode("utf-8", errors="replace")


def fetch_official_page(url: str) -> str:
    """Fetch an allowed portal page, preserving TLS verification in both transports."""
    if not _is_official_portal_url(url):
        raise ValueError(f"URL fuera de los portales oficiales ICAI: {url}")
    request = Request(url, headers={"User-Agent": "ICAI-schedule-extractor/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            if not _is_official_portal_url(response.geturl()):
                raise ValueError("urllib redirigió fuera de los portales oficiales ICAI")
            return response.read().decode("utf-8", errors="replace")
    except Exception as error:
        if not _certificate_verification_failed(error):
            raise
    result = subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--max-time",
            "30",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--write-out",
            "\n__ICAI_EFFECTIVE_URL__:%{url_effective}",
            url,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return _decode_secure_curl_output(result.stdout)


def _weeks_for_ranges(ranges: set[tuple[str, str]]) -> list[str]:
    weeks: set[str] = set()
    for start_value, end_value in ranges:
        current = date.fromisoformat(start_value)
        end = date.fromisoformat(end_value)
        current -= timedelta(days=current.weekday())
        while current <= end:
            weeks.add(current.isoformat())
            current += timedelta(days=7)
    return sorted(weeks)


def build_schedule_payload(catalog: list[dict], pages: list[dict]) -> dict[str, Any]:
    courses: dict[str, dict] = {}
    alternatives: dict[tuple[str, str, str], dict] = {}
    unmatched: list[dict] = []
    alternative_sessions: dict[tuple[str, str, str], set[tuple[Any, ...]]] = {}
    ambiguous_catalog_sessions: dict[str, dict[str, Any]] = {}
    ranges: set[tuple[str, str]] = set()
    for page in pages:
        ranges.add((page["date_start"], page["date_end"]))
        for session in parse_schedule_page(
            page["html"], page["url"], page["group"], page["date_start"], page["date_end"]
        ):
            candidates = matching_catalog_courses(session["raw_name"], catalog, session["group"])
            if not candidates:
                unmatched.append({**session, "reason": "no_exact_catalog_name_match"})
                continue
            if len(candidates) != 1:
                candidate_codes = [str(course["codigo"]) for course in candidates]
                unmatched.append({
                    **session,
                    "reason": "ambiguous_exact_catalog_match",
                    "candidate_codes": candidate_codes,
                })
                session_key = tuple(session[field] for field in (
                    "raw_name", "group", "day", "start", "end", "room", "date_start", "date_end", "source_url"
                ))
                for candidate in candidates:
                    state = ambiguous_catalog_sessions.setdefault(str(candidate["codigo"]), {
                        "candidate_codes": set(),
                        "sessions": set(),
                    })
                    state["candidate_codes"].update(candidate_codes)
                    state["sessions"].add(session_key)
                continue
            course = candidates[0]
            code = course["codigo"]
            course_entry = courses.setdefault(code, {
                "codigo": code,
                "nombre": course["nombre"],
                "alternatives": [],
            })
            key = (code, page["source"], session["group"])
            alternative = alternatives.get(key)
            if alternative is None:
                alternative = {
                    "source": page["source"],
                    "group": session["group"],
                    "sessions": [],
                }
                alternatives[key] = alternative
                course_entry["alternatives"].append(alternative)
            normalized_session = {
                field: session[field]
                for field in ("day", "start", "end", "room", "date_start", "date_end", "source_url")
            }
            session_key = tuple(normalized_session[field] for field in (
                "day", "start", "end", "room", "date_start", "date_end", "source_url"
            ))
            seen_sessions = alternative_sessions.setdefault(key, set())
            if session_key not in seen_sessions:
                alternative["sessions"].append(normalized_session)
                seen_sessions.add(session_key)
    for course in sorted(catalog, key=lambda item: str(item.get("codigo", ""))):
        code = str(course.get("codigo", ""))
        if code and code not in courses:
            ambiguity = ambiguous_catalog_sessions.get(code)
            if ambiguity is None:
                unmatched.append({
                    "codigo": code,
                    "nombre": course.get("nombre", ""),
                    "reason": "no_published_schedule",
                })
            else:
                unmatched.append({
                    "codigo": code,
                    "nombre": course.get("nombre", ""),
                    "reason": "schedule_present_but_not_uniquely_linked",
                    "candidate_codes": sorted(ambiguity["candidate_codes"]),
                    "session_count": len(ambiguity["sessions"]),
                })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {"source": source, "index_url": url}
            for source, url in OFFICIAL_SOURCES.items()
        ],
        "weeks": _weeks_for_ranges(ranges),
        "courses": [courses[code] for code in sorted(courses)],
        "unmatched": unmatched,
    }


def extract_official_schedules(catalog: list[dict]) -> dict[str, Any]:
    """Download only the official indexes and group pages, then build the local payload."""
    pages: list[dict] = []
    for source, index_url in OFFICIAL_SOURCES.items():
        for page in discover_group_pages(fetch_official_page(index_url), index_url):
            page["source"] = source
            page["html"] = fetch_official_page(page["url"])
            pages.append(page)
    return build_schedule_payload(catalog, pages)


def _load_catalog(path: Path) -> list[dict]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, list):
        raise ValueError(f"El catálogo debe ser una lista JSON: {path}")
    return catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)
    payload = extract_official_schedules(_load_catalog(args.catalog))
    write_json_atomically(args.output, payload)
    print(f"OK {args.output}: {len(payload['courses'])} materias vinculadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
