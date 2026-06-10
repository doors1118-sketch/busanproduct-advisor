"""업체추천 전용 화면."""

from __future__ import annotations

import base64
import html
import os
import re
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "pilot_auth.env")

APP_NAME = "업체추천"
CHATBOT_API_URL = os.getenv("CHATBOT_API_URL", "http://127.0.0.1:8001/chat")
VENDOR_SEARCH_REGION = os.getenv("VENDOR_SEARCH_REGION", "busan")
VENDOR_CARD_DISPLAY_LIMIT = int(os.getenv("VENDOR_CARD_DISPLAY_LIMIT", "12"))


def _api_base_url() -> str:
    return CHATBOT_API_URL.rsplit("/", 1)[0]


def _api_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    auth_user = os.getenv("PILOT_AUTH_USER", "admin")
    auth_pass = os.getenv("PILOT_AUTH_PASSWORD", "pilot123!")
    if auth_user and auth_pass:
        token = base64.b64encode(f"{auth_user}:{auth_pass}".encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {token}"
    return headers


def _search_recommendations(
    query: str,
    limit: int,
    budget_krw: int | None = None,
    *,
    include_product_policy: bool = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "q": query,
        "region": VENDOR_SEARCH_REGION,
        "limit": limit,
        "include_product_policy": "true" if include_product_policy else "false",
    }
    if budget_krw:
        params["budget_krw"] = budget_krw
    response = requests.get(
        f"{_api_base_url()}/vendor-recommendations/search",
        params=params,
        headers=_api_headers(),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _download_query_csv(query: str, limit: int) -> bytes:
    response = requests.get(
        f"{_api_base_url()}/vendors/query.csv",
        params={"q": query, "region": VENDOR_SEARCH_REGION, "limit": limit},
        headers=_api_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.content


@st.cache_data(ttl=60, show_spinner=False)
def _download_full_zip() -> bytes:
    response = requests.get(
        f"{_api_base_url()}/vendors/download.zip",
        params={"active_only": "true"},
        headers=_api_headers(),
        timeout=60,
    )
    response.raise_for_status()
    return response.content


def _render_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f6f8fb; }
        .block-container { max-width: 1320px; padding-top: 1.2rem; }
        .vendor-head {
            border-bottom: 1px solid #d8dee8;
            margin-bottom: 1rem;
            padding-bottom: 0.9rem;
        }
        .vendor-head h1 {
            color: #172033;
            font-size: 1.8rem;
            font-weight: 780;
            margin: 0;
        }
        .vendor-head p {
            color: #667085;
            font-size: 0.95rem;
            margin: 0.35rem 0 0;
        }
        .notice {
            background: #fff8e5;
            border: 1px solid #e7c968;
            border-radius: 8px;
            color: #5c4300;
            font-size: 0.9rem;
            line-height: 1.5;
            margin: 0.8rem 0 1rem;
            padding: 0.75rem 0.85rem;
        }
        .policy-band {
            background: #ffffff;
            border: 1px solid #d8dee8;
            border-radius: 8px;
            margin: 0.75rem 0 1rem;
            padding: 0.95rem 1rem;
        }
        .policy-title {
            color: #172033;
            font-size: 1rem;
            font-weight: 760;
            margin-bottom: 0.3rem;
        }
        .policy-message {
            color: #475467;
            font-size: 0.9rem;
            line-height: 1.45;
            margin-bottom: 0.75rem;
        }
        .policy-grid {
            display: grid;
            gap: 0.65rem;
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .policy-match-table {
            border: 1px solid #e3e8ef;
            border-radius: 7px;
            margin-top: 0.75rem;
            overflow: hidden;
        }
        .policy-match-row {
            display: grid;
            gap: 0;
            grid-template-columns: 1.3fr 2fr 0.9fr 1fr;
        }
        .policy-match-row + .policy-match-row {
            border-top: 1px solid #e3e8ef;
        }
        .policy-match-row span {
            color: #475467;
            font-size: 0.78rem;
            line-height: 1.35;
            overflow-wrap: anywhere;
            padding: 0.55rem 0.65rem;
        }
        .policy-match-row--head span {
            background: #f1f5f9;
            color: #344054;
            font-weight: 760;
        }
        .policy-alt-grid {
            display: grid;
            gap: 0.5rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-top: 0.75rem;
        }
        .policy-alt-card {
            background: #f8fafc;
            border: 1px solid #e3e8ef;
            border-radius: 7px;
            padding: 0.65rem 0.75rem;
        }
        .policy-alt-card strong {
            color: #172033;
            display: block;
            font-size: 0.9rem;
            margin-bottom: 0.25rem;
        }
        .policy-alt-card span {
            color: #475467;
            display: block;
            font-size: 0.78rem;
            line-height: 1.4;
            overflow-wrap: anywhere;
        }
        .policy-cell {
            background: #f8fafc;
            border: 1px solid #e3e8ef;
            border-radius: 7px;
            min-height: 74px;
            padding: 0.65rem 0.75rem;
        }
        .policy-cell span,
        .candidate-field span {
            color: #667085;
            display: block;
            font-size: 0.75rem;
            font-weight: 650;
            margin-bottom: 0.22rem;
        }
        .policy-cell strong,
        .candidate-field strong {
            color: #172033;
            display: block;
            font-size: 0.9rem;
            font-weight: 680;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }
        .candidate-card {
            background: #ffffff;
            border: 1px solid #d8dee8;
            border-radius: 8px;
            margin: 0.72rem 0;
            padding: 0.9rem 1rem;
        }
        .candidate-top {
            align-items: flex-start;
            display: flex;
            gap: 0.8rem;
            justify-content: space-between;
        }
        .candidate-title {
            align-items: center;
            display: flex;
            gap: 0.55rem;
            min-width: 0;
        }
        .candidate-rank {
            align-items: center;
            background: #172033;
            border-radius: 999px;
            color: #ffffff;
            display: inline-flex;
            flex: 0 0 auto;
            font-size: 0.76rem;
            font-weight: 760;
            height: 1.8rem;
            justify-content: center;
            width: 1.8rem;
        }
        .candidate-name {
            color: #172033;
            font-size: 1.05rem;
            font-weight: 760;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        .candidate-meta {
            color: #667085;
            font-size: 0.82rem;
            line-height: 1.35;
            margin-top: 0.18rem;
            overflow-wrap: anywhere;
        }
        .candidate-score {
            color: #344054;
            flex: 0 0 auto;
            font-size: 0.78rem;
            font-weight: 700;
            text-align: right;
        }
        .candidate-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin: 0.72rem 0 0.5rem;
        }
        .vendor-badge {
            border-radius: 999px;
            display: inline-flex;
            font-size: 0.76rem;
            font-weight: 700;
            line-height: 1;
            padding: 0.36rem 0.5rem;
        }
        .vendor-badge--ok {
            background: #e8f5ee;
            color: #126b3a;
        }
        .vendor-badge--warn {
            background: #fff4d6;
            color: #8a5a00;
        }
        .vendor-badge--info {
            background: #e9f2ff;
            color: #175cd3;
        }
        .vendor-badge--neutral {
            background: #eef2f6;
            color: #475467;
        }
        .candidate-grid {
            display: grid;
            gap: 0.55rem;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin-top: 0.55rem;
        }
        .candidate-field {
            background: #f8fafc;
            border: 1px solid #e3e8ef;
            border-radius: 7px;
            padding: 0.6rem 0.7rem;
        }
        .candidate-note {
            border-top: 1px solid #e3e8ef;
            color: #475467;
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: 0.75rem;
            padding-top: 0.65rem;
            overflow-wrap: anywhere;
        }
        @media (max-width: 900px) {
            .policy-grid,
            .policy-alt-grid,
            .candidate-grid {
                grid-template-columns: 1fr;
            }
            .policy-match-row {
                grid-template-columns: 1fr;
            }
            .candidate-top {
                display: block;
            }
            .candidate-score {
                margin-top: 0.4rem;
                text-align: left;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _safe_page_link(page: str, label: str) -> None:
    try:
        st.page_link(page, label=label)
    except Exception:
        st.markdown(f"**{html.escape(label)}**")


_EMPTY_TEXTS = {"", "-", "없음", "정보 없음", "미확인", "확인 필요", "none", "null", "nan"}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = [f"{k}: {v}" for k, v in value.items() if v not in (None, "")]
        return " | ".join(parts)
    if isinstance(value, (list, tuple, set)):
        return " | ".join(_clean_text(item) for item in value if _clean_text(item))
    return re.sub(r"\s+", " ", str(value).strip())


def _split_values(value: Any) -> list[str]:
    text = _clean_text(value)
    if not text or text.lower() in _EMPTY_TEXTS:
        return []
    text = text.replace("\r", "\n").replace("^^", "|")
    raw_parts = re.split(r"\s*(?:\||\n|,|;|ㆍ|·)\s*", text)
    parts: list[str] = []
    seen: set[str] = set()
    for raw in raw_parts:
        part = _clean_text(raw)
        if not part or part.lower() in _EMPTY_TEXTS or part in seen:
            continue
        parts.append(part)
        seen.add(part)
    return parts


def _preview(value: Any, *, limit: int = 3, fallback: str = "-") -> str:
    parts = _split_values(value)
    if not parts:
        return fallback
    shown = parts[:limit]
    suffix = f" 외 {len(parts) - limit}건" if len(parts) > limit else ""
    return ", ".join(shown) + suffix


def _escape(value: Any) -> str:
    return html.escape(_clean_text(value), quote=True)


def _is_present(value: Any) -> bool:
    text = _clean_text(value)
    if not text or text.lower() in _EMPTY_TEXTS:
        return False
    lowered = text.lower()
    negative_tokens = ("없음", "미매칭", "확인 필요", "정보 없음", "false", "비대상", "not_found")
    return not any(token in lowered for token in negative_tokens)


def _badge(label: str, tone: str = "neutral") -> str:
    return f'<span class="vendor-badge vendor-badge--{tone}">{html.escape(label)}</span>'


def _candidate_badges(row: dict[str, Any]) -> str:
    badges: list[str] = []
    if _is_present(row.get("matched_query_label")):
        badges.append(_badge(_preview(row.get("matched_query_label"), limit=1), "info"))
    if _is_present(row.get("license_status_label")):
        badges.append(_badge("면허/업종", "ok"))
    if _is_present(row.get("shopping_mall_status_label")):
        badges.append(_badge("종합쇼핑몰", "ok"))
    if _is_present(row.get("mas_status_label")):
        badges.append(_badge("MAS", "ok"))
    if _is_present(row.get("direct_production_certificate_status")):
        badges.append(_badge("직접생산증명서", "warn"))
    if _is_present(row.get("policy_company_labels")):
        badges.append(_badge(_preview(row.get("policy_company_labels"), limit=2), "info"))
    if _is_present(row.get("certified_product_labels")):
        badges.append(_badge("13종 기술개발제품", "info"))
    sme_label = _clean_text(row.get("sme_competition_product_label"))
    if "해당" in sme_label and "미매칭" not in sme_label:
        badges.append(_badge("중기간 경쟁제품", "warn"))
    cooperative_label = _clean_text(row.get("cooperative_purchase_route_label"))
    if "검토 가능" in cooperative_label:
        badges.append(_badge("조합추천/소기업", "warn"))
    return "".join(badges) or _badge("원천자료 확인 필요", "neutral")


def _field(label: str, value: Any, *, limit: int = 3) -> str:
    return (
        '<div class="candidate-field">'
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html.escape(_preview(value, limit=limit))}</strong>"
        "</div>"
    )


def _render_policy_summary(summary: dict[str, Any]) -> None:
    if not summary:
        return
    matched_products = summary.get("matched_products") or []
    matched_names = []
    match_rows = [
        '<div class="policy-match-row policy-match-row--head">'
        "<span>세부품명번호</span><span>세부품명</span><span>중기간</span><span>직생 유효업체</span>"
        "</div>"
    ]
    if isinstance(matched_products, list):
        for item in matched_products[:3]:
            if isinstance(item, dict):
                name = item.get("detail_product_name") or item.get("detail_product_code")
                if name:
                    matched_names.append(_clean_text(name))
                match_rows.append(
                    '<div class="policy-match-row">'
                    f"<span>{_escape(item.get('detail_product_code') or '-')}</span>"
                    f"<span>{_escape(item.get('detail_product_name') or '-')}</span>"
                    f"<span>{_escape(item.get('sme_competition_product') or '확인 필요')}</span>"
                    f"<span>{_escape(item.get('direct_production_valid_supplier_count') or '-')}</span>"
                    "</div>"
                )
    matched_label = ", ".join(matched_names) if matched_names else "세부품명 매칭 없음"
    match_table = ""
    if len(match_rows) > 1:
        match_table = f'<div class="policy-match-table">{"".join(match_rows)}</div>'
    st.markdown(
        f"""
        <div class="policy-band">
            <div class="policy-title">품목 정책 요약</div>
            <div class="policy-message">{_escape(summary.get("message") or "품목검토 결과를 확인하세요.")}</div>
            <div class="policy-grid">
                <div class="policy-cell"><span>중소기업자간 경쟁제품</span><strong>{_escape(summary.get("sme_competition_product") or "확인 필요")}</strong></div>
                <div class="policy-cell"><span>직접생산증명서</span><strong>{_escape(summary.get("direct_production_certificate") or "확인 필요")}</strong></div>
                <div class="policy-cell"><span>조합추천/소기업</span><strong>{_escape(summary.get("cooperative_purchase_route") or "확인 필요")}</strong></div>
                <div class="policy-cell"><span>매칭 세부품명</span><strong>{html.escape(matched_label)}</strong></div>
            </div>
            {match_table}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_policy_preference_summary(summary: dict[str, Any]) -> None:
    if not summary or summary.get("status") == "not_requested":
        return
    requested = summary.get("requested") or []
    labels = []
    if isinstance(requested, list):
        labels = [str(item.get("label") or "") for item in requested if isinstance(item, dict) and item.get("label")]
    title = "정책기업 조건 확인"
    if labels:
        title = f"정책기업 조건 확인: {', '.join(labels)}"
    alternatives = summary.get("alternatives") or []
    alternative_cards = []
    if isinstance(alternatives, list):
        for item in alternatives[:6]:
            if not isinstance(item, dict):
                continue
            meta = " / ".join(part for part in [
                _preview(item.get("policy_labels"), limit=2),
                _clean_text(item.get("location")),
                _clean_text(item.get("representative_product")),
                _clean_text(item.get("industry")),
            ] if part and part != "-")
            matched = _preview(item.get("matched_terms"), limit=3)
            alternative_cards.append(
                '<div class="policy-alt-card">'
                f"<strong>{_escape(item.get('company_name') or '업체명 확인 필요')}</strong>"
                f"<span>{html.escape(meta or '정책기업 보조 DB 후보')}</span>"
                f"<span>매칭어: {html.escape(matched)}</span>"
                "</div>"
            )
    alternative_html = ""
    if alternative_cards:
        alternative_html = f'<div class="policy-alt-grid">{"".join(alternative_cards)}</div>'
    st.markdown(
        f"""
        <div class="policy-band">
            <div class="policy-title">{html.escape(title)}</div>
            <div class="policy-message">{_escape(summary.get("message") or "정책기업 조건을 별도로 확인하세요.")}</div>
            {alternative_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_candidate_card(row: dict[str, Any], rank: int) -> None:
    company_name = _clean_text(row.get("company_name")) or "업체명 확인 필요"
    location = _clean_text(row.get("location")) or "소재지 확인 필요"
    review_score = _clean_text(row.get("review_score"))
    score_label = f"검토점수 {html.escape(review_score)}" if review_score else "검토점수 -"
    contract_types = _preview(row.get("contract_review_types"), limit=3)
    note_parts = [
        f"검토유형: {contract_types}",
        f"예산: {_preview(row.get('budget_review_hint'), limit=2)}",
        f"확인사항: {_preview(row.get('recommended_checks'), limit=3)}",
    ]
    st.markdown(
        f"""
        <div class="candidate-card">
            <div class="candidate-top">
                <div>
                    <div class="candidate-title">
                        <span class="candidate-rank">{rank}</span>
                        <div>
                            <div class="candidate-name">{html.escape(company_name)}</div>
                            <div class="candidate-meta">{html.escape(location)}</div>
                        </div>
                    </div>
                </div>
                <div class="candidate-score">{score_label}</div>
            </div>
            <div class="candidate-badges">{_candidate_badges(row)}</div>
            <div class="candidate-grid">
                {_field("대표품목", row.get("main_products"), limit=3)}
                {_field("면허/업종", row.get("license_or_business_type"), limit=3)}
                {_field("종합쇼핑몰 등록품목", row.get("shopping_mall_product_summary"), limit=2)}
                {_field("MAS 등록품목", row.get("mas_product_summary"), limit=2)}
                {_field("직접생산증명서", row.get("direct_production_certificate_products") or row.get("direct_production_certificate_status"), limit=2)}
                {_field("정책기업", row.get("policy_company_labels"), limit=2)}
                {_field("13종 기술개발제품", row.get("certified_product_labels"), limit=2)}
                {_field("중기간 경쟁제품", row.get("sme_competition_product_label"), limit=2)}
                {_field("조합추천/소기업", row.get("cooperative_purchase_route_label"), limit=2)}
                {_field("검색매칭", row.get("matched_query_label") or row.get("matched_source"), limit=2)}
            </div>
            <div class="candidate-note">{html.escape(" / ".join(note_parts))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _candidate_preview_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    columns = [
        ("업체명", "company_name"),
        ("소재지", "location"),
        ("검토유형", "contract_review_types"),
        ("예산 검토 힌트", "budget_review_hint"),
        ("면허보유", "license_status_label"),
        ("면허/업종", "license_or_business_type"),
        ("주요품목", "main_products"),
        ("종합쇼핑몰", "shopping_mall_status_label"),
        ("종합쇼핑몰 등록품목", "shopping_mall_product_summary"),
        ("MAS", "mas_status_label"),
        ("MAS 등록품목", "mas_product_summary"),
        ("직접생산증명서", "direct_production_certificate_status"),
        ("직접생산증명서 품목", "direct_production_certificate_products"),
        ("13종 기술개발제품", "certified_product_labels"),
        ("기술개발제품 상세", "certified_product_summary"),
        ("정책기업", "policy_company_labels"),
        ("중기간경쟁제품", "sme_competition_product_label"),
        ("조합추천/소기업", "cooperative_purchase_route_label"),
        ("확인사항", "recommended_checks"),
        ("검색매칭", "matched_query_label"),
        ("점수", "review_score"),
    ]
    return [{label: row.get(key, "") for label, key in columns} for row in rows]


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")
    _render_css()

    st.markdown(
        """
        <div class="vendor-head">
            <h1>업체추천</h1>
            <p>품목·면허·업종과 예산을 기준으로 부산 지역 계약 검토 후보를 빠르게 조회합니다. 계약방법 확정은 별도 계약검토 서비스에서 처리합니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="notice">
        이 화면은 계약 가능 확정이 아니라 계약 검토 후보를 찾는 기능입니다. 공고 전 면허, 직접생산증명서, MAS/쇼핑몰 계약상태, 인증 유효성, 영업상태를 원천 자료로 다시 확인해야 합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        _safe_page_link("🏠_홈.py", "홈")
        _safe_page_link("pages/💬_법령챗봇.py", "계약검토")
        _safe_page_link("pages/vendor_search.py", "업체추천")
        st.divider()
        st.caption("검색 예시")
        for sample in ["LED", "CCTV", "조경식재공사업", "행사", "경비"]:
            if st.button(sample, use_container_width=True):
                st.session_state.vendor_search_query = sample
                st.rerun()

    default_query = st.session_state.get("vendor_search_query", "LED")
    with st.form("vendor_recommendation_form"):
        col_q, col_budget, col_limit, col_policy, col_submit = st.columns([4, 1.8, 1.2, 1.4, 1.2])
        with col_q:
            query = st.text_input("검색어", value=default_query, placeholder="품목, 면허, 업종, 업체명")
        with col_budget:
            budget_manwon = st.number_input("예산(만원)", min_value=0, max_value=100_000, value=0, step=100)
        with col_limit:
            limit = st.number_input("표시 건수", min_value=5, max_value=100, value=30, step=5)
        with col_policy:
            include_product_policy = st.checkbox("품목검토", value=True)
        with col_submit:
            submitted = st.form_submit_button("검색", use_container_width=True)

    if submitted:
        st.session_state.vendor_search_query = query.strip()
        st.session_state.vendor_budget_manwon = int(budget_manwon)
        budget_krw = int(budget_manwon) * 10_000 if int(budget_manwon) > 0 else None
        try:
            st.session_state.vendor_recommendation_result = _search_recommendations(
                query.strip(),
                int(limit),
                budget_krw,
                include_product_policy=include_product_policy,
            )
        except Exception as exc:
            st.session_state.vendor_recommendation_result = {"error": str(exc), "rows": [], "count": 0}

    result = st.session_state.get("vendor_recommendation_result")
    if not result:
        st.info("검색어를 입력하고 검색을 실행하세요.")
        return

    if result.get("error"):
        st.error(f"업체추천 API 오류: {result['error']}")
        return

    rows = result.get("rows") or []
    search_plan = result.get("search_plan") or []
    item_policy_summary = result.get("item_policy_summary") or {}
    policy_preference_summary = result.get("policy_preference_summary") or {}
    policy_checks = result.get("product_policy_checks") or []

    metric_cols = st.columns(4)
    metric_cols[0].metric("후보 수", result.get("count", len(rows)))
    metric_cols[1].metric("LLM 사용", "아니오" if result.get("llm_used") is False else "확인 필요")
    metric_cols[2].metric("품목검토 매칭", len(policy_checks))
    metric_cols[3].metric("예산", result.get("budget_label", "미입력"))

    if item_policy_summary:
        _render_policy_summary(item_policy_summary)
    if policy_preference_summary:
        _render_policy_preference_summary(policy_preference_summary)

    if rows:
        card_limit = max(1, min(VENDOR_CARD_DISPLAY_LIMIT, len(rows)))
        st.markdown(f"### 업체 후보 상위 {card_limit}건")
        for rank, row in enumerate(rows[:card_limit], start=1):
            _render_candidate_card(row, rank)
        if len(rows) > card_limit:
            st.caption(f"전체 {len(rows)}건 중 상위 {card_limit}건을 카드로 표시했습니다. 나머지는 상세 표에서 확인하세요.")
        with st.expander("전체 상세 표", expanded=False):
            st.dataframe(_candidate_preview_rows(rows), use_container_width=True, hide_index=True)
    else:
        st.warning("검색 결과가 없습니다. DB에 등록된 품목명 또는 면허명으로 다시 검색하세요.")

    if search_plan:
        with st.expander("검색 확장 계획", expanded=False):
            st.dataframe(search_plan, use_container_width=True, hide_index=True)

    if policy_checks:
        with st.expander("품목검토 상세", expanded=True):
            st.dataframe(policy_checks, use_container_width=True, hide_index=True)

    down_cols = st.columns(2)
    with down_cols[0]:
        if query.strip():
            try:
                st.download_button(
                    "검색 CSV 다운로드",
                    data=_download_query_csv(query.strip(), int(limit)),
                    file_name=f"업체추천_{query.strip()}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            except Exception:
                st.caption("검색 CSV를 준비하지 못했습니다.")
    with down_cols[1]:
        try:
            st.download_button(
                "전체 업체 ZIP 다운로드",
                data=_download_full_zip(),
                file_name="부산업체_전체.zip",
                mime="application/zip",
                use_container_width=True,
            )
        except Exception:
            st.caption("전체 ZIP을 준비하지 못했습니다.")


if __name__ == "__main__":
    main()
