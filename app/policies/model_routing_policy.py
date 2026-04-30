"""
모델 라우팅 정책 (model_routing_policy)
- risk_based 모드: 질문 위험도에 따라 Pro/Flash 자동 선택
- 저위험 → Flash, 고위험 → Pro
- Pro 실패 시 fallback 정책 결정
"""
import os
import re
from typing import Optional


# ─────────────────────────────────────────────
# 환경 변수
# ─────────────────────────────────────────────
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "gemini-2.5-flash")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini-2.5-flash")
MODEL_ROUTING_MODE = os.getenv("MODEL_ROUTING_MODE", "risk_based")


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

    # 기본: Pro 사용 (미분류 → 안전 우선)
    return {
        "risk_level": "medium",
        "high_risk_triggers": [],
        "model_primary": GEMINI_MODEL,
        "model_decision_reason": "미분류 질문 → 안전 우선 Pro 사용",
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

def classify_query_tier(risk_info: dict, intent_labels: list, user_message: str = "") -> int:
    """
    3-Tier 라우팅 구조를 위해 질문의 Tier를 결정합니다.
    Tier 0 (Fast Track): 금액/계약/법령 의도 없고 순수 업체검색.
    Tier 1 (General): 금액 + 수의계약/계약 가능성 질문, 품목/지역업체 선호 없음.
    Tier 2 (Deep Research): 금액 + 품목 + 지역업체 선호 또는 지역상품 구매전략.
    Tier 3 (Agency Specific): 특정 기관 자체규정(공기업/출자출연/부산교통공사 등)이 명확할 때.
    """
    if not intent_labels:
        intent_labels = []

    has_amount = any(w in user_message for w in ["천만원", "백만원", "억원", "금액", "예산", "만원"])
    has_local = any(w in user_message for w in ["지역업체", "부산업체", "부산 업체", "지역 업체", "부산상품", "지역상품"])
    has_item = any(w in user_message for w in ["컴퓨터", "물품", "CCTV", "구매", "조명"])
    has_agency = any(w in user_message for w in ["부산교통공사", "공기업", "출자출연", "시설공단", "환경공단"])

    # Tier 3: 기관명 패턴이 명확할 때만 (단순 "공사"는 오탐 우려로 제외)
    if has_agency:
        return 3

    # Tier 2: 금액 + 품목 + 지역업체 선호
    if has_amount and has_local and has_item:
        return 2

    # Tier 0: 금액이 없고, 특정 위험 요소가 없는 순수 업체 검색
    if not has_amount and risk_info.get("risk_level") == "low" and any(i in intent_labels for i in ["company_search"]):
        return 0

    # Tier 1: 그 외 금액이 있거나, 수의계약 등 일반적인 계약 검토 질문
    return 1

def generate_mandatory_mcp_plan(user_message: str, tier: int) -> list:
    """Tier 1/2 쿼리에 대해 필수적으로 호출해야 할 MCP 계획을 생성합니다."""
    if tier == 1:
        return [
            {"name": "search_law", "args": {"query": "지방계약법 시행령 제25조 수의계약"}},
            {"name": "search_admin_rule", "args": {"query": "지방자치단체 입찰 및 계약집행기준 수의계약 요령"}},
        ]
    elif tier == 2:
        return [
            {"name": "chain_law_system", "args": {"query": "지방계약법 물품 구매 지역제한 제한경쟁"}},
            {"name": "chain_procedure_detail", "args": {"query": "지방자치단체 물품 구매 지역제한 MAS 2단계 경쟁"}},
            {"name": "chain_ordinance_compare", "args": {"query": "부산광역시 지역상품 우선구매 조례"}},
            {"name": "search_admin_rule", "args": {"query": "지방자치단체 입찰시 낙찰자 결정기준 물품 적격심사 지역업체"}},
            {"name": "search_admin_rule", "args": {"query": "조달청 내자구매업무 처리규정"}},
            {"name": "search_admin_rule", "args": {"query": "물품 다수공급자계약 업무처리규정"}}
        ]
    return []
