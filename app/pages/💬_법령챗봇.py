"""지역상품 구매확대 지원 챗봇."""

from __future__ import annotations

import base64
import html
import os
import re
from urllib.parse import urlencode
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
SAMPLE_QUESTIONS = [
    "예산이 4천만원인데, 컴퓨터 구매 절차 알려줘",
    "조경공사를 부산업체 중심으로 발주하려면 지역제한, 면허요건, 업체 추천을 어떻게 설계해야 해?",
    "1억원으로 학교 운동장 천연잔디 조성공사를 하려고 하는데 계약방법, 면허요건, 부산업체 후보를 알려줘",
    "청사 경비용역을 부산업체 중심으로 검토하려면 지역제한과 면허를 어떻게 봐야 해?",
    "발대식 행사 용역 예산 2억원으로 사업 추진하고 싶어. 계약 방법 안내해줘.",
    "노트북 4천5백만원 구매하려고 한다. 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?",
]

AGENCY_TYPES: dict[str, str | None] = {
    "기관 유형 선택": None,
    "지방자치단체": "지방자치단체",
    "지방 공사공단 및 출자출연기관": "출자출연기관",
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
        "chat_started": False,
        "pending_question": None,
        "pending_original_question": None,
        "query_question_processed": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_chat() -> None:
    st.session_state.messages = []
    st.session_state.chat_history = []
    st.session_state.chat_started = False
    st.session_state.pending_question = None
    st.session_state.pending_original_question = None
    st.session_state.query_question_processed = None
    _clear_route_params()


def _agency_label(value: str | None) -> str:
    if not value:
        return "미선택"
    return AGENCY_LABEL_BY_VALUE.get(value, value)


def _set_agency(value: str | None) -> None:
    st.session_state.agency_value = value


def _get_query_param(name: str) -> str | None:
    try:
        value = st.query_params.get(name)
    except Exception:
        value = st.experimental_get_query_params().get(name)
    if isinstance(value, list):
        return str(value[0]) if value else None
    if value is None:
        return None
    return str(value)


def _clear_route_params() -> None:
    try:
        st.query_params.clear()
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            return


def _chat_route_url(question: str | None = None) -> str:
    params: dict[str, str] = {"mode": "chat"}
    if question:
        params["question"] = question
    if st.session_state.get("agency_value"):
        params["agency"] = st.session_state.agency_value
    return f"?{urlencode(params)}"


def _sync_route_from_query() -> None:
    mode = _get_query_param("mode")
    if mode != "chat":
        return

    st.session_state.chat_started = True
    agency = _get_query_param("agency")
    if agency in AGENCY_LABEL_BY_VALUE:
        st.session_state.agency_value = agency

    question = _get_query_param("question")
    if question and st.session_state.query_question_processed != question:
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.session_state.pending_original_question = None
        st.session_state.pending_question = question
        st.session_state.query_question_processed = question


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

        [data-testid="stHeader"] {
            display: none;
            height: 0;
        }

        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
            display: none;
        }

        [data-testid="stBottomBlockContainer"] {
            background: #f6f8fb;
            border-top: 1px solid #d8dee8;
            box-shadow: 0 -12px 28px rgba(23, 32, 51, 0.06);
            padding-top: 0.8rem;
        }

        [data-testid="stChatInput"] {
            background: transparent;
        }

        [data-testid="stChatInput"] > div {
            background: #ffffff;
            border: 1px solid #d8dee8;
            border-radius: 12px;
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.07);
        }

        html, body, button, input, textarea, select {
            font-family: "Pretendard", "Noto Sans KR", "Segoe UI", "Malgun Gothic", sans-serif;
            letter-spacing: 0;
        }

        .block-container {
            max-width: 1120px;
            padding-top: 1.05rem !important;
            padding-bottom: 2.5rem;
        }

        [data-testid="stSidebar"] {
            background: rgba(255,255,255,0.88);
            border-right: 1px solid var(--line);
        }

        .topbar {
            align-items: center;
            border-bottom: 1px solid var(--line);
            display: grid;
            gap: 1rem;
            grid-template-columns: minmax(10rem, 1fr) auto minmax(10rem, 1fr);
            margin-bottom: 1rem;
            margin-top: 0;
            overflow: visible;
            padding-bottom: 1rem;
            padding-top: 0.15rem;
        }

        .title-block {
            grid-column: 2;
            text-align: center;
        }

        .title-block h1 {
            color: var(--ink);
            align-items: center;
            display: flex;
            font-size: 1.72rem;
            font-weight: 780;
            justify-content: center;
            letter-spacing: 0;
            line-height: 1.38;
            margin: 0;
            min-height: 2.55rem;
            padding-top: 0.05rem;
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
            grid-column: 3;
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
            margin-top: 0.25rem;
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

        .sample-link {
            align-items: center;
            border: 1px solid var(--line);
            border-radius: 7px;
            color: var(--ink);
            display: flex;
            font-size: 0.96rem;
            font-weight: 650;
            justify-content: center;
            line-height: 1.45;
            margin-top: 0.55rem;
            min-height: 2.55rem;
            padding: 0.55rem 0.85rem;
            text-align: center;
            text-decoration: none !important;
            transition: background 160ms ease, border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
            width: 100%;
        }

        .sample-link:hover {
            border-color: #b8c3d3;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
            color: var(--ink);
            transform: translateY(-1px);
        }

        .sample-link-secondary {
            background: #ffffff;
        }

        .landing-hero {
            background:
                linear-gradient(135deg, rgba(7, 13, 27, 0.96), rgba(18, 32, 56, 0.94)),
                repeating-linear-gradient(90deg, rgba(255,255,255,0.05) 0 1px, transparent 1px 72px);
            border: 1px solid rgba(118, 145, 184, 0.34);
            border-radius: 12px;
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.18);
            color: #ffffff;
            margin: 0.35rem 0 1rem;
            min-height: 19rem;
            overflow: hidden;
            padding: 3.2rem 2rem 2.35rem;
            position: relative;
            text-align: center;
        }

        .landing-hero::after {
            background: linear-gradient(90deg, transparent, rgba(78, 132, 255, 0.24), transparent);
            content: "";
            height: 1px;
            left: 8%;
            position: absolute;
            right: 8%;
            top: 1.4rem;
        }

        .landing-kicker {
            background: rgba(31, 122, 110, 0.18);
            border: 1px solid rgba(99, 210, 190, 0.32);
            border-radius: 999px;
            color: #b9f5e9;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 650;
            margin-bottom: 1rem;
            padding: 0.34rem 0.72rem;
        }

        .landing-hero h1 {
            color: #ffffff;
            font-size: 2.72rem;
            font-weight: 820;
            letter-spacing: 0;
            line-height: 1.18;
            margin: 0;
        }

        .landing-hero p {
            color: #c8d3e4;
            font-size: 1rem;
            line-height: 1.65;
            margin: 1rem auto 1.35rem;
            max-width: 42rem;
        }

        .landing-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            justify-content: center;
        }

        .landing-meta span {
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 999px;
            color: #eef5ff;
            font-size: 0.82rem;
            padding: 0.42rem 0.76rem;
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

        @keyframes message-in {
            from {
                opacity: 0;
                transform: translateY(6px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        div[data-testid="stChatMessage"] {
            background: rgba(255,255,255,0.86);
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.04);
            margin-bottom: 0.75rem;
            max-width: 92%;
            padding: 0.1rem;
            animation: message-in 180ms ease-out both;
        }

        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]),
        div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]),
        div[data-testid="stChatMessage"]:has([aria-label="assistant avatar"]) {
            background: #eaf4ff;
            border-color: #b8d9ff;
            box-shadow: 0 12px 26px rgba(36, 95, 199, 0.08);
            margin-right: auto;
        }

        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
        div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]),
        div[data-testid="stChatMessage"]:has([aria-label="user avatar"]) {
            background: #eaf8ef;
            border-color: #b9e3c7;
            box-shadow: 0 12px 26px rgba(8, 127, 122, 0.08);
            margin-left: auto;
            max-width: 78%;
        }

        div[data-testid="stChatMessage"] [data-testid*="Avatar"] {
            flex-shrink: 0;
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
            background: #ffffff !important;
            border: 1px solid var(--line) !important;
            border-radius: 7px;
            color: var(--ink) !important;
            min-height: 2.35rem;
            text-align: left;
            white-space: normal;
        }

        .stButton > button p {
            color: inherit !important;
        }

        .stButton > button[kind="primary"] {
            background: #ff464b !important;
            border-color: #ff464b !important;
            color: #ffffff !important;
            justify-content: center;
            text-align: center;
        }

        .stButton > button[kind="secondary"]:hover {
            background: #f8fafc !important;
            border-color: #b8c3d3 !important;
            color: var(--ink) !important;
        }

        .stDownloadButton > button {
            background: #ffffff !important;
            border: 1px solid #b8c3d3 !important;
            color: #1f2937 !important;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
            justify-content: center;
            text-align: center;
        }

        .stDownloadButton > button:hover {
            background: #f8fafc !important;
            border-color: #3182f6 !important;
            color: #0f4fbf !important;
        }

        .stDownloadButton > button p {
            color: inherit !important;
        }

        [data-testid="stSidebar"] .stButton > button {
            background: #2f303b !important;
            border-color: #2f303b !important;
            color: #ffffff !important;
            justify-content: center;
            text-align: center;
        }

        .stTextArea textarea,
        .stTextInput input,
        [data-baseweb="select"] {
            border-radius: 7px;
        }

        @media (max-width: 800px) {
            .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }
            .topbar {
                display: flex;
                flex-direction: column;
                gap: 0.65rem;
            }
            .status-strip {
                justify-content: center;
                width: 100%;
            }
            .title-block h1 {
                font-size: 1.38rem;
            }
            .landing-hero {
                min-height: auto;
                padding: 2.2rem 1rem 1.55rem;
            }
            .landing-hero h1 {
                font-size: 1.86rem;
            }
            .notice,
            .starter,
            div[data-testid="stChatMessage"] {
                max-width: 100%;
            }
            div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
            div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]),
            div[data-testid="stChatMessage"]:has([aria-label="user avatar"]) {
                max-width: 100%;
            }
            [data-testid="stBottomBlockContainer"] {
                padding-left: 0.55rem;
                padding-right: 0.55rem;
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
                <p>기관 구매 및 계약 담당자를 위한 지능형 업무 메뉴얼</p>
            </div>
            <div class="status-strip">
                <span class="chip">기관 유형 <strong>{_agency_label(st.session_state.agency_value)}</strong></span>
                <span class="chip">대화 <strong>{len(st.session_state.messages)}건</strong></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_landing() -> None:
    st.markdown(
        f"""
        <section class="landing-hero">
            <div class="landing-kicker">계약·조달 판단 지원 콘솔</div>
            <h1>{APP_NAME}</h1>
            <p>기관 구매 및 계약 담당자를 위한 지능형 업무 매뉴얼입니다. 기관 유형을 선택하고 예시 질문을 누르거나, 하단 입력창에 실제 검토 사안을 입력하세요.</p>
            <div class="landing-meta">
                <span>수의계약·입찰 경로 검토</span>
                <span>부산업체 후보 탐색</span>
                <span>면허·지역제한 체크</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    _render_starter()


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
            <div class="starter-caption">업무 유형별 예시를 선택하거나, 실제 업무 질문을 자유롭게 입력하세요.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for question in SAMPLE_QUESTIONS:
        link_class = "sample-link-secondary"
        st.markdown(
            f'<a class="sample-link {link_class}" href="{html.escape(_chat_route_url(question), quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(question)}</a>',
            unsafe_allow_html=True,
        )


def _render_agency_notice() -> None:
    if st.session_state.agency_value:
        return
    st.markdown(
        """
        <div class="notice">
        기관 유형이 아직 선택되지 않았습니다. 왼쪽 패널에서 선택하거나 채팅창에 1 지방자치단체, 2 지방 공사공단 및 출자출연기관, 3 국가기관, 4 공기업·준정부기관 중 하나를 입력해 주세요.
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


def _agency_number_from_input(user_input: str) -> str | None:
    compact = re.sub(r"\s+", "", user_input or "")
    if not compact:
        return None

    direct = compact.replace("번", "").replace("호", "")
    if direct in AGENCY_NUMBER_MAP:
        return direct

    normalized = compact
    for token in (
        "대화입력창",
        "대화입력",
        "입력창",
        "기관유형",
        "기관",
        "유형",
        "선택",
        "번호",
        "번",
        "호",
        ":",
        "：",
    ):
        normalized = normalized.replace(token, "")

    if normalized in AGENCY_NUMBER_MAP:
        return normalized
    return None


def _handle_agency_number_input(user_input: str) -> bool:
    agency_number = _agency_number_from_input(user_input)
    if agency_number not in AGENCY_NUMBER_MAP:
        return False
    selected = AGENCY_NUMBER_MAP[agency_number]
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
| 2 | 지방 공사공단 및 출자출연기관 | 자체 규정 및 지방계약법 준용 여부 확인 |
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
    st.session_state.chat_started = True
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
    _sync_route_from_query()
    _render_css()
    _render_sidebar()

    pending_question = st.session_state.pop("pending_question", None)
    if pending_question:
        _process_input(pending_question)
        st.rerun()

    if st.session_state.agency_value and st.session_state.get("pending_original_question"):
        st.session_state.chat_started = True
        pending_original_question = st.session_state.pop("pending_original_question")
        _answer_question(pending_original_question)
        st.rerun()

    if st.session_state.chat_started or st.session_state.messages:
        _render_header()
        _render_messages()
    else:
        _render_landing()

    user_input = st.chat_input("계약·조달 검토 질문을 입력하세요")
    if user_input:
        _process_input(user_input)
        st.rerun()


if __name__ == "__main__":
    main()
