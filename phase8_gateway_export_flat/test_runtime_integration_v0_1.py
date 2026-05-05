import json
import pytest
from app.runtime.chatbot_orchestrator import run_chatbot_runtime
from app.runtime.runtime_schema import ChatbotRuntimeRequest

def test_runtime_integration_success():
    """
    Orchestrator -> Amount Layer -> Evidence Context Loader -> Evidence Answer Builder
    전체 통합 파이프라인 검증
    """
    
    # 1. Mock Router Result for Intent Router (Gemini 의존성 우회)
    # 정책기업 + 1인 견적 + 4000만원 수의계약 케이스
    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "amount": 40000000,
            "contract_method": "direct_contract",
            "company_type": "women",
            "quote_type": "1_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    
    request = ChatbotRuntimeRequest(
        user_query="여성기업 4천만원 수의계약 가능한가요?",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    
    # 2. 실행
    response = run_chatbot_runtime(request)
    
    # 3. 전체 상태 및 Stage 검증
    assert response.runtime_status == "success"
    assert response.answer_output is not None
    assert response.answer_output.fallback_applied is False
    assert response.answer_output.forbidden_phrase_scan_passed is True
    
    stages = {s.stage_name: s.status for s in response.runtime_stages}
    assert stages.get("rule_engine") == "success"
    assert stages.get("evidence_context") == "success"
    assert stages.get("answer_builder") == "success"
    
    md = response.answer_output.rendered_markdown
    
    # 4. Threshold 노출 및 레이블 검증
    assert "적용 기준" in md
    assert "정책기업 1인 견적 기준" in md
    assert "50,000,000원" in md
    assert "P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD" not in md # 내부 파라미터 미노출
    
    # 5. 수치 마스킹 우회 여부 검증 (50,000,000원이 필터에 걸리지 않아야 함)
    assert "[수치 확인 필요]" not in md
    
    # 6. 원문 200자 축약 및 key_articles 로드 검증
    # 소액수의계약 룰이 활성화되었으므로 원문이 있어야 함
    assert "관련 조문 발췌 보기" in md
    assert "너무 긴 원문은 가독성을 위해 축약되었습니다" in md or "<details>" in md
    
    # 7. expected_value_hint 미노출 검증
    assert "expected_value_hint" not in md

def test_runtime_integration_forbidden_phrase_scan_final():
    """
    통합 런타임 결과 전체에 대한 금지어 스캔이 동작하는지 검증
    """
    
    # 의도적으로 금지어를 location 슬롯에 넣어 Company API 검색 조건에 반영시킨다.
    # 이렇게 하면 응답 markdown에 검색 조건으로 "계약 가능합니다"가 포함되어 필터에 걸려야 한다.
    mock_gemini_response = {
        "primary_intent": "candidate_search",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "candidate_lookup_requested": True,
            "location": "계약 가능합니다"
        },
        "routing_decision": "candidate_search_flow"
    }
    
    request = ChatbotRuntimeRequest(
        user_query="계약 가능합니다 지역 업체 찾아줘",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    
    response = run_chatbot_runtime(request)
    
    # 금지어가 포함되어 fallback이 적용되었는지 확인 (forbidden phrase는 degraded 상태 산출)
    assert response.runtime_status == "degraded"
    assert response.fallback_applied is True
    assert "일시적으로 답변이 제한되었습니다" in response.answer_output.rendered_markdown
    assert response.answer_output.forbidden_phrase_scan_passed is False
    assert "계약 가능합니다" in response.answer_output.blocked_phrases_found


def test_runtime_integration_general_30m_2quote():
    """일반기업 3천만원 2인 견적 -> direct small amount 배제 확인"""
    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "amount": 30000000,
            "contract_method": "direct_contract",
            "company_type": "general",
            "quote_type": "2_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    request = ChatbotRuntimeRequest(
        user_query="일반기업 3천만원 2인 견적",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    assert response.runtime_status == "success"
    md = response.answer_output.rendered_markdown
    # 일반 2천만원 수의계약 기준이 '배제'되었음을 안내하는 문구가 있어야 함
    assert "일반 소액수의계약 우선 경로 배제 검토" in md


def test_runtime_integration_small_business_80m_2quote():
    """소기업 8천만원 2인 견적 -> 1억원 기준 적용 확인"""
    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "amount": 80000000,
            "contract_method": "direct_contract",
            "company_type": "small_business",
            "quote_type": "2_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    request = ChatbotRuntimeRequest(
        user_query="소기업 8천만원 2인 견적",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    assert response.runtime_status == "success"
    md = response.answer_output.rendered_markdown
    assert "100,000,000원" in md
    assert "소기업·소상공인 등 수의계약 기준" in md


def test_runtime_integration_competitive_bid():
    """competitive_bid 명시 -> direct contract branch 미활성 확인"""
    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "amount": 30000000,
            "contract_method": "competitive_bid",
            "company_type": "general",
            "quote_type": "1_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    request = ChatbotRuntimeRequest(
        user_query="경쟁입찰 3천만원",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    assert response.runtime_status == "success"
    md = response.answer_output.rendered_markdown
    # 수의계약 금액 기준 미노출
    assert "적용 기준" not in md


def test_runtime_integration_review_all_routes():
    """review_all_routes=True -> 명시적 경쟁입찰에서도 전체경로 검토 확인"""
    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "amount": 30000000,
            "contract_method": "competitive_bid",
            "company_type": "women",
            "quote_type": "1_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    request = ChatbotRuntimeRequest(
        user_query="여성기업 경쟁입찰 3천만원 가능한가요?",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True, "review_all_routes": True},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    assert response.runtime_status == "success"
    md = response.answer_output.rendered_markdown
    # 경쟁입찰 명시했지만 review_all_routes 덕분에 수의계약 기준 검토됨
    assert "정책기업 1인 견적 기준" in md
    assert "50,000,000원" in md


def test_runtime_integration_unresolved_numeric_mock(tmp_path):
    """unresolved numeric mock -> threshold와 조문 발췌 미출력 확인"""
    # 1. 임시 Source Map 생성 (display_allowed: False)
    source_map = {
        "R_DIRECT_GENERAL_SMALL_AMOUNT": {
            "rule_id": "R_DIRECT_GENERAL_SMALL_AMOUNT",
            "rule_type": "AMOUNT_THRESHOLD",
            "display_name": "일반 물품·용역 수의계약",
            "display_level": "source_verified",
            "numeric_parameters": [
                {
                    "parameter_ref": "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD",
                    "display_allowed": False,
                    "requires_manual_numeric_verification": True,
                    "parameter_status": "requires_verification",
                    "resolved_value": 20000000
                }
            ]
        }
    }
    source_map_path = tmp_path / "mock_source_map.json"
    source_map_path.write_text(json.dumps(source_map, ensure_ascii=False), encoding="utf-8")

    mock_gemini_response = {
        "primary_intent": "local_purchase_support",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "amount": 10000000,
            "contract_method": "direct_contract",
            "company_type": "general",
            "quote_type": "2_quote"
        },
        "routing_decision": "local_purchase_support_flow"
    }
    
    # 20M 이하 일반 물품 -> R_DIRECT_GENERAL_SMALL_AMOUNT 트리거됨
    request = ChatbotRuntimeRequest(
        user_query="일반물품 1천만원 수의계약",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True, "source_map_path": str(source_map_path)},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    assert response.runtime_status == "success"
    md = response.answer_output.rendered_markdown
    # Threshold 출력 안됨
    assert "적용 기준" not in md
    # 수치 미검증 문구 포함
    assert "(수치 기준은 최신 법령 원문 확인 필요)" in md
    # 원문 조문 발췌 보기 숨김 처리
    assert "조문 발췌 보기" not in md


def test_runtime_integration_candidate_search_success():
    """candidate search + company API success -> 후보표 + final scan 확인"""
    mock_gemini_response = {
        "primary_intent": "candidate_search",
        "secondary_intents": [],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "item_name": "컴퓨터",
            "candidate_lookup_requested": True,
            "location": "부산"
        },
        "routing_decision": "candidate_search_flow"
    }
    request = ChatbotRuntimeRequest(
        user_query="컴퓨터 업체 찾아줘",
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True},
        mock_gemini_response=mock_gemini_response
    )
    response = run_chatbot_runtime(request)
    assert response.runtime_status == "success"
    md = response.answer_output.rendered_markdown
    assert "검토 후보 업체" in md
    assert "가나다***" in md
    assert "라마바***" in md
    # Final scan passed
    assert response.answer_output.forbidden_phrase_scan_passed is True
