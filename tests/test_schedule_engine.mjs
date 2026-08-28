import test from "node:test";
import assert from "node:assert/strict";

import {
  buildScheduleOptions,
  sessionsForWeek,
  sessionsOverlap,
} from "../webui/schedule-engine.mjs";

const session = (overrides = {}) => ({
  day: "monday",
  start: "09:00",
  end: "10:00",
  date_start: "2026-09-07",
  date_end: "2026-09-13",
  ...overrides,
});

const schedules = (courses, unmatched = [], weeks = []) => ({ courses, unmatched, weeks });

test("does not report overlapping clock times from separate weeks as a conflict", () => {
  // Removing date-range comparison would wrongly reject these otherwise separate sessions.
  assert.equal(
    sessionsOverlap(
      session({ date_start: "2026-09-07", date_end: "2026-09-13" }),
      session({ date_start: "2026-09-14", date_end: "2026-09-20" }),
    ),
    false,
  );
});

test("reports sessions on the same day with intersecting dates and times as a conflict", () => {
  // Comparing only dates or only times would fail to identify this real collision.
  assert.equal(
    sessionsOverlap(
      session({ start: "09:00", end: "10:30" }),
      session({ start: "10:00", end: "11:00" }),
    ),
    true,
  );
});

test("does not report a collision when overlapping ranges contain no declared weekday occurrence", () => {
  // Range-only comparison would falsely turn a Tuesday-to-Friday overlap into a Monday class collision.
  assert.equal(
    sessionsOverlap(
      session({ date_start: "2026-09-08", date_end: "2026-09-09" }),
      session({ date_start: "2026-09-09", date_end: "2026-09-11" }),
    ),
    false,
  );
});

test("rejects calendar dates that are not real ISO dates or ordered ranges", () => {
  // Accepting impossible or reversed dates would make semester conflict results undefined.
  assert.throws(
    () => sessionsOverlap(session({ date_start: "2026-02-29" }), session()),
    TypeError,
  );
  assert.throws(
    () => sessionsOverlap(session({ date_start: "2026-09-14", date_end: "2026-09-13" }), session()),
    TypeError,
  );
});

test("rejects invalid clock minutes, clock hours, and non-positive durations", () => {
  // Permitting malformed or zero-length times would corrupt both conflict and layout calculations.
  assert.throws(() => sessionsOverlap(session({ start: "09:60" }), session()), TypeError);
  assert.throws(() => sessionsOverlap(session({ end: "24:00" }), session()), TypeError);
  assert.throws(() => sessionsOverlap(session({ start: "10:00", end: "10:00" }), session()), TypeError);
});

test("builds every conflict-free selection across course alternatives", () => {
  // Stopping after the first compatible group would hide a valid choice from the user.
  const result = buildScheduleOptions(["A", "B"], schedules([
    {
      codigo: "A",
      alternatives: [
        { group: "A1", sessions: [session({ start: "09:00", end: "10:00" })] },
        { group: "A2", sessions: [session({ start: "11:00", end: "12:00" })] },
      ],
    },
    {
      codigo: "B",
      alternatives: [
        { group: "B1", sessions: [session({ start: "10:00", end: "11:00" })] },
        { group: "B2", sessions: [session({ start: "13:00", end: "14:00" })] },
      ],
    },
  ]));

  assert.deepEqual(
    result.options.map((option) => option.alternatives.map((alternative) => alternative.group)),
    [["A1", "B1"], ["A2", "B1"], ["A2", "B2"], ["A1", "B2"]],
  );
  assert.deepEqual(result.options.map((option) => option.conflictCount), [0, 0, 0, 0]);
  assert.deepEqual(result.unresolved, []);
});

test("keeps every valid branch when another group choice conflicts", () => {
  // Returning after the first valid branch or discarding siblings would hide valid schedules.
  const result = buildScheduleOptions(["A", "B"], schedules([
    {
      codigo: "A",
      alternatives: [
        { group: "A1", sessions: [session({ start: "09:00", end: "11:00" })] },
        { group: "A2", sessions: [session({ start: "12:00", end: "13:00" })] },
      ],
    },
    {
      codigo: "B",
      alternatives: [
        { group: "B1", sessions: [session({ start: "10:00", end: "12:00" })] },
        { group: "B2", sessions: [session({ start: "13:00", end: "14:00" })] },
      ],
    },
  ]));

  assert.deepEqual(
    result.options.map((option) => option.alternatives.map((alternative) => alternative.group)),
    [["A2", "B1"], ["A2", "B2"], ["A1", "B2"]],
  );
  assert.deepEqual(result.options.map((option) => option.conflictCount), [0, 0, 0]);
});

test("deduplicates alternatives that produce the same effective timetable", () => {
  // Keeping both group labels despite identical sessions would show duplicate schedules to choose from.
  const result = buildScheduleOptions(["A"], schedules([{
    codigo: "A",
    alternatives: [
      { group: "A1", sessions: [session()] },
      { group: "A2", sessions: [session()] },
    ],
  }]));

  assert.equal(result.options.length, 1);
  assert.deepEqual(result.options[0].sessions, [
    { ...session(), codigo: "A", group: "A1" },
  ]);
});

test("deduplicates the same weekly timetable expressed as continuous or segmented ranges", () => {
  // Raw publication segments must not create duplicate choices when every actual class occurrence is identical.
  const result = buildScheduleOptions(["A"], schedules([{
    codigo: "A",
    alternatives: [
      {
        group: "A1",
        sessions: [session({ date_start: "2026-09-07", date_end: "2026-09-27" })],
      },
      {
        group: "A2",
        sessions: [
          session({ date_start: "2026-09-07", date_end: "2026-09-13" }),
          session({ date_start: "2026-09-14", date_end: "2026-09-27" }),
        ],
      },
    ],
  }], [], ["2026-09-07", "2026-09-14", "2026-09-21"]));

  assert.equal(result.options.length, 1);
  assert.equal(result.options[0].alternatives[0].group, "A1");
});

test("keeps alternatives whose effective timetable differs in at least one declared week", () => {
  // Matching clock times are still distinct choices when one group stops before a declared teaching week.
  const result = buildScheduleOptions(["A"], schedules([{
    codigo: "A",
    alternatives: [
      {
        group: "A1",
        sessions: [session({ date_start: "2026-09-07", date_end: "2026-09-27" })],
      },
      {
        group: "A2",
        sessions: [session({ date_start: "2026-09-07", date_end: "2026-09-20" })],
      },
    ],
  }], [], ["2026-09-07", "2026-09-14", "2026-09-21"]));

  assert.equal(result.options.length, 2);
  assert.deepEqual(
    result.options.map((option) => option.alternatives[0].group).sort(),
    ["A1", "A2"],
  );
});

test("returns only minimum-conflict alternatives when no conflict-free selection exists", () => {
  // Returning arbitrary conflicting schedules would obscure the best available fallback.
  const result = buildScheduleOptions(["A", "B"], schedules([
    {
      codigo: "A",
      alternatives: [
        {
          group: "A1",
          sessions: [
            session({ start: "09:00", end: "11:00" }),
            session({ start: "14:00", end: "16:00" }),
          ],
        },
        { group: "A2", sessions: [session({ start: "09:00", end: "11:00" })] },
      ],
    },
    {
      codigo: "B",
      alternatives: [
        {
          group: "B1",
          sessions: [
            session({ start: "10:00", end: "12:00" }),
            session({ start: "14:30", end: "15:30" }),
          ],
        },
        { group: "B2", sessions: [session({ start: "10:00", end: "12:00" })] },
      ],
    },
  ]));

  assert.deepEqual(
    result.options.map((option) => option.alternatives.map((alternative) => alternative.group)),
    [["A2", "B2"], ["A1", "B2"], ["A2", "B1"]],
  );
  assert.deepEqual(result.options.map((option) => option.conflictCount), [1, 1, 1]);
});

test("keeps selected courses without published sessions unresolved", () => {
  // Treating an absent timetable as an empty alternative would falsely advertise a valid schedule.
  const result = buildScheduleOptions(["A", "MISSING"], schedules([
    { codigo: "A", alternatives: [{ group: "A1", sessions: [session()] }] },
  ], [{ codigo: "MISSING", nombre: "Pending timetable", reason: "no_published_schedule" }]));

  assert.deepEqual(result.options, []);
  assert.deepEqual(result.unresolved, [
    { codigo: "MISSING", nombre: "Pending timetable", reason: "no_published_schedule" },
  ]);
});

test("returns only sessions whose publication range intersects the requested week", () => {
  // Ignoring a session's end date would render expired classes in later weeks.
  const option = {
    sessions: [
      session({ date_start: "2026-09-07", date_end: "2026-09-13" }),
      session({ day: "tuesday", start: "12:00", end: "13:00", date_start: "2026-09-14", date_end: "2026-09-20" }),
    ],
  };

  assert.deepEqual(
    sessionsForWeek(option, "2026-09-16"),
    [session({ day: "tuesday", start: "12:00", end: "13:00", date_start: "2026-09-14", date_end: "2026-09-20" })],
  );
});

test("does not render a session when its weekday is absent from the requested published range", () => {
  // A range-only weekly filter would render this Monday session in a Tuesday-Wednesday publication span.
  assert.deepEqual(
    sessionsForWeek({ sessions: [session({ date_start: "2026-09-08", date_end: "2026-09-09" })] }, "2026-09-09"),
    [],
  );
});
