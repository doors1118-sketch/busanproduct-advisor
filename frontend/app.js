// Configuration
const params = new URLSearchParams(window.location.search);
const API_BASE_URL =
  params.get("api") ||
  (window.location.port === "8503" ? "http://127.0.0.1:8001" : "");

// DOM Elements
const els = {
    statusHealth: document.getElementById('status-health'),
    statusVersion: document.getElementById('status-version'),
    statusRag: document.getElementById('status-rag'),
    statusDeployment: document.getElementById('status-deployment'),
    
    agencyType: document.getElementById('agency-type'),
    userInput: document.getElementById('user-input'),
    btnSubmit: document.getElementById('btn-submit'),
    btnClear: document.getElementById('btn-clear'),
    
    progressIndicator: document.getElementById('progress-indicator'),
    progressText: document.getElementById('progress-text'),
    
    errorIndicator: document.getElementById('error-indicator'),
    
    outputSection: document.getElementById('output-section'),
    safetyBadges: document.getElementById('safety-badges'),
    answerContent: document.getElementById('answer-content'),
    candidateTableContent: document.getElementById('candidate-table-content'),
    metadataContent: document.getElementById('metadata-content'),
    btnDownloadMd: document.getElementById('btn-download-md'),
    btnDownloadCsv: document.getElementById('btn-download-csv')
};

const PROGRESS_STATES = [
    "질문 분석 중...",
    "지역업체 후보 검색 중...",
    "정책기업·인증제품 확인 중...",
    "법령·매뉴얼 근거 확인 중...",
    "안전 문구 검증 중..."
];

let progressInterval = null;
let currentRawAnswer = "";

function bindExampleChips() {
    const chips = document.querySelectorAll(".example-chip");
    chips.forEach((chip) => {
        chip.addEventListener("click", () => {
            const question = chip.dataset.question || chip.textContent.trim();
            els.userInput.value = question;
            els.userInput.focus();
        });
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkSystemStatus();
    
    els.btnSubmit.addEventListener('click', submitChat);
    els.btnClear.addEventListener('click', clearChat);
    
    if (els.btnDownloadMd) {
        els.btnDownloadMd.addEventListener('click', downloadMarkdown);
    }
    if (els.btnDownloadCsv) {
        els.btnDownloadCsv.addEventListener('click', downloadCsv);
    }
    
    bindExampleChips();
});

// System Status Checks
async function checkSystemStatus() {
    // Health
    try {
        const res = await fetch(`${API_BASE_URL}/health`);
        if (res.ok) {
            els.statusHealth.textContent = "OK";
            els.statusHealth.className = "badge success";
        } else {
            throw new Error("Bad status");
        }
    } catch (e) {
        els.statusHealth.textContent = "FAIL";
        els.statusHealth.className = "badge danger";
    }

    // Version
    try {
        const res = await fetch(`${API_BASE_URL}/version`);
        const data = await res.json();
        els.statusVersion.textContent = data.commit_hash ? data.commit_hash.substring(0, 7) : "Unknown";
        els.statusVersion.className = "badge success";
    } catch (e) {
        els.statusVersion.textContent = "FAIL";
        els.statusVersion.className = "badge danger";
    }

    // RAG Status
    try {
        const res = await fetch(`${API_BASE_URL}/rag/status`);
        const data = await res.json();
        let allSuccess = true;
        if (data.laws?.status !== "SUCCESS" && data.laws !== "SUCCESS") allSuccess = false;
        if (data.manuals?.status !== "SUCCESS" && data.manuals !== "SUCCESS") allSuccess = false;
        if (data.innovation?.status !== "SUCCESS" && data.innovation !== "SUCCESS") allSuccess = false;

        els.statusRag.textContent = allSuccess ? "Ready" : "Degraded";
        els.statusRag.className = allSuccess ? "badge success" : "badge warning";
    } catch (e) {
        els.statusRag.textContent = "FAIL";
        els.statusRag.className = "badge danger";
    }
}

// Security Check (Frontend Redaction)
function redactSensitiveInfo(text) {
    if (!text) return text;
    
    let redacted = text;
    // Business number: xxx-xx-xxxxx
    redacted = redacted.replace(/\d{3}-\d{2}-\d{5}/g, "<span class='sensitive-warning'>[사업자번호 보호됨]</span>");
    
    // API Keys (Simple heuristic for GEMINI/AWS/etc)
    redacted = redacted.replace(/AIza[0-9A-Za-z-_]{35}/g, "<span class='sensitive-warning'>[API 키 보호됨]</span>");
    redacted = redacted.replace(/AKIA[0-9A-Z]{16}/g, "<span class='sensitive-warning'>[API 키 보호됨]</span>");
    
    // Env vars
    if (redacted.includes("GEMINI_API_KEY") || redacted.includes("LAW_API_OC")) {
         redacted = redacted.replace(/GEMINI_API_KEY\s*=\s*\S+/g, "<span class='sensitive-warning'>[환경변수 보호됨]</span>");
         redacted = redacted.replace(/LAW_API_OC\s*=\s*\S+/g, "<span class='sensitive-warning'>[환경변수 보호됨]</span>");
    }
    
    // Traceback
    if (redacted.includes("Traceback (most recent call last):") || redacted.includes("Traceback")) {
        // Just replace the whole thing or a chunk
        redacted = redacted.replace(/Traceback[\s\S]*?(?=\n\n|\Z)/g, "<span class='sensitive-warning'>[시스템 오류 메시지 보호됨]</span>");
    }
    
    return redacted;
}

// Submit Chat
async function submitChat() {
    const message = els.userInput.value.trim();
    const agencyType = els.agencyType.value || "default";
    
    if (!message) return;

    // UI Reset
    els.outputSection.classList.add('hidden');
    els.errorIndicator.classList.add('hidden');
    els.btnSubmit.disabled = true;
    els.progressIndicator.classList.remove('hidden');
    
    // Start Progress Spinner Texts
    let pIdx = 0;
    els.progressText.textContent = PROGRESS_STATES[pIdx];
    progressInterval = setInterval(() => {
        pIdx = (pIdx + 1) % PROGRESS_STATES.length;
        els.progressText.textContent = PROGRESS_STATES[pIdx];
    }, 4000);

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 120000); // 120s timeout

        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                agency_type: agencyType,
                history: []
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            let errorMsg = "API 오류가 발생했습니다.";
            if (response.status === 429 || response.status === 503) {
                errorMsg = "일부 외부 API 또는 데이터 조회가 지연되어 답변이 제한될 수 있습니다. 계약 전 관련 법령과 기관 내부 기준을 추가 확인하세요.";
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();
        renderOutput(data);

    } catch (error) {
        showDegradedError(error.message === "The user aborted a request." 
            ? "응답이 지연되고 있습니다. 외부 API 또는 모델 응답 지연 가능성이 있습니다." 
            : error.message);
    } finally {
        clearInterval(progressInterval);
        els.progressIndicator.classList.add('hidden');
        els.btnSubmit.disabled = false;
    }
}

function renderOutput(data) {
    els.outputSection.classList.remove('hidden');
    
    // 1. Safety Badges
    els.safetyBadges.innerHTML = '';
    
    const badges = [];
    
    if (data.legal_conclusion_allowed === false) {
        badges.push(`<span class="safety-badge warn">⚠️ 법적 결론 유보</span>`);
    }
    if (data.contract_possible_auto_promoted === false) {
        badges.push(`<span class="safety-badge ok">🔒 계약 가능 자동확정 없음</span>`);
    }
    if (Array.isArray(data.forbidden_patterns_remaining_after_rewrite) && data.forbidden_patterns_remaining_after_rewrite.length === 0) {
        badges.push(`<span class="safety-badge ok">✅ 금지표현 검사 통과</span>`);
    }
    if (data.candidate_table_source === "server_structured_formatter") {
        badges.push(`<span class="safety-badge ok">📊 서버 생성 후보표</span>`);
    }
    if (data.production_deployment === "HOLD") {
        badges.push(`<span class="safety-badge warn">🛑 운영 배포 HOLD</span>`);
    }
    
    els.safetyBadges.innerHTML = badges.join('');

    // 2. Answer
    let rawAnswer = data.answer || "답변을 생성하지 못했습니다.";
    
    // Frontend Security Redaction
    rawAnswer = redactSensitiveInfo(rawAnswer);
    currentRawAnswer = rawAnswer;
    
    // Render Markdown
    els.answerContent.innerHTML = DOMPurify.sanitize(marked.parse(rawAnswer));
    
    // Check if table exists for CSV download
    if (els.btnDownloadCsv) {
        if (rawAnswer.includes("|") && rawAnswer.includes("---")) {
            els.btnDownloadCsv.disabled = false;
            els.btnDownloadCsv.title = "";
        } else {
            els.btnDownloadCsv.disabled = true;
            els.btnDownloadCsv.title = "다운로드할 후보표가 없습니다";
        }
    }
    
    // 3. Metadata Whitelist
    const safeMetadata = {
        candidate_table_source: data.candidate_table_source,
        legal_conclusion_allowed: data.legal_conclusion_allowed,
        contract_possible_auto_promoted: data.contract_possible_auto_promoted,
        forbidden_patterns_remaining_after_rewrite: data.forbidden_patterns_remaining_after_rewrite,
        final_answer_scanned: data.final_answer_scanned,
        sensitive_fields_detected: data.sensitive_fields_detected,
        model_selected: data.model_selected,
        model_decision_reason: data.model_decision_reason,
        latency_ms: data.latency_ms,
        production_deployment: data.production_deployment
    };
    els.metadataContent.textContent = JSON.stringify(safeMetadata, null, 2);
    
    // Degraded check
    if (data.result_status === "DEGRADED") {
        showDegradedError("일부 외부 API 또는 데이터 조회가 지연되어 답변이 제한될 수 있습니다. 계약 전 관련 법령과 기관 내부 기준을 추가 확인하세요.");
    }
}

function showDegradedError(msg) {
    els.errorIndicator.textContent = msg;
    els.errorIndicator.classList.remove('hidden');
}

function clearChat() {
    els.userInput.value = '';
    els.outputSection.classList.add('hidden');
    els.errorIndicator.classList.add('hidden');
}

function downloadMarkdown() {
    if (!currentRawAnswer) return;
    const blob = new Blob([currentRawAnswer], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '검토결과.md';
    a.click();
    URL.revokeObjectURL(url);
}

function sanitizeCsvCell(value) {
    const text = String(value ?? "");
    const redacted = redactSensitiveInfo(text).replace(/<[^>]*>/g, "");
    const trimmed = redacted.trim();

    if (/^[=+\-@]/.test(trimmed)) {
        return "'" + redacted;
    }
    return redacted;
}

function csvEscape(value) {
    const safe = sanitizeCsvCell(value);
    return `"${safe.replace(/"/g, '""')}"`;
}

function downloadCsv() {
    if (!currentRawAnswer) return;
    
    // Extract markdown table
    const lines = currentRawAnswer.split('\n');
    let csvContent = "";
    let inTable = false;
    
    for (const line of lines) {
        if (line.trim().startsWith('|')) {
            inTable = true;
            // Skip the separator line
            if (line.includes('---')) continue;
            
            // Basic markdown table parsing with CSV Injection guard
            const row = line.split('|').slice(1, -1).map(cell => {
                return csvEscape(cell);
            });
            csvContent += row.join(',') + '\n';
        } else {
            if (inTable) break; // First table only
        }
    }
    
    if (!csvContent) return;
    
    // Add BOM for Excel UTF-8
    const bom = new Uint8Array([0xEF, 0xBB, 0xBF]);
    const blob = new Blob([bom, csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '후보표.csv';
    a.click();
    URL.revokeObjectURL(url);
}
