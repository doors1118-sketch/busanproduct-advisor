"""지역상품 구매확대 지원 챗봇."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "pilot_auth.env")


def _load_optional_dotenv(path: str | Path) -> None:
    """Load compatibility env files only when the service user can read them."""
    try:
        env_path = Path(path)
        if env_path.exists():
            load_dotenv(env_path)
    except OSError:
        return


_load_optional_dotenv("/root/advisor/pilot_auth.env")

CHATBOT_API_URL = os.getenv("CHATBOT_API_URL", "http://127.0.0.1:8001/chat")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("CHAT_REQUEST_TIMEOUT", "120"))

APP_NAME = "지역상품 구매확대 지원 챗봇"
SAMPLE_QUESTION = "예산이 4천만원인데, 컴퓨터 구매하고 싶어"

AGENCY_TYPES: dict[str, str | None] = {
    "기관 유형 선택": None,
    "지방자치단체": "지방자치단체",
    "출자·출연기관": "출자출연기관",
    "국가기관": "국가기관",
    "공기업·준정부기관": "공기업/준정부기관",
}

AGENCY_NUMBER_MAP = {
    "1": "지방자치단체",
    "2": "출자출연기관",
    "3": "국가기관",
    "4": "공기업/준정부기관",
}

AGENCY_LABEL_BY_VALUE = {value: label for label, value in AGENCY_TYPES.items() if value}

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")


def _api_base_url() -> str:
    return CHATBOT_API_URL.rsplit("/", 1)[0]


def _feedback_api_url() -> str:
    return f"{_api_base_url()}/qa-feedback"


def _candidate_export_api_url(qa_log_id: str) -> str:
    return f"{_api_base_url()}/qa-logs/{qa_log_id}/candidate-export.xlsx"


def _routing_health_api_url() -> str:
    return f"{_api_base_url()}/admin/health/routing"


def _api_headers(include_json: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if include_json:
        headers["Content-Type"] = "application/json"

    admin_token = os.getenv("ADMIN_HEALTH_TOKEN", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    auth_user = os.getenv("PILOT_AUTH_USER", "admin")
    auth_pass = os.getenv("PILOT_AUTH_PASSWORD", "pilot123!")
    if auth_user and auth_pass:
        token = base64.b64encode(f"{auth_user}:{auth_pass}".encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {token}"
    return headers


@st.cache_data(ttl=45, show_spinner=False)
def _load_routing_health() -> dict[str, Any] | None:
    try:
        response = requests.get(_routing_health_api_url(), headers=_api_headers(), timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _submit_feedback(qa_log_id: str, rating: int, satisfied: bool, issue_tags: list[str], comment: str) -> None:
    payload = {
        "qa_log_id": qa_log_id,
        "rating": rating,
        "satisfied": satisfied,
        "issue_tags": issue_tags,
        "comment": comment,
        "source": "streamlit_user",
    }
    response = requests.post(_feedback_api_url(), json=payload, headers=_api_headers(include_json=True), timeout=10)
    response.raise_for_status()


def _init_state() -> None:
    defaults = {
        "messages": [],
        "chat_history": [],
        "agency_value": None,
        "pending_question": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_chat() -> None:
    st.session_state.messages = []
    st.session_state.chat_history = []
    st.session_state.pending_question = None


def _agency_label(value: str | None) -> str:
    if not value:
        return "미선택"
    return AGENCY_LABEL_BY_VALUE.get(value, value)


def _set_agency(value: str | None) -> None:
    st.session_state.agency_value = value


def _append_message(role: str, content: str, **extra: Any) -> None:
    st.session_state.messages.append({"role": role, "content": content, **extra})


def _remember_history(question: str, answer: str, updated_history: list[dict[str, Any]] | None) -> None:
    if updated_history:
        st.session_state.chat_history = updated_history
        return

    history = list(st.session_state.chat_history)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    st.session_state.chat_history = history[-12:]


def _format_latency(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):,.0f} ms"
    except (TypeError, ValueError):
        return "-"


def _render_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

        :root {
            --ink: #172033;
            --muted: #667085;
            --line: #d8dee8;
            --panel: #ffffff;
            --paper: #f6f8fb;
            --blue: #245fc7;
            --teal: #087f7a;
            --amber: #a05a00;
        }

        .stApp {
            background: #f6f8fb;
            color: var(--ink);
            font-family: "Pretendard", "Noto Sans KR", "Segoe UI", "Malgun Gothic", sans-serif;
        }

        html, body, button, input, textarea, select {
            font-family: "Pretendard", "Noto Sans KR", "Segoe UI", "Malgun Gothic", sans-serif;
            letter-spacing: 0;
        }

        .block-container {
            max-width: 1120px;
            padding-top: 1.15rem;
            padding-bottom: 2.5rem;
        }

        [data-testid="stSidebar"] {
            background: rgba(255,255,255,0.88);
            border-right: 1px solid var(--line);
        }

        .topbar {
            align-items: center;
            border-bottom: 1px solid var(--line);
            display: flex;
            gap: 1rem;
            justify-content: space-between;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
        }

        .title-block h1 {
            color: var(--ink);
            font-size: 1.65rem;
            font-weight: 780;
            letter-spacing: 0;
            line-height: 1.25;
            margin: 0;
        }

        .title-block p {
            color: var(--muted);
            font-size: 0.94rem;
            margin: 0.35rem 0 0;
        }

        .status-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            justify-content: flex-end;
        }

        .chip {
            align-items: center;
            background: rgba(255,255,255,0.9);
            border: 1px solid var(--line);
            border-radius: 999px;
            color: #344054;
            display: inline-flex;
            font-size: 0.82rem;
            min-height: 2rem;
            padding: 0.25rem 0.72rem;
            white-space: nowrap;
        }

        .chip strong {
            color: var(--blue);
            font-weight: 760;
            margin-left: 0.25rem;
        }

        .notice {
            background: rgba(255,248,229,0.92);
            border: 1px solid #e7c968;
            border-radius: 8px;
            color: #5c4300;
            font-size: 0.89rem;
            line-height: 1.5;
            margin: 0.75rem 0 1rem;
            padding: 0.72rem 0.82rem;
        }

        .starter {
            background: rgba(255,255,255,0.76);
            border: 1px solid var(--line);
            border-radius: 8px;
            margin-top: 0.75rem;
            padding: 1rem;
        }

        .starter-title {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 720;
            margin-bottom: 0.25rem;
        }

        .starter-caption {
            color: var(--muted);
            font-size: 0.86rem;
            line-height: 1.45;
            margin-bottom: 0.75rem;
        }

        .sidebar-title {
            color: var(--ink);
            font-size: 1.04rem;
            font-weight: 780;
            line-height: 1.36;
            margin-bottom: 0.28rem;
        }

        .sidebar-caption {
            color: var(--muted);
            font-size: 0.83rem;
            line-height: 1.45;
            margin-bottom: 0.85rem;
        }

        .small-muted {
            color: var(--muted);
            font-size: 0.82rem;
            line-height: 1.45;
        }

        div[data-testid="stChatMessage"] {
            background: rgba(255,255,255,0.86);
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.04);
            margin-bottom: 0.75rem;
            padding: 0.1rem;
        }

        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] {
            color: #202b3c;
            font-size: 0.98rem;
            font-weight: 450;
            letter-spacing: 0;
            line-height: 1.72;
            overflow-wrap: anywhere;
            word-break: keep-all;
        }

        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] p {
            margin-bottom: 0.72rem;
        }

        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] strong {
            color: #111827;
            font-weight: 720;
        }

        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] ul,
        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] ol {
            margin-bottom: 0.75rem;
            padding-left: 1.2rem;
        }

        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] li {
            margin-bottom: 0.28rem;
        }

        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] table {
            border-collapse: separate;
            border-spacing: 0;
            font-size: 0.92rem;
            line-height: 1.55;
            margin: 0.65rem 0 0.85rem;
            width: 100%;
        }

        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] th {
            background: #eef3fb;
            color: #172033;
            font-weight: 720;
        }

        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] th,
        div[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] td {
            border-bottom: 1px solid #e2e8f0;
            padding: 0.55rem 0.62rem;
            vertical-align: top;
        }

        .stButton > button {
            border-radius: 7px;
            min-height: 2.35rem;
            text-align: left;
            white-space: normal;
        }

        .stTextArea textarea,
        .stTextInput input,
        [data-baseweb="select"] {
            border-radius: 7px;
        }

        @media (max-width: 800px) {
            .topbar {
                align-items: flex-start;
                flex-direction: column;
            }
            .status-strip {
                justify-content: flex-start;
            }
            .title-block h1 {
                font-size: 1.38rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown(
        f"""
        <div class="topbar">
            <div class="title-block">
                <h1>{APP_NAME}</h1>
                <p>구매담당자를 위한 계약·조달 판단 보조 화면</p>
            </div>
            <div class="status-strip">
                <span class="chip">기관 유형 <strong>{_agency_label(st.session_state.agency_value)}</strong></span>
                <span class="chip">대화 <strong>{len(st.session_state.messages)}건</strong></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-title">{APP_NAME}</div>
            <div class="sidebar-caption">기관 유형을 맞추면 적용 법령과 계약 기준을 더 안정적으로 선택합니다.</div>
            """,
            unsafe_allow_html=True,
        )

        current_index = 0
        labels = list(AGENCY_TYPES.keys())
        current_value = st.session_state.agency_value
        for index, label in enumerate(labels):
            if AGENCY_TYPES[label] == current_value:
                current_index = index
                break

        selected_label = st.selectbox("기관 유형", labels, index=current_index)
        _set_agency(AGENCY_TYPES[selected_label])

        col_reset, col_health = st.columns(2)
        with col_reset:
            if st.button("새 대화", use_container_width=True):
                _reset_chat()
                st.rerun()
        with col_health:
            if st.button("상태 갱신", use_container_width=True):
                _load_routing_health.clear()
                st.rerun()

        with st.expander("운영 상태", expanded=False):
            health = _load_routing_health()
            if not health:
                st.info("라우팅 상태를 불러오지 못했습니다.")
            else:
                status = health.get("status", "unknown")
                settings = health.get("settings", {})
                recent = health.get("recent_routing", {})
                intent_rag = health.get("intent_rag", {})
                st.metric("상태", status)
                st.metric("Intent RAG", intent_rag.get("record_count", 0))
                st.metric("최근 평균 지연", _format_latency(recent.get("avg_latency_ms")))
                st.caption(f"commit: {health.get('commit_hash', 'unknown')}")
                st.caption(
                    "LLM 판정 "
                    f"{'on' if settings.get('llm_adjudicator_enabled') else 'off'} / "
                    f"호출 {recent.get('llm_adjudicator_called_count', 0)} / "
                    f"타임아웃 {recent.get('llm_adjudicator_timeout_count', 0)}"
                )

        st.markdown(
            """
            <div class="small-muted">
            내부 업무 검토용 답변입니다. 최종 처리 전에는 원문 법령, 행정안전부 예규, 기관 내부 지침을 확인해 주세요.
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_starter() -> None:
    st.markdown(
        """
        <div class="starter">
            <div class="starter-title">예시 질문</div>
            <div class="starter-caption">예시는 하나만 두고, 실제 업무 질문은 자유롭게 입력하세요.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(SAMPLE_QUESTION, key="sample-question", use_container_width=True, type="primary"):
        st.session_state.pending_question = SAMPLE_QUESTION
        st.rerun()


def _render_agency_notice() -> None:
    if st.session_state.agency_value:
        return
    st.markdown(
        """
        <div class="notice">
        기관 유형이 아직 선택되지 않았습니다. 왼쪽 패널에서 선택하거나 채팅창에 1 지방자치단체, 2 출자·출연기관, 3 국가기관, 4 공기업·준정부기관 중 하나를 입력해 주세요.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_feedback(qa_log_id: str) -> None:
    sent_key = f"feedback_sent_{qa_log_id}"
    if st.session_state.get(sent_key):
        st.caption("피드백이 저장되었습니다.")
        return

    with st.expander("답변 평가", expanded=False):
        rating = st.slider("만족도", 1, 5, 4, key=f"rating_{qa_log_id}")
        issue_tags = st.multiselect(
            "보완 태그",
            ["의도틀림", "근거부족", "응답느림", "업체검색오류", "답변너무김", "답변부족", "좋은답변"],
            key=f"tags_{qa_log_id}",
        )
        comment = st.text_area("의견", key=f"comment_{qa_log_id}", height=78)
        col_ok, col_bad = st.columns(2)
        with col_ok:
            if st.button("만족", key=f"sat_{qa_log_id}", use_container_width=True):
                _submit_feedback(qa_log_id, rating, True, issue_tags, comment)
                st.session_state[sent_key] = True
                st.rerun()
        with col_bad:
            if st.button("개선 필요", key=f"unsat_{qa_log_id}", use_container_width=True):
                _submit_feedback(qa_log_id, rating, False, issue_tags, comment)
                st.session_state[sent_key] = True
                st.rerun()


def _render_candidate_export(qa_log_id: str) -> None:
    try:
        response = requests.get(_candidate_export_api_url(qa_log_id), headers=_api_headers(), timeout=30)
        if response.status_code != 200:
            st.caption("전체 후보 엑셀은 현재 준비되지 않았습니다.")
            return
        st.download_button(
            "전체 업체 후보 엑셀 다운로드",
            data=response.content,
            file_name=f"부산업체_후보_{qa_log_id}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception:
        st.caption("전체 후보 엑셀 다운로드를 불러오지 못했습니다.")


def _render_debug(data: dict[str, Any]) -> None:
    debug_payload = {
        "pipeline_mode": data.get("pipeline_mode"),
        "runtime_status": data.get("runtime_status"),
        "routing_decision": data.get("routing_decision"),
        "primary_intent": data.get("primary_intent"),
        "fallback_applied": data.get("fallback_applied"),
        "forbidden_phrase_scan_passed": data.get("forbidden_phrase_scan_passed"),
        "latency_ms": data.get("latency_ms"),
    }
    if not any(value is not None for value in debug_payload.values()):
        return
    with st.expander("처리 세부정보", expanded=False):
        cols = st.columns(3)
        cols[0].metric("의도", data.get("primary_intent") or "-")
        cols[1].metric("응답시간", _format_latency(data.get("latency_ms")))
        cols[2].metric("파이프라인", data.get("pipeline_mode") or "-")
        st.json(debug_payload)


def _render_messages() -> None:
    for message in st.session_state.messages:
        role = message["role"]
        with st.chat_message(role):
            st.markdown(message["content"])
            qa_log_id = message.get("qa_log_id")
            if role == "assistant" and qa_log_id:
                if message.get("candidate_export_available"):
                    _render_candidate_export(qa_log_id)
                _render_feedback(qa_log_id)
                if message.get("debug"):
                    _render_debug(message["debug"])


def _handle_agency_number_input(user_input: str) -> bool:
    stripped = user_input.strip().replace("번", "").replace("호", "")
    if stripped not in AGENCY_NUMBER_MAP:
        return False
    selected = AGENCY_NUMBER_MAP[stripped]
    _set_agency(selected)
    _append_message("assistant", f"{_agency_label(selected)} 기준으로 설정했습니다. 이어서 질문을 처리하겠습니다.")
    if st.session_state.get("pending_original_question"):
        st.session_state.pending_question = st.session_state.pop("pending_original_question")
    return True


def _request_agency_before_answer(question: str) -> None:
    st.session_state.pending_original_question = question
    guide = """정확한 기준 적용을 위해 기관 유형을 먼저 선택해 주세요.

| 번호 | 기관 유형 | 주로 적용되는 계약 체계 |
|:---:|---|---|
| 1 | 지방자치단체 | 지방계약법 |
| 2 | 출자·출연기관 | 자체 규정 및 지방계약법 준용 |
| 3 | 국가기관 | 국가계약법 |
| 4 | 공기업·준정부기관 | 공기업·준정부기관 계약사무규칙 |

왼쪽 패널에서 선택하거나 번호를 입력하면 이어서 답변하겠습니다."""
    _append_message("assistant", guide)


def _call_chat_api(question: str) -> dict[str, Any]:
    payload = {
        "message": question,
        "history": st.session_state.chat_history,
        "agency_type": st.session_state.agency_value,
    }
    response = requests.post(CHATBOT_API_URL, json=payload, headers=_api_headers(include_json=True), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _answer_question(question: str) -> None:
    if not st.session_state.agency_value:
        _request_agency_before_answer(question)
        return

    with st.status("답변 생성 중", expanded=False) as status:
        status.write("질문 의도와 계약 기준을 확인하고 있습니다.")
        data = _call_chat_api(question)
        answer = data.get("answer", "응답을 불러올 수 없습니다.")
        status.update(label="답변 완료", state="complete", expanded=False)

    _remember_history(question, answer, data.get("history"))
    _append_message(
        "assistant",
        answer,
        qa_log_id=data.get("qa_log_id", ""),
        candidate_export_available=data.get("candidate_export_available"),
        debug=data,
    )


def _process_input(user_input: str) -> None:
    if not st.session_state.agency_value and _handle_agency_number_input(user_input):
        return
    _append_message("user", user_input)
    try:
        _answer_question(user_input)
    except requests.exceptions.Timeout:
        _append_message("assistant", "서버 응답이 지연되어 타임아웃이 발생했습니다. 잠시 후 다시 시도해 주세요.")
    except Exception as exc:
        _append_message("assistant", f"API 서버 통신 오류가 발생했습니다: {exc}")


def main() -> None:
    _init_state()
    _render_css()
    _render_sidebar()
    _render_header()
    _render_agency_notice()
    _render_messages()

    if st.session_state.agency_value and st.session_state.get("pending_original_question"):
        pending_original_question = st.session_state.pop("pending_original_question")
        _answer_question(pending_original_question)
        st.rerun()

    if not st.session_state.messages:
        _render_starter()

    pending_question = st.session_state.pop("pending_question", None)
    if pending_question:
        _process_input(pending_question)
        st.rerun()

    user_input = st.chat_input("계약·조달 검토 질문을 입력하세요")
    if user_input:
        _process_input(user_input)
        st.rerun()


if __name__ == "__main__":
    main()
