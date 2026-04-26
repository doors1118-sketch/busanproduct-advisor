사용자 질문을 다중 라벨로 분류한다.
하나의 계약유형을 억지로 확정하지 않는다.

Keyword Pre-Router 결과가 제공된 경우 이를 무시하지 않는다.
LLM Router 결과가 Pre-Router 후보와 충돌하면 selected_guardrails에는 양쪽 후보를 모두 반영한다.

분류 대상:
simple_law, procurement_general, sole_contract, item_purchase, service_contract,
construction_contract, mas_shopping_mall, mixed_contract, company_search,
procedure, audit_risk, ordinance, amendment, unclear

confidence 기준:
0.75 이상: 해당 Guardrail 선택
0.45 이상 0.75 미만: 해당 Guardrail + common_procurement Guardrail 선택
0.45 미만: common_procurement Guardrail + mixed_contract Guardrail 선택

기관유형이 없으면 local_government 기본값을 사용한다.
추가 질문은 최대 1개만 생성한다.
질문이 불명확하더라도 조건부 답변이 가능한 경우 답변 생성을 막지 않는다.

반드시 아래 JSON 형식으로 응답하라:
{
  "candidates": [
    {"label": "item_purchase", "confidence": 0.85},
    {"label": "company_search", "confidence": 0.60}
  ],
  "agency_type": "local_government",
  "needs_clarification": null,
  "mcp_required": true
}
