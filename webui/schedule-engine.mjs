const DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

function minutes(value) {
  const match = /^(\d{2}):(\d{2})$/.exec(value ?? "");
  if (!match) throw new TypeError(`Invalid timetable time: ${value}`);
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) throw new TypeError(`Invalid timetable time: ${value}`);
  return hour * 60 + minute;
}

function parseIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value ?? "")) {
    throw new TypeError(`Invalid timetable date: ${value}`);
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value) {
    throw new TypeError(`Invalid timetable date: ${value}`);
  }
  return parsed;
}

function dayPosition(day) {
  const position = DAY_ORDER.indexOf(day);
  if (position === -1) throw new TypeError(`Invalid timetable day: ${day}`);
  return position;
}

function dateRange(start, end) {
  const first = parseIsoDate(start);
  const last = parseIsoDate(end);
  if (first > last) throw new TypeError(`Invalid timetable date range: ${start} - ${end}`);
  return { first, last };
}

function overlappingRange(a, b) {
  const first = a.first > b.first ? a.first : b.first;
  const last = a.last < b.last ? a.last : b.last;
  return first <= last ? { first, last } : null;
}

function sessionDetails(entry) {
  const start = minutes(entry.start);
  const end = minutes(entry.end);
  if (start >= end) throw new TypeError(`Invalid timetable duration: ${entry.start} - ${entry.end}`);
  return {
    day: dayPosition(entry.day),
    start,
    end,
    range: dateRange(entry.date_start, entry.date_end),
  };
}

function occursOnWeekday(range, weekday) {
  const first = new Date(range.first);
  const offset = (weekday - ((first.getUTCDay() + 6) % 7) + 7) % 7;
  first.setUTCDate(first.getUTCDate() + offset);
  return first <= range.last;
}

/** Return whether two timetable sessions ever coincide during the semester. */
export function sessionsOverlap(a, b) {
  const left = sessionDetails(a);
  const right = sessionDetails(b);
  if (left.day !== right.day || left.start >= right.end || right.start >= left.end) return false;
  const sharedRange = overlappingRange(left.range, right.range);
  return sharedRange !== null && occursOnWeekday(sharedRange, left.day);
}

function decorateAlternative(course, alternative) {
  const { codigo, nombre } = course;
  return {
    ...alternative,
    codigo,
    nombre,
    sessions: (alternative.sessions ?? []).map((entry) => {
      sessionDetails(entry);
      return {
        ...entry,
        codigo,
        group: alternative.group,
      };
    }),
  };
}

function declaredWeekSet(weeks) {
  if (!Array.isArray(weeks) || weeks.length === 0) return null;
  return new Set(weeks.map(mondayFor));
}

function occurrenceSignatures(entry, weeks) {
  const details = sessionDetails(entry);
  const occurrence = new Date(details.range.first);
  const firstWeekday = (occurrence.getUTCDay() + 6) % 7;
  occurrence.setUTCDate(occurrence.getUTCDate() + ((details.day - firstWeekday + 7) % 7));
  const signatures = [];
  while (occurrence <= details.range.last) {
    const occurrenceDate = occurrence.toISOString().slice(0, 10);
    if (!weeks || weeks.has(mondayFor(occurrenceDate))) {
      signatures.push([
        entry.codigo,
        occurrenceDate,
        entry.day,
        entry.start,
        entry.end,
        entry.room ?? "",
      ].join("\u001f"));
    }
    occurrence.setUTCDate(occurrence.getUTCDate() + 7);
  }
  return signatures;
}

function optionSignature(sessions, weeks) {
  const declaredWeeks = declaredWeekSet(weeks);
  return [...new Set(sessions.flatMap((entry) => occurrenceSignatures(entry, declaredWeeks)))]
    .sort()
    .join("\u001e");
}

function metrics(sessions, conflicts) {
  const byDay = new Map();
  for (const entry of sessions) {
    const entries = byDay.get(entry.day) ?? [];
    entries.push(entry);
    byDay.set(entry.day, entries);
  }

  let gaps = 0;
  let finish = 0;
  for (const entries of byDay.values()) {
    entries.sort((a, b) => minutes(a.start) - minutes(b.start) || minutes(a.end) - minutes(b.end));
    let latestEnd = minutes(entries[0].end);
    finish = Math.max(finish, latestEnd);
    for (const entry of entries.slice(1)) {
      const start = minutes(entry.start);
      const end = minutes(entry.end);
      gaps += Math.max(0, start - latestEnd);
      latestEnd = Math.max(latestEnd, end);
      finish = Math.max(finish, end);
    }
  }
  return {
    conflictCount: conflicts.length,
    occupiedDays: byDay.size,
    gapMinutes: gaps,
    finishMinutes: finish,
  };
}

function makeOption(alternatives, conflicts) {
  const sessions = alternatives.flatMap((alternative) => alternative.sessions);
  return {
    alternatives,
    sessions,
    conflicts,
    ...metrics(sessions, conflicts),
  };
}

function compareOptions(a, b, weeks) {
  return a.conflictCount - b.conflictCount
    || a.occupiedDays - b.occupiedDays
    || a.gapMinutes - b.gapMinutes
    || a.finishMinutes - b.finishMinutes
    || optionSignature(a.sessions, weeks).localeCompare(optionSignature(b.sessions, weeks));
}

function deduplicateAndSort(options, weeks) {
  const unique = new Map();
  for (const option of options) {
    const signature = optionSignature(option.sessions, weeks);
    const prior = unique.get(signature);
    if (!prior || compareOptions(option, prior, weeks) < 0) unique.set(signature, option);
  }
  return [...unique.values()].sort((a, b) => compareOptions(a, b, weeks));
}

function conflictPairs(newAlternative, chosen) {
  const pairs = [];
  for (const left of newAlternative.sessions) {
    for (const alternative of chosen) {
      for (const right of alternative.sessions) {
        if (sessionsOverlap(left, right)) pairs.push({ left, right });
      }
    }
  }
  return pairs;
}

function findUnresolved(code, schedules) {
  const existing = schedules.unmatched?.find((entry) => entry.codigo === code);
  return existing ?? { codigo: code, reason: "no_published_schedule" };
}

/**
 * Select one published alternative for each requested course code.
 * Returns every conflict-free timetable, or only the least-conflicting fallbacks.
 */
export function buildScheduleOptions(selectedCodes, schedules) {
  const payload = Array.isArray(schedules) ? { courses: schedules } : (schedules ?? {});
  const coursesByCode = new Map((payload.courses ?? []).map((course) => [course.codigo, course]));
  const codes = [...new Set(selectedCodes ?? [])];
  const unresolved = [];
  const alternativesByCode = [];

  for (const code of codes) {
    const course = coursesByCode.get(code);
    if (!course || !Array.isArray(course.alternatives) || course.alternatives.length === 0) {
      unresolved.push(findUnresolved(code, payload));
      continue;
    }
    alternativesByCode.push(course.alternatives.map((alternative) => decorateAlternative(course, alternative)));
  }

  if (unresolved.length > 0 || codes.length === 0) return { options: [], unresolved };

  const valid = [];
  function buildValid(index, chosen) {
    if (index === alternativesByCode.length) {
      valid.push(makeOption(chosen, []));
      return;
    }
    for (const alternative of alternativesByCode[index]) {
      if (conflictPairs(alternative, chosen).length === 0) {
        buildValid(index + 1, [...chosen, alternative]);
      }
    }
  }
  buildValid(0, []);
  if (valid.length > 0) return { options: deduplicateAndSort(valid, payload.weeks), unresolved };

  let lowestConflictCount = Infinity;
  const fallback = [];
  function buildFallback(index, chosen, conflicts) {
    if (conflicts.length > lowestConflictCount) return;
    if (index === alternativesByCode.length) {
      if (conflicts.length < lowestConflictCount) {
        lowestConflictCount = conflicts.length;
        fallback.length = 0;
      }
      if (conflicts.length === lowestConflictCount) fallback.push(makeOption(chosen, conflicts));
      return;
    }
    for (const alternative of alternativesByCode[index]) {
      buildFallback(
        index + 1,
        [...chosen, alternative],
        [...conflicts, ...conflictPairs(alternative, chosen)],
      );
    }
  }
  buildFallback(0, [], []);
  return { options: deduplicateAndSort(fallback, payload.weeks), unresolved };
}

function mondayFor(isoDateValue) {
  const parsed = parseIsoDate(isoDateValue);
  const daysSinceMonday = (parsed.getUTCDay() + 6) % 7;
  parsed.setUTCDate(parsed.getUTCDate() - daysSinceMonday);
  return parsed.toISOString().slice(0, 10);
}

function addDays(dateValue, days) {
  const parsed = parseIsoDate(dateValue);
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

/** Return the option sessions that apply during the Monday-Sunday week of isoDateValue. */
export function sessionsForWeek(option, isoDateValue) {
  const weekStart = mondayFor(isoDateValue);
  const weekEnd = addDays(weekStart, 6);
  const requestedRange = dateRange(weekStart, weekEnd);
  return (option?.sessions ?? []).filter((entry) => {
    const details = sessionDetails(entry);
    const sharedRange = overlappingRange(details.range, requestedRange);
    return sharedRange !== null && occursOnWeekday(sharedRange, details.day);
  });
}
