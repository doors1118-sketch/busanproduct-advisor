const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(path.join(__dirname, "../frontend/vendor/app.js"), "utf8");
const renderSource = source.slice(source.indexOf("function renderCandidate(row,"), source.indexOf("function renderComparison(rows)"));

// Minimal DOM double for the real card-rendering function; live browser checks
// cover template integration and visual layout separately.
function element() {
  return {
    textContent: "", innerHTML: "", removed: false, children: [],
    classList: { add() {} },
    appendChild(child) { this.children.push(child); },
    insertAdjacentElement() {},
    addEventListener() {},
    remove() { this.removed = true; },
  };
}

function render(row, index) {
  const elements = new Map();
  const fragment = { querySelector(selector) {
    if (!elements.has(selector)) elements.set(selector, element());
    return elements.get(selector);
  } };
  const context = {
    els: { template: { content: { cloneNode: () => fragment } } },
    document: { createElement: element },
    valueText: (value, fallback = "-") => value == null || !String(value).trim() ? fallback : String(value).trim(),
    basisLevel: () => "근거 확인",
    buildBadges: () => [], splitValues: value => value ? [value] : [],
    truncate: value => value, compactFeatureTags: () => [], evidenceItems: () => [],
    checkItems: () => ["원천자료 확인"], displayProcurementEvidence: () => "등록 근거",
    historySummaryText: () => "과거 수행이력 상세 확인",
  };
  vm.createContext(context);
  vm.runInContext(renderSource, context);
  assert.equal(context.renderCandidate(row, index), fragment);
  return elements;
}

for (const index of [0, 1, 9]) {
  test(`candidate ${index + 1}: no ordinal badge, details and score preserved`, () => {
    const row = Object.freeze({ company_name: "검증업체", review_score: 123, location: "부산광역시", main_products: "비디오프로젝터" });
    const fields = render(row, index);
    assert.equal(fields.get(".rank").removed, true);
    assert.equal(fields.get(".rank").innerHTML, "");
    assert.equal(fields.get(".candidate-name").textContent, row.company_name);
    assert.equal(fields.get(".score-pill").textContent, "123");
    assert.equal(fields.get(".candidate-location").textContent, row.location);
    assert.equal(fields.get(".candidate-primary-products-text").textContent, row.main_products);
    assert.equal(fields.get(".candidate-actions-slot").children[0].children[0].textContent, "과거 수주 이력 보기");
  });
}

test("missing score still displays the existing fallback", () => {
  assert.equal(render({ company_name: "미산정업체" }, 9).get(".score-pill").textContent, "미산정");
});
