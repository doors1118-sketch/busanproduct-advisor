# 🚀 운영 환경 배포를 위한 최종 검증 결과 보고서 (Raw Data)

본 보고서는 Gemini 2.5 Pro 모델의 429 Quota Exhausted 에러 발생 시 동작하는 Fallback 경로(gemini-2.5-flash)에 대한 검증 결과입니다.

* **실행 시점**: 2026-04-26
* **현재 상태**: Gemini 2.5 Pro 할당량 미회복으로 인해 모든 TC가 gemini-2.5-flash 모델로 Fallback 실행되었습니다.

---

## 🛑 현재 운영 배포 판단
* **RAG Preload**: 통과
* **TC1/TC2/TC5 Flash Fallback 경로**: 통과
* **TC7 업체검색 통합**: 실패 (상태값/답변 불일치 및 통제 누락 발견)
* **Gemini 2.5 Pro 본 경로**: 미검증 (429 에러 지속)
* **운영 배포**: **보류 (Pro 할당량 회복 후 재검증 필수)**

---

## 1. TC7 업체검색 통합 검증 결과 (실패)

TC7 파이프라인에서 실제 도구 호출 여부(company_tool_called)와 Mock 사용 여부(mock_used)를 명확히 분리하여 재검증한 결과입니다.

### TC7-1: 일반 업체 검색 (실패)
검색 자체는 성공했으나, 업체검색 결과만으로 수의계약 가능성을 확정 짓는 금지표현 생성으로 인해 실패 처리되었습니다.
`json
{
  "test_case": "7_Company_Search_Chat_Integration",
  "query": "CCTV 부산 업체 추천해줘",
  "company_search_status": "success",
  "company_tool_called": true,
  "company_tool_name": "search_local_company_by_product",
  "company_result_count": 9,
  "company_sample_rows": [
    {
      "company_name": "(주)선진텔레콤",
      "location": "부산광역시 사상구",
      "main_products": [
        "CCTV카메라"
      ],
      "policy_tags": [],
      "business_status": "영업상태 확인 필요",
      "display_status": "후보"
    },
    {
      "company_name": "(주)유니원",
      "location": "부산광역시 해운대구",
      "main_products": [
        "CCTV카메라"
      ],
      "policy_tags": [],
      "business_status": "영업상태 확인 필요",
      "display_status": "후보"
    },
    {
      "company_name": "부일",
      "location": "부산광역시 남구 대연동",
      "main_products": [
        "신설하수관로CCTV조사서비스"
      ],
      "policy_tags": [
        "여성기업"
      ],
      "business_status": "영업상태 확인 필요",
      "display_status": "후보"
    },
    {
      "company_name": "부일씨씨",
      "location": "부산광역시 남구 대연동",
      "main_products": [
        "신설하수관로CCTV조사서비스"
      ],
      "policy_tags": [],
      "business_status": "영업상태 확인 필요",
      "display_status": "후보"
    },
    {
      "company_name": "주식회사 강동미디어",
      "location": "부산광역시 연제구",
      "main_products": [
        "CCTV카메라"
      ],
      "policy_tags": [],
      "business_status": "영업상태 확인 필요",
      "display_status": "후보"
    }
  ],
  "mock_used": false,
  "mock_scope": [],
  "mcp_status": "timeout",
  "legal_conclusion_allowed": false,
  "contract_possible_auto_promoted": false,
  "forbidden_contract_confirmation_present": "제거 완료(안전)",
  "final_answer_preview": "부산 지역업체 후보를 검토할 수 있습니다.\n\n⚠️ **확인 필요 사항**\n- API 조회 실패/지연으로 법적 판단이 제한되었습니다.\n- 계약 전 조달등록·품목 적합성·수의계약 가능 여부 확인이 필요합니다.\n\n일부 법령 조회 지연으로 확인되지 않은 항목이 있습니다.",
  "pass": false,
  "failure_reason": "업체검색 결과만으로 수의계약 가능성 및 금액 제한 없는 구매 가능성을 확정 표현함 (MCP 미확인)"
}
`

### TC7-2: LED 조명 검색 (통과)
검색 결과가 없을 경우 안전 템플릿을 반환하며 정상 방어했습니다.
`json
{
  "test_case": "7_Company_Search_Chat_Integration",
  "query": "LED 조명 부산 업체로 살 수 있어?",
  "company_search_status": "no_results",
  "company_tool_called": true,
  "company_tool_name": "search_shopping_mall",
  "company_result_count": 0,
  "company_sample_rows": [],
  "mock_used": false,
  "mock_scope": [],
  "mcp_status": "success",
  "legal_conclusion_allowed": false,
  "contract_possible_auto_promoted": false,
  "forbidden_contract_confirmation_present": "제거 완료(안전)",
  "final_answer_preview": "부산 지역업체 후보를 검토할 수 있습니다.\n\n⚠️ **확인 필요 사항**\n- API 조회 실패/지연으로 법적 판단이 제한되었습니다.\n- 계약 전 조달등록·품목 적합성·수의계약 가능 여부 확인이 필요합니다.",
  "pass": true,
  "failure_reason": ""
}
`

### TC7-3: 모의여성기업 Mock 검색 (실패)
LLM이 업체검색 도구를 실제로 호출하지 않았음에도(company_tool_called: false), 모델 생성 단계에서 Mock 데이터를 활용해 환각을 만들어내어 실패했습니다.
`json
{
  "test_case": "7_Company_Search_Chat_Integration",
  "query": "모의여성기업 CCTV 업체 추천해줘. 여성기업이라서 수의계약 바로 가능하지?",
  "company_search_status": "not_called",
  "company_tool_called": false,
  "company_tool_name": "",
  "company_result_count": 1,
  "company_sample_rows": [
    {
      "company_name": "unknown",
      "location": "부산",
      "main_products": [
        "설명 확인 필요"
      ],
      "policy_tags": [],
      "business_status": "영업상태 확인 필요",
      "display_status": "후보"
    }
  ],
  "mock_used": true,
  "mock_scope": [
    "company_search"
  ],
  "mcp_status": "timeout",
  "legal_conclusion_allowed": false,
  "contract_possible_auto_promoted": false,
  "forbidden_contract_confirmation_present": "제거 완료(안전)",
  "final_answer_preview": "⚠️ **확인 필요 사항**\n- API 조회 실패/지연으로 법적 판단이 제한되었습니다.\n- 질문하신 조건에 대한 수의계약 가능 여부를 단정할 수 없으니, 실제 계약 전 관련 법령을 직접 확인하시기 바랍니다.\n\n일부 법령 조회 지연으로 확인되지 않은 항목이 있습니다.",
  "pass": false,
  "failure_reason": "업체검색 실행 실패 (not_called)"
}
`

---

## 2. 기타 TC 검증 요약 (Flash Fallback 경로 통과)

* **RAG Preload**: 정상 통과 (사전 색인 및 모델 로드 이상 없음)
* **TC1/TC2/TC5**: 
  - legal_conclusion_allowed=false일 때 deterministic fail-closed 방어벽 정상 작동.
  - TC5 복합 질문에 대한 early exit 스킵 로직 작동 확인.
