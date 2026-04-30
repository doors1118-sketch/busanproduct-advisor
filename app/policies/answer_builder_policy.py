"""
답변형식 오케스트레이션 (Phase 5)
Tier별 사용자용 답변 텍스트 구조를 조립하고, MCP 실행 결과를 사용자용 근거표로 렌더링합니다.
렌더링 전용 계층: Gemini/MCP/RAG/DB/후보검색 추가 호출 금지.
"""
import re
import time as _time

# ─── 확인 상태 매핑 ───
_SOURCE_STATUS_MAP = {
    "mcp_preflight_success": "MCP 최신 확인",
    "cache_refreshed_from_mcp": "MCP로 최신 갱신",
    "cached_verified": "캐시된 확인 근거 사용",
    "cached_stale_but_available": "기존 확인 근거 사용, 최신성 재확인 필요",
    "no_mcp_required": "법령조회 불필요",
    "mcp_failed_no_basis": "근거 확인 실패, 법적 판단 유보",
}

# ─── Query 기반 사용자용 근거명 매핑 (순서=우선순위, 먼저 매칭되면 채택) ───
_QUERY_LABEL_MAP = [
    ("지역제한 제한경쟁",     ("지방계약법령 지역제한 기준",         "지역제한 제한경쟁입찰 검토")),
    ("낙찰자 결정기준",       ("행안부 낙찰자 결정기준",            "지역업체 가점·적격심사 검토")),
    ("적격심사 지역업체",     ("행안부 낙찰자 결정기준",            "지역업체 가점·적격심사 검토")),
    ("내자구매업무",          ("조달청 내자구매업무 처리규정",       "조달청 구매 절차 검토")),
    ("다수공급자계약",        ("물품 다수공급자계약 업무처리규정",   "MAS 2단계 경쟁 검토")),
    ("지역상품 우선구매 조례", ("부산시 지역상품 우선구매 조례",     "지역상품 구매정책 근거")),
    ("계약집행기준 수의계약",  ("지방자치단체 계약집행기준 수의계약 요령", "1인 견적·수의계약 절차 검토")),
    ("수의계약 요령",         ("지방자치단체 계약집행기준 수의계약 요령", "1인 견적·수의계약 절차 검토")),
    ("수의계약",              ("지방계약법령 수의계약 기준",         "수의계약 금액 기준 검토")),
    ("제25조",                ("지방계약법령 수의계약 기준",         "수의계약 금액 기준 검토")),
    ("계약집행기준",          ("행안부/조달청 관련 규정",           "계약집행 절차 검토")),
    ("MAS 2단계",             ("물품 다수공급자계약 업무처리규정",   "MAS 2단계 경쟁 검토")),
    ("MAS",                   ("물품 다수공급자계약 업무처리규정",   "MAS 2단계 경쟁 검토")),
    ("지방계약법",            ("지방계약법령 지역제한 기준",         "지역제한 제한경쟁입찰 검토")),
]

# ─── Raw tool name 목록 ───
_RAW_TOOL_NAMES = [
    "chain_law_system", "chain_procedure_detail", "chain_ordinance_compare",
    "chain_full_research", "chain_action_basis", "chain_document_review",
    "search_law", "get_law_text", "search_admin_rule", "get_admin_rule",
    "search_interpretations", "search_decisions", "get_annexes",
    "search_local_company_by_product", "search_local_company_by_license",
    "search_local_company_by_category", "search_shopping_mall",
    "search_innovation_products", "search_tech_development_products",
]

# 캐시 사용 고지문
_CACHE_NOTICE = (
    "\n> ℹ️ 일부 근거는 MCP로 확인된 법령·행정규칙 정보를 캐시로 재사용한 것입니다. "
    "실제 계약 전 최신 법령, 기관 내부 기준, 인증 유효기간은 별도 확인이 필요합니다.\n"
)


def _resolve_query_label(entry: str):
    """entry 전체(tool_name:query (status))에서 query 내용 기반으로 사용자 라벨 결정."""
    for keyword, label_pair in _QUERY_LABEL_MAP:
        if keyword in entry:
            return label_pair
    return None


def _render_legal_basis_table(mandatory_mcp_executed: list, generation_meta: dict) -> tuple:
    """MCP 실행 결과를 사용자용 근거표로 렌더링.
    Returns: (table_text: str, has_cache_hit: bool)
    """
    if not mandatory_mcp_executed:
        return "", False

    overall_status_key = generation_meta.get("source_status", "mcp_preflight_success")
    overall_user_status = _SOURCE_STATUS_MAP.get(overall_status_key, "확인")

    seen_labels = set()
    rows = []
    has_cache_hit = False

    for entry in mandatory_mcp_executed:
        # 개별 행 캐시 상태 판정
        is_cached = "cache_hit" in entry
        if is_cached:
            has_cache_hit = True
            row_status = "캐시된 확인 근거 사용"
        else:
            row_status = overall_user_status

        # Query 내용 기반 라벨 결정
        label_pair = _resolve_query_label(entry)
        if label_pair is None:
            continue

        label, meaning = label_pair
        if label not in seen_labels:
            seen_labels.add(label)
            rows.append(f"| {label} | {row_status} | {meaning} |")

    # MAS 행은 실제 mandatory_mcp_executed에 다수공급자계약 관련 조회가 있을 때만 포함
    # (미조회 근거를 MCP 확인된 것처럼 표시하면 안 됨)

    if not rows:
        return "", False

    header = "| 검토 근거 | 확인 상태 | 실무상 의미 |\n|---|---|---|\n"
    return header + "\n".join(rows) + "\n", has_cache_hit


def strip_raw_tool_names(text: str) -> str:
    """답변 본문에서 raw tool name 패턴을 모두 제거한다."""
    for tool in _RAW_TOOL_NAMES:
        text = re.sub(
            r'[ \t]*[-·•]?\s*[✔️☑]*\s*' + re.escape(tool) + r'[^\n]*\n?',
            '', text
        )
    text = re.sub(
        r'-\s*\*\*사전 조회 근거\*\*:\s*시스템에서 다음의 필수 법령 및 매뉴얼 규정을 사전 조회하여 검토 기준에 반영했습니다\.\s*\n\s*\n',
        '', text
    )
    for tool in _RAW_TOOL_NAMES:
        text = text.replace(tool, "")
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _set_timing(generation_meta: dict, start: float):
    """빌더 성능 메타데이터 기록."""
    generation_meta["answer_builder_elapsed_ms"] = int((_time.time() - start) * 1000)
    generation_meta["answer_builder_network_call_count"] = 0


# ─────────────────────────────────────────────
# Tier 0: 단순 업체 검색
# ─────────────────────────────────────────────
def build_simple_company_search_answer(generation_meta: dict, has_candidates: bool = True) -> str:
    _start = _time.time()
    generation_meta["answer_builder_used"] = "build_simple_company_search_answer"
    generation_meta["answer_sections_rendered"] = [1, 2, 3]
    generation_meta["candidate_section_position"] = 2
    generation_meta["legal_basis_section_rendered"] = False
    generation_meta["user_facing_source_labels_used"] = False
    generation_meta["raw_tool_names_hidden_from_answer"] = True
    generation_meta["source_status_user_label"] = "법령조회 불필요"
    generation_meta["legal_basis_table_rendered"] = False
    generation_meta["legal_basis_to_purchase_route_mapped"] = False

    template = (
        "### 1. 질문의도 파악\n"
        "- 입력하신 질문은 법적 계약 가능 여부 판단이 아니라, 부산 지역업체 후보 검색 요청으로 분류했습니다.\n\n"
        "### 2. 지역업체 후보 소개\n"
        "- 아래 후보는 조달등록·정책기업·쇼핑몰/MAS·인증 여부를 기준으로 정리한 검토 후보입니다.\n\n"
    )
    if has_candidates:
        template += "[SERVER_TABLE_PLACEHOLDER]\n\n"
    else:
        template += "(검색 결과에서 유효한 업체 후보를 추출하지 못했습니다.)\n\n"
    template += (
        "### 3. 확인 필요사항\n"
        "- 본 안내는 후보 정보 제공이며, 실제 계약 전 품목 적합성, 조달등록 상태, "
        "인증 유효성, 기관 내부 기준을 확인해야 합니다."
    )
    _set_timing(generation_meta, _start)
    return template


# ─────────────────────────────────────────────
# Tier 1: 금액 기반 계약 방식 안내
# ─────────────────────────────────────────────
def build_amount_contract_guidance_answer(generation_meta: dict, mandatory_mcp_executed: list) -> str:
    _start = _time.time()
    generation_meta["answer_builder_used"] = "build_amount_contract_guidance_answer"
    generation_meta["answer_sections_rendered"] = [1, 2, 3, 4]
    generation_meta["candidate_section_position"] = -1
    generation_meta["legal_basis_section_rendered"] = True
    generation_meta["user_facing_source_labels_used"] = True
    generation_meta["raw_tool_names_hidden_from_answer"] = True

    user_status = _SOURCE_STATUS_MAP.get(generation_meta.get("source_status", ""), "확인")
    generation_meta["source_status_user_label"] = user_status

    basis_table, has_cache = _render_legal_basis_table(mandatory_mcp_executed, generation_meta)
    generation_meta["legal_basis_table_rendered"] = bool(basis_table)
    generation_meta["legal_basis_to_purchase_route_mapped"] = True

    template = (
        "### 1. 질문의도 파악\n"
        "- 입력하신 질문은 금액 기준에 따른 구매/계약 방식 안내 요청으로 분류했습니다.\n\n"
        "### 2. 법령 적용 해석\n"
        f"- 수의계약 한도 등 금액 기준을 검토했습니다. ({user_status})\n"
    )
    if basis_table:
        template += f"\n{basis_table}"
    if has_cache:
        template += _CACHE_NOTICE
    template += (
        "\n### 3. 구매 방법 안내\n"
        "- 2천만원, 5천만원 등 수의계약 한도는 기준 검토 용도로 안내됩니다.\n"
        "- 적용 가능 여부는 기관유형, 추정가격, 품목, 내부 기준에 따라 다르므로 개별 확인이 필요합니다.\n\n"
        "### 4. 확인 필요사항\n"
        "- 안내된 사항은 참고용이며, 기관별 자체 규정에 따라 다를 수 있습니다.\n"
        "- 여성기업, 장애인기업 등 정책기업 요건 충족 시 수의계약 한도가 달라질 수 있으나, "
        "적용 가능 여부를 반드시 개별 확인해야 합니다."
    )
    _set_timing(generation_meta, _start)
    return template


# ─────────────────────────────────────────────
# Tier 2: 지역업체 활용 및 전략 안내
# ─────────────────────────────────────────────
def build_regional_procurement_answer(generation_meta: dict, mandatory_mcp_executed: list) -> str:
    _start = _time.time()
    generation_meta["answer_builder_used"] = "build_regional_procurement_answer"
    generation_meta["answer_sections_rendered"] = [1, 2, 3, 4, 5]
    generation_meta["candidate_section_position"] = 4
    generation_meta["legal_basis_section_rendered"] = True
    generation_meta["user_facing_source_labels_used"] = True
    generation_meta["raw_tool_names_hidden_from_answer"] = True

    user_status = _SOURCE_STATUS_MAP.get(generation_meta.get("source_status", ""), "확인")
    generation_meta["source_status_user_label"] = user_status

    basis_table, has_cache = _render_legal_basis_table(mandatory_mcp_executed, generation_meta)
    generation_meta["legal_basis_table_rendered"] = bool(basis_table)
    generation_meta["legal_basis_to_purchase_route_mapped"] = True

    template = (
        "### 1. 질문의도 파악\n"
        "- 입력하신 금액 및 조건에 따라 지역상품 우선구매 전략을 검토했습니다.\n\n"
        "### 2. 법령 적용 해석\n"
    )
    if basis_table:
        template += f"\n{basis_table}"
    if has_cache:
        template += _CACHE_NOTICE
    template += (
        "\n### 3. 지역상품 구매 방법 안내\n"
        "- 구매 금액과 품목에 따라 지역제한 제한경쟁입찰, MAS 2단계 경쟁, "
        "또는 정책기업 수의계약 검토 경로가 있습니다.\n"
        "- 지역제한 적용 가능 여부는 기관유형, 추정가격, 품목, 내부 기준에 따라 다르므로 "
        "개별 확인이 필요합니다.\n\n"
        "### 4. 지역업체 후보 소개\n"
        "- 아래 후보는 조달등록 여부를 기준으로 정리한 검토 후보입니다.\n\n"
        "[SERVER_TABLE_PLACEHOLDER]\n\n"
        "### 5. 확인 필요사항 및 주의사항\n"
        "- 실제 계약 시 관련 법령 및 부산시 조례, 기관 내부 규정에 따른 절차를 거쳐야 합니다.\n"
        "- 기관유형, 추정가격, 품목, 내부 기준 확인이 필요합니다.\n"
        "- 본 안내는 검토 경로 제시이며, 계약 가능 여부를 확정하지 않습니다."
    )
    _set_timing(generation_meta, _start)
    return template


# ─────────────────────────────────────────────
# Tier 3: 기관 특화 심층 법률 검토
# ─────────────────────────────────────────────
def build_agency_specific_legal_review_answer(generation_meta: dict, model_answer: str) -> str:
    _start = _time.time()
    generation_meta["answer_builder_used"] = "build_agency_specific_legal_review_answer"
    generation_meta["answer_sections_rendered"] = [1, 2, 3]
    generation_meta["candidate_section_position"] = -1
    generation_meta["legal_basis_section_rendered"] = True
    generation_meta["user_facing_source_labels_used"] = True
    generation_meta["raw_tool_names_hidden_from_answer"] = True
    generation_meta["legal_basis_table_rendered"] = False
    generation_meta["source_status_user_label"] = "심층 법령 검토"
    generation_meta["legal_basis_to_purchase_route_mapped"] = False
    _set_timing(generation_meta, _start)
    return strip_raw_tool_names(model_answer)
