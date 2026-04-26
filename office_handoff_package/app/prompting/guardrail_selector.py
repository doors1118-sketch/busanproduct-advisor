"""
Guardrail Selector — Intent/Keyword 결과 기반 가드레일 파일 선택
"""
from .schemas import KeywordRouteResult, IntentRouteResult

# 라벨 → guardrail 파일명 매핑
_LABEL_TO_GUARDRAIL = {
    "item_purchase": "item_purchase",
    "service_contract": "service_contract",
    "construction_contract": "construction_contract",
    "mas_shopping_mall": "mas_shopping_mall",
    "mixed_contract": "mixed_contract",
    "company_search": "company_search",
    "procurement_general": "common_procurement",
    "sole_contract": "common_procurement",
    "procedure": "common_procurement",
    "audit_risk": "common_procurement",
    "ordinance": "common_procurement",
    "amendment": "common_procurement",
    "simple_law": "common_procurement",
    "unclear": "common_procurement",
}


def select_guardrails(
    intent_result: IntentRouteResult,
    keyword_result: KeywordRouteResult,
) -> list[str]:
    """confidence 기반 가드레일 선택"""
    selected = set()

    for candidate in intent_result.candidates:
        guardrail = _LABEL_TO_GUARDRAIL.get(candidate.label, "common_procurement")

        if candidate.confidence >= 0.75:
            selected.add(guardrail)
        elif candidate.confidence >= 0.45:
            selected.add(guardrail)
            selected.add("common_procurement")
        else:
            selected.add("common_procurement")
            selected.add("mixed_contract")

    # forced guardrails (Pre-Router에서 강제)
    for g in keyword_result.forced_guardrails:
        guardrail = _LABEL_TO_GUARDRAIL.get(g, g)
        selected.add(guardrail)

    # common_procurement는 항상 포함
    selected.add("common_procurement")

    return sorted(selected)
