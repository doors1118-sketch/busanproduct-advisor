import uuid
from typing import Optional
from app.gateway.models.slots import GatewayRequest
from app.gateway.models.context import GatewayResponse, GatewayMetadata
from app.gateway.resolvers.source_resolver import resolve_sources
from app.gateway.resolvers.route_resolver import resolve_routes
from app.gateway.resolvers.procedure_resolver import resolve_procedures
from app.gateway.resolvers.item_resolver import resolve_item_eligibility
from app.gateway.resolvers.company_resolver import resolve_company_candidates
from app.gateway.db.reader import ReadOnlyDatabase

def resolve_context(request: GatewayRequest, db_reader: Optional['ReadOnlyDatabase'] = None) -> GatewayResponse:
    
    if not db_reader:
        import os
        from app.gateway.db.reader import ReadOnlyDatabase
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'legal_db_v0_1_3.sqlite')
        if os.path.exists(db_path):
            db_reader = ReadOnlyDatabase(db_path)
    
    # 1. Source
    source_ctx = resolve_sources(
        buyer_type=request.slots.buyer_type,
        contract_object=request.slots.contract_object,
        procurement_route=request.slots.procurement_route,
        contract_method=request.slots.contract_method,
        item_name=request.slots.item_name,
        db_reader=db_reader
    )
    
    # 2. Route
    route_ctx = resolve_routes(
        procurement_route=request.slots.procurement_route,
        contract_method=request.slots.contract_method,
        item_name=request.slots.item_name,
        db_reader=db_reader
    )
    
    # 3. Procedure
    procedure_ctx = resolve_procedures(
        buyer_type=request.slots.buyer_type,
        contract_object=request.slots.contract_object,
        procurement_route=request.slots.procurement_route,
        contract_method=request.slots.contract_method,
        procedure_topic=None,
        db_reader=db_reader
    )
    
    # 4. Item
    item_res = resolve_item_eligibility(
        user_query=request.user_query,
        item_name=request.slots.item_name,
        detail_item_code=request.slots.detail_item_code,
        company_id=request.slots.company_id,
        procurement_route=request.slots.procurement_route,
        contract_method=request.slots.contract_method
    )
    
    # 5. Company
    # detail_item_candidates 파싱 정책
    candidates_codes = None
    if item_res.context and item_res.context.detail_item_candidates:
        candidates_codes = [c.get("detail_item_code") for c in item_res.context.detail_item_candidates if "detail_item_code" in c]
        
    company_ctx = resolve_company_candidates(
        item_name=request.slots.item_name,
        location=request.slots.location,
        company_id=request.slots.company_id,
        detail_item_code=request.slots.detail_item_code,
        detail_item_codes_from_candidates=candidates_codes
    )
    
    # Metadata
    # total_sources_matched는 "base + overlay 적용 source 수"를 의미합니다.
    total_sources = len(source_ctx.sources) + len(route_ctx.overlay_sources)
    proc_sources = len(procedure_ctx.sources)
    trigger_grade = None
    if item_res.context:
        trigger_grade = item_res.context.trigger_grade
        
    meta = GatewayMetadata(
        total_sources_matched=total_sources,
        procedure_sources_matched=proc_sources,
        overlay_applied=route_ctx.overlay_applied,
        item_eligibility_resolver_status=item_res.resolver_status,
        item_eligibility_trigger_grade=trigger_grade,
        company_candidates_found=company_ctx.total_found if company_ctx else 0,
        enrichment_applied=company_ctx.enrichment_applied if company_ctx else False,
        enrichment_scope=company_ctx.enrichment_scope if company_ctx else None
    )
    
    return GatewayResponse(
        request_id=request.request_id,
        source_context=source_ctx,
        route_context=route_ctx,
        procedure_context=procedure_ctx,
        item_eligibility_result=item_res,
        company_candidate_context=company_ctx,
        metadata=meta,
        error=None,
        gateway_version="v0.1.1",
        baseline_db="legal_db_v0_1_3.sqlite"
    )
