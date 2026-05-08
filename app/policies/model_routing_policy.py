"""
모델 라우팅 정책 (model_routing_policy)
- risk_based 모드: 질문 위험도에 따라 라우팅 결정
- Flash 전용 — 응답속도·비용·품질 종합 고려
"""
import os
import re
from typing import Optional


# ─────────────────────────────────────────────
# 환경 변수
# ─────────────────────────────────────────────
ROUTER_MODEL = "gemini-2.5-flash"
# Flash 전용 — Pro 제거
GEMINI_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash"
MODEL_ROUTING_MODE = os.getenv("MODEL_ROUTING_MODE", "risk_based")
MCP_PREFLIGHT_MAX_ITEMS = int(os.getenv("MCP_PREFLIGHT_MAX_ITEMS", "32"))
ADMIN_RULE_KEY_NAMES = (
    "지방자치단체 입찰 및 계약집행기준",
    "지방자치단체 입찰시 낙찰자 결정기준",
    "(계약예규) 정부 입찰·계약 집행기준",
    "(계약예규) 공동계약운용요령",
    "공기업ㆍ준정부기관 계약사무규칙",
    "기타공공기관 계약사무 운영규정",
    "물품 다수공급자계약 업무처리규정",
    "국가종합전자조달시스템 종합쇼핑몰 운영규정",
    "조달청 제조물품 직접생산확인 기준",
    "혁신제품 구매 운영 규정",
    "혁신제품 시범구매계약 추가특수조건",
    "중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙",
    "중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역",
    "소프트웨어사업 계약 및 관리감독에 관한 지침",
    "소프트웨어 기술성 평가기준 지침",
    "건설공사 발주 세부기준",
)


# ─────────────────────────────────────────────
# 고위험 키워드 (Pro 기본 모델 사용)
# ─────────────────────────────────────────────
HIGH_RISK_TRIGGERS = [
    # 수의계약 판단
    "수의계약 가능",
    "수의계약 할 수",
    "수의계약 되",
    "수의 가능",
    "수의계약이 가능",
    "바로 계약",
    "바로 수의",
    # 금액 한도
    "금액 한도",
    "금액 제한",
    "얼마까지",
    "얼마 이하",
    "천만원",
    "백만원",
    "억원",
    "만원 이하",
    "만원 이상",
    "만원까지",
    # 1인 견적
    "1인 견적",
    "한 업체만",
    "1인견적",
    "단일견적",
    # 지역제한 입찰
    "지역제한",
    "지역 제한",
    "지역업체만",
    # MAS 2단계 경쟁
    "2단계 경쟁",
    "MAS 경쟁",
    "2단계경쟁",
    # 정책기업 특례
    "정책기업 특례",
    "여성기업 수의",
    "장애인기업 수의",
    "사회적기업 수의",
    "바로 수의계약 가능",
    # 혁신제품 수의계약
    "혁신제품 수의",
    "혁신제품이면",
    "혁신 수의",
    "금액 제한 없이",
    # 혼합계약·공사
    "혼합계약",
    "공사 계약",
    "공사계약",
    "공사비",
    "공사금액",
    "전기공사",
    "정보통신공사",
    "통신공사",
    "건설공사",
    "소방공사",
    "소프트웨어사업",
    "기술성 평가",
    # 감사 리스크
    "감사 리스크",
    "감사원",
    "감사 지적",
    "감사지적",
    # 법령 해석
    "시행령",
    "시행규칙",
    "법률 해석",
    "법령 해석",
    "행정규칙",
    "조 제",  # "제25조 제1항" 등
    "조에 따라",
    "항에 따라",
]

# ─────────────────────────────────────────────
# 저위험 패턴 (Flash 허용)
# ─────────────────────────────────────────────
LOW_RISK_PATTERNS = [
    # 업체 후보 요청
    r"업체.*추천",
    r"업체.*후보",
    r"업체.*있어",
    r"업체.*알려",
    r"업체.*보여",
    # 검색·목록
    r"등록.*업체",
    r"종합쇼핑몰.*부산",
    r"부산.*업체.*목록",
    # 절차 안내
    r"절차.*알려",
    r"절차.*안내",
    r"방법.*알려",
    # 구매 경로 질문
    r"어디서.*살 수",
    r"어디서.*구매",
    r"어디서.*구입",
    # 상세 조회
    r"상세.*알려",
    r"상세.*보여",
    r"[a-fA-F0-9]{32}",
]


def classify_risk(user_message: str, intent_labels: list = None) -> dict:
    """
    사용자 질문의 위험도를 분류.

    Returns:
        {
            "risk_level": "high" | "low",
            "high_risk_triggers": [...],
            "model_primary": "gemini-2.5-pro" | "gemini-2.5-flash",
            "model_decision_reason": str,
        }
    """
    if MODEL_ROUTING_MODE != "risk_based":
        return {
            "risk_level": "default",
            "high_risk_triggers": [],
            "model_primary": GEMINI_MODEL,
            "model_decision_reason": f"MODEL_ROUTING_MODE={MODEL_ROUTING_MODE}, 기본 모델 사용",
        }

    msg_lower = user_message.lower()
    matched_triggers = []

    for trigger in HIGH_RISK_TRIGGERS:
        if trigger in user_message:
            matched_triggers.append(trigger)

    # intent 기반 고위험 판단
    high_risk_intents = {"sole_contract", "amount_threshold", "audit_risk",
                         "mixed_contract", "construction_contract"}
    if intent_labels:
        for label in intent_labels:
            if label in high_risk_intents:
                matched_triggers.append(f"intent:{label}")

    if matched_triggers:
        return {
            "risk_level": "high",
            "high_risk_triggers": matched_triggers,
            "model_primary": GEMINI_MODEL,
            "model_decision_reason": f"고위험 트리거 감지: {matched_triggers[:3]}",
        }

    # 저위험 패턴 매칭
    for pattern in LOW_RISK_PATTERNS:
        if re.search(pattern, user_message):
            return {
                "risk_level": "low",
                "high_risk_triggers": [],
                "model_primary": FALLBACK_MODEL,
                "model_decision_reason": f"저위험 패턴 매칭 → Flash 사용",
            }

    # 기본: Flash 사용 (모든 경우)
    return {
        "risk_level": "medium",
        "high_risk_triggers": [],
        "model_primary": GEMINI_MODEL,
        "model_decision_reason": "Flash 전용 정책",
    }


def decide_fallback(risk_info: dict,
                     legal_conclusion_allowed: bool,
                     blocked_scope: list,
                     direct_legal_basis_count: int,
                     company_search_success: bool,
                     claim_validation_pass: bool = True) -> dict:
    """Pro 실패 시 fallback 정책 결정."""
    res = {
        "fallback_allowed": False,
        "flash_company_table_fallback_allowed": False,
        "flash_legal_judgment_fallback_allowed": False,
        "deterministic_template_required": True,
        "fallback_model": None,
        "fallback_reason": ""
    }

    # Pro 실패 + legal_basis 충분 (조건: legal_conclusion_allowed=True, blocked_scope=[], count>0, claim pass)
    if legal_conclusion_allowed and not blocked_scope and direct_legal_basis_count > 0 and claim_validation_pass:
        res["fallback_allowed"] = True
        res["flash_company_table_fallback_allowed"] = True
        res["flash_legal_judgment_fallback_allowed"] = True
        res["deterministic_template_required"] = False
        res["fallback_model"] = FALLBACK_MODEL
        res["fallback_reason"] = f"MCP legal_basis 충분({direct_legal_basis_count}건) & claim_validation_pass → Flash fallback 허용"
        return res

    # 법적 결론 불허 또는 blocked_scope 존재
    if not legal_conclusion_allowed or blocked_scope:
        if company_search_success:
            res["fallback_allowed"] = True
            res["fallback_model"] = FALLBACK_MODEL
            res["flash_company_table_fallback_allowed"] = True
            res["flash_legal_judgment_fallback_allowed"] = False
            res["deterministic_template_required"] = True
            res["fallback_reason"] = "업체 후보 표 정리만 허용; 계약 가능 판단은 fail-closed"
            return res
        else:
            res["fallback_allowed"] = False
            res["fallback_reason"] = "legal_conclusion_allowed=false 또는 blocked_scope 존재 → deterministic fail-closed"
            return res

    # 기타: 업체 검색만 성공한 경우
    if company_search_success:
        res["fallback_allowed"] = True
        res["fallback_model"] = FALLBACK_MODEL
        res["flash_company_table_fallback_allowed"] = True
        res["flash_legal_judgment_fallback_allowed"] = False
        res["deterministic_template_required"] = True
        res["fallback_reason"] = "업체 후보 표 정리만 허용; 계약 가능 판단은 fail-closed"
        return res

    res["fallback_allowed"] = False
    res["fallback_reason"] = "MCP legal_basis 부족 + 업체검색 없음 → deterministic fail-closed"
    return res


def build_routing_log(risk_info: dict,
                      model_used: str,
                      model_selected: str = None,
                      pro_call_executed: bool = True,
                      test_type: str = "runtime",
                      legal_judgment_requested: bool = True,
                      legal_judgment_allowed: bool = True,
                      company_table_allowed: bool = True,
                      fallback_used: bool = False,
                      fallback_reason: str = "",
                      retry_count: int = 0,
                      legal_conclusion_allowed=True,
                      blocked_scope: list = None,
                      direct_legal_basis_count: int = 0,
                      deterministic_template_used: bool = False,
                      flash_answer_discarded: bool = False) -> dict:
    """로그용 라우팅 메타데이터 생성"""
    return {
        "model_routing_mode": MODEL_ROUTING_MODE,
        "model_selected": model_selected if model_selected else risk_info.get("model_primary", GEMINI_MODEL),
        "model_used": model_used,
        "pro_call_executed": pro_call_executed,
        "test_type": test_type,
        "model_decision_reason": risk_info.get("model_decision_reason", ""),
        "risk_level": risk_info.get("risk_level", "unknown"),
        "high_risk_triggers": risk_info.get("high_risk_triggers", []),
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "retry_count": retry_count,
        "legal_conclusion_allowed": legal_conclusion_allowed,
        "legal_judgment_requested": legal_judgment_requested,
        "legal_judgment_allowed": legal_judgment_allowed,
        "company_table_allowed": company_table_allowed,
        "blocked_scope": blocked_scope or [],
        "direct_legal_basis_count": direct_legal_basis_count,
        "deterministic_template_used": deterministic_template_used,
        "flash_answer_discarded": flash_answer_discarded,
    }

def _is_pure_legal_explanation(router_result=None) -> bool:
    """Router가 순수 법령·제도 설명으로 판단했는지 확인한다."""
    if router_result is None:
        return False
    return (
        bool(getattr(router_result, "legal_explanation_only", False))
        and not bool(getattr(router_result, "candidate_lookup_required", False))
        and not bool(getattr(router_result, "company_lookup_required", False))
    )


def classify_query_tier(risk_info: dict, intent_labels: list, user_message: str = "", router_result=None) -> int:
    """
    3-Tier 라우팅 구조를 위해 질문의 Tier를 결정합니다.
    Tier 0 (Fast Track): 금액/계약/법령 의도 없고 순수 업체검색.
    Tier 1 (General/Legal Explanation): 순수 법령·제도 설명 또는 금액 중심 단순 계약 안내.
    Tier 2 (Deep Research): 금액 + 품목 + 지역업체 선호 또는 지역상품 구매전략.
    Tier 3 (Agency Specific): 특정 기관 자체규정(공기업/출자출연/부산교통공사 등)이 명확할 때.
    """
    if not intent_labels:
        intent_labels = []

    has_amount = any(w in user_message for w in ["천만원", "백만원", "억원", "억", "금액", "예산", "만원"])
    has_local = any(w in user_message for w in ["지역업체", "부산업체", "부산 업체", "지역 업체", "부산상품", "지역상품"])
    has_item = any(w in user_message for w in ["컴퓨터", "물품", "CCTV", "구매", "조명", "LED", "가구", "차량",
                                                "복사기", "프린터", "에어컨", "냉난방", "소프트웨어", "서버",
                                                "사려", "구입", "납품", "사무용품", "소모품", "청소용품",
                                                "사무기기", "가전", "장비", "기자재", "비품", "용품"])
    has_agency = any(w in user_message for w in ["부산교통공사", "공기업", "출자출연", "시설공단", "환경공단"])
    has_contract_method = any(w in user_message for w in ["수의계약", "입찰", "경쟁입찰", "제한입찰",
                                                           "수의", "견적", "낙찰", "적격심사",
                                                           "공동계약", "MAS", "다수공급자"])

    # Tier 3: 기관명 패턴이 명확할 때만 (단순 "공사"는 오탐 우려로 제외)
    if has_agency:
        return 3

    # Tier 1: 순수 법령·제도 설명은 업체검색/복합검토로 보내지 않는다.
    if _is_pure_legal_explanation(router_result):
        return 1

    # Tier 0: 금액 관련 법적 제한/한도 판단이 주 목적이 아닌 순수 업체 검색/상세 조회
    fast_track_intents = {"company_search", "policy_candidate_search", "shopping_mall_search", "certified_product_search", "company_detail", "license_search", "mas_search", "innovation_product_search", "excellent_procurement_search"}
    if (
        risk_info.get("risk_level") in ["low", "medium"]
        and any(i in intent_labels for i in fast_track_intents)
        and not has_amount
        and not has_contract_method
    ):
        return 0

    # Tier 0 키워드 fallback: 품목+지역업체 언급 + 금액/계약방식 없음 → 순수 업체 검색
    if (has_item or has_local) and not has_amount and not has_contract_method and not has_agency:
        return 0

    # Tier 2: 금액 + 품목, 또는 금액 + 계약방식 (수의계약/입찰 포함 시 반드시 법령 조회)
    if has_amount and (has_item or has_local or has_contract_method):
        return 2

    # Tier 2: 계약방식 키워드만으로도 법령 조회 필요 (금액 없어도)
    if has_contract_method:
        return 2

    # Tier 1: 그 외 금액이 있거나, 일반적인 질문
    return 1

def generate_mandatory_mcp_plan(user_message: str, tier: int, agency_type: str = None) -> list:
    """
    Tier 1/2 쿼리에 대해 필수적으로 호출해야 할 MCP 계획을 생성합니다.
    주제 클러스터 엔진을 우선 사용하고, 실패 시 기존 키워드 매칭을 fallback으로 사용합니다.
    """
    # ── 1순위: 주제 클러스터 엔진 (기관×주제×계약유형 → 조문 클러스터) ──
    try:
        from topic_cluster_engine import build_preflight_plan
        cluster_plan = build_preflight_plan(user_message, agency_type)
        if cluster_plan:
            plan = _augment_with_internal_discovery(user_message, cluster_plan, agency_type=agency_type)
            plan = _augment_with_regional_support_catalog(user_message, plan, agency_type=agency_type)
            plan = _augment_with_tool_orchestration(user_message, plan, agency_type=agency_type)
            return _limit_mandatory_mcp_plan(plan)
    except Exception as e:
        print(f"  [TOPIC_CLUSTER] Fallback to legacy: {e}")
    
    # ── 2순위: 기존 키워드 매칭 (fallback) ──
    plan = _augment_with_internal_discovery(
        user_message,
        _legacy_mandatory_mcp_plan(user_message, tier, agency_type),
        agency_type=agency_type,
    )
    plan = _augment_with_regional_support_catalog(user_message, plan, agency_type=agency_type)
    plan = _augment_with_tool_orchestration(user_message, plan, agency_type=agency_type)
    return _limit_mandatory_mcp_plan(plan)


def _plan_identity(item: dict) -> str:
    args = item.get("args") or {}
    tool_name = item.get("name")
    key_value = (
        args.get("query")
        or args.get("law_name")
        or args.get("mst")
        or args.get("rule_id")
        or ""
    )
    if tool_name == "search_law":
        match = re.search(r"(.+?제\d+조(?:의\d+)?)", str(key_value))
        if match:
            key_value = match.group(1)
    elif tool_name in ("search_admin_rule", "get_admin_rule"):
        compact_key = str(key_value).replace(" ", "")
        for rule_name in ADMIN_RULE_KEY_NAMES:
            if rule_name.replace(" ", "") in compact_key:
                key_value = rule_name
                break
    key_value = re.sub(r"\s+", " ", str(key_value)).strip()
    return f"{tool_name}:{key_value}"


def _plan_category(item: dict) -> str:
    reason = item.get("selected_reason", "") or ""
    if reason.startswith("tool_orchestration:"):
        return "tool"
    if reason.startswith("regional_support_catalog:"):
        return "catalog"
    if reason.startswith("dynamic_internal_discovery"):
        return "dynamic"
    if item.get("name") in ("search_admin_rule", "get_admin_rule"):
        return "dynamic"
    return "cluster"


def _limit_mandatory_mcp_plan(plan: list, max_items: int | None = None) -> list:
    """Keep preflight broad enough for quality without letting latency explode."""
    limit = max_items or MCP_PREFLIGHT_MAX_ITEMS
    if not plan or len(plan) <= limit:
        return plan

    budgets = {
        "cluster": 15,
        "catalog": 8,
        "dynamic": 5,
        "tool": 4,
    }
    by_category = {key: [] for key in budgets}
    for item in plan:
        by_category.setdefault(_plan_category(item), []).append(item)

    selected = []
    seen = set()

    def add_item(item: dict) -> bool:
        if len(selected) >= limit:
            return False
        key = _plan_identity(item)
        if key in seen:
            return False
        selected.append(item)
        seen.add(key)
        return True

    for category, budget in budgets.items():
        for item in by_category.get(category, [])[:budget]:
            add_item(item)

    # Use remaining slots for catalog/tool evidence first, then dynamic discovery,
    # then any leftover fixed cluster entries.
    for category in ("catalog", "tool", "dynamic", "cluster"):
        for item in by_category.get(category, []):
            if len(selected) >= limit:
                break
            add_item(item)

    if len(selected) < len(plan):
        print(
            f"  [MCP-PREFLIGHT] trimmed plan: {len(plan)} -> {len(selected)} "
            f"(limit={limit})",
            flush=True,
        )
    return selected


def _augment_with_regional_support_catalog(user_message: str, base_plan: list, agency_type: str = None) -> list:
    """지역업체 보호·우대제도 카탈로그 매칭 결과로 조회 계획을 보강한다."""
    plan = list(base_plan or [])
    try:
        from policies.regional_support_catalog import build_catalog_evidence_plan
    except ImportError:
        try:
            from app.policies.regional_support_catalog import build_catalog_evidence_plan
        except ImportError as e:
            try:
                from regional_support_catalog import build_catalog_evidence_plan
            except ImportError:
                print(f"  [REGIONAL-CATALOG] unavailable: {e}")
                return plan

    try:
        catalog_plan = build_catalog_evidence_plan(user_message, agency_type=agency_type)
    except Exception as e:
        print(f"  [REGIONAL-CATALOG] failed: {e}")
        return plan

    seen = {
        f"{item.get('name')}:{(item.get('args') or {}).get('query') or (item.get('args') or {}).get('law_name') or ''}"
        for item in plan
    }
    added = 0
    for item in catalog_plan:
        args = item.get("args") or {}
        key = f"{item.get('name')}:{args.get('query') or args.get('law_name') or ''}"
        if key in seen:
            continue
        plan.append(item)
        seen.add(key)
        added += 1

    if added:
        print(f"  [REGIONAL-CATALOG] augmented plan: +{added}, total={len(plan)}")
    return plan


def _augment_with_tool_orchestration(user_message: str, base_plan: list, agency_type: str = None) -> list:
    """체인/종합리서치/별표 도구가 필요한 질문이면 계획을 보강한다."""
    try:
        from policies.tool_orchestration_policy import augment_tool_orchestration
    except ImportError:
        try:
            from tool_orchestration_policy import augment_tool_orchestration
        except ImportError as e:
            print(f"  [TOOL-ORCH] unavailable: {e}")
            return base_plan

    try:
        augmented = augment_tool_orchestration(user_message, base_plan, agency_type=agency_type)
    except Exception as e:
        print(f"  [TOOL-ORCH] failed: {e}")
        return base_plan

    added = len(augmented) - len(base_plan or [])
    if added:
        print(f"  [TOOL-ORCH] augmented plan: +{added}, total={len(augmented)}")
    return augmented


def _augment_with_internal_discovery(
    user_message: str,
    base_plan: list,
    agency_type: str = None,
    max_total: int = 40,
) -> list:
    """고정 조문 클러스터를 내부 DB 동적 탐색 결과로 보강한다."""
    plan = list(base_plan or [])
    try:
        from policies.internal_law_discovery import discover_internal_law_plan
    except ImportError:
        try:
            from internal_law_discovery import discover_internal_law_plan
        except ImportError as e:
            print(f"  [INTERNAL-DISCOVERY] unavailable: {e}")
            return plan

    try:
        extra_plan = discover_internal_law_plan(user_message, agency_type=agency_type)
    except Exception as e:
        print(f"  [INTERNAL-DISCOVERY] failed: {e}")
        return plan

    seen = {
        f"{item.get('name')}:{(item.get('args') or {}).get('query', '')}"
        for item in plan
    }
    added = 0
    for item in extra_plan:
        key = f"{item.get('name')}:{(item.get('args') or {}).get('query', '')}"
        if key in seen:
            continue
        plan.append(item)
        seen.add(key)
        added += 1
        if len(plan) >= max_total:
            break
    if added:
        print(f"  [INTERNAL-DISCOVERY] augmented fixed plan: +{added}, total={len(plan)}")
    return plan


def _legacy_mandatory_mcp_plan(user_message: str, tier: int, agency_type: str = None) -> list:
    """기존 키워드 매칭 기반 MCP 계획 (fallback용)."""
    msg = user_message.lower()
    plan = []
    seen = set()  # 중복 방지

    def add(name: str, args: dict):
        key = f"{name}:{args.get('query','')}{args.get('mst','')}{args.get('jo','')}"
        if key not in seen:
            seen.add(key)
            plan.append({"name": name, "args": args})

    # ━━━ 기관 유형별 법령 체계 결정 ━━━
    at = (agency_type or "").lower().replace(" ", "")
    # 기관 유형 정규화
    if at in ("national_agency", "국가기관", "중앙부처", "national_gov"):
        law_system = "national"
    elif at in ("public_corporation", "공기업", "준정부기관", "공기업/준정부기관", "공공기관", "public_agency"):
        law_system = "public_corp"
    elif at in ("invested_institution", "출자출연기관", "지방공기업", "부산도시공사", "부산교통공사",
                "부산시설공단", "부산관광공사", "busan_entity"):
        law_system = "invested"
    else:
        law_system = "local"  # 지자체 (기본)

    # ━━━ 기관별 핵심 법령 매핑 ━━━
    # ※ 법제처 API는 공백을 AND 조건 처리 → 키워드 3~4개가 최적
    # 수의계약 조문 (법률 + 시행령)
    DIRECT_CONTRACT_QUERIES = {
        "local": [
            ("search_law", "지방계약법 제9조"),
            ("search_law", "지방계약법 시행령 제25조"),
            ("search_law", "지방계약법 시행령 제30조"),
        ],
        "national": [
            ("search_law", "국가계약법 제7조"),
            ("search_law", "국가계약법 시행령 제26조"),
            ("search_law", "국가계약법 시행령 제30조"),
        ],
        "public_corp": [
            ("search_law", "공기업 준정부기관 계약사무규칙 수의계약"),
            ("search_law", "국가계약법 제7조"),
            ("search_law", "국가계약법 시행령 제26조"),
        ],
        "invested": [
            ("search_law", "지방계약법 제9조"),
            ("search_law", "지방계약법 시행령 제25조"),
            ("search_law", "지방계약법 시행령 제30조"),
            ("search_law", "출자출연기관 운영 법률 계약"),
        ],
    }
    # 제한입찰 조문
    LIMITED_BID_QUERIES = {
        "local": [
            ("search_law", "지방계약법 시행령 제20조"),
            ("search_admin_rule", "지방자치단체 입찰시 낙찰자 결정기준"),
        ],
        "national": [
            ("search_law", "국가계약법 시행령 제21조"),
            ("search_admin_rule", "정부 입찰 계약 집행기준"),
        ],
        "public_corp": [
            ("search_law", "계약사무규칙 경쟁입찰"),
            ("search_admin_rule", "기타공공기관 계약사무 운영규정"),
        ],
        "invested": [
            ("search_law", "지방계약법 시행령 제20조"),
            ("search_admin_rule", "지방자치단체 입찰시 낙찰자 결정기준"),
        ],
    }
    # 공동계약 조문 (법률→시행령→운용요령 연쇄 필요 → chain_law_system 사용)
    JOINT_CONTRACT_QUERIES = {
        "local": [
            ("chain_law_system", "지방계약법 공동계약 의무비율 지역업체"),
        ],
        "national": [
            ("chain_law_system", "국가계약법 공동계약 의무비율"),
        ],
        "public_corp": [
            ("chain_law_system", "국가계약법 공동계약 의무비율"),
        ],
        "invested": [
            ("chain_law_system", "지방계약법 공동계약 의무비율 지역업체"),
        ],
    }
    # 기본 행정규칙
    DEFAULT_ADMIN_QUERIES = {
        "local": [
            ("search_admin_rule", "지방자치단체 입찰 및 계약집행기준"),
        ],
        "national": [
            ("search_admin_rule", "정부 입찰 계약 집행기준"),
        ],
        "public_corp": [
            ("search_admin_rule", "기타공공기관 계약사무 운영규정"),
        ],
        "invested": [
            ("search_admin_rule", "지방자치단체 입찰 및 계약집행기준"),
        ],
    }
    # 정책기업 수의계약 특례
    POLICY_COMPANY_QUERIES = {
        "local": [
            ("search_law", "지방계약법 시행령 제25조 제5호 여성기업 장애인기업 사회적기업 수의계약"),
        ],
        "national": [
            ("search_law", "국가계약법 시행령 제26조 여성기업 장애인기업 사회적기업 수의계약"),
        ],
        "public_corp": [
            ("search_law", "공기업 준정부기관 계약사무규칙 여성기업 장애인기업 수의계약"),
        ],
        "invested": [
            ("search_law", "지방계약법 시행령 제25조 제5호 여성기업 장애인기업 사회적기업 수의계약"),
        ],
    }
    # 적격심사(공사/용역)
    CONSTRUCTION_QUERIES = {
        "local": "지방자치단체 입찰시 낙찰자 결정기준 공사 적격심사",
        "national": "조달청 시설공사 적격심사세부기준",
        "public_corp": "조달청 시설공사 적격심사세부기준",
        "invested": "지방자치단체 입찰시 낙찰자 결정기준 공사 적격심사",
    }
    SERVICE_QUERIES = {
        "local": "지방자치단체 입찰시 낙찰자 결정기준 용역 적격심사",
        "national": "조달청 일반용역 적격심사 세부기준",
        "public_corp": "조달청 일반용역 적격심사 세부기준",
        "invested": "지방자치단체 입찰시 낙찰자 결정기준 용역 적격심사",
    }
    # 평가/가점 관련
    EVALUATION_QUERIES = {
        "local": [
            ("search_admin_rule", "지방자치단체 입찰시 낙찰자 결정기준 지역업체 가점"),
            ("search_admin_rule", "지방자치단체 입찰시 낙찰자 결정기준 적격심사 세부기준"),
        ],
        "national": [
            ("search_admin_rule", "정부 입찰 계약 집행기준 적격심사 지역가점"),
            ("search_admin_rule", "조달청 적격심사 세부기준 신인도 가점"),
        ],
        "public_corp": [
            ("search_admin_rule", "기타공공기관 계약사무 운영규정 적격심사"),
        ],
        "invested": [
            ("search_admin_rule", "지방자치단체 입찰시 낙찰자 결정기준 지역업체 가점"),
            ("search_admin_rule", "지방자치단체 입찰시 낙찰자 결정기준 적격심사 세부기준"),
        ],
    }
    # 가격/예정가격 관련
    PRICE_QUERIES = {
        "local": [
            ("search_law", "지방계약법 시행령 예정가격 작성기준"),
            ("search_admin_rule", "지방자치단체 원가계산 및 예정가격 작성요령"),
        ],
        "national": [
            ("search_law", "국가계약법 시행령 예정가격 작성기준"),
            ("search_admin_rule", "원가계산에 의한 예정가격 작성준칙"),
        ],
        "public_corp": [
            ("search_law", "국가계약법 시행령 예정가격 작성기준"),
        ],
        "invested": [
            ("search_law", "지방계약법 시행령 예정가격 작성기준"),
            ("search_admin_rule", "지방자치단체 원가계산 및 예정가격 작성요령"),
        ],
    }

    # ━━━ 의도 감지 ━━━
    has_amount = bool(re.search(r'\d+[천만백억]', msg))
    has_contract_method = any(w in msg for w in ["수의계약", "견적", "1인", "2인", "소액", "수의",
                                                  "수의시담", "소액수의", "견적서"])
    has_bid = any(w in msg for w in ["입찰", "경쟁입찰", "공개입찰", "낙찰", "적격심사",
                                      "제한경쟁", "일반경쟁", "지명경쟁", "입찰공고",
                                      "투찰", "개찰", "유찰", "재공고"])
    has_regional = any(w in msg for w in ["지역", "부산", "지역제한", "지역업체", "로컬",
                                           "지역가점", "지역상생", "지역상품", "지역보호",
                                           "본점소재지", "소재지"])
    has_joint = any(w in msg for w in ["공동계약", "공동도급", "공동수급", "JV", "컨소시엄"])
    has_mas = any(w in msg for w in ["종합쇼핑몰", "MAS", "다수공급", "쇼핑몰", "3자단가", "제3자",
                                      "나라장터", "카탈로그", "단가계약"])
    has_excellence = any(w in msg for w in ["우수조달", "우수물품", "혁신제품", "혁신", "기술개발",
                                             "신기술", "신제품", "성능인증", "품질인증",
                                             "우수발명", "녹색제품"])
    has_policy_company = any(w in msg for w in ["여성기업", "장애인기업", "사회적기업", "청년창업",
                                                 "소기업", "소상공인", "정책기업",
                                                 "사회적협동조합", "자활기업", "마을기업",
                                                 "중증장애인", "장애인표준사업장"])
    has_priority = any(w in msg for w in ["우선구매", "의무구매", "중소기업제품",
                                           "직접생산", "경쟁제품", "중소기업자간"])
    has_construction = any(w in msg for w in ["공사", "건설", "시공", "건축", "종합공사", "전문공사"])
    has_service = any(w in msg for w in ["용역", "설계", "감리", "컨설팅", "엔지니어링", "기술용역"])
    # [추가 의도]
    has_evaluation = any(w in msg for w in ["가점", "배점", "평가기준", "평가항목", "심사기준",
                                             "신인도", "신용평가", "종합평가", "기술평가",
                                             "제안서평가", "가격점수", "비가격점수"])
    has_price = any(w in msg for w in ["예정가격", "추정가격", "기초금액", "원가계산",
                                        "예가", "투찰률", "사정률", "낙찰률",
                                        "계약보증금", "하자보증", "지체상금", "선금",
                                        "기성", "설계변경"])

    # ━━━ Tier 1: 기본 법령 조회 ━━━
    if tier == 1:
        if has_contract_method or has_amount:
            for tool, q in DIRECT_CONTRACT_QUERIES[law_system]:
                add(tool, {"query": q})
        if has_bid:
            for tool, q in LIMITED_BID_QUERIES[law_system]:
                add(tool, {"query": q})
        if not plan:
            for tool, q in DIRECT_CONTRACT_QUERIES[law_system][:1]:
                add(tool, {"query": q})
            for tool, q in DEFAULT_ADMIN_QUERIES[law_system]:
                add(tool, {"query": q})
        return plan

    # ━━━ Tier 2: 의도 기반 동적 쿼리 ━━━
    if tier != 2:
        return plan

    # [기본] 수의계약/금액이 포함되면 핵심 조문
    if has_contract_method or has_amount:
        for tool, q in DIRECT_CONTRACT_QUERIES[law_system]:
            add(tool, {"query": q})

    # [의도 1] 지역제한/부산 → 지역제한 법체계 + 부산 조례
    if has_regional:
        if law_system == "local":
            add("chain_law_system", {"query": "지방계약법 물품 구매 지역제한 제한경쟁"})
        elif law_system == "national":
            add("chain_law_system", {"query": "국가계약법 물품 구매 지역제한 제한경쟁"})
        else:
            add("chain_law_system", {"query": "지방계약법 물품 구매 지역제한 제한경쟁"})
        add("chain_ordinance_compare", {"query": "부산광역시 지역상품 우선구매 조례"})

    # [의도 2] MAS/종합쇼핑몰 → MAS 규정 (기관 공통)
    if has_mas:
        add("search_admin_rule", {"query": "물품 다수공급자계약 업무처리규정"})
        add("search_admin_rule", {"query": "국가종합전자조달시스템 종합쇼핑몰 운영규정"})

    # [의도 3] 우수조달/혁신제품 → 우수물품 특례 (기관 공통)
    if has_excellence:
        add("search_admin_rule", {"query": "우수조달물품 지정 관리 규정"})
        add("search_admin_rule", {"query": "혁신제품 구매 운영 규정"})

    # [의도 4] 정책기업(여성/장애인/사회적) → 기관별 특례 조문
    if has_policy_company:
        for tool, q in POLICY_COMPANY_QUERIES[law_system]:
            add(tool, {"query": q})

    # [의도 5] 공동계약 → 기관별 공동계약 조문 + 운용요령
    if has_joint:
        for tool, q in JOINT_CONTRACT_QUERIES[law_system]:
            add(tool, {"query": q})
        add("search_admin_rule", {"query": "공동계약운용요령"})

    # [의도 6] 입찰/낙찰 → 기관별 입찰 관련 행정규칙 + 법체계 보충
    if has_bid:
        for tool, q in LIMITED_BID_QUERIES[law_system]:
            add(tool, {"query": q})
        # 법체계 맥락 보충 (개별 조문의 상위/하위 법령 관계 파악용)
        if law_system == "local":
            add("chain_law_system", {"query": "지방계약법 입찰 제한경쟁 낙찰자"})
        elif law_system == "national":
            add("chain_law_system", {"query": "국가계약법 입찰 제한경쟁 낙찰자"})

    # [의도 7] 우선구매/의무구매 → 중소기업 우선구매 (기관 공통)
    if has_priority:
        add("search_law", {"query": "중소기업제품 구매촉진 및 판로지원에 관한 법률"})
        add("search_admin_rule", {"query": "중소기업자간 경쟁제품 직접구매 대상 품목"})

    # [의도 8] 공사 → 기관별 적격심사 기준
    if has_construction:
        add("search_admin_rule", {"query": CONSTRUCTION_QUERIES[law_system]})

    # [의도 9] 용역 → 기관별 적격심사 기준
    if has_service:
        add("search_admin_rule", {"query": SERVICE_QUERIES[law_system]})

    # [의도 10] 가점/평가/심사 → 기관별 평가 기준
    if has_evaluation:
        for tool, q in EVALUATION_QUERIES[law_system]:
            add(tool, {"query": q})

    # [의도 11] 예정가격/원가계산/보증금 등 → 기관별 가격 기준 + 법체계 보충
    if has_price:
        for tool, q in PRICE_QUERIES[law_system]:
            add(tool, {"query": q})
        # 법체계 맥락 보충
        if law_system == "local":
            add("chain_law_system", {"query": "지방계약법 예정가격 원가계산"})
        elif law_system == "national":
            add("chain_law_system", {"query": "국가계약법 예정가격 원가계산"})

    # [안전망] 아무 의도도 감지 안 되면 → 질문 원문으로 직접 검색
    if not plan:
        # 질문 원문에서 핵심 키워드를 추출하여 법령 검색
        # (의도에 걸리지 않은 미지의 질문도 대응)
        add("chain_full_research", {"query": user_message[:80]})
        # 기본 법령도 함께 주입
        for tool, q in DIRECT_CONTRACT_QUERIES[law_system][:1]:
            add(tool, {"query": q})

    return plan


