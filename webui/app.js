const CARRERAS = [
  { id: "icai",                    label: "ICAI Comillas", institution: "icai" },
  { id: "icai_combinaciones",      label: "ICAI combinaciones", institution: "icai", combinations: true },
];

const DATASET_VERSION = "icai-excel-2026-08-28-v2";
const assetUrl = url => WebuiAssets.versionedAssetUrl(url, DATASET_VERSION);

const CART_STORAGE_KEY = "equivalencias-carrito-v1";
const CART_CSV_FIELDS = [
  "codigo_externo", "nombre_externo", "carrera",
  "tipo_externo", "curso_externo", "ects_externo",
  "horas_clase", "creditos_itba",
  "codigo_itba", "nombre_itba",
  "confianza", "comentario",
  "pdf_path_externo", "url_guia_externo",
];

const ECTS_TO_CLASS_HOURS = 10;
const SEMANAS_SEMESTRE = 15;
const SCHEDULE_START_MINUTES = 8 * 60;
const SCHEDULE_END_MINUTES = 22 * 60;
const SCHEDULE_HOUR_HEIGHT = 58;
const SCHEDULE_DAYS = [
  ["monday", "Lun"],
  ["tuesday", "Mar"],
  ["wednesday", "Mié"],
  ["thursday", "Jue"],
  ["friday", "Vie"],
];
const SCHEDULE_COLORS = [
  { bg: "#c6dce8", border: "#36738e", text: "#173b4b" },
  { bg: "#d9c39f", border: "#866a3b", text: "#493719" },
  { bg: "#bcd4bd", border: "#4d7652", text: "#244329" },
  { bg: "#d6b8c8", border: "#8a526f", text: "#512d40" },
  { bg: "#c8bfdc", border: "#67588d", text: "#3b3158" },
  { bg: "#e0c2a9", border: "#946443", text: "#55351f" },
  { bg: "#b9d8d2", border: "#3d7970", text: "#1f4842" },
  { bg: "#d6d2a9", border: "#7c763d", text: "#49451f" },
];

const state = {
  carrera: CARRERAS[0].id,
  conf: 2,
  tipos: new Set(),
  cursos: new Set(),
  studies: new Set(),
  availability: new Set(),
  timingRisks: new Set(),
  permissions: new Set(),
  recommendationBuckets: new Set(),
  search: "",
  showUnmatched: false,
  onlyCart: false,
  sortKey: "codigo_externo",
  sortDir: "asc",
  data: {},
  icaiCatalogo: [],
  icaiByCode: {},
  itbaTargets: {},
  cart: [],
  cartIndex: new Set(),
  scheduleStatus: "loading",
  scheduleData: null,
  scheduleError: "",
  scheduleEngine: null,
  scheduleTab: "materials",
  cartOpen: false,
  scheduleOptionIndex: 0,
  scheduleWeek: "",
  scheduleSelectionKey: "",
};

function cartKey(codigoExterno, codigoItba) {
  return `${codigoExterno ?? ""}|${codigoItba ?? ""}`;
}

function rebuildCartIndex() {
  state.cartIndex = new Set(state.cart.map(c => cartKey(c.codigo_externo, c.codigo_itba)));
}

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_STORAGE_KEY);
    state.cart = raw ? JSON.parse(raw) : [];
  } catch {
    state.cart = [];
  }
  rebuildCartIndex();
}

function persistCart() {
  localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(state.cart));
}

function loadCsv(url) {
  return new Promise(resolve => {
    Papa.parse(assetUrl(url), {
      download: true,
      header: true,
      skipEmptyLines: true,
      complete: r => resolve(r.data),
      error: () => resolve([]),
    });
  });
}

function loadJson(url) {
  return fetch(assetUrl(url)).then(r => r.json()).catch(() => []);
}

function validIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value ?? "")) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
}

function validateSchedulePayload(data) {
  if (!data || !Array.isArray(data.weeks) || !Array.isArray(data.courses)) {
    throw new TypeError("El archivo de horarios no tiene el formato esperado");
  }
  if (data.unmatched !== undefined && !Array.isArray(data.unmatched)) {
    throw new TypeError("La lista de horarios sin vínculo no tiene el formato esperado");
  }
  for (const week of data.weeks) {
    if (!validIsoDate(week)) throw new TypeError(`Semana de horarios inválida: ${week}`);
  }
  for (const [courseIndex, course] of data.courses.entries()) {
    if (!course || !String(course.codigo ?? "").trim() || !Array.isArray(course.alternatives)) {
      throw new TypeError(`Materia de horarios inválida en posición ${courseIndex + 1}`);
    }
    for (const [alternativeIndex, alternative] of course.alternatives.entries()) {
      if (!String(alternative?.group ?? "").trim() || !Array.isArray(alternative.sessions)) {
        throw new TypeError(`Alternativa inválida para ${course.codigo} en posición ${alternativeIndex + 1}`);
      }
      for (const [sessionIndex, session] of alternative.sessions.entries()) {
        const required = ["day", "start", "end", "date_start", "date_end"];
        if (!session || required.some(field => !String(session[field] ?? "").trim())) {
          throw new TypeError(`Sesión inválida para ${course.codigo} en posición ${sessionIndex + 1}`);
        }
        const validDay = SCHEDULE_DAYS.some(([day]) => day === session.day);
        const validTime = value => /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
        if (!validDay || !validTime(session.start) || !validTime(session.end)
          || timetableMinutes(session.start) >= timetableMinutes(session.end)
          || !validIsoDate(session.date_start) || !validIsoDate(session.date_end)
          || session.date_start > session.date_end) {
          throw new TypeError(`Sesión inválida para ${course.codigo} en posición ${sessionIndex + 1}`);
        }
      }
    }
  }
  return data;
}

async function loadScheduleBundle() {
  state.scheduleStatus = "loading";
  state.scheduleError = "";
  try {
    const [engine, response] = await Promise.all([
      import("./schedule-engine.mjs"),
      fetch(assetUrl("data/horarios_icai.json")),
    ]);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = validateSchedulePayload(await response.json());
    state.scheduleEngine = engine;
    state.scheduleData = data;
    state.scheduleStatus = "ready";
  } catch (error) {
    state.scheduleEngine = null;
    state.scheduleData = null;
    state.scheduleStatus = "error";
    state.scheduleError = error?.message || "Error desconocido";
  }
  if (scheduleIsVisible()) renderSchedule();
}

async function loadAll() {
  const [itba, icai] = await Promise.all([
    loadJson("data/itba_targets.json"),
    loadJson("data/icai_catalogo.json"),
  ]);
  state.icaiCatalogo = icai;
  state.icaiByCode = Object.fromEntries(icai.map(u => [String(u.codigo), u]));
  state.itbaTargets = Object.fromEntries(
    itba.map(i => [String(i.codigo), i])
  );
  await Promise.all(CARRERAS.filter(c => !c.combinations).map(async c => {
    const [eq, sin] = await Promise.all([
      loadCsv(`data/${c.id}_equivalencias.csv`),
      loadCsv(`data/${c.id}_sin_equivalencia.csv`),
    ]);
    state.data[c.id] = { eq, sin };
  }));

  state.data.icai_combinaciones = {
    eq: await loadCsv("data/icai_combinaciones.csv"),
    sin: [],
  };
}

function buildCareerTabs() {
  const nav = document.getElementById("career-tabs");
  nav.innerHTML = "";
  for (const c of CARRERAS) {
    const btn = document.createElement("button");
    btn.textContent = c.label;
    if (c.id === state.carrera) btn.classList.add("active");
    btn.addEventListener("click", () => {
      state.carrera = c.id;
      if (isIcaiActive()) {
        state.sortKey = "recommendation_bucket";
        state.sortDir = "asc";
      } else if (isIcaiCombinationActive()) {
        state.sortKey = "confianza";
        state.sortDir = "desc";
      }
      buildCareerTabs();
      buildTipoFilter();
      buildCursoFilter();
      buildIcaiFilters();
      render();
    });
    nav.appendChild(btn);
  }
}

function activeCarreraDef() {
  return CARRERAS.find(c => c.id === state.carrera) || CARRERAS[0];
}

function isIcaiActive() {
  return state.carrera === "icai";
}

function isIcaiCombinationActive() {
  return !!activeCarreraDef().combinations;
}

function usesIcaiFilters() {
  return isIcaiActive() || isIcaiCombinationActive();
}

function tiposForActiveTab() {
  if (isIcaiCombinationActive()) {
    const eq = state.data.icai_combinaciones?.eq ?? [];
    return [...new Set(eq.map(u => `${u.term_1} / ${u.term_2}`).filter(Boolean))].sort();
  }
  if (isIcaiActive()) {
    return [...new Set(state.icaiCatalogo.map(u => u.term).filter(Boolean))].sort();
  }
  return [];
}

function cursosForActiveTab() {
  if (isIcaiCombinationActive()) {
    const eq = state.data.icai_combinaciones?.eq ?? [];
    return [...new Set(eq.map(u => `${u.studies_1} / ${u.studies_2}`).filter(Boolean))].sort();
  }
  if (isIcaiActive()) {
    const eq = state.data.icai?.eq ?? [];
    return [...new Set(eq.map(u => String(u.degree)).filter(s => s && s !== "undefined"))].sort();
  }
  return [];
}

function buildTipoFilter() {
  const fs = document.getElementById("tipo-filter");
  const tipos = tiposForActiveTab();
  fs.innerHTML = `<legend>${usesIcaiFilters() ? "Term" : "Tipo"}</legend>`;
  state.tipos = new Set(tipos);
  for (const t of tipos) {
    const id = `tipo-${t.replace(/\s+/g, "-")}`;
    const wrap = document.createElement("label");
    wrap.innerHTML = `<input type="checkbox" id="${escape(id)}" checked> ${escape(t)}`;
    fs.appendChild(wrap);
    wrap.querySelector("input").addEventListener("change", e => {
      if (e.target.checked) state.tipos.add(t); else state.tipos.delete(t);
      render();
    });
  }
}

function buildCursoFilter() {
  const fs = document.getElementById("curso-filter");
  const cursos = cursosForActiveTab();
  fs.innerHTML = `<legend>${isIcaiCombinationActive() ? "Nivel par" : isIcaiActive() ? "Degree" : "Curso"}</legend>`;
  state.cursos = new Set(cursos);
  for (const c of cursos) {
    const wrap = document.createElement("label");
    wrap.innerHTML = `<input type="checkbox" checked> ${escape(c)}`;
    fs.appendChild(wrap);
    wrap.querySelector("input").addEventListener("change", e => {
      if (e.target.checked) state.cursos.add(c); else state.cursos.delete(c);
      render();
    });
  }
}

function buildCheckboxFilter(elementId, legend, values, targetSet) {
  const fs = document.getElementById(elementId);
  fs.style.display = usesIcaiFilters() && values.length ? "" : "none";
  fs.innerHTML = `<legend>${legend}</legend>`;
  targetSet.clear();
  for (const value of values) targetSet.add(value);
  for (const value of values) {
    const wrap = document.createElement("label");
    wrap.innerHTML = `<input type="checkbox" checked> ${escape(value)}`;
    fs.appendChild(wrap);
    wrap.querySelector("input").addEventListener("change", e => {
      if (e.target.checked) targetSet.add(value); else targetSet.delete(value);
      render();
    });
  }
}

function buildIcaiFilters() {
  const eq = state.data[state.carrera]?.eq ?? [];
  const studiesValues = isIcaiCombinationActive()
    ? [...new Set(eq.map(r => `${r.studies_1} / ${r.studies_2}`).filter(Boolean))].sort()
    : [...new Set(eq.map(r => r.studies).filter(Boolean))].sort();
  const availabilityValues = isIcaiCombinationActive()
    ? [...new Set(eq.map(r => r.availability_pair_label).filter(Boolean))].sort()
    : [...new Set(eq.map(r => r.availability_label).filter(Boolean))].sort();
  const permissionValues = isIcaiCombinationActive()
    ? [...new Set(eq.map(r => r.permission_pair_label).filter(Boolean))].sort()
    : [...new Set(eq.map(r => r.permission_label).filter(Boolean))].sort();
  buildCheckboxFilter("studies-filter", "Nivel", studiesValues, state.studies);
  buildCheckboxFilter("availability-filter", "Disponibilidad", availabilityValues, state.availability);
  buildCheckboxFilter("timing-risk-filter", "Riesgo", [...new Set(eq.map(r => r.timing_risk_label).filter(Boolean))].sort(), state.timingRisks);
  buildCheckboxFilter("permission-filter", "Permiso", permissionValues, state.permissions);
  buildCheckboxFilter("bucket-filter", "Ranking", [...new Set(eq.map(r => r.recommendation_bucket).filter(Boolean))].sort(), state.recommendationBuckets);
}

function bindFilters() {
  const slider = document.getElementById("conf-slider");
  const confValue = document.getElementById("conf-value");
  slider.addEventListener("input", () => {
    state.conf = parseInt(slider.value, 10);
    confValue.textContent = state.conf;
    render();
  });
  document.getElementById("search-box").addEventListener("input", e => {
    state.search = e.target.value.toLowerCase();
    render();
  });
  document.getElementById("show-unmatched").addEventListener("change", e => {
    state.showUnmatched = e.target.checked;
    render();
  });
  document.getElementById("only-cart").addEventListener("change", e => {
    state.onlyCart = e.target.checked;
    render();
  });
  document.querySelectorAll("#equiv-table th[data-sort]").forEach(th => {
    th.addEventListener("click", () => {
      const k = th.dataset.sort;
      if (state.sortKey === k) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = k;
        state.sortDir = "asc";
      }
      render();
    });
  });
}

function confDots(n) {
  const N = parseInt(n, 10) || 0;
  let html = "";
  for (let i = 1; i <= 5; i++) {
    html += `<span class="dot${i <= N ? ` on-${N}` : ""}"></span>`;
  }
  return `${html} ${N}`;
}

function icaiBadges(r) {
  if (!usesIcaiFilters()) return "";
  const badges = isIcaiCombinationActive() ? [
    "combinacion_2x1",
    r.availability_label,
    r.permission_label,
    ...(String(r.source_label ?? "").split(",").filter(Boolean)),
  ] : [
    r.availability_label,
    r.timing_risk_label ? `risk-${r.timing_risk_label}` : "",
    r.permission_label,
    r.recommendation_bucket,
    r.source_label,
    r.program_label,
  ].filter(Boolean);
  return `<div class="label-badges">${badges.map(b => `<span class="label-badge ${escape(b)}">${escape(b)}</span>`).join("")}</div>`;
}

function rowsForCareer() {
  const eq = state.data[state.carrera]?.eq ?? [];
  if (isIcaiCombinationActive()) {
    return eq.map(r => normalizeCombinationRow({ ...r, _matched: true, carrera: "icai_combinaciones" }));
  }
  if (isIcaiActive()) {
    const matched = new Set(eq.map(r => String(r.codigo_icai)));
    const out = eq.map(r => normalizeInstitutionRow({ ...r, _matched: true, carrera: "icai" }));
    if (state.showUnmatched) {
      for (const u of state.icaiCatalogo) {
        if (!matched.has(String(u.codigo))) {
          out.push(normalizeInstitutionRow({
            codigo_icai: u.codigo,
            nombre_icai: u.nombre,
            term: u.term,
            studies: u.studies,
            degree: u.degree,
            schedule: u.schedule,
            language: u.language,
            ects_icai: u.ects_semester ?? u.ects,
            codigo_itba: "",
            nombre_itba: "(sin equivalencia ITBA encontrada)",
            confianza: "0",
            comentario: "",
            availability_label: u.labels?.availability ?? "",
            timing_risk_label: u.labels?.timing_risk ?? "",
            level_label: u.labels?.level ?? "",
            permission_label: u.labels?.permission ?? "",
            language_label: u.labels?.language ?? "",
            schedule_label: u.labels?.schedule ?? "",
            recommendation_bucket: "",
            source_label: u.source_label ?? "",
            program_label: u.program_label ?? "",
            source_url: u.source_url ?? "",
            url_guia_icai: u.url_guia,
            carrera: "icai",
            _matched: false,
          }));
        }
      }
    }
    return out;
  }
  return [];
}

function normalizeInstitutionRow(r) {
  if (state.carrera !== "icai") return r;
  return {
    ...r,
    codigo_externo: r.codigo_icai,
    nombre_externo: r.nombre_icai,
    tipo_externo: r.term,
    curso_externo: r.degree,
    ects_externo: r.ects_icai,
    url_guia_externo: r.url_guia_icai,
  };
}

function joinNonEmpty(parts, separator = " / ") {
  return parts.map(p => String(p ?? "").trim()).filter(Boolean).join(separator);
}

function normalizeCombinationRow(r) {
  const codePair = joinNonEmpty([r.codigo_icai_1, r.codigo_icai_2], " + ");
  const namePair = joinNonEmpty([r.nombre_icai_1, r.nombre_icai_2], " + ");
  const termPair = joinNonEmpty([r.term_1, r.term_2]);
  const studiesPair = joinNonEmpty([r.studies_1, r.studies_2]);
  const notes = [
    r.comentario_combinacion,
    r.complementa_por ? `Complementa: ${r.complementa_por}` : "",
    r.gaps_restantes ? `Gaps: ${r.gaps_restantes}` : "",
  ].filter(Boolean).join(" ");
  return {
    ...r,
    codigo_externo: codePair,
    nombre_externo: namePair,
    tipo_externo: termPair,
    curso_externo: studiesPair,
    ects_externo: r.ects_total,
    confianza: r.confianza_combinada,
    comentario: notes,
    studies: studiesPair,
    availability_label: r.availability_pair_label,
    permission_label: r.permission_pair_label,
    source_label: r.source_labels,
    url_guia_externo: joinNonEmpty([r.url_guia_icai_1, r.url_guia_icai_2], " | "),
    _combination: true,
    _matched: true,
  };
}

function applyFilters(rows) {
  return rows.filter(r => {
    const inCart = state.cartIndex.has(cartKey(r.codigo_externo, r.codigo_itba));
    if (state.onlyCart && !inCart) return false;
    if (r._matched && parseInt(r.confianza, 10) < state.conf) return false;
    if (!state.tipos.has(r.tipo_externo)) return false;
    if (!state.cursos.has(String(r.curso_externo))) return false;
    if (usesIcaiFilters()) {
      if (r.studies && !state.studies.has(r.studies)) return false;
      if (r.availability_label && !state.availability.has(r.availability_label)) return false;
      if (r.timing_risk_label && !state.timingRisks.has(r.timing_risk_label)) return false;
      if (r.permission_label && !state.permissions.has(r.permission_label)) return false;
      if (r.recommendation_bucket && !state.recommendationBuckets.has(r.recommendation_bucket)) return false;
    }
    if (state.search) {
      const hay = `${r.codigo_externo} ${r.nombre_externo} ${r.nombre_itba} ${r.comentario} ${r.term ?? ""} ${r.studies ?? ""} ${r.degree ?? ""} ${r.source_label ?? ""} ${r.program_label ?? ""}`.toLowerCase();
      if (!hay.includes(state.search)) return false;
    }
    return true;
  });
}

function sortRows(rows) {
  const k = state.sortKey;
  const dir = state.sortDir === "asc" ? 1 : -1;
  const bucketOrder = { primary: 0, strong_candidate: 1, conditional: 2, backup_only: 3 };
  const availabilityOrder = { exchange_term: 0, exchange_term_all_year: 1, full_year: 1, not_in_exchange_term: 2, unknown: 3 };
  const permissionOrder = { standard: 0, permission_required: 1 };
  return rows.slice().sort((a, b) => {
    if (isIcaiActive() && k === "recommendation_bucket") {
      const av = [
        bucketOrder[a.recommendation_bucket] ?? 99,
        -(parseInt(a.confianza, 10) || 0),
        availabilityOrder[a.availability_label] ?? 99,
        permissionOrder[a.permission_label] ?? 99,
        String(a.codigo_icai ?? ""),
      ];
      const bv = [
        bucketOrder[b.recommendation_bucket] ?? 99,
        -(parseInt(b.confianza, 10) || 0),
        availabilityOrder[b.availability_label] ?? 99,
        permissionOrder[b.permission_label] ?? 99,
        String(b.codigo_icai ?? ""),
      ];
      for (let i = 0; i < av.length; i++) {
        if (av[i] < bv[i]) return -1;
        if (av[i] > bv[i]) return 1;
      }
      return 0;
    }
    let av = a[k], bv = b[k];
    if (k === "confianza" || k === "ects_externo" || k === "curso_externo") {
      av = parseFloat(av) || 0;
      bv = parseFloat(bv) || 0;
    } else {
      av = String(av ?? "").toLowerCase();
      bv = String(bv ?? "").toLowerCase();
    }
    return av < bv ? -dir : av > bv ? dir : 0;
  });
}

function escape(s) {
  return String(s ?? "").replace(/[<>&"]/g, c => (
    { "<": "&lt;", ">": "&gt;", "&": "&amp;", "\"": "&quot;" }[c]
  ));
}

function fallbackHorasClase(ects) {
  const v = parseFloat(String(ects).replace(",", "."));
  return isNaN(v) ? "" : String(Math.round(v * ECTS_TO_CLASS_HOURS));
}

function fallbackCreditosItba(ects) {
  const v = parseFloat(String(ects).replace(",", "."));
  if (isNaN(v)) return "";
  return String(Math.round(v * ECTS_TO_CLASS_HOURS / SEMANAS_SEMESTRE));
}

function pickHorasClase(r, course) {
  return String(r.horas_clase_externo || course.horas_clase || fallbackHorasClase(r.ects_externo ?? course.ects));
}

function pickCreditosItba(r, course) {
  return String(r.creditos_itba_estimado || course.creditos_itba_estimado || fallbackCreditosItba(r.ects_externo ?? course.ects));
}

function rowToCartItem(r, carrera) {
  const course = state.icaiByCode[String(r.codigo_externo)] || {};
  const ects = String(r.ects_externo ?? "");
  return {
    codigo_externo: String(r.codigo_externo ?? ""),
    nombre_externo: String(r.nombre_externo ?? ""),
    carrera: r.carrera ?? carrera ?? "",
    tipo_externo: String(r.tipo_externo ?? ""),
    curso_externo: String(r.curso_externo ?? ""),
    ects_externo: ects,
    horas_clase: pickHorasClase(r, course),
    creditos_itba: pickCreditosItba(r, course),
    codigo_itba: String(r.codigo_itba ?? ""),
    nombre_itba: String(r.nombre_itba ?? ""),
    confianza: String(r.confianza ?? ""),
    comentario: String(r.comentario ?? ""),
    pdf_path_externo: String(r.pdf_path_externo ?? course.pdf_path ?? ""),
    url_guia_externo: String(r.url_guia_externo ?? course.url_guia ?? ""),
  };
}

function normalizeEcts(v) {
  if (v === undefined || v === null) return "";
  const s = String(v).replace(",", ".");
  const f = parseFloat(s);
  return isNaN(f) ? s : String(f);
}

function enrichCartFromCatalog() {
  let dirty = false;
  state.cart = state.cart.filter(c => {
    if (c.carrera !== "icai") return true;
    const exists = !!state.icaiByCode[String(c.codigo_externo)];
    if (!exists) dirty = true;
    return exists;
  });
  for (const c of state.cart) {
    const course = state.icaiByCode[String(c.codigo_externo)];
    if (!course) continue;
    if (c.carrera === "icai") {
      const semesterEcts = normalizeEcts(course.ects_semester ?? course.ects);
      if (c.ects_externo !== semesterEcts) { c.ects_externo = semesterEcts; dirty = true; }
      if (c.tipo_externo !== course.term) { c.tipo_externo = course.term; dirty = true; }
      if (c.nombre_externo !== course.nombre) { c.nombre_externo = course.nombre; dirty = true; }
    }
    if (!c.pdf_path_externo && course.pdf_path) { c.pdf_path_externo = course.pdf_path; dirty = true; }
    if (!c.url_guia_externo && course.url_guia) { c.url_guia_externo = course.url_guia; dirty = true; }
    const normalEcts = normalizeEcts(c.ects_externo);
    if (normalEcts && c.ects_externo !== normalEcts) { c.ects_externo = normalEcts; dirty = true; }
    const newHoras = pickHorasClase(c, course);
    const newCred = pickCreditosItba(c, course);
    if (newHoras && c.horas_clase !== newHoras) { c.horas_clase = newHoras; dirty = true; }
    if (newCred && c.creditos_itba !== newCred) { c.creditos_itba = newCred; dirty = true; }
    if (c.horas_estimadas !== undefined) { delete c.horas_estimadas; dirty = true; }
  }
  if (dirty) persistCart();
}

const carreraLabel = id => (CARRERAS.find(c => c.id === id) || {}).label || id;

function externalLabel(carrera) {
  return carrera === "icai_combinaciones" ? "ICAI ×2" : "ICAI";
}

function toggleCartItem(r) {
  const key = cartKey(r.codigo_externo, r.codigo_itba);
  if (state.cartIndex.has(key)) {
    state.cart = state.cart.filter(c => cartKey(c.codigo_externo, c.codigo_itba) !== key);
  } else {
    state.cart.push(rowToCartItem(r, state.carrera));
  }
  rebuildCartIndex();
  persistCart();
  renderCart();
  render();
}

function removeCartItem(key) {
  state.cart = state.cart.filter(c => cartKey(c.codigo_externo, c.codigo_itba) !== key);
  rebuildCartIndex();
  persistCart();
  renderCart();
  render();
}

function clearCart() {
  if (!state.cart.length) return;
  if (!confirm(`¿Vaciar el carrito? Vas a perder ${state.cart.length} items.`)) return;
  state.cart = [];
  rebuildCartIndex();
  persistCart();
  renderCart();
  render();
}

function cartTotalEcts() {
  const seen = new Set();
  let total = 0;
  for (const c of state.cart) {
    if (seen.has(c.codigo_externo)) continue;
    seen.add(c.codigo_externo);
    const v = parseFloat(String(c.ects_externo).replace(",", "."));
    if (!isNaN(v)) total += v;
  }
  return total;
}

function uniqueExternalInCart() {
  return new Set(state.cart.map(c => c.codigo_externo)).size;
}

function fmtEcts(n) {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function isIcaiCartItem(item) {
  const code = String(item.codigo_externo ?? "");
  return item.carrera === "icai" || (!item.carrera && !!state.icaiByCode[code]);
}

function selectedIcaiCodes() {
  return [...new Set(
    state.cart.filter(isIcaiCartItem).map(item => String(item.codigo_externo)).filter(Boolean)
  )].sort();
}

function scheduleIsVisible() {
  return state.cartOpen && state.scheduleTab === "schedule";
}

function scheduleColor(code) {
  let hash = 2166136261;
  for (const character of String(code)) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return SCHEDULE_COLORS[(hash >>> 0) % SCHEDULE_COLORS.length];
}

function timetableMinutes(value) {
  const [hours, minutes] = String(value ?? "").split(":").map(Number);
  return hours * 60 + minutes;
}

function sessionKey(session) {
  return [
    session.codigo,
    session.group,
    session.day,
    session.start,
    session.end,
    session.date_start,
    session.date_end,
    session.room ?? "",
  ].join("|");
}

function formatWeek(weekStart) {
  const start = new Date(`${weekStart}T00:00:00Z`);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 4);
  const format = new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
  return `${format.format(start)} – ${format.format(end)}`;
}

function layoutDaySessions(sessions) {
  const sorted = sessions
    .map(session => ({
      session,
      startMinutes: timetableMinutes(session.start),
      endMinutes: timetableMinutes(session.end),
    }))
    .sort((a, b) => a.startMinutes - b.startMinutes || a.endMinutes - b.endMinutes);
  const laidOut = [];
  let cluster = [];
  let clusterEnd = -Infinity;

  function finishCluster() {
    if (!cluster.length) return;
    const laneEnds = [];
    for (const entry of cluster) {
      let lane = laneEnds.findIndex(end => end <= entry.startMinutes);
      if (lane === -1) lane = laneEnds.length;
      laneEnds[lane] = entry.endMinutes;
      entry.lane = lane;
    }
    const laneCount = laneEnds.length;
    for (const entry of cluster) laidOut.push({ ...entry, laneCount });
    cluster = [];
    clusterEnd = -Infinity;
  }

  for (const entry of sorted) {
    if (cluster.length && entry.startMinutes >= clusterEnd) finishCluster();
    cluster.push(entry);
    clusterEnd = Math.max(clusterEnd, entry.endMinutes);
  }
  finishCluster();
  return laidOut;
}

function conflictKeysForVisibleWeek(option, sessions) {
  const visibleKeys = new Set(sessions.map(sessionKey));
  const conflicts = new Set();
  for (const pair of option.conflicts ?? []) {
    const leftKey = sessionKey(pair.left);
    const rightKey = sessionKey(pair.right);
    if (visibleKeys.has(leftKey) && visibleKeys.has(rightKey)) {
      conflicts.add(leftKey);
      conflicts.add(rightKey);
    }
  }
  return conflicts;
}

function scheduleCourseName(session) {
  const publishedName = String(session.nombre ?? "").trim();
  const catalogName = String(state.icaiByCode[String(session.codigo)]?.nombre ?? "").trim();
  return publishedName || catalogName || "Materia ICAI";
}

function renderScheduleEvent(entry, conflictKeys) {
  const { session, startMinutes, endMinutes, lane, laneCount } = entry;
  const clippedStart = Math.max(startMinutes, SCHEDULE_START_MINUTES);
  const clippedEnd = Math.min(endMinutes, SCHEDULE_END_MINUTES);
  if (clippedStart >= clippedEnd) return "";
  const color = scheduleColor(session.codigo);
  const top = (clippedStart - SCHEDULE_START_MINUTES) / 60 * SCHEDULE_HOUR_HEIGHT;
  const height = (clippedEnd - clippedStart) / 60 * SCHEDULE_HOUR_HEIGHT;
  const conflict = conflictKeys.has(sessionKey(session));
  const room = session.room || "Aula no publicada";
  const courseName = scheduleCourseName(session);
  const label = `${courseName}, grupo ${session.group}, ${room}, ${session.start} a ${session.end}${conflict ? ", con conflicto" : ""}`;
  return `
    <article class="schedule-event${conflict ? " has-conflict" : ""}" role="group"
      aria-label="${escape(label)}"
      style="--event-top:${top}px;--event-height:${height}px;--event-lane:${lane};--event-lanes:${laneCount};--event-bg:${color.bg};--event-border:${color.border};--event-text:${color.text}">
      <strong>${escape(courseName)}</strong>
      <span>${escape(session.codigo)} · Grupo ${escape(session.group)}</span>
      <span>${escape(room)}</span>
      <time>${escape(session.start)}–${escape(session.end)}</time>
    </article>`;
}

function renderScheduleGrid(option, week) {
  const sessions = state.scheduleEngine.sessionsForWeek(option, week);
  const conflictKeys = conflictKeysForVisibleWeek(option, sessions);
  const timeLabels = Array.from({ length: 15 }, (_, index) => {
    const hour = index + 8;
    const edgeClass = index === 0 ? " first" : index === 14 ? " last" : "";
    return `<span class="schedule-time${edgeClass}" style="--time-y:${index * SCHEDULE_HOUR_HEIGHT}px">${String(hour).padStart(2, "0")}:00</span>`;
  }).join("");
  const dayHeaders = SCHEDULE_DAYS.map(([, label]) => `<div class="schedule-day-header">${label}</div>`).join("");
  const dayColumns = SCHEDULE_DAYS.map(([day, label]) => {
    const laidOut = layoutDaySessions(sessions.filter(session => session.day === day));
    return `<div class="schedule-day-column" role="group" aria-label="${label}">
      ${laidOut.map(entry => renderScheduleEvent(entry, conflictKeys)).join("")}
    </div>`;
  }).join("");
  return `
    ${sessions.length ? "" : `<p class="schedule-week-empty">No hay clases publicadas para esta opción durante la semana elegida.</p>`}
    <div class="schedule-grid-scroll" role="region" tabindex="0" aria-label="Horario semanal del ${escape(formatWeek(week))}; desplazable horizontalmente">
      <div class="schedule-grid">
        <div class="schedule-corner">Hora</div>
        ${dayHeaders}
        <div class="schedule-time-axis" aria-hidden="true">${timeLabels}</div>
        ${dayColumns}
      </div>
    </div>`;
}

function scheduleLegend(codes) {
  return `<ul class="schedule-legend" aria-label="Materias incluidas">${codes.map(code => {
    const course = state.icaiByCode[code] ?? {};
    const color = scheduleColor(code);
    return `<li><span class="schedule-swatch" style="--swatch:${color.bg};--swatch-border:${color.border}"></span><strong>${escape(code)}</strong> ${escape(course.nombre || "Materia ICAI")}</li>`;
  }).join("")}</ul>`;
}

function bindRenderedScheduleControls(weeks, optionCount) {
  const weekSelect = document.getElementById("schedule-week-select");
  if (weekSelect) {
    weekSelect.addEventListener("change", event => {
      state.scheduleWeek = event.target.value;
      renderSchedule();
    });
  }
  const bind = (id, action) => {
    const button = document.getElementById(id);
    if (button) button.addEventListener("click", action);
  };
  bind("schedule-week-prev", () => {
    const index = weeks.indexOf(state.scheduleWeek);
    if (index > 0) {
      state.scheduleWeek = weeks[index - 1];
      renderSchedule();
    }
  });
  bind("schedule-week-next", () => {
    const index = weeks.indexOf(state.scheduleWeek);
    if (index >= 0 && index < weeks.length - 1) {
      state.scheduleWeek = weeks[index + 1];
      renderSchedule();
    }
  });
  bind("schedule-option-prev", () => {
    if (state.scheduleOptionIndex > 0) {
      state.scheduleOptionIndex -= 1;
      renderSchedule();
    }
  });
  bind("schedule-option-next", () => {
    if (state.scheduleOptionIndex < optionCount - 1) {
      state.scheduleOptionIndex += 1;
      renderSchedule();
    }
  });
}

function renderScheduleLoadError(content) {
  content.innerHTML = `
    <div class="schedule-state schedule-state-error" role="alert">
      <strong>No se pudieron cargar los horarios</strong>
      <p>Falta o no es válido <code>webui/data/horarios_icai.json</code>. Refrescá los datos con el extractor oficial y volvé a abrir esta vista.</p>
      <small>Detalle: ${escape(state.scheduleError || "Error desconocido")}</small>
    </div>`;
}

function renderSchedule() {
  const content = document.getElementById("schedule-content");
  if (!content || !scheduleIsVisible()) return;
  if (state.scheduleStatus === "loading") {
    content.innerHTML = `<div class="schedule-state schedule-state-loading">Cargando horarios oficiales…</div>`;
    return;
  }
  if (state.scheduleStatus === "error" || !state.scheduleEngine || !state.scheduleData) {
    renderScheduleLoadError(content);
    return;
  }
  try {
    renderReadySchedule(content);
  } catch (error) {
    console.error("Error rendering schedule data:", error);
    state.scheduleStatus = "error";
    state.scheduleError = error?.message || "Datos de horarios inválidos";
    renderScheduleLoadError(content);
  }
}

function renderReadySchedule(content) {
  const codes = selectedIcaiCodes();
  const ignoredCount = state.cart.filter(item => !isIcaiCartItem(item)).length;

  if (!codes.length) {
    content.innerHTML = `
      <div class="schedule-state schedule-state-empty">
        <span aria-hidden="true">☆</span>
        <strong>Elegí materias ICAI</strong>
        <p>Marcá una o más estrellas en la pestaña ICAI Comillas para generar sus combinaciones de horarios.</p>
        ${ignoredCount ? `<small>${ignoredCount} ${ignoredCount === 1 ? "materia externa no participa" : "materias externas no participan"} en este combinador.</small>` : ""}
      </div>`;
    return;
  }

  const selectionKey = codes.join("|");
  if (selectionKey !== state.scheduleSelectionKey) {
    state.scheduleSelectionKey = selectionKey;
    state.scheduleOptionIndex = 0;
  }
  const result = state.scheduleEngine.buildScheduleOptions(codes, state.scheduleData);
  const weeks = [...state.scheduleData.weeks].sort();
  if (!state.scheduleWeek || !weeks.includes(state.scheduleWeek)) state.scheduleWeek = weeks[0] || "";

  if (result.unresolved.length) {
    const unresolvedItems = result.unresolved.map(item => {
      const course = state.icaiByCode[String(item.codigo)] ?? {};
      return `<li><strong>${escape(item.codigo)}</strong> — ${escape(course.nombre || item.nombre || "Materia ICAI")} <span>(${escape(item.reason || "sin horario publicado")})</span></li>`;
    }).join("");
    content.innerHTML = `
      ${scheduleLegend(codes)}
      <div class="schedule-state schedule-state-unresolved" role="alert">
        <strong>Sin horario vinculado</strong>
        <p>No se genera una opción incompleta: estas materias no tienen un horario oficial vinculado de forma exacta.</p>
        <ul>${unresolvedItems}</ul>
      </div>`;
    return;
  }
  if (!result.options.length) {
    content.innerHTML = `
      ${scheduleLegend(codes)}
      <div class="schedule-state schedule-state-error" role="alert">
        <strong>No hay combinaciones disponibles</strong>
        <p>Los datos publicados no permiten construir una opción para toda la selección.</p>
      </div>`;
    return;
  }
  if (!weeks.length) {
    content.innerHTML = `
      ${scheduleLegend(codes)}
      <div class="schedule-state schedule-state-error" role="alert">
        <strong>No hay semanas publicadas</strong>
        <p>El archivo de horarios no incluye semanas válidas para visualizar.</p>
      </div>`;
    return;
  }

  state.scheduleOptionIndex = Math.min(state.scheduleOptionIndex, result.options.length - 1);
  const option = result.options[state.scheduleOptionIndex];
  const weekIndex = weeks.indexOf(state.scheduleWeek);
  const conflictSummary = option.conflictCount
    ? `<div class="schedule-conflict-summary has-conflicts" role="status"><span aria-hidden="true">!</span><strong>${option.conflictCount} ${option.conflictCount === 1 ? "conflicto mínimo" : "conflictos mínimos"}</strong> durante el semestre. Los bloques coincidentes de esta semana comparten carriles y llevan borde rojo.</div>`
    : `<div class="schedule-conflict-summary is-clear" role="status"><span aria-hidden="true">✓</span><strong>Sin superposiciones</strong> durante todo el semestre Fall.</div>`;
  const ignoredNote = ignoredCount
    ? `<p class="schedule-scope-note">${ignoredCount} ${ignoredCount === 1 ? "materia no ICAI queda fuera" : "materias no ICAI quedan fuera"} del combinador.</p>`
    : "";
  content.innerHTML = `
    <div class="schedule-toolbar">
      <div class="schedule-control-group" aria-label="Semana visible">
        <span class="schedule-control-label">Semana</span>
        <div class="schedule-control-row">
          <button id="schedule-week-prev" type="button" aria-label="Semana anterior" ${weekIndex <= 0 ? "disabled" : ""}>←</button>
          <select id="schedule-week-select" aria-label="Semana visible">
            ${weeks.map(week => `<option value="${escape(week)}"${week === state.scheduleWeek ? " selected" : ""}>${escape(formatWeek(week))}</option>`).join("")}
          </select>
          <button id="schedule-week-next" type="button" aria-label="Semana siguiente" ${weekIndex >= weeks.length - 1 ? "disabled" : ""}>→</button>
        </div>
      </div>
      <div class="schedule-control-group schedule-option-control" aria-label="Opción de horario">
        <span class="schedule-control-label">Combinación</span>
        <div class="schedule-control-row">
          <button id="schedule-option-prev" type="button" aria-label="Opción anterior" ${state.scheduleOptionIndex <= 0 ? "disabled" : ""}>←</button>
          <output aria-live="polite">Opción ${state.scheduleOptionIndex + 1} de ${result.options.length}</output>
          <button id="schedule-option-next" type="button" aria-label="Opción siguiente" ${state.scheduleOptionIndex >= result.options.length - 1 ? "disabled" : ""}>→</button>
        </div>
      </div>
    </div>
    ${conflictSummary}
    ${ignoredNote}
    ${scheduleLegend(codes)}
    ${renderScheduleGrid(option, state.scheduleWeek)}`;
  bindRenderedScheduleControls(weeks, result.options.length);
}

function renderEquiv(rows) {
  const tbody = document.querySelector("#equiv-table tbody");
  tbody.innerHTML = "";

  document.querySelectorAll("#equiv-table th").forEach(th =>
    th.classList.remove("sort-asc", "sort-desc")
  );
  const active = document.querySelector(`#equiv-table th[data-sort="${state.sortKey}"]`);
  if (active) active.classList.add(state.sortDir === "asc" ? "sort-asc" : "sort-desc");

  for (const r of rows) {
    const inCart = state.cartIndex.has(cartKey(r.codigo_externo, r.codigo_itba));
    const tr = document.createElement("tr");
    if (!r._matched) tr.classList.add("unmatched");
    if (inCart) tr.classList.add("in-cart");
    const course = state.icaiByCode[String(r.codigo_externo)] || {};
    const hasPdf = false;
    const urlGuia = r.url_guia_externo || course.url_guia || "";
    const hasGuiaContent = course.guia && Object.values(course.guia).some(v => typeof v === "string" && v.trim());
    const guiaCell = r._combination ? `
      ${r.url_guia_icai_1 ? `<a class="guia-link url-link" href="${escape(r.url_guia_icai_1)}" target="_blank" title="URL del programa 1">1</a>` : ""}
      ${r.url_guia_icai_2 ? `<a class="guia-link url-link" href="${escape(r.url_guia_icai_2)}" target="_blank" title="URL del programa 2">2</a>` : ""}` : `
      ${hasPdf ? `<a class="guia-link pdf-link" href="data/pdfs/${escape(r.codigo_externo)}.pdf" target="_blank" title="PDF guía docente firmada">📄</a>` : ""}
      ${urlGuia ? `<a class="guia-link url-link" href="${escape(urlGuia)}" target="_blank" title="URL del programa">🔗</a>` : ""}
      ${hasGuiaContent ? `<button class="guia-link guia-expand" title="Ver guía docente parseada inline">📖</button>` : ""}`;
    const carreraBadge = activeCarreraDef().crossCarrera && r.carrera
      ? `<span class="carrera-badge" title="${escape(carreraLabel(r.carrera))}">${escape(carreraLabel(r.carrera))}</span> `
      : "";

    tr.innerHTML = `
      <td class="cart-col"><button class="cart-toggle${inCart ? " in-cart" : ""}" title="${inCart ? "Quitar del carrito" : "Agregar al carrito"}">${inCart ? "★" : "☆"}</button></td>
      <td>${escape(r.codigo_externo)}</td>
      <td>${carreraBadge}${escape(r.nombre_externo)}${icaiBadges(r)}</td>
      <td class="guia-col">${guiaCell}</td>
      <td>${escape(r.tipo_externo)}</td>
      <td>${escape(r.curso_externo)}</td>
      <td>${escape(r.ects_externo)}</td>
      <td class="itba-code" data-itba="${escape(r.codigo_itba)}">${escape(r.codigo_itba)}</td>
      <td>${escape(r.nombre_itba)}</td>
      <td class="confianza">${r._matched ? confDots(r.confianza) : "—"}</td>
      <td>${escape(r.comentario)}</td>`;
    tr.querySelector(".cart-toggle").addEventListener("click", e => {
      e.stopPropagation();
      toggleCartItem(r);
    });
    const expandBtn = tr.querySelector(".guia-expand");
    if (expandBtn) {
      expandBtn.addEventListener("click", e => {
        e.stopPropagation();
        toggleGuiaExpand(tr, course);
      });
    }
    tbody.appendChild(tr);
  }

  tbody.querySelectorAll("td.itba-code").forEach(td => {
    td.addEventListener("click", () => {
      const cod = td.dataset.itba;
      if (!cod) return;
      const tr = td.closest("tr");
      const next = tr.nextElementSibling;
      if (next && next.classList.contains("expanded-row")) {
        next.remove();
        return;
      }
      const itba = state.itbaTargets[cod];
      if (!itba) return;
      const exp = document.createElement("tr");
      exp.classList.add("expanded-row");
      exp.innerHTML = `<td colspan="11"><strong>Contenidos mínimos ITBA ${escape(cod)}:</strong> ${escape(itba.contenidos_minimos || "(no disponible)")}</td>`;
      tr.after(exp);
    });
  });
}

const SECTION_LABELS = {
  descripcion: "Descripción general",
  resultados: "Resultados",
  competencias_transversales: "Competencias transversales",
  conocimientos_previos: "Conocimientos previos",
  unidades_didacticas: "Unidades didácticas (temario)",
  distribucion: "Distribución del trabajo",
  evaluacion: "Evaluación",
  bibliografia: "Bibliografía",
  porcentaje_de_ausencia_maxima: "Porcentaje de ausencia máxima",
};

function toggleGuiaExpand(tr, course) {
  const next = tr.nextElementSibling;
  if (next && next.classList.contains("expanded-row")) {
    next.remove();
    return;
  }
  const guia = course.guia || {};
  const sections = Object.entries(guia)
    .filter(([k, v]) => typeof v === "string" && v.trim() && !k.startsWith("grado_en_"))
    .map(([k, v]) => `<div class="guia-section"><strong>${escape(SECTION_LABELS[k] || k)}:</strong> ${escape(v)}</div>`)
    .join("");
  const exp = document.createElement("tr");
  exp.classList.add("expanded-row");
  exp.innerHTML = `<td colspan="11"><div class="guia-expanded"><strong>Guía docente ICAI ${escape(course.codigo)} — ${escape(course.nombre)}</strong>${sections || "<p>(Sin guía parseada disponible)</p>"}</div></td>`;
  tr.after(exp);
}

function renderSinEquiv() {
  const sin = state.data[state.carrera]?.sin ?? [];
  document.getElementById("sin-equiv-count").textContent = sin.length;
  const tbody = document.querySelector("#sin-equiv-table tbody");
  tbody.innerHTML = "";
  for (const r of sin) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escape(r.codigo_itba)}</td>
      <td>${escape(r.nombre_itba)}</td>
      <td>${escape(r.contenidos_minimos)}</td>`;
    tbody.appendChild(tr);
  }
}

function renderCart() {
  const items = state.cart;
  const totalEcts = cartTotalEcts();
  const uniqExternal = uniqueExternalInCart();

  document.getElementById("cart-count-items").textContent = items.length;
  document.getElementById("cart-count-ects").textContent = fmtEcts(totalEcts);
  document.getElementById("cart-summary-items").textContent = items.length;
  document.getElementById("cart-summary-external").textContent = uniqExternal;
  document.getElementById("cart-summary-ects").textContent = fmtEcts(totalEcts);

  const list = document.getElementById("cart-list");
  const empty = document.getElementById("cart-empty");
  list.innerHTML = "";

  if (!items.length) {
    empty.style.display = "block";
    if (scheduleIsVisible()) renderSchedule();
    return;
  }
  empty.style.display = "none";

  for (const it of items) {
    const li = document.createElement("li");
    const key = cartKey(it.codigo_externo, it.codigo_itba);
    const itbaLine = it.codigo_itba
      ? `↔ ITBA <strong>${escape(it.codigo_itba)}</strong> ${escape(it.nombre_itba)}<span class="conf">[${escape(it.confianza)}]</span>`
      : `<em>(sin ITBA asociada)</em>`;
    li.innerHTML = `
      <button class="cart-item-remove" title="Quitar">✕</button>
      <div class="cart-item-head">
        <span class="cart-item-external">${escape(externalLabel(it.carrera))} ${escape(it.codigo_externo)} — ${escape(it.nombre_externo)}</span>
        <span class="cart-item-meta">${escape(it.ects_externo)} ECTS · ${escape(carreraLabel(it.carrera))}</span>
      </div>
      <div class="cart-item-itba">${itbaLine}</div>
      ${it.comentario ? `<div class="cart-item-comment">${escape(it.comentario)}</div>` : ""}`;
    li.querySelector(".cart-item-remove").addEventListener("click", () => removeCartItem(key));
    list.appendChild(li);
  }
  if (scheduleIsVisible()) renderSchedule();
}

function exportCart() {
  if (!state.cart.length) {
    alert("El carrito está vacío.");
    return;
  }
  const data = state.cart.map(item => {
    const row = {};
    for (const f of CART_CSV_FIELDS) row[f] = item[f] ?? "";
    return row;
  });
  const csv = Papa.unparse({ fields: CART_CSV_FIELDS, data });
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "mi_carrito.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function importCart(file) {
  Papa.parse(file, {
    header: true,
    skipEmptyLines: true,
    complete: r => {
      const valid = (r.data || []).filter(row => row.codigo_externo);
      if (!valid.length) {
        alert("El CSV no contiene filas válidas (requiere columna codigo_externo).");
        return;
      }
      const replace = confirm(`Vas a reemplazar el carrito (${state.cart.length} items) con ${valid.length} items del CSV. ¿Continuar?\n\nCancelar = mergear (combinar sin duplicar).`);
      const incoming = valid.map(row => ({
        codigo_externo: String(row.codigo_externo ?? ""),
        nombre_externo: String(row.nombre_externo ?? ""),
        carrera: String(row.carrera ?? ""),
        tipo_externo: String(row.tipo_externo ?? ""),
        curso_externo: String(row.curso_externo ?? ""),
        ects_externo: String(row.ects_externo ?? ""),
        codigo_itba: String(row.codigo_itba ?? ""),
        nombre_itba: String(row.nombre_itba ?? ""),
        confianza: String(row.confianza ?? ""),
        comentario: String(row.comentario ?? ""),
      }));
      if (replace) {
        state.cart = incoming;
      } else {
        const existing = new Set(state.cart.map(c => cartKey(c.codigo_externo, c.codigo_itba)));
        for (const it of incoming) {
          if (!existing.has(cartKey(it.codigo_externo, it.codigo_itba))) state.cart.push(it);
        }
      }
      rebuildCartIndex();
      persistCart();
      renderCart();
      render();
    },
    error: () => alert("Error parseando el CSV."),
  });
}

function bindCart() {
  const fab = document.getElementById("cart-fab");
  const panel = document.getElementById("cart-panel");
  const backdrop = document.getElementById("cart-backdrop");
  const close = document.getElementById("cart-close");
  const materialTab = document.getElementById("cart-tab-materials");
  const scheduleTab = document.getElementById("cart-tab-schedule");
  const materialPanel = document.getElementById("cart-materials-panel");
  const schedulePanel = document.getElementById("cart-schedule-panel");

  function activateTab(tabName, focus = false) {
    state.scheduleTab = tabName;
    const showSchedule = tabName === "schedule";
    materialTab.setAttribute("aria-selected", String(!showSchedule));
    materialTab.tabIndex = showSchedule ? -1 : 0;
    scheduleTab.setAttribute("aria-selected", String(showSchedule));
    scheduleTab.tabIndex = showSchedule ? 0 : -1;
    materialPanel.hidden = showSchedule;
    schedulePanel.hidden = !showSchedule;
    panel.classList.toggle("schedule-open", showSchedule);
    if (showSchedule) renderSchedule();
    if (focus) (showSchedule ? scheduleTab : materialTab).focus();
  }

  function open() {
    state.cartOpen = true;
    panel.classList.add("open");
    panel.removeAttribute("inert");
    panel.setAttribute("aria-hidden", "false");
    backdrop.hidden = false;
    if (scheduleIsVisible()) renderSchedule();
    close.focus();
  }
  function shut() {
    state.cartOpen = false;
    panel.classList.remove("open");
    backdrop.hidden = true;
    fab.focus();
    panel.setAttribute("aria-hidden", "true");
    panel.setAttribute("inert", "");
  }

  fab.addEventListener("click", open);
  close.addEventListener("click", shut);
  backdrop.addEventListener("click", shut);
  materialTab.addEventListener("click", () => activateTab("materials"));
  scheduleTab.addEventListener("click", () => activateTab("schedule"));
  for (const tab of [materialTab, scheduleTab]) {
    tab.addEventListener("keydown", event => {
      if (!(["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))) return;
      event.preventDefault();
      const nextTab = event.key === "ArrowLeft" || event.key === "Home" ? "materials" : "schedule";
      activateTab(nextTab, true);
    });
  }
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && panel.classList.contains("open")) shut();
  });

  document.getElementById("cart-export").addEventListener("click", exportCart);
  document.getElementById("cart-clear").addEventListener("click", clearCart);

  const fileInput = document.getElementById("cart-import-file");
  document.getElementById("cart-import").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", e => {
    const f = e.target.files?.[0];
    if (f) importCart(f);
    e.target.value = "";
  });
  activateTab(state.scheduleTab);
}

function render() {
  let rows = rowsForCareer();
  rows = applyFilters(rows);
  rows = sortRows(rows);
  renderEquiv(rows);
  const def = activeCarreraDef();
  const hideSinEquiv = !!def.crossCarrera || !!def.combinations;
  document.getElementById("sin-equiv-section").style.display = hideSinEquiv ? "none" : "";
  document.getElementById("show-unmatched").disabled = hideSinEquiv;
  document.getElementById("icai-source-notice").style.display = usesIcaiFilters() ? "" : "none";
  if (!hideSinEquiv) renderSinEquiv();
}

(async function init() {
  loadCart();
  void loadScheduleBundle();
  try {
    await loadAll();
  } catch (err) {
    console.error("Error loading data:", err);
  }
  enrichCartFromCatalog();
  buildCareerTabs();
  buildTipoFilter();
  buildCursoFilter();
  buildIcaiFilters();
  bindFilters();
  bindCart();
  renderCart();
  render();
})();
