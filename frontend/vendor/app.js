const params = new URLSearchParams(window.location.search);
const DEFAULT_API_BASE_URL = (() => {
  if (window.location.protocol === "file:" || window.location.port === "5177") return "http://127.0.0.1:8001";
  if (window.location.port === "8001") return "";
  return "/advisor-api";
})();
const API_BASE_URL =
  params.get("api") ||
  DEFAULT_API_BASE_URL;
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
  itemSelectionPopover: document.querySelector("#item-selection-popover"),
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
  summaryDownloadCard: document.querySelector("#summary-download-card"),
  summaryDownload: document.querySelector("#summary-download"),
  routeTitle: document.querySelector("#route-title"),
  routeBadges: document.querySelector("#route-badges"),
  routeDecisionPanel: document.querySelector("#route-decision-panel"),
  routeOptions: document.querySelector("#route-options"),
  itemPolicyPanel: document.querySelector("#item-policy-panel"),
  routeNotice: document.querySelector("#route-notice"),
  downloadLink: document.querySelector("#download-link"),
  candidateList: document.querySelector("#candidate-list"),
  compareBody: document.querySelector("#compare-body"),
  visibleCount: document.querySelector("#visible-count"),
  template: document.querySelector("#candidate-template"),
  leakageList: document.querySelector("#leakage-list"),
  leakageUpdated: document.querySelector("#leakage-updated"),
  historyModal: document.querySelector("#history-modal"),
  historyModalTitle: document.querySelector("#history-modal-title"),
  historyModalMeta: document.querySelector("#history-modal-meta"),
  historyModalBody: document.querySelector("#history-modal-body"),
  historyModalClose: document.querySelector("#history-modal-close"),
};

let lastPayload = null;
let lastQuery = "";

function setDefaultDataDate() {
  if (els.dataDate) els.dataDate.textContent = `DB 기준 ${todayKstDateText()}`;
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
  );
}

function cleanEvidenceValue(value) {
  return valueText(value, "")
    .replace(/\bvalid\s*~?\s*\d{4}-\d{2}-\d{2}/gi, "")
    .replace(/\bactive\b/gi, "")
    .replace(/win_win_cooperation_product/gi, "상생협력제품")
    .replace(/_/g, " ")
    .replace(/\s{2,}/g, " ")
    .replace(/\s*\/\s*$/g, "")
    .trim();
}

function displayEvidenceList(value, fallback = "") {
  const seen = new Set();
  const items = splitValues(cleanEvidenceValue(value))
    .map((item) => item
      .replace(/^직접생산\s*일치:\s*/g, "")
      .replace(/^MAS\s*일치:\s*/g, "")
      .replace(/^종합쇼핑몰\s*일치:\s*/g, "")
      .replace(/\s{2,}/g, " ")
      .trim())
    .filter((item) => {
      if (!item || seen.has(item)) return false;
      seen.add(item);
      return true;
    });
  return items.length ? items.slice(0, 4).join(" · ") : fallback;
}

function displayCertifiedLabels(row) {
  return displayEvidenceList(row.certified_product_labels);
}

function displayDirectEvidence(row) {
  return displayEvidenceList(directEvidence(row));
}

function displayMasEvidence(row) {
  return displayEvidenceList(masEvidence(row));
}

function displayShoppingEvidence(row) {
  return displayEvidenceList(shoppingEvidence(row));
}

function displayProcurementEvidence(row) {
  return [
    displayDirectEvidence(row),
    displayMasEvidence(row),
    displayShoppingEvidence(row),
    historyEvidence(row),
    policyCompanyTags(row).join(" · "),
    displayCertifiedLabels(row),
    valueText(row.sme_competition_product_label, ""),
    valueText(row.cooperative_purchase_route_label, ""),
  ].filter(Boolean).join(" / ");
}

function masEvidence(row) {
  return firstPositive(row.mas_match, row.mas_status_label);
}

function shoppingEvidence(row) {
  return firstPositive(row.shopping_mall_match, row.shopping_mall_status_label);
}

function constructionEvidence(row) {
  return firstPositive(row.construction_capacity_match, row.construction_capacity_summary, row.construction_license_match);
}

function historyEvidence(row) {
  return firstPositive(row.contract_history_match, row.contract_history_summary, row.contract_history_status_label);
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

function policyCompanyTags(row) {
  const raw = [
    valueText(row.policy_company_labels, ""),
    valueText(row.policy_subtypes, ""),
    valueText(row.procurement_attributes, ""),
  ].join("|");
  const tags = [];
  if (/여성기업|women_company|women_company_product_label/.test(raw)) tags.push("여성기업");
  if (/장애인기업|disabled_company|disabled_company_product_label/.test(raw)) tags.push("장애인기업");
  if (/사회적기업|social_enterprise|social_enterprise_product_label/.test(raw)) tags.push("사회적기업");
  if (/예비사회적|pre_social_enterprise/.test(raw)) tags.push("예비사회적기업");
  if (/중증장애인|severely_disabled|severe_disabled/.test(raw)) tags.push("중증장애인생산품");
  if (/소상공인|small_merchant/.test(raw)) tags.push("소상공인");
  return [...new Set(tags)];
}

function compactFeatureTags(row) {
  const features = [];
  const policyTags = policyCompanyTags(row);
  const policy = policyTags.length ? policyTags.join(" · ") : valueText(row.policy_company_labels, "");
  const cert = displayCertifiedLabels(row);
  const direct = displayDirectEvidence(row);
  const mas = displayMasEvidence(row);
  const shopping = displayShoppingEvidence(row);
  const history = historyEvidence(row);
  const license = constructionEvidence(row) || valueText(row.license_status_label, "");
  const sme = valueText(row.sme_competition_product_label, "");
  const coop = valueText(row.cooperative_purchase_route_label, "");
  const venture = firstPositive(row.venture_nara_product_summary, row.venture_nara_order_summary, row.venture_nara_status_label);
  const status = valueText(row.business_status_label || row.business_status, "");

  if (status) features.push(["영업상태", status, /정상|active|fresh/i.test(status) ? "good" : "warn"]);
  if (policy) features.push(["정책기업", policy, "good"]);
  if (cert) features.push(["인증제품", cert, "good"]);
  if (direct) features.push(["직접생산", direct, "good"]);
  if (mas) features.push(["MAS", mas, "info"]);
  if (shopping) features.push(["쇼핑몰", shopping, "info"]);
  if (history) features.push(["수행이력", history, toneFor(history)]);
  if (license) features.push(["면허", license, toneFor(license)]);
  if (sme) features.push(["중기경쟁제품", sme, toneFor(sme)]);
  if (coop) features.push(["조합", coop, toneFor(coop)]);
  if (venture) features.push(["벤처나라", venture, toneFor(venture)]);

  if (!features.length) features.push(["확인", "업체 특성 근거 확인 필요", "warn"]);
  return features.slice(0, 8);
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
  policyCompanyTags(row).forEach((label) => badges.push(tag(label, "good")));
  if (directEvidence(row)) badges.push(tag("직접생산", "good"));
  if (masEvidence(row)) badges.push(tag("MAS", "info"));
  if (shoppingEvidence(row)) badges.push(tag("종합쇼핑몰", "info"));
  if (historyEvidence(row)) badges.push(tag("과거 수행이력", "info"));
  if (constructionEvidence(row)) badges.push(tag("면허·시공능력", "good"));
  if (valueText(row.certified_product_labels, "")) badges.push(tag("기술개발·인증", "good"));
  if (!policyCompanyTags(row).length && policyEvidence(row)) badges.push(tag("정책근거", "good"));
  if (!badges.length) badges.push(tag("근거 확인 필요", "warn"));
  return badges.slice(0, 8);
}

function evidenceItems(row) {
  return [
    ["조건 충족", conditionText(row), toneFor(row.condition_match_type)],
    ["품목·검색 근거", firstPositive(row.requested_item_evidence_summary, row.matched_query_label, row.main_products) || "요청 품목 근거 확인 필요", toneFor(row.requested_item_evidence_summary)],
    ["구매수단 적합성", valueText(row.purchase_route_fit_summary, "지역업체 구매 지원 근거는 별도 확인 필요"), toneFor(row.purchase_route_fit_summary)],
    ["과거 수행이력", historyEvidence(row) || "유사 계약 수행이력 근거 없음", historyEvidence(row) ? "info" : "warn"],
    ["직접생산", displayDirectEvidence(row) || "직접생산 근거 없음 또는 확인 필요", directEvidence(row) ? "good" : "warn"],
    ["MAS/종합쇼핑몰", [displayMasEvidence(row), displayShoppingEvidence(row)].filter(Boolean).join(" · ") || "등록 근거 없음 또는 확인 필요", masEvidence(row) || shoppingEvidence(row) ? "good" : "warn"],
    ["면허·시공능력", constructionEvidence(row) || firstPositive(row.license_or_business_type) || "면허·시공능력 확인 필요", constructionEvidence(row) ? "good" : "info"],
    ["정책기업", policyCompanyTags(row).join(" · ") || valueText(row.policy_company_labels, "") || "여성·사회적·장애인기업 여부 근거 없음", policyCompanyTags(row).length || valueText(row.policy_company_labels, "") ? "good" : "info"],
    ["기술개발·인증", displayCertifiedLabels(row) || "인증제품 근거 없음 또는 확인 필요", valueText(row.certified_product_labels, "") ? "good" : "info"],
  ];
}

function checkItems(row) {
  const checks = splitValues(row.recommended_checks);
  if (!directEvidence(row) && /중기간|중소기업자간|직접생산/.test(valueText(row.sme_competition_product_label, ""))) {
    checks.push("중소기업자간 경쟁제품이면 직접생산확인증명서 세부품명과 유효기간 확인");
  }
  if (!masEvidence(row) && !shoppingEvidence(row)) {
    checks.push("조달청 종합쇼핑몰 또는 MAS 등록 여부 별도 확인");
  }
  if (!constructionEvidence(row) && /공사|면허|시공/.test(valueText(row.contract_review_types, ""))) {
    checks.push("공고 면허, 주력분야, 시공능력평가금액 기준연도 확인");
  }
  if (historyEvidence(row)) {
    checks.push("과거 수행이력은 참고자료이며 현재 과업범위·면허·자격요건 재확인");
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

function routeStatusLabel(status, priority = "") {
  if (status === "no_local_supplier") return "부산 공급업체 미확인";
  if (status === "registered_only") return "등록 확인";
  if (status === "candidate_evidence_only") return "후보 근거";
  if (priority === "primary") return "먼저 확인";
  if (priority === "secondary") return "다음 검토";
  if (priority === "reference") return "참고";
  if (priority === "excluded") return "어려움";
  if (status === "candidate_found") return "지역업체 존재";
  if (status === "policy_only") return "품목정책 확인";
  if (status === "reference_only") return "참고자료";
  if (status === "mas_direct_check") return "직접구매 검토";
  if (status === "mas_second_stage_check") return "2단계 확인";
  if (status === "viable_check") return "검토 가능";
  if (status === "needs_amount_check" || status === "needs_lookup") return "확인 필요";
  if (status === "not_viable" || status === "no_candidate_found") return "제외";
  return "확인 필요";
}

function routeStatusTone(status, priority = "") {
  if (priority === "primary") return "good";
  if (priority === "secondary") return "info";
  if (priority === "reference") return "neutral";
  if (priority === "excluded") return "warn";
  if (status === "candidate_found") return "good";
  if (status === "policy_only") return "info";
  if (status === "reference_only") return "neutral";
  if (status === "mas_direct_check" || status === "viable_check") return "good";
  if (status === "mas_second_stage_check" || status === "needs_amount_check" || status === "needs_lookup") return "warn";
  if (status === "not_viable" || status === "no_candidate_found") return "warn";
  return "warn";
}

function policyFactTone(value) {
  const normalized = valueText(value, "");
  if (!normalized || /확인 필요|미확인|없음|not_found|unavailable/i.test(normalized)) return "warn";
  if (/미해당|비대상/i.test(normalized)) return "info";
  if (/해당|필요|가능|대상|등록|있음|충족|true|matched/i.test(normalized)) return "good";
  return "info";
}

function numberOrZero(value) {
  const numeric = Number(value || 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

function maxPolicyCount(checks, key) {
  return Math.max(0, ...checks.map((item) => numberOrZero(item?.[key])));
}

function isPolicyPositive(value) {
  const normalized = valueText(value, "");
  if (!normalized || /미해당|확인 필요|미확인|없음|not_found|unavailable/i.test(normalized)) return false;
  return /해당|필요|가능|대상|등록|있음|충족|true|matched|valid/i.test(normalized);
}

function countRows(rows, predicate) {
  return rows.filter((row) => {
    try {
      return predicate(row);
    } catch {
      return false;
    }
  }).length;
}

function policyCandidateCounts(rows) {
  const counts = {
    total: 0,
    women: 0,
    disabled: 0,
    social: 0,
    severeDisabled: 0,
    smallMerchant: 0,
  };
  rows.forEach((row) => {
    const tags = policyCompanyTags(row);
    if (!tags.length) return;
    counts.total += 1;
    if (tags.includes("여성기업")) counts.women += 1;
    if (tags.includes("장애인기업")) counts.disabled += 1;
    if (tags.includes("사회적기업") || tags.includes("예비사회적기업")) counts.social += 1;
    if (tags.includes("중증장애인생산품")) counts.severeDisabled += 1;
    if (tags.includes("소상공인")) counts.smallMerchant += 1;
  });
  return counts;
}

function primaryMatchedProduct(summary, checks) {
  const products = Array.isArray(summary?.matched_products) ? summary.matched_products : [];
  const combined = [...products, ...(Array.isArray(checks) ? checks : [])];
  if (!combined.length) return null;
  return (
    combined.find((item) => isPolicyPositive(item?.sme_competition_product || item?.is_sme_competition_product)) ||
    combined.find((item) => numberOrZero(item?.shopping_mall_active_busan_supplier_count) > 0) ||
    combined.find((item) => numberOrZero(item?.mas_active_supplier_count) > 0) ||
    combined.find((item) => numberOrZero(item?.direct_production_valid_supplier_count) > 0) ||
    combined[0]
  );
}

function buildRouteNarrative(payload, primary, summary, checks) {
  const rows = Array.isArray(payload?.rows) ? payload.rows : [];
  const composition = payload?.candidate_composition || {};
  const query = valueText(payload?.query, "입력 품목");
  const totalCandidateCount = Math.max(
    numberOrZero(composition.total_registered_candidates),
    numberOrZero(payload?.total_candidate_count || payload?.count || rows.length),
  );
  const visibleCandidateCount = numberOrZero(payload?.visible_candidate_count || rows.length || payload?.count);
  const product = primaryMatchedProduct(summary, checks);
  const productName = valueText(product?.detail_product_name || product?.name, "");
  const productCode = valueText(product?.detail_product_code, "");
  const directSupplierCount = Math.max(
    maxPolicyCount(checks, "direct_production_valid_supplier_count"),
    numberOrZero(product?.direct_production_valid_supplier_count),
  );
  const masSupplierCount = Math.max(
    maxPolicyCount(checks, "mas_active_supplier_count"),
    numberOrZero(product?.mas_active_supplier_count),
  );
  const shoppingSupplierCount = Math.max(
    numberOrZero(payload?.purchase_route_guidance?.shopping_mall_busan_supplier_count),
    maxPolicyCount(checks, "shopping_mall_active_busan_supplier_count"),
    numberOrZero(product?.shopping_mall_active_busan_supplier_count),
  );
  const candidateExactSupplierCount = numberOrZero(payload?.purchase_route_guidance?.shopping_mall_candidate_exact_supplier_count);
  const localSupplierBasis = valueText(payload?.purchase_route_guidance?.shopping_mall_local_supplier_basis, "none");
  const mallRegisteredCount = Math.max(
    numberOrZero(payload?.purchase_route_guidance?.shopping_mall_active_registered_count),
    numberOrZero(summary?.shopping_mall_active_registered_count),
    maxPolicyCount(checks, "shopping_mall_active_registered_count"),
    numberOrZero(product?.shopping_mall_active_registered_count),
  );
  const mallSupplierCount = Math.max(
    numberOrZero(payload?.purchase_route_guidance?.shopping_mall_active_supplier_count),
    numberOrZero(summary?.shopping_mall_active_supplier_count),
    maxPolicyCount(checks, "shopping_mall_active_supplier_count"),
    numberOrZero(product?.shopping_mall_active_supplier_count),
  );
  const policyCounts = policyCandidateCounts(rows);
  const directRows = Math.max(numberOrZero(composition.direct_production_count), countRows(rows, (row) => Boolean(directEvidence(row))));
  const mallRows = Math.max(numberOrZero(composition.shopping_mall_mas_count), countRows(rows, (row) => Boolean(masEvidence(row) || shoppingEvidence(row))));
  const policyTotal = Math.max(numberOrZero(composition.policy_company_count), policyCounts.total);
  const lines = [];

  const addLine = (label, text, tone) => {
    lines.push({ label, text, tone });
  };

  const selectionOptions = itemSelectionOptions(summary, checks);
  if (selectionOptions.length) {
    addLine(
      "세부품명 선택",
      valueText(summary?.message, `${query}은(는) 복수 세부품명으로 나뉘므로 실제 구매 품목을 먼저 선택해야 합니다.`),
      "warn",
    );
    addLine(
      "선택 후보",
      `선택 가능한 매칭품목은 ${selectionOptions.map((item) => item.name).join(", ")}입니다. 선택 후 중소기업자간 경쟁제품, 직접생산, 쇼핑몰/MAS, 부산업체 후보를 다시 계산합니다.`,
      "route",
    );
    addLine(
      "계약 전 확인",
      "세부품명번호가 확정되기 전에는 후보업체를 표시하지 않습니다. 세부품명 확정 후 표시되는 업체와 원천자료를 다시 확인하세요.",
      "caution",
    );
    return lines;
  }

  addLine(
    "품목 매칭",
    productName
      ? `${query}은(는) DB 기준 '${productName}'${productCode ? `(${productCode})` : ""} 품목으로 매칭됩니다.`
      : `${query}은(는) 입력어 기준으로 지역업체 후보와 구매 지원 근거를 조회했습니다.`,
    "info",
  );

  if (isPolicyPositive(summary?.sme_competition_product) || isPolicyPositive(product?.sme_competition_product || product?.is_sme_competition_product)) {
    addLine(
      "필수 확인",
      `해당 품목은 중소기업자간 경쟁제품이므로 직접생산확인증명서의 세부품명과 유효기간을 먼저 확인해야 합니다.${directSupplierCount ? ` 현재 DB상 직접생산 유효 공급업체 수는 ${directSupplierCount.toLocaleString("ko-KR")}개입니다.` : ""}`,
      "warn",
    );
  } else if (valueText(summary?.sme_competition_product, "") === "미해당") {
    addLine(
      "품목정책",
      "중소기업자간 경쟁제품에 미해당입니다(DB 기준). 직접생산 의무도 현재 품목정책 DB 기준 확인되지 않습니다. 다만 공고 전 세부품명번호는 원천자료에서 최종 확인하세요.",
      "info",
    );
  } else if (summary?.sme_competition_product) {
    addLine(
      "품목정책",
      "중소기업자간 경쟁제품 해당 여부를 현재 DB 매칭값만으로 확정하지 못했습니다. 공고 전 세부품명번호 기준 재확인이 필요합니다.",
      "warn",
    );
  }

  if (primary?.label || summary?.shopping_mall_contract_basis_label || masSupplierCount || shoppingSupplierCount || mallRegisteredCount) {
    const basis = valueText(summary?.shopping_mall_contract_basis_label || payload?.purchase_route_guidance?.purchase_route_basis_label || primary?.label, "조달청 등록 경로");
    const localMallEvidence = Math.max(mallRows, shoppingSupplierCount);
    const isThirdPartyRoute = /제3자|3자/.test(basis) || /제3자|3자/.test(valueText(primary?.label, ""));
    const isMasRoute = /MAS|다수공급자/.test(basis) || /MAS|다수공급자/.test(valueText(primary?.label, ""));
    const routeName = isThirdPartyRoute
      ? "조달청 제3자단가계약"
      : isMasRoute
        ? "조달청 다수공급자계약(MAS)"
        : "조달청 종합쇼핑몰";
    const routeText = localMallEvidence
      ? localSupplierBasis === "candidate_exact_evidence"
        ? `${routeName}에서 요청 세부품명과 일치하는 부산 지역업체가 ${candidateExactSupplierCount.toLocaleString("ko-KR")}개 확인됩니다. 이 수치는 업체별 후보 DB 기준이며 품목별 쇼핑몰 공급업체 집계와 차이가 있으므로, 계약 전 나라장터에서 물품식별번호, 계약상태, 공급업체 유효 여부를 수동 확인해야 합니다.`
        : `${routeName}에서 요청 세부품명과 일치하는 부산 지역업체가 ${localMallEvidence.toLocaleString("ko-KR")}개 확인됩니다. 품목 마스터 기준은 '${basis}'입니다.${mallRegisteredCount ? ` 전국 기준 쇼핑몰 등록 건수는 ${mallRegisteredCount.toLocaleString("ko-KR")}건입니다.` : ""}${mallSupplierCount ? ` 전국 기준 공급업체 수는 ${mallSupplierCount.toLocaleString("ko-KR")}개입니다.` : ""}`
      : isMasRoute
        ? "다수공급자계약(MAS) 품목으로 확인됩니다. 원칙적으로 조달청 종합쇼핑몰/MAS 2단계경쟁 경로를 우선 확인해야 합니다. 다만 현재 DB 기준 이 세부품명으로 등록된 부산 MAS/쇼핑몰 공급업체가 확인되지 않거나, 필요한 규격·조건을 MAS로 충족하기 어려운 경우에는 조달청 입찰 또는 발주기관 일반입찰 가능성을 계약부서와 별도 검토해야 합니다."
        : `${routeName} 품목으로 확인됩니다. 다만 현재 DB 기준 이 세부품명으로 등록된 부산 MAS/쇼핑몰 공급업체는 확인되지 않습니다. 중소기업자간 경쟁제품이 아니면 직접생산 필수 품목으로 보지 않으므로, 조달등록 부산 유통사·제조사를 직접계약 또는 입찰공고 대안으로 함께 검토할 수 있습니다.`;
    addLine(
      "구매경로",
      routeText,
      "route",
    );
  }

  addLine(
    "업체 현황",
    `조달청 등록 부산 지역업체 후보는 총 ${totalCandidateCount.toLocaleString("ko-KR")}개이며, 이 중 DB상 조건 일치도가 높은 상위 ${visibleCandidateCount.toLocaleString("ko-KR")}개를 화면에 표시합니다. 전체 후보 기준 직접생산 보유 업체는 ${directRows.toLocaleString("ko-KR")}개, 종합쇼핑몰/MAS 등록 지역업체는 ${mallRows.toLocaleString("ko-KR")}개, 정책기업은 ${policyTotal.toLocaleString("ko-KR")}개입니다.`,
    "good",
  );

  if (policyTotal) {
    const womenCount = Math.max(numberOrZero(composition.women_company_count), policyCounts.women);
    const disabledCount = Math.max(numberOrZero(composition.disabled_company_count), policyCounts.disabled);
    const socialCount = Math.max(numberOrZero(composition.social_enterprise_count), policyCounts.social);
    const policyBreakdown = [
      womenCount ? `여성기업 ${womenCount}개` : "",
      disabledCount ? `장애인기업 ${disabledCount}개` : "",
      socialCount ? `사회적기업 ${socialCount}개` : "",
      policyCounts.severeDisabled ? `중증장애인 생산품 ${policyCounts.severeDisabled}개` : "",
    ].filter(Boolean).join(", ");
    addLine(
      "정책기업",
      `정책기업 후보는 ${policyBreakdown || `${policyCounts.total}개`}입니다. 물품·용역의 정책기업 수의계약은 추정가격 1억원 이하 범위에서 검토 가능성이 있으나, 발주기관 적용 법령, 계약목적, 인증 유효기간은 별도 확인해야 합니다.`,
      "policy",
    );
  }

  addLine(
    "계약 전 확인",
    "아래 후보업체는 확정 추천이 아니라 DB상 조건 일치도가 높은 검토 대상입니다. 최종 계약 가능 여부는 원천자료와 법령해석 탭에서 재확인하세요.",
    "caution",
  );
  return lines;
}

function buildCandidateComposition(payload) {
  const rows = Array.isArray(payload?.rows) ? payload.rows : [];
  const composition = payload?.candidate_composition || {};
  const fallbackPolicy = policyCandidateCounts(rows);
  const total = Math.max(
    numberOrZero(composition.total_registered_candidates),
    numberOrZero(payload?.total_candidate_count || payload?.count || rows.length),
  );
  const direct = Math.max(numberOrZero(composition.direct_production_count), countRows(rows, (row) => Boolean(directEvidence(row))));
  const mall = Math.max(numberOrZero(composition.shopping_mall_mas_count), countRows(rows, (row) => Boolean(masEvidence(row) || shoppingEvidence(row))));
  const policy = Math.max(numberOrZero(composition.policy_company_count), fallbackPolicy.total);
  const women = Math.max(numberOrZero(composition.women_company_count), fallbackPolicy.women);
  const disabled = Math.max(numberOrZero(composition.disabled_company_count), fallbackPolicy.disabled);
  const social = Math.max(numberOrZero(composition.social_enterprise_count), fallbackPolicy.social);
  const maxValue = Math.max(total, direct, mall, policy, 1);
  const percent = (value) => {
    if (!value) return 0;
    return Math.max(8, Math.min(100, Math.round((value / maxValue) * 100)));
  };
  return {
    basisLabel: valueText(composition.basis_label, composition.basis ? "전체 후보 기준" : "화면 후보 기준"),
    items: [
      {
        label: "조달청 등록 지역업체",
        value: total,
        detail: "검색 조건에 걸린 부산 업체 후보",
        tone: "total",
      },
      {
        label: "직생 보유 지역업체",
        value: direct,
        detail: "직접생산확인증명서 보유",
        tone: "direct",
      },
      {
        label: "쇼핑몰/MAS 지역업체",
        value: mall,
        detail: "조달청 종합쇼핑몰 또는 MAS 등록",
        tone: "mall",
      },
      {
        label: "정책기업",
        value: policy,
        detail: [
          women ? `여성 ${women}` : "",
          social ? `사회적 ${social}` : "",
          disabled ? `장애인 ${disabled}` : "",
        ].filter(Boolean).join(" · ") || "여성·사회적·장애인 여부",
        tone: "policy",
      },
    ].map((item) => ({ ...item, percent: percent(item.value) })),
  };
}

function renderCandidateComposition(payload) {
  const composition = buildCandidateComposition(payload);
  const hasAny = composition.items.some((item) => item.value > 0);
  if (!hasAny) return "";
  return `
    <section class="vendor-composition-panel" aria-label="지역업체 후보 구성">
      <div class="vendor-composition-head">
        <b>지역업체 후보 구성</b>
        <small>${escapeHtml(composition.basisLabel)}</small>
      </div>
      <div class="vendor-composition-grid">
        ${composition.items.map((item) => `
          <article class="vendor-composition-item ${escapeHtml(item.tone)}" style="--value:${item.percent}%">
            <div>
              <span>${escapeHtml(item.label)}</span>
              <strong>${item.value.toLocaleString("ko-KR")}개</strong>
            </div>
            <div class="composition-bar" aria-hidden="true"><i></i></div>
            <p>${escapeHtml(item.detail)}</p>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function routeDecisionLine(label, value, tone = "neutral") {
  return `<span class="decision-fact ${tone}"><b>${escapeHtml(label)}</b>${escapeHtml(valueText(value, "확인 필요"))}</span>`;
}

function itemSelectionOptions(summary, checks = []) {
  const status = valueText(summary?.status, "");
  const selectionRequired = status === "needs_item_selection" || summary?.selection_required === true;
  if (!selectionRequired) return [];

  const matchedProducts = Array.isArray(summary?.matched_products) ? summary.matched_products : [];
  const rawOptions = Array.isArray(summary?.selection_options) && summary.selection_options.length
    ? summary.selection_options
    : matchedProducts;
  const references = [...matchedProducts, ...(Array.isArray(checks) ? checks : [])];
  const seen = new Set();

  return rawOptions
    .map((item) => {
      const name = valueText(item.detail_product_name || item.name || item.selection_query, "");
      const code = valueText(item.detail_product_code || item.code, "");
      if (!name) return null;
      const reference =
        references.find((candidate) => code && valueText(candidate.detail_product_code || candidate.code, "") === code) ||
        references.find((candidate) => name && valueText(candidate.detail_product_name || candidate.name, "") === name) ||
        item;
      const key = code || name;
      if (seen.has(key)) return null;
      seen.add(key);
      return {
        code,
        name,
        query: valueText(item.selection_query || name, name),
        source: valueText(item.matched_policy_source || reference.matched_policy_source, ""),
        busanProductCount: numberOrZero(reference.busan_company_product_count),
        shoppingSupplierCount: Math.max(
          numberOrZero(reference.shopping_mall_active_busan_supplier_count),
          numberOrZero(reference.shopping_mall_active_supplier_count),
        ),
      };
    })
    .filter(Boolean)
    .slice(0, 8);
}

function renderItemSelectionOptions(summary, checks = [], mode = "panel") {
  const options = itemSelectionOptions(summary, checks);
  if (!options.length) return "";
  const title =
    mode === "search"
      ? valueText(summary?.selection_title, "세부품명 선택 필요")
      : mode === "empty"
        ? "세부품명 선택 후 다시 조회"
        : "매칭품목 선택";
  const description =
    mode === "search"
      ? valueText(summary?.message, "검색어만으로는 세부품명을 확정할 수 없습니다. 실제 구매하려는 품목을 선택하세요.")
      : mode === "empty"
        ? "현재 검색어는 범위가 넓어 업체 후보를 표시하지 않습니다. 실제 구매하려는 세부품명을 선택하면 품목정책과 부산업체 후보를 다시 계산합니다."
        : "아래 세부품명 중 실제 구매 대상에 가까운 항목을 선택하면 해당 품목 기준으로 다시 조회합니다.";
  return `
    <div class="item-selection-box ${mode === "empty" ? "is-empty" : ""} ${mode === "search" ? "is-search" : ""}">
      <div class="item-selection-copy">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(description)}</span>
      </div>
      <div class="item-selection-list" role="list" aria-label="세부품명 선택">
        ${options.map((option) => {
          const meta = [
            option.code ? `세부품명번호 ${option.code}` : "",
            option.busanProductCount ? `부산 조달업체 ${option.busanProductCount.toLocaleString("ko-KR")}개` : "",
            option.shoppingSupplierCount ? `쇼핑몰 공급 ${option.shoppingSupplierCount.toLocaleString("ko-KR")}개` : "",
          ].filter(Boolean).join(" · ") || valueText(option.source, "품목정책 재판정");
          return `
            <button type="button" class="item-selection-button" data-item-selection-query="${escapeHtml(option.query)}" role="listitem">
              <span>${escapeHtml(option.name)}</span>
              <em>${escapeHtml(meta)}</em>
            </button>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function hideSearchSelectionPopover() {
  if (!els.itemSelectionPopover) return;
  els.itemSelectionPopover.innerHTML = "";
  els.itemSelectionPopover.hidden = true;
}

function renderSearchSelectionPopover(payload) {
  if (!els.itemSelectionPopover) return;
  const summary = payload?.item_policy_summary || {};
  const checks = Array.isArray(payload?.product_policy_checks) ? payload.product_policy_checks : [];
  const html = renderItemSelectionOptions(summary, checks, "search");
  if (!html) {
    hideSearchSelectionPopover();
    return;
  }
  els.itemSelectionPopover.innerHTML = html;
  els.itemSelectionPopover.hidden = false;
  attachItemSelectionHandlers(els.itemSelectionPopover);
}

function attachItemSelectionHandlers(root) {
  root.querySelectorAll("[data-item-selection-query]").forEach((button) => {
    button.addEventListener("click", () => {
      const query = valueText(button.dataset.itemSelectionQuery, "");
      if (!query) return;
      hideSearchSelectionPopover();
      els.input.value = query;
      els.input.focus();
      search(query);
      els.routeDecisionPanel?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function renderRouteDecision(payload, cards) {
  if (!els.routeDecisionPanel) return;
  const guide = payload?.purchase_route_guidance || {};
  const summary = payload?.item_policy_summary || {};
  const checks = Array.isArray(payload?.product_policy_checks) ? payload.product_policy_checks : [];
  const primary = guide.primary_route || cards[0] || {};
  const narrativeLines = buildRouteNarrative(payload, primary, summary, checks);
  const compositionPanel = renderCandidateComposition(payload);

  els.routeDecisionPanel.innerHTML = `
    <article class="route-narrative-card">
      <span>실무 요약</span>
      <strong>${escapeHtml(valueText(primary.label || guide.title, "직접계약/입찰공고 검토"))}</strong>
      ${compositionPanel}
      <ol class="route-narrative-list">
        ${narrativeLines.map((line) => `
          <li class="${escapeHtml(line.tone)}">
            <div class="narrative-copy">
              <b>${escapeHtml(line.label)}</b>
              <p>${escapeHtml(line.text)}</p>
            </div>
          </li>
        `).join("")}
      </ol>
    </article>
  `;
  attachItemSelectionHandlers(els.routeDecisionPanel);
}

function renderRouteOptions(cards) {
  if (!els.routeOptions) return;
  els.routeOptions.innerHTML = "";
  if (!cards.length) {
    els.routeOptions.classList.add("is-empty");
    return;
  }
  els.routeOptions.classList.remove("is-empty");
  cards.slice(0, 5).forEach((card, index) => {
    const article = document.createElement("article");
    article.className = `route-option-card${index === 0 ? " is-primary" : ""}`;
    const nextActions = Array.isArray(card.next_actions) ? card.next_actions.filter(Boolean).slice(0, 3) : [];
    const checks = Array.isArray(card.required_checks) ? card.required_checks.filter(Boolean).slice(0, 3) : [];
    const status = valueText(card.status, "needs_check");
    const priority = valueText(card.route_priority, "");
    const basis = valueText(card.basis_explanation, "");
    const rankLabel =
      priority === "excluded"
        ? "현재 조건상 어려움"
        : priority === "reference"
          ? "참고 확인"
          : index === 0
            ? "먼저 확인할 방식"
            : `${index + 1}번째 검토 방식`;
    const detailItems = nextActions.length ? nextActions : checks;
    article.innerHTML = `
      <div class="route-option-head">
        <div>
          <span class="route-rank">${rankLabel}</span>
          <strong>${escapeHtml(valueText(card.label, "구매방식 확인"))}</strong>
        </div>
        <span class="tag ${routeStatusTone(status, priority)}">${escapeHtml(routeStatusLabel(status, priority))}</span>
      </div>
      <p>${escapeHtml(valueText(card.reason, "원천 DB 근거를 확인해야 합니다."))}</p>
      ${basis ? `<small class="route-basis">${escapeHtml(basis)}</small>` : ""}
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
  const cards = Array.isArray(guide.route_cards) ? guide.route_cards : [];
  const badges = Array.isArray(guide.badges) ? guide.badges : [];

  els.routeTitle.textContent = cards.length ? "지역업체 구매 지원 방안과 후보 대안" : "지역업체 후보 검토";
  els.routeNotice.textContent =
    guide.legal_notice || "지역업체 구매 지원 방안 안내는 후보 정보입니다. 최종 계약 가능 여부와 법령 해석은 별도 검토가 필요합니다.";
  renderRouteDecision(payload, cards);
  if (els.routeOptions) {
    els.routeOptions.innerHTML = "";
    els.routeOptions.classList.add("is-empty");
  }

  els.routeBadges.innerHTML = "";
  if (badges.length) {
    badges.forEach((item) => els.routeBadges.appendChild(tag(item.label || "확인 필요", item.tone || "info")));
  } else if (cards.length) {
    cards.slice(0, 4).forEach((item) => els.routeBadges.appendChild(tag(item.label || item.route_id, item.status === "candidate_found" ? "info" : "warn")));
  }
}

function renderItemPolicySummary(payload) {
  if (!els.itemPolicyPanel) return;
  const summary = payload?.item_policy_summary || {};
  const checks = Array.isArray(payload?.product_policy_checks) ? payload.product_policy_checks : [];
  const matchedProducts = Array.isArray(summary.matched_products) ? summary.matched_products : [];
  const status = valueText(summary.status, "not_requested");
  const selectionRequired = status === "needs_item_selection" || summary.selection_required === true;
  const statusLabel =
    selectionRequired
      ? valueText(summary.selection_title, "세부 품목 선택 필요")
      : status === "matched"
      ? "품목정책 DB 매칭"
      : status === "not_requested"
        ? "품목정책 조회 제외"
        : "품목정책 확인 필요";
  const statusTone = status === "matched" ? "good" : status === "not_requested" ? "info" : "warn";
  const facts = [
    ["중소기업자간 경쟁제품", summary.sme_competition_product],
    ["직접생산 필요", summary.direct_production_certificate],
    ["조합추천/공동사업", summary.cooperative_purchase_route],
  ]
    .map(([label, value]) => `<span class="policy-fact"><b>${escapeHtml(label)}</b>${escapeHtml(valueText(value, "확인 필요"))}</span>`)
    .join("");
  const productRows = selectionRequired ? [] : matchedProducts.slice(0, 4).map((item) => {
    const name = valueText(item.detail_product_name || item.name, "품목명 미확인");
    const code = valueText(item.detail_product_code || item.code, "");
    const detail = code ? `세부품명번호 ${code}` : "세부품명번호 확인 필요";
    return `<li><strong>${escapeHtml(name)}</strong><span>${escapeHtml(detail)}</span></li>`;
  });
  const sourceRows = selectionRequired ? [] : checks.slice(0, 4).map((item) => {
    const name = valueText(item.detail_product_name, "품목명 미확인");
    const source = valueText(item.matched_policy_source, "DB");
    const shopping = valueText(item.shopping_mall_active_contract_types, "");
    const counts = [
      item.mas_active_supplier_count ? `MAS ${item.mas_active_supplier_count}` : "",
      item.shopping_mall_active_supplier_count ? `쇼핑몰 ${item.shopping_mall_active_supplier_count}` : "",
      item.direct_production_valid_supplier_count ? `직생 ${item.direct_production_valid_supplier_count}` : "",
    ].filter(Boolean).join(" · ");
    return `<li><strong>${escapeHtml(name)}</strong><span>${escapeHtml([source, shopping, counts].filter(Boolean).join(" / ") || "근거 확인")}</span></li>`;
  });

  els.itemPolicyPanel.innerHTML = `
    <div class="item-policy-head">
      <div>
        <span class="route-rank">품목정책 판정</span>
        <strong>${escapeHtml(statusLabel)}</strong>
      </div>
      <span class="tag ${statusTone}">${escapeHtml(selectionRequired ? "선택 필요" : status === "matched" ? "근거 있음" : "확인 필요")}</span>
    </div>
    ${selectionRequired ? `<p class="policy-selection-notice">${escapeHtml(valueText(summary.message, "실제 구매하려는 세부품명을 선택해 주세요."))}</p>` : ""}
    <div class="policy-fact-grid">${facts}</div>
    ${
      productRows.length || sourceRows.length
        ? `<div class="policy-source-grid">
            <div>
              <em>매칭 품목</em>
              <ul>${productRows.join("") || "<li><span>매칭 품목 없음</span></li>"}</ul>
            </div>
            <div>
              <em>원천 근거</em>
              <ul>${sourceRows.join("") || "<li><span>원천 근거 없음</span></li>"}</ul>
            </div>
          </div>`
        : `<p>${escapeHtml(valueText(summary.message, "품목정책 DB에서 근거를 확인하지 못했습니다."))}</p>`
    }
  `;

  attachItemSelectionHandlers(els.itemPolicyPanel);
}

function zeroResultStatus(payload) {
  const status = payload?.zero_result_status || {};
  const actions = Array.isArray(status.next_actions) ? status.next_actions.filter(Boolean) : [];
  return {
    status: valueText(status.status, ""),
    label: valueText(status.label, "조건에 맞는 후보가 없습니다."),
    message: valueText(status.message, "검색어를 품목명, 세부품명, 면허명 또는 업종명 중심으로 다시 확인해야 합니다."),
    actions,
  };
}

function renderSummary(payload, rows) {
  if (!els.summaryCount || !els.summaryDesc || !els.summaryCondition || !els.summaryRoute || !els.summaryDownload) {
    return;
  }
  const count = Number(payload?.count || rows.length || 0);
  const conditionLabels = rows.map((row) => valueText(row.condition_match_type, ""));
  const all = conditionLabels.filter((label) => /모두 충족|조건 충족/.test(label)).length;
  const evidenceChecked = conditionLabels.filter((label) => /품목근거 확인|공사면허 확인|근거 확인|후보 표시/.test(label)).length;
  const partial = conditionLabels.filter((label) => label.includes("일부 충족")).length;
  const needs = conditionLabels.filter((label) => /근거 부족|확인 필요/.test(label)).length;
  const routeEvidence = rows.filter((row) => directEvidence(row) || masEvidence(row) || shoppingEvidence(row) || policyEvidence(row)).length;
  const guide = payload?.purchase_route_guidance || {};
  const basisLabel = valueText(guide.purchase_route_basis_label, "");
  const zeroStatus = zeroResultStatus(payload);

  els.summaryCount.textContent = `${count.toLocaleString("ko-KR")}개`;
  els.summaryDesc.textContent = count
    ? `화면에는 근거 충족도가 높은 상위 ${Math.min(DISPLAY_LIMIT, rows.length)}개를 표시합니다. 조달청 등록 전체 지역업체는 XLSX로 내려받아 검토하세요.`
    : "조건에 맞는 후보가 없습니다. 검색어를 품목명 또는 면허명 중심으로 바꿔보세요.";
  if (!count && zeroStatus.message) {
    els.summaryDesc.textContent = zeroStatus.message;
  }
  els.summaryCondition.textContent = all
    ? `조건 충족 ${all}개`
    : evidenceChecked
      ? `근거 확인 ${evidenceChecked}개`
      : partial
        ? `일부 충족 ${partial}개`
        : needs
          ? `확인 필요 ${needs}개`
          : "-";
  els.summaryRoute.textContent = basisLabel || (routeEvidence ? `근거 있음 ${routeEvidence}개` : "확인 필요");
  els.summaryDownload.textContent = count ? "조달청 등록 전체 지역업체 XLSX" : "대기";
}

function formatHistoryKrw(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "-";
  if (numeric >= 100000000) return `${(numeric / 100000000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억원`;
  return `${Math.round(numeric / 10000).toLocaleString("ko-KR")}만원`;
}

function historySummaryText(row) {
  const count = Number(row.contract_history_recent_count || 0);
  const amount = Number(row.contract_history_total_amount || 0);
  const last = valueText(row.contract_history_last_date, "");
  const parts = [];
  if (count > 0) parts.push(`유사계약 ${count.toLocaleString("ko-KR")}건`);
  if (amount > 0) parts.push(formatHistoryKrw(amount));
  if (last) parts.push(`최근 ${last}`);
  return parts.join(" / ") || historyEvidence(row) || "과거 수행이력 상세 확인";
}

function closeHistoryModal() {
  if (!els.historyModal) return;
  els.historyModal.hidden = true;
  document.body.classList.remove("modal-open");
}

function openHistoryModal(title, metaHtml, bodyHtml) {
  if (!els.historyModal) return;
  els.historyModalTitle.textContent = title;
  els.historyModalMeta.innerHTML = metaHtml;
  els.historyModalBody.innerHTML = bodyHtml;
  els.historyModal.hidden = false;
  document.body.classList.add("modal-open");
}

function renderHistoryTable(payload) {
  const rows = Array.isArray(payload?.rows) ? payload.rows : [];
  const limitations = Array.isArray(payload?.limitations) ? payload.limitations : [];
  if (!rows.length) {
    return `
      <div class="history-empty">
        <strong>표시할 과거 수주 이력이 없습니다.</strong>
        <p>현재 검색어 기준으로 매칭되는 계약 이력이 없거나, 원천 DB에 해당 업체의 수행 이력이 아직 없습니다.</p>
      </div>
      <ul class="history-limitations">${limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    `;
  }

  const body = rows
    .map((row) => {
      const itemName = valueText(row.product_classification_name || row.product_mid_classification_name || row.product_large_classification_name, "-");
      return `
        <tr>
          <td>${escapeHtml(valueText(row.contract_date, "-"))}</td>
          <td>${escapeHtml(valueText(row.contract_type, "-"))}</td>
          <td>${escapeHtml(valueText(row.agency_name, "-"))}</td>
          <td><strong>${escapeHtml(valueText(row.contract_name, "-"))}</strong><span>${escapeHtml(itemName)}</span></td>
          <td>${escapeHtml(formatHistoryKrw(row.contract_amount))}</td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="history-table-wrap">
      <table class="history-table">
        <thead>
          <tr>
            <th>계약일</th>
            <th>구분</th>
            <th>수요기관</th>
            <th>계약명 / 품목</th>
            <th>계약금액</th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>
    <ul class="history-limitations">${limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
  `;
}

async function showContractHistory(row) {
  const companyId = valueText(row.company_id, "");
  const companyName = valueText(row.company_name, "업체명 미확인");
  if (!companyId) {
    openHistoryModal(companyName, '<span class="tag warn">company_id 없음</span>', '<div class="history-empty"><strong>상세 이력을 조회할 수 없습니다.</strong><p>후보 데이터에 company_id가 없습니다.</p></div>');
    return;
  }
  openHistoryModal(companyName, '<span class="tag neutral">조회 중</span>', '<div class="history-loading">과거 수주 이력을 조회하고 있습니다.</div>');
  const requestParams = new URLSearchParams({
    q: lastQuery || valueText(els.input.value, ""),
    limit: "20",
  });
  try {
    const response = await fetch(`${API_BASE_URL}/vendor-recommendations/${encodeURIComponent(companyId)}/contract-history?${requestParams.toString()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const terms = Array.isArray(payload?.matched_terms) && payload.matched_terms.length ? `검색어: ${payload.matched_terms.map(escapeHtml).join(", ")}` : "전체 이력 기준";
    const meta = [
      `<span class="tag info">${Number(payload?.count || 0).toLocaleString("ko-KR")}건</span>`,
      `<span class="tag neutral">${escapeHtml(formatHistoryKrw(payload?.total_amount))}</span>`,
      payload?.last_date ? `<span class="tag neutral">최근 ${escapeHtml(payload.last_date)}</span>` : "",
      `<span class="history-query">${terms}</span>`,
    ].filter(Boolean).join("");
    openHistoryModal(companyName, meta, renderHistoryTable(payload));
  } catch (error) {
    openHistoryModal(
      companyName,
      '<span class="tag warn">조회 실패</span>',
      `<div class="history-empty"><strong>과거 수주 이력 조회에 실패했습니다.</strong><p>${escapeHtml(error.message || error)}</p></div>`,
    );
  }
}

function renderCandidate(row, index) {
  const node = els.template.content.cloneNode(true);
  const card = node.querySelector(".candidate-card");
  if (index === 0) card.classList.add("is-top");
  node.querySelector(".rank").innerHTML = `<span>후보</span><strong>${String(index + 1).padStart(2, "0")}</strong>`;
  node.querySelector(".candidate-name").textContent = valueText(row.company_name, "업체명 미확인");
  node.querySelector(".candidate-location").textContent = [row.location, row.detail_address].map((item) => valueText(item, "")).filter(Boolean).join(" · ") || "소재지 확인 필요";
  node.querySelector(".basis-level").textContent = basisLevel(row);
  const reviewScore = Number(row.review_score);
  node.querySelector(".score-pill").textContent = Number.isFinite(reviewScore) && reviewScore > 0 ? reviewScore.toLocaleString("ko-KR") : "미산정";

  const badgeRow = node.querySelector(".card-badges");
  buildBadges(row).slice(0, 6).forEach((item) => badgeRow.appendChild(item));

  const primaryProducts = splitValues(row.main_products).slice(0, 4).join(", ") || "대표품목 확인 필요";
  node.querySelector(".candidate-primary-products-text").textContent = truncate(primaryProducts, 120);

  const featureStrip = document.createElement("div");
  featureStrip.className = "feature-strip";
  compactFeatureTags(row).slice(0, 4).forEach(([label, value, tone]) => {
    const item = document.createElement("div");
    item.className = `feature-pill ${tone}`;
    item.innerHTML = `<span>${escapeHtml(label)}</span><strong title="${escapeHtml(value)}">${escapeHtml(truncate(value, 54))}</strong>`;
    featureStrip.appendChild(item);
  });
  badgeRow.insertAdjacentElement("afterend", featureStrip);

  const grid = node.querySelector(".evidence-grid");
  evidenceItems(row)
    .filter(([label]) => ["품목·검색 근거", "구매수단 적합성", "과거 수행이력", "직접생산", "MAS/종합쇼핑몰", "정책기업", "기술개발·인증", "면허·시공능력"].includes(label))
    .slice(0, 6)
    .forEach(([label, value, tone]) => {
    const div = document.createElement("div");
    div.className = `evidence-item ${tone}`;
    div.innerHTML = `<span>${escapeHtml(label)}</span><strong title="${escapeHtml(value)}">${escapeHtml(truncate(value, 86))}</strong>`;
    grid.appendChild(div);
  });

  const checks = checkItems(row);
  node.querySelector(".candidate-alert-count").textContent = `${checks.length.toLocaleString("ko-KR")}개`;
  node.querySelector(".candidate-alert-copy").textContent = checks[0] || "최종 계약 가능 여부를 원천자료로 확인하세요.";

  const checkList = node.querySelector(".check-list");
  checks.slice(0, 4).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    checkList.appendChild(li);
  });

  node.querySelector(".main-products").textContent = truncate(splitValues(row.main_products).join(", "), 220);
  node.querySelector(".licenses").textContent = truncate(splitValues(row.license_or_business_type).join(", "), 260);
  node.querySelector(".procurement-evidence").textContent = truncate(
    displayProcurementEvidence(row) || "조달 근거 확인 필요",
    260,
  );
  node.querySelector(".checks").textContent = truncate(checks.join(" / "), 260);

  const actionRow = document.createElement("div");
  actionRow.className = "candidate-actions";
  const historyButton = document.createElement("button");
  historyButton.type = "button";
  historyButton.className = "history-button";
  historyButton.textContent = "과거 수주 이력 보기";
  historyButton.addEventListener("click", () => showContractHistory(row));
  const historyMini = document.createElement("span");
  historyMini.className = "history-mini";
  historyMini.textContent = historySummaryText(row);
  actionRow.appendChild(historyButton);
  actionRow.appendChild(historyMini);
  node.querySelector(".candidate-actions-slot").appendChild(actionRow);

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
    if (els.downloadLink) {
      els.downloadLink.classList.add("disabled");
      els.downloadLink.setAttribute("aria-disabled", "true");
    }
    if (els.summaryDownloadCard) {
      els.summaryDownloadCard.classList.add("disabled");
      els.summaryDownloadCard.setAttribute("aria-disabled", "true");
    }
    return;
  }
  if (els.downloadLink) {
    els.downloadLink.classList.remove("disabled");
    els.downloadLink.setAttribute("aria-disabled", "false");
  }
  if (els.summaryDownloadCard) {
    els.summaryDownloadCard.classList.remove("disabled");
    els.summaryDownloadCard.setAttribute("aria-disabled", "false");
  }
}

function renderPayload(payload) {
  const rows = Array.isArray(payload?.rows) ? payload.rows : [];
  lastPayload = payload;
  els.candidateList.innerHTML = "";

  if (!rows.length) {
    const zeroStatus = zeroResultStatus(payload);
    const actionList = zeroStatus.actions.length
      ? `<ul class="zero-action-list">${zeroStatus.actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
      : "";
    els.candidateList.innerHTML = `
      <article class="empty-panel">
        <strong>${escapeHtml(zeroStatus.label)}</strong>
        <span>${escapeHtml(zeroStatus.message)}</span>
        ${actionList}
      </article>
    `;
  } else {
    rows.slice(0, DISPLAY_LIMIT).forEach((row, index) => els.candidateList.appendChild(renderCandidate(row, index)));
  }

  els.visibleCount.textContent = `${Math.min(DISPLAY_LIMIT, rows.length)}개 표시`;
  const date = sourceDate(rows);
  if (date) els.dataDate.textContent = `DB 기준 ${date}`;
  renderSummary(payload, rows);
  renderSearchSelectionPopover(payload);
  renderRouteGuide(payload);
  renderItemPolicySummary(payload);
  renderComparison(rows);
  setDownloadState(rows.length > 0);
}

async function search(query) {
  lastQuery = query;
  hideSearchSelectionPopover();
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
  if (!els.leakageList || !els.leakageUpdated) return;
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
    hideSearchSelectionPopover();
    els.input.value = button.dataset.query || button.textContent.trim();
    els.input.focus();
  });
});

els.input.addEventListener("input", hideSearchSelectionPopover);

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
  hideSearchSelectionPopover();
  renderPayload({ rows: [], count: 0, purchase_route_guidance: {} });
});

els.downloadLink.addEventListener("click", (event) => {
  event.preventDefault();
  if (els.downloadLink.classList.contains("disabled")) return;
  downloadXlsx();
});

if (els.summaryDownloadCard) {
  els.summaryDownloadCard.addEventListener("click", () => {
    if (els.summaryDownloadCard.classList.contains("disabled")) return;
    downloadXlsx();
  });

  els.summaryDownloadCard.addEventListener("keydown", (event) => {
    if (!["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    if (els.summaryDownloadCard.classList.contains("disabled")) return;
    downloadXlsx();
  });
}

if (els.historyModalClose) {
  els.historyModalClose.addEventListener("click", closeHistoryModal);
}

if (els.historyModal) {
  els.historyModal.addEventListener("click", (event) => {
    if (event.target?.dataset?.historyClose !== undefined) closeHistoryModal();
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && els.historyModal && !els.historyModal.hidden) {
    closeHistoryModal();
  }
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
