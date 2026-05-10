"""
💬 법령챗봇 — AI 법령 해석 상담
지역상생 조달 어드바이저의 핵심 기능 2.
"""
import os
import sys
import base64

# app 디렉토리를 Python 경로에 추가
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)

import streamlit as st
from dotenv import load_dotenv

# .env 파일 및 pilot_auth.env 파일 로드
PROJECT_ROOT = os.path.dirname(APP_DIR)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
load_dotenv(os.path.join(PROJECT_ROOT, "pilot_auth.env"))
# 운영 환경 대비 절대 경로 체크
if os.path.exists("/root/advisor/pilot_auth.env"):
    load_dotenv("/root/advisor/pilot_auth.env")

import requests

from system_prompt import EXAMPLE_QUESTIONS


def _feedback_api_url() -> str:
    api_url = os.getenv("CHATBOT_API_URL", "http://127.0.0.1:8001/chat")
    return api_url.rsplit("/", 1)[0] + "/qa-feedback"


def _routing_health_api_url() -> str:
    api_url = os.getenv("CHATBOT_API_URL", "http://127.0.0.1:8001/chat")
    return api_url.rsplit("/", 1)[0] + "/admin/health/routing"


def _api_headers() -> dict:
    headers = {}
    admin_token = os.getenv("ADMIN_HEALTH_TOKEN", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    auth_user = os.getenv("PILOT_AUTH_USER", "admin")
    auth_pass = os.getenv("PILOT_AUTH_PASSWORD", "pilot123!")
    if auth_user and auth_pass:
        token = base64.b64encode(f"{auth_user}:{auth_pass}".encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {token}"
    return headers


def _load_routing_health() -> dict:
    response = requests.get(
        _routing_health_api_url(),
        headers=_api_headers(),
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def _submit_feedback(qa_log_id: str, rating: int, satisfied: bool, issue_tags: list[str], comment: str):
    payload = {
        "qa_log_id": qa_log_id,
        "rating": rating,
        "satisfied": satisfied,
        "issue_tags": issue_tags,
        "comment": comment,
        "source": "streamlit_user",
    }
    headers = _api_headers()
    response = requests.post(_feedback_api_url(), json=payload, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()

# ── 스타일 ──
st.markdown("""
<style>
    /* 메인 영역 좌우 여백 축소 */
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }
    .chat-header {
        font-size: 1.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1e3a5f 0%, #2e86de 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .chat-sub {
        color: #666;
        font-size: 0.95rem;
        margin-bottom: 1rem;
    }
    /* 예시 질문 버튼 크기 통일 */
    .stButton > button {
        min-height: 3.2rem !important;
        height: auto !important;
        white-space: normal !important;
        line-height: 1.3 !important;
    }
    .disclaimer {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.85rem;
        color: #856404;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 ──
AGENCY_TYPES = {
    "미지정 (소속기관 선택)": None,
    "지방자치단체 (부산시·구·군·교육청)": "지방자치단체",
    "부산시 출자출연기관 (도시공사·교통공사 등)": "출자출연기관",
    "국가기관 (중앙부처·소속기관)": "국가기관",
    "국가 공기업·준정부기관": "공기업/준정부기관",
}

# 번호 입력 → agency_type 매핑 (인터랙티브 가이드용)
_AGENCY_NUMBER_MAP = {
    "1": "지방자치단체",
    "2": "출자출연기관",
    "3": "국가기관",
    "4": "공기업/준정부기관",
}

with st.sidebar:
    st.markdown("### 💬 AI 법령 챗봇")
    st.caption("Source Map + Orchestrator 기반")
    st.markdown("---")
    st.markdown("""
    **사용 방법**
    1. 소속기관 유형 선택
    2. 계약·조달 관련 질문 입력
    3. 해당 법령 기준으로 답변
    """)
    st.markdown("---")
    st.markdown("**📌 답변 구조**")
    st.markdown("""
    - 계약 검토 요약
    - 조달경로 검토
    - 지역업체 구매지원 제도 검토
    - 품목 적격성 검토
    - 근거 기반 검토 상태
    - 검토 후보 업체
    - 주의사항
    """)
    st.markdown("---")
    if st.button("🗑️ 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.rerun()

    with st.expander("운영 상태"):
        st.caption("라우팅·RAG·도구루프 상태를 서버에서 점검합니다.")
        if st.button("상태 새로고침", use_container_width=True):
            try:
                st.session_state["_routing_health"] = _load_routing_health()
            except Exception as exc:
                st.session_state["_routing_health_error"] = str(exc)
        if st.session_state.get("_routing_health_error"):
            st.warning(st.session_state.pop("_routing_health_error"))
        health = st.session_state.get("_routing_health")
        if health:
            status = health.get("status", "unknown")
            if status == "ok":
                st.success("라우팅 상태 정상")
            elif status == "warning":
                st.warning("라우팅 상태 주의")
            else:
                st.error("라우팅 상태 위험")
            settings = health.get("settings", {})
            recent = health.get("recent_routing", {})
            intent_rag = health.get("intent_rag", {})
            st.caption(f"commit: {health.get('commit_hash', 'unknown')}")
            c1, c2 = st.columns(2)
            c1.metric("Intent RAG", intent_rag.get("record_count", 0))
            c2.metric("최근 평균 지연", recent.get("avg_latency_ms", 0))
            st.caption(
                "adjudicator "
                f"{'on' if settings.get('llm_adjudicator_enabled') else 'off'} / "
                f"called {recent.get('llm_adjudicator_called_count', 0)} / "
                f"timeout {recent.get('llm_adjudicator_timeout_count', 0)}"
            )

# ── 세션 상태 초기화 ──
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── 메인 헤더 ──
st.markdown('<div class="chat-header">💬 부산광역시 지역경제 상생협력 어드바이저</div>', unsafe_allow_html=True)
st.markdown('<div class="chat-sub">사전 매핑된 Source Map과 내부 검토 규칙을 기준으로 계약·조달 검토 항목을 구조화하여 안내합니다.</div>', unsafe_allow_html=True)

# ── 소속기관 유형 선택 + 대화 초기화 (메인 영역) ──
col_agency, col_reset = st.columns([4, 1])
with col_agency:
    # 번호 입력으로 설정된 override가 있으면 해당 index 사용
    _override = st.session_state.get("_agency_override", None)
    _default_idx = 0
    if _override:
        _keys = list(AGENCY_TYPES.keys())
        for i, (label, val) in enumerate(AGENCY_TYPES.items()):
            if val == _override:
                _default_idx = i
                break
    agency_key = st.selectbox(
        "📋 소속기관 유형",
        options=list(AGENCY_TYPES.keys()),
        index=_default_idx,
    )
    selected_agency = AGENCY_TYPES[agency_key]
with col_reset:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ 대화 초기화", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.session_state.pop("_agency_override", None)
        st.rerun()

# ── 기관 설정 완료 안내 (번호 입력 후 rerun 시) ──
if st.session_state.pop("_agency_just_set", False):
    _set_name = st.session_state.get("_agency_override", "지방자치단체")
    st.success(f"✅ **{_set_name}** 기준으로 설정되었습니다. 이제 질문을 입력해주세요!")

# ── 대화가 없을 때 예시 질문 표시 ──
if not st.session_state.messages:
    st.markdown("#### 💡 이런 질문을 해보세요")
    cols = st.columns(min(len(EXAMPLE_QUESTIONS), 3))
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        col_idx = i % 3
        with cols[col_idx]:
            if st.button(q, key=f"example_{i}", use_container_width=True):
                st.session_state.pending_question = q
                st.rerun()

# ── 기존 대화 표시 ──
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "⚖️"):
        st.markdown(msg["content"])
        qa_log_id = msg.get("qa_log_id")
        if msg["role"] == "assistant" and qa_log_id:
            sent_key = f"feedback_sent_{qa_log_id}"
            if st.session_state.get(sent_key):
                st.caption("피드백이 저장되었습니다.")
            else:
                with st.expander("답변 평가"):
                    rating = st.slider("만족도", 1, 5, 4, key=f"rating_{qa_log_id}")
                    issue_tags = st.multiselect(
                        "보완 태그",
                        ["의도틀림", "근거부족", "응답느림", "업체검색오류", "답변너무김", "답변부족", "좋은답변"],
                        key=f"tags_{qa_log_id}",
                    )
                    comment = st.text_area("의견", key=f"comment_{qa_log_id}", height=80)
                    col_ok, col_bad = st.columns(2)
                    with col_ok:
                        if st.button("만족", key=f"sat_{qa_log_id}", use_container_width=True):
                            _submit_feedback(qa_log_id, rating, True, issue_tags, comment)
                            st.session_state[sent_key] = True
                            st.rerun()
                    with col_bad:
                        if st.button("불만족", key=f"unsat_{qa_log_id}", use_container_width=True):
                            _submit_feedback(qa_log_id, rating, False, issue_tags, comment)
                            st.session_state[sent_key] = True
                            st.rerun()

# ── 사용자 입력 처리 ──
user_input = st.chat_input("계약·조달 법령에 대해 질문하세요...")

# 예시 질문 버튼에서 온 입력 처리
if "pending_question" in st.session_state:
    user_input = st.session_state.pending_question
    del st.session_state.pending_question

if user_input:
    # ── [Case B] 기관 미선택 시: 번호 입력 파싱 ──
    if not selected_agency:
        stripped = user_input.strip().replace("번", "").replace("호", "")
        if stripped in _AGENCY_NUMBER_MAP:
            selected_agency = _AGENCY_NUMBER_MAP[stripped]
            st.session_state["_agency_override"] = selected_agency
            # 확인 메시지를 채팅에 추가
            confirm = f"✅ **{selected_agency}** 기준으로 설정되었습니다!"
            st.session_state.messages.append({"role": "assistant", "content": confirm})
            # 원래 질문이 저장되어 있으면 자동 실행
            original_q = st.session_state.pop("_pending_original_question", None)
            if original_q:
                st.session_state.pending_question = original_q
                confirm2 = f"💬 여쭤보신 질문에 대해 답변드리겠습니다..."
                st.session_state.messages.append({"role": "assistant", "content": confirm2})
            st.rerun()
        elif "건너뛰기" in user_input or "기본" in user_input or "부산시" in user_input:
            selected_agency = "지방자치단체"
            st.session_state["_agency_override"] = selected_agency
            confirm = "✅ **부산광역시(지방자치단체)** 기준으로 설정되었습니다!"
            st.session_state.messages.append({"role": "assistant", "content": confirm})
            original_q = st.session_state.pop("_pending_original_question", None)
            if original_q:
                st.session_state.pending_question = original_q
                confirm2 = f"💬 여쭤보신 질문에 대해 답변드리겠습니다..."
                st.session_state.messages.append({"role": "assistant", "content": confirm2})
            st.rerun()

    # ── 사용자 메시지 표시 ──
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(user_input)

    # ── [Case B] 여전히 기관 미선택 → 인터랙티브 가이드 출력 (API 호출 없음) ──
    if not selected_agency:
        # 원래 질문을 저장 (기관 선택 후 자동 실행용)
        st.session_state["_pending_original_question"] = user_input
        guide_msg = """안녕하세요! 🧚‍♀️ 정확한 법령 기준으로 답변드리기 위해 **소속기관 유형**을 먼저 알려주세요.

| 번호 | 기관 유형 | 적용 법령 |
|:---:|---------|----------|
| **1️⃣** | **지방자치단체** | 지방계약법 (부산시, 구청, 교육청) |
| **2️⃣** | **부산시 출자출연기관** | 자체규정 + 지방계약법 준용 (도시공사 등) |
| **3️⃣** | **국가기관** | 국가계약법 (중앙부처, 소속기관) |
| **4️⃣** | **공기업/준정부기관** | 공운법 + 계약사무규칙 |

👆 **번호(1~4)**를 입력하시거나 왼쪽 사이드바에서 선택해 주세요!

_(잘 모르시겠다면 **'1번'** 또는 **'건너뛰기'**를 입력하시면 부산시 기준으로 안내해 드려요.)_"""
        with st.chat_message("assistant", avatar="⚖️"):
            st.markdown(guide_msg)
        st.session_state.messages.append({"role": "assistant", "content": guide_msg})
        st.stop()  # API 호출 없이 여기서 중단

    # ── [Case A] 기관 확정 → 실제 분석 실행 ──
    # 기관 유형은 별도 필드로 전송하므로 원문만 사용합니다.
    chat_input = user_input

    # AI 답변 생성
    with st.chat_message("assistant", avatar="⚖️"):
        status_container = st.status("서버에서 답변을 생성 중입니다...", expanded=True)
        try:
            # FastAPI 서버 호출
            api_url = os.getenv("CHATBOT_API_URL", "http://127.0.0.1:8001/chat")
            payload = {
                "message": chat_input,
                "history": st.session_state.chat_history,
                "agency_type": selected_agency
            }
            
            headers = {}
            auth_user = os.getenv("PILOT_AUTH_USER", "admin")
            auth_pass = os.getenv("PILOT_AUTH_PASSWORD", "pilot123!")
            if auth_user and auth_pass:
                token = base64.b64encode(f"{auth_user}:{auth_pass}".encode("utf-8")).decode("utf-8")
                headers["Authorization"] = f"Basic {token}"
            
            response = requests.post(api_url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            data = response.json()
            
            answer = data.get("answer", "⚠️ 응답을 불러올 수 없습니다.")
            updated_history = data.get("history", st.session_state.chat_history)
            
            status_container.update(label="✅ 답변 완료", state="complete", expanded=False)
            st.session_state.chat_history = updated_history
            
            # 마크다운 렌더링
            st.markdown(answer)
            qa_log_id = data.get("qa_log_id", "")
            st.session_state.messages.append({"role": "assistant", "content": answer, "qa_log_id": qa_log_id})

            if qa_log_id:
                with st.expander("답변 평가"):
                    rating = st.slider("만족도", 1, 5, 4, key=f"rating_{qa_log_id}")
                    issue_tags = st.multiselect(
                        "보완 태그",
                        ["의도틀림", "근거부족", "응답느림", "업체검색오류", "답변너무김", "답변부족", "좋은답변"],
                        key=f"tags_{qa_log_id}",
                    )
                    comment = st.text_area("의견", key=f"comment_{qa_log_id}", height=80)
                    col_ok, col_bad = st.columns(2)
                    with col_ok:
                        if st.button("만족", key=f"sat_{qa_log_id}", use_container_width=True):
                            _submit_feedback(qa_log_id, rating, True, issue_tags, comment)
                            st.session_state[f"feedback_sent_{qa_log_id}"] = True
                            st.rerun()
                    with col_bad:
                        if st.button("불만족", key=f"unsat_{qa_log_id}", use_container_width=True):
                            _submit_feedback(qa_log_id, rating, False, issue_tags, comment)
                            st.session_state[f"feedback_sent_{qa_log_id}"] = True
                            st.rerun()
            
            # 디버그 정보 표시 (운영 환경에서도 테스트 확인용)
            with st.expander("🛠️ 시스템 처리 로그 (검증용)"):
                st.json({
                    "pipeline_mode": data.get("pipeline_mode"),
                    "runtime_status": data.get("runtime_status"),
                    "routing_decision": data.get("routing_decision"),
                    "primary_intent": data.get("primary_intent"),
                    "fallback_applied": data.get("fallback_applied"),
                    "forbidden_phrase_scan_passed": data.get("forbidden_phrase_scan_passed"),
                    "latency_ms": data.get("latency_ms"),
                })
                
        except requests.exceptions.Timeout:
            status_container.update(label="❌ 오류 발생", state="error", expanded=False)
            error_msg = "⏳ **서버 응답 지연**\n\n내부 조회 시간이 오래 걸려 타임아웃이 발생했습니다."
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
        except Exception as e:
            status_container.update(label="❌ 오류 발생", state="error", expanded=False)
            error_msg = f"⚠️ API 서버 통신 오류가 발생했습니다: {str(e)}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})

# ── 면책 고지 ──
if st.session_state.messages:
    st.markdown("""
    <div class="disclaimer">
        ⚖️ <strong>면책 고지</strong>: 본 챗봇의 답변은 참고용이며 법적 효력이 없습니다.
        정확한 판단은 법제 담당 부서와 협의하세요.
    </div>
    """, unsafe_allow_html=True)
