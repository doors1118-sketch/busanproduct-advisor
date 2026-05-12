"""
부산 공공조달 AI 챗봇 — FastAPI REST API 서버
Streamlit UI와 병행 구조. gemini_engine.chat()을 wrapping.
Production deployment: HOLD
"""
import os
import sys
import time
import subprocess
import traceback
import json
import queue
import threading
from io import BytesIO
from datetime import datetime

# app 디렉터리를 Python 경로에 추가
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
sys.path.insert(0, APP_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path
import secrets
import base64

# ─────────────────────────────────────────────
# Set Default Chroma Paths
# ─────────────────────────────────────────────
if "CHROMA_DIR" not in os.environ:
    os.environ["CHROMA_DIR"] = os.path.join(PROJECT_ROOT, "app", ".chroma")
if "CHROMA_LAWS_DIR" not in os.environ:
    os.environ["CHROMA_LAWS_DIR"] = os.path.join(PROJECT_ROOT, "app", ".chroma")
if "CHROMA_MANUALS_DIR" not in os.environ:
    os.environ["CHROMA_MANUALS_DIR"] = os.path.join(PROJECT_ROOT, "app", ".chroma")
if "CHROMA_INNOVATION_DIR" not in os.environ:
    os.environ["CHROMA_INNOVATION_DIR"] = os.path.join(PROJECT_ROOT, "app", ".chroma")

print("CHROMA_DIR default set to:", os.environ["CHROMA_DIR"])

# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────
app = FastAPI(
    title="부산 공공조달 AI 챗봇 API",
    description="Gemini + RAG 기반 공공조달 법령 챗봇 REST API. Production deployment: HOLD.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PRODUCTION_DEPLOYMENT = "HOLD"
SERVER_STARTED_AT = time.time()

# ─────────────────────────────────────────────
# Pilot Basic Auth Middleware (DISABLED)
# ─────────────────────────────────────────────
@app.middleware("http")
async def pilot_auth_middleware(request: Request, call_next):
    # 사용자의 요청에 따라 모든 비밀번호/인증 로직 무효화 (프리패스)
    return await call_next(request)

# ─────────────────────────────────────────────
# Frontend StaticFiles Mount
# ─────────────────────────────────────────────
FRONTEND_DIR = Path(PROJECT_ROOT) / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

@app.get("/")
def root():
    return {
        "service": "busanproduct-advisor-api",
        "ui": "/ui",
        "health": "/health",
        "production_deployment": PRODUCTION_DEPLOYMENT
    }


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., description="사용자 질문")
    agency_type: Optional[str] = Field(None, description="소속기관 유형 (예: local_government)")
    history: list = Field(default_factory=list, description="대화 이력")


class ChatResponse(BaseModel):
    answer: str
    history: list = []
    qa_log_id: str = ""
    candidate_table_source: str = "not_exposed_yet"
    candidate_export_available: bool = False
    legal_conclusion_allowed: bool = False
    contract_possible_auto_promoted: bool = False
    forbidden_patterns_remaining_after_rewrite: list = []
    final_answer_scanned: bool = True
    post_scan_policy_version: str = ""
    post_scan_critical_count: int = 0
    post_scan_warning_count: int = 0
    post_scan_warning_patterns: list = []
    sensitive_fields_detected: list = []
    model_selected: str = ""
    model_decision_reason: str = ""
    latency_ms: int = 0
    rag_status: dict = {}
    production_deployment: str = PRODUCTION_DEPLOYMENT
    # 지역업체 경로 안내 확장 필드
    route_guidance_provided: bool = False
    regional_route_guidance_provided: bool = False
    amount_detected: Optional[int] = None
    amount_band: Optional[str] = None
    candidate_counts_by_type: dict = {}
    source_call_statuses: dict = {}
    sensitive_fields_removed: bool = True
    enrichment_join_key_redacted: bool = True
    # Latency breakdown & tools
    total_latency_ms: Optional[int] = None
    rag_elapsed_ms: Optional[int] = None
    model_elapsed_ms: Optional[int] = None
    rewrite_elapsed_ms: Optional[int] = None
    tool_elapsed_ms_by_name: dict = {}
    tool_call_count: int = 0
    tool_args_log: list = []
    fast_track_applied: bool = False
    deterministic_template_used: bool = False
    
    # Phase 4 (Orchestration)
    tier_resolved: int = 1
    answer_schema_version: str = "regional_procurement_v1"
    mandatory_mcp_plan: list = []
    mandatory_mcp_executed: list = []
    mandatory_mcp_missing: list = []
    intent_frame: dict = {}
    route_plan: dict = {}
    evidence_cards: list = []
    evidence_card_count: int = 0
    internal_db_hit_count: int = 0
    external_mcp_fallback_count: int = 0
    evidence_missing_count: int = 0
    mcp_chain_statuses: dict = {}
    admin_rule_call_statuses: dict = {}
    pps_rule_call_statuses: dict = {}
    mcp_preflight_elapsed_ms: Optional[int] = None
    legal_basis_cache_used: bool = False
    legal_basis_cache_hit_count: int = 0
    legal_basis_cache_miss_count: int = 0
    mcp_called_for_cache_miss: bool = False
    mcp_called_for_freshness: bool = False
    cache_status: str = ""
    source_status: str = ""
    
    # Phase 2: 업체 데이터 상태 분리
    company_cache_used: bool = False
    company_cache_refreshed_at: Optional[str] = None
    company_cache_age_hours: Optional[float] = None
    company_source_status: str = "no_company_query"
    company_source_status_user_label: str = "업체검색 불필요"
    company_search_status: str = "not_called"
    company_data_sources_used: list = []
    company_cache_mode: str = "none"
    
    # Phase 5 Orchestration Metadata
    answer_builder_used: Optional[str] = None
    answer_sections_rendered: list = []
    candidate_section_position: int = -1
    legal_basis_section_rendered: bool = False
    user_facing_source_labels_used: bool = False
    raw_tool_names_hidden_from_answer: bool = False
    legal_basis_table_rendered: bool = False
    source_status_user_label: str = ""
    legal_basis_to_purchase_route_mapped: bool = False
    answer_builder_elapsed_ms: int = 0
    answer_builder_network_call_count: int = 0
    practice_manual_card_count: int = 0
    pps_qa_card_count: int = 0
    tool_loop_gate_mode: str = "shadow"
    tool_loop_gate_recommendation: str = ""
    tool_loop_gate_evidence_sufficiency_score: float = 0.0
    tool_loop_gate_should_allow_loop: bool = True
    tool_loop_gate_can_use_writer_only: bool = False
    tool_loop_gate_enforced: bool = False
    tool_loop_gate_reasons: list = []
    tool_loop_gate_blockers: list = []
    tool_loop_gate_missing_supports: list = []
    intent_rag_enabled: bool = False
    intent_rag_status: str = ""
    intent_rag_primary_intent: str = ""
    intent_rag_labels: list = []
    intent_rag_sub_intents: list = []
    intent_rag_answer_mode: str = ""
    intent_rag_confidence: float = 0.0
    intent_rag_confidence_level: str = ""
    intent_rag_company_search_required: bool = False
    intent_rag_company_search_blocked: bool = False
    intent_rag_local_purchase_support_required: bool = False
    intent_rag_contract_review_required: bool = False
    intent_rag_procedure_required: bool = False
    intent_rag_legal_basis_required: bool = False
    intent_rag_llm_router_required: bool = True
    intent_rag_corpus_record_count: int = 0
    intent_rag_item_name: str = ""
    intent_rag_contract_object: str = ""
    intent_rag_amount: Optional[int] = None
    intent_rag_reasons: list = []
    intent_rag_matched_examples: list = []
    llm_adjudicator_enabled: bool = False
    llm_adjudicator_required: bool = False
    llm_adjudicator_called: bool = False
    llm_adjudicator_status: str = ""
    llm_adjudicator_elapsed_ms: int = 0
    llm_adjudicator_reasons: list = []
    llm_adjudicator_conflicts: list = []
    llm_adjudicator_missing_slots: list = []
    llm_adjudicator_labels_before: list = []
    llm_adjudicator_labels_after: list = []
    # Payload/context telemetry for latency analysis
    mcp_context_mode_requested: str = ""
    mcp_context_mode_applied: str = ""
    mcp_context_raw_chars: int = 0
    mcp_context_card_chars: int = 0
    mcp_context_llm_chars: int = 0
    mcp_context_char_savings_pct: float = 0.0
    tool_response_context_raw_chars: int = 0
    tool_response_context_llm_chars: int = 0
    tool_response_context_char_savings_pct: float = 0.0
    tool_response_context_card_count: int = 0
    tool_response_context_compressed_count: int = 0
    tool_response_context_modes: dict = {}
    llm_payload_core_prompt_chars: int = 0
    llm_payload_dynamic_context_chars: int = 0
    llm_payload_rag_context_chars: int = 0
    llm_payload_mcp_context_chars: int = 0
    llm_payload_practice_context_chars: int = 0
    llm_payload_pps_qa_context_chars: int = 0
    llm_payload_route_plan_guidance_chars: int = 0
    llm_payload_intent_rag_guidance_chars: int = 0
    llm_payload_router_guidance_chars: int = 0
    llm_payload_tool_count_available: int = 0
    llm_payload_initial_contents_chars: int = 0
    llm_payload_max_contents_chars: int = 0
    llm_payload_after_tool_response_chars: int = 0
    llm_payload_after_forced_prefetch_chars: int = 0
    llm_payload_model_round_count: int = 0
    llm_payload_model_timeout_count: int = 0
    llm_payload_model_error_statuses: list = []
    llm_answer_thinking_budget: int = 0
    llm_answer_thinking_budget_reason: str = ""
    llm_tool_loop_enabled: bool = False
    llm_internal_tools_disabled: bool = True
    natural_language_writer_enabled: bool = False
    natural_language_writer_applied: bool = False
    natural_language_writer_mode: str = ""
    natural_language_writer_model: str = ""
    natural_language_writer_reason: str = ""
    natural_language_writer_skip_reason: str = ""
    natural_language_writer_elapsed_ms: int = 0
    natural_language_writer_split_mode: str = ""
    natural_language_writer_target_chars: int = 0
    natural_language_writer_suffix_chars: int = 0
    natural_language_writer_output_chars: int = 0
    natural_language_writer_table_preserved: bool = False

    # Phase 11: Orchestrator Pipeline Metadata
    pipeline_mode: str = ""  # orchestrator / legacy_gemini
    runtime_status: str = ""  # success / degraded / failed
    routing_decision: str = ""
    primary_intent: str = ""
    routing_confidence_score: float = 0.0
    routing_confidence_level: str = ""
    routing_ambiguous: bool = False
    routing_ambiguity_reasons: list = []
    routing_required_slots_missing: list = []
    routing_confidence_action: str = ""
    runtime_stages: list = []
    forbidden_phrase_scan_passed: bool = True
    blocked_phrases_found: list = []


class QaFeedbackRequest(BaseModel):
    qa_log_id: Optional[str] = Field(None, description="ChatResponse.qa_log_id")
    rating: Optional[int] = Field(None, ge=1, le=5, description="1=매우 불만족, 5=매우 만족")
    satisfied: Optional[bool] = Field(None, description="간단 만족/불만족")
    issue_tags: list = Field(default_factory=list, description="의도틀림/근거부족/느림 등")
    comment: Optional[str] = Field("", description="사용자 자유 의견")
    expected_intent: Optional[str] = Field("", description="운영자/테스터가 보는 기대 의도")
    corrected_answer: Optional[str] = Field("", description="운영자/테스터가 보는 수정 답변")
    question: Optional[str] = Field("", description="qa_log_id가 없을 때 보조 질문")
    answer_excerpt: Optional[str] = Field("", description="qa_log_id가 없을 때 보조 답변 일부")
    source: Optional[str] = Field("user", description="user/tester/operator")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _get_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=PROJECT_ROOT,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _client_is_local(request: Request) -> bool:
    host = getattr(getattr(request, "client", None), "host", "") or ""
    return host in {"127.0.0.1", "::1", "localhost"} or host.startswith("127.")


def _admin_health_authorized(request: Request) -> bool:
    """Detailed health is localhost-only unless ADMIN_HEALTH_TOKEN is configured."""
    token = os.getenv("ADMIN_HEALTH_TOKEN", "").strip()
    if not token:
        return _client_is_local(request)

    header_token = request.headers.get("X-Admin-Token", "").strip()
    auth = request.headers.get("Authorization", "").strip()
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    return secrets.compare_digest(header_token, token) or secrets.compare_digest(bearer, token)


def _candidate_export_requested(question: str) -> bool:
    q = (question or "").replace(" ", "").lower()
    return any(term in q for term in ("업체", "후보", "추천", "공급사", "부산업체", "지역업체"))


def _candidate_policy_labels(candidate: dict) -> list[str]:
    label_map = {
        "women_company": "여성기업",
        "disabled_company": "장애인기업",
        "social_enterprise": "사회적기업",
        "social_cooperative": "사회적협동조합",
        "youth_startup": "청년창업기업",
        "startup": "창업기업",
        "venture_company": "벤처기업",
    }
    raw_values = []
    for key in ("policy_subtypes", "policy_tags"):
        value = candidate.get(key) or []
        if isinstance(value, str):
            raw_values.extend(part.strip() for part in value.split("|"))
        else:
            raw_values.extend(str(part).strip() for part in value if str(part).strip())
    labels: list[str] = []
    for raw in raw_values:
        label = label_map.get(raw, raw)
        if label and label not in labels:
            labels.append(label)
    return labels


def _candidate_rows_from_results(results: list[tuple[str, list[dict]]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_label, candidates in results:
        for candidate in candidates:
            key = str(candidate.get("company_id") or candidate.get("company_name") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append({
                "조회기준": source_label,
                "업체명": str(candidate.get("company_name") or "").strip(),
                "소재지": str(candidate.get("location") or "").strip(),
                "면허·업종": ", ".join(candidate.get("license_or_business_type") or []),
                "주요 품목·업무": ", ".join(candidate.get("main_products") or []),
                "정책기업": ", ".join(_candidate_policy_labels(candidate)),
                "쇼핑몰/MAS": ", ".join(candidate.get("shopping_mall_flags") or []),
                "검토 메모": "면허·품목·영업상태·직접수행 여부 재확인 필요",
            })
    return rows


def _generic_candidate_export_rows(question: str, *, limit: int = 200) -> list[dict[str, str]]:
    try:
        import company_db
    except Exception:
        return []

    q = question or ""
    searches: list[tuple[str, str, str]] = []
    if any(term in q for term in ("천연잔디", "잔디 조성", "잔디조성", "잔디 식재", "잔디시공", "운동장 잔디", "운동장잔디")):
        searches.extend([
            ("품목: 잔디", "product", "잔디"),
            ("품목: 조경식재공사", "product", "조경식재공사"),
            ("품목: 토양개량", "product", "토양개량"),
            ("품목: 복합비료", "product", "복합비료"),
            ("면허: 조경식재공사업", "license", "조경식재공사업"),
            ("면허: 조경식재ㆍ시설물공사업", "license", "조경식재ㆍ시설물공사업"),
            ("업체명: 에코그린", "company_name", "에코그린"),
        ])
    elif "조경" in q:
        searches.extend([
            ("면허: 조경공사업", "license", "조경공사업"),
            ("면허: 조경식재공사업", "license", "조경식재공사업"),
            ("면허: 조경식재ㆍ시설물공사업", "license", "조경식재ㆍ시설물공사업"),
            ("면허: 조경시설물설치공사업", "license", "조경시설물설치공사업"),
            ("품목: 조경식재공사", "product", "조경식재공사"),
            ("품목: 기타조경시설물", "product", "기타조경시설물"),
            ("업체명: 에코그린", "company_name", "에코그린"),
        ])
    else:
        product_terms = [
            "컴퓨터", "노트북", "서버", "데스크톱", "프린터", "보안용카메라", "CCTV",
            "소프트웨어", "번역", "청소", "경비", "냉난방기", "에어컨",
        ]
        for term in product_terms:
            if term.lower() in q.lower():
                searches.append((f"품목: {term}", "product", term))
                searches.append((f"면허/업종: {term}", "license", term))

    results: list[tuple[str, list[dict]]] = []
    for source_label, search_type, term in searches:
        try:
            if search_type == "product":
                data = company_db.search_by_product(term, limit=limit)
            elif search_type == "license":
                data = company_db.search_by_license(term, limit=limit)
            else:
                data = company_db.search_by_company_name(term, limit=limit)
        except Exception:
            data = None
        candidates = (data or {}).get("candidates") or []
        if candidates:
            results.append((source_label, candidates))
    return _candidate_rows_from_results(results)


def _build_candidate_export_xlsx(question: str) -> bytes | None:
    rows = _generic_candidate_export_rows(question)
    if not rows:
        return None
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "업체후보"
    headers = ["조회기준", "업체명", "소재지", "면허·업종", "주요 품목·업무", "정책기업", "쇼핑몰/MAS", "검토 메모"]
    ws.append(headers)
    for row in rows:
        ws.append([row.get(header, "") for header in headers])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center")
    for idx, width in enumerate([18, 28, 18, 46, 34, 20, 22, 36], 1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"

    summary = wb.create_sheet("안내")
    summary.append(["항목", "내용"])
    summary.append(["원 질문", question])
    summary.append(["주의", "이 엑셀은 내부 DB 조회 후보 목록입니다. 낙찰 가능, 수의계약 가능, 면허 적격을 확정하지 않습니다. 공고 전 면허·주력분야·영업상태·실적·직접수행 여부를 다시 확인하세요."])
    for cell in summary[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    summary.column_dimensions["A"].width = 18
    summary.column_dimensions["B"].width = 120
    summary["B3"].alignment = Alignment(wrap_text=True, vertical="top")

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def _find_qa_log_by_id(qa_log_id: str) -> dict | None:
    log_dir = Path(APP_DIR) / "data" / "qa_test_logs"
    if not qa_log_id or not log_dir.exists():
        return None
    for path in sorted(log_dir.glob("qa_log_*.jsonl"), reverse=True):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("qa_log_id") == qa_log_id:
                    return record
        except Exception:
            continue
    return None


def _json_file_status(relative_path: str, *, max_count_bytes: int = 8_000_000) -> dict:
    path = Path(PROJECT_ROOT) / relative_path
    info = {
        "path": relative_path,
        "exists": path.exists(),
        "status": "missing",
        "size_bytes": 0,
        "modified_at": None,
        "record_count": None,
    }
    if not path.exists():
        return info

    stat = path.stat()
    info.update({
        "status": "ok",
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    })
    if stat.st_size <= max_count_bytes and path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                info["record_count"] = len(data)
            elif isinstance(data, list):
                info["record_count"] = len(data)
        except Exception as e:
            info["status"] = "read_error"
            info["error"] = str(e)[:200]
    return info


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_data_file_health() -> dict:
    files = {
        "law_articles": "app/data/law_articles_db.json",
        "admin_rules": "app/data/admin_rules_db.json",
        "law_annexes": "app/data/law_annexes_db.json",
        "admin_rule_annexes": "app/data/admin_rule_annexes_db.json",
        "pps_qa_cases": "app/data/pps_qa_cases.json",
        "practice_manual_cards": "app/data/practice_manual_cards.json",
        "intent_rag_corpus": "app/data/intent_rag_corpus.json",
        "purchase_support_source_map": "app/data/purchase_support_rule_source_map.json",
    }
    result = {name: _json_file_status(path) for name, path in files.items()}
    required = ("law_articles", "admin_rules", "pps_qa_cases", "practice_manual_cards", "intent_rag_corpus")
    missing_required = [name for name in required if not result[name]["exists"]]
    return {
        "status": "critical" if missing_required else "ok",
        "missing_required": missing_required,
        "files": result,
    }


def _get_routing_runtime_settings() -> dict:
    try:
        from app.router.llm_route_adjudicator import (
            RAG_HIGH_CONFIDENCE,
            RAG_LOW_CONFIDENCE,
            RAG_VERY_HIGH_CONFIDENCE,
        )
    except Exception:
        try:
            from router.llm_route_adjudicator import (
                RAG_HIGH_CONFIDENCE,
                RAG_LOW_CONFIDENCE,
                RAG_VERY_HIGH_CONFIDENCE,
            )
        except Exception:
            RAG_LOW_CONFIDENCE, RAG_HIGH_CONFIDENCE, RAG_VERY_HIGH_CONFIDENCE = 0.58, 0.78, 0.86

    try:
        from app.router.gemini_intent_router import resolve_router_client_config
    except Exception:
        try:
            from router.gemini_intent_router import resolve_router_client_config
        except Exception:
            resolve_router_client_config = None

    router_client_config = (
        resolve_router_client_config() if resolve_router_client_config is not None else {}
    )
    adjudicator_enabled = os.getenv(
        "USE_GEMINI_ROUTE_ADJUDICATOR",
        os.getenv("USE_GEMINI_INTENT_ROUTER_IN_LEGACY", "true"),
    ).lower() == "true"
    return {
        "prompt_mode": os.getenv("PROMPT_MODE", "legacy"),
        "model_routing_mode": os.getenv("MODEL_ROUTING_MODE", "risk_based"),
        "model_primary": os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        "fallback_model": os.getenv("FALLBACK_MODEL", "gemini-2.5-flash"),
        "gemini_api_key_configured": bool(os.getenv("GEMINI_API_KEY")),
        "gemini_router_provider": router_client_config.get("provider", "unknown"),
        "gemini_router_vertex_project": router_client_config.get("project", ""),
        "gemini_router_vertex_location": router_client_config.get("location", ""),
        "llm_adjudicator_enabled": adjudicator_enabled,
        "gemini_router_model": os.getenv("GEMINI_ROUTER_MODEL", "gemini-2.5-flash"),
        "gemini_router_thinking_budget": _env_int("GEMINI_ROUTER_THINKING_BUDGET", 0),
        "gemini_adjudicator_thinking_budget": _env_int("GEMINI_ADJUDICATOR_THINKING_BUDGET", 128),
        "gemini_route_adjudicator_timeout_sec": _env_float("GEMINI_ROUTE_ADJUDICATOR_TIMEOUT_SEC", 3.0),
        "gemini_pro_fallback_enabled": os.getenv("GEMINI_PRO_FALLBACK_ENABLED", "true").lower() == "true",
        "tool_loop_gate_mode": os.getenv("TOOL_LOOP_GATE_MODE", "shadow").lower(),
        "llm_tool_loop_enabled": os.getenv("LLM_TOOL_LOOP_ENABLED", "false").lower() == "true",
        "llm_internal_tools_disabled": os.getenv("LLM_TOOL_LOOP_ENABLED", "false").lower() != "true",
        "natural_language_writer_enabled": os.getenv("NATURAL_LANGUAGE_WRITER_ENABLED", "false").lower() == "true",
        "natural_language_writer_mode": os.getenv("NATURAL_LANGUAGE_WRITER_MODE", "selective"),
        "natural_language_writer_model": os.getenv("NATURAL_LANGUAGE_WRITER_MODEL", "gemini-2.5-flash"),
        "natural_language_writer_timeout_sec": _env_float("NATURAL_LANGUAGE_WRITER_TIMEOUT_SEC", 15.0),
        "natural_language_writer_max_input_chars": _env_int("NATURAL_LANGUAGE_WRITER_MAX_INPUT_CHARS", 3500),
        "max_tool_call_rounds": _env_int("MAX_TOOL_CALL_ROUNDS", 2),
        "intent_rag_thresholds": {
            "low": RAG_LOW_CONFIDENCE,
            "high": RAG_HIGH_CONFIDENCE,
            "very_high": RAG_VERY_HIGH_CONFIDENCE,
        },
    }


def _get_intent_rag_health() -> dict:
    try:
        try:
            from app.router.intent_rag_resolver import get_intent_rag_corpus_status
        except Exception:
            from router.intent_rag_resolver import get_intent_rag_corpus_status
        status = get_intent_rag_corpus_status()
        return {
            "status": "ok" if status.get("available") else "warning",
            **status,
        }
    except Exception as e:
        return {"status": "critical", "error": str(e)[:300]}


def _probe_company_api() -> dict:
    base_url = os.getenv("MONITORING_COMPANY_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    if os.getenv("ADMIN_HEALTH_PROBE_COMPANY_API", "true").lower() != "true":
        return {"status": "skipped", "base_url": base_url}
    try:
        import requests
        start = time.time()
        response = requests.get(f"{base_url}/health", timeout=1.2)
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "status": "ok" if response.status_code < 500 else "warning",
            "base_url": base_url,
            "http_status": response.status_code,
            "elapsed_ms": elapsed_ms,
        }
    except Exception as e:
        return {
            "status": "warning",
            "base_url": base_url,
            "error": str(e)[:200],
        }


def _summarize_recent_routing_logs(limit: int = 100) -> dict:
    try:
        from qa_test_logger import get_qa_logs
        rows = get_qa_logs(limit=limit)
    except Exception as e:
        return {"status": "warning", "error": str(e)[:200], "count": 0}

    if not rows:
        return {"status": "empty", "count": 0}

    latencies = [int(row.get("latency_ms") or 0) for row in rows]
    tool_counts = [int(row.get("tool_call_count") or 0) for row in rows]
    adjudicator_called = 0
    adjudicator_required = 0
    adjudicator_timeouts = 0
    rag_conf_values: list[float] = []
    slow_count = 0
    timeout_like_count = 0
    source_status_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}

    for row in rows:
        extra = row.get("extra") or {}
        if isinstance(extra, dict):
            if extra.get("llm_adjudicator_called"):
                adjudicator_called += 1
            if extra.get("llm_adjudicator_required"):
                adjudicator_required += 1
            if extra.get("llm_adjudicator_status") == "timeout":
                adjudicator_timeouts += 1
            conf = extra.get("intent_rag_confidence")
            if isinstance(conf, (int, float)):
                rag_conf_values.append(float(conf))
            src = str(extra.get("source_status") or "unknown")
            source_status_counts[src] = source_status_counts.get(src, 0) + 1

        latency = int(row.get("latency_ms") or 0)
        if latency >= 30_000:
            slow_count += 1
        answer = str(row.get("answer") or "")
        if latency >= 60_000 or "timeout" in answer.lower() or "시간 초과" in answer:
            timeout_like_count += 1

        tier = row.get("tier_resolved")
        tier_key = f"tier_{tier}" if tier is not None else "tier_unknown"
        tier_counts[tier_key] = tier_counts.get(tier_key, 0) + 1

    return {
        "status": "warning" if timeout_like_count or slow_count else "ok",
        "count": len(rows),
        "avg_latency_ms": int(sum(latencies) / len(latencies)),
        "max_latency_ms": max(latencies),
        "slow_over_30s_count": slow_count,
        "timeout_like_count": timeout_like_count,
        "avg_tool_calls": round(sum(tool_counts) / len(tool_counts), 2),
        "llm_adjudicator_required_count": adjudicator_required,
        "llm_adjudicator_called_count": adjudicator_called,
        "llm_adjudicator_timeout_count": adjudicator_timeouts,
        "intent_rag_avg_confidence": round(sum(rag_conf_values) / len(rag_conf_values), 3) if rag_conf_values else None,
        "source_status_counts": source_status_counts,
        "tier_counts": tier_counts,
    }


def _overall_health_status(parts: dict) -> str:
    statuses = []
    for value in parts.values():
        if isinstance(value, dict):
            statuses.append(str(value.get("status", "")))
    if "critical" in statuses:
        return "critical"
    if "warning" in statuses:
        return "warning"
    return "ok"


def _get_rag_status() -> dict:
    """ChromaDB 컬렉션 상태를 조회. warmup_rag() 구조를 재사용."""
    intent_rag_info = {"status": "UNKNOWN", "record_count": 0}
    try:
        from app.router.intent_rag_resolver import get_intent_rag_corpus_status
    except Exception:
        try:
            from router.intent_rag_resolver import get_intent_rag_corpus_status
        except Exception as e:
            get_intent_rag_corpus_status = None
            intent_rag_info = {"status": f"ERROR: {e}", "record_count": 0}
    if get_intent_rag_corpus_status is not None:
        try:
            status = get_intent_rag_corpus_status()
            intent_rag_info = {
                "status": "SUCCESS" if status.get("available") else "FALLBACK",
                "record_count": status.get("record_count", 0),
                "path": status.get("path", ""),
                "fallback_manual_examples": status.get("fallback_manual_examples", 0),
            }
        except Exception as e:
            intent_rag_info = {"status": f"ERROR: {e}", "record_count": 0}

    try:
        import chromadb
        chroma_dir = os.environ.get(
            "CHROMA_DIR",
            os.path.join(APP_DIR, ".chroma"),
        )
        client = chromadb.PersistentClient(path=chroma_dir)

        # laws
        laws_info = {"status": "FAIL", "doc_count": 0}
        try:
            laws_col = client.get_collection("laws")
            laws_info = {"status": "SUCCESS", "doc_count": laws_col.count()}
        except Exception as e:
            laws_info = {"status": f"FAIL: {e}", "doc_count": 0}

        # manuals (split collections)
        manuals_info = {
            "status": "FAIL",
            "collection_strategy": "split_collections",
            "collections": [],
            "doc_count": 0,
            "retrieved_doc_count": 3,
        }
        total = 0
        cols_found = []
        for col_info in client.list_collections():
            cname = col_info.name if hasattr(col_info, "name") else col_info
            if cname.startswith("manuals_"):
                cnt = client.get_collection(cname).count()
                cols_found.append({"name": cname, "doc_count": cnt})
                total += cnt
        if cols_found:
            # 이름순 정렬
            cols_found.sort(key=lambda x: x["name"])
            manuals_info["collections"] = cols_found
            manuals_info["doc_count"] = total
            manuals_info["status"] = "SUCCESS"

        # innovation
        innovation_info = {"status": "FAIL", "product_count": 0}
        try:
            innov_col = client.get_collection("innovation")
            innovation_info = {"status": "SUCCESS", "product_count": innov_col.count()}
        except Exception as e:
            innovation_info = {"status": f"FAIL: {e}", "product_count": 0}

        return {
            "laws": laws_info,
            "manuals": manuals_info,
            "innovation": innovation_info,
            "intent_rag": intent_rag_info,
            "production_deployment": PRODUCTION_DEPLOYMENT,
        }
    except Exception as e:
        return {
            "laws": {"status": f"ERROR: {e}", "doc_count": 0},
            "manuals": {"status": f"ERROR: {e}", "doc_count": 0},
            "innovation": {"status": f"ERROR: {e}", "product_count": 0},
            "intent_rag": intent_rag_info,
            "production_deployment": PRODUCTION_DEPLOYMENT,
        }


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "busanproduct-advisor-api",
        "production_deployment": PRODUCTION_DEPLOYMENT,
    }


@app.get("/version")
def version():
    return {
        "commit_hash": _get_commit_hash(),
        "model_primary": os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        "model_fallback": os.getenv("FALLBACK_MODEL", "gemini-2.5-flash"),
        "prompt_mode": os.getenv("PROMPT_MODE", "legacy"),
        "model_routing_mode": os.getenv("MODEL_ROUTING_MODE", "risk_based"),
        "production_deployment": PRODUCTION_DEPLOYMENT,
    }


@app.get("/rag/status")
def rag_status():
    return _get_rag_status()


@app.get("/admin/health/routing")
def admin_routing_health(request: Request, recent_limit: int = 100):
    """Detailed routing health for operators.

    Access control:
    - If ADMIN_HEALTH_TOKEN is set, require X-Admin-Token or Bearer token.
    - If no token is configured, allow localhost only.
    """
    if not _admin_health_authorized(request):
        raise HTTPException(status_code=403, detail="admin health is restricted")

    recent_limit = max(1, min(int(recent_limit or 100), 500))
    parts = {
        "intent_rag": _get_intent_rag_health(),
        "data_files": _get_data_file_health(),
        "company_api": _probe_company_api(),
        "recent_routing": _summarize_recent_routing_logs(limit=recent_limit),
    }
    return JSONResponse(
        content={
            "status": _overall_health_status(parts),
            "service": "busanproduct-advisor-api",
            "checked_at": datetime.now().isoformat(),
            "uptime_seconds": int(time.time() - SERVER_STARTED_AT),
            "commit_hash": _get_commit_hash(),
            "production_deployment": PRODUCTION_DEPLOYMENT,
            "settings": _get_routing_runtime_settings(),
            **parts,
        },
        media_type="application/json; charset=utf-8",
    )


# 운영 기준은 legacy_gemini 경로다. Orchestrator는 아직 gateway/rule/legal
# preflight 일부가 stub이므로, 명시적으로 켠 경우에만 실험 경로로 사용한다.
USE_ORCHESTRATOR_CHAT = os.getenv("USE_ORCHESTRATOR_CHAT", "false").lower() == "true"
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# ─────────────────────────────────────────────
# PII / Security Filter
# ─────────────────────────────────────────────
_SECURITY_REDACT_KEYS = {
    "parameter_ref", "expected_value_hint", "source_map_path",
    "api_key", "GEMINI_API_KEY", "LAW_API_OC",
}

def _sanitize_response_dict(d: dict) -> dict:
    """운영 응답에서 내부 정보/PII를 필터링한다."""
    import re
    sanitized = {}
    for k, v in d.items():
        if k in _SECURITY_REDACT_KEYS:
            continue
        if isinstance(v, str):
            # 사업자등록번호 마스킹
            v = re.sub(r'\d{3}-\d{2}-\d{5}', '[사업자번호 보호됨]', v)
            # API Key 패턴
            v = re.sub(r'AIza[0-9A-Za-z\-_]{35}', '[API키 보호됨]', v)
            # Traceback 제거 (운영 모드)
            if not DEBUG_MODE and 'Traceback' in v:
                v = '[시스템 오류 - 관리자 문의]'
        sanitized[k] = v
    return sanitized


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    start = time.time()

    # ── Orchestrator 경로 (기본) ──
    if USE_ORCHESTRATOR_CHAT:
        return _chat_orchestrator(req, start)

    # ── Legacy 경로 (롤백용) ──
    return _chat_legacy(req, start)


def _sse_event(event: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {data}\n\n"


def _json_response_body(response: JSONResponse) -> dict:
    try:
        body = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)
        data = json.loads(body)
        return data if isinstance(data, dict) else {"answer": str(data)}
    except Exception as exc:
        return {"answer": "⚠️ 응답 변환 중 오류가 발생했습니다.", "error": str(exc)[:200]}


@app.post("/chat/stream")
def chat_stream_endpoint(req: ChatRequest):
    """SSE progress stream for the web UI.

    This is progress-event streaming, not token streaming. The final answer is
    still produced by the same /chat pipeline, so answer quality and logging stay
    aligned with the normal endpoint.
    """
    start = time.time()
    events: queue.Queue[tuple[str, dict]] = queue.Queue()

    def emit_progress(message: str):
        events.put((
            "progress",
            {
                "message": str(message or "처리 중..."),
                "elapsed_ms": int((time.time() - start) * 1000),
            },
        ))

    def worker():
        try:
            emit_progress("질문 의도와 기관 유형을 확인 중입니다.")
            if USE_ORCHESTRATOR_CHAT:
                response = _chat_orchestrator(req, start)
            else:
                response = _chat_legacy(req, start, progress_callback=emit_progress)

            data = _json_response_body(response)
            if getattr(response, "status_code", 200) >= 400:
                events.put(("error", {
                    "message": data.get("answer") or "답변 생성 중 오류가 발생했습니다.",
                    "status_code": getattr(response, "status_code", 500),
                }))
            else:
                events.put(("final", data))
        except Exception as exc:
            print(f"[STREAM ERROR] {traceback.format_exc()}")
            events.put(("error", {
                "message": "답변 생성 중 오류가 발생했습니다.",
                "detail": str(exc)[:200] if DEBUG_MODE else "",
            }))
        finally:
            events.put(("done", {"elapsed_ms": int((time.time() - start) * 1000)}))

    threading.Thread(target=worker, daemon=True).start()

    def event_generator():
        yield _sse_event("progress", {
            "message": "질문을 접수했습니다.",
            "elapsed_ms": 0,
        })
        while True:
            try:
                event, payload = events.get(timeout=15)
            except queue.Empty:
                yield _sse_event("heartbeat", {"elapsed_ms": int((time.time() - start) * 1000)})
                continue

            yield _sse_event(event, payload)
            if event in {"done", "error"}:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _chat_orchestrator(req: ChatRequest, start: float):
    """Orchestrator 파이프라인 기반 /chat 처리."""
    try:
        from app.runtime.chatbot_orchestrator import run_chatbot_runtime
        from app.runtime.runtime_schema import ChatbotRuntimeRequest

        runtime_req = ChatbotRuntimeRequest(
            user_query=req.message,
            runtime_options={},
        )
        runtime_resp = run_chatbot_runtime(runtime_req)

        latency_ms = int((time.time() - start) * 1000)

        # Answer: rendered_markdown 그대로 반환
        answer = runtime_resp.answer_output.rendered_markdown

        # runtime_stages → serializable list
        stages_list = []
        for s in runtime_resp.runtime_stages:
            stages_list.append({
                "stage": s.stage_name,
                "status": s.status,
                "skipped": s.skipped,
                "reason": s.reason if DEBUG_MODE else None,
            })

        # errors는 DEBUG_MODE에서만 상세 노출
        errors_out = runtime_resp.errors if DEBUG_MODE else []

        resp_obj = ChatResponse(
            answer=answer,
            history=req.history,
            latency_ms=latency_ms,
            total_latency_ms=latency_ms,
            production_deployment=PRODUCTION_DEPLOYMENT,
            legal_conclusion_allowed=False,
            contract_possible_auto_promoted=False,
            final_answer_scanned=True,
            sensitive_fields_removed=True,
            enrichment_join_key_redacted=True,
            deterministic_template_used=True,
            # Phase 11 Orchestrator metadata
            pipeline_mode="orchestrator",
            runtime_status=runtime_resp.runtime_status,
            routing_decision=runtime_resp.router_result.routing_decision,
            primary_intent=runtime_resp.router_result.primary_intent,
            runtime_stages=stages_list,
            forbidden_phrase_scan_passed=runtime_resp.answer_output.forbidden_phrase_scan_passed,
            blocked_phrases_found=runtime_resp.answer_output.blocked_phrases_found,
            # answer builder
            answer_builder_used=runtime_resp.router_result.routing_decision,
            candidate_table_source="orchestrator_structured" if runtime_resp.answer_output.candidate_table_section else "none",
            candidate_export_available=_candidate_export_requested(req.message),
        )

        try:
            from qa_test_logger import save_qa_log
            qa_log_id = save_qa_log(
                question=req.message,
                answer=answer,
                agency_type=req.agency_type,
                latency_ms=latency_ms,
                tier_resolved=1,
                tool_call_count=0,
                model_used="orchestrator",
                pipeline_mode="orchestrator",
                extra_meta={
                    "runtime_status": runtime_resp.runtime_status,
                    "routing_decision": runtime_resp.router_result.routing_decision,
                    "primary_intent": runtime_resp.router_result.primary_intent,
                    "forbidden_phrase_scan_passed": runtime_resp.answer_output.forbidden_phrase_scan_passed,
                    "blocked_phrases_found": runtime_resp.answer_output.blocked_phrases_found,
                },
            )
            resp_obj.qa_log_id = qa_log_id
        except Exception as log_err:
            print(f"  [QA_LOG] Failed: {log_err}")

        resp_dict = resp_obj.dict()
        resp_dict = _sanitize_response_dict(resp_dict)

        return JSONResponse(content=resp_dict, media_type="application/json; charset=utf-8")

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        err_str = str(e)

        if not DEBUG_MODE:
            print(f"[ORCHESTRATOR ERROR] {traceback.format_exc()}")

        if any(kw in err_str for kw in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"]):
            error_msg = "API 사용량 한도 초과 또는 서버 지연. 잠시 후 다시 시도하세요."
        else:
            error_msg = "내부 처리 오류가 발생했습니다."

        resp_obj = ChatResponse(
            answer=f"⚠️ {error_msg}",
            history=req.history,
            latency_ms=latency_ms,
            total_latency_ms=latency_ms,
            production_deployment=PRODUCTION_DEPLOYMENT,
            pipeline_mode="orchestrator",
            runtime_status="failed",
        )
        return JSONResponse(
            content=_sanitize_response_dict(resp_obj.dict()),
            status_code=500,
            media_type="application/json; charset=utf-8",
        )


def _chat_legacy(req: ChatRequest, start: float, progress_callback=None):
    """기존 gemini_engine.chat() 경로 (USE_ORCHESTRATOR_CHAT=false 롤백용)."""
    try:
        from gemini_engine import chat as engine_chat, get_last_generation_meta

        answer, updated_history = engine_chat(
            user_message=req.message,
            history=req.history,
            progress_callback=progress_callback,
            agency_type=req.agency_type,
        )
        latency_ms = int((time.time() - start) * 1000)
        meta = get_last_generation_meta()
        legacy_router_meta = meta.get("legacy_gemini_intent_router", {}) or {}
        llm_adjudicator_meta = legacy_router_meta.get("adjudicator", {}) or {}

        resp_obj = ChatResponse(
            answer=answer,
            history=updated_history,
            latency_ms=latency_ms,
            total_latency_ms=latency_ms,
            production_deployment=PRODUCTION_DEPLOYMENT,
            pipeline_mode="legacy_gemini",
            candidate_table_source=meta.get("candidate_table_source", "not_available"),
            legal_conclusion_allowed=meta.get("legal_conclusion_allowed", False),
            forbidden_patterns_remaining_after_rewrite=meta.get("forbidden_patterns_remaining_after_rewrite", []),
            final_answer_scanned=meta.get("final_answer_scanned", False),
            post_scan_policy_version=meta.get("post_scan_policy_version", ""),
            post_scan_critical_count=meta.get("post_scan_critical_count", 0),
            post_scan_warning_count=meta.get("post_scan_warning_count", 0),
            post_scan_warning_patterns=meta.get("post_scan_warning_patterns", []),
            model_selected=meta.get("model_used", os.getenv("GEMINI_MODEL", "gemini-2.5-pro")),
            model_decision_reason=meta.get("model_decision_reason", ""),
            tier_resolved=meta.get("tier_resolved", 1),
            mandatory_mcp_plan=meta.get("mandatory_mcp_plan", []),
            mandatory_mcp_executed=meta.get("mandatory_mcp_executed", []),
            mandatory_mcp_missing=meta.get("mandatory_mcp_missing", []),
            intent_frame=legacy_router_meta.get("intent_frame", {}),
            route_plan=legacy_router_meta.get("route_plan", {}),
            evidence_cards=meta.get("evidence_cards", []),
            evidence_card_count=meta.get("evidence_card_count", 0),
            internal_db_hit_count=meta.get("internal_db_hit_count", 0),
            external_mcp_fallback_count=meta.get("external_mcp_fallback_count", 0),
            evidence_missing_count=meta.get("evidence_missing_count", 0),
            mcp_preflight_elapsed_ms=meta.get("mcp_preflight_elapsed_ms", 0),
            tool_call_count=meta.get("tool_call_count", 0),
            rag_elapsed_ms=meta.get("rag_elapsed_ms"),
            model_elapsed_ms=meta.get("model_elapsed_ms"),
            rewrite_elapsed_ms=meta.get("rewrite_elapsed_ms"),
            tool_elapsed_ms_by_name=meta.get("tool_elapsed_ms_by_name", {}),
            tool_args_log=meta.get("tool_args_log", []),
            fast_track_applied=meta.get("fast_track_applied", False),
            deterministic_template_used=meta.get("deterministic_template_used", False),
            source_status=meta.get("source_status", ""),
            legal_basis_cache_used=meta.get("legal_basis_cache_used", False),
            legal_basis_cache_hit_count=meta.get("legal_basis_cache_hit_count", 0),
            legal_basis_cache_miss_count=meta.get("legal_basis_cache_miss_count", 0),
            mcp_called_for_cache_miss=meta.get("mcp_called_for_cache_miss", False),
            mcp_called_for_freshness=meta.get("mcp_called_for_freshness", False),
            cache_status=meta.get("cache_status", ""),
            route_guidance_provided=meta.get("route_guidance_provided", False),
            regional_route_guidance_provided=meta.get("regional_route_guidance_provided", False),
            routing_confidence_score=meta.get("routing_confidence_score", 0.0),
            routing_confidence_level=meta.get("routing_confidence_level", ""),
            routing_ambiguous=meta.get("routing_ambiguous", False),
            routing_ambiguity_reasons=meta.get("routing_ambiguity_reasons", []),
            routing_required_slots_missing=meta.get("routing_required_slots_missing", []),
            routing_confidence_action=meta.get("routing_confidence_action", ""),
            amount_detected=meta.get("amount_detected"),
            amount_band=meta.get("amount_band"),
            candidate_counts_by_type=meta.get("candidate_counts_by_type", {}),
            source_call_statuses=meta.get("source_call_statuses", {}),
            company_cache_used=meta.get("company_cache_used", False),
            company_cache_refreshed_at=meta.get("company_cache_refreshed_at"),
            company_cache_age_hours=meta.get("company_cache_age_hours"),
            company_source_status=meta.get("company_source_status", "no_company_query"),
            company_source_status_user_label=meta.get("company_source_status_user_label", "업체검색 불필요"),
            company_search_status=meta.get("company_search_status", "not_called"),
            company_data_sources_used=meta.get("company_data_sources_used", []),
            company_cache_mode=meta.get("company_cache_mode", "none"),
            answer_builder_used=meta.get("answer_builder_used"),
            answer_sections_rendered=meta.get("answer_sections_rendered", []),
            candidate_section_position=meta.get("candidate_section_position", -1),
            legal_basis_section_rendered=meta.get("legal_basis_section_rendered", False),
            practice_manual_card_count=meta.get("practice_manual_card_count", 0),
            pps_qa_card_count=meta.get("pps_qa_card_count", 0),
            tool_loop_gate_mode=meta.get("tool_loop_gate_mode", "shadow"),
            tool_loop_gate_recommendation=meta.get("tool_loop_gate_recommendation", ""),
            tool_loop_gate_evidence_sufficiency_score=meta.get("tool_loop_gate_evidence_sufficiency_score", 0.0),
            tool_loop_gate_should_allow_loop=meta.get("tool_loop_gate_should_allow_loop", True),
            tool_loop_gate_can_use_writer_only=meta.get("tool_loop_gate_can_use_writer_only", False),
            tool_loop_gate_enforced=meta.get("tool_loop_gate_enforced", False),
            tool_loop_gate_reasons=meta.get("tool_loop_gate_reasons", []),
            tool_loop_gate_blockers=meta.get("tool_loop_gate_blockers", []),
            tool_loop_gate_missing_supports=meta.get("tool_loop_gate_missing_supports", []),
            intent_rag_enabled=meta.get("intent_rag_enabled", False),
            intent_rag_status=meta.get("intent_rag_status", ""),
            intent_rag_primary_intent=meta.get("intent_rag_primary_intent", ""),
            intent_rag_labels=meta.get("intent_rag_labels", []),
            intent_rag_sub_intents=meta.get("intent_rag_sub_intents", []),
            intent_rag_answer_mode=meta.get("intent_rag_answer_mode", ""),
            intent_rag_confidence=meta.get("intent_rag_confidence", 0.0),
            intent_rag_confidence_level=meta.get("intent_rag_confidence_level", ""),
            intent_rag_company_search_required=meta.get("intent_rag_company_search_required", False),
            intent_rag_company_search_blocked=meta.get("intent_rag_company_search_blocked", False),
            intent_rag_local_purchase_support_required=meta.get("intent_rag_local_purchase_support_required", False),
            intent_rag_contract_review_required=meta.get("intent_rag_contract_review_required", False),
            intent_rag_procedure_required=meta.get("intent_rag_procedure_required", False),
            intent_rag_legal_basis_required=meta.get("intent_rag_legal_basis_required", False),
            intent_rag_llm_router_required=meta.get("intent_rag_llm_router_required", True),
            intent_rag_corpus_record_count=meta.get("intent_rag_corpus_record_count", 0),
            intent_rag_item_name=meta.get("intent_rag_item_name", ""),
            intent_rag_contract_object=meta.get("intent_rag_contract_object", ""),
            intent_rag_amount=meta.get("intent_rag_amount"),
            intent_rag_reasons=meta.get("intent_rag_reasons", []),
            intent_rag_matched_examples=meta.get("intent_rag_matched_examples", []),
            llm_adjudicator_enabled=llm_adjudicator_meta.get("enabled", False),
            llm_adjudicator_required=llm_adjudicator_meta.get("required", False),
            llm_adjudicator_called=llm_adjudicator_meta.get("called", False),
            llm_adjudicator_status=llm_adjudicator_meta.get("status", ""),
            llm_adjudicator_elapsed_ms=llm_adjudicator_meta.get("elapsed_ms", 0),
            llm_adjudicator_reasons=llm_adjudicator_meta.get("reasons", []),
            llm_adjudicator_conflicts=llm_adjudicator_meta.get("conflicts", []),
            llm_adjudicator_missing_slots=llm_adjudicator_meta.get("missing_slots", []),
            llm_adjudicator_labels_before=llm_adjudicator_meta.get("labels_before", []),
            llm_adjudicator_labels_after=llm_adjudicator_meta.get("labels_after", []),
            mcp_context_mode_requested=meta.get("mcp_context_mode_requested", ""),
            mcp_context_mode_applied=meta.get("mcp_context_mode_applied", ""),
            mcp_context_raw_chars=meta.get("mcp_context_raw_chars", 0),
            mcp_context_card_chars=meta.get("mcp_context_card_chars", 0),
            mcp_context_llm_chars=meta.get("mcp_context_llm_chars", 0),
            mcp_context_char_savings_pct=meta.get("mcp_context_char_savings_pct", 0.0),
            tool_response_context_raw_chars=meta.get("tool_response_context_raw_chars", 0),
            tool_response_context_llm_chars=meta.get("tool_response_context_llm_chars", 0),
            tool_response_context_char_savings_pct=meta.get("tool_response_context_char_savings_pct", 0.0),
            tool_response_context_card_count=meta.get("tool_response_context_card_count", 0),
            tool_response_context_compressed_count=meta.get("tool_response_context_compressed_count", 0),
            tool_response_context_modes=meta.get("tool_response_context_modes", {}),
            llm_payload_core_prompt_chars=meta.get("llm_payload_core_prompt_chars", 0),
            llm_payload_dynamic_context_chars=meta.get("llm_payload_dynamic_context_chars", 0),
            llm_payload_rag_context_chars=meta.get("llm_payload_rag_context_chars", 0),
            llm_payload_mcp_context_chars=meta.get("llm_payload_mcp_context_chars", 0),
            llm_payload_practice_context_chars=meta.get("llm_payload_practice_context_chars", 0),
            llm_payload_pps_qa_context_chars=meta.get("llm_payload_pps_qa_context_chars", 0),
            llm_payload_route_plan_guidance_chars=meta.get("llm_payload_route_plan_guidance_chars", 0),
            llm_payload_intent_rag_guidance_chars=meta.get("llm_payload_intent_rag_guidance_chars", 0),
            llm_payload_router_guidance_chars=meta.get("llm_payload_router_guidance_chars", 0),
            llm_payload_tool_count_available=meta.get("llm_payload_tool_count_available", 0),
            llm_payload_initial_contents_chars=meta.get("llm_payload_initial_contents_chars", 0),
            llm_payload_max_contents_chars=meta.get("llm_payload_max_contents_chars", 0),
            llm_payload_after_tool_response_chars=meta.get("llm_payload_after_tool_response_chars", 0),
            llm_payload_after_forced_prefetch_chars=meta.get("llm_payload_after_forced_prefetch_chars", 0),
            llm_payload_model_round_count=meta.get("llm_payload_model_round_count", 0),
            llm_payload_model_timeout_count=meta.get("llm_payload_model_timeout_count", 0),
            llm_payload_model_error_statuses=meta.get("llm_payload_model_error_statuses", []),
            llm_answer_thinking_budget=meta.get("llm_answer_thinking_budget", 0),
            llm_answer_thinking_budget_reason=meta.get("llm_answer_thinking_budget_reason", ""),
            llm_tool_loop_enabled=meta.get("llm_tool_loop_enabled", False),
            llm_internal_tools_disabled=meta.get("llm_internal_tools_disabled", True),
            natural_language_writer_enabled=meta.get("natural_language_writer_enabled", False),
            natural_language_writer_applied=meta.get("natural_language_writer_applied", False),
            natural_language_writer_mode=meta.get("natural_language_writer_mode", ""),
            natural_language_writer_model=meta.get("natural_language_writer_model", ""),
            natural_language_writer_reason=meta.get("natural_language_writer_reason", ""),
            natural_language_writer_skip_reason=meta.get("natural_language_writer_skip_reason", ""),
            natural_language_writer_elapsed_ms=meta.get("natural_language_writer_elapsed_ms", 0),
            natural_language_writer_split_mode=meta.get("natural_language_writer_split_mode", ""),
            natural_language_writer_target_chars=meta.get("natural_language_writer_target_chars", 0),
            natural_language_writer_suffix_chars=meta.get("natural_language_writer_suffix_chars", 0),
            natural_language_writer_output_chars=meta.get("natural_language_writer_output_chars", 0),
            natural_language_writer_table_preserved=meta.get("natural_language_writer_table_preserved", False),
            candidate_export_available=_candidate_export_requested(req.message),
        )

        # ── QA 테스트 로그 자동 저장 ──
        try:
            from qa_test_logger import save_qa_log
            qa_log_id = save_qa_log(
                question=req.message,
                answer=answer,
                agency_type=req.agency_type,
                latency_ms=latency_ms,
                tier_resolved=meta.get("tier_resolved"),
                tool_call_count=meta.get("tool_call_count", 0),
                mcp_preflight_elapsed_ms=meta.get("mcp_preflight_elapsed_ms", 0),
                mandatory_mcp_plan=meta.get("mandatory_mcp_plan"),
                mandatory_mcp_executed=meta.get("mandatory_mcp_executed"),
                mandatory_mcp_missing=meta.get("mandatory_mcp_missing"),
                model_used=meta.get("model_used"),
                pipeline_mode="legacy_gemini",
                extra_meta={
                    "rag_elapsed_ms": meta.get("rag_elapsed_ms"),
                    "model_elapsed_ms": meta.get("model_elapsed_ms"),
                    "legal_basis_cache_hit_count": meta.get("legal_basis_cache_hit_count"),
                    "legal_basis_cache_miss_count": meta.get("legal_basis_cache_miss_count"),
                    "evidence_card_count": meta.get("evidence_card_count"),
                    "internal_db_hit_count": meta.get("internal_db_hit_count"),
                    "external_mcp_fallback_count": meta.get("external_mcp_fallback_count"),
                    "evidence_missing_count": meta.get("evidence_missing_count"),
                    "deterministic_template_used": meta.get("deterministic_template_used"),
                    "source_status": meta.get("source_status"),
                    "practice_manual_card_count": meta.get("practice_manual_card_count", 0),
                    "pps_qa_card_count": meta.get("pps_qa_card_count", 0),
                    "intent_rag_primary_intent": meta.get("intent_rag_primary_intent"),
                    "intent_rag_labels": meta.get("intent_rag_labels", []),
                    "intent_rag_answer_mode": meta.get("intent_rag_answer_mode"),
                    "intent_rag_confidence": meta.get("intent_rag_confidence"),
                    "intent_rag_corpus_record_count": meta.get("intent_rag_corpus_record_count"),
                    "intent_rag_company_search_required": meta.get("intent_rag_company_search_required"),
                    "intent_rag_company_search_blocked": meta.get("intent_rag_company_search_blocked"),
                    "intent_rag_reasons": meta.get("intent_rag_reasons", []),
                    "llm_adjudicator_required": llm_adjudicator_meta.get("required", False),
                    "llm_adjudicator_called": llm_adjudicator_meta.get("called", False),
                    "llm_adjudicator_status": llm_adjudicator_meta.get("status", ""),
                    "llm_adjudicator_elapsed_ms": llm_adjudicator_meta.get("elapsed_ms", 0),
                    "llm_adjudicator_reasons": llm_adjudicator_meta.get("reasons", []),
                    "llm_adjudicator_conflicts": llm_adjudicator_meta.get("conflicts", []),
                    "llm_adjudicator_missing_slots": llm_adjudicator_meta.get("missing_slots", []),
                    "llm_adjudicator_labels_before": llm_adjudicator_meta.get("labels_before", []),
                    "llm_adjudicator_labels_after": llm_adjudicator_meta.get("labels_after", []),
                    "mcp_context_raw_chars": meta.get("mcp_context_raw_chars", 0),
                    "mcp_context_card_chars": meta.get("mcp_context_card_chars", 0),
                    "mcp_context_llm_chars": meta.get("mcp_context_llm_chars", 0),
                    "tool_response_context_raw_chars": meta.get("tool_response_context_raw_chars", 0),
                    "tool_response_context_llm_chars": meta.get("tool_response_context_llm_chars", 0),
                    "llm_payload_core_prompt_chars": meta.get("llm_payload_core_prompt_chars", 0),
                    "llm_payload_dynamic_context_chars": meta.get("llm_payload_dynamic_context_chars", 0),
                    "llm_payload_mcp_context_chars": meta.get("llm_payload_mcp_context_chars", 0),
                    "llm_payload_initial_contents_chars": meta.get("llm_payload_initial_contents_chars", 0),
                    "llm_payload_max_contents_chars": meta.get("llm_payload_max_contents_chars", 0),
                    "llm_payload_model_timeout_count": meta.get("llm_payload_model_timeout_count", 0),
                    "llm_payload_model_error_statuses": meta.get("llm_payload_model_error_statuses", []),
                },
            )
            resp_obj.qa_log_id = qa_log_id
        except Exception as log_err:
            print(f"  [QA_LOG] Failed: {log_err}")

        return JSONResponse(content=resp_obj.dict(), media_type="application/json; charset=utf-8")

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        print(f"[LEGACY ERROR] {traceback.format_exc()}")
        resp_obj = ChatResponse(
            answer="⚠️ 내부 서버 오류",
            history=req.history,
            latency_ms=latency_ms,
            total_latency_ms=latency_ms,
            production_deployment=PRODUCTION_DEPLOYMENT,
            pipeline_mode="legacy_gemini",
            runtime_status="failed",
        )
        return JSONResponse(
            content=resp_obj.dict(),
            status_code=500,
            media_type="application/json; charset=utf-8",
        )


# ─────────────────────────────────────────────
# QA 테스트 로그 조회 API
# ─────────────────────────────────────────────
@app.get("/qa-logs")
def get_qa_logs_endpoint(date: str = None, limit: int = 100):
    """QA 테스트 로그 조회. ?date=20260507&limit=50"""
    try:
        from qa_test_logger import get_qa_logs
        logs = get_qa_logs(date_str=date, limit=limit)
        return JSONResponse(
            content={"count": len(logs), "logs": logs},
            media_type="application/json; charset=utf-8",
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/qa-logs/{qa_log_id}/candidate-export.xlsx")
def get_candidate_export_endpoint(qa_log_id: str):
    """Download candidate companies used for follow-up verification as XLSX."""
    record = _find_qa_log_by_id(qa_log_id)
    if not record:
        raise HTTPException(status_code=404, detail="qa_log_id not found")
    question = str(record.get("question") or "")
    content = _build_candidate_export_xlsx(question)
    if not content:
        raise HTTPException(status_code=404, detail="candidate export not available")
    filename = f"busan_candidate_export_{qa_log_id}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/qa-summary")
def get_qa_summary_endpoint(date: str = None):
    """QA 테스트 일별 요약. ?date=20260507"""
    try:
        from qa_test_logger import get_qa_summary
        summary = get_qa_summary(date_str=date)
        return JSONResponse(
            content=summary,
            media_type="application/json; charset=utf-8",
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/qa-feedback")
def save_qa_feedback_endpoint(req: QaFeedbackRequest):
    """답변별 사용자/테스터 피드백 저장.

    이 피드백은 코퍼스 자동 승인값이 아니라, 실패질문 후보 생성의 입력 신호로만 사용한다.
    """
    try:
        from qa_test_logger import save_qa_feedback

        feedback_id = save_qa_feedback(
            qa_log_id=req.qa_log_id or "",
            rating=req.rating,
            satisfied=req.satisfied,
            issue_tags=req.issue_tags,
            comment=req.comment or "",
            expected_intent=req.expected_intent or "",
            corrected_answer=req.corrected_answer or "",
            question=req.question or "",
            answer_excerpt=req.answer_excerpt or "",
            source=req.source or "user",
        )
        return JSONResponse(
            content={
                "status": "saved" if feedback_id else "failed",
                "feedback_id": feedback_id,
                "qa_log_id": req.qa_log_id or "",
                "corpus_approval_status": "not_approved_feedback_only",
            },
            media_type="application/json; charset=utf-8",
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/qa-feedback")
def get_qa_feedback_endpoint(date: str = None, limit: int = 100):
    """피드백 로그 조회. ?date=20260509&limit=100"""
    try:
        from qa_test_logger import get_qa_feedback
        rows = get_qa_feedback(date_str=date, limit=limit)
        return JSONResponse(
            content={"count": len(rows), "feedback": rows},
            media_type="application/json; charset=utf-8",
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ─────────────────────────────────────────────
# 직접 실행
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8001"))
    print(f"Starting API server on port {port}...")
    print(f"Production deployment: {PRODUCTION_DEPLOYMENT}")
    uvicorn.run(app, host="0.0.0.0", port=port)
