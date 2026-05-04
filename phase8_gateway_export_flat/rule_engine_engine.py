from app.gateway.models.context import GatewayResponse
from app.rule_engine.decision_context import DecisionContext

def execute_rule_engine(gateway_response: GatewayResponse, request_slots: dict = None) -> DecisionContext:
    # 1. 초기 상태 설정
    ctx = DecisionContext(review_outcome="not_triggered")
    
    # 2. Source Context 수집
    if gateway_response.source_context and gateway_response.source_context.sources:
        for s in gateway_response.source_context.sources:
            ctx.applied_source_ids.append(s.source_id)
            
    if gateway_response.route_context and gateway_response.route_context.overlay_sources:
        for o in gateway_response.route_context.overlay_sources:
            ctx.overlay_source_ids.append(o.source_id)
            
    if gateway_response.procedure_context and gateway_response.procedure_context.sources:
        for p in gateway_response.procedure_context.sources:
            ctx.procedure_source_ids.append(p.source_id)
            
    # 3. Route Context 검사
    if gateway_response.route_context and gateway_response.route_context.overlay_applied:
        ctx.route_directive = "base_law_plus_pps_overlay_review"
        ctx.dual_routing_active = True
        
    # 4. Item / Enrichment 세팅
    item_res = gateway_response.item_eligibility_result
    comp_ctx = gateway_response.company_candidate_context
    
    if comp_ctx and comp_ctx.enrichment_applied:
        ctx.enrichment_available = True
        
    if item_res:
        ctx.item_eligibility_status = item_res.resolver_status
        
    if item_res and item_res.context:
        ctx.item_eligibility_grade = item_res.context.trigger_grade
        if item_res.context.eligibility_status:
            ctx.item_eligibility_status = item_res.context.eligibility_status
        
    # 4.5. Phase 9.1 Local Purchase Support Rule Mapping
    request_slots = request_slots or {}
    contract_object = request_slots.get("contract_object")
    procurement_route = request_slots.get("procurement_route")
    contract_method = request_slots.get("contract_method")
    
    tools = set()
    
    if contract_object == "goods":
        tools.update(["지역제한 경쟁입찰 검토", "수의계약 활용 가능성 검토", "지역상품 우선구매 조례·시책 검토"])
    elif contract_object == "service":
        tools.update(["지역제한 경쟁입찰 검토", "지역업체 참여도 가점 검토", "수의계약 활용 가능성 검토"])
    elif contract_object == "construction":
        tools.update(["지역제한 경쟁입찰 검토", "지역의무공동도급 검토", "지역업체 참여도 가점 검토"])
        
    if procurement_route in ("mas", "pps_shopping_mall", "third_party_unit_price_contract"):
        tools.add("MAS·종합쇼핑몰 내 지역업체 후보 활용 검토")
        
    if contract_method == "direct_contract":
        tools.add("수의계약 활용 가능성 검토")
        
    if item_res and item_res.context and item_res.context.trigger_grade == "explicit":
        tools.add("품목별 중기경쟁제품·직접생산확인 추가 검토")
        
    if gateway_response.source_context and gateway_response.source_context.buyer_type_confidence == "low":
        tools.add("기관유형 확인 필요")
        
    if tools:
        ctx.local_purchase_support_review_required = True
        fixed_order = [
            "기관유형 확인 필요",
            "지역제한 경쟁입찰 검토",
            "지역의무공동도급 검토",
            "지역업체 참여도 가점 검토",
            "지역상품 우선구매 조례·시책 검토",
            "수의계약 활용 가능성 검토",
            "MAS·종합쇼핑몰 내 지역업체 후보 활용 검토",
            "품목별 중기경쟁제품·직접생산확인 추가 검토"
        ]
        ctx.local_purchase_support_tools = [t for t in fixed_order if t in tools]

    # 5. Rule Engine 우선순위 매핑 (1 -> 6)
    
    # 1) out_of_scope: ReviewOutcome에는 있으나 v0.1에서는 emitting rule이 없음.
    # 향후 jurisdiction/scope rule에서 사용할 예정임.
    
    # 2) insufficient_data (buyer_type)
    if gateway_response.source_context and gateway_response.source_context.buyer_type_confidence == "low":
        ctx.review_outcome = "insufficient_data"
        ctx.buyer_type_assumed = True
        if "buyer_type" not in ctx.missing_required_slots:
            ctx.missing_required_slots.append("buyer_type")
        return ctx  # 최우선 순위이므로 즉시 반환
        
    # 2) insufficient_data (item data)
    if item_res and item_res.resolver_status == "data_unavailable":
        ctx.review_outcome = "insufficient_data"
        if "detail_item_code" not in ctx.missing_required_slots:
            ctx.missing_required_slots.append("detail_item_code")
        return ctx
        
    # 3) manual_review_required
    if item_res and item_res.resolver_status == "ambiguous":
        ctx.review_outcome = "manual_review_required"
        ctx.item_action_required = "disambiguate_item"
        ctx.manual_review_reasons.append("detail_item_code_ambiguous")
        return ctx
        
    # 4) & 5) review_candidate & conditional_review
    if item_res and item_res.resolver_status == "resolved" and item_res.context and item_res.context.trigger_grade == "explicit":
        cert_status = item_res.context.company_cert_status
        if cert_status == "valid":
            ctx.review_outcome = "review_candidate"
            ctx.item_action_required = "verify_direct_production_cert"
        elif cert_status == "unknown":
            ctx.review_outcome = "conditional_review"
            ctx.item_action_required = "request_cert_submission"
        else:
            ctx.review_outcome = "conditional_review"
            ctx.item_action_required = "verify_direct_production_cert"
        return ctx
        
    # 6) not_triggered
    ctx.review_outcome = "not_triggered"
    return ctx
