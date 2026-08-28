const test = require("node:test");
const assert = require("node:assert/strict");

const { versionedAssetUrl } = require("../webui/url-version.js");

test("adds a dataset version to a plain asset URL", () => {
  assert.equal(
    versionedAssetUrl("data/icai_equivalencias.csv", "icai-excel-2026-08-28"),
    "data/icai_equivalencias.csv?v=icai-excel-2026-08-28",
  );
});

test("preserves existing query parameters when adding a dataset version", () => {
  assert.equal(
    versionedAssetUrl("data/catalog.json?view=full", "v2"),
    "data/catalog.json?view=full&v=v2",
  );
});
