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
import csv
import zipfile
import requests
import re
from io import BytesIO, StringIO
from datetime import datetime

# app 디렉터리를 Python 경로에 추가
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
sys.path.insert(0, APP_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

try:
    from policies.item_normalization_policy import normalize_item_query
except Exception:
    normalize_item_query = None
try:
    from policies.purchase_route_guidance_policy import build_purchase_route_cards
except Exception:
    build_purchase_route_cards = None

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

VENDOR_FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "vendor")
if os.path.isdir(VENDOR_FRONTEND_DIR):
    app.mount("/vendor-ui", StaticFiles(directory=VENDOR_FRONTEND_DIR, html=True), name="vendor-ui")

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
        "vendors": {
            "search_json": "/vendors/search?q=computer&region=busan&limit=10",
            "search_csv": "/vendors/query.csv?q=computer&region=busan&limit=10",
            "download_zip": "/vendors/download.zip",
        },
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
    return any(term in q for term in (
        "업체", "후보", "추천", "공급사", "부산업체", "지역업체",
        "행사용역", "행사", "축제", "발대식", "기념식", "행사기획", "행사대행",
    ))


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
    elif any(term in q for term in ("행사용역", "행사 용역", "발대식", "기념식", "행사기획", "행사대행", "이벤트")):
        searches.extend([
            ("품목: 행사", "product", "행사"),
            ("품목: 기타행사기획및대행서비스", "product", "기타행사기획및대행서비스"),
            ("품목: 공연기획및대행서비스", "product", "공연기획및대행서비스"),
            ("품목: 전시회기획및대행서비스", "product", "전시회기획및대행서비스"),
            ("면허/업종: 행사", "license", "행사"),
            ("면허/업종: 이벤트", "license", "이벤트"),
        ])
    elif any(term in q for term in ("청사 경비", "청사경비", "경비용역", "시설경비", "무인경비", "기계경비", "특수경비")):
        searches.extend([
            ("면허: 시설경비업무", "license", "시설경비업무"),
            ("면허: 시설경비업", "license", "시설경비업"),
            ("면허: 기계경비업무", "license", "기계경비업무"),
            ("면허: 기계경비업", "license", "기계경비업"),
            ("면허: 특수경비업무", "license", "특수경비업무"),
            ("면허: 특수경비업", "license", "특수경비업"),
            ("면허: 경비용역", "license", "경비용역"),
            ("품목: 시설물경비서비스", "product", "시설물경비서비스"),
            ("품목: 경비", "product", "경비"),
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


VENDOR_CSV_FIELDS = [
    "company_id",
    "company_name",
    "location",
    "detail_address",
    "business_status",
    "display_status",
    "license_or_business_type",
    "main_products",
    "candidate_types",
    "primary_candidate_type",
    "policy_subtypes",
    "certified_product_types",
    "is_sme_competition_product",
    "shopping_mall_flags",
    "has_shopping_mall",
    "has_mas",
    "certified_product_summary",
    "shopping_mall_product_summary",
    "mas_product_summary",
    "direct_production_summary",
    "construction_capacity_summary",
    "venture_nara_product_summary",
    "venture_nara_order_summary",
    "direct_production_flags",
    "procurement_attributes",
    "general_certifications",
    "manufacturer_type",
    "business_status_freshness",
    "source_refreshed_at",
    "contract_history_match",
    "contract_history_summary",
    "contract_history_recent_count",
    "contract_history_total_amount",
    "contract_history_last_date",
]

VENDOR_RECOMMENDATION_COLUMNS = [
    "company_name",
    "location",
    "contract_review_types",
    "budget_review_hint",
    "purchase_route_fit_summary",
    "purchase_route_fit_score",
    "license_status_label",
    "license_or_business_type",
    "main_products",
    "shopping_mall_status_label",
    "shopping_mall_match",
    "shopping_mall_product_summary",
    "mas_status_label",
    "mas_match",
    "mas_product_summary",
    "direct_production_certificate_status",
    "direct_production_match",
    "direct_production_certificate_products",
    "requested_item_evidence_summary",
    "contract_history_status_label",
    "contract_history_match",
    "contract_history_summary",
    "contract_history_recent_count",
    "contract_history_total_amount",
    "contract_history_last_date",
    "condition_match_type",
    "condition_match_summary",
    "construction_capacity_status_label",
    "construction_license_match",
    "construction_capacity_match",
    "construction_capacity_amount",
    "construction_capacity_summary",
    "venture_nara_status_label",
    "venture_nara_product_summary",
    "venture_nara_order_summary",
    "certified_product_labels",
    "certified_product_summary",
    "policy_company_labels",
    "sme_competition_product_label",
    "cooperative_purchase_route_label",
    "business_status",
    "business_status_label",
    "business_status_freshness",
    "business_status_freshness_label",
    "recommended_checks",
    "matched_query_label",
    "review_score",
]

_VENDOR_POLICY_LABELS = {
    "women_company": "여성기업",
    "disabled_company": "장애인기업",
    "social_enterprise": "사회적기업",
    "social_cooperative": "사회적협동조합",
    "self_support_company": "자활기업",
    "village_company": "마을기업",
    "sme": "중소기업",
    "small_business": "소상공인",
    "startup": "창업기업",
    "youth_startup": "청년창업기업",
    "venture_company": "벤처기업",
}

_VENDOR_CERT_LABELS = {
    "nep_product": "NEP(신제품)",
    "net_certified_product": "NET(신기술)",
    "performance_certification": "성능인증",
    "green_technology_product": "녹색기술",
    "gs_certified_product": "GS인증",
    "innovation_product": "혁신제품",
    "innovation_prototype_product": "혁신시제품",
    "excellent_procurement_product": "우수조달물품",
    "quality_assured_procurement_product": "품질보증조달물품",
    "excellent_invention_product": "우수발명품",
    "disaster_safety_certified_product": "재난안전제품",
    "priority_purchase_product": "기술개발제품",
}


def _vendor_import_company_db():
    try:
        import company_db
        return company_db
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"company DB module unavailable: {exc}") from exc


def _vendor_join(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "|".join(f"{k}:{v}" for k, v in value.items())
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = (
                    item.get("product_name")
                    or item.get("detail_product_name")
                    or item.get("license_name")
                    or item.get("name")
                    or item.get("type")
                    or ""
                )
                if item.get("order_count") is not None or item.get("total_amount") is not None:
                    order_count = item.get("order_count")
                    total_amount = item.get("total_amount")
                    order_label = f"{order_count}건" if str(order_count or "").strip() else ""
                    try:
                        amount_label = f"{int(str(total_amount).replace(',', '')):,}원" if str(total_amount or "").strip() else ""
                    except ValueError:
                        amount_label = str(total_amount or "")
                    compact = " / ".join(
                        str(x)
                        for x in (name, order_label, amount_label, item.get("last_order_date") or "")
                        if str(x)
                    )
                    if compact:
                        parts.append(compact)
                    continue
                if item.get("category_name") is not None or item.get("venture_company_marked") is not None:
                    compact = " / ".join(
                        str(x)
                        for x in (name, item.get("category_name") or "", item.get("valid_until") or "")
                        if str(x)
                    )
                    if compact:
                        parts.append(compact)
                    continue
                code = item.get("detail_product_code") or item.get("construction_capacity_amount") or ""
                typ = item.get("type") or ""
                status = item.get("status") or item.get("valid_until") or item.get("last_order_date") or ""
                compact = " / ".join(str(x) for x in (name, code, typ, status) if str(x))
                if compact:
                    parts.append(compact)
            elif item is not None:
                parts.append(str(item))
        return "|".join(parts)
    return str(value)


def _vendor_pipe_has(raw, token: str) -> bool:
    return token.lower() in str(raw or "").lower()


def _vendor_row_from_candidate(candidate: dict) -> dict[str, str]:
    shopping_flags = candidate.get("shopping_mall_flags") or []
    mas_summary = candidate.get("mas_product_summary") or []
    return {
        "company_id": _vendor_join(candidate.get("company_id")),
        "company_name": _vendor_join(candidate.get("company_name")),
        "location": _vendor_join(candidate.get("location")),
        "detail_address": _vendor_join(candidate.get("detail_address")),
        "business_status": _vendor_join(candidate.get("business_status")),
        "display_status": _vendor_join(candidate.get("display_status")),
        "license_or_business_type": _vendor_join(candidate.get("license_or_business_type")),
        "main_products": _vendor_join(candidate.get("main_products")),
        "candidate_types": _vendor_join(candidate.get("candidate_types")),
        "primary_candidate_type": _vendor_join(candidate.get("primary_candidate_type")),
        "policy_subtypes": _vendor_join(candidate.get("policy_subtypes")),
        "certified_product_types": _vendor_join(candidate.get("certified_product_types")),
        "is_sme_competition_product": "true" if candidate.get("sme_competition_product") else "false",
        "shopping_mall_flags": _vendor_join(shopping_flags),
        "has_shopping_mall": "true" if shopping_flags else "false",
        "has_mas": "true" if mas_summary else "false",
        "certified_product_summary": _vendor_join(candidate.get("certified_product_summary")),
        "shopping_mall_product_summary": _vendor_join(candidate.get("shopping_mall_product_summary")),
        "mas_product_summary": _vendor_join(mas_summary),
        "direct_production_summary": _vendor_join(candidate.get("direct_production_summary")),
        "construction_capacity_summary": _vendor_join(candidate.get("construction_capacity_summary")),
        "venture_nara_product_summary": _vendor_join(candidate.get("venture_nara_product_summary")),
        "venture_nara_order_summary": _vendor_join(candidate.get("venture_nara_order_summary")),
        "direct_production_flags": _vendor_join(candidate.get("direct_production_flags")),
        "procurement_attributes": _vendor_join(candidate.get("procurement_attributes")),
        "general_certifications": _vendor_join(candidate.get("general_certifications")),
        "manufacturer_type": _vendor_join(candidate.get("manufacturer_type")),
        "business_status_freshness": _vendor_join(candidate.get("business_status_freshness")),
        "source_refreshed_at": _vendor_join(candidate.get("source_refreshed_at")),
    }


def _vendor_row_from_db(row: dict) -> dict[str, str]:
    shopping_raw = row.get("shopping_mall_flags_raw")
    mas_raw = row.get("mas_product_summary_raw")
    return {
        "company_id": _vendor_join(row.get("company_id")),
        "company_name": _vendor_join(row.get("company_name")),
        "location": _vendor_join(row.get("location")),
        "detail_address": _vendor_join(row.get("detail_address")),
        "business_status": _vendor_join(row.get("business_status")),
        "display_status": _vendor_join(row.get("display_status")),
        "license_or_business_type": _vendor_join(row.get("license_or_business_type")),
        "main_products": _vendor_join(row.get("main_products")),
        "candidate_types": _vendor_join(row.get("candidate_types")),
        "primary_candidate_type": _vendor_join(row.get("primary_candidate_type")),
        "policy_subtypes": _vendor_join(row.get("policy_subtypes_raw")),
        "certified_product_types": _vendor_join(row.get("certified_product_types_raw")),
        "is_sme_competition_product": "true" if row.get("is_sme_competition_product") else "false",
        "shopping_mall_flags": _vendor_join(shopping_raw),
        "has_shopping_mall": "true" if str(shopping_raw or "").strip() else "false",
        "has_mas": "true" if str(mas_raw or "").strip() or _vendor_pipe_has(shopping_raw, "mas") else "false",
        "certified_product_summary": _vendor_join(row.get("certified_product_summary_raw")),
        "shopping_mall_product_summary": _vendor_join(row.get("shopping_mall_product_summary_raw")),
        "mas_product_summary": _vendor_join(mas_raw),
        "direct_production_summary": _vendor_join(row.get("direct_production_summary_raw")),
        "construction_capacity_summary": _vendor_join(row.get("construction_capacity_summary_raw")),
        "venture_nara_product_summary": _vendor_join(row.get("venture_nara_product_summary_raw")),
        "venture_nara_order_summary": _vendor_join(row.get("venture_nara_order_summary_raw")),
        "direct_production_flags": _vendor_join(row.get("direct_production_flags_raw")),
        "procurement_attributes": _vendor_join(row.get("procurement_attributes_raw")),
        "general_certifications": _vendor_join(row.get("general_certifications_raw")),
        "manufacturer_type": _vendor_join(row.get("manufacturer_type")),
        "business_status_freshness": _vendor_join(row.get("business_status_freshness")),
        "source_refreshed_at": _vendor_join(row.get("source_refreshed_at")),
    }


def _vendor_region_matches(row: dict[str, str], region: str) -> bool:
    region = (region or "").strip()
    if not region:
        return True
    normalized = {"busan": "부산", "BUSAN": "부산"}.get(region, region)
    haystack = f"{row.get('location', '')} {row.get('detail_address', '')}"
    return normalized in haystack


_VENDOR_QUERY_STOPWORDS = {
    "예산",
    "계약",
    "방법",
    "방안",
    "근거",
    "중심",
    "안내",
    "구매",
    "확대",
    "부산",
    "업체",
    "지역",
    "지역업체",
    "물품",
    "용역",
    "공사",
    "검토",
    "가능",
    "후보",
    "나라장터",
    "종합쇼핑몰",
    "조달",
    "수의계약",
    "견적",
}

_VENDOR_ALIAS_TOKENS = {
    "컴퓨터": ["컴퓨터", "데스크톱", "데스크탑", "노트북", "일체형컴퓨터", "개인용컴퓨터", "컴퓨터서버", "서버"],
    "노트북": ["노트북", "컴퓨터", "개인용컴퓨터"],
    "서버": ["서버", "컴퓨터서버"],
    "cctv": ["CCTV", "씨씨티비", "카메라", "감시카메라", "보안카메라", "보안캠", "보안용카메라", "영상감시장치", "영상감시"],
    "카메라": ["카메라", "CCTV", "보안캠", "영상감시장치"],
    "led": ["LED", "LED조명", "LED실내조명등", "LED램프", "조명", "등기구"],
    "조명": ["조명", "등기구", "LED"],
    "소프트웨어": [
        "소프트웨어", "시스템", "프로그램", "SW", "상용소프트웨어", "패키지소프트웨어",
        "보안소프트웨어", "보안SW", "백신", "백신프로그램", "안티바이러스", "정보보호", "방화벽",
    ],
    "인쇄": ["인쇄", "인쇄물", "홍보물", "리플릿", "책자", "브로슈어", "포스터", "카탈로그", "현수막"],
    "통역": ["통역", "통번역", "번역", "번역용역", "외국어", "언어"],
    "공기청정기": ["공기청정기", "공기청정", "청정기"],
    "캐비닛": ["캐비닛", "보관함", "수납장", "가구"],
    "주방기기": ["주방기기", "주방", "급식실", "급식", "조리기기"],
    "레미콘": ["레미콘", "ready mixed concrete"],
    "아스콘": ["아스콘", "아스팔트콘크리트", "아스팔트"],
    "탄성포장재": ["탄성포장재", "체육시설탄성포장재", "운동장포장", "운동장 탄성포장"],
    "포장공사": ["포장공사", "도로포장", "지반조성포장", "지반조성ㆍ포장공사업", "포장"],
    "행사": ["행사", "축제", "행사용역", "행사기획", "행사대행", "기타행사기획및대행서비스", "이벤트", "발대식", "기념식", "개회식", "공연", "전시", "홍보"],
    "번역": ["번역", "번역용역", "통번역", "통역", "외국어", "언어"],
    "경비": ["경비", "경비용역", "시설경비", "시설경비업무", "기계경비", "특수경비", "시설물경비서비스"],
    "조경": ["조경", "조경공사업", "조경식재공사업", "조경식재공사", "조경시설물설치공사업", "잔디", "수목"],
    "출입통제시스템": ["출입통제시스템", "출입통제장치", "출입관리시스템", "출입통제", "출입관리", "출입보안시스템"],
}

_VENDOR_AMBIGUOUS_PRODUCT_RULES = (
    {
        "key": "telephone_type",
        "generic_markers": ("전화기",),
        "specific_markers": (
            "유선전화",
            "일반전화",
            "휴대전화",
            "휴대폰",
            "스마트폰",
            "무선전화",
            "ip전화",
            "인터넷전화",
            "voip",
        ),
        "search_terms": ("유선전화기", "일반전화기", "휴대전화기", "IP전화기", "인터넷전화기", "전화기"),
        "title": "전화기 종류 선택 필요",
        "message": (
            "'전화기'만으로는 유선전화기·휴대전화기·IP전화기 등 세부품명을 확정할 수 없습니다. "
            "아래 세부품명 후보를 선택한 뒤 품목정책을 다시 판정해야 합니다."
        ),
    },
    {
        "key": "camera_type",
        "generic_markers": ("카메라",),
        "specific_markers": (
            "보안카메라",
            "보안용카메라",
            "감시카메라",
            "cctv",
            "씨씨티비",
            "영상감시장치",
            "영상감시",
            "디지털카메라",
            "디카",
            "비디오카메라",
            "캠코더",
            "웹카메라",
            "웹캠",
        ),
        "search_terms": (
            "보안용카메라",
            "영상감시장치",
            "감시카메라",
            "CCTV",
            "디지털카메라",
            "비디오카메라",
            "캠코더",
            "웹카메라",
            "아날로그카메라",
        ),
        "option_markers": (
            "보안용카메라",
            "영상감시장치",
            "감시카메라",
            "디지털카메라",
            "비디오카메라",
            "캠코더",
            "웹카메라",
            "아날로그카메라",
        ),
        "exclude_option_markers": (
            "회전대",
            "하우징",
            "컨트롤러",
            "브래킷",
            "브라켓",
            "렌즈",
            "마운트",
            "케이블",
            "거치대",
        ),
        "title": "카메라 종류 선택 필요",
        "message": (
            "'카메라'만으로는 보안용카메라·디지털카메라·비디오카메라 등 세부품명을 확정할 수 없습니다. "
            "아래 세부품명 후보를 선택한 뒤 품목정책과 부산업체 후보를 다시 판정해야 합니다."
        ),
    },
    {
        "key": "computer_type",
        "generic_markers": ("컴퓨터",),
        "specific_markers": (
            "데스크톱",
            "데스크탑",
            "노트북",
            "랩톱",
            "랩탑",
            "서버",
            "컴퓨터서버",
            "일체형",
            "태블릿",
            "컴퓨터책상",
        ),
        "search_terms": (
            "데스크톱컴퓨터",
            "노트북컴퓨터",
            "컴퓨터서버",
            "일체형컴퓨터",
            "태블릿컴퓨터",
            "컴퓨터",
        ),
        "option_exact_names": (
            "데스크톱컴퓨터",
            "노트북컴퓨터",
            "컴퓨터서버",
            "일체형컴퓨터",
            "태블릿컴퓨터",
        ),
        "title": "컴퓨터 종류 선택 필요",
        "message": (
            "'컴퓨터'만으로는 데스크톱컴퓨터·노트북컴퓨터·컴퓨터서버 등 세부품명을 확정할 수 없습니다. "
            "아래 세부품명 후보를 선택한 뒤 품목정책과 부산업체 후보를 다시 판정해야 합니다."
        ),
    },
)


def _vendor_compact(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _vendor_item_disambiguation(q: str) -> dict[str, object] | None:
    compact = _vendor_compact(q)
    for rule in _VENDOR_AMBIGUOUS_PRODUCT_RULES:
        if not any(_vendor_compact(marker) in compact for marker in rule["generic_markers"]):
            continue
        if any(_vendor_compact(marker) in compact for marker in rule["specific_markers"]):
            continue
        return dict(rule)
    return None


def _vendor_item_selection_terms(q: str) -> list[str]:
    text = _vendor_intent_text(q)
    text = re.sub(r"\d+[,\d]*(억|천만|백만|만)?원?", " ", text)
    text = re.sub(r"[?!.]", " ", text)
    raw_tokens = [
        token
        for token in re.findall(r"[가-힣A-Za-z0-9]+", text)
        if token and token not in _VENDOR_QUERY_STOPWORDS and not token.isdigit()
    ]
    terms: list[str] = []
    if raw_tokens:
        phrase = " ".join(raw_tokens).strip()
        if phrase:
            terms.append(phrase)
        # If the user gave only one meaningful item word such as "의자" or
        # "컴퓨터", it is safe to ask the DB whether that word expands to
        # several detail items. For multi-word phrases, do not fall back to a
        # broad component like "컴퓨터" because that would undo a concrete query
        # such as "데스크톱 컴퓨터".
        if len(raw_tokens) == 1:
            terms.append(raw_tokens[0])
    cleaned: list[str] = []
    for term in terms:
        compact_term = _vendor_compact(term)
        if compact_term and term not in cleaned:
            cleaned.append(term)
    return cleaned


def _vendor_db_item_disambiguation(q: str) -> dict[str, object] | None:
    try:
        company_db = _vendor_import_company_db()
        search_item_selection_options = getattr(company_db, "search_item_selection_options", None)
    except Exception:
        return None
    if not callable(search_item_selection_options):
        return None
    seen_terms: set[str] = set()
    for term in _vendor_item_selection_terms(q):
        compact_term = _vendor_compact(term)
        if not compact_term or compact_term in seen_terms:
            continue
        seen_terms.add(compact_term)
        try:
            data = search_item_selection_options(term, limit=20)
        except Exception:
            data = None
        options = (data or {}).get("selection_options") or []
        if len(options) >= 2:
            return {
                "key": "db_item_hierarchy",
                "title": str(data.get("selection_title") or f"{term} 세부품명 선택 필요"),
                "message": str(
                    data.get("message")
                    or f"'{term}'만으로는 세부품명을 하나로 확정할 수 없습니다. 실제 구매하려는 세부품명을 선택해야 합니다."
                ),
                "selection_options": options,
                "source": str(((data.get("meta") or {}).get("source")) or "item_dictionary_db"),
            }
    return None


def _vendor_intent_text(q: str) -> str:
    text = str(q or "")
    typo_aliases = {
        "컴퓨타": "컴퓨터",
        "콤퓨터": "컴퓨터",
        "컴터": "컴퓨터",
        "디카": "디지털카메라",
    }
    for typo, canonical in typo_aliases.items():
        text = text.replace(typo, canonical)
    context_patterns = (
        r"(?:문화행사|행사)\s*담당\s*부서\s*(?:에서|가|는)?",
        r"(?:시설관리|청사관리)\s*부서\s*(?:에서|가|는)?",
        r"(?:구청|학교|도서관|복지관|공공기관|공기업|부산시\s*산하기관)\s*(?:발주|구매|계약)?\s*담당자\s*(?:가|에서|는)?",
    )
    for pattern in context_patterns:
        text = re.sub(pattern, " ", text)
    return " ".join(text.split())


def _vendor_normalized_item_terms(q: str) -> tuple[str, list[str]]:
    if normalize_item_query is None:
        return "", []
    try:
        normalized = normalize_item_query(_vendor_intent_text(q))
    except Exception:
        return "", []
    if not getattr(normalized, "found", False):
        return "", []
    terms = [
        getattr(normalized, "primary_search_term", ""),
        *list(getattr(normalized, "search_terms", []) or []),
    ]
    cleaned: list[str] = []
    for term in terms:
        value = " ".join(str(term or "").split())
        if value and value not in cleaned:
            cleaned.append(value)
    return str(getattr(normalized, "canonical_name", "") or ""), cleaned


def _vendor_term_should_search_license(term: str) -> bool:
    compact = _vendor_compact(term)
    if any(token in compact for token in ("광고대행", "옥외광고", "홍보마케팅")):
        return True
    return any(token in compact for token in (
        "공사업",
        "공사",
        "시설업",
        "업무",
        "용역",
        "경비",
        "청소",
        "시설관리",
        "행사",
        "번역",
        "통신",
        "소방",
        "전기",
        "조경",
        "포장",
        "기계설비",
        "실내건축",
        "건축사",
        "사무소",
        "디자인전문회사",
        "제작업",
        "옥외광고",
        "소프트웨어사업자",
        "소독업",
        "폐기물",
        "측량",
        "엔지니어링",
        "원가계산",
        "원가검토",
        "법무",
        "여행업",
        "여객자동차",
        "전세버스",
        "승강기",
        "초경량비행장치",
    ))


def _vendor_query_tokens(q: str) -> list[str]:
    text = str(q or "")
    compact = _vendor_compact(text)
    tokens: list[str] = []
    if any(term in compact for term in ("통역", "번역", "통번역", "외국어")):
        tokens.extend(["통역", "번역", "통번역", "외국어", "언어"])
        return list(dict.fromkeys(tokens))
    if any(term in compact for term in ("인쇄", "인쇄물", "홍보물", "리플릿", "책자", "브로슈어", "포스터", "카탈로그", "현수막")):
        tokens.extend(["인쇄", "인쇄물", "홍보물", "리플릿", "책자", "브로슈어", "포스터", "카탈로그", "현수막"])
        return list(dict.fromkeys(tokens))
    _, normalized_terms = _vendor_normalized_item_terms(text)
    tokens.extend(str(term).lower() for term in normalized_terms)
    for key, aliases in _VENDOR_ALIAS_TOKENS.items():
        if key.lower() in compact or any(_vendor_compact(alias) in compact for alias in aliases):
            tokens.extend(str(alias).lower() for alias in aliases)
    if tokens:
        return list(dict.fromkeys(tokens))
    for raw in re.findall(r"[가-힣A-Za-z0-9]{2,}", text):
        token = raw.lower()
        if token in _VENDOR_QUERY_STOPWORDS:
            continue
        if token.isdigit() or re.fullmatch(r"\d+만원|\d+천만원|\d+억원", token):
            continue
        tokens.append(token)
    return list(dict.fromkeys(tokens[:5]))


def _vendor_add_plan(plan: list[dict[str, str]], seen: set[tuple[str, str]], search_type: str, term: str, label: str = "") -> None:
    term = " ".join(str(term or "").split())
    if not term:
        return
    key = (search_type, term)
    if key in seen:
        return
    seen.add(key)
    plan.append({"search_type": search_type, "term": term, "label": label or f"{search_type}: {term}"})


_VENDOR_CONSTRUCTION_LICENSE_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("금속창호", "금속 창호", "창호공사", "창호 공사", "금속구조물창호", "금속구조물 창호"),
        (
            "금속창호공사업",
            "금속창호ㆍ지붕건축물조립공사업",
            "금속창호지붕건축물조립공사업",
            "금속구조물ㆍ창호ㆍ온실공사업",
            "금속구조물·창호·온실공사업",
            "금속구조물창호온실공사업",
            "창호공사",
        ),
    ),
    (
        ("상하수도", "상하수도설비", "상수도설비", "하수도설비", "상하수도 공사"),
        ("상하수도설비공사업", "상하수도설비공사"),
    ),
    (
        ("실내건축", "실내 건축", "인테리어공사", "인테리어 공사", "실내건축공사"),
        ("실내건축공사업", "실내건축공사"),
    ),
    (
        ("전기공사", "전기 공사", "수배전", "분전반설치"),
        ("전기공사업", "전기공사"),
    ),
    (
        ("정보통신공사", "정보 통신 공사", "통신공사", "네트워크공사"),
        ("정보통신공사업", "정보통신공사"),
    ),
    (
        ("소방공사", "소방시설공사", "소방 설비 공사"),
        ("전문소방시설공사업", "일반소방시설공사업", "소방시설공사업", "소방시설공사"),
    ),
    (
        ("기계설비공사", "기계 설비 공사", "설비공사", "냉난방설비"),
        ("기계설비공사업", "기계가스설비공사업", "기계설비공사"),
    ),
    (
        ("가스시설공사", "가스시설시공", "가스 난방 공사", "가스난방공사", "난방공사", "기계가스설비"),
        ("가스시설시공업제1종", "가스시설시공업제2종", "가스시설시공업제3종", "가스난방공사업", "기계가스설비공사업"),
    ),
    (
        ("도장공사", "도색공사", "페인트공사"),
        ("도장공사업", "도장ㆍ습식ㆍ방수ㆍ석공사업", "도장공사"),
    ),
    (
        ("방수공사", "습식방수", "누수보수"),
        ("습식ㆍ방수공사업", "도장ㆍ습식ㆍ방수ㆍ석공사업", "방수공사"),
    ),
    (
        ("철근콘크리트", "철콘", "콘크리트공사"),
        ("철근ㆍ콘크리트공사업", "철근콘크리트공사"),
    ),
    (
        ("토공사", "지반조성", "흙막이", "터파기"),
        ("토공사업", "지반조성ㆍ포장공사업", "토공사"),
    ),
    (
        ("도로포장", "도로 포장", "포장공사", "포장 공사", "지반조성포장", "지반조성 포장"),
        ("지반조성ㆍ포장공사업", "포장공사업", "포장공사"),
    ),
    (
        ("조경식재", "조경공사", "조경시설물", "잔디식재"),
        ("조경공사업", "조경식재공사업", "조경식재ㆍ시설물공사업", "조경시설물설치공사업"),
    ),
)


_VENDOR_SERVICE_LICENSE_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("건축설계", "건축 설계", "설계용역", "건축감리", "공사감리"),
        ("건축사사무소", "건축사", "건축설계", "공사감리"),
    ),
    (
        ("기술용역", "엔지니어링", "토목설계", "실시설계", "기본설계", "건설사업관리", "건설사업관리용역", "건설기술용역", "감리용역", "CM용역"),
        ("엔지니어링사업자", "기술사사무소", "건설엔지니어링업", "건설기술용역업", "엔지니어링서비스", "건설사업관리", "감리"),
    ),
    (
        ("측량", "측량용역", "공공측량", "지적측량"),
        ("측량업", "공공측량업", "일반측량업", "측량용역"),
    ),
    (
        ("폐기물", "폐기물처리", "폐기물수집", "폐기물운반"),
        ("폐기물수집운반업", "폐기물처리업", "폐기물처리용역"),
    ),
    (
        ("소독", "방역", "소독방역", "방역용역"),
        ("소독업", "방역서비스", "소독용역"),
    ),
    (
        ("청소", "청소용역", "환경미화", "건물청소"),
        ("건물위생관리업", "위생관리용역업", "청소용역"),
    ),
    (
        ("경비", "경비용역", "시설경비", "기계경비", "특수경비"),
        ("시설경비업무", "시설경비업", "기계경비업무", "기계경비업", "특수경비업무", "특수경비업"),
    ),
    (
        ("시설관리", "청사관리", "건물관리", "청사유지관리"),
        ("건물(시설)관리용역", "시설관리", "건물관리", "시설물관리를 전문으로 하는 자"),
    ),
    (
        ("소프트웨어유지보수", "시스템유지보수", "정보시스템유지보수", "전산유지보수"),
        ("소프트웨어사업자(컴퓨터관련서비스사업)", "소프트웨어사업자", "정보시스템유지관리서비스"),
    ),
    (
        ("전기안전관리", "전기안전관리대행", "전기안전점검"),
        ("전기안전관리", "전기안전관리대행", "전기공사업"),
    ),
    (
        ("소방시설점검", "소방시설 점검", "소방점검", "소방시설관리"),
        ("전문소방시설공사업", "일반소방시설공사업", "소방시설", "소방"),
    ),
    (
        ("건축물안전점검", "건축물 안전점검", "시설물안전점검", "정밀안전점검"),
        ("시설물유지관리업", "안전진단", "건축물안전점검", "건축사사무소", "건설엔지니어링업"),
    ),
    (
        ("행사", "축제", "행사용역", "행사기획", "행사대행", "이벤트"),
        ("행사", "이벤트", "기타행사기획및대행서비스", "공연기획및대행서비스", "전시회기획및대행서비스"),
    ),
    (
        ("교육훈련", "교육 용역", "훈련 용역", "연수", "강의", "교육운영"),
        ("교육서비스", "교육훈련서비스", "기타교육서비스", "교육운영용역", "강의서비스"),
    ),
    (
        ("학술연구", "연구용역", "정책연구", "조사용역", "실태조사"),
        ("학술연구용역", "학술.연구용역", "학술 연구용역", "연구용역", "연구개발서비스", "조사연구서비스", "정책연구용역"),
    ),
    (
        ("교통영향평가", "교통량조사", "교통량 조사", "교통조사"),
        ("엔지니어링사업(교통)", "교통영향평가", "교통조사", "학술.연구용역", "학술연구용역"),
    ),
    (
        ("지반조사", "지질조사", "토질조사"),
        ("엔지니어링사업(토질", "엔지니어링사업(지질", "지반조사", "지질및지반조사", "토질조사"),
    ),
    (
        ("환경영향평가", "환경조사", "환경 조사"),
        ("환경영향평가업", "환경전문공사업", "환경컨설팅회사", "학술.연구용역", "학술연구용역"),
    ),
    (
        ("원가계산", "원가검토", "계약원가", "예정가격 검토"),
        ("원가계산용역", "원가계산기관", "회계서비스", "회계감사"),
    ),
)


def _vendor_construction_compact(value: str) -> str:
    return re.sub(r"[\sㆍ·\.\-/_,()]+", "", str(value or "")).lower()


def _vendor_requested_construction_terms(q: str) -> list[str]:
    compact = _vendor_construction_compact(q)
    terms: list[str] = []
    for markers, licenses in _VENDOR_CONSTRUCTION_LICENSE_GROUPS:
        if any(_vendor_construction_compact(marker) in compact for marker in markers):
            for license_name in licenses:
                if license_name not in terms:
                    terms.append(license_name)
    if any(marker in compact for marker in ("상하수도", "상수도설비", "하수도설비")):
        terms = [
            term
            for term in terms
            if _vendor_construction_compact(term)
            not in {"기계설비공사업", "기계가스설비공사업", "기계설비공사"}
        ]
    return terms


def _vendor_has_construction_material_intent(q: str) -> bool:
    compact = _vendor_compact(q)
    return any(
        term in compact
        for term in (
            "자재",
            "재료",
            "관급",
            "직접구매",
            "구매",
            "납품",
            "아스콘",
            "아스팔트",
            "아스팔트콘크리트",
            "포장재",
        )
    )


def _vendor_requested_service_terms(q: str) -> list[str]:
    compact = _vendor_construction_compact(q)
    terms: list[str] = []
    for markers, licenses in _VENDOR_SERVICE_LICENSE_GROUPS:
        if any(marker in compact for marker in ("통역", "번역", "통번역")) and any(
            _vendor_construction_compact(marker) in {"행사", "행사용역", "행사기획", "행사대행", "이벤트"}
            for marker in markers
        ):
            continue
        if any(_vendor_construction_compact(marker) in compact for marker in markers):
            for license_name in licenses:
                if license_name not in terms:
                    terms.append(license_name)
    return terms


def _vendor_query_plan(q: str) -> list[dict[str, str]]:
    raw_text = str(q or "")
    text = _vendor_intent_text(raw_text) or raw_text
    compact = _vendor_compact(text)
    plan: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    canonical_name, normalized_terms = _vendor_normalized_item_terms(text)
    direct_or_sme_query = any(marker in compact for marker in ("직접생산", "직생", "중기간경쟁", "중소기업자간경쟁"))
    service_terms = _vendor_requested_service_terms(text)
    service_intent = bool(service_terms) or any(
        marker in compact
        for marker in ("용역", "위탁", "대행", "행사", "축제", "공연", "전시", "교육", "연구", "감리", "평가")
    )
    if (
        service_intent
        and canonical_name in {"운영체제", "소프트웨어"}
        and "운영" in compact
        and not any(marker in compact for marker in ("운영체제", "소프트웨어", "프로그램", "시스템", "sw"))
    ):
        canonical_name = ""
        normalized_terms = []

    for term in _vendor_requested_construction_terms(text):
        _vendor_add_plan(plan, seen, "license", term, f"공사업 면허: {term}")
    for term in service_terms:
        _vendor_add_plan(plan, seen, "license", term, f"용역 면허/업종: {term}")

    if any(term in compact for term in ("인쇄", "인쇄물", "홍보물", "리플릿", "책자", "브로슈어", "포스터", "카탈로그", "현수막")):
        if any(marker in compact for marker in ("직접생산", "직생", "중기간경쟁", "중소기업자간경쟁")):
            direct_print_terms = ["인쇄물", "기타인쇄물", "현수막", "종이인쇄물제작서비스"]
            direct_print_terms.sort(key=lambda term: 0 if _vendor_compact(term) in compact else 1)
            for term in direct_print_terms:
                _vendor_add_plan(plan, seen, "direct_production", term, f"직접생산: {term}")
        print_terms = ["인쇄물", "기타인쇄물", "상업인쇄물", "홍보물", "현수막"]
        if "현수막" in compact:
            print_terms.sort(key=lambda term: 0 if term == "현수막" else 1)
        for term in print_terms:
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
        for term in ("인쇄", "인쇄사"):
            _vendor_add_plan(plan, seen, "license", term, f"면허/업종: {term}")
    elif any(term in compact for term in ("법률자문", "법률", "변호사", "법률사무소", "법무법인")):
        for term in ("법률", "변호", "법률사무소", "변호사사무소"):
            _vendor_add_plan(plan, seen, "company_name", term, f"업체명: {term}")
        for term in ("변호사사무소", "법무법인", "법무서비스", "법무사업(사무소)"):
            _vendor_add_plan(plan, seen, "license", term, f"면허/업종: {term}")
        for term in ("법무서비스", "법률"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
    elif (
        any(term in compact for term in ("보안소프트웨어", "보안sw", "안티바이러스", "정보보호", "방화벽"))
        or ("백신" in compact and any(term in compact for term in ("프로그램", "소프트웨어", "sw", "보안")))
    ):
        if "방화벽" in compact:
            for term in ("방화벽장치", "보안소프트웨어"):
                _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
        else:
            for term in ("보안소프트웨어", "패키지소프트웨어개발및도입서비스", "소프트웨어"):
                _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
        for term in ("소프트웨어사업자(패키지소프트웨어개발.공급사업)", "소프트웨어사업자(컴퓨터관련서비스사업)"):
            _vendor_add_plan(plan, seen, "license", term, f"면허/업종: {term}")
    elif any(term in compact for term in ("통역", "번역", "통번역", "외국어")):
        if "번역" in compact and "통역" not in compact:
            translation_terms = ("번역", "번역서비스", "통번역", "통역")
        elif "통역" in compact and "번역" not in compact:
            translation_terms = ("통역", "통번역", "번역", "번역서비스")
        else:
            translation_terms = ("통번역", "통역", "번역", "번역서비스")
        for term in translation_terms:
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
        for term in ("통역", "번역"):
            _vendor_add_plan(plan, seen, "license", term, f"면허/업종: {term}")
    elif any(term in compact for term in ("아스콘", "아스팔트콘크리트", "아스팔트")):
        if direct_or_sme_query:
            for term in ("아스팔트콘크리트", "순환상온아스팔트콘크리트", "아스콘"):
                _vendor_add_plan(plan, seen, "direct_production", term, f"직접생산: {term}")
        for term in ("아스팔트콘크리트", "아스콘", "순환상온아스팔트콘크리트"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
    elif "토너" in compact:
        for term in ("토너", "정품토너", "잉크토너", "프린터토너"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
    elif "드론" in compact:
        for term in ("드론", "무인항공기"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
    elif "분전반" in compact:
        for term in ("분전반", "배전반", "폐쇄형배전반"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
    elif any(term in compact for term in ("출입통제", "출입관리", "출입보안")):
        for term in ("출입통제시스템", "출입통제장치", "출입관리시스템", "출입통제"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
    elif any(term in compact for term in ("탄성포장", "체육시설탄성포장", "운동장탄성포장")):
        for term in ("탄성포장재", "체육시설탄성포장재", "운동장포장"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
        for term in ("조경시설물설치공사업", "지반조성ㆍ포장공사업", "포장공사업"):
            _vendor_add_plan(plan, seen, "license", term, f"면허: {term}")
    elif any(term in compact for term in ("도로포장", "포장공사", "지반조성포장", "포장업체")):
        for term in ("지반조성ㆍ포장공사업", "포장공사업", "토공사업"):
            _vendor_add_plan(plan, seen, "license", term, f"면허: {term}")
        if _vendor_has_construction_material_intent(text):
            for term in ("아스팔트콘크리트", "아스콘", "순환상온아스팔트콘크리트"):
                _vendor_add_plan(plan, seen, "product", term, f"보조 품목/자재: {term}")
    elif any(term in compact for term in ("천연잔디", "잔디조성", "잔디식재", "잔디시공", "운동장잔디")):
        for term in ("잔디", "조경식재공사", "토양개량", "복합비료"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
        for term in ("조경식재공사업", "조경식재ㆍ시설물공사업"):
            _vendor_add_plan(plan, seen, "license", term, f"면허: {term}")
        _vendor_add_plan(plan, seen, "company_name", "에코그린", "업체명: 에코그린")
    elif "조경" in compact:
        for term in ("조경공사업", "조경식재공사업", "조경식재ㆍ시설물공사업", "조경시설물설치공사업"):
            _vendor_add_plan(plan, seen, "license", term, f"면허: {term}")
        for term in ("조경식재공사", "기타조경시설물"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
        _vendor_add_plan(plan, seen, "company_name", "에코그린", "업체명: 에코그린")

    if canonical_name not in {"", "행사용역", "시설관리용역"}:
        if direct_or_sme_query:
            direct_terms = [*normalized_terms]
            if canonical_name == "컴퓨터":
                direct_terms = [term for term in direct_terms if term in {"데스크톱컴퓨터", "노트북컴퓨터"}]
            elif canonical_name == "노트북":
                direct_terms = [term for term in direct_terms if term in {"노트북컴퓨터", "노트북"}]
            elif canonical_name == "주방기기":
                direct_terms = [term for term in direct_terms if term in {"주방기기", "조리기기", "조리대"}]
            direct_terms.sort(key=lambda term: 0 if _vendor_compact(term) in compact else 1)
            for term in direct_terms:
                label_prefix = f"품목정규화({canonical_name})" if canonical_name else "품목정규화"
                _vendor_add_plan(plan, seen, "direct_production", term, f"{label_prefix}/직접생산: {term}")
        product_terms = [*normalized_terms]
        if canonical_name == "컴퓨터":
            product_terms = [term for term in product_terms if term in {"데스크톱컴퓨터", "노트북컴퓨터", "컴퓨터"}]
        elif canonical_name == "노트북":
            product_terms = [term for term in product_terms if term in {"노트북컴퓨터", "노트북", "휴대용 컴퓨터"}]
        elif canonical_name == "주방기기":
            product_terms = [term for term in product_terms if term in {"주방기기", "조리기기", "조리대"}]
        product_terms.sort(key=lambda term: 0 if _vendor_compact(term) in compact else 1)
        for term in product_terms:
            label_prefix = f"품목정규화({canonical_name})" if canonical_name else "품목정규화"
            _vendor_add_plan(plan, seen, "product", term, f"{label_prefix}: {term}")
            if _vendor_term_should_search_license(term):
                _vendor_add_plan(plan, seen, "license", term, f"{label_prefix}/면허: {term}")

    elif any(term in compact for term in ("행사용역", "행사", "축제", "발대식", "기념식", "행사기획", "행사대행", "이벤트")):
        for term in ("행사", "기타행사기획및대행서비스", "공연기획및대행서비스", "전시회기획및대행서비스"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
        for term in ("행사", "이벤트"):
            _vendor_add_plan(plan, seen, "license", term, f"면허/업종: {term}")
    elif any(term in compact for term in ("청사경비", "경비용역", "시설경비", "무인경비", "기계경비", "특수경비")):
        for term in ("시설경비업무", "시설경비업", "기계경비업무", "기계경비업", "특수경비업무", "특수경비업", "경비용역"):
            _vendor_add_plan(plan, seen, "license", term, f"면허: {term}")
        for term in ("시설물경비서비스", "경비"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
    elif any(term in compact for term in ("청사관리", "건물관리", "시설관리", "청사유지관리")):
        for term in ("건물(시설)관리용역", "시설관리", "건물관리", "시설물관리를 전문으로 하는 자"):
            _vendor_add_plan(plan, seen, "license", term, f"면허/업종: {term}")
        for term in ("시설관리용역", "건물관리", "시설관리", "청소", "경비"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
        for term in ("청소용역", "시설경비업무"):
            _vendor_add_plan(plan, seen, "license", term, f"면허/업종: {term}")
    elif any(term in compact for term in ("빔프로젝트", "빔프로젝터", "프로젝터", "비디오프로젝터")):
        for term in ("비디오프로젝터", "프로젝터"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
    elif "방향제" in compact:
        for term in ("방향제", "탈취제", "공기청향제"):
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")

    default_terms = [
        "컴퓨터", "노트북", "서버", "데스크톱", "프린터", "복합기",
        "보안용카메라", "CCTV", "소프트웨어", "번역", "통역",
        "보안소프트웨어", "보안SW", "안티바이러스", "정보보호", "방화벽",
        "청소", "경비", "냉난방기", "에어컨", "공기청정기",
        "LED", "조명", "책상", "의자", "가구", "캐비닛", "보관함",
        "주방기기", "급식", "레미콘", "아스콘", "아스팔트콘크리트",
        "스텐밴드", "스테인리스밴드",
        "탄성포장재", "포장공사", "도로포장", "방수공사",
    ]
    for term in default_terms:
        if term.lower() in text.lower() or _vendor_compact(term) in compact:
            _vendor_add_plan(plan, seen, "product", term, f"품목: {term}")
            if _vendor_term_should_search_license(text) or _vendor_term_should_search_license(term):
                _vendor_add_plan(plan, seen, "license", term, f"면허/업종: {term}")

    if not plan:
        _vendor_add_plan(plan, seen, "product", text, f"품목: {text}")
        _vendor_add_plan(plan, seen, "license", text, f"면허/업종: {text}")
        _vendor_add_plan(plan, seen, "company_name", text, f"업체명: {text}")
    return plan


def _vendor_row_relevance_score(row: dict[str, str], q: str) -> int:
    tokens = _vendor_query_tokens(q)
    if not tokens:
        return 1
    product_text = " ".join(str(row.get(field) or "") for field in (
        "main_products",
        "shopping_mall_product_summary",
        "mas_product_summary",
        "certified_product_summary",
        "direct_production_summary",
        "venture_nara_product_summary",
        "venture_nara_order_summary",
    )).lower()
    license_text = str(row.get("license_or_business_type") or "").lower()
    company_text = str(row.get("company_name") or "").lower()
    score = 0
    for token in tokens:
        token_l = str(token).lower()
        if not token_l:
            continue
        if token_l in product_text:
            score += 4
        if token_l in license_text:
            score += 2
        if token_l in company_text:
            score += 1
    return score


def _vendor_match_rank_score(row: dict[str, str], q: str) -> int:
    compact_q = _vendor_compact(q)
    label = str(row.get("matched_query_label") or "")
    matched_query = str(row.get("matched_query") or "")
    product_text = _vendor_compact(" ".join(str(row.get(field) or "") for field in (
        "main_products",
        "shopping_mall_product_summary",
        "mas_product_summary",
        "certified_product_summary",
        "direct_production_summary",
        "venture_nara_product_summary",
        "venture_nara_order_summary",
        "contract_history_summary",
        "contract_history_match",
    )))
    license_text = _vendor_compact(str(row.get("license_or_business_type") or ""))
    company_text = _vendor_compact(str(row.get("company_name") or ""))
    score = _vendor_row_relevance_score(row, q)
    policy_text = " ".join(str(row.get(field) or "") for field in (
        "policy_company_labels",
        "policy_subtypes",
        "candidate_types",
        "procurement_attributes",
    )).lower()
    service_terms = _vendor_requested_service_terms(q)
    service_intent = bool(service_terms) or any(term in compact_q for term in ("용역", "과업", "위탁", "교육훈련", "학술연구", "원가계산", "감리", "건설사업관리"))
    if service_intent:
        service_term_hit = any(_vendor_compact(term) in license_text or _vendor_compact(term) in product_text for term in service_terms)
        service_keyword_hit = any(
            term in license_text or term in product_text
            for term in ("용역", "서비스", "교육", "훈련", "학술", "연구", "원가계산", "감리", "건설사업관리", "시설관리", "폐기물", "행사", "번역")
        )
        goods_only_evidence = any(
            term in product_text
            for term in ("cctv", "카메라", "타일", "모니터", "컴퓨터", "프린터", "조명", "밸브", "펌프", "책상", "의자")
        )
        if service_term_hit:
            score += 40
        elif service_keyword_hit:
            score += 18
        if goods_only_evidence and not service_term_hit and not service_keyword_hit:
            score -= 35

    if "품목정규화" in label:
        score += 12
    if "preferred" in label.lower():
        score += 4
    if matched_query and _vendor_compact(matched_query) in product_text:
        score += 14
    if matched_query and _vendor_compact(matched_query) in license_text:
        score += 8
    if matched_query and _vendor_compact(matched_query) in company_text:
        score += 10

    exact_groups: list[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
        (("음향", "조명", "임대"), ("영상음향및조명장치임대서비스", "음향장비", "조명장비"), ("led", "다운라이트", "경관조명", "교통신호")),
        (("빔프로젝터", "프로젝터"), ("비디오프로젝터", "프로젝터"), ("화이트보드", "전자칠판")),
        (("토너",), ("토너", "재제조토너", "정품토너"), ("복사용지", "프린트및복사용지", "3d프린터", "3차원프린터")),
        (("드론",), ("드론", "초경량비행장치"), ("정보시스템개발서비스", "소프트웨어")),
        (("사무용가구", "중기간경쟁제품"), ("책상", "의자", "사무용가구", "보조책상"), ("기타미분류가구",)),
        (("방화벽",), ("방화벽", "방화벽장치", "보안소프트웨어"), ("소프트웨어사업자",)),
        (("도로포장", "포장공사"), ("지반조성포장공사업", "포장공사업", "포장공사"), ("아스팔트콘크리트", "순환상온아스팔트콘크리트")),
        (("탄성포장", "탄성포장재"), ("탄성포장재", "체육시설탄성포장재", "운동장포장"), ("조경시설물설치공사업",)),
        (("현수막",), ("현수막",), ("인쇄물", "기타인쇄물", "상업인쇄물")),
        (("pc", "데스크톱", "데스크탑"), ("데스크톱컴퓨터", "노트북컴퓨터", "컴퓨터서버"), ("컴퓨터책상",)),
        (("노트북", "랩톱", "랩탑"), ("노트북컴퓨터", "휴대용컴퓨터"), ("컴퓨터책상",)),
    ]
    for query_terms, positive_terms, negative_terms in exact_groups:
        if not any(_vendor_compact(term) in compact_q for term in query_terms):
            continue
        positive_match = any(_vendor_compact(term) in product_text or _vendor_compact(term) in license_text for term in positive_terms)
        negative_product_match = any(_vendor_compact(term) in product_text for term in negative_terms)
        negative_license_match = any(_vendor_compact(term) in license_text for term in negative_terms)
        if positive_match:
            score += 35
        if negative_product_match or (negative_license_match and not positive_match):
            score -= 25

    if any(term in compact_q for term in ("소독방역", "방역용역", "방역서비스", "소독용역")):
        if any(term in product_text or term in license_text for term in ("방역서비스", "소독업")):
            score += 35
        if any(term in product_text for term in ("손소독제", "살균제")) and "소독업" not in license_text:
            score -= 30

    if "책상" in compact_q:
        if "책상" in product_text or "책상" in license_text:
            score += 45
        if "의자" in product_text and "책상" not in product_text:
            score -= 35
    if "의자" in compact_q:
        if "의자" in product_text or "의자" in license_text:
            score += 45
        if "책상" in product_text and "의자" not in product_text:
            score -= 20

    if any(term in compact_q for term in ("예방접종", "접종백신", "의약품백신")):
        if any(term in product_text for term in ("소프트웨어", "보안소프트웨어", "패키지소프트웨어")):
            score -= 80

    if any(term in compact_q for term in ("법률자문", "법률", "변호사", "법률사무소", "법무법인")):
        if any(term in company_text or term in license_text for term in ("변호사", "법률사무소", "법무법인")):
            score += 45
        elif any(term in company_text or term in license_text for term in ("법무사", "법무사업")):
            score += 10

    if any(term in compact_q for term in ("벤처나라", "거래실적", "구매실적", "납품실적", "주문거래")):
        if _vendor_compact(str(row.get("venture_nara_order_summary") or "")):
            score += 55
        elif _vendor_compact(str(row.get("venture_nara_product_summary") or "")):
            score += 30
        else:
            score -= 10

    if any(term in compact_q for term in ("직접생산", "직생")):
        direct_text = _vendor_compact(
            " ".join(
                str(row.get(field) or "")
                for field in (
                    "direct_production_summary",
                    "direct_production_certificate_products",
                    "direct_production_flags",
                )
            )
        )
        if direct_text:
            score += 25
        else:
            score -= 5

    if any(term in compact_q for term in ("종합쇼핑몰", "쇼핑몰", "mas", "다수공급자")):
        if _vendor_compact(str(row.get("shopping_mall_product_summary") or "")):
            score += 25
        if _vendor_compact(str(row.get("mas_product_summary") or "")):
            score += 25

    if "토너" in compact_q:
        office_vendor_terms = ("전산", "사무", "문구", "잉크", "oa", "디지털", "정보", "프린터", "복사기")
        food_license_terms = ("식육", "축산", "식품", "급식소", "농산", "수산")
        has_procurement_evidence = any(
            _vendor_compact(str(row.get(field) or ""))
            for field in (
                "shopping_mall_product_summary",
                "mas_product_summary",
                "certified_product_summary",
                "direct_production_summary",
            )
        )
        if any(term in company_text or term in license_text for term in office_vendor_terms):
            score += 18
        if any(term in license_text for term in food_license_terms) and not has_procurement_evidence:
            score -= 35

    for item in _vendor_requested_policy_preferences(q):
        rule = next((rule for rule in _VENDOR_POLICY_PREFERENCE_RULES if rule[0] == item["key"]), None)
        if rule and any(str(token).lower() in policy_text for token in rule[2]):
            score += 45

    return score


def _vendor_query_has_any(q: str, terms: tuple[str, ...]) -> bool:
    compact = _vendor_compact(q)
    return any(_vendor_compact(term) in compact for term in terms)


def _vendor_is_medical_vaccine_query(q: str) -> bool:
    compact = _vendor_compact(q)
    return "백신" in compact and any(term in compact for term in ("예방접종", "접종", "의약품", "의료용", "병원"))


def _vendor_forbidden_row_terms(q: str) -> tuple[str, ...]:
    if _vendor_query_has_any(q, ("행사용역", "행사", "발대식", "기념식", "행사기획", "행사대행", "이벤트")):
        return ("건물청소서비스", "청소서비스", "청소용역", "시설물경비서비스", "경비용역")
    if _vendor_query_has_any(q, ("방향제", "탈취제", "공기청향제")):
        return ("화장실용화장지", "화장실칸막이", "이동식화장실", "화장지")
    if _vendor_query_has_any(q, ("전기안전관리", "전기안전관리대행", "전기안전점검")):
        return ("행사대행", "행사기획", "전시회기획", "축제기획", "전시홍보관", "전시부스")
    if _vendor_query_has_any(q, ("번역", "번역용역", "통번역", "통역")):
        return ("청소서비스", "행사기획", "행사대행", "조명장치", "경비용역")
    if _vendor_query_has_any(q, ("청사경비", "경비용역", "시설경비", "무인경비", "기계경비", "특수경비")):
        return ("행사기획", "행사대행", "번역서비스", "조명장치")
    if _vendor_query_has_any(q, ("청소용역", "건물청소", "환경미화", "청소")):
        return ("시설물경비서비스", "경비용역", "행사기획", "행사대행", "번역서비스")
    return ()


def _vendor_product_matches_query(row: dict[str, str], q: str) -> bool:
    tokens = _vendor_query_tokens(q)
    if not tokens:
        return False
    product_text = _vendor_compact(" ".join(str(row.get(field) or "") for field in (
        "main_products",
        "shopping_mall_product_summary",
        "mas_product_summary",
        "certified_product_summary",
        "direct_production_summary",
        "venture_nara_product_summary",
        "venture_nara_order_summary",
    )))
    return any(_vendor_compact(token) and _vendor_compact(token) in product_text for token in tokens)


def _vendor_has_forbidden_terms(row: dict[str, str], q: str) -> bool:
    forbidden = _vendor_forbidden_row_terms(q)
    if not forbidden:
        return False
    if _vendor_product_matches_query(row, q):
        return False
    haystack = " ".join(str(row.get(field) or "") for field in (
        "company_name",
        "license_or_business_type",
        "main_products",
        "shopping_mall_product_summary",
        "mas_product_summary",
        "certified_product_summary",
        "direct_production_summary",
        "venture_nara_product_summary",
        "venture_nara_order_summary",
    ))
    return any(term in haystack for term in forbidden)


def _vendor_filter_relevant_rows(rows: list[dict[str, str]], q: str) -> list[dict[str, str]]:
    if not rows:
        return rows
    scored = [(row, _vendor_match_rank_score(row, q)) for row in rows]
    relevant = [(row, score) for row, score in scored if score > 0]
    if relevant:
        filtered = [(row, score) for row, score in relevant if not _vendor_has_forbidden_terms(row, q)]
        return [row for row, _ in sorted(filtered or relevant, key=lambda item: item[1], reverse=True)]
    return rows


def _vendor_available_columns(conn) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute("PRAGMA table_info(chatbot_company_candidate_view)").fetchall()}
    except Exception:
        return set()


def _vendor_basic_search_rows(company_db, q: str, *, region: str = "부산", limit: int = 50) -> list[dict[str, str]]:
    connect = getattr(company_db, "_connect", None)
    if not callable(connect):
        return []
    conn = connect()
    if conn is None:
        return []
    try:
        columns = _vendor_available_columns(conn)
        searchable_columns = [
            col
            for col in (
                "company_name",
                "license_or_business_type",
                "main_products",
                "candidate_types",
                "policy_subtypes_raw",
                "manufacturer_type",
                "shopping_mall_product_summary_raw",
                "mas_product_summary_raw",
                "certified_product_summary_raw",
                "direct_production_summary_raw",
                "venture_nara_product_summary_raw",
                "venture_nara_order_summary_raw",
                "location",
            )
            if col in columns
        ]
        if not searchable_columns:
            return []
        terms = [q, *_vendor_query_tokens(q)]
        clauses: list[str] = []
        params: list[str] = []
        for term in terms:
            if not term:
                continue
            sub = []
            for col in searchable_columns:
                sub.append(f"COALESCE({col}, '') LIKE ?")
                params.append(f"%{term}%")
            clauses.append("(" + " OR ".join(sub) + ")")
        if not clauses:
            return []
        order_parts = ["CASE WHEN business_status = 'active' THEN 0 ELSE 1 END"] if "business_status" in columns else []
        if "shopping_mall_flags_raw" in columns:
            order_parts.append("CASE WHEN shopping_mall_flags_raw IS NOT NULL AND shopping_mall_flags_raw != '' THEN 0 ELSE 1 END")
        order_parts.append("company_name")
        sql = f"""
            SELECT *
            FROM chatbot_company_candidate_view
            WHERE {' OR '.join(clauses)}
            ORDER BY {', '.join(order_parts)}
            LIMIT ?
        """
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for db_row in conn.execute(sql, [*params, max(limit * 2, limit)]).fetchall():
            row = _vendor_row_from_db(dict(db_row))
            row["matched_source"] = "local_view_basic"
            row["matched_query"] = q
            row["matched_query_label"] = f"기본검색: {q}"
            key = row.get("company_id") or row.get("company_name")
            if not key or key in seen:
                continue
            if _vendor_is_closed_or_suspended(row):
                continue
            if not _vendor_region_matches(row, region):
                continue
            seen.add(key)
            rows.append(row)
            if len(rows) >= limit:
                break
        return rows
    except Exception:
        return []
    finally:
        conn.close()


_VENDOR_HISTORY_STOPWORDS = {
    "busan",
    "krw",
    "goods",
    "service",
    "vendor",
    "candidate",
    "contract",
    "부산",
    "부산업체",
    "지역업체",
    "업체",
    "후보",
    "추천",
    "가능",
    "가능한",
    "과거",
    "수행",
    "수행이력",
    "이력",
    "있는",
    "보유",
    "대행",
    "계약",
    "구매",
    "구입",
    "발주",
    "예산",
    "금액",
    "관리",
    "교체",
    "설치",
    "구축",
    "운영",
    "유지",
    "보수",
    "물품",
    "용역",
    "공사",
    "조달",
    "나라장터",
    "종합쇼핑몰",
    "쇼핑몰",
    "제안",
    "리스트",
    "목록",
    "보여줘",
    "찾아줘",
}


def _vendor_contract_history_terms(q: str) -> list[str]:
    text = str(q or "")
    terms: list[str] = []
    terms.extend(re.findall(r"[^\W_]{2,}", text, flags=re.UNICODE))
    compact_intent = _vendor_compact(_vendor_intent_text(text))
    precise_camera_history_terms = (
        (("디지털카메라", "디카"), ("디지털카메라", "디카")),
        (("비디오카메라", "캠코더"), ("비디오카메라", "캠코더")),
        (("웹카메라", "웹캠"), ("웹카메라", "웹캠")),
        (("아날로그카메라",), ("아날로그카메라",)),
    )
    for markers, aliases in precise_camera_history_terms:
        if any(_vendor_compact(marker) in compact_intent for marker in markers):
            terms.extend(aliases)
            break
    else:
        terms.extend(_vendor_query_tokens(text))
    cleaned: list[str] = []
    for term in terms:
        term = str(term or "").strip().lower()
        term = re.sub(r"^[^\w가-힣]+|[^\w가-힣]+$", "", term)
        if len(term) < 2 or term.isdigit() or term in _VENDOR_HISTORY_STOPWORDS:
            continue
        if term not in cleaned:
            cleaned.append(term)
    return cleaned[:8]


def _vendor_contract_history_min_hits(terms: list[str]) -> int:
    return 2 if len(terms) >= 3 else 1


def _vendor_contract_history_table_ready(conn) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = 'vendor_contract_history' LIMIT 1"
        ).fetchone()
        return bool(row)
    except Exception:
        return False


def _vendor_contract_history_search_rows(company_db, q: str, *, region: str = "부산", limit: int = 30) -> list[dict[str, str]]:
    connect = getattr(company_db, "_connect", None)
    if not callable(connect):
        return []
    terms = _vendor_contract_history_terms(q)
    if not terms:
        return []
    conn = connect()
    if conn is None:
        return []
    try:
        if not _vendor_contract_history_table_ready(conn):
            return []
        clauses = " OR ".join(["LOWER(h.search_text) LIKE ?" for _ in terms])
        match_expr = " + ".join(["CASE WHEN LOWER(h.search_text) LIKE ? THEN 1 ELSE 0 END" for _ in terms])
        match_params = [f"%{term}%" for term in terms]
        where_params = [f"%{term}%" for term in terms]
        required_hits = _vendor_contract_history_min_hits(terms)
        sql = f"""
            WITH row_hits AS (
                SELECT
                    h.company_id,
                    h.contract_amount,
                    h.contract_date,
                    ({match_expr}) AS term_hits
                FROM vendor_contract_history h
                WHERE {clauses}
            ),
            matched AS (
                SELECT
                    company_id,
                    COUNT(*) AS history_count,
                    SUM(COALESCE(contract_amount, 0)) AS history_amount,
                    MAX(contract_date) AS history_last_date,
                    MAX(term_hits) AS max_term_hits
                FROM row_hits
                WHERE term_hits >= ?
                GROUP BY company_id
            )
            SELECT v.*
            FROM matched m
            JOIN chatbot_company_candidate_view v ON v.company_id = m.company_id
            ORDER BY m.max_term_hits DESC, m.history_count DESC, m.history_amount DESC, m.history_last_date DESC
            LIMIT ?
        """
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for db_row in conn.execute(sql, [*match_params, *where_params, required_hits, max(limit * 3, limit)]).fetchall():
            row = _vendor_row_from_db(dict(db_row))
            row["matched_source"] = "contract_history"
            row["matched_query"] = " | ".join(terms)
            row["matched_query_label"] = f"과거 계약이력: {' / '.join(terms[:3])}"
            key = row.get("company_id") or row.get("company_name")
            if not key or key in seen:
                continue
            if _vendor_is_closed_or_suspended(row):
                continue
            if not _vendor_region_matches(row, region):
                continue
            seen.add(key)
            rows.append(row)
            if len(rows) >= limit:
                break
        return rows
    except Exception:
        return []
    finally:
        conn.close()


def _vendor_contract_history_summary(conn, company_id: str, terms: list[str]) -> dict[str, object] | None:
    if not company_id or not terms:
        return None
    clauses = " OR ".join(["LOWER(search_text) LIKE ?" for _ in terms])
    match_expr = " + ".join(["CASE WHEN LOWER(search_text) LIKE ? THEN 1 ELSE 0 END" for _ in terms])
    match_params = [f"%{term}%" for term in terms]
    where_params = [f"%{term}%" for term in terms]
    required_hits = _vendor_contract_history_min_hits(terms)
    try:
        row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS history_count,
                SUM(COALESCE(contract_amount, 0)) AS history_amount,
                MAX(contract_date) AS history_last_date
            FROM (
                SELECT contract_amount, contract_date, ({match_expr}) AS term_hits
                FROM vendor_contract_history
                WHERE company_id = ? AND ({clauses})
            )
            WHERE term_hits >= ?
            """,
            [*match_params, company_id, *where_params, required_hits],
        ).fetchone()
        if not row or int(row["history_count"] or 0) <= 0:
            return None
        samples = conn.execute(
            f"""
            SELECT contract_type, contract_name, agency_name, contract_amount, contract_date
            FROM (
                SELECT contract_type, contract_name, agency_name, contract_amount, contract_date, ({match_expr}) AS term_hits
                FROM vendor_contract_history
                WHERE company_id = ? AND ({clauses})
            )
            WHERE term_hits >= ?
            ORDER BY contract_date DESC, contract_amount DESC
            LIMIT 3
            """,
            [*match_params, company_id, *where_params, required_hits],
        ).fetchall()
        return {
            "count": int(row["history_count"] or 0),
            "amount": int(row["history_amount"] or 0),
            "last_date": str(row["history_last_date"] or ""),
            "samples": [dict(sample) for sample in samples],
        }
    except Exception:
        return None


def _vendor_contract_history_detail_payload(company_id: str, q: str = "", *, limit: int = 20) -> dict[str, object]:
    company_id = str(company_id or "").strip()
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id is required")
    limit = max(1, min(int(limit or 20), 100))
    company_db = _vendor_import_company_db()
    connect = getattr(company_db, "_connect", None)
    if not callable(connect):
        raise HTTPException(status_code=503, detail="company DB connection unavailable")
    conn = connect()
    if conn is None:
        raise HTTPException(status_code=503, detail="company DB connection unavailable")
    try:
        if not _vendor_contract_history_table_ready(conn):
            raise HTTPException(status_code=404, detail="vendor contract history table not found")
        terms = _vendor_contract_history_terms(q)
        min_hits = _vendor_contract_history_min_hits(terms)
        if terms:
            like_terms = [f"%{term}%" for term in terms]
            score_expr = " + ".join(["CASE WHEN LOWER(search_text) LIKE ? THEN 1 ELSE 0 END" for _ in terms])
            where_terms = " OR ".join(["LOWER(search_text) LIKE ?" for _ in terms])
            count_sql = f"""
                SELECT
                    COUNT(*) AS history_count,
                    SUM(COALESCE(contract_amount, 0)) AS history_amount,
                    MAX(contract_date) AS history_last_date
                FROM (
                    SELECT contract_amount, contract_date, ({score_expr}) AS match_score
                    FROM vendor_contract_history
                    WHERE company_id = ? AND ({where_terms})
                )
                WHERE match_score >= ?
            """
            count_params = [*like_terms, company_id, *like_terms, min_hits]
            detail_sql = f"""
                SELECT
                    history_id,
                    company_id,
                    company_name,
                    contract_type,
                    contract_name,
                    contract_amount,
                    contract_date,
                    agency_name,
                    product_classification_no,
                    product_classification_name,
                    product_mid_classification_name,
                    product_large_classification_name,
                    source_contract_no,
                    contractor_role,
                    contractor_share,
                    source_name,
                    ({score_expr}) AS match_score
                FROM vendor_contract_history
                WHERE company_id = ?
                  AND ({where_terms})
                  AND ({score_expr}) >= ?
                ORDER BY match_score DESC, contract_date DESC, contract_amount DESC
                LIMIT ?
            """
            detail_params = [*like_terms, company_id, *like_terms, *like_terms, min_hits, limit]
        else:
            count_sql = """
                SELECT
                    COUNT(*) AS history_count,
                    SUM(COALESCE(contract_amount, 0)) AS history_amount,
                    MAX(contract_date) AS history_last_date
                FROM vendor_contract_history
                WHERE company_id = ?
            """
            count_params = [company_id]
            detail_sql = """
                SELECT
                    history_id,
                    company_id,
                    company_name,
                    contract_type,
                    contract_name,
                    contract_amount,
                    contract_date,
                    agency_name,
                    product_classification_no,
                    product_classification_name,
                    product_mid_classification_name,
                    product_large_classification_name,
                    source_contract_no,
                    contractor_role,
                    contractor_share,
                    source_name,
                    0 AS match_score
                FROM vendor_contract_history
                WHERE company_id = ?
                ORDER BY contract_date DESC, contract_amount DESC
                LIMIT ?
            """
            detail_params = [company_id, limit]
        summary_row = conn.execute(count_sql, count_params).fetchone()
        rows = []
        for row in conn.execute(detail_sql, detail_params).fetchall():
            item = dict(row)
            item["contract_amount"] = int(item.get("contract_amount") or 0)
            rows.append(item)
        return {
            "company_id": company_id,
            "query": q,
            "matched_terms": terms,
            "limit": limit,
            "count": int(summary_row["history_count"] or 0) if summary_row else 0,
            "total_amount": int(summary_row["history_amount"] or 0) if summary_row else 0,
            "last_date": str(summary_row["history_last_date"] or "") if summary_row else "",
            "rows": rows,
            "limitations": [
                "Past contract history is reference evidence, not a legal eligibility confirmation.",
                "Licenses, direct-production certificates, MAS/shopping-mall status, and policy-company validity must be checked against original sources before notice or contract.",
                "Some long-term continuing contracts may have source-date limits.",
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"contract history lookup failed: {exc}") from exc
    finally:
        conn.close()


def _vendor_apply_contract_history_evidence(rows: list[dict[str, str | int]], q: str) -> list[dict[str, str | int]]:
    if not rows:
        return rows
    terms = _vendor_contract_history_terms(q)
    if not terms:
        return rows
    company_db = _vendor_import_company_db()
    connect = getattr(company_db, "_connect", None)
    if not callable(connect):
        return rows
    conn = connect()
    if conn is None:
        return rows
    try:
        if not _vendor_contract_history_table_ready(conn):
            return rows
        for row in rows:
            company_id = str(row.get("company_id") or "")
            summary = _vendor_contract_history_summary(conn, company_id, terms)
            if not summary:
                row.setdefault("contract_history_status_label", "과거 유사계약 이력 없음")
                continue
            count = int(summary.get("count") or 0)
            amount = int(summary.get("amount") or 0)
            last_date = str(summary.get("last_date") or "")
            samples = summary.get("samples") or []
            sample_labels = []
            for sample in samples:
                name = str(sample.get("contract_name") or "").strip()
                agency = str(sample.get("agency_name") or "").strip()
                date = str(sample.get("contract_date") or "").strip()
                label = " / ".join(part for part in (date, agency, name) if part)
                if label:
                    sample_labels.append(label)
            amount_label = _format_krw_short(amount) if amount else "금액 미상"
            row["contract_history_status_label"] = "과거 유사계약 수행이력 있음"
            row["contract_history_match"] = f"유사계약 {count:,}건 / {amount_label}"
            row["contract_history_summary"] = " | ".join(sample_labels[:3]) or row["contract_history_match"]
            row["contract_history_recent_count"] = str(count)
            row["contract_history_total_amount"] = str(amount)
            row["contract_history_last_date"] = last_date
            current_score = int(row.get("review_score") or 0)
            row["review_score"] = current_score + min(25, 8 + count * 2)
            if str(row.get("condition_match_type") or "").strip() in {"", "후보 표시", "확인 필요"}:
                row["condition_match_type"] = "과거 유사계약 이력 확인"
            if not str(row.get("condition_match_summary") or "").strip():
                row["condition_match_summary"] = row["contract_history_match"]
            checks = str(row.get("recommended_checks") or "")
            history_check = "과거 수행이력은 참고자료이며 현재 과업범위·면허·자격요건 재확인"
            if history_check not in checks:
                row["recommended_checks"] = " | ".join(part for part in (checks, history_check) if part)
        return rows
    except Exception:
        return rows
    finally:
        conn.close()


def _vendor_search_rows(q: str, *, region: str = "부산", limit: int = 50) -> list[dict[str, str]]:
    q = " ".join(str(q or "").split())
    if not q:
        raise HTTPException(status_code=400, detail="q query parameter is required")
    limit = max(1, min(int(limit or 50), 500))
    compact_q = _vendor_compact(q)
    service_terms_for_query = _vendor_requested_service_terms(q)
    service_intent_for_query = bool(service_terms_for_query) or any(
        marker in compact_q
        for marker in ("용역", "과업", "위탁", "대행", "교육", "연구", "감리", "평가", "조사", "점검", "유지관리")
    )
    company_db = _vendor_import_company_db()
    product_calls = [
        ("product", getattr(company_db, "search_by_product", None)),
        ("shopping_mall_product", getattr(company_db, "search_shopping_mall_product", None)),
    ]
    if _vendor_query_has_any(q, ("인증", "기술개발", "혁신", "우수조달", "시제품", "벤처나라")):
        product_calls.extend([
            ("certified_product", getattr(company_db, "search_certified_product", None)),
            ("innovation_product", getattr(company_db, "search_innovation_product", None)),
            ("excellent_procurement_product", getattr(company_db, "search_excellent_procurement_product", None)),
        ])
    calls_by_type = {
        "product": product_calls,
        "license": [("license", getattr(company_db, "search_by_license", None))],
        "company_name": [("company_name", getattr(company_db, "search_by_company_name", None))],
        "direct_production": [("direct_production", getattr(company_db, "search_by_direct_production", None))],
    }
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    multi_condition_query = _vendor_is_multi_condition_query(q)
    if multi_condition_query:
        calls_by_type["product"] = calls_by_type["product"][:2]
    per_call_limit = max(limit, 20)
    result_target = limit
    if _vendor_query_has_any(q, ("출입통제시스템", "출입통제장치", "출입관리시스템", "출입통제", "출입관리")):
        per_call_limit = min(per_call_limit, 12)
        result_target = min(result_target, 12)
    if multi_condition_query:
        # AND-style questions need evidence for more than the first matched
        # term. Keep each individual lookup bounded, but continue through the
        # plan so rows from the second/third condition can compete in ranking.
        per_call_limit = min(max(2, limit // 6), 4)
        result_target = min(max(limit // 2, 6), 10)
    if _vendor_query_has_any(q, ("번역", "번역용역", "통번역", "통역", "외국어")):
        result_target = min(result_target, 10)
        per_call_limit = min(per_call_limit, 10)
    query_plan = _vendor_query_plan(q)
    if not multi_condition_query:
        # The DB adapter already expands product aliases internally. Repeating
        # multiple normalized product terms at the API plan layer makes no-hit
        # searches scan the same large text summaries several times. Keep a
        # small cap for interactive dashboard latency while preserving explicit
        # AND-style multi-condition searches.
        max_product_plan_terms = max(1, min(int(os.getenv("VENDOR_PRODUCT_PLAN_TERM_LIMIT", "2")), 8))
        product_plan_count = 0
        bounded_plan: list[dict[str, str]] = []
        for item in query_plan:
            if item.get("search_type") == "product":
                product_plan_count += 1
                if product_plan_count > max_product_plan_terms:
                    continue
            bounded_plan.append(item)
        query_plan = bounded_plan
    if multi_condition_query:
        query_plan = query_plan[:12]
    min_plan_scans = min(2, len(query_plan)) if multi_condition_query else 1
    for plan_index, plan_item in enumerate(query_plan, 1):
        term = plan_item["term"]
        label = plan_item.get("label") or term
        source_calls = calls_by_type.get(plan_item["search_type"], [])
        min_source_scans = 2 if plan_item.get("search_type") == "product" and len(source_calls) >= 2 else 1
        for source_index, (source, func) in enumerate(source_calls, 1):
            if not callable(func):
                continue
            try:
                data = func(term, limit=per_call_limit) or {}
            except Exception:
                continue
            for candidate in data.get("candidates") or []:
                row = _vendor_row_from_candidate(candidate)
                row["matched_source"] = source
                row["matched_query"] = term
                row["matched_query_label"] = label
                key = row.get("company_id") or row.get("company_name")
                if not key or key in seen:
                    continue
                if _vendor_is_closed_or_suspended(row):
                    continue
                if not _vendor_region_matches(row, region):
                    continue
                seen.add(key)
                rows.append(row)
                if len(rows) >= result_target and source_index >= min_source_scans:
                    break
            if len(rows) >= result_target and source_index >= min_source_scans and (not multi_condition_query or plan_index >= min_plan_scans):
                break
        if len(rows) >= result_target and (not multi_condition_query or plan_index >= min_plan_scans):
            break
    if not rows:
        if _vendor_is_medical_vaccine_query(q):
            return []
        rows = _vendor_basic_search_rows(company_db, q, region=region, limit=limit)
    filtered_rows = _vendor_filter_relevant_rows(rows, q)
    if not filtered_rows and rows and not _vendor_is_medical_vaccine_query(q):
        fallback_rows = _vendor_basic_search_rows(company_db, q, region=region, limit=limit)
        fallback_filtered = _vendor_filter_relevant_rows(fallback_rows, q)
        if fallback_filtered:
            filtered_rows = fallback_filtered
        elif not service_intent_for_query:
            filtered_rows = fallback_rows
    return filtered_rows[:limit]


def _vendor_download_rows(*, active_only: bool = True, limit: int = 0) -> list[dict[str, str]]:
    company_db = _vendor_import_company_db()
    connect = getattr(company_db, "_connect", None)
    if not callable(connect):
        raise HTTPException(status_code=503, detail="company DB connection unavailable")
    conn = connect()
    if conn is None:
        raise HTTPException(status_code=503, detail="company DB file not found or disabled")
    try:
        where = (
            """
            WHERE COALESCE(NULLIF(TRIM(LOWER(business_status)), ''), 'unknown')
                  NOT IN ('inactive', 'closed', '폐업', '휴업', '종료', 'cancelled', 'canceled')
            """
            if active_only
            else ""
        )
        limit_sql = "LIMIT ?" if int(limit or 0) > 0 else ""
        params = [int(limit)] if int(limit or 0) > 0 else []
        sql = f"""
            SELECT *
            FROM chatbot_company_candidate_view
            {where}
            ORDER BY company_name
            {limit_sql}
        """
        db_rows = conn.execute(sql, params).fetchall()
        return [_vendor_row_from_db(dict(row)) for row in db_rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"vendor export query failed: {exc}") from exc
    finally:
        conn.close()


def _vendor_rows_to_csv_bytes(rows: list[dict[str, str]]) -> bytes:
    output = StringIO(newline="")
    fields = [*VENDOR_CSV_FIELDS]
    for extra_field in ("matched_source", "matched_query", "matched_query_label"):
        if any(extra_field in row for row in rows):
            fields.append(extra_field)
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue().encode("utf-8-sig")


def _vendor_recommendation_payload(
    q: str,
    *,
    region: str = "부산",
    limit: int = 30,
    budget_krw: int | None = None,
    include_product_policy: bool = True,
) -> dict:
    normalized_budget = _normalize_budget_krw(budget_krw)
    requested_limit = max(1, min(int(limit or 30), 100))
    evidence_pool_limit = max(requested_limit, min(max(requested_limit + 25, 30), 100))
    rows = _vendor_recommendation_rows(q, region=region, limit=evidence_pool_limit, budget_krw=normalized_budget)
    product_policy_requested = bool(include_product_policy and _vendor_should_check_product_policy(q))
    product_policy_limit = 12 if _vendor_item_disambiguation(q) else 5
    product_policy_checks = _vendor_product_policy_checks(q, limit=product_policy_limit) if product_policy_requested else []
    _vendor_log_item_policy_miss(q, product_policy_checks, requested=product_policy_requested)
    rows = _vendor_apply_item_evidence(rows, q, product_policy_checks)
    rows = _vendor_apply_construction_evidence(rows, q)
    rows = _vendor_filter_rows_for_policy_item(rows, product_policy_checks)
    total_candidate_count = len(rows)
    rows = rows[:requested_limit]
    item_policy_summary = _vendor_item_policy_summary(q, product_policy_checks, requested=product_policy_requested)
    if item_policy_summary.get("status") == "needs_item_selection":
        rows = []
        total_candidate_count = 0
    zero_result_status = _vendor_zero_result_status(
        q,
        rows,
        product_policy_checks,
        product_policy_requested=product_policy_requested,
        item_policy_summary=item_policy_summary,
    )
    purchase_route_guidance = _vendor_purchase_route_guidance(
        q,
        rows,
        product_policy_checks,
        item_policy_summary,
        budget_krw=normalized_budget,
    )
    policy_preference_summary = _vendor_policy_preference_summary(q, rows, region=region)
    policy_company_alternatives = policy_preference_summary.get("alternatives") or []
    return {
        "query": q,
        "region": region,
        "budget_krw": normalized_budget,
        "budget_label": _format_krw_short(normalized_budget),
        "limit": requested_limit,
        "count": len(rows),
        "total_candidate_count": total_candidate_count,
        "visible_candidate_count": len(rows),
        "columns": VENDOR_RECOMMENDATION_COLUMNS,
        "rows": rows,
        "search_plan": _vendor_query_plan(q),
        "purchase_route_guidance": purchase_route_guidance,
        "item_policy_summary": item_policy_summary,
        "zero_result_status": zero_result_status,
        "policy_preference_summary": policy_preference_summary,
        "policy_company_alternative_count": len(policy_company_alternatives),
        "policy_company_alternatives": policy_company_alternatives,
        "product_policy_checks": product_policy_checks,
        "mode": "vendor_recommendation_only",
        "llm_used": False,
        "limitations": [
            "계약 가능 확정이 아니라 계약 검토 후보 목록입니다.",
            "공고 전 면허·직접생산·MAS/쇼핑몰 계약상태·영업상태·인증 유효성을 원천 자료로 재확인해야 합니다.",
            "법령 해석이나 계약방법 판단은 별도 계약검토 서비스에서 처리합니다.",
        ],
    }


def _xlsx_cell_value(value, *, max_len: int = 32000) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return value
    text_value = str(value)
    return text_value if len(text_value) <= max_len else text_value[: max_len - 1] + "…"


def _vendor_recommendation_xlsx_bytes(payload: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "후보업체"
    columns = [
        ("company_name", "업체명", 28),
        ("location", "지역", 14),
        ("detail_address", "상세주소", 42),
        ("business_status_label", "영업상태", 14),
        ("matched_query_label", "후보분류", 28),
        ("condition_match_type", "조건충족유형", 18),
        ("condition_match_summary", "조건충족요약", 44),
        ("purchase_route_fit_summary", "구매수단 적합성", 36),
        ("purchase_route_fit_score", "구매수단 점수", 12),
        ("requested_item_evidence_summary", "검색어-품목 근거", 58),
        ("license_or_business_type", "면허·업종", 45),
        ("main_products", "주요품목", 36),
        ("direct_production_match", "직접생산 근거", 44),
        ("mas_match", "MAS 근거", 42),
        ("shopping_mall_match", "종합쇼핑몰 근거", 46),
        ("construction_license_match", "공사면허 근거", 34),
        ("construction_capacity_match", "시공능력 근거", 34),
        ("construction_capacity_summary", "시공능력 요약", 34),
        ("policy_company_labels", "정책기업", 22),
        ("certified_product_labels", "인증제품", 26),
        ("sme_competition_product_label", "중기간경쟁제품", 18),
        ("cooperative_purchase_route_label", "조합추천/공동사업", 22),
        ("venture_nara_status_label", "벤처나라", 18),
        ("recommended_checks", "확인 필요 항목", 56),
        ("review_score", "검토점수", 12),
        ("match_rank_score", "매칭점수", 12),
        ("source_refreshed_at", "DB기준일", 20),
    ]
    ws.append([label for _, label, _ in columns])
    for row in payload.get("rows") or []:
        ws.append([_xlsx_cell_value(row.get(key, "")) for key, _, _ in columns])

    header_fill = PatternFill("solid", fgColor="12372F")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for idx, (_, _, width) in enumerate(columns, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    policy_ws = wb.create_sheet("품목정책")
    policy_headers = [
        "세부품명번호",
        "세부품명",
        "매칭키워드",
        "정책소스",
        "중기간경쟁제품",
        "공사용자재직접구매",
        "직생 유효 공급업체",
        "MAS 활성 공급업체",
        "부산 업체 품목 수",
        "필수특이사항",
    ]
    policy_ws.append(policy_headers)
    for item in payload.get("product_policy_checks") or []:
        policy_ws.append([
            _xlsx_cell_value(item.get("detail_product_code", "")),
            _xlsx_cell_value(item.get("detail_product_name", "")),
            _xlsx_cell_value(item.get("matched_policy_keyword", "")),
            _xlsx_cell_value(item.get("matched_policy_source", "")),
            _xlsx_cell_value(item.get("is_sme_competition_product", "")),
            _xlsx_cell_value(item.get("is_construction_material_direct_purchase", "")),
            _xlsx_cell_value(item.get("direct_production_valid_supplier_count", "")),
            _xlsx_cell_value(item.get("mas_active_supplier_count", "")),
            _xlsx_cell_value(item.get("busan_company_product_count", "")),
            _xlsx_cell_value(item.get("required_special_note", "")),
        ])
    for cell in policy_ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for idx, width in enumerate([16, 28, 18, 24, 18, 20, 18, 18, 18, 44], 1):
        policy_ws.column_dimensions[get_column_letter(idx)].width = width
    for row in policy_ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    policy_ws.freeze_panes = "A2"
    policy_ws.auto_filter.ref = policy_ws.dimensions

    guide_ws = wb.create_sheet("안내")
    item_policy = payload.get("item_policy_summary") or {}
    guide_rows = [
        ("검색어", payload.get("query", "")),
        ("지역", payload.get("region", "")),
        ("예산", payload.get("budget_label", "")),
        ("후보 수", payload.get("count", "")),
        ("품목정책 상태", item_policy.get("status", "")),
        ("품목정책 메시지", item_policy.get("message", "")),
        ("중기간경쟁제품", item_policy.get("sme_competition_product", "")),
        ("직접생산 확인", item_policy.get("direct_production_certificate", "")),
        ("조합추천/공동사업", item_policy.get("cooperative_purchase_route", "")),
        ("주의", "\n".join(payload.get("limitations") or [])),
    ]
    guide_ws.append(["항목", "내용"])
    for key, value in guide_rows:
        guide_ws.append([key, _xlsx_cell_value(value)])
    for cell in guide_ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    guide_ws.column_dimensions["A"].width = 22
    guide_ws.column_dimensions["B"].width = 120
    for row in guide_ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def _vendor_zip_bytes(csv_name: str, rows: list[dict[str, str]]) -> bytes:
    payload = BytesIO()
    readme = (
        "Busan vendor candidate export\n"
        "This file is exported from the internal chatbot_company_candidate_view.\n"
        "It is a candidate list for review, not a legal eligibility confirmation.\n"
    )
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(csv_name, _vendor_rows_to_csv_bytes(rows))
        zf.writestr("README.txt", readme.encode("utf-8"))
    return payload.getvalue()


def _vendor_is_truthy(value) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    text = str(value).strip().lower()
    if any(marker in text for marker in ("근거 없음", "미확인", "확인 필요", "no evidence", "not found")):
        return False
    return text not in {"", "false", "0", "none", "unknown", "[]"}


def _vendor_split_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text or text == "[]":
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
    parts = re.split(r"[|,]", text)
    return [part.strip() for part in parts if part.strip()]


def _vendor_label_values(value, label_map: dict[str, str]) -> str:
    labels: list[str] = []
    for raw in _vendor_split_values(value):
        key, status = (raw.split(":", 1) + [""])[:2] if ":" in raw else (raw, "")
        key = key.strip()
        label = label_map.get(key, key)
        if status.strip():
            label = f"{label}({status.strip()})"
        if label and label not in labels:
            labels.append(label)
    return " | ".join(labels)


def _vendor_data_status(value, *, positive_label: str, empty_label: str = "DB 등록정보 없음") -> str:
    return positive_label if _vendor_is_truthy(value) else empty_label


def _vendor_business_status_label(row: dict[str, str]) -> str:
    status = str(row.get("business_status") or "").strip().lower()
    labels = {
        "active": "정상 영업",
        "closed": "폐업",
        "suspended": "휴업",
        "inactive": "비활성",
        "unknown": "영업상태 미확인",
        "not_checked": "영업상태 미확인",
    }
    return labels.get(status, row.get("business_status") or "영업상태 미확인")


def _vendor_business_freshness_label(row: dict[str, str]) -> str:
    freshness = str(row.get("business_status_freshness") or "").strip().lower()
    labels = {
        "fresh": "최신 검증",
        "stale": "재검증 필요",
        "not_checked": "미검증",
        "unknown": "검증상태 미확인",
    }
    return labels.get(freshness, row.get("business_status_freshness") or "검증상태 미확인")


def _vendor_is_closed_or_suspended(row: dict[str, str]) -> bool:
    status = str(row.get("business_status") or "").strip().lower()
    return status in {"closed", "suspended", "inactive", "폐업", "휴업", "종료", "cancelled", "canceled"}


def _vendor_sme_competition_row_label(row: dict[str, str]) -> str:
    if row.get("is_sme_competition_product") == "true" or _vendor_contains_any(row, ["procurement_attributes"], ("sme", "competition", "중소기업자간")):
        return "해당"
    return "DB 등록정보 없음"


def _vendor_cooperative_purchase_row_label(row: dict[str, str]) -> str:
    if _vendor_contains_any(
        row,
        ["procurement_attributes", "policy_subtypes", "candidate_types"],
        ("coop", "cooperative", "협동조합", "조합추천", "소기업공동", "small_business_collective"),
    ):
        return "조합추천/소기업 공동사업제품 경로 검토 가능성"
    return "품목검토 필요"


def _vendor_contains_any(row: dict[str, str], fields: list[str], needles: tuple[str, ...]) -> bool:
    haystack = " ".join(str(row.get(field) or "") for field in fields).lower()
    return any(needle.lower() in haystack for needle in needles)


def _vendor_direct_contract_support(row: dict[str, object], *, direct_items: list[dict[str, object]] | None = None) -> tuple[int, list[str]]:
    score = 0
    parts: list[str] = []
    if _vendor_is_truthy(row.get("policy_company_labels")) or _vendor_is_truthy(row.get("policy_subtypes")):
        score += 18
        parts.append("정책기업 수의계약 근거")
    if _vendor_is_truthy(row.get("certified_product_labels")) or _vendor_is_truthy(row.get("certified_product_types")) or _vendor_is_truthy(row.get("certified_product_summary")):
        score += 22
        parts.append("기술개발/인증제품 수의계약 근거")
    if _vendor_contains_any(
        row,
        ["procurement_attributes", "policy_subtypes", "candidate_types", "cooperative_purchase_route_label"],
        ("coop", "cooperative", "협동조합", "조합추천", "소기업공동", "small_business_collective"),
    ):
        score += 24
        parts.append("조합추천/소기업 공동사업 경로")
    if direct_items:
        score += 18
        parts.append("요청품목 직접생산 근거")
    elif _vendor_is_truthy(row.get("direct_production_summary")) or _vendor_is_truthy(row.get("direct_production_flags")):
        score += 8
        parts.append("직접생산 보유")
    return score, parts


def _vendor_contract_review_types(row: dict[str, str]) -> list[str]:
    review_types: list[str] = []
    if _vendor_is_truthy(row.get("license_or_business_type")):
        review_types.append("면허/업종 검토")
    if _vendor_is_truthy(row.get("main_products")):
        review_types.append("품목 후보")
    if _vendor_is_truthy(row.get("has_shopping_mall")):
        review_types.append("종합쇼핑몰 등록")
    if _vendor_is_truthy(row.get("has_mas")):
        review_types.append("MAS 검토")
    if _vendor_is_truthy(row.get("direct_production_summary")) or _vendor_is_truthy(row.get("direct_production_flags")):
        review_types.append("직접생산증명서 확인")
    if _vendor_is_truthy(row.get("construction_capacity_summary")):
        review_types.append("시공능력평가금액 확인")
    if _vendor_is_truthy(row.get("venture_nara_product_summary")) or _vendor_is_truthy(row.get("venture_nara_order_summary")):
        review_types.append("벤처나라 등록/거래실적")
    if _vendor_is_truthy(row.get("certified_product_types")) or _vendor_is_truthy(row.get("certified_product_summary")):
        review_types.append("인증/기술개발제품")
    if _vendor_is_truthy(row.get("policy_subtypes")):
        review_types.append("정책기업")
    if row.get("is_sme_competition_product") == "true" or _vendor_contains_any(row, ["procurement_attributes"], ("sme", "competition", "중소기업자간")):
        review_types.append("중기간경쟁제품 검토")
    return review_types


def _vendor_recommended_checks(row: dict[str, str]) -> list[str]:
    checks = ["영업상태 최신 여부"]
    if str(row.get("business_status") or "").lower() != "active":
        checks.append("국세청 영업상태 원장 재확인")
    if _vendor_is_truthy(row.get("license_or_business_type")):
        checks.append("공고 면허·업종 적합성")
    if _vendor_is_truthy(row.get("direct_production_summary")) or _vendor_is_truthy(row.get("direct_production_flags")):
        checks.append("직접생산증명서 세부품명·유효기간")
    if _vendor_is_truthy(row.get("construction_capacity_summary")):
        checks.append("시공능력평가금액 기준연도·면허명 일치 여부")
    if _vendor_is_truthy(row.get("venture_nara_product_summary")) or _vendor_is_truthy(row.get("venture_nara_order_summary")):
        checks.append("벤처나라 상품 유효기간·거래실적 원장 확인")
    if _vendor_is_truthy(row.get("has_mas")) or _vendor_is_truthy(row.get("has_shopping_mall")):
        checks.append("MAS/쇼핑몰 계약상태·납품조건")
    if _vendor_is_truthy(row.get("certified_product_types")):
        checks.append("인증제품 지정상태·적용 품명")
    if _vendor_is_truthy(row.get("policy_subtypes")):
        checks.append("정책기업 지위 유효성")
    if row.get("is_sme_competition_product") == "true":
        checks.append("중소기업자간 경쟁제품 해당 여부")
    return checks


def _vendor_review_score(row: dict[str, str]) -> int:
    score = 0
    status = str(row.get("business_status") or "").lower()
    if status in {"active", "정상", "계속사업자"}:
        score += 20
    elif _vendor_is_closed_or_suspended(row):
        score -= 100
    if "부산" in f"{row.get('location', '')} {row.get('detail_address', '')}":
        score += 20
    for review_type in _vendor_contract_review_types(row):
        if review_type in {"면허/업종 검토", "품목 후보"}:
            score += 10
        elif review_type in {"MAS 검토", "종합쇼핑몰 등록", "직접생산증명서 확인"}:
            score += 8
        else:
            score += 5
    return score


def _normalize_budget_krw(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        budget = int(str(value).replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return None
    return budget if budget > 0 else None


def _format_krw_short(value: int | None) -> str:
    if not value:
        return "미입력"
    eok = value // 100_000_000
    man = (value % 100_000_000) // 10_000
    if eok and man:
        return f"{eok}억 {man:,}만원"
    if eok:
        return f"{eok}억원"
    return f"{man:,}만원"


def _vendor_budget_review_hint(row: dict[str, str], budget_krw: int | None) -> str:
    if not budget_krw:
        return "예산 미입력: 업체 속성 중심 후보입니다."
    hints = [f"예산 {_format_krw_short(budget_krw)} 입력됨"]
    if _vendor_is_truthy(row.get("has_mas")) or _vendor_is_truthy(row.get("has_shopping_mall")):
        hints.append("MAS/종합쇼핑몰 경로 우선 검토")
    if _vendor_is_truthy(row.get("direct_production_summary")) or _vendor_is_truthy(row.get("direct_production_flags")):
        hints.append("직접생산증명서 세부품명·유효기간 확인")
    if _vendor_is_truthy(row.get("construction_capacity_summary")):
        hints.append("공사·기술용역이면 시공능력평가금액과 면허 범위 확인")
    if _vendor_is_truthy(row.get("venture_nara_product_summary")) or _vendor_is_truthy(row.get("venture_nara_order_summary")):
        hints.append("벤처나라 등록상품·거래실적은 참고자료로 확인")
    if row.get("is_sme_competition_product") == "true" or _vendor_contains_any(row, ["procurement_attributes"], ("sme", "competition", "중소기업자간")):
        hints.append("중기간경쟁제품 여부 확인")
    if _vendor_is_truthy(row.get("certified_product_types")):
        hints.append("인증제품/기술개발제품 예외 가능성 별도 검토")
    if _vendor_is_truthy(row.get("policy_subtypes")):
        hints.append("정책기업 수의계약 가능성은 금액·기관유형 기준 별도 검토")
    hints.append("계약방법 확정은 계약검토 서비스로 분리")
    return " | ".join(hints)


def _vendor_recommendation_row(row: dict[str, str], *, budget_krw: int | None = None) -> dict[str, str | int]:
    review_types = _vendor_contract_review_types(row)
    checks = _vendor_recommended_checks(row)
    rec = dict(row)
    rec["contract_review_types"] = " | ".join(review_types)
    rec["license_status_label"] = _vendor_data_status(row.get("license_or_business_type"), positive_label="보유 정보 있음")
    rec["shopping_mall_status_label"] = _vendor_data_status(row.get("has_shopping_mall"), positive_label="종합쇼핑몰 등록정보 있음")
    rec["mas_status_label"] = _vendor_data_status(row.get("has_mas"), positive_label="MAS 등록정보 있음")
    direct_summary = row.get("direct_production_summary") or row.get("direct_production_flags") or ""
    rec["direct_production_certificate_status"] = _vendor_data_status(
        direct_summary,
        positive_label="직접생산증명서 정보 있음",
    )
    rec["direct_production_certificate_products"] = direct_summary
    rec["contract_history_status_label"] = row.get("contract_history_status_label") or "과거 유사계약 이력 없음"
    rec["contract_history_match"] = row.get("contract_history_match") or ""
    rec["contract_history_summary"] = row.get("contract_history_summary") or ""
    rec["contract_history_recent_count"] = row.get("contract_history_recent_count") or ""
    rec["contract_history_total_amount"] = row.get("contract_history_total_amount") or ""
    rec["contract_history_last_date"] = row.get("contract_history_last_date") or ""
    rec["construction_capacity_status_label"] = _vendor_data_status(
        row.get("construction_capacity_summary"),
        positive_label="시공능력평가금액 정보 있음",
    )
    rec["construction_license_match"] = ""
    rec["construction_capacity_match"] = ""
    rec["construction_capacity_amount"] = ""
    rec["venture_nara_status_label"] = _vendor_data_status(
        row.get("venture_nara_product_summary") or row.get("venture_nara_order_summary"),
        positive_label="벤처나라 정보 있음",
    )
    rec["certified_product_labels"] = _vendor_label_values(row.get("certified_product_types"), _VENDOR_CERT_LABELS)
    rec["policy_company_labels"] = _vendor_label_values(row.get("policy_subtypes"), _VENDOR_POLICY_LABELS)
    rec["sme_competition_product_label"] = _vendor_sme_competition_row_label(row)
    rec["cooperative_purchase_route_label"] = _vendor_cooperative_purchase_row_label(row)
    rec["business_status_label"] = _vendor_business_status_label(row)
    rec["business_status_freshness_label"] = _vendor_business_freshness_label(row)
    rec["budget_krw"] = budget_krw or ""
    rec["budget_review_hint"] = _vendor_budget_review_hint(row, budget_krw)
    rec["recommended_checks"] = " | ".join(checks)
    rec["review_score"] = _vendor_review_score(row)
    return rec


def _vendor_parse_int(value) -> int | None:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _vendor_format_krw_full(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value:,}원"


def _vendor_construction_capacity_items(raw: object) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for part in re.split(r"\|\|\||\|", str(raw or "")):
        part = part.strip()
        if not part:
            continue
        if "^^" in part:
            fields = [field.strip() for field in part.split("^^")]
        else:
            fields = [field.strip() for field in part.split("/") if field.strip()]
        license_name = fields[0] if fields else ""
        amount = None
        source = ""
        for field in fields[1:]:
            parsed = _vendor_parse_int(field)
            if parsed is not None and amount is None:
                amount = parsed
            elif field:
                source = field
        if not license_name and amount is None:
            continue
        items.append({"license_name": license_name, "amount": amount, "source": source})
    return items


def _vendor_capacity_item_matches(item: dict[str, object], requested_terms: list[str]) -> bool:
    license_compact = _vendor_construction_compact(str(item.get("license_name") or ""))
    if not license_compact:
        return False
    for term in requested_terms:
        term_compact = _vendor_construction_compact(term)
        if term_compact and (term_compact in license_compact or license_compact in term_compact):
            return True
    return False


def _vendor_apply_construction_evidence(
    rows: list[dict[str, str | int]],
    q: str,
) -> list[dict[str, str | int]]:
    requested_terms = _vendor_requested_construction_terms(q)
    if not rows or not requested_terms:
        return rows

    construction_material_intent = _vendor_has_construction_material_intent(q)
    requested_label = ", ".join(requested_terms[:4])
    for row in rows:
        license_text = str(row.get("license_or_business_type") or "")
        capacity_text = str(row.get("construction_capacity_summary") or "")
        license_compact = _vendor_construction_compact(license_text)
        capacity_compact = _vendor_construction_compact(capacity_text)
        license_matched = [
            term
            for term in requested_terms
            if _vendor_construction_compact(term)
            and (
                _vendor_construction_compact(term) in license_compact
                or _vendor_construction_compact(term) in capacity_compact
            )
        ]
        capacity_items = [
            item
            for item in _vendor_construction_capacity_items(capacity_text)
            if _vendor_capacity_item_matches(item, requested_terms)
        ]

        if capacity_items:
            capacity_items.sort(key=lambda item: int(item.get("amount") or 0), reverse=True)
            labels = []
            for item in capacity_items[:3]:
                amount = _vendor_format_krw_full(item.get("amount") if isinstance(item.get("amount"), int) else None)
                label = " ".join(str(x) for x in (item.get("license_name"), amount) if str(x or "").strip())
                if label:
                    labels.append(label)
            top_amount = capacity_items[0].get("amount")
            row["construction_license_match"] = f"요청 면허 일치: {requested_label}"
            row["construction_capacity_match"] = "시공능력 확인: " + " / ".join(labels)
            row["construction_capacity_amount"] = int(top_amount) if isinstance(top_amount, int) else ""
            row["construction_capacity_status_label"] = "요청 공사업 시공능력평가금액 확인"
            if not construction_material_intent:
                row["condition_match_type"] = "공사면허 확인"
                row["condition_match_summary"] = "요청 공사업 면허/시공능력 근거 확인"
            row["review_score"] = int(row.get("review_score") or 0) + 45
        elif license_matched:
            row["construction_license_match"] = "요청 면허 일치: " + ", ".join(license_matched[:4])
            row["construction_capacity_match"] = "면허는 일치하나 시공능력평가금액은 후보뷰에서 확인 필요"
            row["construction_capacity_amount"] = ""
            if not construction_material_intent:
                row["condition_match_type"] = "공사면허 확인"
                row["condition_match_summary"] = "요청 공사업 면허 근거 확인, 시공능력평가금액은 추가 확인 필요"
            row["review_score"] = int(row.get("review_score") or 0) + 20
        else:
            row["construction_license_match"] = f"요청 면허 근거 없음: {requested_label}"
            row["construction_capacity_match"] = "요청 공사업 기준 시공능력평가금액 근거 없음"
            row["construction_capacity_amount"] = ""
            if not construction_material_intent:
                row["condition_match_type"] = "확인 필요"
                row["condition_match_summary"] = "요청 공사업 면허/시공능력 근거 확인 필요"
            row["review_score"] = int(row.get("review_score") or 0) - 15

    rows.sort(
        key=lambda row: (
            0 if _vendor_is_truthy(row.get("construction_capacity_amount")) else 1,
            -int(row.get("review_score") or 0),
            str(row.get("company_name") or ""),
        )
    )
    return rows


def _vendor_add_evidence_search_term(terms: list[str], value: object, *, max_len: int = 80) -> None:
    term = " ".join(str(value or "").split())
    if term and len(term) <= max_len and term not in terms:
        terms.append(term)


def _vendor_policy_code_terms(product_policy_checks: list[dict[str, str]] | None) -> list[str]:
    terms: list[str] = []
    for item in product_policy_checks or []:
        for key in (
            "detail_product_code",
            "shopping_mall_product_class_code",
            "product_class_code",
            "product_code",
        ):
            term = " ".join(str(item.get(key) or "").split())
            if not term:
                continue
            if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z\-]{3,24}", term):
                continue
            _vendor_add_evidence_search_term(terms, term, max_len=25)
    return terms


def _vendor_evidence_search_terms(q: str, product_policy_checks: list[dict[str, str]] | None = None) -> list[str]:
    terms: list[str] = []
    for term in _vendor_policy_code_terms(product_policy_checks):
        _vendor_add_evidence_search_term(terms, term, max_len=25)
    for item in _vendor_query_plan(q):
        if item.get("search_type") not in {"product", "direct_production", "shopping_mall_product", "license"}:
            continue
        _vendor_add_evidence_search_term(terms, item.get("term"))
    for item in product_policy_checks or []:
        for key in ("detail_product_name", "matched_policy_keyword"):
            _vendor_add_evidence_search_term(terms, item.get(key))
    for token in _vendor_query_tokens(q):
        _vendor_add_evidence_search_term(terms, token)
    return terms[:20]


def _vendor_is_multi_condition_query(q: str) -> bool:
    compact = _vendor_compact(q)
    markers = ("둘다", "둘 다", "모두", "동시", "와", "과", "및", "그리고", "+", "&")
    return any(_vendor_compact(marker) in compact for marker in markers)


def _vendor_evidence_item_label(item: dict[str, object]) -> str:
    name = _vendor_join(item.get("detail_product_name") or item.get("product_name"))
    code = _vendor_join(item.get("detail_product_code") or item.get("product_code"))
    status = _vendor_join(item.get("status"))
    valid_to = _vendor_join(item.get("valid_to") or item.get("contract_end_date"))
    parts = [part for part in (name, code, status, f"~{valid_to}" if valid_to else "") if part]
    return " ".join(parts)


def _vendor_evidence_source_summary(evidence: dict[str, list[dict[str, object]]]) -> str:
    parts: list[str] = []
    labels = (
        ("direct_production", "직접생산"),
        ("mas", "MAS"),
        ("shopping_mall", "종합쇼핑몰"),
    )
    for key, label in labels:
        items = evidence.get(key) or []
        if not items:
            continue
        item_labels = [_vendor_evidence_item_label(item) for item in items[:3]]
        parts.append(f"{label}: " + " / ".join(item for item in item_labels if item))
    return " | ".join(parts)


def _vendor_evidence_match_label(label: str, evidence_items: list[dict[str, object]]) -> str:
    if not evidence_items:
        return f"{label} 근거 없음"
    return f"{label} 일치: " + " / ".join(_vendor_evidence_item_label(item) for item in evidence_items[:3])


def _vendor_policy_item_identity(
    product_policy_checks: list[dict[str, str]] | None,
) -> tuple[set[str], set[str], set[str]]:
    detail_codes: set[str] = set()
    class_codes: set[str] = set()
    detail_names: set[str] = set()
    for item in product_policy_checks or []:
        for key in ("detail_product_code", "product_code"):
            code = re.sub(r"\D", "", str(item.get(key) or ""))
            if len(code) >= 9:
                detail_codes.add(code)
        for key in ("shopping_mall_product_class_code", "product_class_code"):
            code = re.sub(r"\D", "", str(item.get(key) or ""))
            if 6 <= len(code) <= 8:
                class_codes.add(code)
        name = _vendor_compact(str(item.get("detail_product_name") or ""))
        if len(name) >= 3:
            detail_names.add(name)
    return detail_codes, class_codes, detail_names


def _vendor_has_policy_item_identity(product_policy_checks: list[dict[str, str]] | None) -> bool:
    detail_codes, class_codes, detail_names = _vendor_policy_item_identity(product_policy_checks)
    return bool(detail_codes or class_codes or detail_names)


def _vendor_has_policy_item_code_identity(product_policy_checks: list[dict[str, str]] | None) -> bool:
    detail_codes, class_codes, _ = _vendor_policy_item_identity(product_policy_checks)
    return bool(detail_codes or class_codes)


def _vendor_evidence_item_matches_policy(
    item: dict[str, object],
    detail_codes: set[str],
    class_codes: set[str],
    detail_names: set[str],
) -> bool:
    item_codes = [
        re.sub(r"\D", "", str(item.get(key) or ""))
        for key in ("detail_product_code", "product_code")
    ]
    for code in item_codes:
        if code and code in detail_codes:
            return True
        if code and any(len(class_code) >= 6 and code.startswith(class_code) for class_code in class_codes):
            return True

    item_names = [
        _vendor_compact(str(item.get(key) or ""))
        for key in ("detail_product_name", "product_name")
    ]
    return any(name and name in detail_names for name in item_names)


def _vendor_filter_evidence_items_for_policy(
    product_policy_checks: list[dict[str, str]] | None,
    items: list[dict[str, object]],
) -> list[dict[str, object]]:
    detail_codes, class_codes, detail_names = _vendor_policy_item_identity(product_policy_checks)
    if not detail_codes and not class_codes and not detail_names:
        return items
    return [
        item
        for item in items
        if _vendor_evidence_item_matches_policy(item, detail_codes, class_codes, detail_names)
    ]


def _vendor_row_matches_policy_item(
    row: dict[str, str | int],
    product_policy_checks: list[dict[str, str]] | None,
) -> bool:
    detail_codes, class_codes, detail_names = _vendor_policy_item_identity(product_policy_checks)
    if not detail_codes and not class_codes and not detail_names:
        return True

    text_fields = (
        "requested_item_evidence_summary",
        "main_products",
        "matched_query",
        "matched_query_label",
        "shopping_mall_product_summary",
        "mas_product_summary",
        "direct_production_summary",
        "certified_product_summary",
        "venture_nara_product_summary",
        "venture_nara_order_summary",
        "contract_history_summary",
        "contract_history_match",
    )
    haystack = " ".join(str(row.get(field) or "") for field in text_fields)
    compact_haystack = _vendor_compact(haystack)
    numeric_haystack = re.sub(r"\D", "", haystack)

    if any(code and code in numeric_haystack for code in detail_codes):
        return True
    if any(class_code and class_code in numeric_haystack for class_code in class_codes):
        return True
    return any(name and name in compact_haystack for name in detail_names)


def _vendor_filter_rows_for_policy_item(
    rows: list[dict[str, str | int]],
    product_policy_checks: list[dict[str, str]] | None,
) -> list[dict[str, str | int]]:
    if not rows or not _vendor_has_policy_item_code_identity(product_policy_checks):
        return rows
    return [row for row in rows if _vendor_row_matches_policy_item(row, product_policy_checks)]


def _vendor_condition_terms(q: str, evidence_terms: list[str]) -> list[str]:
    compact_q = _vendor_compact(q)
    terms: list[str] = []
    noisy_markers = ("둘다", "둘 다", "모두", "동시", "같이", "함께", "와", "과", "및", "그리고", "가능", "업체", "추천", "후보", "계약")
    for term in evidence_terms:
        compact_term = _vendor_compact(term)
        if not compact_term or compact_term not in compact_q:
            continue
        if len(compact_term) < 2:
            continue
        if len(compact_term) > 12 and any(_vendor_compact(marker) in compact_term for marker in noisy_markers):
            continue
        if term not in terms:
            terms.append(term)
    compact_terms = {term: _vendor_compact(term) for term in terms}
    terms = [
        term
        for term in terms
        if not any(
            term != other
            and compact_terms[term]
            and compact_terms[term] in compact_terms[other]
            and len(compact_terms[term]) < len(compact_terms[other])
            for other in terms
        )
    ]
    if len(terms) >= 2:
        return terms[:6]
    return evidence_terms[:2] if _vendor_is_multi_condition_query(q) else evidence_terms[:1]


def _vendor_term_supported_by_row(row: dict[str, str | int], term: str) -> bool:
    compact_term = _vendor_compact(term)
    if not compact_term:
        return False
    haystack = _vendor_compact(" ".join(str(row.get(field) or "") for field in (
        "license_or_business_type",
        "main_products",
        "shopping_mall_product_summary",
        "mas_product_summary",
        "direct_production_summary",
        "construction_capacity_summary",
        "construction_license_match",
        "construction_capacity_match",
        "venture_nara_product_summary",
        "requested_item_evidence_summary",
        "matched_query",
        "matched_query_label",
        "condition_match_summary",
    )))
    if compact_term in haystack:
        return True
    construction_term = _vendor_construction_compact(term)
    construction_haystack = _vendor_construction_compact(" ".join(str(row.get(field) or "") for field in (
        "license_or_business_type",
        "construction_capacity_summary",
        "construction_license_match",
        "construction_capacity_match",
        "matched_query",
        "matched_query_label",
    )))
    return bool(construction_term and construction_term in construction_haystack)


def _vendor_policy_int(value) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0


def _vendor_policy_contract_signal(
    product_policy_checks: list[dict[str, str]] | None,
    rows: list[dict[str, str | int]] | None = None,
) -> dict[str, object]:
    third_party_count = 0
    mas_count = 0
    general_unit_price_count = 0
    registered_count = 0
    supplier_count = 0
    busan_supplier_count = 0
    contract_types: list[str] = []
    item_master_used = False

    for item in product_policy_checks or []:
        if "pps_shopping_mall_item_policy_summary" in str(item.get("matched_policy_source") or ""):
            item_master_used = True
        third_party_count = max(third_party_count, _vendor_policy_int(item.get("shopping_mall_active_third_party_count")))
        mas_count = max(mas_count, _vendor_policy_int(item.get("shopping_mall_active_mas_count")))
        general_unit_price_count = max(
            general_unit_price_count,
            _vendor_policy_int(item.get("shopping_mall_active_general_unit_price_count")),
        )
        registered_count = max(registered_count, _vendor_policy_int(item.get("shopping_mall_active_registered_count")))
        supplier_count = max(supplier_count, _vendor_policy_int(item.get("shopping_mall_active_supplier_count")))
        busan_supplier_count = max(
            busan_supplier_count,
            _vendor_policy_int(item.get("shopping_mall_active_busan_supplier_count")),
        )
        for part in _vendor_split_values(item.get("shopping_mall_active_contract_types")):
            if part and part not in contract_types:
                contract_types.append(part)

    candidate_row_evidence_count = 0
    for row in rows or []:
        if _vendor_is_truthy(row.get("mas_match")) or _vendor_is_truthy(row.get("shopping_mall_match")):
            candidate_row_evidence_count += 1

    has_confirmed_contract = any((third_party_count, mas_count, general_unit_price_count))
    if third_party_count > 0:
        basis_level = "confirmed_third_party_unit_price"
        basis_label = "제3자단가계약 품목으로 확인"
        basis_explanation = "조달청 종합쇼핑몰 품목 마스터에서 계약유형이 제3자단가계약으로 확인됩니다."
    elif mas_count > 0:
        basis_level = "confirmed_mas"
        basis_label = "다수공급자계약(MAS) 품목으로 확인"
        basis_explanation = "조달청 종합쇼핑몰 품목 마스터에서 계약유형이 다수공급자계약(MAS)으로 확인됩니다."
    elif general_unit_price_count > 0:
        basis_level = "confirmed_general_unit_price"
        basis_label = "일반단가계약 품목으로 확인"
        basis_explanation = "조달청 종합쇼핑몰 품목 마스터에서 일반단가계약 유형이 확인됩니다."
    elif registered_count > 0:
        basis_level = "shopping_mall_registered_only"
        basis_label = "종합쇼핑몰 등록 품목이나 계약유형 확인 필요"
        basis_explanation = "종합쇼핑몰 등록 품목은 확인되지만 제3자단가·MAS·일반단가 계약유형은 별도 확인이 필요합니다."
    elif candidate_row_evidence_count > 0:
        basis_level = "candidate_row_evidence_only"
        basis_label = "후보업체 쇼핑몰/MAS 근거"
        basis_explanation = "후보업체 DB에 쇼핑몰/MAS 근거가 있으나 품목 마스터의 계약유형 확정 근거는 아직 없습니다."
    else:
        basis_level = "no_central_procurement_evidence"
        basis_label = "조달청 단가계약 근거 미확인"
        basis_explanation = "현재 DB 기준 제3자단가·MAS·일반단가·종합쇼핑몰 등록 근거가 확인되지 않았습니다."

    return {
        "basis_level": basis_level,
        "basis_label": basis_label,
        "basis_explanation": basis_explanation,
        "item_master_used": item_master_used,
        "has_confirmed_contract": has_confirmed_contract,
        "has_item_master_local_supplier": busan_supplier_count > 0,
        "has_candidate_exact_local_supplier": candidate_row_evidence_count > 0,
        "third_party_count": third_party_count,
        "mas_count": mas_count,
        "general_unit_price_count": general_unit_price_count,
        "registered_count": registered_count,
        "supplier_count": supplier_count,
        "busan_supplier_count": busan_supplier_count,
        "candidate_row_evidence_count": candidate_row_evidence_count,
        "contract_types": contract_types,
        "has_local_shopping_supplier": busan_supplier_count > 0 or candidate_row_evidence_count > 0,
        "local_supplier_basis": (
            "item_master_busan_supplier"
            if busan_supplier_count > 0
            else "candidate_exact_evidence"
            if candidate_row_evidence_count > 0
            else "none"
        ),
    }


def _vendor_local_supplier_basis_text(contract_signal: dict[str, object]) -> str:
    busan_count = int(contract_signal.get("busan_supplier_count") or 0)
    exact_count = int(contract_signal.get("candidate_row_evidence_count") or 0)
    if busan_count > 0:
        return f"품목 마스터 기준 부산 쇼핑몰/MAS 공급업체 {busan_count}개가 확인됩니다."
    if exact_count > 0:
        return (
            f"업체별 세부근거에서 요청 세부품명과 일치하는 부산 MAS/쇼핑몰 공급업체 {exact_count}개가 확인됩니다. "
            "다만 품목 마스터의 부산 공급업체 집계는 0이므로 계약 전 나라장터에서 물품식별번호와 계약상태를 수동 확인해야 합니다."
        )
    return (
        "현재 DB 기준 해당 세부품명으로 조달청 쇼핑몰/MAS에 등록된 부산 공급업체가 확인되지 않습니다. "
        "조달등록·취급 후보만으로는 조달청 쇼핑몰 구매 가능 업체로 보기 어렵습니다."
    )


def _vendor_policy_route_requirements(product_policy_checks: list[dict[str, str]]) -> dict[str, bool]:
    requires_direct = False
    has_mas_route = False
    has_shopping_route = False
    has_facility_material = False
    is_sme_competition = False
    for item in product_policy_checks or []:
        sme = _vendor_item_bool(item.get("is_sme_competition_product"))
        if sme is True:
            is_sme_competition = True
            requires_direct = True
        if _vendor_policy_int(item.get("direct_production_valid_supplier_count")) > 0:
            requires_direct = True
        if _vendor_policy_int(item.get("mas_active_supplier_count")) > 0:
            has_mas_route = True
            has_shopping_route = True
        if _vendor_policy_int(item.get("shopping_mall_active_third_party_count")) > 0:
            has_mas_route = True
            has_shopping_route = True
        if _vendor_policy_int(item.get("shopping_mall_active_mas_count")) > 0:
            has_mas_route = True
            has_shopping_route = True
        if _vendor_policy_int(item.get("shopping_mall_active_general_unit_price_count")) > 0:
            has_shopping_route = True
        if _vendor_policy_int(item.get("shopping_mall_active_registered_count")) > 0:
            has_shopping_route = True
        if str(item.get("matched_policy_source") or "") == "facility_material_price_file":
            has_facility_material = True
    contract_signal = _vendor_policy_contract_signal(product_policy_checks)
    return {
        "requires_direct_production": requires_direct,
        "has_mas_route": has_mas_route,
        "has_shopping_route": has_shopping_route,
        "has_facility_material_price": has_facility_material,
        "is_sme_competition_product": is_sme_competition,
        "has_confirmed_unit_contract": bool(contract_signal["has_confirmed_contract"]),
        "has_registered_shopping_mall_item": bool(contract_signal["registered_count"]),
        "has_busan_shopping_mall_supplier": bool(contract_signal["busan_supplier_count"]),
    }


def _vendor_apply_item_evidence(
    rows: list[dict[str, str | int]],
    q: str,
    product_policy_checks: list[dict[str, str]],
) -> list[dict[str, str | int]]:
    if not rows:
        return rows
    terms = _vendor_evidence_search_terms(q, product_policy_checks)
    condition_terms = _vendor_condition_terms(q, terms)
    company_ids = [str(row.get("company_id") or "") for row in rows if row.get("company_id")]
    evidence_by_company: dict[str, dict[str, list[dict[str, object]]]] = {}
    if company_ids and terms:
        try:
            company_db = _vendor_import_company_db()
            search_company_item_evidence = getattr(company_db, "search_company_item_evidence", None)
            if callable(search_company_item_evidence):
                evidence_by_company = search_company_item_evidence(company_ids, terms, limit_per_company=5) or {}
        except Exception:
            evidence_by_company = {}

    multi_condition = _vendor_is_multi_condition_query(q) and len(condition_terms) >= 2
    compact_q = _vendor_compact(q)
    construction_terms = _vendor_requested_construction_terms(q)
    construction_material_intent = _vendor_has_construction_material_intent(q)
    wants_direct = any(term in compact_q for term in ("직접생산", "직생"))
    wants_mas = any(term in compact_q for term in ("mas", "다수공급자", "다수공급자계약"))
    wants_shopping = any(term in compact_q for term in ("종합쇼핑몰", "쇼핑몰"))
    route_requirements = _vendor_policy_route_requirements(product_policy_checks)
    strict_policy_item_identity = _vendor_has_policy_item_code_identity(product_policy_checks)
    confirmed_central_route = route_requirements["has_confirmed_unit_contract"] or route_requirements["has_registered_shopping_mall_item"]
    direct_contract_preferred = (
        not route_requirements["has_confirmed_unit_contract"]
        or not route_requirements["has_busan_shopping_mall_supplier"]
    )
    for row in rows:
        company_id = str(row.get("company_id") or "")
        evidence = evidence_by_company.get(company_id) or {"direct_production": [], "shopping_mall": [], "mas": []}
        direct_items = _vendor_filter_evidence_items_for_policy(product_policy_checks, evidence.get("direct_production") or [])
        shopping_items = _vendor_filter_evidence_items_for_policy(product_policy_checks, evidence.get("shopping_mall") or [])
        mas_items = _vendor_filter_evidence_items_for_policy(product_policy_checks, evidence.get("mas") or [])
        filtered_evidence = {
            "direct_production": direct_items,
            "shopping_mall": shopping_items,
            "mas": mas_items,
        }
        evidence_summary = _vendor_evidence_source_summary(filtered_evidence)
        row["direct_production_match"] = _vendor_evidence_match_label("직접생산", direct_items)
        row["mas_match"] = _vendor_evidence_match_label("MAS", mas_items)
        row["shopping_mall_match"] = _vendor_evidence_match_label("종합쇼핑몰", shopping_items)
        row["requested_item_evidence_summary"] = evidence_summary or "요청 품목 기준 직생/MAS/쇼핑몰 세부 근거 없음"

        route_score = 0
        if wants_direct:
            route_score += 25 if direct_items else -8
        if wants_mas:
            route_score += 30 if mas_items else -10
        if wants_shopping:
            route_score += 30 if shopping_items else -10
        if not any((wants_direct, wants_mas, wants_shopping)) and evidence_summary:
            route_score += 10

        row_has_direct_generic = _vendor_is_truthy(row.get("direct_production_summary")) or _vendor_is_truthy(row.get("direct_production_flags"))
        row_has_mas_generic = _vendor_is_truthy(row.get("has_mas")) or _vendor_is_truthy(row.get("mas_product_summary"))
        row_has_shopping_generic = _vendor_is_truthy(row.get("has_shopping_mall")) or _vendor_is_truthy(row.get("shopping_mall_product_summary"))
        if strict_policy_item_identity:
            row_has_direct_generic = False
            row_has_mas_generic = False
            row_has_shopping_generic = False
        route_fit_score = 0
        route_fit_parts: list[str] = []
        if route_requirements["requires_direct_production"]:
            if direct_items:
                route_fit_score += 35
                route_fit_parts.append("직접생산 요청품목 근거 충족")
            elif row_has_direct_generic:
                route_fit_score += 8
                route_fit_parts.append("직접생산 보유(요청품목 일치 확인 필요)")
            else:
                route_fit_score -= 30 if route_requirements["is_sme_competition_product"] else 20
                route_fit_parts.append("직접생산 근거 미확인")
        if route_requirements["has_mas_route"]:
            if mas_items:
                route_fit_score += 25
                route_fit_parts.append("MAS 요청품목 등록 근거 충족")
            elif row_has_mas_generic:
                route_fit_score += 5
                route_fit_parts.append("MAS 보유(요청품목 일치 확인 필요)")
            else:
                route_fit_score -= 8
                route_fit_parts.append("MAS 등록 근거 미확인")
        if route_requirements["has_shopping_route"]:
            if shopping_items:
                route_fit_score += 18
                route_fit_parts.append("종합쇼핑몰 요청품목 등록 근거 충족")
            elif row_has_shopping_generic:
                route_fit_score += 4
                route_fit_parts.append("종합쇼핑몰 보유(요청품목 일치 확인 필요)")
            elif not route_requirements["has_mas_route"]:
                route_fit_score -= 5
                route_fit_parts.append("종합쇼핑몰 등록 근거 미확인")
        if confirmed_central_route and strict_policy_item_identity and not (mas_items or shopping_items):
            route_fit_score -= 18
            route_fit_parts.append("조달청 쇼핑몰/MAS 요청품목 부산공급 근거 미확인")
        if route_requirements["has_facility_material_price"]:
            route_fit_parts.append("시설자재 가격정보 매칭 품목")
        if direct_contract_preferred:
            support_score, support_parts = _vendor_direct_contract_support(row, direct_items=direct_items)
            if support_score:
                route_fit_score += support_score
                route_fit_parts.append("지역업체 직접계약 지원 근거: " + ", ".join(support_parts))
            elif not route_requirements["has_confirmed_unit_contract"]:
                route_fit_score -= 4
                route_fit_parts.append("수의계약 지원 근거 미확인")
        if route_fit_score:
            route_score += route_fit_score
        row["purchase_route_fit_score"] = route_fit_score
        row["purchase_route_fit_summary"] = " | ".join(route_fit_parts)

        if direct_items:
            row["direct_production_certificate_status"] = "직접생산증명서 품목 일치"
            row["direct_production_certificate_products"] = _vendor_evidence_match_label("직접생산", direct_items)
        elif strict_policy_item_identity:
            row["direct_production_certificate_products"] = ""
        if mas_items:
            row["mas_status_label"] = "MAS 품목 일치"
            row["has_mas"] = "true"
        elif strict_policy_item_identity:
            row["mas_status_label"] = "MAS 요청품목 근거 없음"
        if shopping_items:
            row["shopping_mall_status_label"] = "종합쇼핑몰 품목 일치"
            row["has_shopping_mall"] = "true"
        elif strict_policy_item_identity:
            row["shopping_mall_status_label"] = "종합쇼핑몰 요청품목 근거 없음"

        if multi_condition:
            matched_terms = [term for term in condition_terms if _vendor_term_supported_by_row(row, term)]
            row["condition_match_summary"] = f"{len(matched_terms)}/{len(condition_terms)} 조건 근거 확인"
            if len(matched_terms) == len(condition_terms):
                row["condition_match_type"] = "모두 충족"
                row["review_score"] = int(row.get("review_score") or 0) + 30
            elif matched_terms:
                row["condition_match_type"] = "일부 충족"
            else:
                row["condition_match_type"] = "근거 부족"
                row["review_score"] = int(row.get("review_score") or 0) - 10
        else:
            if construction_terms and not construction_material_intent:
                construction_positive = _vendor_is_truthy(row.get("construction_capacity_amount")) or (
                    _vendor_is_truthy(row.get("construction_license_match"))
                    and "근거 없음" not in str(row.get("construction_license_match") or "")
                )
                if construction_positive:
                    row["condition_match_type"] = "공사면허 확인"
                    row["condition_match_summary"] = "요청 공사업 면허/시공능력 근거 확인"
                else:
                    row["condition_match_type"] = "확인 필요"
                    row["condition_match_summary"] = "요청 공사업 면허/시공능력 근거 확인 필요"
            elif evidence_summary:
                row["condition_match_type"] = "품목근거 확인"
                row["condition_match_summary"] = "요청 품목 기준 직생/MAS/쇼핑몰 근거 확인"
                row["review_score"] = int(row.get("review_score") or 0) + 10
            elif confirmed_central_route and strict_policy_item_identity:
                row["condition_match_type"] = "대안 검토"
                row["condition_match_summary"] = "조달등록 부산업체이나 요청 세부품명의 쇼핑몰/MAS 부산공급 근거는 미확인"
            else:
                row["condition_match_type"] = "후보 표시"
                row["condition_match_summary"] = "업체 후보이나 요청 품목 기준 직생/MAS/쇼핑몰 세부 근거는 별도 확인 필요"
        row["review_score"] = int(row.get("review_score") or 0) + route_score
    if multi_condition:
        rank = {"모두 충족": 0, "일부 충족": 1, "근거 부족": 2}
        rows.sort(key=lambda row: (rank.get(str(row.get("condition_match_type") or ""), 3), -int(row.get("review_score") or 0), str(row.get("company_name") or "")))
    else:
        rows.sort(key=lambda row: (-int(row.get("review_score") or 0), str(row.get("company_name") or "")))
    return rows


def _monitoring_company_api_base_url() -> str:
    return os.getenv("MONITORING_COMPANY_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


_MONITORING_API_FALLBACK_DISABLED_UNTIL = 0.0


def _monitoring_api_get(endpoint: str, params: dict[str, object], *, timeout: float = 2.0) -> dict | None:
    global _MONITORING_API_FALLBACK_DISABLED_UNTIL
    now = time.monotonic()
    if now < _MONITORING_API_FALLBACK_DISABLED_UNTIL:
        return None
    try:
        response = requests.get(f"{_monitoring_company_api_base_url()}{endpoint}", params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        _MONITORING_API_FALLBACK_DISABLED_UNTIL = 0.0
        return data if isinstance(data, dict) else {"items": data}
    except Exception:
        cooldown = float(os.getenv("MONITORING_COMPANY_API_FALLBACK_COOLDOWN_SEC", "60"))
        if cooldown > 0:
            _MONITORING_API_FALLBACK_DISABLED_UNTIL = now + cooldown
        return None


def _vendor_item_bool(value) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "해당", "대상"}:
        return True
    if text in {"false", "0", "no", "n", "미해당", "비대상"}:
        return False
    return None


def _vendor_item_policy_summary(q: str, product_policy_checks: list[dict[str, str]], *, requested: bool) -> dict[str, object]:
    if not requested:
        return {
            "status": "not_requested",
            "query": q,
            "message": "제품정책 검토를 실행하지 않았습니다.",
            "sme_competition_product": "확인 필요",
            "direct_production_certificate": "확인 필요",
            "cooperative_purchase_route": "확인 필요",
            "matched_products": [],
        }
    if not product_policy_checks:
        return {
            "status": "not_found_or_unavailable",
            "query": q,
            "message": "제품정책 DB/API에서 품목 매칭을 확인하지 못했습니다.",
            "sme_competition_product": "확인 필요",
            "direct_production_certificate": "확인 필요",
            "cooperative_purchase_route": "확인 필요",
            "matched_products": [],
        }

    matched_products: list[dict[str, str]] = []
    sme_values: list[bool] = []
    direct_supplier_counts: list[int] = []
    contract_signal = _vendor_policy_contract_signal(product_policy_checks)
    for item in product_policy_checks:
        sme_flag = _vendor_item_bool(item.get("is_sme_competition_product"))
        if sme_flag is not None:
            sme_values.append(sme_flag)
        try:
            direct_supplier_counts.append(int(str(item.get("direct_production_valid_supplier_count") or "0").replace(",", "")))
        except ValueError:
            pass
        matched_products.append({
            "detail_product_code": _vendor_join(item.get("detail_product_code")),
            "detail_product_name": _vendor_join(item.get("detail_product_name")),
            "matched_policy_source": _vendor_join(item.get("matched_policy_source")),
            "sme_competition_product": "해당" if sme_flag is True else "미해당" if sme_flag is False else "확인 필요",
            "direct_production_valid_supplier_count": _vendor_join(item.get("direct_production_valid_supplier_count")),
            "mas_active_supplier_count": _vendor_join(item.get("mas_active_supplier_count")),
            "busan_company_product_count": _vendor_join(item.get("busan_company_product_count")),
            "shopping_mall_active_registered_count": _vendor_join(item.get("shopping_mall_active_registered_count")),
            "shopping_mall_active_third_party_count": _vendor_join(item.get("shopping_mall_active_third_party_count")),
            "shopping_mall_active_mas_count": _vendor_join(item.get("shopping_mall_active_mas_count")),
            "shopping_mall_active_general_unit_price_count": _vendor_join(item.get("shopping_mall_active_general_unit_price_count")),
            "shopping_mall_active_supplier_count": _vendor_join(item.get("shopping_mall_active_supplier_count")),
            "shopping_mall_active_busan_supplier_count": _vendor_join(item.get("shopping_mall_active_busan_supplier_count")),
            "shopping_mall_active_contract_types": _vendor_join(item.get("shopping_mall_active_contract_types")),
            "required_special_note": _vendor_join(item.get("required_special_note")),
            "facility_material_active_price_count": _vendor_join(item.get("facility_material_active_price_count")),
            "facility_material_latest_posted_date": _vendor_join(item.get("facility_material_latest_posted_date")),
            "facility_material_price_range": _vendor_join(item.get("facility_material_price_range")),
        })

    is_sme = any(sme_values)
    if is_sme:
        sme_status = "해당"
    elif sme_values and all(value is False for value in sme_values):
        sme_status = "미해당"
    else:
        sme_status = "확인 필요"
    direct_count = max(direct_supplier_counts) if direct_supplier_counts else 0
    disambiguation = _vendor_item_disambiguation(q)
    if disambiguation:
        raw_selection_markers = (
            tuple(disambiguation.get("option_markers") or ())
            or (
                tuple(disambiguation.get("generic_markers") or ())
                + tuple(disambiguation.get("specific_markers") or ())
            )
        )
        selection_markers = tuple(
            _vendor_compact(marker)
            for marker in raw_selection_markers
            if marker
        )
        exclude_markers = tuple(
            _vendor_compact(marker)
            for marker in tuple(disambiguation.get("exclude_option_markers") or ())
            if marker
        )
        exact_option_names = tuple(
            _vendor_compact(name)
            for name in tuple(disambiguation.get("option_exact_names") or ())
            if name
        )
        selection_options: list[dict[str, str]] = []
        seen_selection_names: set[str] = set()
        for item in matched_products:
            detail_name = item.get("detail_product_name")
            compact_name = _vendor_compact(detail_name)
            if not detail_name:
                continue
            if exact_option_names:
                if compact_name not in exact_option_names:
                    continue
            elif selection_markers and not any(marker in compact_name for marker in selection_markers):
                continue
            if any(marker in compact_name for marker in exclude_markers):
                continue
            if compact_name in seen_selection_names:
                continue
            seen_selection_names.add(compact_name)
            selection_options.append({
                "detail_product_code": item["detail_product_code"],
                "detail_product_name": item["detail_product_name"],
                "selection_query": item["detail_product_name"],
                "matched_policy_source": item["matched_policy_source"],
            })
        db_disambiguation = _vendor_db_item_disambiguation(q)
        for option in list((db_disambiguation or {}).get("selection_options") or []):
            if not isinstance(option, dict):
                continue
            detail_name = _vendor_join(option.get("detail_product_name") or option.get("selection_query"))
            compact_name = _vendor_compact(detail_name)
            if not detail_name:
                continue
            if exact_option_names:
                if compact_name not in exact_option_names:
                    continue
            elif selection_markers and not any(marker in compact_name for marker in selection_markers):
                continue
            if any(marker in compact_name for marker in exclude_markers):
                continue
            if compact_name in seen_selection_names:
                continue
            seen_selection_names.add(compact_name)
            selection_options.append({
                "detail_product_code": _vendor_join(option.get("detail_product_code")),
                "detail_product_name": detail_name,
                "selection_query": _vendor_join(option.get("selection_query")) or detail_name,
                "matched_policy_source": _vendor_join(option.get("matched_policy_source")),
                "busan_company_product_count": _vendor_join(option.get("busan_company_product_count")),
                "shopping_mall_active_registered_count": _vendor_join(option.get("active_registered_count") or option.get("shopping_mall_active_registered_count")),
                "shopping_mall_active_third_party_count": _vendor_join(option.get("active_third_party_count") or option.get("shopping_mall_active_third_party_count")),
                "shopping_mall_active_mas_count": _vendor_join(option.get("active_mas_count") or option.get("shopping_mall_active_mas_count")),
                "shopping_mall_active_supplier_count": _vendor_join(option.get("active_supplier_count") or option.get("shopping_mall_active_supplier_count")),
                "shopping_mall_active_busan_supplier_count": _vendor_join(option.get("active_busan_supplier_count") or option.get("shopping_mall_active_busan_supplier_count")),
                "shopping_mall_active_contract_types": _vendor_join(option.get("active_contract_types") or option.get("shopping_mall_active_contract_types")),
            })
        return {
            "status": "needs_item_selection",
            "query": q,
            "message": str(disambiguation["message"]),
            "selection_title": str(disambiguation["title"]),
            "selection_required": True,
            "selection_options": selection_options,
            "sme_competition_product": "세부품명 선택 후 판정",
            "direct_production_certificate": "세부품명 선택 후 판정",
            "cooperative_purchase_route": "세부품명 선택 후 판정",
            "shopping_mall_contract_basis_level": "item_selection_required",
            "shopping_mall_contract_basis_label": "세부품명 선택 필요",
            "shopping_mall_contract_basis_explanation": str(disambiguation["message"]),
            "shopping_mall_busan_supplier_count": 0,
            "shopping_mall_active_registered_count": 0,
            "matched_products": matched_products,
        }
    db_disambiguation = _vendor_db_item_disambiguation(q)
    if db_disambiguation:
        selection_options: list[dict[str, str]] = []
        seen_selection_names: set[str] = set()
        for option in list(db_disambiguation.get("selection_options") or []):
            if not isinstance(option, dict):
                continue
            detail_name = _vendor_join(option.get("detail_product_name") or option.get("selection_query"))
            if not detail_name:
                continue
            compact_name = _vendor_compact(detail_name)
            if compact_name in seen_selection_names:
                continue
            seen_selection_names.add(compact_name)
            selection_options.append({
                "detail_product_code": _vendor_join(option.get("detail_product_code")),
                "detail_product_name": detail_name,
                "selection_query": _vendor_join(option.get("selection_query")) or detail_name,
                "matched_policy_source": _vendor_join(option.get("matched_policy_source")) or _vendor_join(db_disambiguation.get("source")),
                "busan_company_product_count": _vendor_join(option.get("busan_company_product_count")),
                "shopping_mall_active_registered_count": _vendor_join(option.get("active_registered_count") or option.get("shopping_mall_active_registered_count")),
                "shopping_mall_active_third_party_count": _vendor_join(option.get("active_third_party_count") or option.get("shopping_mall_active_third_party_count")),
                "shopping_mall_active_mas_count": _vendor_join(option.get("active_mas_count") or option.get("shopping_mall_active_mas_count")),
                "shopping_mall_active_supplier_count": _vendor_join(option.get("active_supplier_count") or option.get("shopping_mall_active_supplier_count")),
                "shopping_mall_active_busan_supplier_count": _vendor_join(option.get("active_busan_supplier_count") or option.get("shopping_mall_active_busan_supplier_count")),
                "shopping_mall_active_contract_types": _vendor_join(option.get("active_contract_types") or option.get("shopping_mall_active_contract_types")),
            })
        if len(selection_options) >= 2:
            return {
                "status": "needs_item_selection",
                "query": q,
                "message": str(db_disambiguation["message"]),
                "selection_title": str(db_disambiguation["title"]),
                "selection_required": True,
                "selection_options": selection_options,
                "sme_competition_product": "세부품명 선택 후 판정",
                "direct_production_certificate": "세부품명 선택 후 판정",
                "cooperative_purchase_route": "세부품명 선택 후 판정",
                "shopping_mall_contract_basis_level": "item_selection_required",
                "shopping_mall_contract_basis_label": "세부품명 선택 필요",
                "shopping_mall_contract_basis_explanation": str(db_disambiguation["message"]),
                "shopping_mall_busan_supplier_count": 0,
                "shopping_mall_active_registered_count": 0,
                "matched_products": matched_products,
            }
    if sme_status == "해당":
        direct_label = "직접생산증명서 세부품명·유효기간 확인 필요"
        cooperative_label = "조합추천/소기업 공동사업제품 수의계약 경로 검토 가능"
        message = "검색 품목이 중소기업자간 경쟁제품으로 매칭되었습니다. 직접생산증명서와 예외 구매경로를 별도 확인해야 합니다."
    elif sme_status == "미해당":
        direct_label = "DB 기준 직접생산 의무 미확인"
        cooperative_label = "중소기업자간 경쟁제품 DB 기준 미해당"
        message = "검색 품목은 중소기업자간 경쟁제품에 미해당입니다(DB 기준). 공고 전 세부품명번호 기준 최종 재확인은 필요합니다."
    else:
        direct_label = "품목 매칭상 직접생산증명서 의무 여부 확인 필요"
        cooperative_label = "중소기업자간 경쟁제품 해당 여부 확인 필요"
        message = "검색 품목은 DB 매칭값만으로 중소기업자간 경쟁제품 해당 여부를 확정하지 못했습니다. 세부품명번호 기준 재확인이 필요합니다."
    if direct_count:
        direct_label = f"{direct_label} / 유효 공급업체 수: {direct_count}"
    if any(str(item.get("matched_policy_source") or "") == "facility_material_price_file" for item in product_policy_checks):
        message = f"{message} 시설공통자재 가격정보 파일에 등록된 품목이 포함되어 있으므로, 현행 가격게시 여부와 계약수단을 함께 확인해야 합니다."

    return {
        "status": "matched",
        "query": q,
        "message": message,
        "sme_competition_product": sme_status,
        "direct_production_certificate": direct_label,
        "cooperative_purchase_route": cooperative_label,
        "shopping_mall_contract_basis_level": contract_signal["basis_level"],
        "shopping_mall_contract_basis_label": contract_signal["basis_label"],
        "shopping_mall_contract_basis_explanation": contract_signal["basis_explanation"],
        "shopping_mall_busan_supplier_count": contract_signal["busan_supplier_count"],
        "shopping_mall_active_registered_count": contract_signal["registered_count"],
        "matched_products": matched_products,
    }


def _vendor_zero_result_status(
    q: str,
    rows: list[dict[str, str | int]],
    product_policy_checks: list[dict[str, str]],
    *,
    product_policy_requested: bool,
    item_policy_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    if rows:
        return {
            "status": "has_candidates",
            "label": "후보 있음",
            "message": "부산업체 후보가 조회되었습니다.",
            "next_actions": [],
        }
    if item_policy_summary and item_policy_summary.get("status") == "needs_item_selection":
        return {
            "status": "item_selection_required",
            "label": "세부품명 선택 필요",
            "message": str(
                item_policy_summary.get("message")
                or "세부품명을 선택한 뒤 품목정책과 구매방식을 다시 판정해야 합니다."
            ),
            "next_actions": [
                "실제 구매하려는 세부품명 선택",
                "세부품명번호 10자리 확인",
                "세부품명 확정 후 업체 후보 재조회",
            ],
        }
    construction_terms = _vendor_requested_construction_terms(q)
    service_terms = _vendor_requested_service_terms(q)
    if product_policy_checks:
        contract_signal = _vendor_policy_contract_signal(product_policy_checks)
        if int(contract_signal.get("busan_supplier_count") or 0) == 0 and int(contract_signal.get("registered_count") or 0) > 0:
            return {
                "status": "item_identified_no_busan_supplier",
                "label": "품목 확인됨 / 부산 공급업체 미확인",
                "message": "품목정책 또는 조달청 쇼핑몰 품목은 확인됐지만 현재 DB 기준 부산 공급업체 후보가 없습니다.",
                "next_actions": ["세부품명번호 확인", "나라장터 종합쇼핑몰 부산 공급업체 수동 확인", "조달청 입찰 또는 지역업체 대안 검토"],
            }
        return {
            "status": "item_identified_no_vendor_match",
            "label": "품목 확인됨 / 후보업체 매칭 없음",
            "message": "원천 품목은 확인됐지만 부산업체 후보뷰와 연결된 업체가 없습니다.",
            "next_actions": ["품목-업체 연결 테이블 보강", "직접생산/MAS/쇼핑몰 공급업체 원천 재확인", "수동 후보 검토"],
        }
    if construction_terms:
        return {
            "status": "construction_license_no_candidate",
            "label": "공사 면허 인식 / 후보 없음",
            "message": "공사 질의로 분류됐지만 해당 면허 또는 시공능력 기준 후보가 없습니다.",
            "next_actions": ["면허명 동의어 확인", "부산 본사 면허 DB 재검증", "시공능력평가 자료 보강"],
        }
    if service_terms:
        return {
            "status": "service_term_no_candidate",
            "label": "용역 업종 인식 / 후보 없음",
            "message": "용역 질의로 분류됐지만 현재 용역 업종/실적 사전 기준 후보가 없습니다.",
            "next_actions": ["용역 업종 사전 보강", "입찰공고/계약명 기반 용역 사전 보강", "수행실적 원천자료 확인"],
        }
    if product_policy_requested:
        return {
            "status": "item_policy_not_found",
            "label": "품목정책 미분류",
            "message": "제품정책 DB/API에서 품목을 확인하지 못했고 후보업체도 조회되지 않았습니다.",
            "next_actions": ["검색어 동의어 확인", "세부품명번호 수동 확인", "원천 DB 보강 대상 등록"],
        }
    return {
        "status": "unclassified_no_candidate",
        "label": "검색어 미분류 / 후보 없음",
        "message": "검색어가 품목·공사·용역 사전과 후보업체 DB에 충분히 매칭되지 않았습니다.",
        "next_actions": ["검색어를 품목명 또는 면허명으로 구체화", "사전 보강 대상 검토"],
    }


def _vendor_has_shopping_mall_item_master_evidence(product_policy_checks: list[dict[str, str]]) -> bool:
    for item in product_policy_checks or []:
        if any(
            _vendor_policy_int(item.get(field)) > 0
            for field in (
                "shopping_mall_active_registered_count",
                "shopping_mall_active_third_party_count",
                "shopping_mall_active_mas_count",
                "shopping_mall_active_general_unit_price_count",
                "shopping_mall_active_supplier_count",
                "shopping_mall_active_busan_supplier_count",
            )
        ):
            return True
    return False


def _vendor_log_item_policy_miss(q: str, product_policy_checks: list[dict[str, str]], *, requested: bool) -> None:
    if not requested:
        return
    if not product_policy_checks:
        return
    if _vendor_has_shopping_mall_item_master_evidence(product_policy_checks):
        return
    if os.getenv("VENDOR_ITEM_POLICY_MISS_QUEUE_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        return
    try:
        canonical_name, normalized_terms = _vendor_normalized_item_terms(q)
        queue_path = Path(os.getenv(
            "VENDOR_ITEM_POLICY_MISS_QUEUE_PATH",
            os.path.join(APP_DIR, "data", "vendor_item_policy_miss_queue.jsonl"),
        ))
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "logged_at": datetime.now().isoformat(),
            "query": q,
            "normalized_canonical_name": canonical_name,
            "normalized_terms": normalized_terms,
            "reason": "shopping_mall_item_master_not_matched",
            "matched_policy_products": [
                {
                    "detail_product_code": _vendor_join(item.get("detail_product_code")),
                    "detail_product_name": _vendor_join(item.get("detail_product_name")),
                    "matched_policy_source": _vendor_join(item.get("matched_policy_source")),
                    "matched_policy_keyword": _vendor_join(item.get("matched_policy_keyword")),
                }
                for item in product_policy_checks[:10]
            ],
            "review_status": "pending",
        }
        with queue_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


_VENDOR_POLICY_PREFERENCE_RULES = [
    ("disabled_company", "장애인기업", ("장애인기업", "장애인 표준사업장", "장애인표준사업장", "중증장애인생산품", "disabled")),
    ("women_company", "여성기업", ("여성기업", "여성 업체", "women")),
    ("social_enterprise", "사회적기업", ("사회적기업", "사회적 기업", "social")),
    ("social_cooperative", "사회적협동조합", ("사회적협동조합", "사회적 협동조합", "social_cooperative")),
    ("self_support_company", "자활기업", ("자활기업", "자활 업체", "self_support")),
    ("village_company", "마을기업", ("마을기업", "마을 업체", "village_company")),
    ("small_business", "소상공인", ("소상공인", "소상공 업체", "소기업", "small_business")),
    ("startup", "창업기업", ("창업기업", "창업 업체", "스타트업", "startup")),
    ("youth_startup", "청년창업기업", ("청년창업기업", "청년 창업기업", "청년 창업", "youth_startup")),
    ("venture_company", "벤처기업", ("벤처기업", "벤처 업체", "venture")),
]

_VENDOR_POLICY_COMPANY_CACHE: list[dict[str, object]] | None = None


def _vendor_requested_policy_preferences(q: str) -> list[dict[str, str]]:
    requested: list[dict[str, str]] = []
    compact = _vendor_compact(q)
    for key, label, triggers in _VENDOR_POLICY_PREFERENCE_RULES:
        if any(_vendor_compact(trigger) in compact for trigger in triggers[:3]):
            requested.append({"key": key, "label": label})
    return requested


def _vendor_policy_company_entries() -> list[dict[str, object]]:
    global _VENDOR_POLICY_COMPANY_CACHE
    if _VENDOR_POLICY_COMPANY_CACHE is not None:
        return _VENDOR_POLICY_COMPANY_CACHE

    path = Path(APP_DIR) / "policy_companies.json"
    entries: list[dict[str, object]] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _VENDOR_POLICY_COMPANY_CACHE = []
        return _VENDOR_POLICY_COMPANY_CACHE

    if isinstance(raw, dict):
        iterator = raw.values()
    elif isinstance(raw, list):
        iterator = raw
    else:
        iterator = []
    for item in iterator:
        if not isinstance(item, dict):
            continue
        tags = [str(tag) for tag in item.get("tags") or [] if str(tag).strip()]
        entries.append({
            "company_name": _vendor_join(item.get("name")),
            "location": _vendor_join(item.get("location")),
            "business_type": _vendor_join(item.get("biz_type")),
            "industry": _vendor_join(item.get("industry")),
            "representative_product": _vendor_join(item.get("product")),
            "manufacturer": _vendor_join(item.get("manufacturer")),
            "registered_at": _vendor_join(item.get("registered")),
            "policy_labels": tags,
            "source": "policy_companies_json",
        })
    _VENDOR_POLICY_COMPANY_CACHE = entries
    return _VENDOR_POLICY_COMPANY_CACHE


def _vendor_policy_company_search_terms(q: str) -> list[str]:
    terms: list[str] = []
    requested_labels = {item["label"] for item in _vendor_requested_policy_preferences(q)}
    for item in _vendor_query_plan(q):
        if item.get("search_type") not in {"product", "license"}:
            continue
        term = " ".join(str(item.get("term") or "").split())
        if not term or term in requested_labels:
            continue
        if term not in terms:
            terms.append(term)
    for token in _vendor_query_tokens(q):
        token = " ".join(str(token or "").split())
        if token and token not in requested_labels and token not in terms:
            terms.append(token)
    return terms[:12]


def _vendor_policy_company_alternatives(
    q: str,
    requested: list[dict[str, str]],
    *,
    region: str = "부산",
    limit: int = 10,
) -> list[dict[str, object]]:
    if not requested:
        return []

    requested_labels = {item["label"] for item in requested}
    terms = _vendor_policy_company_search_terms(q)
    region_text = "부산" if str(region).lower() == "busan" else str(region or "")
    scored: list[tuple[int, dict[str, object]]] = []
    seen: set[tuple[str, str]] = set()
    for entry in _vendor_policy_company_entries():
        labels = {str(label) for label in entry.get("policy_labels") or []}
        if not labels.intersection(requested_labels):
            continue
        location = str(entry.get("location") or "")
        if region_text and region_text not in location:
            continue
        haystack = " ".join(str(entry.get(field) or "") for field in (
            "company_name",
            "location",
            "business_type",
            "industry",
            "representative_product",
        ))
        compact_haystack = _vendor_compact(haystack)
        matched_terms: list[str] = []
        score = 0
        for term in terms:
            compact_term = _vendor_compact(term)
            if not compact_term or compact_term not in compact_haystack:
                continue
            matched_terms.append(term)
            if compact_term in _vendor_compact(str(entry.get("representative_product") or "")):
                score += 5
            elif compact_term in _vendor_compact(str(entry.get("industry") or "")):
                score += 4
            else:
                score += 2
        if terms and not matched_terms:
            continue
        name = str(entry.get("company_name") or "")
        key = (name, location)
        if not name or key in seen:
            continue
        seen.add(key)
        scored.append((score, {**entry, "matched_terms": matched_terms}))

    scored.sort(key=lambda item: (-item[0], str(item[1].get("company_name") or "")))
    return [entry for _, entry in scored[:max(1, min(int(limit or 10), 30))]]


def _vendor_policy_preference_summary(q: str, rows: list[dict[str, str | int]], *, region: str = "부산") -> dict[str, object]:
    requested = _vendor_requested_policy_preferences(q)
    if not requested:
        return {
            "status": "not_requested",
            "requested": [],
            "matched_count": 0,
            "alternative_count": 0,
            "alternatives": [],
            "message": "",
        }

    matched_rows: list[dict[str, str]] = []
    for row in rows:
        haystack = " ".join(str(row.get(field) or "") for field in (
            "policy_company_labels",
            "policy_subtypes",
            "candidate_types",
            "procurement_attributes",
        )).lower()
        for item in requested:
            rule = next((rule for rule in _VENDOR_POLICY_PREFERENCE_RULES if rule[0] == item["key"]), None)
            if rule and any(str(token).lower() in haystack for token in rule[2]):
                matched_rows.append({
                    "company_name": str(row.get("company_name") or ""),
                    "matched_policy": item["label"],
                })
                break

    requested_labels = ", ".join(item["label"] for item in requested)
    if matched_rows:
        message = f"{requested_labels} 조건과 일치하는 후보가 {len(matched_rows)}건 확인됩니다. 해당 지위의 유효기간과 증빙은 공고 전 재확인해야 합니다."
        status = "matched"
        alternatives: list[dict[str, object]] = []
    else:
        alternatives = _vendor_policy_company_alternatives(q, requested, region=region, limit=10)
        if alternatives:
            message = f"{requested_labels} 조건은 일반 후보 목록에서는 확인되지 않았지만, 정책기업 보조 DB에서 {len(alternatives)}건의 별도 확인 후보가 검색되었습니다."
        else:
            message = f"{requested_labels} 조건을 포함한 질문입니다. 현재 후보 목록과 정책기업 보조 DB에서 해당 조건 후보를 확인하지 못했습니다."
        status = "not_found_in_candidates"
    return {
        "status": status,
        "requested": requested,
        "matched_count": len(matched_rows),
        "matched_companies": matched_rows[:10],
        "alternative_count": len(alternatives),
        "alternatives": alternatives[:10],
        "message": message,
    }


def _vendor_should_check_facility_material_policy(q: str) -> bool:
    compact = _vendor_compact(q)
    return any(
        marker in compact
        for marker in (
            "시설공통자재",
            "시설자재",
            "공사용자재",
            "공사자재",
            "관급자재",
            "건설자재",
            "토목자재",
            "건축자재",
            "기계설비자재",
            "전기자재",
            "정보통신자재",
            "시장시공가격",
            "표준시장단가",
            "가격정보",
        )
    )


def _vendor_product_policy_checks(q: str, *, limit: int = 5) -> list[dict[str, str]]:
    timeout = float(os.getenv("VENDOR_PRODUCT_POLICY_TIMEOUT_SEC", "0.8"))
    checks: list[dict[str, str]] = []
    seen_codes: set[str] = set()

    def merge_check(payload: dict[str, str]) -> None:
        code = _vendor_join(payload.get("detail_product_code"))
        name = _vendor_join(payload.get("detail_product_name"))
        key = code or name
        target: dict[str, str] | None = None
        if key:
            for existing in checks:
                existing_key = _vendor_join(existing.get("detail_product_code")) or _vendor_join(existing.get("detail_product_name"))
                if existing_key == key:
                    target = existing
                    break
        if target is None:
            if key:
                seen_codes.add(key)
            checks.append(payload)
            return
        for field, value in payload.items():
            value_text = _vendor_join(value)
            if not value_text:
                continue
            if field.endswith("_count") and _vendor_policy_int(value_text) > _vendor_policy_int(target.get(field)):
                target[field] = value_text
                continue
            if not _vendor_join(target.get(field)):
                target[field] = value_text
        source = _vendor_join(payload.get("matched_policy_source"))
        current_source = _vendor_join(target.get("matched_policy_source"))
        if source and current_source and source not in current_source.split("+"):
            target["matched_policy_source"] = f"{current_source}+{source}"
        elif source and not current_source:
            target["matched_policy_source"] = source

    disambiguation = _vendor_item_disambiguation(q)
    terms: list[str] = []
    if disambiguation:
        terms = [str(term) for term in disambiguation.get("search_terms", ()) if str(term).strip()]
    else:
        for item in _vendor_query_plan(q):
            if item.get("search_type") == "product":
                term = " ".join(str(item.get("term") or "").split())
                if term and term not in terms:
                    terms.append(term)
    if not terms:
        terms = [q]
    compact_q = _vendor_compact(q)
    if any(token in compact_q for token in ("pc", "피씨", "컴퓨터", "데스크톱", "데스크탑", "노트북", "태블릿", "일체형")):
        use_preferred_terms_only = False
        if "컴퓨터책상" in compact_q:
            preferred_terms = ["컴퓨터책상"]
            use_preferred_terms_only = True
        elif any(token in compact_q for token in ("컴퓨터서버", "서버")):
            preferred_terms = ["컴퓨터서버"]
            use_preferred_terms_only = True
        elif "태블릿" in compact_q:
            preferred_terms = ["태블릿컴퓨터", "태블릿"]
            use_preferred_terms_only = True
        elif "일체형" in compact_q:
            preferred_terms = ["일체형컴퓨터", "일체형"]
            use_preferred_terms_only = True
        elif any(token in compact_q for token in ("노트북", "랩톱", "랩탑")):
            preferred_terms = ["노트북컴퓨터", "노트북", "휴대용 컴퓨터"]
            use_preferred_terms_only = True
        elif any(token in compact_q for token in ("데스크톱", "데스크탑", "pc", "피씨")):
            preferred_terms = ["데스크톱컴퓨터", "데스크톱"]
            use_preferred_terms_only = True
        else:
            preferred_terms = ["데스크톱컴퓨터", "노트북컴퓨터", "컴퓨터", "데스크톱"]
        ambiguous_terms = {"pc", "피씨"}
        reordered: list[str] = []
        source_terms = preferred_terms if use_preferred_terms_only else [*preferred_terms, *terms]
        for term in source_terms:
            if _vendor_compact(term) in ambiguous_terms:
                continue
            if term and term not in reordered:
                reordered.append(term)
        terms = reordered or terms
    max_checks = max(1, min(int(limit or 5), 20))
    facility_policy_requested = _vendor_should_check_facility_material_policy(q)
    for term_index, term in enumerate(terms[:8]):
        if facility_policy_requested:
            try:
                company_db = _vendor_import_company_db()
                search_facility_material_policy = getattr(company_db, "search_facility_material_policy", None)
                if callable(search_facility_material_policy):
                    facility_data = search_facility_material_policy(term, limit=min(2, max_checks))
                    facility_items = (facility_data or {}).get("candidates") or []
                    for item in facility_items:
                        if not isinstance(item, dict):
                            continue
                        code = _vendor_join(item.get("detail_product_code"))
                        name = _vendor_join(item.get("detail_product_name"))
                        product_identifier_no = _vendor_join(item.get("product_identifier_no"))
                        min_price = _vendor_join(item.get("facility_material_min_price_amount"))
                        max_price = _vendor_join(item.get("facility_material_max_price_amount"))
                        if min_price and max_price and min_price != max_price:
                            price_range = f"{min_price}~{max_price}"
                        else:
                            price_range = min_price or max_price
                        merge_check({
                            "detail_product_code": code,
                            "detail_product_name": name,
                            "matched_policy_keyword": term,
                            "matched_policy_source": "facility_material_price_file",
                            "is_sme_competition_product": "",
                            "is_construction_material_direct_purchase": "",
                            "direct_production_valid_supplier_count": "",
                            "mas_active_supplier_count": "",
                            "busan_company_product_count": "",
                            "required_special_note": _vendor_join(item.get("required_special_note")),
                            "facility_material_active_price_count": _vendor_join(item.get("facility_material_active_price_count")),
                            "facility_material_latest_posted_date": _vendor_join(item.get("facility_material_latest_posted_date")),
                            "facility_material_price_range": price_range,
                        })
                        if len(checks) >= max_checks:
                            break
            except Exception:
                pass
        try:
            company_db = _vendor_import_company_db()
            search_shopping_mall_item_policy = getattr(company_db, "search_shopping_mall_item_policy", None)
            if callable(search_shopping_mall_item_policy):
                mall_policy_data = search_shopping_mall_item_policy(term, limit=max_checks)
                mall_policy_items = (mall_policy_data or {}).get("candidates") or []
                for item in mall_policy_items:
                    if not isinstance(item, dict):
                        continue
                    code = _vendor_join(item.get("detail_product_code"))
                    name = _vendor_join(item.get("detail_product_name"))
                    merge_check({
                        "detail_product_code": code,
                        "detail_product_name": name,
                        "matched_policy_keyword": term,
                        "matched_policy_source": "pps_shopping_mall_item_policy_summary",
                        "shopping_mall_product_class_code": _vendor_join(item.get("product_class_code")),
                        "shopping_mall_product_class_name": _vendor_join(item.get("product_class_name")),
                        "shopping_mall_active_registered_count": _vendor_join(item.get("active_registered_count")),
                        "shopping_mall_active_third_party_count": _vendor_join(item.get("active_third_party_count")),
                        "shopping_mall_active_mas_count": _vendor_join(item.get("active_mas_count")),
                        "shopping_mall_active_general_unit_price_count": _vendor_join(item.get("active_general_unit_price_count")),
                        "shopping_mall_active_excellent_procurement_count": _vendor_join(item.get("active_excellent_procurement_count")),
                        "shopping_mall_active_sme_competition_count": _vendor_join(item.get("active_sme_competition_count")),
                        "shopping_mall_active_supplier_count": _vendor_join(item.get("active_supplier_count")),
                        "shopping_mall_active_busan_supplier_count": _vendor_join(item.get("active_busan_supplier_count")),
                        "shopping_mall_active_price_range": _vendor_join(
                            "~".join(
                                part for part in (
                                    _vendor_join(item.get("active_min_price_amount")),
                                    _vendor_join(item.get("active_max_price_amount")),
                                )
                                if part
                            )
                        ),
                        "shopping_mall_active_contract_types": _vendor_join(item.get("active_contract_types")),
                        "shopping_mall_source_refreshed_at": _vendor_join(item.get("source_refreshed_at")),
                    })
                    if len(checks) >= max_checks:
                        break
        except Exception:
            pass
        data = None
        used_db_policy = False
        slow_policy_already_checked = (
            bool(checks)
            and disambiguation is None
            and not _vendor_is_multi_condition_query(q)
            and any(
                any(source in str(item.get("matched_policy_source") or "") for source in ("product_policy_summary", "monitoring_api"))
                for item in checks
            )
        )
        if slow_policy_already_checked:
            data = {"candidates": []}
        else:
            try:
                company_db = _vendor_import_company_db()
                search_product_policy = getattr(company_db, "search_product_policy", None)
                if callable(search_product_policy):
                    data = search_product_policy(term, limit=max_checks)
                    used_db_policy = bool(data and (data.get("candidates") or data.get("items") or data.get("data")))
            except Exception:
                data = None
            if not (data and (data.get("candidates") or data.get("items") or data.get("data"))):
                data = _monitoring_api_get(
                    "/api/chatbot/product-policy/search",
                    {"keyword": term, "limit": max_checks},
                    timeout=timeout,
                )
                used_db_policy = False
        if not data:
            continue
        policy_source = str((data.get("meta") or {}).get("source") or "product_policy_summary") if used_db_policy else "monitoring_api"
        raw_items = data.get("candidates") or data.get("items") or data.get("data") or []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            code = _vendor_join(item.get("detail_product_code"))
            name = _vendor_join(item.get("detail_product_name"))
            key = code or name
            merge_check({
                "detail_product_code": code,
                "detail_product_name": name,
                "matched_policy_keyword": term,
                "matched_policy_source": policy_source,
                "is_sme_competition_product": _vendor_join(item.get("is_sme_competition_product")),
                "is_construction_material_direct_purchase": _vendor_join(item.get("is_construction_material_direct_purchase")),
                "direct_production_valid_supplier_count": _vendor_join(item.get("direct_production_valid_supplier_count")),
                "mas_active_supplier_count": _vendor_join(item.get("mas_active_supplier_count")),
                "busan_company_product_count": _vendor_join(item.get("busan_company_product_count")),
                "required_special_note": _vendor_join(item.get("required_special_note")),
            })
            if name and name != term:
                try:
                    company_db = _vendor_import_company_db()
                    search_shopping_mall_item_policy = getattr(company_db, "search_shopping_mall_item_policy", None)
                    if callable(search_shopping_mall_item_policy):
                        mall_policy_data = search_shopping_mall_item_policy(name, limit=2)
                        for mall_item in (mall_policy_data or {}).get("candidates") or []:
                            if not isinstance(mall_item, dict):
                                continue
                            mall_code = _vendor_join(mall_item.get("detail_product_code"))
                            mall_name = _vendor_join(mall_item.get("detail_product_name"))
                            merge_check({
                                "detail_product_code": mall_code,
                                "detail_product_name": mall_name,
                                "matched_policy_keyword": name,
                                "matched_policy_source": "pps_shopping_mall_item_policy_summary",
                                "shopping_mall_product_class_code": _vendor_join(mall_item.get("product_class_code")),
                                "shopping_mall_product_class_name": _vendor_join(mall_item.get("product_class_name")),
                                "shopping_mall_active_registered_count": _vendor_join(mall_item.get("active_registered_count")),
                                "shopping_mall_active_third_party_count": _vendor_join(mall_item.get("active_third_party_count")),
                                "shopping_mall_active_mas_count": _vendor_join(mall_item.get("active_mas_count")),
                                "shopping_mall_active_general_unit_price_count": _vendor_join(mall_item.get("active_general_unit_price_count")),
                                "shopping_mall_active_excellent_procurement_count": _vendor_join(mall_item.get("active_excellent_procurement_count")),
                                "shopping_mall_active_sme_competition_count": _vendor_join(mall_item.get("active_sme_competition_count")),
                                "shopping_mall_active_supplier_count": _vendor_join(mall_item.get("active_supplier_count")),
                                "shopping_mall_active_busan_supplier_count": _vendor_join(mall_item.get("active_busan_supplier_count")),
                                "shopping_mall_active_contract_types": _vendor_join(mall_item.get("active_contract_types")),
                                "shopping_mall_source_refreshed_at": _vendor_join(mall_item.get("source_refreshed_at")),
                            })
                except Exception:
                    pass
            if len(checks) >= max_checks:
                return _vendor_sort_product_policy_checks(q, checks)
        if checks and disambiguation is None and not _vendor_is_multi_condition_query(q):
            contract_signal = _vendor_policy_contract_signal(checks)
            if contract_signal["busan_supplier_count"] or term_index >= 5:
                return _vendor_sort_product_policy_checks(q, checks)
    return _vendor_sort_product_policy_checks(q, checks)


def _vendor_route_candidate_count(rows: list[dict[str, str | int]], *fields: str) -> int:
    count = 0
    for row in rows:
        if any(_vendor_is_truthy(row.get(field)) for field in fields):
            count += 1
    return count


def _vendor_policy_tool_results(
    rows: list[dict[str, str | int]],
    product_policy_checks: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    def result(tool_name: str, count: int) -> dict[str, object]:
        return {
            "tool_name": tool_name,
            "status": "success",
            "result": f"부산 지역업체 검색 결과: 총 {count}건" if count else "검색 결과가 없습니다.",
            "elapsed_ms": 0,
        }

    candidate_exact_shopping_count = _vendor_route_candidate_count(
        rows,
        "mas_match",
        "shopping_mall_match",
    )
    generic_shopping_count = _vendor_route_candidate_count(
        rows,
        "mas_product_summary",
        "has_mas",
        "shopping_mall_product_summary",
        "has_shopping_mall",
    )
    third_party_count = 0
    for row in rows:
        mall_text = _vendor_join(row.get("shopping_mall_product_summary"))
        flags_text = _vendor_join(row.get("shopping_mall_flags"))
        combined = f"{mall_text} {flags_text}".lower()
        if any(term in combined for term in ("third_party_unit_price", "third party", "제3자", "3자단가", "제3자를 위한 단가")):
            third_party_count += 1
    contract_signal = _vendor_policy_contract_signal(product_policy_checks, rows)
    item_master_third_party_count = int(contract_signal["third_party_count"] or 0)
    item_master_shopping_count = max(
        int(contract_signal["registered_count"] or 0),
        int(contract_signal["mas_count"] or 0),
        int(contract_signal["general_unit_price_count"] or 0),
        int(contract_signal["supplier_count"] or 0),
        int(contract_signal["busan_supplier_count"] or 0),
    )
    # 구매경로 우선순위는 품목 마스터의 계약유형 근거를 우선한다.
    # 후보업체의 일반 보유 플래그는 후보 정렬에는 쓰되, 조달청 경로 확정 근거로 승격하지 않는다.
    shopping_count = max(item_master_shopping_count, candidate_exact_shopping_count)
    if not shopping_count and not product_policy_checks:
        shopping_count = generic_shopping_count
    third_party_count = max(third_party_count, item_master_third_party_count)
    policy_count = _vendor_route_candidate_count(rows, "policy_company_labels", "policy_subtypes")
    certified_count = _vendor_route_candidate_count(rows, "certified_product_labels", "certified_product_summary")

    return [
        result("search_third_party_unit_price", third_party_count),
        result("search_shopping_mall", shopping_count),
        result("search_local_company_by_product", len(rows)),
        result("search_company_by_policy", policy_count),
        result("search_certified_product", certified_count),
    ]


def _vendor_contract_object_for_route(q: str, construction_terms: list[str]) -> str:
    compact = _vendor_compact(q)
    if construction_terms and not _vendor_has_construction_material_intent(q):
        return "construction"
    if "공사" in compact and not _vendor_has_construction_material_intent(q):
        return "construction"
    if any(term in compact for term in ("용역", "과업", "위탁", "유지보수", "청소", "방역", "설계", "교육훈련", "학술연구", "원가계산")):
        return "service"
    return "goods"


def _vendor_route_item_name(q: str, product_policy_checks: list[dict[str, str]]) -> str:
    compact = _vendor_compact(q)
    preferred_names: list[str] = []
    if any(term in compact for term in ("데스크탑", "데스크톱", "desktop", "pc")):
        preferred_names.append("데스크톱컴퓨터")
    if any(term in compact for term in ("노트북", "랩톱", "랩탑", "notebook", "laptop")):
        preferred_names.append("노트북컴퓨터")
    for preferred in preferred_names:
        for item in product_policy_checks:
            name = _vendor_join(item.get("detail_product_name"))
            if preferred in name:
                return preferred
    for item in product_policy_checks:
        name = _vendor_join(item.get("detail_product_name"))
        if name:
            return name
    if any(term in compact for term in ("데스크탑", "데스크톱", "desktop", "pc")):
        return "데스크톱컴퓨터"
    if any(term in compact for term in ("노트북", "랩톱", "랩탑", "notebook", "laptop")):
        return "노트북컴퓨터"
    return q


def _vendor_priority_route_cards(
    q: str,
    rows: list[dict[str, str | int]],
    product_policy_checks: list[dict[str, str]],
    *,
    budget_krw: int | None,
    construction_terms: list[str],
) -> list[dict[str, object]]:
    if not budget_krw or build_purchase_route_cards is None:
        return []

    contract_signal = _vendor_policy_contract_signal(product_policy_checks, rows)
    basis_level = str(contract_signal["basis_level"])
    has_confirmed_contract = bool(contract_signal["has_confirmed_contract"])
    has_registered_item = int(contract_signal["registered_count"] or 0) > 0
    has_local_shopping_supplier = bool(contract_signal["has_local_shopping_supplier"])
    local_supplier_basis_text = _vendor_local_supplier_basis_text(contract_signal)

    try:
        item_name = _vendor_route_item_name(q, product_policy_checks)
        policy_cards = build_purchase_route_cards(
            amount=budget_krw,
            item_name=item_name,
            contract_object=_vendor_contract_object_for_route(q, construction_terms),
            tool_results=_vendor_policy_tool_results(rows, product_policy_checks),
        )
    except Exception:
        return []

    priority_order = {"primary": 0, "secondary": 1, "reference": 2, "excluded": 3}
    route_order = {
        "third_party_unit_price": -1,
        "shopping_mall_mas": 0,
        "local_company_alternative": 1,
        "two_quote_small_value": 1,
        "policy_company_one_quote": 2,
        "sme_competition_direct_production": 3,
        "general_small_value_direct": 4,
        "local_company_competitive": 5,
        "technology_development_product": 6,
        "innovation_product": 7,
    }

    route_cards: list[dict[str, object]] = []
    for card in sorted(
        [card for card in policy_cards if getattr(card, "display_policy", "show") != "hide"],
        key=lambda card: (
            priority_order.get(getattr(card, "route_priority", ""), 9),
            route_order.get(getattr(card, "route_id", ""), 80),
            getattr(card, "route_id", ""),
        ),
    ):
        route_id = getattr(card, "route_id", "")
        route_priority = getattr(card, "route_priority", "")
        status = getattr(card, "status", "")
        reason = getattr(card, "practical_meaning", "")
        user_label = getattr(card, "user_label", "")
        display_label = getattr(card, "title", "")
        basis_explanation = str(contract_signal["basis_explanation"])

        if route_id == "shopping_mall_mas":
            if basis_level == "confirmed_third_party_unit_price":
                display_label = "제3자단가계약"
            elif basis_level == "confirmed_mas":
                display_label = "다수공급자계약(MAS)"
            elif basis_level == "confirmed_general_unit_price":
                display_label = "일반단가계약"
            elif has_registered_item:
                display_label = "종합쇼핑몰 등록 품목이나 계약유형 확인 필요"
            if has_confirmed_contract:
                basis_label = str(contract_signal["basis_label"])
                if not has_local_shopping_supplier:
                    status = "no_local_supplier"
                    route_priority = "secondary"
                    reason = (
                        f"{basis_explanation} {local_supplier_basis_text} "
                        "조달청 계약경로로 바로 지역업체를 구매하기는 어려울 수 있으므로 조달청 입찰 가능성, "
                        "지역업체 직접계약·견적·입찰 가능성을 함께 검토해야 합니다."
                    )
                    user_label = f"{basis_label} / 부산 공급업체 미확인"
                else:
                    reason = f"{basis_explanation} {local_supplier_basis_text} 쇼핑몰/MAS 경로를 먼저 확인합니다."
                    user_label = basis_label
            elif has_registered_item:
                status = "registered_only"
                route_priority = "secondary"
                user_label = str(contract_signal["basis_label"])
                reason = (
                    f"{basis_explanation} 등록 사실만으로 조달청 구매 의무나 쇼핑몰 우선구매를 단정하지 말고, "
                    "물품식별번호·계약유형·계약상태·기관유형을 확인한 뒤 지역업체 후보와 비교합니다."
                )
            elif basis_level == "candidate_row_evidence_only":
                status = "candidate_evidence_only"
                route_priority = "secondary"
                user_label = "후보업체 단위 근거"
                reason = (
                    f"{basis_explanation} 쇼핑몰/MAS 구매 가능성은 열어두되, "
                    "품목 자체가 단가계약 대상인지 조달청 원천자료로 재확인해야 합니다."
                )
            else:
                status = "needs_lookup"
                route_priority = "reference"
                user_label = "조달청 단가계약 근거 미확인"
                reason = (
                    "현재 DB 기준 조달청 단가계약·MAS·종합쇼핑몰 등록 근거가 확정되지 않았습니다. "
                    "지역업체 직접계약, 2인 이상 견적, 입찰공고 조건 설계를 우선 대안으로 검토합니다."
                )
        elif route_id == "third_party_unit_price":
            display_label = "제3자단가계약"
            if basis_level == "confirmed_third_party_unit_price":
                if not has_local_shopping_supplier:
                    status = "no_local_supplier"
                    route_priority = "primary"
                    user_label = "제3자단가계약 품목으로 확인 / 부산 공급업체 미확인"
                    reason = (
                        f"{basis_explanation} {local_supplier_basis_text} "
                        "조달청 납품요구 가능성, 조달청 입찰 가능성, 지역업체 대안 경로를 분리해서 검토해야 합니다."
                    )
                else:
                    user_label = "제3자단가계약 품목으로 확인"
                    reason = f"{basis_explanation} {local_supplier_basis_text} 조달청 납품요구 경로를 먼저 확인합니다."
            elif status in {"needs_lookup", "no_candidate_found"}:
                route_priority = "reference"
        elif has_confirmed_contract and route_id in {"two_quote_small_value", "general_small_value_direct", "policy_company_one_quote"}:
            if route_priority == "primary":
                route_priority = "secondary"
                reason = (
                    f"{reason} 다만 품목 마스터에서 조달청 계약유형이 확인되므로, "
                    "조달청 납품요구·입찰 가능성을 먼저 확인한 뒤 지역업체 대안으로 검토합니다."
                )

        route_cards.append({
            "route_id": getattr(card, "route_id", ""),
            "label": display_label,
            "status": status,
            "route_priority": route_priority,
            "reason": reason,
            "required_checks": list(getattr(card, "required_checks", []) or []),
            "practical_note": f"예산 {_format_krw_short(budget_krw)} 기준: {user_label}",
            "next_actions": list(getattr(card, "required_checks", []) or [])[:3],
            "legal_refs": list(getattr(card, "legal_refs", ()) or ()),
            "display_policy": getattr(card, "display_policy", "show"),
            "exclusion_reason": getattr(card, "exclusion_reason", ""),
            "basis_level": basis_level if route_id in {"third_party_unit_price", "shopping_mall_mas"} else "",
            "basis_explanation": basis_explanation if route_id in {"third_party_unit_price", "shopping_mall_mas"} else "",
        })
    if has_confirmed_contract and not has_local_shopping_supplier:
        route_cards.append({
            "route_id": "local_company_alternative",
            "label": "지역업체 대안 검토",
            "status": "candidate_found",
            "route_priority": "secondary",
            "reason": (
                "조달청 단가계약 또는 쇼핑몰 계약경로 확인 대상이어도 해당 세부품명으로 부산 공급업체가 확인되지 않으면 "
                "조달등록·취급 후보만으로는 바로 구매 가능 업체로 보기 어렵습니다. 조달청 입찰 가능성, 지역업체 직접계약, "
                "2인 이상 견적, 지역제한 입찰, 정책기업·인증제품 경로를 대안으로 비교합니다."
            ),
            "required_checks": ["조달청 입찰 가능 여부", "직접계약 가능 여부", "2인 이상 견적 가능 여부", "지역제한 입찰 가능 여부", "정책기업·인증제품 증빙"],
            "practical_note": f"예산 {_format_krw_short(budget_krw)} 기준: 부산 쇼핑몰 공급업체 미확인 시 대안",
            "next_actions": ["조달등록 부산업체 취급품목 확인", "정책기업·직접생산·인증제품 근거 확인", "입찰 또는 견적 방식 검토"],
            "legal_refs": ["지방계약법 시행령 제25조", "지방계약법 시행령 제30조", "지방계약법 시행규칙 제24조"],
            "display_policy": "show",
            "exclusion_reason": "",
            "basis_level": "local_vendor_alternative",
            "basis_explanation": "부산 쇼핑몰 공급업체가 없을 때 지역업체 활용 가능성을 닫지 않기 위한 대안 카드입니다.",
        })
        route_cards.sort(
            key=lambda item: (
                priority_order.get(str(item.get("route_priority")), 9),
                route_order.get(str(item.get("route_id")), 80),
                str(item.get("route_id", "")),
            )
        )
    return route_cards


def _vendor_purchase_route_guidance(
    q: str,
    rows: list[dict[str, str | int]],
    product_policy_checks: list[dict[str, str]],
    item_policy_summary: dict[str, object],
    *,
    budget_krw: int | None = None,
) -> dict[str, object]:
    if item_policy_summary.get("status") == "needs_item_selection":
        message = str(
            item_policy_summary.get("message")
            or "세부품명을 선택한 뒤 품목정책과 구매방식을 다시 판정해야 합니다."
        )
        selection_card = {
            "route_id": "item_selection_required",
            "label": "세부 품목 선택 필요",
            "status": "needs_item_selection",
            "reason": message,
            "required_checks": ["정확한 세부품명", "세부품명번호 10자리", "구매 규격·용도"],
            "practical_note": "세부품명 선택 전에는 중기간·직접생산·조달청 구매경로를 확정하지 않습니다.",
            "next_actions": ["품목정책 판정 영역에서 실제 구매하려는 세부품명 선택"],
            "route_priority": "primary",
            "basis_level": "item_selection_required",
            "basis_explanation": message,
        }
        return {
            "title": "세부 품목 선택 필요",
            "primary_route": selection_card,
            "route_cards": [selection_card],
            "badges": [{"label": "품목 선택 필요", "tone": "warn"}],
            "required_checks": list(selection_card["required_checks"]),
            "ranking_basis": ["세부품명 선택 전에는 구매방식과 업체 순위를 확정하지 않음"],
            "item_policy_status": "needs_item_selection",
            "purchase_route_basis_level": "item_selection_required",
            "purchase_route_basis_label": "세부품명 선택 필요",
            "purchase_route_basis_explanation": message,
            "shopping_mall_busan_supplier_count": 0,
            "shopping_mall_candidate_exact_supplier_count": 0,
            "shopping_mall_local_supplier_basis": "none",
            "shopping_mall_active_registered_count": 0,
            "legal_notice": "세부품명번호 10자리를 확정한 뒤 현행 품목정책과 계약 가능 여부를 재확인해야 합니다.",
        }
    requirements = _vendor_policy_route_requirements(product_policy_checks)
    contract_signal = _vendor_policy_contract_signal(product_policy_checks, rows)
    basis_level = str(contract_signal["basis_level"])
    has_confirmed_contract = bool(contract_signal["has_confirmed_contract"])
    has_registered_item = int(contract_signal["registered_count"] or 0) > 0
    has_local_shopping_supplier = bool(contract_signal["has_local_shopping_supplier"])
    local_supplier_basis = str(contract_signal.get("local_supplier_basis") or "none")
    local_supplier_basis_text = _vendor_local_supplier_basis_text(contract_signal)
    construction_terms = _vendor_requested_construction_terms(q)
    contract_object = _vendor_contract_object_for_route(q, construction_terms)
    service_route_primary = contract_object == "service"
    construction_material_intent = _vendor_has_construction_material_intent(q)
    construction_route_primary = bool(construction_terms) and not construction_material_intent
    strict_policy_item_identity = _vendor_has_policy_item_code_identity(product_policy_checks)
    row_has_direct = any(
        _vendor_is_truthy(row.get("direct_production_match"))
        or (
            not strict_policy_item_identity
            and (
                _vendor_is_truthy(row.get("direct_production_certificate_products"))
                or _vendor_is_truthy(row.get("direct_production_summary"))
                or _vendor_is_truthy(row.get("direct_production_flags"))
            )
        )
        for row in rows
    )
    row_has_mas = any(
        _vendor_is_truthy(row.get("mas_match"))
        or (
            not strict_policy_item_identity
            and (
                _vendor_is_truthy(row.get("mas_product_summary"))
                or _vendor_is_truthy(row.get("has_mas"))
            )
        )
        for row in rows
    )
    row_has_shopping = any(
        _vendor_is_truthy(row.get("shopping_mall_match"))
        or (
            not strict_policy_item_identity
            and (
                _vendor_is_truthy(row.get("shopping_mall_product_summary"))
                or _vendor_is_truthy(row.get("has_shopping_mall"))
            )
        )
        for row in rows
    )
    row_has_construction = any(
        _vendor_is_truthy(row.get("construction_license_match"))
        or _vendor_is_truthy(row.get("construction_capacity_match"))
        or _vendor_is_truthy(row.get("construction_capacity_amount"))
        or _vendor_is_truthy(row.get("construction_capacity_summary"))
        for row in rows
    )
    row_has_policy = any(
        _vendor_is_truthy(row.get("policy_company_labels"))
        or _vendor_is_truthy(row.get("policy_subtypes"))
        for row in rows
    )
    row_has_certified = any(
        _vendor_is_truthy(row.get("certified_product_labels"))
        or _vendor_is_truthy(row.get("certified_product_types"))
        or _vendor_is_truthy(row.get("certified_product_summary"))
        for row in rows
    )
    row_has_cooperative = any(
        _vendor_contains_any(
            row,
            ["procurement_attributes", "policy_subtypes", "candidate_types", "cooperative_purchase_route_label"],
            ("coop", "cooperative", "협동조합", "조합추천", "소기업공동", "small_business_collective"),
        )
        for row in rows
    )
    direct_contract_support_count = sum(
        1
        for row in rows
        if _vendor_direct_contract_support(row)[0] > 0
    )
    direct_contract_preferred = not has_confirmed_contract or not has_local_shopping_supplier

    route_cards: list[dict[str, object]] = []

    def add_card(
        route_id: str,
        label: str,
        status: str,
        reason: str,
        required_checks: list[str],
        practical_note: str = "",
        next_actions: list[str] | None = None,
        route_priority: str = "",
        basis_level_override: str = "",
        basis_explanation: str = "",
    ) -> None:
        route_cards.append({
            "route_id": route_id,
            "label": label,
            "status": status,
            "reason": reason,
            "required_checks": required_checks,
            "practical_note": practical_note,
            "next_actions": next_actions or [],
            "route_priority": route_priority,
            "basis_level": basis_level_override,
            "basis_explanation": basis_explanation,
        })

    def add_direct_contract_support_card() -> None:
        if not direct_contract_preferred or not direct_contract_support_count:
            return
        if any(str(card.get("route_id")) == "regional_direct_contract_support" for card in route_cards):
            return
        support_labels = []
        if row_has_policy:
            support_labels.append("정책기업")
        if row_has_certified:
            support_labels.append("기술개발/인증제품")
        if row_has_cooperative:
            support_labels.append("조합추천/공동사업")
        if row_has_direct:
            support_labels.append("직접생산")
        reason_prefix = (
            "현재 DB에서 조달청 단가계약 경로가 확정되지 않아"
            if not has_confirmed_contract
            else "조달청 계약경로는 확인되지만 부산 쇼핑몰 공급업체가 확인되지 않아"
        )
        add_card(
            "regional_direct_contract_support",
            "지역업체 직접계약 지원 근거",
            "candidate_found",
            f"{reason_prefix} 정책기업·기술개발제품·조합추천·직접생산 등 수의계약 또는 지역업체 활용 근거가 있는 후보를 우선 비교합니다.",
            ["수의계약 가능 금액", "정책기업/인증제품/조합추천 증빙", "직접생산확인증명서 세부품명", "발주기관 적용 법령", "가격 적정성"],
            f"확인된 지원 근거: {', '.join(support_labels) if support_labels else '후보별 세부 근거 확인 필요'}",
            ["후보표의 구매 지원 근거와 증빙 유효기간 확인", "수의계약 한도와 1인/2인 견적 요건 확인", "조달청 구매 의무 대상이면 조달청 경로를 먼저 판단"],
            route_priority="secondary",
            basis_level_override="regional_direct_contract_support",
            basis_explanation="조달청 우선 구매 대상이 명확하지 않거나 부산 쇼핑몰 공급업체가 없을 때 적용하는 지역업체 대안 판단입니다.",
        )

    if construction_terms:
        add_card(
            "construction_license",
            "공사 면허/시공능력 검토",
            "candidate_found" if row_has_construction else "needs_check",
            "입력 질의가 공사업 면허 또는 공사 시공 조건으로 해석됩니다.",
            ["공사 종류", "요구 면허", "시공능력평가금액", "입찰공고/직접계약 가능 여부"],
            "공사는 품목 구매가 아니라 면허·실적·시공능력 기준으로 후보를 좁히는 경로입니다.",
            ["요구 면허와 시공능력평가금액을 먼저 확인", "공사 내용이 공사용자재 직접구매 대상과 연결되는지 별도 확인"],
            route_priority="reference" if _vendor_has_construction_material_intent(q) else "primary",
        )
    if service_route_primary and not has_confirmed_contract:
        add_card(
            "service_contract_review",
            "용역 직접계약/입찰공고 검토",
            "candidate_found" if rows else "needs_check",
            "입력 질의가 용역으로 해석되며, 현재 DB 기준 조달청 단가계약/MAS 품목 근거가 확정되지 않았습니다.",
            ["용역 범위", "업종·면허·인력 요건", "수행실적", "지역제한 가능 여부", "수의계약/입찰공고 가능 여부"],
            "용역은 물품식별번호보다 과업 범위, 업종·면허, 수행실적, 발주기관 적용 법령을 먼저 확인해야 합니다.",
            ["후보업체의 실제 수행 가능 용역 확인", "수의계약 가능 금액과 견적 요건 확인", "지역제한 또는 평가항목 적용 가능성 확인"],
            route_priority="primary",
        )
    if requirements["has_mas_route"] or has_confirmed_contract or (row_has_mas and not service_route_primary):
        if basis_level == "confirmed_third_party_unit_price":
            central_route_id = "third_party_unit_price"
            central_route_title = "제3자단가계약"
            central_required_checks = ["제3자단가계약 여부", "계약기간", "납품조건", "납품요구 가능 여부", "부산 공급업체 여부"]
            central_practical_note = "제3자단가계약 품목으로 확인되면 조달청 종합쇼핑몰 납품요구 경로를 우선 확인합니다."
            central_next_actions = ["조달청 종합쇼핑몰에서 동일 세부품명 검색", "부산 공급업체 등록 여부 확인", "계약기간과 납품조건 확인"]
        elif basis_level == "confirmed_mas":
            central_route_id = "mas"
            central_route_title = "다수공급자계약(MAS)"
            central_required_checks = ["MAS 계약상태", "계약기간", "납품조건", "2단계 경쟁 필요 여부", "부산 공급업체 여부"]
            central_practical_note = (
                "다수공급자계약(MAS) 품목으로 확인됩니다. 원칙적으로 조달청 종합쇼핑몰/MAS 2단계경쟁 경로를 우선 확인해야 합니다. "
                "다만 현재 DB 기준 부산 MAS/쇼핑몰 공급업체가 확인되지 않거나 필요한 규격·조건을 MAS로 충족하기 어려운 경우에는 "
                "조달청 입찰 또는 발주기관 일반입찰 가능성을 계약부서와 별도 검토해야 합니다."
            )
            central_next_actions = ["조달청 종합쇼핑몰에서 동일 세부품명 검색", "2단계 경쟁 대상 금액인지 확인", "부산업체의 MAS 계약 유효 여부 확인", "MAS 충족 곤란 시 입찰 대안 검토"]
        elif basis_level == "confirmed_general_unit_price":
            central_route_id = "general_unit_price"
            central_route_title = "일반단가계약"
            central_required_checks = ["일반단가계약 여부", "계약기간", "납품조건", "부산 공급업체 여부"]
            central_practical_note = "일반단가계약 품목으로 확인되면 조달청 계약조건과 기관 구매 가능 여부를 확인합니다."
            central_next_actions = ["조달청 종합쇼핑몰에서 동일 세부품명 검색", "계약기간과 납품조건 확인", "부산 공급업체 등록 여부 확인"]
        else:
            central_route_id = "mas"
            central_route_title = "다수공급자계약(MAS)"
            central_required_checks = ["제3자단가계약 여부", "MAS 계약상태", "계약기간", "납품조건", "2단계 경쟁 필요 여부"]
            central_practical_note = "금액·품목 조건에 따라 바로구매 또는 2단계 경쟁으로 갈라질 수 있으므로 물품식별번호와 계약조건 확인이 필요합니다."
            central_next_actions = ["조달청 종합쇼핑몰에서 동일 세부품명 검색", "2단계 경쟁 대상 금액인지 확인", "부산업체의 MAS 계약 유효 여부 확인"]
        if has_confirmed_contract:
            mas_status = "candidate_found" if has_local_shopping_supplier else "no_local_supplier"
            mas_reason = (
                f"{contract_signal['basis_explanation']} {local_supplier_basis_text} "
                "조달청 종합쇼핑몰/MAS 계약경로를 먼저 확인합니다."
                if has_local_shopping_supplier
                else (
                    f"{contract_signal['basis_explanation']} {local_supplier_basis_text} "
                    "조달청 계약경로로 바로 지역업체를 구매하기 어려울 수 있으므로 조달청 입찰 가능성과 지역업체 대안 경로를 함께 검토합니다."
                )
            )
            mas_priority = "primary" if has_local_shopping_supplier else "secondary"
        elif row_has_mas:
            mas_status = "candidate_evidence_only"
            mas_reason = "후보업체 DB에 MAS 근거가 있으나 품목 마스터 기준 계약유형 확정 근거는 추가 확인이 필요합니다."
            mas_priority = "primary" if construction_material_intent else "reference"
        else:
            mas_status = "policy_only"
            mas_reason = "제3자단가계약 또는 다수공급자계약 가능성이 있으면 조달청 종합쇼핑몰/MAS 구매 경로를 검토합니다."
            mas_priority = "reference"
        add_card(
            central_route_id,
            central_route_title,
            mas_status,
            mas_reason,
            central_required_checks,
            central_practical_note,
            central_next_actions,
            route_priority=mas_priority,
            basis_level_override=basis_level,
            basis_explanation=str(contract_signal["basis_explanation"]),
        )
    if requirements["has_shopping_route"] or has_registered_item or (row_has_shopping and not service_route_primary):
        if has_registered_item and not has_confirmed_contract:
            shopping_status = "registered_only"
            shopping_reason = (
                f"{contract_signal['basis_explanation']} 등록 사실만으로 조달청 구매 의무나 쇼핑몰 우선구매를 단정하지 말고 "
                "계약유형, 물품식별번호, 기관유형을 확인해야 합니다."
            )
            shopping_priority = "secondary"
        elif row_has_shopping and not has_confirmed_contract:
            shopping_status = "candidate_evidence_only"
            shopping_reason = "후보업체 DB에 쇼핑몰 등록 근거가 있으나 품목 계약유형은 조달청 원천자료로 확인해야 합니다."
            shopping_priority = "reference"
        else:
            shopping_status = "candidate_found" if row_has_shopping else "policy_only"
            shopping_reason = (
                f"{local_supplier_basis_text} 종합쇼핑몰 등록 상품이면 조달청 쇼핑몰 구매 또는 수의계약 성격의 바로구매 가능성을 검토할 수 있습니다."
                if has_confirmed_contract
                else "종합쇼핑몰 등록 상품이면 조달청 쇼핑몰 구매 또는 수의계약 성격의 바로구매 가능성을 검토할 수 있습니다."
            )
            shopping_priority = "reference" if not has_confirmed_contract else "secondary"
        add_card(
            "shopping_mall",
            "종합쇼핑몰 구매",
            shopping_status,
            shopping_reason,
            ["쇼핑몰 등록상태", "물품식별번호", "가격/규격", "납품 가능지역"],
            "지역업체가 쇼핑몰에 등록돼 있으면 담당자가 별도 공고 없이 구매 가능한지 확인하기 쉬운 근거가 됩니다.",
            ["부산업체 등록 상품 여부 확인", "가격·규격·납품 가능지역 확인", "동일 품목의 타지역 상품과 비교"],
            route_priority=shopping_priority,
            basis_level_override=basis_level,
            basis_explanation=str(contract_signal["basis_explanation"]),
        )
    if has_confirmed_contract and not has_local_shopping_supplier:
        add_card(
            "local_company_alternative",
            "지역업체 대안 검토",
            "candidate_found",
            (
                f"{local_supplier_basis_text} 조달청 단가계약 또는 쇼핑몰 계약경로 확인 대상이어도 부산 공급업체가 확인되지 않으면 "
                "조달등록·취급 후보만으로 바로 구매 가능 업체로 보지 말고 조달청 입찰 가능성과 지역업체 직접계약·견적·입찰 가능성을 함께 봅니다."
            ),
            ["조달청 입찰 가능 여부", "직접계약 가능 여부", "2인 이상 견적 가능 여부", "지역제한 입찰 가능 여부", "정책기업·인증제품 증빙"],
            "부산 쇼핑몰 공급업체 미확인 시 지역업체 후보를 닫지 않고 대안으로 비교합니다.",
            ["조달등록 부산업체 취급품목 확인", "정책기업·직접생산·인증제품 근거 확인", "입찰 또는 견적 방식 검토"],
            route_priority="secondary",
            basis_level_override="local_vendor_alternative",
            basis_explanation="부산 쇼핑몰 공급업체가 없을 때 지역업체 활용 가능성을 검토하기 위한 대안입니다.",
        )
    if requirements["is_sme_competition_product"] or requirements["requires_direct_production"]:
        add_card(
            "sme_direct_production",
            "중소기업자간 경쟁제품/직접생산",
            "candidate_found" if row_has_direct else "needs_check",
            "중소기업자간 경쟁제품이면 중소기업제품 검색과 직접생산확인증명서 보유 여부를 먼저 확인해야 합니다.",
            ["중기간 경쟁제품 해당 여부", "직접생산확인증명서", "세부품명 일치", "유효기간"],
            "직접생산이 필요한 품목에서 증명서가 없는 업체는 상위 후보라도 계약 전 검토 대상에서 제외될 수 있습니다.",
            ["세부품명 기준 중기간 경쟁제품 여부 확인", "직접생산확인증명서 유효기간 확인", "조합추천·공동사업 적용 가능성 확인"],
            route_priority="secondary",
        )
    if row_has_policy:
        add_card(
            "policy_company_direct",
            "정책기업 수의계약 검토 가능",
            "candidate_found",
            "여성기업·장애인기업·사회적기업 등 정책기업 근거가 있는 업체는 관련 법령상 수의계약 가능 범위 확대 여부를 검토할 수 있습니다.",
            ["정책기업 유형", "인증 유효기간", "수의계약 한도", "발주기관 적용 법령"],
            "정책기업 여부는 구매 편의성을 높이는 보조 근거이며, 최종 가능 여부는 금액·계약목적·발주기관 법령에 따라 달라집니다.",
            ["정책기업 유형과 유효기간 확인", "국가계약/지방계약 적용 여부 확인", "동일 품목 공급 가능성 확인"],
            route_priority="secondary",
        )
    if requirements["has_facility_material_price"]:
        add_card(
            "facility_material_price",
            "시설공통자재 가격정보",
            "reference_only",
            "시설공통자재 가격정보와 매칭된 품목이면 가격 기준과 규격을 참고하고 공사용자재 직접구매 대상 여부를 확인합니다.",
            ["가격 기준일", "규격 일치", "공사용자재 직접구매 대상 여부"],
            "가격정보는 후보업체 확정 근거가 아니라 설계·예정가격·품목 식별을 보조하는 참고자료입니다.",
            ["동일 규격 가격정보 확인", "공사용자재 직접구매 대상 여부 확인"],
            route_priority="reference",
        )

    if (
        basis_level == "no_central_procurement_evidence"
        and not service_route_primary
        and not construction_route_primary
        and not (construction_material_intent and (row_has_mas or row_has_shopping))
        and not any(str(card.get("route_id")) == "open_market_or_bid" for card in route_cards)
    ):
        add_card(
            "open_market_or_bid",
            "직접계약/입찰공고 검토",
            "needs_check",
            "품목정책 DB에서 제3자단가·MAS·쇼핑몰·직접생산 필수 근거가 명확히 확인되지 않았습니다.",
            ["조달등록 여부", "면허/업종", "영업상태", "공고 조건"],
            "이 경우에는 조달등록 부산업체 후보를 기준으로 직접계약 가능성 또는 입찰공고 조건 설계를 검토합니다.",
            ["조달등록·영업상태 확인", "면허·업종과 실제 취급품목 확인", "공고 조건에 지역업체 참여 가능성을 반영할지 검토"],
            route_priority="primary",
            basis_level_override=basis_level,
            basis_explanation=str(contract_signal["basis_explanation"]),
        )

    if not route_cards:
        add_card(
            "open_market_or_bid",
            "직접계약/입찰공고 검토",
            "needs_check",
            "품목정책 DB에서 제3자단가·MAS·쇼핑몰·직접생산 필수 근거가 명확히 확인되지 않았습니다.",
            ["조달등록 여부", "면허/업종", "영업상태", "공고 조건"],
            "이 경우에는 조달등록 부산업체 후보를 기준으로 직접계약 가능성 또는 입찰공고 조건 설계를 검토합니다.",
            ["조달등록·영업상태 확인", "면허·업종과 실제 취급품목 확인", "공고 조건에 지역업체 참여 가능성을 반영할지 검토"],
            route_priority="secondary",
            basis_level_override=basis_level,
            basis_explanation=str(contract_signal["basis_explanation"]),
        )

    budget_route_cards = _vendor_priority_route_cards(
        q,
        rows,
        product_policy_checks,
        budget_krw=budget_krw,
        construction_terms=construction_terms,
    )
    if budget_route_cards:
        route_cards = budget_route_cards
    add_direct_contract_support_card()

    priority = {
        "candidate_found": 0,
        "policy_only": 1,
        "needs_check": 2,
        "reference_only": 3,
    }
    route_priority = {
        "primary": 0,
        "secondary": 1,
        "reference": 2,
        "excluded": 3,
    }
    route_order = {
        "third_party_unit_price": -1,
        "shopping_mall_mas": 0,
        "mas": 0,
        "general_unit_price": 0,
        "shopping_mall": 1,
        "two_quote_small_value": 2,
        "local_company_alternative": 2,
        "regional_direct_contract_support": 2,
        "sme_direct_production": 2,
        "sme_competition_direct_production": 3,
        "policy_company_one_quote": 4,
        "policy_company_direct": 4,
        "general_small_value_direct": 5,
        "facility_material_price": 4,
        "construction_license": 6,
        "service_contract_review": 6,
        "local_company_competitive": 7,
        "technology_development_product": 8,
        "innovation_product": 9,
        "open_market_or_bid": 10,
    }

    def route_sort_key(item: dict[str, object]) -> tuple[int, int, str]:
        route_id = str(item.get("route_id"))
        if construction_route_primary and route_id == "construction_license":
            return (-1, priority.get(str(item.get("status")), 9), route_id)
        priority_group = route_priority.get(str(item.get("route_priority")), priority.get(str(item.get("status")), 9))
        return (priority_group, route_order.get(route_id, 80), route_id)

    route_cards.sort(key=route_sort_key)
    primary = route_cards[0]
    badges = []
    if basis_level == "confirmed_third_party_unit_price":
        badges.append({"label": "제3자단가계약 품목", "tone": "warn" if not has_local_shopping_supplier else "info"})
    elif basis_level == "confirmed_mas":
        badges.append({"label": "다수공급자계약(MAS) 품목", "tone": "warn" if not has_local_shopping_supplier else "info"})
    elif basis_level == "confirmed_general_unit_price":
        badges.append({"label": "일반단가계약 품목", "tone": "warn" if not has_local_shopping_supplier else "info"})
    elif basis_level == "shopping_mall_registered_only":
        badges.append({"label": "종합쇼핑몰 등록 품목·계약유형 확인 필요", "tone": "warn"})
    if has_confirmed_contract and not has_local_shopping_supplier:
        badges.append({"label": "부산 MAS/쇼핑몰 공급업체 미확인", "tone": "warn"})
    elif has_confirmed_contract and local_supplier_basis == "candidate_exact_evidence":
        badges.append({"label": "업체별 MAS/쇼핑몰 부산근거 수동확인", "tone": "warn"})
    if construction_terms:
        badges.append({"label": "공사 면허/시공능력 검토", "tone": "good" if row_has_construction else "warn"})
    if requirements["is_sme_competition_product"]:
        badges.append({"label": "중소기업자간 경쟁제품 해당(DB 기준)", "tone": "warn"})
    if requirements["requires_direct_production"]:
        badges.append({"label": "직접생산 확인 필요", "tone": "warn" if not row_has_direct else "good"})
    if row_has_mas and (not has_confirmed_contract or has_local_shopping_supplier):
        badges.append({"label": "조달청 다수공급자계약(MAS) 지역업체 존재", "tone": "info"})
    if row_has_shopping and (not has_confirmed_contract or has_local_shopping_supplier):
        badges.append({"label": "조달청 나라장터 지역업체 존재", "tone": "info"})
    if row_has_policy:
        badges.append({"label": "정책기업 수의계약 검토 가능", "tone": "good"})
    if direct_contract_preferred and direct_contract_support_count:
        badges.append({"label": "지역업체 직접계약 근거 있음", "tone": "good"})
    if has_confirmed_contract and not has_local_shopping_supplier:
        badges.append({"label": "지역업체 대안 검토", "tone": "info"})
    if requirements["has_facility_material_price"]:
        badges.append({"label": "시설자재 가격정보 매칭", "tone": "neutral"})
    required_checks: list[str] = []
    for card in route_cards:
        for check in card.get("required_checks") or []:
            if check not in required_checks:
                required_checks.append(str(check))

    return {
        "title": str(primary["label"]),
        "primary_route": primary,
        "route_cards": route_cards,
        "badges": badges,
        "required_checks": required_checks,
        "ranking_basis": [
            "입력 품목/면허와 직접 일치하는 업체",
            "품목 마스터의 계약유형이 확인된 경우 해당 조달청 경로에 맞는 업체",
            "부산 쇼핑몰 공급업체가 없을 경우 직접계약·견적·입찰 대안으로 검토 가능한 지역업체",
            "조달청 우선경로가 확정되지 않은 경우 정책기업·기술개발제품·조합추천 등 수의계약 지원 근거가 있는 업체",
            "지역업체 구매 지원 근거(MAS/쇼핑몰/직접생산/시공능력)가 있는 업체",
            "정상 영업 상태와 부산 본사 근거가 확인되는 업체",
            "정책기업·인증제품 등 계약 편의성이 있는 업체",
        ],
        "item_policy_status": item_policy_summary.get("status"),
        "purchase_route_basis_level": basis_level,
        "purchase_route_basis_label": contract_signal["basis_label"],
        "purchase_route_basis_explanation": contract_signal["basis_explanation"],
        "shopping_mall_busan_supplier_count": contract_signal["busan_supplier_count"],
        "shopping_mall_candidate_exact_supplier_count": contract_signal["candidate_row_evidence_count"],
        "shopping_mall_local_supplier_basis": contract_signal["local_supplier_basis"],
        "shopping_mall_active_registered_count": contract_signal["registered_count"],
        "legal_notice": "구매방식 안내는 후보 정보입니다. 최종 계약 가능 여부, 수의계약 가능 한도, 법령 해석은 별도 계약검토/법령해석 절차에서 확인해야 합니다.",
    }


def _vendor_sort_product_policy_checks(q: str, checks: list[dict[str, str]]) -> list[dict[str, str]]:
    compact_q = _vendor_compact(q)

    def rank(item: dict[str, str]) -> tuple[int, int, str]:
        name = _vendor_compact(item.get("detail_product_name") or "")
        keyword = _vendor_compact(item.get("matched_policy_keyword") or "")
        score = 0
        if keyword and keyword in name:
            score += 20
        if any(term in compact_q for term in ("pc", "데스크톱", "데스크탑")):
            if any(term in name for term in ("데스크톱컴퓨터", "노트북컴퓨터", "컴퓨터서버")):
                score += 40
            if "컴퓨터책상" in name:
                score -= 50
        if any(term in compact_q for term in ("노트북", "랩톱", "랩탑")):
            if "노트북컴퓨터" in name:
                score += 50
            if "컴퓨터책상" in name:
                score -= 50
        if "토너" in compact_q:
            if "토너" in name:
                score += 50
            if any(term in name for term in ("프린터", "복사용지")):
                score -= 20
        if any(term in compact_q for term in ("빔프로젝터", "프로젝터")):
            if "비디오프로젝터" in name or "프로젝터" in name:
                score += 50
        if "드론" in compact_q and "드론" in name:
            score += 50
        if "사무용가구" in compact_q:
            if any(term in name for term in ("책상", "의자", "사무용가구")):
                score += 35
            if "기타미분류가구" in name:
                score -= 20
        try:
            direct_count = int(str(item.get("direct_production_valid_supplier_count") or "0").replace(",", ""))
        except ValueError:
            direct_count = 0
        return (score, direct_count, str(item.get("detail_product_name") or ""))

    return sorted(checks, key=rank, reverse=True)


def _vendor_should_check_product_policy(q: str) -> bool:
    compact = _vendor_compact(q)
    product_markers = (
        "구매",
        "납품",
        "물품",
        "제품",
        "장치",
        "기기",
        "자재",
        "소모품",
        "컴퓨터",
        "노트북",
        "led",
        "cctv",
        "토너",
        "드론",
        "가구",
        "분전반",
        "인쇄",
        "홍보물",
        "현수막",
        "소프트웨어",
        "sw",
        "방화벽",
        "프로젝터",
        "빔프로젝터",
        "빔프로젝트",
        "레미콘",
        "아스콘",
        "아스팔트",
        "아스팔트콘크리트",
        "탄성포장재",
        "책상",
        "의자",
        "캐비닛",
        "문서보관",
        "보관함",
        "수납장",
        "냉난방기",
        "에어컨",
    )
    service_markers = (
        "용역",
        "공사",
        "경비",
        "청소",
        "번역",
        "통역",
        "행사",
        "시설관리",
        "방역",
        "소독",
        "설계",
        "측량",
        "폐기물",
        "원가계산",
        "법무",
        "유지보수",
    )
    if any(marker in compact for marker in product_markers):
        return True
    if any(marker in compact for marker in service_markers):
        return False
    return True


def _vendor_recommendation_rows(q: str, *, region: str = "부산", limit: int = 30, budget_krw: int | None = None) -> list[dict[str, str | int]]:
    requested_limit = max(1, min(int(limit or 30), 100))
    # The candidate search fans out over several product/license sources. A fixed
    # 30-row pool made short UI requests pay for broad follow-up searches even
    # after enough candidates were already available. Keep a modest ranking
    # buffer, but do not force every 5-row UI query to collect 30 raw rows.
    pool_limit = max(requested_limit, min(max(requested_limit + 8, 15), 100))
    if _vendor_query_has_any(q, ("벤처나라", "거래실적", "구매실적", "납품실적", "주문거래")):
        pool_limit = max(pool_limit, min(max(requested_limit + 25, 30), 100))
    raw_rows = _vendor_search_rows(q, region=region, limit=pool_limit)
    if not _vendor_is_medical_vaccine_query(q):
        company_db = _vendor_import_company_db()
        history_rows = _vendor_contract_history_search_rows(company_db, q, region=region, limit=pool_limit)
        if history_rows:
            seen = {row.get("company_id") or row.get("company_name") for row in raw_rows}
            for history_row in history_rows:
                key = history_row.get("company_id") or history_row.get("company_name")
                if not key or key in seen:
                    continue
                raw_rows.append(history_row)
                seen.add(key)
                if len(raw_rows) >= pool_limit:
                    break
    rows = [_vendor_recommendation_row(row, budget_krw=budget_krw) for row in raw_rows]
    rows = _vendor_apply_contract_history_evidence(rows, q)
    for row in rows:
        row["match_rank_score"] = _vendor_match_rank_score(row, q)
    rows.sort(
        key=lambda row: (
            int(row.get("match_rank_score") or 0),
            int(row.get("review_score") or 0),
        ),
        reverse=True,
    )
    return rows[:requested_limit]


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


@app.get("/vendors/search")
def vendor_search(q: str, region: str = "부산", limit: int = 50):
    rows = _vendor_search_rows(q, region=region, limit=limit)
    return JSONResponse(
        content={
            "query": q,
            "region": region,
            "limit": max(1, min(int(limit or 50), 500)),
            "count": len(rows),
            "columns": VENDOR_CSV_FIELDS,
            "rows": rows,
            "limitations": [
                "candidate list only; contract eligibility is not confirmed",
                "business status, licenses, direct production, and product validity must be rechecked before notice or contract",
            ],
        },
        media_type="application/json; charset=utf-8",
    )


@app.get("/vendor-recommendations/search")
def vendor_recommendation_search(
    q: str,
    region: str = "부산",
    limit: int = 30,
    budget_krw: int | None = None,
    include_product_policy: bool = True,
):
    payload = _vendor_recommendation_payload(
        q,
        region=region,
        limit=limit,
        budget_krw=budget_krw,
        include_product_policy=include_product_policy,
    )
    return JSONResponse(
        content=payload,
        media_type="application/json; charset=utf-8",
    )


@app.get("/vendor-recommendations/search.xlsx")
def vendor_recommendation_search_xlsx(
    q: str,
    region: str = "부산",
    limit: int = 100,
    budget_krw: int | None = None,
    include_product_policy: bool = True,
):
    payload = _vendor_recommendation_payload(
        q,
        region=region,
        limit=limit,
        budget_krw=budget_krw,
        include_product_policy=include_product_policy,
    )
    content = _vendor_recommendation_xlsx_bytes(payload)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="busan_vendor_recommendations.xlsx"'},
    )


@app.get("/vendor-recommendations/{company_id}/contract-history")
def vendor_recommendation_contract_history(
    company_id: str,
    q: str = "",
    limit: int = 20,
):
    payload = _vendor_contract_history_detail_payload(company_id, q=q, limit=limit)
    return JSONResponse(
        content=payload,
        media_type="application/json; charset=utf-8",
    )


@app.get("/vendors/query.csv")
def vendor_query_csv(q: str, region: str = "부산", limit: int = 50):
    rows = _vendor_search_rows(q, region=region, limit=limit)
    return Response(
        content=_vendor_rows_to_csv_bytes(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="busan_vendor_query.csv"'},
    )


@app.get("/vendors/search.csv")
def vendor_search_csv(q: str, region: str = "부산", limit: int = 50):
    return vendor_query_csv(q=q, region=region, limit=limit)


@app.get("/vendors/download.csv")
def vendor_download_csv(active_only: bool = True, limit: int = 0):
    rows = _vendor_download_rows(active_only=active_only, limit=limit)
    return Response(
        content=_vendor_rows_to_csv_bytes(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="busan_vendor_candidates.csv"'},
    )


@app.get("/vendors/download.zip")
def vendor_download_zip(active_only: bool = True, limit: int = 0):
    rows = _vendor_download_rows(active_only=active_only, limit=limit)
    return Response(
        content=_vendor_zip_bytes("busan_vendor_candidates.csv", rows),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="busan_vendor_candidates.zip"'},
    )


@app.get("/vendors/download-file.zip")
def vendor_download_file_zip(active_only: bool = True, limit: int = 0):
    return vendor_download_zip(active_only=active_only, limit=limit)


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
