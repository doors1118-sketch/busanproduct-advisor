import pytest
import os
import uuid
import json
from dataclasses import asdict
from jsonschema import validate
from app.gateway.db.reader import ReadOnlyDatabase
from app.gateway.models.slots import GatewayRequest, SlotValues
from app.gateway.gateway import resolve_context

@pytest.fixture
def real_db_reader():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'data', 'legal_db_v0_1_3.sqlite')
    if not os.path.exists(db_path):
        pytest.skip(f"Real DB not found at {db_path}, skipping smoke test")
    return ReadOnlyDatabase(db_path)

@pytest.fixture
def response_schema():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(base_dir, 'app', 'data', 'phase8_gateway_response_schema.json')
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_real_db_smoke(real_db_reader, response_schema):
    # 1. Query that will hit all resolvers normally
    req = GatewayRequest(
        request_id=str(uuid.uuid4()),
        user_query="직접생산확인 가능한 업체 찾아줘",
        slots=SlotValues(
            item_name="가구", 
            location="부산", 
            buyer_type=None, 
            contract_object="goods", 
            amount=None, 
            procurement_route="mas", 
            contract_method=None, 
            detail_item_code=None, 
            company_id=None
        )
    )
    
    resp = resolve_context(req, db_reader=real_db_reader)
    
    # Invariant: Source Resolver returns at least 1 entry (assuming 'local_government' base rule exists)
    assert len(resp.source_context.sources) > 0
    
    # Verify fallback properties for buyer_type=None
    assert resp.source_context.buyer_type_confidence == "low"
    assert "buyer_type" in resp.source_context.required_slots_missing
    
    # Invariant: All sources have active_for_rule=True
    for s in resp.source_context.sources:
        assert s.active_for_rule is True
        
    # Invariant: All procedure sources have usage='procedure_guidance_only'
    for p in resp.procedure_context.sources:
        assert p.usage == "procedure_guidance_only"
        
    # Invariant: Procedure Context has judgment_eligible=False
    assert resp.procedure_context.judgment_eligible is False
    
    # dual_routing check if overlay exists
    if resp.route_context.overlay_applied:
        assert resp.route_context.dual_routing is True
    
    # Schema validation
    validate(instance=asdict(resp), schema=response_schema)
    
    # 2. Query without procurement_route to check overlay logic
    req2 = GatewayRequest(
        request_id=str(uuid.uuid4()),
        user_query="일반",
        slots=SlotValues(
            item_name="가구", 
            location="부산", 
            buyer_type=None, 
            contract_object=None, 
            amount=None, 
            procurement_route=None, 
            contract_method=None, 
            detail_item_code=None, 
            company_id=None
        )
    )
    resp2 = resolve_context(req2, db_reader=real_db_reader)
    
    # Invariant: overlay_applied=False and sources=[] when route is None
    assert resp2.route_context.overlay_applied is False
    assert resp2.route_context.overlay_sources == []
    assert resp2.route_context.dual_routing is False
    
    # Schema validation for resp2
    validate(instance=asdict(resp2), schema=response_schema)
