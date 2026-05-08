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
    "partial_mcp_with_missing": "일부 근거만 확인, 미확인 근거 존재",
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
    "실제 계약 전 최신 법령, 기관 내부 기준, 인증 상태는 별도 확인이 필요합니다.\n"
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
    evidence_cards = generation_meta.get("evidence_cards") or []
    if evidence_cards:
        return _render_evidence_card_table(evidence_cards, generation_meta)

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


def _render_evidence_card_table(evidence_cards: list, generation_meta: dict) -> tuple:
    """구조화 근거카드를 사용자용 근거표로 렌더링."""
    overall_status_key = generation_meta.get("source_status", "mcp_preflight_success")
    overall_user_status = _SOURCE_STATUS_MAP.get(overall_status_key, "확인")
    rows = []
    seen = set()
    has_cache_hit = False

    for card in evidence_cards:
        if card.get("status") != "hit":
            continue
        label = card.get("law_name") or card.get("query")
        if not label:
            continue
        article = card.get("article_no")
        if article and article not in label:
            label = f"{label} {article}"
        if label in seen:
            continue
        seen.add(label)
        if card.get("from_cache"):
            has_cache_hit = True
            row_status = "캐시된 확인 근거 사용"
        elif card.get("source") == "internal_db":
            row_status = "내부 DB 확인"
        elif card.get("source") == "external_mcp":
            row_status = "외부 MCP 확인"
        else:
            row_status = overall_user_status

        meaning = _meaning_from_supports(card.get("supports") or [])
        date = card.get("effective_date")
        if date:
            meaning = f"{meaning} (시행일 {date})"
        rows.append(f"| {label} | {row_status} | {meaning} |")

    if not rows:
        return "", has_cache_hit
    header = "| 검토 근거 | 확인 상태 | 실무상 의미 |\n|---|---|---|\n"
    return header + "\n".join(rows[:8]) + "\n", has_cache_hit


def _meaning_from_supports(supports: list) -> str:
    mapping = {
        "direct_contract": "수의계약 가능성 검토",
        "one_person_quote": "1인 견적 가능성 검토",
        "amount_threshold": "금액 기준 검토",
        "regional_restriction": "지역제한 경쟁입찰 검토",
        "local_company_point": "지역업체 가점 검토",
        "joint_contract": "공동도급 기준 검토",
        "mas": "MAS/종합쇼핑몰 경로 검토",
        "priority_purchase": "우선구매 제도 검토",
    }
    labels = [mapping[s] for s in supports if s in mapping]
    return " · ".join(labels[:2]) if labels else "법령 근거 확인"


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


def _render_missing_mcp_table(generation_meta: dict) -> str:
    """mandatory_mcp_missing을 사용자용 '미확인 근거' 표로 렌더링한다.
    raw tool name은 노출하지 않고 _QUERY_LABEL_MAP 기반 사용자 라벨만 표시."""
    missing_list = generation_meta.get("mandatory_mcp_missing", [])
    if not missing_list:
        return ""
    seen = set()
    rows = []
    for entry in missing_list:
        label_pair = _resolve_query_label(entry)
        if label_pair is None:
            continue
        label, meaning = label_pair
        if label not in seen:
            seen.add(label)
            rows.append(f"| {label} | 조회 실패 | {meaning} 유보 |")
    if not rows:
        return ""
    header = "\n### 미확인 근거\n| 미확인 근거 | 상태 | 의미 |\n|---|---|---|\n"
    return header + "\n".join(rows) + "\n"


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
        "### 3. 바로 할 일\n"
        "- 후보 업체가 실제 구매 품목을 납품할 수 있는지 품목·규격을 먼저 확인하세요.\n"
        "- 조달등록, 종합쇼핑몰/MAS 등록, 인증 상태, 정책기업 지위를 확인하세요.\n"
        "- 금액이나 계약방식이 정해져 있다면 별도 법령 검토 후 수의계약·입찰·MAS 경로를 선택하세요.\n"
        "- 이 표는 후보 발굴용이며, 업체 적격성이나 계약 가능성을 확정하지 않습니다."
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
        "### 1. 판단 요약\n"
        f"- 입력 조건을 기준으로 수의계약·견적 방식·경쟁입찰 필요성을 검토했습니다. ({user_status})\n"
        "- 금액 기준만으로 바로 결론을 확정하지 않고, 기관유형·품목·정책기업/인증 여부를 함께 봐야 합니다.\n\n"
        "### 2. 확인한 근거\n"
    )
    if basis_table:
        template += f"\n{basis_table}"
    missing_table = _render_missing_mcp_table(generation_meta)
    if missing_table:
        template += missing_table
    if has_cache:
        template += _CACHE_NOTICE
    template += (
        "\n### 3. 실무 실행 경로\n"
        "- **일반 소액 수의계약 경로**: 추정가격과 1인/2인 이상 견적 기준을 먼저 확인합니다.\n"
        "- **정책기업 경로**: 여성기업·장애인기업·사회적기업·소기업 등 해당 여부가 있으면 별도 한도와 견적 방식을 검토합니다.\n"
        "- **인증·우선구매 경로**: 혁신제품, 우수조달물품, 기술개발제품이면 수의계약 특례나 우선구매 가능성을 별도로 확인합니다.\n"
        "- **경쟁입찰 전환 경로**: 수의계약이 어렵다면 지역제한, MAS 2단계, 평가 가점 등으로 지역상품 구매 가능성을 검토합니다.\n\n"
        "### 4. 바로 할 일\n"
        "- 기관유형이 지방자치단체인지, 국가기관인지, 공기업·준정부기관인지 확정하세요.\n"
        "- 추정가격 기준 금액인지 부가세 포함 총액인지 구분하세요.\n"
        "- 품목이 중소기업자간 경쟁제품, 직접생산확인 대상, 혁신제품, 우수조달물품인지 확인하세요.\n"
        "- 수의계약을 검토한다면 1인 견적 가능 여부와 2인 이상 견적 필요 여부를 따로 확인하세요."
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
        "### 1. 판단 요약\n"
        "- 입력하신 조건을 기준으로 지역상품·지역업체로 연결할 수 있는 구매 경로를 검토했습니다.\n"
        "- 법령상 바로 어려운 경로가 있더라도, 지역제한·MAS·정책기업·인증제품 경로를 순서대로 검토합니다.\n\n"
        "### 2. 확인한 근거\n"
    )
    if basis_table:
        template += f"\n{basis_table}"
    missing_table = _render_missing_mcp_table(generation_meta)
    if missing_table:
        template += missing_table
    if has_cache:
        template += _CACHE_NOTICE
    template += (
        "\n### 3. 지역상품 구매 실행 경로\n"
        "- **지역제한 입찰**: 금액·계약유형 기준에 맞으면 부산 지역업체 제한 가능성을 우선 검토합니다.\n"
        "- **MAS/종합쇼핑몰 경로**: 쇼핑몰 등록 품목이면 2단계 경쟁, 납품지역, 평가방식에서 지역 요소를 확인합니다.\n"
        "- **정책기업 수의계약 경로**: 여성기업·장애인기업·사회적기업 등 정책기업이면 금액 한도와 견적 방식을 분리해 검토합니다.\n"
        "- **인증제품 경로**: 혁신제품·우수조달·기술개발제품이면 해당 지정·인증 유효성을 확인하고 특례 가능성을 검토합니다.\n"
        "- **일반 지역업체 후보 발굴**: 법령상 계약방식이 정해진 뒤, 실제 납품 가능한 부산 업체 후보를 비교합니다.\n\n"
        "### 4. 부산 지역업체 후보\n"
        "- 아래 후보는 조달등록·정책기업·쇼핑몰/MAS·인증 여부를 기준으로 정리한 검토 후보입니다.\n\n"
        "[SERVER_TABLE_PLACEHOLDER]\n\n"
        "### 5. 바로 할 일\n"
        "- 품목 규격과 세부품명을 확정한 뒤, 쇼핑몰/MAS 등록 여부를 확인하세요.\n"
        "- 후보 업체의 조달등록, 인증 상태, 직접생산확인, 정책기업 지위를 확인하세요.\n"
        "- 수의계약이 어려우면 지역제한 입찰 또는 MAS 2단계 경쟁에서 지역요소를 반영할 수 있는지 검토하세요.\n"
        "- 본 안내는 실행 경로 제시이며, 최종 계약 가능 여부는 기관 내부 검토로 확정해야 합니다."
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
