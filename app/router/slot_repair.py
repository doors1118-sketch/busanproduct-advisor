import re
from app.router.intent_schema import RouterResult

try:
    from app.router.intent_normalization import normalize_query_intent
except Exception:  # Runtime path when app/ is on sys.path.
    from router.intent_normalization import normalize_query_intent

def repair_slots(user_query: str, router_result: RouterResult) -> RouterResult:
    """LLM이 누락한 주요 슬롯을 정규식/키워드 기반으로 보정한다."""
    norm = normalize_query_intent(user_query)
    slots = router_result.slots
    repaired_slots = []
    
    # 1. 금액 파싱 (비어있을 때만)
    if not slots.amount:
        if norm.amount is not None:
            slots.amount = norm.amount
            repaired_slots.append("amount")
        else:
            # 가장 흔한 금액 패턴을 앞쪽에 배치
            amount_patterns = [
                (r"100,000,000\s*원?", 100000000),
                (r"1억\s*원?", 100000000),
                (r"50,000,000\s*원?", 50000000),
                (r"5천만\s*원?", 50000000),
                (r"40,000,000\s*원?", 40000000),
                (r"4천만\s*원?", 40000000),
                (r"30,000,000\s*원?", 30000000),
                (r"3천만\s*원?", 30000000),
                (r"3000만\s*원?", 30000000),
            ]
            for pattern, val in amount_patterns:
                if re.search(pattern, user_query):
                    slots.amount = val
                    repaired_slots.append("amount")
                    break
                
    # 2. 기업 유형 (비어있을 때만)
    if not slots.company_type:
        if "여성기업" in user_query:
            slots.company_type = "women"
            repaired_slots.append("company_type")
        elif "일반기업" in user_query:
            slots.company_type = "general"
            repaired_slots.append("company_type")
        elif "소기업" in user_query or "소상공인" in user_query:
            slots.company_type = "small_business"
            repaired_slots.append("company_type")
            
    # 3. 견적 종류 (비어있을 때만)
    if not slots.quote_type:
        if re.search(r"1인\s*견적", user_query) or re.search(r"1인견적", user_query):
            slots.quote_type = "1_quote"
            repaired_slots.append("quote_type")
        elif re.search(r"2인\s*(이상\s*)?견적", user_query) or re.search(r"2인견적", user_query):
            slots.quote_type = "2_quote"
            repaired_slots.append("quote_type")
            
    # 4. 품목명 및 계약목적물
    if norm.item_name:
        normalized_slot_item = "LED조명" if norm.item_name == "LED 조명" else norm.item_name
        if not slots.item_name:
            slots.item_name = normalized_slot_item
            repaired_slots.append("item_name")
        if not slots.contract_object and norm.contract_object:
            slots.contract_object = norm.contract_object
            repaired_slots.append("contract_object")

    items = [
        ("LED조명", "LED조명"), ("LED 조명", "LED 조명"), ("LED", "LED"),
        ("컴퓨터", "컴퓨터"), ("CCTV", "CCTV"),
        ("에어컨", "에어컨"), ("프린터", "프린터"), ("복사기", "복사기"),
        ("가구", "가구"), ("차량", "차량"), ("서버", "서버"),
    ]
    for keyword, item_name_val in items:
        if slots.item_name:
            break
        if keyword in user_query:
            if not slots.item_name:
                slots.item_name = item_name_val
                repaired_slots.append("item_name")
            if not slots.contract_object:
                slots.contract_object = "goods"
                repaired_slots.append("contract_object")
            break
            
    # 5. 업체 조회 의도 및 지역 보정
    if not slots.location:
        if "부산" in user_query:
            slots.location = "부산"
            repaired_slots.append("location")

    if not slots.local_supplier_intent:
        if norm.local_support_requested or re.search(r"(지역업체|부산업체|부산 업체|지역 업체|지역상품|지역제품|지역제한|지역가점)", user_query):
            slots.local_supplier_intent = True
            repaired_slots.append("local_supplier_intent")
            
    if norm.company_lookup_blocked:
        if slots.candidate_lookup_requested:
            slots.candidate_lookup_requested = False
            repaired_slots.append("candidate_lookup_blocked")
        router_result.candidate_lookup_required = False
        router_result.company_lookup_required = False

    if not norm.company_lookup_blocked and not slots.candidate_lookup_requested:
        if norm.company_lookup_requested or re.search(r"업체.*(찾아|추천|알려|있어|있나|있는지|어디|보여|검색|리스트)", user_query):
            slots.candidate_lookup_requested = True
            repaired_slots.append("candidate_lookup_requested")

    if repaired_slots:
        repair_msg = f" | Repaired slots: {repaired_slots} (regex_keyword_rule)"
        current_reason = getattr(router_result, "reason", "") or ""
        if repair_msg not in current_reason:
            router_result.reason = current_reason + repair_msg
        
        if slots.candidate_lookup_requested and slots.item_name:
            router_result.candidate_lookup_required = True
            router_result.company_lookup_required = True
        elif slots.candidate_lookup_requested and not slots.item_name:
            router_result.candidate_lookup_required = False
            router_result.company_lookup_required = False
            
        # 승격(Promotion) 로직
        if router_result.routing_decision in ["clarification_required", "out_of_scope"]:
            has_contract_info = bool(slots.amount or slots.company_type or slots.quote_type)
            has_item = bool(slots.item_name)
            
            POLICY_COMPANY_TYPES = ["women", "disabled", "social", "startup", "small_business"]
            has_local_support = bool(slots.company_type in POLICY_COMPANY_TYPES or "지역" in user_query or "부산" in user_query)
            
            # 업체 조회 의도가 있고 품목이 있으면 mixed_flow 또는 candidate_search_flow로 승격
            if router_result.candidate_lookup_required and has_item:
                if has_contract_info:
                    router_result.routing_decision = "mixed_flow"
                    router_result.primary_intent = "contract_review"
                    if "candidate_search" not in router_result.secondary_intents:
                        router_result.secondary_intents.append("candidate_search")
                else:
                    router_result.routing_decision = "candidate_search_flow"
                    router_result.primary_intent = "candidate_search"
            # 계약 정보(금액, 견적 종류 등)가 있으면
            elif has_contract_info:
                if has_local_support:
                    router_result.routing_decision = "local_purchase_support_flow"
                    router_result.primary_intent = "local_purchase_support"
                else:
                    router_result.routing_decision = "contract_review_flow"
                    router_result.primary_intent = "contract_review"
                    
            # 승격되었다면 clarification_needed 초기화
            if router_result.routing_decision not in ["clarification_required", "out_of_scope"]:
                router_result.clarification_needed = []

        if router_result.candidate_lookup_required and slots.item_name:
            router_result.company_lookup_required = True
        elif router_result.candidate_lookup_required and not slots.item_name:
            router_result.candidate_lookup_required = False
            router_result.company_lookup_required = False
        if slots.local_supplier_intent or "지역" in user_query or "부산" in user_query:
            router_result.local_purchase_support_required = True
            if "부산 지역상품 구매지원 경로" not in router_result.answer_focus:
                router_result.answer_focus.append("부산 지역상품 구매지원 경로")
        if slots.amount or slots.contract_method or slots.quote_type or "계약" in user_query or "입찰" in user_query:
            router_result.legal_review_required = True
            if "법령상 계약 가능 범위와 확인 필요사항" not in router_result.answer_focus:
                router_result.answer_focus.insert(0, "법령상 계약 가능 범위와 확인 필요사항")
        if router_result.company_lookup_required and slots.item_name and "부산 업체·상품 후보 조회" not in router_result.answer_focus:
            router_result.answer_focus.append("부산 업체·상품 후보 조회")
                
    return router_result
