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

# app 디렉터리를 Python 경로에 추가
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
sys.path.insert(0, APP_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
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
    candidate_table_source: str = "not_exposed_yet"
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


def _get_rag_status() -> dict:
    """ChromaDB 컬렉션 상태를 조회. warmup_rag() 구조를 재사용."""
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
            "production_deployment": PRODUCTION_DEPLOYMENT,
        }
    except Exception as e:
        return {
            "laws": {"status": f"ERROR: {e}", "doc_count": 0},
            "manuals": {"status": f"ERROR: {e}", "doc_count": 0},
            "innovation": {"status": f"ERROR: {e}", "product_count": 0},
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
        )

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


def _chat_legacy(req: ChatRequest, start: float):
    """기존 gemini_engine.chat() 경로 (USE_ORCHESTRATOR_CHAT=false 롤백용)."""
    try:
        from gemini_engine import chat as engine_chat, get_last_generation_meta

        answer, updated_history = engine_chat(
            user_message=req.message,
            history=req.history,
            progress_callback=None,
            agency_type=req.agency_type,
        )
        latency_ms = int((time.time() - start) * 1000)
        meta = get_last_generation_meta()

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
        )

        # ── QA 테스트 로그 자동 저장 ──
        try:
            from qa_test_logger import save_qa_log
            save_qa_log(
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
                },
            )
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


# ─────────────────────────────────────────────
# 직접 실행
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8001"))
    print(f"Starting API server on port {port}...")
    print(f"Production deployment: {PRODUCTION_DEPLOYMENT}")
    uvicorn.run(app, host="0.0.0.0", port=port)
