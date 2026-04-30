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
# Pilot Basic Auth Middleware
# ─────────────────────────────────────────────
@app.middleware("http")
async def pilot_auth_middleware(request: Request, call_next):
    if os.getenv("PILOT_AUTH_ENABLED", "").lower() != "true":
        return await call_next(request)

    path = request.url.path
    protected_paths = ["/ui", "/chat", "/rag/status", "/version"]
    is_protected = any(path.startswith(p) for p in protected_paths)

    if not is_protected:
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")

            expected_user = os.getenv("PILOT_AUTH_USER", "")
            expected_pass = os.getenv("PILOT_AUTH_PASSWORD", "")

            if expected_user and expected_pass:
                if secrets.compare_digest(username, expected_user) and secrets.compare_digest(password, expected_pass):
                    return await call_next(request)
        except Exception:
            pass

    return Response(
        content="Unauthorized",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Pilot Access"'}
    )

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
    tool_call_count: int = 0
    fast_track_applied: bool = False
    deterministic_template_used: bool = False


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


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    start = time.time()

    try:
        from gemini_engine import chat as engine_chat, get_last_generation_meta

        # gemini_engine.chat() 호출
        answer, updated_history = engine_chat(
            user_message=req.message,
            history=req.history,
            progress_callback=None,
            agency_type=req.agency_type,
        )

        latency_ms = int((time.time() - start) * 1000)

        # 실제 generation_meta 읽기
        meta = get_last_generation_meta()

        # RAG status (lightweight)
        rag_summary = {}
        try:
            rag_full = _get_rag_status()
            rag_summary = {
                "laws": rag_full["laws"]["status"],
                "manuals": rag_full["manuals"]["status"],
                "innovation": rag_full["innovation"]["status"],
            }
        except Exception:
            rag_summary = {"laws": "unknown", "manuals": "unknown", "innovation": "unknown"}

        # safety metadata: 실제 값 우선, 없으면 기본값
        candidate_table_source = meta.get("candidate_table_source", "not_available")
        legal_conclusion_allowed = meta.get("legal_conclusion_allowed", False)
        forbidden_remaining = meta.get("forbidden_patterns_remaining_after_rewrite", [])
        final_answer_scanned = meta.get("final_answer_scanned", False)
        model_used = meta.get("model_used", os.getenv("GEMINI_MODEL", "gemini-2.5-pro"))
        model_decision_reason = meta.get("model_decision_reason", "")
        safety_metadata_status = "ACTUAL" if meta else "NOT_EXPOSED"

        resp_obj = ChatResponse(
            answer=answer,
            history=updated_history,
            candidate_table_source=candidate_table_source,
            legal_conclusion_allowed=legal_conclusion_allowed,
            contract_possible_auto_promoted=False,
            forbidden_patterns_remaining_after_rewrite=forbidden_remaining,
            final_answer_scanned=final_answer_scanned,
            sensitive_fields_detected=[],
            model_selected=model_used,
            model_decision_reason=model_decision_reason,
            latency_ms=latency_ms,
            rag_status=rag_summary,
            production_deployment=PRODUCTION_DEPLOYMENT,
            route_guidance_provided=meta.get("route_guidance_provided", False),
            regional_route_guidance_provided=meta.get("regional_route_guidance_provided", False),
            amount_detected=meta.get("amount_detected"),
            amount_band=meta.get("amount_band"),
            candidate_counts_by_type=meta.get("candidate_counts_by_type", {}),
            source_call_statuses=meta.get("source_call_statuses", {}),
            sensitive_fields_removed=meta.get("sensitive_fields_removed", True),
            enrichment_join_key_redacted=meta.get("enrichment_join_key_redacted", True),
            total_latency_ms=latency_ms,
            rag_elapsed_ms=meta.get("rag_elapsed_ms"),
            model_elapsed_ms=meta.get("model_elapsed_ms"),
            rewrite_elapsed_ms=meta.get("rewrite_elapsed_ms"),
            tool_call_count=meta.get("tool_call_count", 0),
            fast_track_applied=meta.get("fast_track_applied", False),
            deterministic_template_used=meta.get("deterministic_template_used", False),
        )
        return JSONResponse(content=resp_obj.dict(), media_type="application/json; charset=utf-8")

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        err_str = str(e)

        # Fail-closed: 외부 API 오류 분류
        if any(kw in err_str for kw in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"]):
            error_msg = "API 사용량 한도 초과 또는 서버 지연. 잠시 후 다시 시도하세요."
            resp_obj = ChatResponse(
                answer=f"⚠️ {error_msg}",
                history=req.history,
                candidate_table_source="none",
                legal_conclusion_allowed=False,
                contract_possible_auto_promoted=False,
                forbidden_patterns_remaining_after_rewrite=[],
                final_answer_scanned=False,
                sensitive_fields_detected=[],
                model_selected="",
                model_decision_reason=f"error: {error_msg}",
                latency_ms=latency_ms,
                rag_status={},
                production_deployment=PRODUCTION_DEPLOYMENT,
                total_latency_ms=latency_ms,
            )
            return JSONResponse(content=resp_obj.dict(), media_type="application/json; charset=utf-8")
        else:
            print(f"[API ERROR] {traceback.format_exc()}")
            error_msg = "내부 서버 오류"
            resp_obj = ChatResponse(
                answer=f"⚠️ {error_msg}",
                history=req.history,
                candidate_table_source="none",
                legal_conclusion_allowed=False,
                contract_possible_auto_promoted=False,
                forbidden_patterns_remaining_after_rewrite=[],
                final_answer_scanned=False,
                sensitive_fields_detected=[],
                model_selected="",
                model_decision_reason=f"error: {error_msg}",
                latency_ms=latency_ms,
                rag_status={},
                production_deployment=PRODUCTION_DEPLOYMENT,
                total_latency_ms=latency_ms,
            )
            return JSONResponse(content=resp_obj.dict(), status_code=500, media_type="application/json; charset=utf-8")


# ─────────────────────────────────────────────
# 직접 실행
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8001"))
    print(f"Starting API server on port {port}...")
    print(f"Production deployment: {PRODUCTION_DEPLOYMENT}")
    uvicorn.run(app, host="0.0.0.0", port=port)
