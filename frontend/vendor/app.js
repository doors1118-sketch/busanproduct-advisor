const params = new URLSearchParams(window.location.search);
const API_BASE_URL =
  params.get("api") ||
  (window.location.protocol === "file:" || window.location.port === "5177" ? "http://127.0.0.1:8001" : "");
const MONITORING_API_BASE_URL = (params.get("monitoring") || "https://busanproduct.co.kr").replace(/\/$/, "");

const DISPLAY_LIMIT = 8;

const els = {
  form: document.querySelector("#search-form"),
  input: document.querySelector("#query-input"),
  button: document.querySelector("#search-button"),
  apiState: document.querySelector("#api-state"),
  dataDate: document.querySelector("#data-date"),
  summaryTitle: document.querySelector("#summary-title"),
  summaryDesc: document.querySelector("#summary-desc"),
  downloadLink: document.querySelector("#download-link"),
  downloadDetail: document.querySelector("#download-detail"),
  candidateList: document.querySelector("#candidate-list"),
  visibleCount: document.querySelector("#visible-count"),
  template: document.querySelector("#candidate-template"),
  monitoringState: document.querySelector("#monitoring-state"),
  metricOverall: document.querySelector("#metric-overall"),
  metricGenerated: document.querySelector("#metric-generated"),
  metricBusanGroup: document.querySelector("#metric-busan-group"),
  metricNationalGroup: document.querySelector("#metric-national-group"),
  metricCompanyDb: document.querySelector("#metric-company-db"),
  sectorConstruction: document.querySelector("#sector-construction"),
  sectorService: document.querySelector("#sector-service"),
  sectorGoods: document.querySelector("#sector-goods"),
  sectorShopping: document.querySelector("#sector-shopping"),
  leakageList: document.querySelector("#leakage-list"),
  leakageUpdated: document.querySelector("#leakage-updated"),
  routeTitle: document.querySelector("#route-title"),
  routeDesc: document.querySelector("#route-desc"),
  routeBadges: document.querySelector("#route-badges"),
  routePrimary: document.querySelector("#route-primary"),
  routeRequired: document.querySelector("#route-required"),
  routeRanking: document.querySelector("#route-ranking"),
};

let lastSearchQuery = "";
let lastSearchRows = [];
let lastSearchIsFallback = true;

const sampleRows = [
  {
    company_name: "주식회사 예스텍",
    location: "부산광역시",
    detail_address: "부산광역시 소재",
    business_status_label: "정상영업 확인",
    license_or_business_type: "정보통신공사업 | 소프트웨어사업자",
    main_products: "CCTV | 영상감시장치 | 보안장비",
    shopping_mall_status_label: "종합쇼핑몰 등록정보 있음",
    mas_status_label: "MAS 등록정보 있음",
    direct_production_certificate_status: "직접생산증명 정보 있음",
    policy_company_labels: "",
    certified_product_labels: "기술개발제품",
    sme_competition_product_label: "중기간경쟁제품 확인 필요",
    recommended_checks: "직접생산 유효기간 확인 | 쇼핑몰 단가 확인 | 실제 납품 가능지역 확인",
    source_refreshed_at: "2026-06-10",
    review_score: 92,
  },
  {
    company_name: "부산정보통신 주식회사",
    location: "부산광역시",
    detail_address: "부산광역시 소재",
    business_status_label: "정상영업 확인",
    license_or_business_type: "정보통신공사업",
    main_products: "영상장비 | 네트워크장비 | 통신공사",
    shopping_mall_status_label: "DB 등록정보 없음",
    mas_status_label: "DB 등록정보 없음",
    direct_production_certificate_status: "직접생산증명 정보 있음",
    policy_company_labels: "여성기업",
    certified_product_labels: "",
    sme_competition_product_label: "",
    recommended_checks: "면허 유효성 확인 | 직접생산 품목 일치 여부 확인",
    source_refreshed_at: "2026-06-10",
    review_score: 84,
  },
];

function text(value, fallback = "-") {
  if (value === null || value === undefined) return fallback;
  const normalized = String(value).trim();
  return normalized || fallback;
}

function splitValues(value) {
  return text(value, "")
    .split(/\s*\|\s*|,\s*|\n+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, idx, arr) => arr.indexOf(item) === idx);
}

function positiveText(value) {
  const normalized = text(value, "").trim();
  if (!normalized) return "";
  if (
    /없음|미확인|근거\s*없|정보\s*없|not\s*found|unknown|unavailable|false|^0$/i.test(normalized)
  ) {
    return "";
  }
  return normalized;
}

function evidenceTone(value, fallback = "neutral") {
  const normalized = text(value, "").trim();
  if (!normalized) return "warn";
  if (/일부|확인\s*필요|미확인|없음|근거\s*부족|주의|재확인|필요/i.test(normalized)) return "warn";
  if (/모두\s*충족|충족|등록|보유|확인|유효|대상|있음|match|true|valid/i.test(normalized)) return "good";
  return fallback;
}

function firstPositive(...values) {
  for (const value of values) {
    const normalized = positiveText(value);
    if (normalized) return normalized;
  }
  return "";
}

function conditionLabel(row) {
  return firstPositive(row.condition_match_type, evidenceLevel(row));
}

function conditionSummary(row) {
  const type = conditionLabel(row);
  const summary = firstPositive(row.condition_match_summary, row.requested_item_evidence_summary);
  return summary ? `${type} · ${summary}` : type;
}

function matchLabel(row) {
  return firstPositive(
    row.matched_query_label,
    row.primary_candidate_type,
    row.candidate_types,
    row.contract_review_types,
    row.license_status_label,
    "관련 부산업체",
  );
}

function evidenceItem(label, value, tone = null) {
  const normalized = text(value, "확인 필요");
  return {
    label,
    value: truncate(normalized, 150),
    tone: tone || evidenceTone(normalized),
  };
}

function directProductionEvidence(row) {
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
  const capacity = firstPositive(row.construction_capacity_match, row.construction_capacity_summary);
  const license = firstPositive(row.construction_license_match, row.construction_capacity_status_label);
  if (capacity && license) return `${license} · ${capacity}`;
  return capacity || license;
}

function policyEvidence(row) {
  return firstPositive(
    row.policy_company_labels,
    row.certified_product_summary,
    row.certified_product_labels,
    row.sme_competition_product_label,
    row.cooperative_purchase_route_label,
  );
}

function ventureEvidence(row) {
  return firstPositive(row.venture_nara_status_label, row.venture_nara_product_summary, row.venture_nara_order_summary);
}

function buildEvidenceItems(row) {
  const items = [
    evidenceItem("조건 충족도", conditionSummary(row), evidenceTone(row.condition_match_type)),
    evidenceItem("검색어-품목 근거", firstPositive(row.requested_item_evidence_summary, row.main_products) || "원천 DB 확인 필요"),
    evidenceItem("직접생산", directProductionEvidence(row) || "DB 등록 근거 없음", directProductionEvidence(row) ? "good" : "warn"),
    evidenceItem("MAS", masEvidence(row) || "DB 등록 근거 없음", masEvidence(row) ? "good" : "neutral"),
    evidenceItem("종합쇼핑몰", shoppingEvidence(row) || "DB 등록 근거 없음", shoppingEvidence(row) ? "good" : "neutral"),
    evidenceItem("면허/시공능력", constructionEvidence(row) || firstPositive(row.license_or_business_type) || "원천 DB 확인 필요"),
    evidenceItem("정책·인증", policyEvidence(row) || "해당 근거 없음", policyEvidence(row) ? "good" : "neutral"),
  ];
  const venture = ventureEvidence(row);
  if (venture) items.push(evidenceItem("벤처나라", venture, "good"));
  return items;
}

function buildCheckItems(row) {
  const checks = splitValues(row.recommended_checks);
  const condition = text(row.condition_match_type, "");
  if (/일부|부족|미확인|확인\s*필요/i.test(condition)) {
    checks.push("검색 조건 중 미충족 또는 근거 부족 항목 원천자료 확인");
  }
  if (!positiveText(row.business_status_label) || /폐업|휴업|미확인/i.test(text(row.business_status_label, ""))) {
    checks.push("사업자 영업상태 재확인");
  }
  if (!directProductionEvidence(row) && rowIsSmeCompetition(row)) {
    checks.push("중기간경쟁제품이면 직접생산확인증명 보유 여부 확인");
  }
  if (!masEvidence(row) && !shoppingEvidence(row)) {
    checks.push("조달청 쇼핑몰·MAS 등록 여부 별도 확인");
  }
  checks.push("공고 전 면허·인증·계약 가능 상태를 원천 사이트에서 재확인");
  return [...new Set(checks.map((item) => item.trim()).filter(Boolean))].slice(0, 6);
}

function renderEvidenceList(container, items) {
  container.innerHTML = "";
  items.forEach((item) => {
    const div = document.createElement("div");
    div.className = `evidence-item ${item.tone}`;
    div.innerHTML = `<span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong>`;
    container.appendChild(div);
  });
}

function renderCheckList(container, checks) {
  container.innerHTML = "";
  checks.forEach((check) => {
    const li = document.createElement("li");
    li.textContent = check;
    container.appendChild(li);
  });
}

function csvCell(value) {
  const normalized = text(value, "").replace(/\r?\n/g, " ");
  return `"${normalized.replaceAll('"', '""')}"`;
}

function rowsToCsv(rows) {
  const columns = [
    ["company_name", "업체명"],
    ["location", "지역"],
    ["detail_address", "상세주소"],
    ["business_status_label", "영업상태"],
    ["matched_query_label", "후보분류"],
    ["condition_match_type", "조건충족유형"],
    ["condition_match_summary", "조건충족요약"],
    ["requested_item_evidence_summary", "검색어품목근거"],
    ["license_or_business_type", "면허업종"],
    ["main_products", "주요품목"],
    ["direct_production_match", "직접생산근거"],
    ["mas_match", "MAS근거"],
    ["shopping_mall_match", "종합쇼핑몰근거"],
    ["construction_license_match", "공사면허근거"],
    ["construction_capacity_match", "시공능력근거"],
    ["policy_company_labels", "정책기업"],
    ["certified_product_labels", "인증제품"],
    ["sme_competition_product_label", "중기간경쟁제품"],
    ["venture_nara_status_label", "벤처나라"],
    ["recommended_checks", "확인필요항목"],
    ["review_score", "검토점수"],
    ["source_refreshed_at", "DB기준일"],
  ];
  const header = columns.map(([, label]) => csvCell(label)).join(",");
  const body = rows.map((row) => columns.map(([key]) => csvCell(row[key])).join(","));
  return [header, ...body].join("\r\n");
}

function updateDownloadState(enabled, detail = "") {
  els.downloadLink.classList.toggle("disabled", !enabled);
  els.downloadLink.setAttribute("aria-disabled", enabled ? "false" : "true");
  if (els.downloadDetail) {
    els.downloadDetail.textContent = detail || (enabled ? "현재 검색조건 기준 최대 100건 XLSX" : "검색 후 다운로드 가능");
  }
}

function downloadRecommendationXlsx() {
  if (lastSearchIsFallback || !lastSearchQuery) return;
  updateDownloadState(true, "XLSX 생성 요청");
  const url = `${API_BASE_URL}/vendor-recommendations/search.xlsx?q=${encodeURIComponent(lastSearchQuery)}&region=${encodeURIComponent("부산")}&limit=100&include_product_policy=true`;
  const a = document.createElement("a");
  a.href = url;
  a.download = "busan_vendor_recommendations.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  updateDownloadState(true, `상세 근거 최대 100건 XLSX`);
}

function hasPositive(value) {
  const normalized = text(value, "").toLowerCase();
  if (!normalized) return false;
  return !/없음|unknown|미확인|not|false|0/.test(normalized);
}

function escapeHtml(value) {
  return text(value, "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function truncate(value, max = 90) {
  const normalized = text(value, "");
  if (normalized.length <= max) return normalized || "-";
  return `${normalized.slice(0, max - 1)}…`;
}

function evidenceLevel(row) {
  const condition = text(row.condition_match_type, "");
  if (/모두\s*충족/i.test(condition)) return "조건 충족";
  if (/일부/i.test(condition)) return "일부 충족";
  if (/부족|미확인|확인\s*필요/i.test(condition)) return "확인 필요";
  const score = Number(row.review_score || 0);
  if (score >= 85) return "근거 충분";
  if (score >= 65) return "추가 확인";
  return "기본 후보";
}

function badge(label, tone = "neutral") {
  const span = document.createElement("span");
  span.className = `badge ${tone}`;
  span.textContent = label;
  return span;
}

function routeBadge(label, tone = "neutral") {
  const span = document.createElement("span");
  span.className = `route-badge ${tone}`;
  span.textContent = label;
  return span;
}

function buildBadges(row) {
  const badges = [badge("부산 후보", "info")];
  const condition = text(row.condition_match_type, "");

  if (/모두\s*충족/i.test(condition)) badges.push(badge("조건 모두 충족", "good"));
  else if (/일부/i.test(condition)) badges.push(badge("조건 일부 충족", "warn"));
  else if (condition) badges.push(badge("조건 확인 필요", "warn"));

  if (hasPositive(row.business_status_label) && !/폐업|휴업/.test(text(row.business_status_label, ""))) {
    badges.push(badge("정상영업", "good"));
  } else {
    badges.push(badge("영업상태 확인", "warn"));
  }

  if (hasPositive(row.license_or_business_type)) badges.push(badge("면허·업종", "neutral"));
  if (directProductionEvidence(row)) badges.push(badge("직접생산", "good"));
  if (masEvidence(row)) badges.push(badge("MAS", "info"));
  if (shoppingEvidence(row)) badges.push(badge("종합쇼핑몰", "info"));
  if (constructionEvidence(row)) badges.push(badge("면허·시공능력", "neutral"));
  if (hasPositive(row.policy_company_labels)) badges.push(badge("정책기업", "good"));
  if (hasPositive(row.certified_product_labels)) badges.push(badge("인증제품", "neutral"));
  if (hasPositive(row.sme_competition_product_label)) badges.push(badge("중기간경쟁 확인", "warn"));

  return badges;
}

function isTruthyValue(value) {
  const normalized = text(value, "").toLowerCase();
  return ["true", "1", "yes", "y", "valid"].includes(normalized);
}

function rowHasMas(row) {
  return isTruthyValue(row.has_mas) || hasPositive(row.mas_status_label) || hasPositive(row.mas_product_summary);
}

function rowHasShopping(row) {
  return (
    isTruthyValue(row.has_shopping_mall) ||
    hasPositive(row.shopping_mall_status_label) ||
    hasPositive(row.shopping_mall_product_summary)
  );
}

function rowHasDirectProduction(row) {
  return (
    hasPositive(row.direct_production_certificate_status) ||
    hasPositive(row.direct_production_certificate_products) ||
    hasPositive(row.direct_production_summary) ||
    hasPositive(row.direct_production_flags)
  );
}

function rowIsSmeCompetition(row) {
  return (
    isTruthyValue(row.is_sme_competition_product) ||
    /해당|중기간|중소기업자간/i.test(text(row.sme_competition_product_label, "")) ||
    /sme|competition|중소기업자간/i.test(text(row.procurement_attributes, ""))
  );
}

function summarizePurchaseRoute(data, rows) {
  const itemPolicy = data?.item_policy_summary || {};
  const policyStatus = text(itemPolicy.status, "");
  const matchedProducts = Array.isArray(itemPolicy.matched_products) ? itemPolicy.matched_products : [];
  const hasPolicyMatch = matchedProducts.length > 0 && !/not_found|unavailable/i.test(policyStatus);
  const hasMas = rows.some(rowHasMas);
  const hasShopping = rows.some(rowHasShopping);
  const hasDirect = rows.some(rowHasDirectProduction);
  const hasSme = rows.some(rowIsSmeCompetition) || /해당/.test(text(itemPolicy.sme_competition_product, ""));
  const hasVendorRows = rows.length > 0;

  const badges = [];
  const required = [];
  let title = "발주처 직접계약·입찰공고 검토형";
  let desc = "조달등록 부산업체 후보를 넓게 보되, 공고 전 면허·업종·영업상태를 확인해야 합니다.";
  let primary = "직접계약 또는 자체 입찰공고 검토";
  let ranking = "조달등록, 면허·업종, 정상영업 상태가 확인되는 업체를 우선 표시";

  if (hasShopping || hasMas) {
    title = "조달청 쇼핑몰/MAS 우선 검토형";
    desc = "종합쇼핑몰 또는 MAS 등록 여부가 구매 가능성 판단의 핵심입니다. 미등록 업체는 바로구매 후보가 아니라 관련 부산업체로 분리해야 합니다.";
    primary = hasMas ? "MAS/종합쇼핑몰 납품요구 우선 검토" : "종합쇼핑몰 등록업체 우선 검토";
    ranking = "MAS·종합쇼핑몰 등록, 직생, 정상영업 상태가 확인되는 업체를 우선 표시";
    badges.push(routeBadge("쇼핑몰/MAS 근거 있음", "info"));
    required.push("MAS/쇼핑몰 계약상태·납품조건");
  }

  if (hasSme) {
    title = hasMas || hasShopping ? "쇼핑몰/MAS + 중기간경쟁 확인형" : "중소기업자간 경쟁제품 확인형";
    badges.push(routeBadge("중기간경쟁 확인 필요", "warn"));
    required.push("중소기업자간 경쟁제품 해당 여부");
    ranking = "중기간경쟁 해당 시 직접생산확인 보유 업체를 우선 표시";
  }

  if (hasDirect) {
    badges.push(routeBadge("직접생산 근거 있음", "good"));
    required.push("직접생산확인 세부품명·유효기간");
  } else if (hasSme) {
    badges.push(routeBadge("직생 미확인 후보 주의", "warn"));
    required.push("직접생산확인 보유 여부");
  }

  if (hasPolicyMatch) {
    badges.push(routeBadge("품목정책 DB 매칭", "good"));
  } else {
    badges.push(routeBadge("품목정책 DB 확인 필요", "neutral"));
  }

  if (!hasVendorRows) {
    title = "후보 미확인";
    desc = "입력 조건에 맞는 후보가 아직 없습니다. 품목명, 세부품명, 면허명을 바꿔 확인해야 합니다.";
    primary = "검색조건 재확인";
    ranking = "후보 없음";
    required.push("검색어 정규화");
  }

  return {
    title,
    desc,
    primary,
    required: [...new Set(required)].join(" / ") || "면허·업종·영업상태 확인",
    ranking,
    badges,
  };
}

function renderPurchaseGuide(data, rows, isFallback = false) {
  if (!els.routeTitle) return;
  const summary = summarizePurchaseRoute(data || {}, rows || []);
  els.routeTitle.textContent = isFallback ? "샘플 기준 구매수단 적합성" : summary.title;
  els.routeDesc.textContent = isFallback
    ? "API 연결 전 샘플 데이터 기준입니다. 실제 판정은 업체 DB와 품목정책 DB 연결 후 확인해야 합니다."
    : summary.desc;
  els.routePrimary.textContent = summary.primary;
  els.routeRequired.textContent = summary.required;
  els.routeRanking.textContent = summary.ranking;
  els.routeBadges.innerHTML = "";
  summary.badges.forEach((item) => els.routeBadges.appendChild(item));
}

function procurementEvidence(row) {
  const items = [];
  if (directProductionEvidence(row)) items.push("직접생산");
  if (masEvidence(row)) items.push("MAS");
  if (shoppingEvidence(row)) items.push("종합쇼핑몰");
  if (constructionEvidence(row)) items.push("면허·시공능력");
  if (hasPositive(row.policy_company_labels)) items.push(text(row.policy_company_labels));
  if (hasPositive(row.certified_product_labels)) items.push(text(row.certified_product_labels));
  if (hasPositive(row.venture_nara_status_label)) items.push("벤처나라");
  return items.length ? items.join(" / ") : "DB 등록 근거 없음";
}

function sourceDate(rows) {
  const dates = rows
    .map((row) => text(row.source_refreshed_at, ""))
    .filter(Boolean)
    .map((item) => item.slice(0, 10));
  return dates[0] || "";
}

function findRateValue(obj, keys) {
  if (!obj || typeof obj !== "object") return "";
  for (const key of keys) {
    if (obj[key] !== undefined && obj[key] !== null && obj[key] !== "") return obj[key];
  }
  return "";
}

function findNestedRate(data, pathCandidates) {
  for (const path of pathCandidates) {
    let cur = data;
    for (const key of path) {
      if (!cur || typeof cur !== "object") {
        cur = null;
        break;
      }
      cur = cur[key];
    }
    const rate = findRateValue(cur, ["수주율", "rate", "award_rate", "local_rate"]);
    if (rate !== "") return rate;
  }
  return "";
}

function formatRate(value) {
  if (value === "" || value === null || value === undefined) return "";
  const numeric = Number(String(value).replace("%", ""));
  if (!Number.isFinite(numeric)) return String(value);
  return `${numeric.toFixed(1)}%`;
}

function formatKrwShort(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "-";
  if (numeric >= 100000000) return `${(numeric / 100000000).toFixed(1)}억`;
  if (numeric >= 10000) return `${Math.round(numeric / 10000).toLocaleString("ko-KR")}만`;
  return numeric.toLocaleString("ko-KR");
}

function setSectorMetric(el, value) {
  const label = formatRate(value);
  if (!label) return;
  el.textContent = label;
  const bar = el.parentElement?.querySelector("i");
  if (bar) bar.style.setProperty("--value", label);
}

async function loadMonitoringSummary() {
  if (!els.monitoringState) return;
  try {
    const response = await fetch(`${MONITORING_API_BASE_URL}/api/summary`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const overall = findNestedRate(data, [["1_전체"], ["summary"], ["overall"], ["전체"]]);
    const busanGroup = findNestedRate(data, [["3_그룹별", "부산광역시 및 소속기관"], ["by_group", "부산광역시 및 소속기관"]]);
    const nationalGroup = findNestedRate(data, [["3_그룹별", "정부 및 국가공공기관"], ["by_group", "정부 및 국가공공기관"]]);
    const construction = findNestedRate(data, [["2_분야별", "공사"], ["by_sector", "공사"]]);
    const service = findNestedRate(data, [["2_분야별", "용역"], ["by_sector", "용역"]]);
    const goods = findNestedRate(data, [["2_분야별", "물품"], ["by_sector", "물품"]]);
    const shopping = findNestedRate(data, [["2_분야별", "쇼핑몰"], ["by_sector", "쇼핑몰"]]);

    if (overall) els.metricOverall.textContent = formatRate(overall);
    if (busanGroup) els.metricBusanGroup.textContent = formatRate(busanGroup);
    if (nationalGroup) els.metricNationalGroup.textContent = formatRate(nationalGroup);
    if (construction) setSectorMetric(els.sectorConstruction, construction);
    if (service) setSectorMetric(els.sectorService, service);
    if (goods) setSectorMetric(els.sectorGoods, goods);
    if (shopping) setSectorMetric(els.sectorShopping, shopping);
    if (data.generated_at) els.metricGenerated.textContent = `생성 ${data.generated_at}`;
    els.monitoringState.textContent = "모니터링 지표 연결됨";
  } catch {
    els.monitoringState.textContent = "모니터링 지표는 API 연결 시 갱신";
  }
}

function leakageValue(item, names, fallback = "") {
  for (const name of names) {
    if (item && item[name] !== undefined && item[name] !== null && item[name] !== "") return item[name];
  }
  return fallback;
}

function renderLeakageItems(items) {
  if (!els.leakageList) return;
  els.leakageList.innerHTML = "";
  const visible = items.slice(0, 5);
  if (!visible.length) {
    els.leakageList.innerHTML = '<p class="side-muted">현재 표시할 쇼핑몰 주요 유출품목이 없습니다.</p>';
    return;
  }

  visible.forEach((item) => {
    const name = text(leakageValue(item, ["품목명", "item_name", "product_name"]), "품목명 미확인");
    const amount = leakageValue(item, ["유출액", "leakage_amount", "amount"], 0);
    const rate = leakageValue(item, ["유출율", "유출률", "leakage_rate"], "");
    const count = leakageValue(item, ["유출건수", "count"], "");
    const agency = text(leakageValue(item, ["주요수요기관", "agency"], ""), "");
    const busanSupplierCount = leakageValue(item, ["부산공급업체", "busan_supplier_count"], "");

    const button = document.createElement("button");
    button.type = "button";
    button.className = "leakage-item";
    button.innerHTML = `
      <span class="leakage-name">${escapeHtml(name)}</span>
      <span class="leakage-meta">
        <b>${escapeHtml(formatKrwShort(amount))}</b>
        <span>유출 ${escapeHtml(formatRate(rate) || "-")}</span>
        <span>${escapeHtml(text(count, "0"))}건</span>
      </span>
      <span class="leakage-sub">
        ${escapeHtml(agency || "주요수요기관 미확인")}
        ${busanSupplierCount !== "" ? ` · 부산공급 ${escapeHtml(text(busanSupplierCount))}` : ""}
      </span>
    `;
    button.addEventListener("click", () => {
      els.input.value = name;
      els.input.focus();
      els.form.requestSubmit();
    });
    els.leakageList.appendChild(button);
  });
}

async function loadShoppingLeakage() {
  if (!els.leakageList) return;
  try {
    const response = await fetch(`${MONITORING_API_BASE_URL}/api/leakage/shopping`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const items = data["유출품목"] || data["쇼핑몰_유출품목"] || data.items || [];
    renderLeakageItems(Array.isArray(items) ? items : []);
    if (els.leakageUpdated) {
      els.leakageUpdated.textContent = data.generated_at ? data.generated_at.slice(5, 16) : "연결됨";
    }
  } catch {
    els.leakageList.innerHTML = '<p class="side-muted">쇼핑몰 유출품목 API 연결이 필요합니다.</p>';
    if (els.leakageUpdated) els.leakageUpdated.textContent = "미연결";
  }
}

function renderRows(rows, query, totalCount, isFallback = false, responseData = {}) {
  lastSearchQuery = query;
  lastSearchRows = rows;
  lastSearchIsFallback = isFallback;
  els.candidateList.innerHTML = "";
  const visibleRows = rows.slice(0, DISPLAY_LIMIT);
  els.visibleCount.textContent = `${visibleRows.length}개 표시`;
  renderPurchaseGuide(responseData, rows, isFallback);

  if (!visibleRows.length) {
    const empty = document.createElement("article");
    empty.className = "empty-panel";
    empty.innerHTML = "<strong>조건에 해당하는 후보가 없습니다.</strong><span>검색어를 품목명, 세부품명, 면허명 중심으로 바꿔 다시 조회하세요.</span>";
    els.candidateList.appendChild(empty);
  }

  visibleRows.forEach((row, index) => {
    const node = els.template.content.cloneNode(true);
    node.querySelector(".candidate-rank").textContent = `후보 ${index + 1}`;
    node.querySelector(".candidate-name").textContent = text(row.company_name, "업체명 미확인");
    node.querySelector(".basis-level").textContent = evidenceLevel(row);
    node.querySelector(".candidate-location").textContent = [row.location, row.detail_address]
      .map((item) => text(item, ""))
      .filter(Boolean)
      .join(" · ") || "소재지 정보 확인 필요";

    const badgeRow = node.querySelector(".badge-row");
    buildBadges(row).forEach((item) => badgeRow.appendChild(item));

    const score = Number(row.review_score || row.match_rank_score || 0);
    node.querySelector(".score-pill").textContent = score ? `검토점수 ${score.toFixed(0)}` : "점수 미산정";
    node.querySelector(".match-label").textContent = truncate(matchLabel(row), 90);
    node.querySelector(".condition-summary").textContent = truncate(conditionLabel(row), 80);
    node.querySelector(".business-status").textContent = truncate(text(row.business_status_label, "영업상태 확인 필요"), 80);
    node.querySelector(".requested-evidence").textContent = truncate(
      firstPositive(row.requested_item_evidence_summary, row.condition_match_summary) || "검색어 기준 근거 확인",
      110,
    );
    renderEvidenceList(node.querySelector(".evidence-list"), buildEvidenceItems(row));
    renderCheckList(node.querySelector(".check-list"), buildCheckItems(row));

    node.querySelector(".main-products").textContent = truncate(splitValues(row.main_products).join(", "), 120);
    node.querySelector(".licenses").textContent = truncate(splitValues(row.license_or_business_type).join(", "), 120);
    node.querySelector(".procurement-evidence").textContent = truncate(procurementEvidence(row), 120);
    node.querySelector(".checks").textContent = truncate(buildCheckItems(row).join(", "), 150);

    els.candidateList.appendChild(node);
  });

  const countLabel = Number.isFinite(totalCount) ? totalCount : rows.length;
  els.summaryTitle.textContent = `관련 부산업체 후보 ${countLabel.toLocaleString("ko-KR")}개 확인`;
  els.summaryDesc.textContent = isFallback
    ? "API 연결 전 디자인 검토용 샘플을 표시 중입니다. 실제 결과는 서버 API 연결 후 확인해야 합니다."
    : `화면에는 대표 후보 ${visibleRows.length}개를 표시합니다. 전체 후보군은 CSV로 내려받아 비교 검토하세요.`;

  const date = sourceDate(rows);
  els.dataDate.textContent = date ? `DB 기준일 ${date}` : "DB 기준일 확인 필요";

  els.downloadLink.href = "#";
  updateDownloadState(!isFallback && rows.length > 0, rows.length > 0 ? "현재 검색조건 기준 최대 100건 XLSX" : "다운로드할 후보 없음");
}

async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    els.apiState.textContent = "API 연결됨";
    els.apiState.className = "state-pill state-ok";
  } catch {
    els.apiState.textContent = "API 미연결";
    els.apiState.className = "state-pill state-warn";
  }
}

async function search(query) {
  els.button.disabled = true;
  els.button.textContent = "조회 중";
  els.apiState.textContent = "조회 중";
  els.apiState.className = "state-pill state-muted";

  try {
    const url = `${API_BASE_URL}/vendor-recommendations/search?q=${encodeURIComponent(query)}&region=${encodeURIComponent("부산")}&limit=30&include_product_policy=true`;
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderRows(data.rows || [], query, Number(data.count || 0), false, data);
    els.apiState.textContent = "API 연결됨";
    els.apiState.className = "state-pill state-ok";
  } catch (error) {
    renderRows(sampleRows, query, sampleRows.length, true, {});
    els.apiState.textContent = "샘플 표시";
    els.apiState.className = "state-pill state-warn";
  } finally {
    els.button.disabled = false;
    els.button.textContent = "후보 조회";
  }
}

document.querySelectorAll(".sample-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    els.input.value = chip.dataset.query || chip.textContent.trim();
    els.input.focus();
  });
});

els.downloadLink.addEventListener("click", (event) => {
  event.preventDefault();
  if (els.downloadLink.classList.contains("disabled")) return;
  downloadRecommendationXlsx();
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

checkHealth();
loadMonitoringSummary();
loadShoppingLeakage();

const initialQuery = params.get("q");
if (initialQuery) {
  els.input.value = initialQuery;
  search(initialQuery);
}
