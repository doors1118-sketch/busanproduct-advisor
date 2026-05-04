import pytest
import os
import json
import sqlite3
import uuid
from dataclasses import asdict
from jsonschema import validate

from app.gateway import resolve_context, GatewayRequest, SlotValues
from app.gateway.db.reader import ReadOnlyDatabase

def test_gateway_skeleton_schema_and_logic():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(base_dir, 'app', 'data', 'phase8_gateway_response_schema.json')
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)
        
    req = GatewayRequest(
        request_id=str(uuid.uuid4()),
        user_query="CCTV 구매 절차",
        slots=SlotValues(
            buyer_type=None,
            contract_object="goods",
            amount=50000000,
            procurement_route=None,
            contract_method=None,
            item_name="CCTV",
            detail_item_code=None,
            company_id=None,
            location="부산"
        )
    )
    
    resp = resolve_context(req)
    resp_dict = asdict(resp)
    
    # 1. Schema Validation
    validate(instance=resp_dict, schema=schema)
    
    # 2. Procedure Context 제약
    assert resp.procedure_context.judgment_eligible is False
    
    # 3. Source Context 제약
    for src in resp.source_context.sources:
        assert src.active_for_rule is True
        
    # 4. 상태 정합성
    assert resp.metadata.item_eligibility_resolver_status == resp.item_eligibility_result.resolver_status
    if resp.item_eligibility_result.context:
        assert resp.metadata.item_eligibility_trigger_grade == resp.item_eligibility_result.context.trigger_grade
        
    if resp.company_candidate_context:
        assert resp.metadata.enrichment_applied == resp.company_candidate_context.enrichment_applied
        assert resp.metadata.enrichment_scope == resp.company_candidate_context.enrichment_scope
        
    # 5. 금지 표현 미포함
    prohibited = ["계약 가능합니다", "구매 가능합니다", "수의계약 가능합니다", "지역제한 가능합니다", "낙찰 가능합니다"]
    resp_str = json.dumps(resp_dict, ensure_ascii=False)
    for phrase in prohibited:
        assert phrase not in resp_str

def test_gateway_triggers_and_enrichment():
    # 1. "CCTV 업체 추천" -> silent trigger
    req1 = GatewayRequest(
        request_id=str(uuid.uuid4()),
        user_query="CCTV 업체 추천",
        slots=SlotValues(item_name="CCTV", location="부산", buyer_type=None, contract_object=None, amount=None, procurement_route=None, contract_method=None, detail_item_code=None, company_id=None)
    )
    resp1 = resolve_context(req1)
    assert resp1.item_eligibility_result.resolver_status == "resolved"
    assert resp1.item_eligibility_result.context.trigger_grade == "silent"
    
    # 2. "CCTV 구매 절차" -> silent trigger
    req2 = GatewayRequest(
        request_id=str(uuid.uuid4()),
        user_query="CCTV 구매 절차",
        slots=SlotValues(item_name="CCTV", location="부산", buyer_type=None, contract_object=None, amount=None, procurement_route=None, contract_method=None, detail_item_code=None, company_id=None)
    )
    resp2 = resolve_context(req2)
    assert resp2.item_eligibility_result.resolver_status == "resolved"
    assert resp2.item_eligibility_result.context.trigger_grade == "silent"
    
    # 3. "CCTV 직생도 봐줘" -> explicit trigger
    req3 = GatewayRequest(
        request_id=str(uuid.uuid4()),
        user_query="CCTV 직생도 봐줘",
        slots=SlotValues(item_name="CCTV", location="부산", buyer_type=None, contract_object=None, amount=None, procurement_route=None, contract_method=None, detail_item_code=None, company_id=None)
    )
    resp3 = resolve_context(req3)
    assert resp3.item_eligibility_result.resolver_status == "resolved"
    assert resp3.item_eligibility_result.context.trigger_grade == "explicit"
    
    # 4. enrichment_applied=False이면 enrichment_scope is None
    req4 = GatewayRequest(
        request_id=str(uuid.uuid4()),
        user_query="그냥 업체 찾아줘",
        slots=SlotValues(item_name="기타", location="부산", buyer_type=None, contract_object=None, amount=None, procurement_route=None, contract_method=None, detail_item_code=None, company_id=None)
    )
    resp4 = resolve_context(req4)
    if resp4.company_candidate_context:
        assert resp4.company_candidate_context.enrichment_applied is False
        assert resp4.company_candidate_context.enrichment_scope is None

    # 5. "소프트웨어 중기경쟁 확인해줘" -> ambiguous
    req5 = GatewayRequest(
        request_id=str(uuid.uuid4()),
        user_query="소프트웨어 중기경쟁 확인해줘",
        slots=SlotValues(item_name="소프트웨어", location="부산", buyer_type=None, contract_object=None, amount=None, procurement_route=None, contract_method=None, detail_item_code=None, company_id=None)
    )
    resp5 = resolve_context(req5)
    assert resp5.item_eligibility_result.resolver_status == "ambiguous"
    
    # 6. "부산 펌프 업체 추천해줘" -> enrichment_applied == True, enrichment_scope == "general"
    req6 = GatewayRequest(
        request_id=str(uuid.uuid4()),
        user_query="부산 펌프 업체 추천해줘",
        slots=SlotValues(item_name="펌프", location="부산", buyer_type=None, contract_object=None, amount=None, procurement_route=None, contract_method=None, detail_item_code=None, company_id=None)
    )
    resp6 = resolve_context(req6)
    if resp6.company_candidate_context:
        assert resp6.company_candidate_context.enrichment_applied is True
        assert resp6.company_candidate_context.enrichment_scope == "general"

def test_db_reader_mutation_block(tmp_path):
    # create dummy db
    db_file = tmp_path / "dummy.sqlite"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE test (id int)")
    conn.close()
    
    reader = ReadOnlyDatabase(str(db_file))
    
    # regex block test
    with pytest.raises(ValueError, match="Prohibited SQL keyword"):
        reader.execute("INSERT INTO test VALUES (1)")
        
    # query check block test
    with pytest.raises(ValueError, match="Only SELECT or WITH"):
        reader.execute("SHOW TABLES")
        
    # PRAGMA/authorizer block test: We can bypass regex to test authorizer directly by using execute on cursor
    cursor = reader.conn.cursor()
    with pytest.raises(sqlite3.DatabaseError):
        cursor.execute("UPDATE test SET id=2")
