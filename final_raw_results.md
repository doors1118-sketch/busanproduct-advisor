
### scenario_a_raw.json
```json
{
  "answer": "### 1. 질문의도 파악\n\n- 금액(70,000,000원) 기준의 수의계약 가능 여부와 함께 지역업체(부산 등) 활용 방안을 모색하려는 의도로 분석되었습니다.\n\n### 2. 법령 적용 해석\n\n- **금액 한도**: 70,000,000원은 소액 수의계약 한도를 초과합니다. 경쟁입찰 또는 MAS/우수조달물품 등 다른 조달 경로를 검토해야 합니다.\n- **사전 조회 근거**: 시스템에서 다음의 필수 법령 및 매뉴얼 규정을 사전 조회하여 검토 기준에 반영했습니다.\n  - ✔️ chain_procedure_detail:지방자치단체 물품 구매 지역제한 MAS 2단계 경쟁 (689ms)\n  - ✔️ search_admin_rule:지방자치단체 입찰시 낙찰자 결정기준 물품 적격심사 지역업체 (119ms)\n  - ✔️ search_admin_rule:조달청 내자구매업무 처리규정 (132ms)\n  - ✔️ search_admin_rule:물품 다수공급자계약 업무처리규정 (116ms)\n  - ✔️ chain_ordinance_compare:부산광역시 지역상품 우선구매 조례 (1192ms)\n  - ✔️ chain_law_system:지방계약법 물품 구매 지역제한 제한경쟁 (1429ms)\n\n### 3. 구매 방법 안내\n\n**1) 지역제한 제한경쟁입찰**\n- 추정가격이 행안부령 기준 미만이면 지역을 제한한 제한경쟁입찰 공고가 가능합니다.\n\n**2) 다수공급자계약(MAS) 2단계 경쟁 시 지역제한**\n- 종합쇼핑몰 납품요구 시, 2단계 경쟁 대상인 경우 지역제한 규정을 적용할 수 있습니다.\n\n**3) 혁신제품·우수조달물품 우선구매**\n- 해당 품목에 부산업체 생산 혁신/우수조달물품이 있는지 확인하여 수의계약을 검토합니다.\n\n**4) 적격심사 지역업체 가점 부여**\n- 물품 적격심사 세부기준에 따라 지역업체 참여 시 가점 또는 우대 평가를 적용할 수 있습니다.\n\n### 4. 관련 업체 후보 소개\n\n*(아래 표에 검색된 후보 업체 정보가 제공됩니다.)*\n\n### 5. 필수 확인사항\n\n| 확인 항목 | 상태 |\n| :--- | :--- |\n| 기관유형 (지자체/출자출연/국가기관) | 확인 필요 |\n| 추정가격 (VAT 제외 여부) | 확인 필요 |\n| 조달청 등록 및 인증 유효기간 | 확인 필요 |\n| 정책기업 인증 유효성 | 확인 필요 |\n| 기관 내부 계약규정 | 확인 필요 |\n\n⚖️ 본 안내는 검토 경로 제시이며, 법적 효력이 없습니다. 실제 계약 전 적용 법령과 기관 내부 기준을 반드시 확인하세요.\n\n**[시스템 자동 추출 후보 표]**\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 입찰·수의계약 검토용 조달등록 부산업체 후보**\n| 후보유형 | 업체명 | 소재지 | 대표품목/등록상품명 | 조달등록 | 쇼핑몰/MAS | 정책기업 태그 | 인증유형 | 유효기간 | 검토 가능 경로 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 조달등록 | (주) 블루앤시스 | 부산광역시 사상구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주) 애로우윙즈 | 부산광역시 남구 | 컴퓨터지원제조소프트웨어 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)기주건설 | 부산광역시 강서구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)나라기술 | 부산광역시 부산진구 | 컴퓨터지원제조소프트웨어 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)블루햇 | 부산광역시 금정구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)선테크 | 부산광역시 금정구 | 데스크톱컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)세롬 | 부산광역시 부산진구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)세원정보시스템 | 부산광역시 부산진구 | 데스크톱컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)시큐리티즌 | 부산광역시 해운대구 | 컴퓨터네트워크또는인터넷보안서비스 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)쏠비전아이티 | 부산광역시 남구 | 태블릿컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n\n",
  "history": [
    {
      "role": "user",
      "text": "7천만원으로 컴퓨터 구매해야 한다. 가급적 지역업체랑 계약하고 싶은데 방법이 있을까?"
    },
    {
      "role": "model",
      "text": "### 1. 질문의도 파악\n\n- 금액(70,000,000원) 기준의 수의계약 가능 여부와 함께 지역업체(부산 등) 활용 방안을 모색하려는 의도로 분석되었습니다.\n\n### 2. 법령 적용 해석\n\n- **금액 한도**: 70,000,000원은 소액 수의계약 한도를 초과합니다. 경쟁입찰 또는 MAS/우수조달물품 등 다른 조달 경로를 검토해야 합니다.\n- **사전 조회 근거**: 시스템에서 다음의 필수 법령 및 매뉴얼 규정을 사전 조회하여 검토 기준에 반영했습니다.\n  - ✔️ chain_procedure_detail:지방자치단체 물품 구매 지역제한 MAS 2단계 경쟁 (689ms)\n  - ✔️ search_admin_rule:지방자치단체 입찰시 낙찰자 결정기준 물품 적격심사 지역업체 (119ms)\n  - ✔️ search_admin_rule:조달청 내자구매업무 처리규정 (132ms)\n  - ✔️ search_admin_rule:물품 다수공급자계약 업무처리규정 (116ms)\n  - ✔️ chain_ordinance_compare:부산광역시 지역상품 우선구매 조례 (1192ms)\n  - ✔️ chain_law_system:지방계약법 물품 구매 지역제한 제한경쟁 (1429ms)\n\n### 3. 구매 방법 안내\n\n**1) 지역제한 제한경쟁입찰**\n- 추정가격이 행안부령 기준 미만이면 지역을 제한한 제한경쟁입찰 공고가 가능합니다.\n\n**2) 다수공급자계약(MAS) 2단계 경쟁 시 지역제한**\n- 종합쇼핑몰 납품요구 시, 2단계 경쟁 대상인 경우 지역제한 규정을 적용할 수 있습니다.\n\n**3) 혁신제품·우수조달물품 우선구매**\n- 해당 품목에 부산업체 생산 혁신/우수조달물품이 있는지 확인하여 수의계약을 검토합니다.\n\n**4) 적격심사 지역업체 가점 부여**\n- 물품 적격심사 세부기준에 따라 지역업체 참여 시 가점 또는 우대 평가를 적용할 수 있습니다.\n\n### 4. 관련 업체 후보 소개\n\n*(아래 표에 검색된 후보 업체 정보가 제공됩니다.)*\n\n### 5. 필수 확인사항\n\n| 확인 항목 | 상태 |\n| :--- | :--- |\n| 기관유형 (지자체/출자출연/국가기관) | 확인 필요 |\n| 추정가격 (VAT 제외 여부) | 확인 필요 |\n| 조달청 등록 및 인증 유효기간 | 확인 필요 |\n| 정책기업 인증 유효성 | 확인 필요 |\n| 기관 내부 계약규정 | 확인 필요 |\n\n⚖️ 본 안내는 검토 경로 제시이며, 법적 효력이 없습니다. 실제 계약 전 적용 법령과 기관 내부 기준을 반드시 확인하세요.\n\n**[시스템 자동 추출 후보 표]**\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 입찰·수의계약 검토용 조달등록 부산업체 후보**\n| 후보유형 | 업체명 | 소재지 | 대표품목/등록상품명 | 조달등록 | 쇼핑몰/MAS | 정책기업 태그 | 인증유형 | 유효기간 | 검토 가능 경로 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 조달등록 | (주) 블루앤시스 | 부산광역시 사상구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주) 애로우윙즈 | 부산광역시 남구 | 컴퓨터지원제조소프트웨어 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)기주건설 | 부산광역시 강서구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)나라기술 | 부산광역시 부산진구 | 컴퓨터지원제조소프트웨어 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)블루햇 | 부산광역시 금정구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)선테크 | 부산광역시 금정구 | 데스크톱컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)세롬 | 부산광역시 부산진구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)세원정보시스템 | 부산광역시 부산진구 | 데스크톱컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)시큐리티즌 | 부산광역시 해운대구 | 컴퓨터네트워크또는인터넷보안서비스 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)쏠비전아이티 | 부산광역시 남구 | 태블릿컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n\n"
    }
  ],
  "candidate_table_source": "server_structured_formatter",
  "legal_conclusion_allowed": false,
  "contract_possible_auto_promoted": false,
  "forbidden_patterns_remaining_after_rewrite": [],
  "final_answer_scanned": true,
  "sensitive_fields_detected": [],
  "model_selected": "bypass_tier_1_2",
  "model_decision_reason": "",
  "latency_ms": 23485,
  "rag_status": {
    "laws": "SUCCESS",
    "manuals": "SUCCESS",
    "innovation": "SUCCESS"
  },
  "production_deployment": "HOLD",
  "route_guidance_provided": true,
  "regional_route_guidance_provided": true,
  "amount_detected": 70000000,
  "amount_band": "over_50m_under_100m",
  "candidate_counts_by_type": {
    "local_procurement_company": 10,
    "shopping_mall_supplier": 0,
    "policy_company": 0,
    "innovation_product": 0,
    "priority_purchase_product": 0
  },
  "source_call_statuses": {
    "search_shopping_mall": "success",
    "search_local_company_by_product": "success"
  },
  "sensitive_fields_removed": true,
  "enrichment_join_key_redacted": true,
  "total_latency_ms": 23485,
  "rag_elapsed_ms": 0,
  "model_elapsed_ms": 0,
  "rewrite_elapsed_ms": 72,
  "tool_elapsed_ms_by_name": {},
  "tool_call_count": 2,
  "fast_track_applied": false,
  "deterministic_template_used": true,
  "tier_resolved": 2,
  "answer_schema_version": "regional_procurement_v2",
  "mandatory_mcp_plan": [
    {
      "name": "chain_law_system",
      "args": {
        "query": "지방계약법 물품 구매 지역제한 제한경쟁"
      }
    },
    {
      "name": "chain_procedure_detail",
      "args": {
        "query": "지방자치단체 물품 구매 지역제한 MAS 2단계 경쟁"
      }
    },
    {
      "name": "chain_ordinance_compare",
      "args": {
        "query": "부산광역시 지역상품 우선구매 조례"
      }
    },
    {
      "name": "search_admin_rule",
      "args": {
        "query": "지방자치단체 입찰시 낙찰자 결정기준 물품 적격심사 지역업체"
      }
    },
    {
      "name": "search_admin_rule",
      "args": {
        "query": "조달청 내자구매업무 처리규정"
      }
    },
    {
      "name": "search_admin_rule",
      "args": {
        "query": "물품 다수공급자계약 업무처리규정"
      }
    }
  ],
  "mandatory_mcp_executed": [
    "chain_procedure_detail:지방자치단체 물품 구매 지역제한 MAS 2단계 경쟁 (689ms)",
    "search_admin_rule:지방자치단체 입찰시 낙찰자 결정기준 물품 적격심사 지역업체 (119ms)",
    "search_admin_rule:조달청 내자구매업무 처리규정 (132ms)",
    "search_admin_rule:물품 다수공급자계약 업무처리규정 (116ms)",
    "chain_ordinance_compare:부산광역시 지역상품 우선구매 조례 (1192ms)",
    "chain_law_system:지방계약법 물품 구매 지역제한 제한경쟁 (1429ms)"
  ],
  "mandatory_mcp_missing": [],
  "mcp_chain_statuses": {},
  "admin_rule_call_statuses": {},
  "pps_rule_call_statuses": {},
  "mcp_preflight_elapsed_ms": 1430,
  "legal_basis_cache_used": true,
  "legal_basis_cache_hit_count": 0,
  "legal_basis_cache_miss_count": 6,
  "mcp_called_for_cache_miss": true,
  "mcp_called_for_freshness": false,
  "cache_status": "enabled",
  "source_status": "cache_refreshed_from_mcp"
}
```

### scenario_b_raw.json
```json
{
  "answer": "### 1. 질문의도 파악\n\n- 금액(80,000,000원) 기준의 수의계약 가능 여부 및 적합한 조달 경로를 찾고자 하는 의도로 분석되었습니다.\n\n### 2. 법령 적용 해석\n\n- **금액 한도**: 80,000,000원은 소액 수의계약 한도를 초과합니다. 경쟁입찰 또는 MAS/우수조달물품 등 다른 조달 경로를 검토해야 합니다.\n- **사전 조회 근거**: 시스템에서 다음의 필수 법령 및 매뉴얼 규정을 사전 조회하여 검토 기준에 반영했습니다.\n  - ✔️ search_admin_rule:지방자치단체 입찰 및 계약집행기준 수의계약 요령 (198ms)\n  - ✔️ search_law:지방계약법 시행령 제25조 수의계약 (200ms)\n\n### 3. 구매 방법 안내\n\n**1) 종합쇼핑몰(MAS) 및 우수조달물품**\n- 나라장터 종합쇼핑몰 등록 제품 납품요구 또는 우수조달물품 수의계약을 검토합니다.\n\n**2) 혁신제품 구매**\n- 혁신제품으로 지정되어 지정기간이 유효한 경우 수의계약을 검토할 수 있습니다.\n\n**3) 일반경쟁 및 제한경쟁입찰**\n- 수의계약 요건을 충족하지 못하는 경우 일반적인 입찰 절차를 진행합니다.\n\n### 4. 관련 업체 후보 소개\n\n*(아래 표에 검색된 후보 업체 정보가 제공됩니다.)*\n\n### 5. 필수 확인사항\n\n| 확인 항목 | 상태 |\n| :--- | :--- |\n| 기관유형 (지자체/출자출연/국가기관) | 확인 필요 |\n| 추정가격 (VAT 제외 여부) | 확인 필요 |\n| 조달청 등록 및 인증 유효기간 | 확인 필요 |\n| 정책기업 인증 유효성 | 확인 필요 |\n| 기관 내부 계약규정 | 확인 필요 |\n\n⚖️ 본 안내는 검토 경로 제시이며, 법적 효력이 없습니다. 실제 계약 전 적용 법령과 기관 내부 기준을 반드시 확인하세요.\n\n",
  "history": [
    {
      "role": "user",
      "text": "8천만원 물품 수의계약 가능해?"
    },
    {
      "role": "model",
      "text": "### 1. 질문의도 파악\n\n- 금액(80,000,000원) 기준의 수의계약 가능 여부 및 적합한 조달 경로를 찾고자 하는 의도로 분석되었습니다.\n\n### 2. 법령 적용 해석\n\n- **금액 한도**: 80,000,000원은 소액 수의계약 한도를 초과합니다. 경쟁입찰 또는 MAS/우수조달물품 등 다른 조달 경로를 검토해야 합니다.\n- **사전 조회 근거**: 시스템에서 다음의 필수 법령 및 매뉴얼 규정을 사전 조회하여 검토 기준에 반영했습니다.\n  - ✔️ search_admin_rule:지방자치단체 입찰 및 계약집행기준 수의계약 요령 (198ms)\n  - ✔️ search_law:지방계약법 시행령 제25조 수의계약 (200ms)\n\n### 3. 구매 방법 안내\n\n**1) 종합쇼핑몰(MAS) 및 우수조달물품**\n- 나라장터 종합쇼핑몰 등록 제품 납품요구 또는 우수조달물품 수의계약을 검토합니다.\n\n**2) 혁신제품 구매**\n- 혁신제품으로 지정되어 지정기간이 유효한 경우 수의계약을 검토할 수 있습니다.\n\n**3) 일반경쟁 및 제한경쟁입찰**\n- 수의계약 요건을 충족하지 못하는 경우 일반적인 입찰 절차를 진행합니다.\n\n### 4. 관련 업체 후보 소개\n\n*(아래 표에 검색된 후보 업체 정보가 제공됩니다.)*\n\n### 5. 필수 확인사항\n\n| 확인 항목 | 상태 |\n| :--- | :--- |\n| 기관유형 (지자체/출자출연/국가기관) | 확인 필요 |\n| 추정가격 (VAT 제외 여부) | 확인 필요 |\n| 조달청 등록 및 인증 유효기간 | 확인 필요 |\n| 정책기업 인증 유효성 | 확인 필요 |\n| 기관 내부 계약규정 | 확인 필요 |\n\n⚖️ 본 안내는 검토 경로 제시이며, 법적 효력이 없습니다. 실제 계약 전 적용 법령과 기관 내부 기준을 반드시 확인하세요.\n\n"
    }
  ],
  "candidate_table_source": "none",
  "legal_conclusion_allowed": false,
  "contract_possible_auto_promoted": false,
  "forbidden_patterns_remaining_after_rewrite": [],
  "final_answer_scanned": true,
  "sensitive_fields_detected": [],
  "model_selected": "bypass_tier_1_2",
  "model_decision_reason": "",
  "latency_ms": 274,
  "rag_status": {
    "laws": "SUCCESS",
    "manuals": "SUCCESS",
    "innovation": "SUCCESS"
  },
  "production_deployment": "HOLD",
  "route_guidance_provided": true,
  "regional_route_guidance_provided": false,
  "amount_detected": 80000000,
  "amount_band": "over_50m_under_100m",
  "candidate_counts_by_type": {
    "local_procurement_company": 0,
    "shopping_mall_supplier": 0,
    "policy_company": 0,
    "innovation_product": 0,
    "priority_purchase_product": 0
  },
  "source_call_statuses": {},
  "sensitive_fields_removed": true,
  "enrichment_join_key_redacted": true,
  "total_latency_ms": 274,
  "rag_elapsed_ms": 0,
  "model_elapsed_ms": 0,
  "rewrite_elapsed_ms": 72,
  "tool_elapsed_ms_by_name": {},
  "tool_call_count": 0,
  "fast_track_applied": false,
  "deterministic_template_used": true,
  "tier_resolved": 1,
  "answer_schema_version": "amount_contract_guidance_v1",
  "mandatory_mcp_plan": [
    {
      "name": "search_law",
      "args": {
        "query": "지방계약법 시행령 제25조 수의계약"
      }
    },
    {
      "name": "search_admin_rule",
      "args": {
        "query": "지방자치단체 입찰 및 계약집행기준 수의계약 요령"
      }
    }
  ],
  "mandatory_mcp_executed": [
    "search_admin_rule:지방자치단체 입찰 및 계약집행기준 수의계약 요령 (198ms)",
    "search_law:지방계약법 시행령 제25조 수의계약 (200ms)"
  ],
  "mandatory_mcp_missing": [],
  "mcp_chain_statuses": {},
  "admin_rule_call_statuses": {},
  "pps_rule_call_statuses": {},
  "mcp_preflight_elapsed_ms": 200,
  "legal_basis_cache_used": true,
  "legal_basis_cache_hit_count": 0,
  "legal_basis_cache_miss_count": 2,
  "mcp_called_for_cache_miss": true,
  "mcp_called_for_freshness": false,
  "cache_status": "enabled",
  "source_status": "cache_refreshed_from_mcp"
}
```

### scenario_c_raw.json
```json
{
  "answer": "### 1. 질문의도 파악\n\n- 금액(20,000,000원) 기준의 수의계약 가능 여부와 함께 지역업체(부산 등) 활용 방안을 모색하려는 의도로 분석되었습니다.\n\n### 2. 법령 적용 해석\n\n- **금액 한도**: 20,000,000원은 일반 소액 수의계약 한도(2천만원 이하) 및 정책기업 소액 수의계약 한도(5천만원 이하) 이내입니다.\n- **사전 조회 근거**: 시스템에서 다음의 필수 법령 및 매뉴얼 규정을 사전 조회하여 검토 기준에 반영했습니다.\n  - ✔️ search_admin_rule:지방자치단체 입찰시 낙찰자 결정기준 물품 적격심사 지역업체 (cache_hit)\n  - ✔️ chain_law_system:지방계약법 물품 구매 지역제한 제한경쟁 (cache_hit)\n  - ✔️ search_admin_rule:조달청 내자구매업무 처리규정 (cache_hit)\n  - ✔️ chain_ordinance_compare:부산광역시 지역상품 우선구매 조례 (cache_hit)\n  - ✔️ search_admin_rule:물품 다수공급자계약 업무처리규정 (cache_hit)\n  - ✔️ chain_procedure_detail:지방자치단체 물품 구매 지역제한 MAS 2단계 경쟁 (cache_hit)\n\n### 3. 구매 방법 안내\n\n**1) 지역제한 제한경쟁입찰**\n- 추정가격이 행안부령 기준 미만이면 지역을 제한한 제한경쟁입찰 공고가 가능합니다.\n\n**2) 다수공급자계약(MAS) 2단계 경쟁 시 지역제한**\n- 종합쇼핑몰 납품요구 시, 2단계 경쟁 대상인 경우 지역제한 규정을 적용할 수 있습니다.\n\n**3) 혁신제품·우수조달물품 우선구매**\n- 해당 품목에 부산업체 생산 혁신/우수조달물품이 있는지 확인하여 수의계약을 검토합니다.\n\n**4) 적격심사 지역업체 가점 부여**\n- 물품 적격심사 세부기준에 따라 지역업체 참여 시 가점 또는 우대 평가를 적용할 수 있습니다.\n\n### 4. 관련 업체 후보 소개\n\n*(아래 표에 검색된 후보 업체 정보가 제공됩니다.)*\n\n### 5. 필수 확인사항\n\n| 확인 항목 | 상태 |\n| :--- | :--- |\n| 기관유형 (지자체/출자출연/국가기관) | 확인 필요 |\n| 추정가격 (VAT 제외 여부) | 확인 필요 |\n| 조달청 등록 및 인증 유효기간 | 확인 필요 |\n| 정책기업 인증 유효성 | 확인 필요 |\n| 기관 내부 계약규정 | 확인 필요 |\n\n⚖️ 본 안내는 검토 경로 제시이며, 법적 효력이 없습니다. 실제 계약 전 적용 법령과 기관 내부 기준을 반드시 확인하세요.\n\n**[시스템 자동 추출 후보 표]**\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 입찰·수의계약 검토용 조달등록 부산업체 후보**\n| 후보유형 | 업체명 | 소재지 | 대표품목/등록상품명 | 조달등록 | 쇼핑몰/MAS | 정책기업 태그 | 인증유형 | 유효기간 | 검토 가능 경로 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 조달등록 | (주) 블루앤시스 | 부산광역시 사상구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주) 애로우윙즈 | 부산광역시 남구 | 컴퓨터지원제조소프트웨어 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)기주건설 | 부산광역시 강서구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)나라기술 | 부산광역시 부산진구 | 컴퓨터지원제조소프트웨어 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)블루햇 | 부산광역시 금정구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)선테크 | 부산광역시 금정구 | 데스크톱컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)세롬 | 부산광역시 부산진구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)세원정보시스템 | 부산광역시 부산진구 | 데스크톱컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)시큐리티즌 | 부산광역시 해운대구 | 컴퓨터네트워크또는인터넷보안서비스 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)쏠비전아이티 | 부산광역시 남구 | 태블릿컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n\n",
  "history": [
    {
      "role": "user",
      "text": "2천만원 컴퓨터 부산업체랑 계약하고 싶어"
    },
    {
      "role": "model",
      "text": "### 1. 질문의도 파악\n\n- 금액(20,000,000원) 기준의 수의계약 가능 여부와 함께 지역업체(부산 등) 활용 방안을 모색하려는 의도로 분석되었습니다.\n\n### 2. 법령 적용 해석\n\n- **금액 한도**: 20,000,000원은 일반 소액 수의계약 한도(2천만원 이하) 및 정책기업 소액 수의계약 한도(5천만원 이하) 이내입니다.\n- **사전 조회 근거**: 시스템에서 다음의 필수 법령 및 매뉴얼 규정을 사전 조회하여 검토 기준에 반영했습니다.\n  - ✔️ search_admin_rule:지방자치단체 입찰시 낙찰자 결정기준 물품 적격심사 지역업체 (cache_hit)\n  - ✔️ chain_law_system:지방계약법 물품 구매 지역제한 제한경쟁 (cache_hit)\n  - ✔️ search_admin_rule:조달청 내자구매업무 처리규정 (cache_hit)\n  - ✔️ chain_ordinance_compare:부산광역시 지역상품 우선구매 조례 (cache_hit)\n  - ✔️ search_admin_rule:물품 다수공급자계약 업무처리규정 (cache_hit)\n  - ✔️ chain_procedure_detail:지방자치단체 물품 구매 지역제한 MAS 2단계 경쟁 (cache_hit)\n\n### 3. 구매 방법 안내\n\n**1) 지역제한 제한경쟁입찰**\n- 추정가격이 행안부령 기준 미만이면 지역을 제한한 제한경쟁입찰 공고가 가능합니다.\n\n**2) 다수공급자계약(MAS) 2단계 경쟁 시 지역제한**\n- 종합쇼핑몰 납품요구 시, 2단계 경쟁 대상인 경우 지역제한 규정을 적용할 수 있습니다.\n\n**3) 혁신제품·우수조달물품 우선구매**\n- 해당 품목에 부산업체 생산 혁신/우수조달물품이 있는지 확인하여 수의계약을 검토합니다.\n\n**4) 적격심사 지역업체 가점 부여**\n- 물품 적격심사 세부기준에 따라 지역업체 참여 시 가점 또는 우대 평가를 적용할 수 있습니다.\n\n### 4. 관련 업체 후보 소개\n\n*(아래 표에 검색된 후보 업체 정보가 제공됩니다.)*\n\n### 5. 필수 확인사항\n\n| 확인 항목 | 상태 |\n| :--- | :--- |\n| 기관유형 (지자체/출자출연/국가기관) | 확인 필요 |\n| 추정가격 (VAT 제외 여부) | 확인 필요 |\n| 조달청 등록 및 인증 유효기간 | 확인 필요 |\n| 정책기업 인증 유효성 | 확인 필요 |\n| 기관 내부 계약규정 | 확인 필요 |\n\n⚖️ 본 안내는 검토 경로 제시이며, 법적 효력이 없습니다. 실제 계약 전 적용 법령과 기관 내부 기준을 반드시 확인하세요.\n\n**[시스템 자동 추출 후보 표]**\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 입찰·수의계약 검토용 조달등록 부산업체 후보**\n| 후보유형 | 업체명 | 소재지 | 대표품목/등록상품명 | 조달등록 | 쇼핑몰/MAS | 정책기업 태그 | 인증유형 | 유효기간 | 검토 가능 경로 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 조달등록 | (주) 블루앤시스 | 부산광역시 사상구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주) 애로우윙즈 | 부산광역시 남구 | 컴퓨터지원제조소프트웨어 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)기주건설 | 부산광역시 강서구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)나라기술 | 부산광역시 부산진구 | 컴퓨터지원제조소프트웨어 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)블루햇 | 부산광역시 금정구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)선테크 | 부산광역시 금정구 | 데스크톱컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)세롬 | 부산광역시 부산진구 | 컴퓨터서버 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)세원정보시스템 | 부산광역시 부산진구 | 데스크톱컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)시큐리티즌 | 부산광역시 해운대구 | 컴퓨터네트워크또는인터넷보안서비스 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)쏠비전아이티 | 부산광역시 남구 | 태블릿컴퓨터 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n\n"
    }
  ],
  "candidate_table_source": "server_structured_formatter",
  "legal_conclusion_allowed": false,
  "contract_possible_auto_promoted": false,
  "forbidden_patterns_remaining_after_rewrite": [],
  "final_answer_scanned": true,
  "sensitive_fields_detected": [],
  "model_selected": "bypass_tier_1_2",
  "model_decision_reason": "",
  "latency_ms": 11810,
  "rag_status": {
    "laws": "SUCCESS",
    "manuals": "SUCCESS",
    "innovation": "SUCCESS"
  },
  "production_deployment": "HOLD",
  "route_guidance_provided": true,
  "regional_route_guidance_provided": true,
  "amount_detected": 20000000,
  "amount_band": "under_20m",
  "candidate_counts_by_type": {
    "local_procurement_company": 10,
    "shopping_mall_supplier": 0,
    "policy_company": 0,
    "innovation_product": 0,
    "priority_purchase_product": 0
  },
  "source_call_statuses": {
    "search_shopping_mall": "success",
    "search_local_company_by_product": "success"
  },
  "sensitive_fields_removed": true,
  "enrichment_join_key_redacted": true,
  "total_latency_ms": 11810,
  "rag_elapsed_ms": 0,
  "model_elapsed_ms": 0,
  "rewrite_elapsed_ms": 63,
  "tool_elapsed_ms_by_name": {},
  "tool_call_count": 2,
  "fast_track_applied": false,
  "deterministic_template_used": true,
  "tier_resolved": 2,
  "answer_schema_version": "regional_procurement_v2",
  "mandatory_mcp_plan": [
    {
      "name": "chain_law_system",
      "args": {
        "query": "지방계약법 물품 구매 지역제한 제한경쟁"
      }
    },
    {
      "name": "chain_procedure_detail",
      "args": {
        "query": "지방자치단체 물품 구매 지역제한 MAS 2단계 경쟁"
      }
    },
    {
      "name": "chain_ordinance_compare",
      "args": {
        "query": "부산광역시 지역상품 우선구매 조례"
      }
    },
    {
      "name": "search_admin_rule",
      "args": {
        "query": "지방자치단체 입찰시 낙찰자 결정기준 물품 적격심사 지역업체"
      }
    },
    {
      "name": "search_admin_rule",
      "args": {
        "query": "조달청 내자구매업무 처리규정"
      }
    },
    {
      "name": "search_admin_rule",
      "args": {
        "query": "물품 다수공급자계약 업무처리규정"
      }
    }
  ],
  "mandatory_mcp_executed": [
    "search_admin_rule:지방자치단체 입찰시 낙찰자 결정기준 물품 적격심사 지역업체 (cache_hit)",
    "chain_law_system:지방계약법 물품 구매 지역제한 제한경쟁 (cache_hit)",
    "search_admin_rule:조달청 내자구매업무 처리규정 (cache_hit)",
    "chain_ordinance_compare:부산광역시 지역상품 우선구매 조례 (cache_hit)",
    "search_admin_rule:물품 다수공급자계약 업무처리규정 (cache_hit)",
    "chain_procedure_detail:지방자치단체 물품 구매 지역제한 MAS 2단계 경쟁 (cache_hit)"
  ],
  "mandatory_mcp_missing": [],
  "mcp_chain_statuses": {},
  "admin_rule_call_statuses": {},
  "pps_rule_call_statuses": {},
  "mcp_preflight_elapsed_ms": 1,
  "legal_basis_cache_used": true,
  "legal_basis_cache_hit_count": 6,
  "legal_basis_cache_miss_count": 0,
  "mcp_called_for_cache_miss": false,
  "mcp_called_for_freshness": false,
  "cache_status": "enabled",
  "source_status": "cached_verified"
}
```

### scenario_d_raw.json
```json
{
  "answer": "### 1. 질문의도 파악\n- 입력하신 질문은 계약 가능 여부 판단이 아니라, 부산 지역업체 후보 검색 요청으로 분류했습니다.\n\n### 2. 지역업체 후보 소개\n- 아래 후보는 조달등록·정책기업·쇼핑몰/MAS·인증 여부를 기준으로 정리한 검토 후보입니다.\n\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 입찰·수의계약 검토용 조달등록 부산업체 후보**\n| 후보유형 | 업체명 | 소재지 | 대표품목/등록상품명 | 조달등록 | 쇼핑몰/MAS | 정책기업 태그 | 인증유형 | 유효기간 | 검토 가능 경로 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 조달등록 | (주)선진텔레콤 | 부산광역시 사상구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)유니원 | 부산광역시 해운대구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 부일씨씨 | 부산광역시 남구 대연동 | 신설하수관로CCTV조사서비스 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 주식회사 강동미디어 | 부산광역시 연제구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 주식회사 마린시큐 | 부산광역시 남구 | CCTV카메라용렌즈 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 주식회사 예스텍 | 부산광역시 부산진구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 주식회사 태인테크 | 부산광역시 부산진구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n\n**[표 2] 정책기업 수의계약 검토 후보**\n| 후보유형 | 업체명 | 소재지 | 대표품목/등록상품명 | 조달등록 | 쇼핑몰/MAS | 정책기업 태그 | 인증유형 | 유효기간 | 검토 가능 경로 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 정책기업 | 부일 | 부산광역시 남구 대연동 | 신설하수관로CCTV조사서비스 | 확인 | 확인 필요 | 여성기업 | 확인 필요 | 확인 필요 | 정책기업 수의계약 검토, 1인 견적 가능성 검토(한도 내) | 후보, 인증 유효성·금액·계약유형 확인 필요 |\n\n> ℹ️ 여성기업·장애인기업·사회적기업 등 정책기업 태그는 수의계약 검토의 후보 자격 정보이며, 금액·계약유형·인증 유효성·견적 방식 확인 전에는 계약 가능 여부가 확정되지 않습니다.\n\n\n\n### 3. 확인 필요사항\n- 실제 계약 전 품목 적합성, 조달등록 상태, 종합쇼핑몰/MAS 등록 여부, 정책기업 인증 유효성, 기관 내부 기준을 확인해야 합니다.\n- 본 안내는 후보 정보 제공이며 계약 가능 여부를 자동 확정하지 않습니다.\n- 계약 전 조달등록·품목 적합성·수의계약 가능 여부 확인이 필요합니다.",
  "history": [
    {
      "role": "user",
      "text": "CCTV 부산업체 추천해줘"
    },
    {
      "role": "model",
      "text": "### 1. 질문의도 파악\n- 입력하신 질문은 계약 가능 여부 판단이 아니라, 부산 지역업체 후보 검색 요청으로 분류했습니다.\n\n### 2. 지역업체 후보 소개\n- 아래 후보는 조달등록·정책기업·쇼핑몰/MAS·인증 여부를 기준으로 정리한 검토 후보입니다.\n\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 입찰·수의계약 검토용 조달등록 부산업체 후보**\n| 후보유형 | 업체명 | 소재지 | 대표품목/등록상품명 | 조달등록 | 쇼핑몰/MAS | 정책기업 태그 | 인증유형 | 유효기간 | 검토 가능 경로 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 조달등록 | (주)선진텔레콤 | 부산광역시 사상구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | (주)유니원 | 부산광역시 해운대구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 부일씨씨 | 부산광역시 남구 대연동 | 신설하수관로CCTV조사서비스 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 주식회사 강동미디어 | 부산광역시 연제구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 주식회사 마린시큐 | 부산광역시 남구 | CCTV카메라용렌즈 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 주식회사 예스텍 | 부산광역시 부산진구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n| 조달등록 | 주식회사 태인테크 | 부산광역시 부산진구 | CCTV카메라 | 확인 | 확인 필요 | 해당 없음 | 확인 필요 | 확인 필요 | 수의계약 검토, 2인 이상 견적 검토 | 후보, 법적 적격성 확인 필요 |\n\n**[표 2] 정책기업 수의계약 검토 후보**\n| 후보유형 | 업체명 | 소재지 | 대표품목/등록상품명 | 조달등록 | 쇼핑몰/MAS | 정책기업 태그 | 인증유형 | 유효기간 | 검토 가능 경로 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 정책기업 | 부일 | 부산광역시 남구 대연동 | 신설하수관로CCTV조사서비스 | 확인 | 확인 필요 | 여성기업 | 확인 필요 | 확인 필요 | 정책기업 수의계약 검토, 1인 견적 가능성 검토(한도 내) | 후보, 인증 유효성·금액·계약유형 확인 필요 |\n\n> ℹ️ 여성기업·장애인기업·사회적기업 등 정책기업 태그는 수의계약 검토의 후보 자격 정보이며, 금액·계약유형·인증 유효성·견적 방식 확인 전에는 계약 가능 여부가 확정되지 않습니다.\n\n\n\n### 3. 확인 필요사항\n- 실제 계약 전 품목 적합성, 조달등록 상태, 종합쇼핑몰/MAS 등록 여부, 정책기업 인증 유효성, 기관 내부 기준을 확인해야 합니다.\n- 본 안내는 후보 정보 제공이며 계약 가능 여부를 자동 확정하지 않습니다.\n- 계약 전 조달등록·품목 적합성·수의계약 가능 여부 확인이 필요합니다."
    }
  ],
  "candidate_table_source": "server_structured_formatter",
  "legal_conclusion_allowed": false,
  "contract_possible_auto_promoted": false,
  "forbidden_patterns_remaining_after_rewrite": [],
  "final_answer_scanned": true,
  "sensitive_fields_detected": [],
  "model_selected": "bypass_tier_0",
  "model_decision_reason": "Tier 0 (Fast Track): LLM 및 MCP 전면 우회",
  "latency_ms": 7271,
  "rag_status": {
    "laws": "SUCCESS",
    "manuals": "SUCCESS",
    "innovation": "SUCCESS"
  },
  "production_deployment": "HOLD",
  "route_guidance_provided": false,
  "regional_route_guidance_provided": false,
  "amount_detected": null,
  "amount_band": null,
  "candidate_counts_by_type": {
    "local_procurement_company": 7,
    "shopping_mall_supplier": 0,
    "policy_company": 1,
    "innovation_product": 0,
    "priority_purchase_product": 0
  },
  "source_call_statuses": {},
  "sensitive_fields_removed": true,
  "enrichment_join_key_redacted": true,
  "total_latency_ms": 7271,
  "rag_elapsed_ms": null,
  "model_elapsed_ms": null,
  "rewrite_elapsed_ms": 63,
  "tool_elapsed_ms_by_name": {},
  "tool_call_count": 0,
  "fast_track_applied": true,
  "deterministic_template_used": true,
  "tier_resolved": 0,
  "answer_schema_version": "simplified_company_search_v1",
  "mandatory_mcp_plan": [],
  "mandatory_mcp_executed": [],
  "mandatory_mcp_missing": [],
  "mcp_chain_statuses": {},
  "admin_rule_call_statuses": {},
  "pps_rule_call_statuses": {},
  "mcp_preflight_elapsed_ms": null,
  "legal_basis_cache_used": false,
  "legal_basis_cache_hit_count": 0,
  "legal_basis_cache_miss_count": 0,
  "mcp_called_for_cache_miss": false,
  "mcp_called_for_freshness": false,
  "cache_status": "",
  "source_status": "no_mcp_required"
}
```
