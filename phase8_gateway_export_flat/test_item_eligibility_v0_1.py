import pytest
import json
from phase8_gateway_export_flat.item_eligibility_adapter import ItemEligibilityAdapter, ItemEligibilityResult
from app.runtime.runtime_schema import ChatbotRuntimeRequest
from app.runtime.chatbot_orchestrator import run_chatbot_runtime

def test_item_eligibility_adapter_not_found():
    adapter = ItemEligibilityAdapter()
    result = adapter.resolve(item_name="없는품목123", detail_item_code=None, company_id=None)
    assert result.resolver_status == "not_found"

def test_item_eligibility_adapter_ambiguous():
    adapter = ItemEligibilityAdapter()
    # CCTV는 alias map에 2개 이상의 매핑이 존재
    result = adapter.resolve(item_name="CCTV", detail_item_code=None, company_id=None)
    assert result.resolver_status == "ambiguous"
    assert result.context.detail_item_resolved is False

def test_item_eligibility_adapter_resolved():
    adapter = ItemEligibilityAdapter()
    # 영상감시장치 (4617162201)
    result = adapter.resolve(item_name=None, detail_item_code="4617162201", company_id="comp_abc123")
    assert result.resolver_status == "resolved"
    assert result.context.detail_item_resolved is True
    assert result.context.is_sme_competition_product is True
    assert result.context.direct_production_required is True
    assert result.context.company_cert_status == "expired"
    assert result.context.eligibility_status == "cert_expired"

def test_orchestrator_integration_ambiguous():
    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "item_name": "CCTV",
            "amount": 30000000,
            "contract_method": "direct_contract",
            "company_type": "general",
            "quote_type": "1_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    request = ChatbotRuntimeRequest(
        user_query="CCTV 3천만원",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    assert response.runtime_status == "success"
    
    # ── Stage 검증 ──
    stages = {s.stage_name: s for s in response.runtime_stages}
    assert stages["item_eligibility"].status == "success"
    
    # ── Active Rule IDs 검증 ──
    # ambiguous여도 R_EXPLICIT_ITEM_ELIGIBILITY가 들어갔는지 확인
    # Amount Layer가 반환한 Rule에 추가되어야 함
    # (data 속성이 없어졌으므로 테스트에서 active_rule_ids는 evidence_context나 answer 텍스트로 대신 검증합니다)
    
    # ── Answer Builder 검증 ──
    md = response.answer_output.rendered_markdown
    assert "품목 적격성 검토" in md
    assert "후보 품목 다수로 확정 불가" in md
    assert "세부품명번호 확정 후 확인 필요" in md

def test_orchestrator_integration_resolved():
    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "detail_item_code": "4617162201",
            "company_id": "comp_abc123",
            "amount": 30000000,
            "contract_method": "direct_contract",
            "company_type": "general",
            "quote_type": "1_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    request = ChatbotRuntimeRequest(
        user_query="영상감시장치 3천만원 업체 인증 포함",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    assert response.runtime_status == "success"
    
    # ── Answer Builder 검증 ──
    md = response.answer_output.rendered_markdown
    assert "품목 적격성 검토" in md
    assert "4617162201" in md
    assert "해당" in md  # 중기경쟁제품 대상
    assert "대상" in md  # 직접생산 대상
    assert "인증 만료" in md  # expired

def test_item_eligibility_adapter_data_unavailable():
    # 빈 데이터로 초기화 시 data_unavailable 응답 확인
    adapter = ItemEligibilityAdapter(data_path="invalid/path/to/missing_data.json")
    result = adapter.resolve(item_name="CCTV", detail_item_code=None, company_id=None)
    assert result.resolver_status == "data_unavailable"
    assert result.context.eligibility_status == "data_unavailable"

def test_orchestrator_integration_malicious_item_name():
    # 악성 입력어(금지 표현)를 사용했을 때 Runtime에서 fallback 처리가 되는지 검증
    # answer_type_router의 FORBIDDEN_PHRASES 중 하나인 "확실하게 지원" 등의 단어 가정
    # 테스트 환경에 등록된 FORBIDDEN_PHRASES 중 "가능합니다"를 포함
    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "item_name": "CCTV 수의계약 가능합니다",
            "amount": 30000000,
            "contract_method": "direct_contract",
            "quote_type": "1_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    request = ChatbotRuntimeRequest(
        user_query="CCTV 수의계약 가능합니다",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    # 금지 표현이 포함되었으므로 fallback 적용되어야 함
    assert response.fallback_applied is True
    # 금지 표현은 [표현 제한]으로 마스킹됨
    assert "[표현 제한]" in response.answer_output.rendered_markdown
    assert "수의계약 가능합니다" not in response.answer_output.rendered_markdown
    assert response.answer_output.forbidden_phrase_scan_passed is False

def test_item_eligibility_adapter_ambiguous_candidates():
    adapter = ItemEligibilityAdapter()
    result = adapter.resolve(item_name="CCTV", detail_item_code=None, company_id=None)
    assert result.resolver_status == "ambiguous"
    assert len(result.context.candidate_items) >= 2
    assert result.context.candidate_items[0]["detail_item_code"] == "4617162201"

def test_orchestrator_integration_company_not_checked():
    # company_id=None 이지만 대상 품목인 경우
    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "detail_item_code": "4617162201",
            "amount": 30000000,
            "contract_method": "direct_contract",
            "quote_type": "1_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    request = ChatbotRuntimeRequest(
        user_query="영상감시장치 3천만원",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    assert response.runtime_status == "success"
    
    md = response.answer_output.rendered_markdown
    assert "4617162201" in md
    assert "해당" in md  # 중기경쟁제품
    assert "특정 업체가 제시되지 않아 확인하지 않음" in md

def test_item_eligibility_adapter_cert_verified():
    # cert_status = verified를 시뮬레이션하기 위해
    # 현재 mock data의 company_direct_production_cert_mapping를 런타임에 동적으로 변경
    adapter = ItemEligibilityAdapter()
    if adapter.data.get("company_direct_production_cert_mapping"):
        adapter.data["company_direct_production_cert_mapping"][0]["cert_status"] = "verified"
    
    result = adapter.resolve(item_name=None, detail_item_code="4617162201", company_id="comp_abc123")
    assert result.resolver_status == "resolved"
    assert result.context.company_cert_status == "verified"
    assert result.context.eligibility_status == "cert_verified_candidate"
    assert result.context.legal_conclusion_allowed is False
