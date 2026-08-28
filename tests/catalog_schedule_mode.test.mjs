import test from "node:test";
import assert from "node:assert/strict";

import {
  buildScheduleCatalogRows,
  courseViews,
  equivalencyDatasetIds,
} from "../webui/catalog-schedule-mode.mjs";

test("builds one schedule-selectable row per ICAI course without an ITBA equivalency", () => {
  const catalog = [
    {
      codigo: "ICAI-101",
      nombre: "Course One",
      term: "Fall",
      studies: "Undergraduate",
      degree: "2-GITI",
      language: "English",
      schedule: "Published",
      ects: 6,
      ects_semester: 6,
      url_guia: "https://example.test/one",
      labels: {
        availability: "exchange_term",
        timing_risk: "low",
        level: "undergraduate",
        permission: "standard",
        language: "english",
        schedule: "published",
      },
    },
    {
      codigo: "ICAI-202",
      nombre: "Course Two",
      term: "All-year",
      studies: "Master",
      degree: "1-MIA",
      language: "Spanish",
      schedule: "Unknown",
      ects: 9,
      ects_semester: 4.5,
      labels: {
        availability: "exchange_term_all_year",
        timing_risk: "medium",
        level: "postgraduate",
        permission: "permission_required",
        language: "spanish",
        schedule: "unknown",
      },
    },
  ];

  assert.deepEqual(buildScheduleCatalogRows(catalog), [
    {
      codigo_externo: "ICAI-101",
      nombre_externo: "Course One",
      tipo_externo: "Fall",
      curso_externo: "2-GITI",
      ects_externo: 6,
      codigo_itba: "",
      nombre_itba: "",
      confianza: "",
      comentario: "",
      studies: "Undergraduate",
      availability_label: "exchange_term",
      timing_risk_label: "low",
      level_label: "undergraduate",
      permission_label: "standard",
      language_label: "english",
      schedule_label: "published",
      language: "English",
      schedule: "Published",
      recommendation_bucket: "",
      source_label: "",
      program_label: "",
      source_url: "",
      url_guia_externo: "https://example.test/one",
      carrera: "icai_horarios",
      _matched: false,
      _scheduleOnly: true,
    },
    {
      codigo_externo: "ICAI-202",
      nombre_externo: "Course Two",
      tipo_externo: "All-year",
      curso_externo: "1-MIA",
      ects_externo: 4.5,
      codigo_itba: "",
      nombre_itba: "",
      confianza: "",
      comentario: "",
      studies: "Master",
      availability_label: "exchange_term_all_year",
      timing_risk_label: "medium",
      level_label: "postgraduate",
      permission_label: "permission_required",
      language_label: "spanish",
      schedule_label: "unknown",
      language: "Spanish",
      schedule: "Unknown",
      recommendation_bucket: "",
      source_label: "",
      program_label: "",
      source_url: "",
      url_guia_externo: "",
      carrera: "icai_horarios",
      _matched: false,
      _scheduleOnly: true,
    },
  ]);
});

test("loads equivalency CSVs only for tabs backed by equivalency datasets", () => {
  const tabs = [
    { id: "icai" },
    { id: "icai_combinaciones", combinations: true },
    { id: "icai_horarios", scheduleOnly: true },
  ];

  assert.deepEqual(equivalencyDatasetIds(tabs), ["icai"]);
});

test("presents the schedule combiner first with ITBA-specific equivalency labels", () => {
  assert.deepEqual(courseViews.map(({ id, label }) => ({ id, label })), [
    { id: "icai_horarios", label: "Combinador de horarios" },
    { id: "icai", label: "Equivalencias ITBA" },
    { id: "icai_combinaciones", label: "ITBA combinaciones" },
  ]);
});
