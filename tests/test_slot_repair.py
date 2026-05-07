import pytest
from app.router.intent_schema import RouterResult, RouterSlots
from app.router.slot_repair import repair_slots

def test_slot_repair_led_100m():
    query = "LED조명 1억원 구매 방법 알려줘"
    router_result = RouterResult(
        primary_intent="out_of_scope",
        routing_decision="clarification_required",
        slots=RouterSlots()
    )
    
    result = repair_slots(query, router_result)
    
    assert result.slots.amount == 100000000
    assert result.slots.item_name == "LED조명"
    assert result.slots.contract_object == "goods"
    assert result.routing_decision == "contract_review_flow"
    assert result.primary_intent == "contract_review"

def test_slot_repair_women_40m_1quote():
    query = "여성기업 4천만원 1인 견적 검토해줘"
    router_result = RouterResult(
        primary_intent="out_of_scope",
        routing_decision="clarification_required",
        slots=RouterSlots()
    )
    
    result = repair_slots(query, router_result)
    
    assert result.slots.amount == 40000000
    assert result.slots.company_type == "women"
    assert result.slots.quote_type == "1_quote"
    assert result.routing_decision == "local_purchase_support_flow"
    assert result.primary_intent == "local_purchase_support"

def test_slot_repair_general_30m_2quote():
    query = "일반기업 3천만원 2인 견적 가능해?"
    router_result = RouterResult(
        primary_intent="out_of_scope",
        routing_decision="clarification_required",
        slots=RouterSlots()
    )
    
    result = repair_slots(query, router_result)
    
    assert result.slots.amount == 30000000
    assert result.slots.company_type == "general"
    assert result.slots.quote_type == "2_quote"
    assert result.routing_decision == "contract_review_flow"
    assert result.primary_intent == "contract_review"

def test_slot_repair_computer_busan_search():
    query = "컴퓨터 부산 업체 찾아줘"
    router_result = RouterResult(
        primary_intent="out_of_scope",
        routing_decision="clarification_required",
        slots=RouterSlots(location="부산") # LLM이 지역만 잡아낸 상황 가정
    )
    
    result = repair_slots(query, router_result)
    
    assert result.slots.item_name == "컴퓨터"
    assert result.slots.location == "부산" # 기존 값 유지
    assert result.slots.candidate_lookup_requested is True
    assert result.candidate_lookup_required is True
    assert result.routing_decision == "candidate_search_flow"
    assert result.primary_intent == "candidate_search"

def test_slot_repair_idempotency():
    query = "여성기업 1억원"
    router_result = RouterResult(
        primary_intent="out_of_scope",
        routing_decision="clarification_required",
        slots=RouterSlots()
    )
    
    repaired_1 = repair_slots(query, router_result)
    assert repaired_1.slots.company_type == "women"
    assert repaired_1.slots.amount == 100000000
    
    reason_1 = repaired_1.reason
    
    # second call
    repaired_2 = repair_slots(query, repaired_1)
    assert repaired_2.reason == reason_1

def test_slot_repair_out_of_scope_promotion():
    query = "부산업체로 1억짜리 LED조명 사려면?"
    router_result = RouterResult(
        primary_intent="out_of_scope",
        routing_decision="out_of_scope", # Gemini incorrectly returned out_of_scope
        slots=RouterSlots()
    )
    
    result = repair_slots(query, router_result)
    assert result.slots.amount == 100000000
    assert result.slots.item_name == "LED조명"
    assert result.routing_decision == "local_purchase_support_flow"
