export function equivalencyDatasetIds(tabs) {
  return tabs.filter(tab => !tab.combinations && !tab.scheduleOnly).map(tab => tab.id);
}

export function buildScheduleCatalogRows(catalog) {
  return catalog.map(course => ({
    codigo_externo: String(course.codigo ?? ""),
    nombre_externo: String(course.nombre ?? ""),
    tipo_externo: String(course.term ?? ""),
    curso_externo: String(course.degree ?? ""),
    ects_externo: course.ects_semester ?? course.ects ?? "",
    codigo_itba: "",
    nombre_itba: "",
    confianza: "",
    comentario: "",
    studies: String(course.studies ?? ""),
    availability_label: String(course.labels?.availability ?? ""),
    timing_risk_label: String(course.labels?.timing_risk ?? ""),
    level_label: String(course.labels?.level ?? ""),
    permission_label: String(course.labels?.permission ?? ""),
    language_label: String(course.labels?.language ?? ""),
    schedule_label: String(course.labels?.schedule ?? ""),
    language: String(course.language ?? ""),
    schedule: String(course.schedule ?? ""),
    recommendation_bucket: "",
    source_label: String(course.source_label ?? ""),
    program_label: String(course.program_label ?? ""),
    source_url: String(course.source_url ?? ""),
    url_guia_externo: String(course.url_guia ?? ""),
    carrera: "icai_horarios",
    _matched: false,
    _scheduleOnly: true,
  }));
}
