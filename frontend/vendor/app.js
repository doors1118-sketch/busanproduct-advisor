const params = new URLSearchParams(window.location.search);
const API_BASE_URL =
  params.get("api") ||
  (window.location.protocol === "file:" || window.location.port === "5177" ? "http://127.0.0.1:8001" : "");
const MONITORING_API_BASE_URL = (params.get("monitoring") || "https://busanproduct.co.kr").replace(/\/$/, "");

const DISPLAY_LIMIT = 10;

function todayKstDateText() {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
    .format(new Date())
    .replace(/\. /g, "-")
    .replace(".", "");
}

const els = {
  form: document.querySelector("#search-form"),
  input: document.querySelector("#query-input"),
  budget: document.querySelector("#budget-input"),
  limit: document.querySelector("#limit-input"),
  button: document.querySelector("#search-button"),
  clear: document.querySelector("#clear-button"),
  apiState: document.querySelector("#api-state"),
  dataDate: document.querySelector("#data-date"),
  metricTotalAmount: document.querySelector("#metric-total-amount"),
  metricLocalAmount: document.querySelector("#metric-local-amount"),
  metricOverall: document.querySelector("#metric-overall"),
  metricSectorMix: document.querySelector("#metric-sector-mix"),
  metricGenerated: document.querySelector("#metric-generated"),
  metricBusanGroup: document.querySelector("#metric-busan-group"),
  metricNationalGroup: document.querySelector("#metric-national-group"),
  metricCompanyDb: document.querySelector("#metric-company-db"),
  summaryCount: document.querySelector("#summary-count"),
  summaryDesc: document.querySelector("#summary-desc"),
  summaryCondition: document.querySelector("#summary-condition"),
  summaryRoute: document.querySelector("#summary-route"),
  summaryDownload: document.querySelector("#summary-download"),
  routeTitle: document.querySelector("#route-title"),
  routeBadges: document.querySelector("#route-badges"),
  routePrimary: document.querySelector("#route-primary"),
  routeRequired: document.querySelector("#route-required"),
  routeRanking: document.querySelector("#route-ranking"),
  routeOptions: document.querySelector("#route-options"),
  routeNotice: document.querySelector("#route-notice"),
  downloadLink: document.querySelector("#download-link"),
  candidateList: document.querySelector("#candidate-list"),
  compareBody: document.querySelector("#compare-body"),
  visibleCount: document.querySelector("#visible-count"),
  template: document.querySelector("#candidate-template"),
  leakageList: document.querySelector("#leakage-list"),
  leakageUpdated: document.querySelector("#leakage-updated"),
};

let lastPayload = null;
let lastQuery = "";

function setDefaultDataDate() {
  if (els.dataDate) els.dataDate.textContent = `기준일 ${todayKstDateText()}`;
}

function valueText(value, fallback = "-") {
  if (value === null || value === undefined) return fallback;
  const normalized = String(value).trim();
  return normalized || fallback;
}

function escapeHtml(value) {
  return valueText(value, "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function truncate(value, max = 140) {
  const normalized = valueText(value, "");
  if (normalized.length <= max) return normalized;
  return `${normalized.slice(0, max - 1)}…`;
}

function splitValues(value) {
  return valueText(value, "")
    .split(/\s*\|\s*|\s*\/\s*|\n+|,\s*/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, arr) => arr.indexOf(item) === index);
}

function isPositive(value) {
  const normalized = valueText(value, "").toLowerCase();
  if (!normalized) return false;
  return !/(없음|미확인|근거 없음|확인 필요|not found|unknown|unavailable|false|^0$)/i.test(normalized);
}

function firstPositive(...values) {
  for (const value of values) {
    if (isPositive(value)) return valueText(value, "");
  }
  return "";
}

function toneFor(value) {
  const normalized = valueText(value, "");
  if (!normalized) return "warn";
  if (/(모두 충족|충족|일치|등록|보유|확인|유효|active|valid|true)/i.test(normalized)) return "good";
  if (/(일부 충족|확인 필요|미확인|근거 없음|주의|없음|unknown|not found)/i.test(normalized)) return "warn";
  return "info";
}

function tag(text, tone = "neutral") {
  const span = document.createElement("span");
  span.className = `tag ${tone}`;
  span.textContent = text;
  return span;
}

function directEvidence(row) {
  return firstPositive(
    row.direct_production_match,
    row.direct_production_certificate_products,
    row.direct_production_summary,
    row.direct_production_certificate_status,
  );
}

function masEvidence(row) {
  return firstPositive(row.mas_match, row.mas_product_summary, row.mas_status_label);
}

function shoppingEvidence(row) {
  return firstPositive(row.shopping_mall_match, row.shopping_mall_product_summary, row.shopping_mall_status_label);
}

function constructionEvidence(row) {
  return firstPositive(row.construction_capacity_match, row.construction_capacity_summary, row.construction_license_match);
}

function policyEvidence(row) {
  return firstPositive(
    row.policy_company_labels,
    row.certified_product_labels,
    row.certified_product_summary,
    row.sme_competition_product_label,
    row.cooperative_purchase_route_label,
  );
}

function conditionText(row) {
  const type = valueText(row.condition_match_type, "후보 표시");
  const summary = valueText(row.condition_match_summary, "");
  return summary ? `${type} · ${summary}` : type;
}

function basisLevel(row) {
  const condition = valueText(row.condition_match_type, "");
  if (condition.includes("모두 충족")) return "조건 충족";
  if (condition.includes("일부 충족")) return "일부 충족";
  if (condition.includes("근거 부족")) return "확인 필요";
  if (isPositive(row.purchase_route_fit_summary) || isPositive(row.requested_item_evidence_summary)) return "근거 확인";
  return "후보";
}

function buildBadges(row) {
  const badges = [];
  const status = valueText(row.business_status_label || row.business_status, "");
  if (status) badges.push(tag(status, /정상|active|fresh/i.test(status) ? "good" : "warn"));
  if (directEvidence(row)) badges.push(tag("직접생산", "good"));
  if (masEvidence(row)) badges.push(tag("MAS", "info"));
  if (shoppingEvidence(row)) badges.push(tag("종합쇼핑몰", "info"));
  if (constructionEvidence(row)) badges.push(tag("면허·시공능력", "good"));
  if (policyEvidence(row)) badges.push(tag("정책·인증", "good"));
  if (!badges.length) badges.push(tag("근거 확인 필요", "warn"));
  return badges.slice(0, 8);
}

function evidenceItems(row) {
  return [
    ["조건 충족", conditionText(row), toneFor(row.condition_match_type)],
    ["품목·검색 근거", firstPositive(row.requested_item_evidence_summary, row.matched_query_label, row.main_products) || "요청 품목 근거 확인 필요", toneFor(row.requested_item_evidence_summary)],
    ["구매수단 적합성", valueText(row.purchase_route_fit_summary, "지역업체 구매 지원 근거는 별도 확인 필요"), toneFor(row.purchase_route_fit_summary)],
    ["직접생산", directEvidence(row) || "직접생산 근거 없음 또는 확인 필요", directEvidence(row) ? "good" : "warn"],
    ["MAS/종합쇼핑몰", [masEvidence(row), shoppingEvidence(row)].filter(Boolean).join(" · ") || "등록 근거 없음 또는 확인 필요", masEvidence(row) || shoppingEvidence(row) ? "good" : "warn"],
    ["면허·시공능력", constructionEvidence(row) || firstPositive(row.license_or_business_type) || "면허·시공능력 확인 필요", constructionEvidence(row) ? "good" : "info"],
    ["정책기업·인증", policyEvidence(row) || "해당 근거 없음 또는 확인 필요", policyEvidence(row) ? "good" : "info"],
  ];
}

function checkItems(row) {
  const checks = splitValues(row.recommended_checks);
  if (!directEvidence(row) && /중기간|직접생산/.test(valueText(row.sme_competition_product_label, ""))) {
    checks.push("중기간 경쟁제품이면 직접생산확인증명서 세부품명과 유효기간 확인");
  }
  if (!masEvidence(row) && !shoppingEvidence(row)) {
    checks.push("조달청 종합쇼핑몰 또는 MAS 등록 여부 별도 확인");
  }
  if (!constructionEvidence(row) && /공사|면허|시공/.test(valueText(row.contract_review_types, ""))) {
    checks.push("공고 면허, 주력분야, 시공능력평가금액 기준연도 확인");
  }
  checks.push("최종 계약 가능 여부는 공고 전 원천자료로 재확인");
  return [...new Set(checks)].slice(0, 6);
}

function formatKrw(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "";
  if (numeric >= 100000000) return `${(numeric / 100000000).toFixed(1)}억원`;
  return `${Math.round(numeric / 10000).toLocaleString("ko-KR")}만원`;
}

function formatRate(value) {
  if (value === "" || value === null || value === undefined) return "";
  const numeric = Number(String(value).replace("%", ""));
  if (!Number.isFinite(numeric)) return valueText(value, "");
  return `${numeric.toFixed(1)}%`;
}

function formatWonCompact(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  if (Math.abs(numeric) >= 1000000000000) return `${(numeric / 1000000000000).toFixed(1)}조`;
  if (Math.abs(numeric) >= 100000000) return `${Math.round(numeric / 100000000).toLocaleString("ko-KR")}억`;
  return `${Math.round(numeric).toLocaleString("ko-KR")}원`;
}

function sourceDate(rows) {
  for (const row of rows) {
    const date = valueText(row.source_refreshed_at, "");
    if (date) return date;
  }
  return "";
}

function routeStatusLabel(status) {
  if (status === "candidate_found") return "후보 근거 있음";
  if (status === "policy_only") return "품목정책 확인";
  if (status === "reference_only") return "참고자료";
  return "확인 필요";
}

function routeStatusTone(status) {
  if (status === "candidate_found") return "good";
  if (status === "policy_only") return "info";
  if (status === "reference_only") return "neutral";
  return "warn";
}

function renderRouteOptions(cards) {
  if (!els.routeOptions) return;
  els.routeOptions.innerHTML = "";
  if (!cards.length) {
    els.routeOptions.classList.add("is-empty");
    return;
  }
  els.routeOptions.classList.remove("is-empty");
  cards.slice(0, 5).forEach((card) => {
    const article = document.createElement("article");
    article.className = "route-option-card";
    const nextActions = Array.isArray(card.next_actions) ? card.next_actions.filter(Boolean).slice(0, 3) : [];
    const checks = Array.isArray(card.required_checks) ? card.required_checks.filter(Boolean).slice(0, 3) : [];
    const status = valueText(card.status, "needs_check");
    const detailItems = nextActions.length ? nextActions : checks;
    article.innerHTML = `
      <div class="route-option-head">
        <strong>${escapeHtml(valueText(card.label, "구매방식 확인"))}</strong>
        <span class="tag ${routeStatusTone(status)}">${escapeHtml(routeStatusLabel(status))}</span>
      </div>
      <p>${escapeHtml(valueText(card.reason, "원천 DB 근거를 확인해야 합니다."))}</p>
      ${card.practical_note ? `<em>${escapeHtml(card.practical_note)}</em>` : ""}
      ${
        detailItems.length
          ? `<ul>${detailItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : ""
      }
    `;
    els.routeOptions.appendChild(article);
  });
}

function renderRouteGuide(payload) {
  const guide = payload?.purchase_route_guidance || {};
  const primary = guide.primary_route || {};
  const cards = Array.isArray(guide.route_cards) ? guide.route_cards : [];
  const badges = Array.isArray(guide.badges) ? guide.badges : [];

  els.routeTitle.textContent = guide.title || primary.label || "구매방식 확인 필요";
  els.routePrimary.textContent = primary.label
    ? `${primary.label}: ${[primary.reason, primary.practical_note].filter(Boolean).join(" ")}`
    : "입력 품목 기준으로 구매방식을 확인해야 합니다.";
  els.routeRequired.textContent = (guide.required_checks || primary.required_checks || ["원천자료 확인"]).join(" · ");
  els.routeRanking.textContent = (guide.ranking_basis || ["조건 일치", "구매 지원 근거", "영업상태", "정책·인증"]).join(" · ");
  els.routeNotice.textContent =
    guide.legal_notice || "구매방식 안내는 후보 정보입니다. 최종 계약 가능 여부와 법령 해석은 별도 검토가 필요합니다.";
  renderRouteOptions(cards);

  els.routeBadges.innerHTML = "";
  if (badges.length) {
    badges.forEach((item) => els.routeBadges.appendChild(tag(item.label || "확인 필요", item.tone || "info")));
  } else if (cards.length) {
    cards.slice(0, 4).forEach((item) => els.routeBadges.appendChild(tag(item.label || item.route_id, item.status === "candidate_found" ? "info" : "warn")));
  } else {
    els.routeBadges.appendChild(tag("확인 필요", "warn"));
  }
}

function renderSummary(payload, rows) {
  const count = Number(payload?.count || rows.length || 0);
  const conditionLabels = rows.map((row) => valueText(row.condition_match_type, ""));
  const all = conditionLabels.filter((label) => /모두 충족|조건 충족/.test(label)).length;
  const evidenceChecked = conditionLabels.filter((label) => /품목근거 확인|공사면허 확인|근거 확인|후보 표시/.test(label)).length;
  const partial = conditionLabels.filter((label) => label.includes("일부 충족")).length;
  const needs = conditionLabels.filter((label) => /근거 부족|확인 필요/.test(label)).length;
  const routeEvidence = rows.filter((row) => directEvidence(row) || masEvidence(row) || shoppingEvidence(row) || policyEvidence(row)).length;

  els.summaryCount.textContent = `${count.toLocaleString("ko-KR")}개`;
  els.summaryDesc.textContent = count
    ? `화면에는 상위 ${Math.min(DISPLAY_LIMIT, rows.length)}개를 표시합니다. 전체 후보는 XLSX로 내려받아 검토하세요.`
    : "조건에 맞는 후보가 없습니다. 검색어를 품목명 또는 면허명 중심으로 바꿔보세요.";
  els.summaryCondition.textContent = all
    ? `조건 충족 ${all}개`
    : evidenceChecked
      ? `근거 확인 ${evidenceChecked}개`
      : partial
        ? `일부 충족 ${partial}개`
        : needs
          ? `확인 필요 ${needs}개`
          : "-";
  els.summaryRoute.textContent = routeEvidence ? `근거 있음 ${routeEvidence}개` : "확인 필요";
  els.summaryDownload.textContent = count ? "가능" : "대기";
}

function renderCandidate(row, index) {
  const node = els.template.content.cloneNode(true);
  node.querySelector(".rank").textContent = `후보 ${index + 1}`;
  node.querySelector(".candidate-name").textContent = valueText(row.company_name, "업체명 미확인");
  node.querySelector(".candidate-location").textContent = [row.location, row.detail_address].map((item) => valueText(item, "")).filter(Boolean).join(" · ") || "소재지 확인 필요";
  node.querySelector(".basis-level").textContent = basisLevel(row);
  node.querySelector(".score-pill").textContent = row.review_score ? `검토점수 ${row.review_score}` : "점수 미산정";

  const badgeRow = node.querySelector(".card-badges");
  buildBadges(row).forEach((item) => badgeRow.appendChild(item));

  const grid = node.querySelector(".evidence-grid");
  evidenceItems(row).forEach(([label, value, tone]) => {
    const div = document.createElement("div");
    div.className = `evidence-item ${tone}`;
    div.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(truncate(value, 190))}</strong>`;
    grid.appendChild(div);
  });

  const checkList = node.querySelector(".check-list");
  checkItems(row).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    checkList.appendChild(li);
  });

  node.querySelector(".main-products").textContent = truncate(splitValues(row.main_products).join(", "), 220);
  node.querySelector(".licenses").textContent = truncate(splitValues(row.license_or_business_type).join(", "), 260);
  node.querySelector(".procurement-evidence").textContent = truncate(
    [directEvidence(row), masEvidence(row), shoppingEvidence(row), policyEvidence(row)].filter(Boolean).join(" / ") || "조달 근거 확인 필요",
    260,
  );
  node.querySelector(".checks").textContent = truncate(checkItems(row).join(" / "), 260);

  return node;
}

function renderComparison(rows) {
  els.compareBody.innerHTML = "";
  if (!rows.length) {
    els.compareBody.innerHTML = '<tr><td colspan="7">조회 후 비교표가 표시됩니다.</td></tr>';
    return;
  }

  rows.slice(0, DISPLAY_LIMIT).forEach((row) => {
    const tr = document.createElement("tr");
    const route = valueText(row.purchase_route_fit_summary, "확인 필요");
    const mall = [masEvidence(row), shoppingEvidence(row)].filter(Boolean).join(" / ") || "확인 필요";
    tr.innerHTML = `
      <td><strong>${escapeHtml(valueText(row.company_name))}</strong><br><span class="muted">${escapeHtml(valueText(row.location, ""))}</span></td>
      <td>${escapeHtml(conditionText(row))}</td>
      <td>${escapeHtml(truncate(route, 120))}</td>
      <td>${escapeHtml(truncate(directEvidence(row) || "확인 필요", 100))}</td>
      <td>${escapeHtml(truncate(mall, 120))}</td>
      <td>${escapeHtml(truncate(constructionEvidence(row) || valueText(row.license_or_business_type, "확인 필요"), 140))}</td>
      <td>${escapeHtml(truncate(checkItems(row).join(" / "), 160))}</td>
    `;
    els.compareBody.appendChild(tr);
  });
}

function setDownloadState(enabled) {
  if (!enabled) {
    els.downloadLink.classList.add("disabled");
    els.downloadLink.setAttribute("aria-disabled", "true");
    return;
  }
  els.downloadLink.classList.remove("disabled");
  els.downloadLink.setAttribute("aria-disabled", "false");
}

function renderPayload(payload) {
  const rows = Array.isArray(payload?.rows) ? payload.rows : [];
  lastPayload = payload;
  els.candidateList.innerHTML = "";

  if (!rows.length) {
    els.candidateList.innerHTML = `
      <article class="empty-panel">
        <strong>조건에 맞는 후보가 없습니다.</strong>
        <span>예: 품목명, 세부품명, 면허명, 업종명을 더 구체적으로 입력해 보세요.</span>
      </article>
    `;
  } else {
    rows.slice(0, DISPLAY_LIMIT).forEach((row, index) => els.candidateList.appendChild(renderCandidate(row, index)));
  }

  els.visibleCount.textContent = `${Math.min(DISPLAY_LIMIT, rows.length)}개 표시`;
  const date = sourceDate(rows);
  if (date) els.dataDate.textContent = `DB 기준 ${date}`;
  renderSummary(payload, rows);
  renderRouteGuide(payload);
  renderComparison(rows);
  setDownloadState(rows.length > 0);
}

async function search(query) {
  lastQuery = query;
  els.button.disabled = true;
  els.button.textContent = "조회 중";
  els.apiState.textContent = "조회 중";
  els.apiState.className = "state-pill muted";

  const requestParams = new URLSearchParams({
    q: query,
    region: "부산",
    limit: valueText(els.limit.value, "30"),
    include_product_policy: "true",
  });
  const budget = Number(els.budget.value || 0);
  if (Number.isFinite(budget) && budget > 0) requestParams.set("budget_krw", String(Math.round(budget)));

  try {
    const response = await fetch(`${API_BASE_URL}/vendor-recommendations/search?${requestParams.toString()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    renderPayload(payload);
    els.apiState.textContent = "API 연결됨";
    els.apiState.className = "state-pill ok";
  } catch (error) {
    els.apiState.textContent = "API 오류";
    els.apiState.className = "state-pill warn";
    els.candidateList.innerHTML = `
      <article class="empty-panel">
        <strong>API 응답을 불러오지 못했습니다.</strong>
        <span>${escapeHtml(error.message || "네트워크 상태와 API 서버를 확인하세요.")}</span>
      </article>
    `;
  } finally {
    els.button.disabled = false;
    els.button.textContent = "후보 조회";
  }
}

function downloadXlsx() {
  if (!lastPayload || !lastQuery) return;
  const requestParams = new URLSearchParams({
    q: lastQuery,
    region: "부산",
    limit: "100",
    include_product_policy: "true",
  });
  const budget = Number(els.budget.value || 0);
  if (Number.isFinite(budget) && budget > 0) requestParams.set("budget_krw", String(Math.round(budget)));
  window.location.href = `${API_BASE_URL}/vendor-recommendations/search.xlsx?${requestParams.toString()}`;
}

async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    els.apiState.textContent = "API 연결됨";
    els.apiState.className = "state-pill ok";
  } catch {
    els.apiState.textContent = "API 미연결";
    els.apiState.className = "state-pill warn";
  }
}

function findRateValue(obj) {
  if (!obj || typeof obj !== "object") return "";
  for (const key of ["수주율", "rate", "award_rate", "local_rate"]) {
    if (obj[key] !== undefined && obj[key] !== null && obj[key] !== "") return obj[key];
  }
  return "";
}

function findValueByKeys(obj, keys) {
  if (!obj || typeof obj !== "object") return "";
  for (const key of keys) {
    if (obj[key] !== undefined && obj[key] !== null && obj[key] !== "") return obj[key];
  }
  return "";
}

function findNestedObject(data, paths) {
  for (const path of paths) {
    let current = data;
    for (const key of path) current = current && current[key];
    if (current && typeof current === "object") return current;
  }
  return null;
}

function findNestedRate(data, paths) {
  for (const path of paths) {
    let current = data;
    for (const key of path) current = current && current[key];
    const rate = findRateValue(current);
    if (rate !== "") return rate;
  }
  return "";
}

function buildSectorMix(data, totalAmount) {
  const bySector = data?.["2_분야별"];
  const total = Number(totalAmount);
  if (!bySector || typeof bySector !== "object" || !Number.isFinite(total) || total <= 0) return "";
  const values = ["공사", "용역", "물품", "쇼핑몰"]
    .reduce((acc, label) => {
      const amount = Number(findValueByKeys(bySector[label], ["발주액", "total_amount", "contract_amount"]));
      if (Number.isFinite(amount)) acc[label] = `${label} ${((amount / total) * 100).toFixed(1)}%`;
      return acc;
    }, {});
  const rows = [
    [values["공사"], values["용역"]].filter(Boolean).join(" · "),
    [values["물품"], values["쇼핑몰"]].filter(Boolean).join(" · "),
  ].filter(Boolean);
  return rows.map((row) => `<span class="sector-row">${row}</span>`).join("");
}

async function loadMonitoringSummary() {
  try {
    const response = await fetch(`${MONITORING_API_BASE_URL}/api/summary`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const overallObject = findNestedObject(data, [["1_전체"], ["summary"], ["overall"], ["전체"]]);
    const overall = findRateValue(overallObject);
    const totalAmount = findValueByKeys(overallObject, ["발주액", "총계약액", "total_amount", "contract_amount"]);
    const localAmount = findValueByKeys(overallObject, ["수주액", "지역업체 수주액", "local_amount", "award_amount"]);
    const sectorMix = buildSectorMix(data, totalAmount);
    const busanGroup = findNestedRate(data, [["3_그룹별", "부산광역시 및 소속기관"], ["by_group", "부산광역시 및 소속기관"]]);
    const nationalGroup = findNestedRate(data, [["3_그룹별", "정부 및 국가공공기관"], ["by_group", "정부 및 국가공공기관"]]);
    if (totalAmount) els.metricTotalAmount.textContent = formatWonCompact(totalAmount);
    if (localAmount) els.metricLocalAmount.textContent = formatWonCompact(localAmount);
    if (overall) els.metricOverall.textContent = formatRate(overall);
    if (sectorMix) els.metricSectorMix.innerHTML = sectorMix;
    if (busanGroup) els.metricBusanGroup.textContent = formatRate(busanGroup);
    if (nationalGroup) els.metricNationalGroup.textContent = formatRate(nationalGroup);
    if (data.generated_at) els.metricGenerated.textContent = `생성 ${data.generated_at}`;
  } catch {
    els.metricTotalAmount.textContent = "연결 필요";
    els.metricLocalAmount.textContent = "-";
    els.metricOverall.textContent = "-";
    els.metricSectorMix.textContent = "모니터링 API 확인 필요";
    els.metricGenerated.textContent = "모니터링 API 확인 필요";
  }
}

async function loadShoppingLeakage() {
  try {
    const response = await fetch(`${MONITORING_API_BASE_URL}/api/leakage/shopping`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const items = data["유출품목"] || data["쇼핑몰 유출품목"] || data.items || [];
    els.leakageList.innerHTML = "";
    if (!Array.isArray(items) || !items.length) throw new Error("empty");
    items.slice(0, 5).forEach((item) => {
      const name = item["품목명"] || item.item_name || item.product_name || "품목명 미확인";
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = name;
      button.addEventListener("click", () => {
        els.input.value = name;
        search(name);
      });
      els.leakageList.appendChild(button);
    });
    els.leakageUpdated.textContent = data.generated_at || "연결됨";
  } catch {
    els.leakageList.innerHTML = '<p class="muted">쇼핑몰 유출품목 API 연결 확인 필요</p>';
    els.leakageUpdated.textContent = "미연결";
  }
}

document.querySelectorAll(".sample-row button").forEach((button) => {
  button.addEventListener("click", () => {
    els.input.value = button.dataset.query || button.textContent.trim();
    els.input.focus();
  });
});

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = els.input.value.trim();
  if (!query) {
    els.input.focus();
    return;
  }
  search(query);
});

els.clear.addEventListener("click", () => {
  els.input.value = "";
  els.budget.value = "";
  lastPayload = null;
  lastQuery = "";
  renderPayload({ rows: [], count: 0, purchase_route_guidance: {} });
});

els.downloadLink.addEventListener("click", (event) => {
  event.preventDefault();
  if (els.downloadLink.classList.contains("disabled")) return;
  downloadXlsx();
});

setDefaultDataDate();
checkHealth();
loadMonitoringSummary();
loadShoppingLeakage();

const initialQuery = params.get("q");
if (initialQuery) {
  els.input.value = initialQuery;
  search(initialQuery);
}
