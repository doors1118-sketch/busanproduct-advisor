# TC7 Gemini Runtime Tool Call Integration 검증 보고서

[1] 변경한 파일 목록
- app/gemini_engine.py
- run_tc7_gemini_runtime.py

[2] 테스트 통과/실패
- 통과: 8/8
- 실패: 0

[3] 개별 상태
- G-RT-1: PASS
- G-RT-2: PASS
- G-RT-3_Forbidden_Expression_Check_Iter1: PASS
- G-RT-3_Forbidden_Expression_Check_Iter2: PASS
- G-RT-3_Forbidden_Expression_Check_Iter3: PASS
- G-RT-3_Forbidden_Expression_Check_Iter4: PASS
- G-RT-3_Forbidden_Expression_Check_Iter5: PASS
- Malformed_Mock: PASS

[4] 실패 원인

[5] Raw JSON Output
```json
[
  {
    "test_case": "G-RT-1_Innovation_Product",
    "test_type": "gemini_runtime_tool_call_integration",
    "query": "공기청정기 혁신제품 부산업체 찾아줘",
    "tool_called": true,
    "tool_name": "search_innovation_products",
    "attempted_tool_name": "search_innovation_products",
    "model_used": "gemini-2.5-pro",
    "legal_conclusion_allowed": false,
    "blocked_scope": [
      "no_direct_legal_basis",
      "unsupported_legal_conclusion"
    ],
    "candidate_table_generated": true,
    "candidate_table_source": "server_structured_formatter",
    "llm_generated_table_discarded": true,
    "final_answer_scanned": true,
    "malformed_function_call_detected": false,
    "function_call_retry_count": 0,
    "function_call_final_status": "not_detected",
    "prefetch_tool_called": false,
    "prefetch_tool_name": null,
    "tool_call_path": "gemini_tool_execution",
    "model_function_call_malformed": false,
    "malformed_source": null,
    "forbidden_patterns_matched": [],
    "regex_rewrite_applied": true,
    "forbidden_patterns_detected_before_rewrite": [
      "수의계약 추진",
      "1인 견적 수의계약"
    ],
    "forbidden_patterns_remaining_after_rewrite": [
      "수의계약 추진",
      "1인 견적 수의계약"
    ],
    "rewritten_sentences_count": 2,
    "deterministic_template_used": true,
    "final_answer_source": "deterministic_template_plus_server_table",
    "tool_execution_attempted": true,
    "tool_execution_status": "success",
    "classified_candidate_count": 11,
    "formatter_input_count": 11,
    "formatter_output_chars": 1806,
    "contract_possible_auto_promoted": false,
    "sensitive_fields_detected": [],
    "final_answer_preview": "⚠️ 질문하신 조건에 대한 계약 가능 여부나 금액 한도는 시스템이 단정할 수 없습니다. 계약 전 관련 법령 및 지침을 직접 확인하시기 바랍니다.\n\n**[시스템 자동 추출 후보 표]**\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 혁신제품·혁신시제품 수의계약 검토 후보**\n| 제품명 | 업체명 | 소재지 | 혁신구분 | 인증번호 | 지정/인증 유효기간 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 융복합공기청정기, 성진하이텍, BIZ-33K-150NC, 공기청정승강조명제어 | 주식회사 성진하이텍 | 부산광역시 해운대구 센텀중앙로97 (재송동) | 혁신제품(유형2) | 2024-237 | 확인 필요 | 후보, 지정 유효기간 확인 필요 |\n| 융복합공기청정기, 성진하이텍, BIZ-33K-180NC, 공기청정승강조명제어 | 주식회사 성진하이텍 | 부산광역시 해운대구 센텀중앙로97 (재송동) | 혁신제품(유형2) | 2024-237 | 확인 필요 | 후보, 지정 유효기간 확인 필요 |\n| 융복합공기청정기, 성진하이텍, BIZ-33K-150NCS, 공기청정승강조명 | 주식회사 성진하이텍 |",
    "pass": true,
    "failure_reason": ""
  },
  {
    "test_case": "G-RT-2_Tech_Dev_Product",
    "test_type": "gemini_runtime_tool_call_integration",
    "query": "부산업체 중 기술개발제품 인증 보유 LED 업체 찾아줘",
    "tool_called": true,
    "tool_name": "search_tech_development_products",
    "attempted_tool_name": "search_tech_development_products",
    "model_used": "gemini-2.5-pro",
    "legal_conclusion_allowed": false,
    "blocked_scope": [
      "no_direct_legal_basis",
      "unsupported_legal_conclusion"
    ],
    "candidate_table_generated": true,
    "candidate_table_source": "server_structured_formatter",
    "llm_generated_table_discarded": true,
    "final_answer_scanned": true,
    "malformed_function_call_detected": false,
    "function_call_retry_count": 0,
    "function_call_final_status": "not_detected",
    "prefetch_tool_called": false,
    "prefetch_tool_name": null,
    "tool_call_path": "gemini_tool_execution",
    "model_function_call_malformed": false,
    "malformed_source": null,
    "forbidden_patterns_matched": [],
    "regex_rewrite_applied": true,
    "forbidden_patterns_detected_before_rewrite": [
      "수의계약 추진",
      "직접 계약",
      "계약 방식.*수의계약"
    ],
    "forbidden_patterns_remaining_after_rewrite": [
      "수의계약 추진",
      "직접 계약",
      "계약 방식.*수의계약"
    ],
    "rewritten_sentences_count": 3,
    "deterministic_template_used": true,
    "final_answer_source": "deterministic_template_plus_server_table",
    "tool_execution_attempted": true,
    "tool_execution_status": "success",
    "classified_candidate_count": 6,
    "formatter_input_count": 6,
    "formatter_output_chars": 902,
    "contract_possible_auto_promoted": false,
    "sensitive_fields_detected": [],
    "final_answer_preview": "⚠️ 질문하신 조건에 대한 계약 가능 여부나 금액 한도는 시스템이 단정할 수 없습니다. 계약 전 관련 법령 및 지침을 직접 확인하시기 바랍니다.\n\n**[시스템 자동 추출 후보 표]**\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 기술개발제품 13종 인증 보유 부산업체 우선구매 검토 후보**\n| 제품명 | 업체명 | 인증구분 | 인증번호 | 인증일 | 유효기간 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 에너지절감 스마트 LED전광판 | 하얀코끼리LED | 녹색기술제품 | GTP-24-04071 | 2024-01-25 | 유효 | 후보, 인증 유효기간 확인 필요 |\n| LED등기구 | 주식회사 비젼테크 | 우수조달물품지정 | 2024193 | 2025-01-20 | 유효 | 후보, 인증 유효기간 확인 필요 |\n| 격자구조를 갖는 히트싱크형 PCB가 적용된 LED 등기구 | (주)금경라이팅 | 우수조달물품지정 | 2023062 | 2023-07-21 | 유효 | 후보, 인증 유효기간 확인 필요 |\n| 다목적 전광판 운영 프로그램 V1MultiPurpose LED MANAGER V1",
    "pass": true,
    "failure_reason": ""
  },
  {
    "test_case": "G-RT-3_Forbidden_Expression_Check_Iter1",
    "test_type": "gemini_runtime_tool_call_integration",
    "query": "혁신제품이면 금액 제한 없이 수의계약 가능해?",
    "tool_called": true,
    "tool_name": "search_innovation_products",
    "attempted_tool_name": "search_innovation_products",
    "model_used": "gemini-2.5-pro",
    "legal_conclusion_allowed": false,
    "blocked_scope": [
      "amount_threshold",
      "innovation_product_special_rule",
      "no_direct_legal_basis",
      "unsupported_legal_conclusion"
    ],
    "candidate_table_generated": true,
    "candidate_table_source": "server_structured_formatter",
    "llm_generated_table_discarded": false,
    "final_answer_scanned": true,
    "malformed_function_call_detected": false,
    "function_call_retry_count": 0,
    "function_call_final_status": "not_detected",
    "prefetch_tool_called": false,
    "prefetch_tool_name": null,
    "tool_call_path": "gemini_tool_execution",
    "model_function_call_malformed": false,
    "malformed_source": null,
    "forbidden_patterns_matched": [],
    "regex_rewrite_applied": false,
    "forbidden_patterns_detected_before_rewrite": [],
    "forbidden_patterns_remaining_after_rewrite": [],
    "rewritten_sentences_count": 0,
    "deterministic_template_used": false,
    "final_answer_source": "model_generation_with_caution",
    "tool_execution_attempted": true,
    "tool_execution_status": "success",
    "classified_candidate_count": 20,
    "formatter_input_count": 20,
    "formatter_output_chars": 3065,
    "contract_possible_auto_promoted": false,
    "sensitive_fields_detected": [],
    "final_answer_preview": "\n\n**주의**: 위 목록은 예시이며, 실제 계약 시점에는 혁신제품 지정이 유효한지, 제품 규격이 요구사항과 일치하는지 반드시 확인해야 합니다.\n\n### 3. 확인 필요사항\n*   **혁신제품 지정 유효기간**: 계약하려는 시점에 해당 제품의 혁신제품 지정이 유효한지 '혁신장터'에서 반드시 확인해야 합니다.\n*   **특정규격 감사위험**: 사업부서의 특정 요구가 특정 혁신제품으로 유도한 것으로 보일 경우, 특정규격 심사나 감사 지적의 대상이 될 수 있습니다. 구매 결정 과정에서 공정성과 필요성을 명확히 해두는 것이 중요합니다.\n\n⚖️ 본 답변은 참고용 정보이며 법적 효력이 없습니다. 정확한 판단은 기관 내 법제 담당 부서와 최종 협의하시기 바랍니다.\n\n---\n⚠️ **확인 필요 사항**\n- 금액 한도는 법령 조회 지연으로 확정되지 않았습니다. 법제처 법령정보센터에서 최신 기준을 확인하세요.\n- 현재 응답에서는 수의계약 가능 여부와 금액 기준을 확정하지 않습니다. 실제 계약 전 혁신제품 지정 유효기간, 혁신장터 등록 여부, 조달청 계약 여부, 수요기관 적용 법령 확인이 필요합니다.\n\n---\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 혁신",
    "pass": true,
    "failure_reason": ""
  },
  {
    "test_case": "G-RT-3_Forbidden_Expression_Check_Iter2",
    "test_type": "gemini_runtime_tool_call_integration",
    "query": "혁신제품이면 금액 제한 없이 수의계약 가능해?",
    "tool_called": true,
    "tool_name": "search_innovation_products",
    "attempted_tool_name": "search_innovation_products",
    "model_used": "gemini-2.5-pro",
    "legal_conclusion_allowed": false,
    "blocked_scope": [
      "amount_threshold",
      "innovation_product_special_rule",
      "no_direct_legal_basis",
      "unsupported_legal_conclusion"
    ],
    "candidate_table_generated": true,
    "candidate_table_source": "server_structured_formatter",
    "llm_generated_table_discarded": true,
    "final_answer_scanned": true,
    "malformed_function_call_detected": false,
    "function_call_retry_count": 0,
    "function_call_final_status": "not_detected",
    "prefetch_tool_called": false,
    "prefetch_tool_name": null,
    "tool_call_path": "gemini_tool_execution",
    "model_function_call_malformed": false,
    "malformed_source": null,
    "forbidden_patterns_matched": [],
    "regex_rewrite_applied": true,
    "forbidden_patterns_detected_before_rewrite": [
      "수의계약 추진",
      "금액 제한이 없더라도"
    ],
    "forbidden_patterns_remaining_after_rewrite": [
      "수의계약 추진",
      "금액 제한이 없더라도"
    ],
    "rewritten_sentences_count": 2,
    "deterministic_template_used": true,
    "final_answer_source": "deterministic_template_plus_server_table",
    "tool_execution_attempted": true,
    "tool_execution_status": "success",
    "classified_candidate_count": 20,
    "formatter_input_count": 20,
    "formatter_output_chars": 3065,
    "contract_possible_auto_promoted": false,
    "sensitive_fields_detected": [],
    "final_answer_preview": "⚠️ 질문하신 조건에 대한 계약 가능 여부나 금액 한도는 시스템이 단정할 수 없습니다. 계약 전 관련 법령 및 지침을 직접 확인하시기 바랍니다.\n\n**[시스템 자동 추출 후보 표]**\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 혁신제품·혁신시제품 수의계약 검토 후보**\n| 제품명 | 업체명 | 소재지 | 혁신구분 | 인증번호 | 지정/인증 유효기간 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-12.5-S, 특고압반 | 주식회사 세풍전기 | 부산광역시 사상구 새벽로167번길 92() | 혁신제품(유형1) | 2024-390 | 확인 필요 | 후보, 지정 유효기간 확인 필요 |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-12.5-N, 특고압반 | 주식회사 세풍전기 | 부산광역시 사상구 새벽로167번길 92() | 혁신제품(유형1) | 2024-390 | 확인 필요 | 후보, 지정 유효기간 확인 필요 |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-25-S, 특고압반 | 주식",
    "pass": true,
    "failure_reason": ""
  },
  {
    "test_case": "G-RT-3_Forbidden_Expression_Check_Iter3",
    "test_type": "gemini_runtime_tool_call_integration",
    "query": "혁신제품이면 금액 제한 없이 수의계약 가능해?",
    "tool_called": true,
    "tool_name": "search_innovation_products",
    "attempted_tool_name": "search_innovation_products",
    "model_used": "gemini-2.5-pro",
    "legal_conclusion_allowed": false,
    "blocked_scope": [
      "amount_threshold",
      "innovation_product_special_rule",
      "no_direct_legal_basis",
      "unsupported_legal_conclusion"
    ],
    "candidate_table_generated": true,
    "candidate_table_source": "server_structured_formatter",
    "llm_generated_table_discarded": true,
    "final_answer_scanned": true,
    "malformed_function_call_detected": false,
    "function_call_retry_count": 0,
    "function_call_final_status": "not_detected",
    "prefetch_tool_called": false,
    "prefetch_tool_name": null,
    "tool_call_path": "gemini_tool_execution",
    "model_function_call_malformed": false,
    "malformed_source": null,
    "forbidden_patterns_matched": [],
    "regex_rewrite_applied": true,
    "forbidden_patterns_detected_before_rewrite": [
      "수의계약 체결"
    ],
    "forbidden_patterns_remaining_after_rewrite": [
      "수의계약 체결"
    ],
    "rewritten_sentences_count": 1,
    "deterministic_template_used": true,
    "final_answer_source": "deterministic_template_plus_server_table",
    "tool_execution_attempted": true,
    "tool_execution_status": "success",
    "classified_candidate_count": 20,
    "formatter_input_count": 20,
    "formatter_output_chars": 3119,
    "contract_possible_auto_promoted": false,
    "sensitive_fields_detected": [],
    "final_answer_preview": "⚠️ 질문하신 조건에 대한 계약 가능 여부나 금액 한도는 시스템이 단정할 수 없습니다. 계약 전 관련 법령 및 지침을 직접 확인하시기 바랍니다.\n\n**[시스템 자동 추출 후보 표]**\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 혁신제품·혁신시제품 수의계약 검토 후보**\n| 제품명 | 업체명 | 소재지 | 혁신구분 | 인증번호 | 지정/인증 유효기간 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-12.5-S, 특고압반 | 주식회사 세풍전기 | 부산광역시 사상구 새벽로167번길 92() | 혁신제품(유형1) | 2024-390 | 확인 필요 | 후보, 지정 유효기간 확인 필요 |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-12.5-N, 특고압반 | 주식회사 세풍전기 | 부산광역시 사상구 새벽로167번길 92() | 혁신제품(유형1) | 2024-390 | 확인 필요 | 후보, 지정 유효기간 확인 필요 |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-25-S, 특고압반 | 주식",
    "pass": true,
    "failure_reason": ""
  },
  {
    "test_case": "G-RT-3_Forbidden_Expression_Check_Iter4",
    "test_type": "gemini_runtime_tool_call_integration",
    "query": "혁신제품이면 금액 제한 없이 수의계약 가능해?",
    "tool_called": true,
    "tool_name": "search_innovation_products",
    "attempted_tool_name": "search_innovation_products",
    "model_used": "gemini-2.5-pro",
    "legal_conclusion_allowed": false,
    "blocked_scope": [
      "amount_threshold",
      "innovation_product_special_rule",
      "no_direct_legal_basis",
      "unsupported_legal_conclusion"
    ],
    "candidate_table_generated": true,
    "candidate_table_source": "server_structured_formatter",
    "llm_generated_table_discarded": false,
    "final_answer_scanned": true,
    "malformed_function_call_detected": false,
    "function_call_retry_count": 0,
    "function_call_final_status": "not_detected",
    "prefetch_tool_called": false,
    "prefetch_tool_name": null,
    "tool_call_path": "gemini_tool_execution",
    "model_function_call_malformed": false,
    "malformed_source": null,
    "forbidden_patterns_matched": [],
    "regex_rewrite_applied": false,
    "forbidden_patterns_detected_before_rewrite": [],
    "forbidden_patterns_remaining_after_rewrite": [],
    "rewritten_sentences_count": 0,
    "deterministic_template_used": false,
    "final_answer_source": "model_generation_with_caution",
    "tool_execution_attempted": true,
    "tool_execution_status": "success",
    "classified_candidate_count": 20,
    "formatter_input_count": 20,
    "formatter_output_chars": 3119,
    "contract_possible_auto_promoted": false,
    "sensitive_fields_detected": [],
    "final_answer_preview": "\n\n> ⚖️ 본 답변은 참고용 정보이며 법적 효력이 없습니다. 정확한 판단은 기관 내 법제 담당 부서와 최종 협의하시기 바랍니다.\n\n---\n⚠️ **확인 필요 사항**\n- 금액 한도는 법령 조회 지연으로 확정되지 않았습니다. 법제처 법령정보센터에서 최신 기준을 확인하세요.\n- 현재 응답에서는 수의계약 가능 여부와 금액 기준을 확정하지 않습니다. 실제 계약 전 혁신제품 지정 유효기간, 혁신장터 등록 여부, 조달청 계약 여부, 수요기관 적용 법령 확인이 필요합니다.\n\n---\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 혁신제품·혁신시제품 수의계약 검토 후보**\n| 제품명 | 업체명 | 소재지 | 혁신구분 | 인증번호 | 지정/인증 유효기간 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-12.5-S, 특고압반 | 주식회사 세풍전기 | 부산광역시 사상구 새벽로167번길 92() | 혁신제품(유형1) | 2024-390 | 확인 필요 | 후보, 지정 유효기간 확인 필요 |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VC",
    "pass": true,
    "failure_reason": ""
  },
  {
    "test_case": "G-RT-3_Forbidden_Expression_Check_Iter5",
    "test_type": "gemini_runtime_tool_call_integration",
    "query": "혁신제품이면 금액 제한 없이 수의계약 가능해?",
    "tool_called": true,
    "tool_name": "search_innovation_products",
    "attempted_tool_name": "search_innovation_products",
    "model_used": "gemini-2.5-pro",
    "legal_conclusion_allowed": false,
    "blocked_scope": [
      "amount_threshold",
      "innovation_product_special_rule",
      "no_direct_legal_basis",
      "unsupported_legal_conclusion"
    ],
    "candidate_table_generated": true,
    "candidate_table_source": "server_structured_formatter",
    "llm_generated_table_discarded": false,
    "final_answer_scanned": true,
    "malformed_function_call_detected": false,
    "function_call_retry_count": 0,
    "function_call_final_status": "not_detected",
    "prefetch_tool_called": false,
    "prefetch_tool_name": null,
    "tool_call_path": "gemini_tool_execution",
    "model_function_call_malformed": false,
    "malformed_source": null,
    "forbidden_patterns_matched": [],
    "regex_rewrite_applied": false,
    "forbidden_patterns_detected_before_rewrite": [],
    "forbidden_patterns_remaining_after_rewrite": [],
    "rewritten_sentences_count": 0,
    "deterministic_template_used": false,
    "final_answer_source": "model_generation_with_caution",
    "tool_execution_attempted": true,
    "tool_execution_status": "success",
    "classified_candidate_count": 20,
    "formatter_input_count": 20,
    "formatter_output_chars": 3121,
    "contract_possible_auto_promoted": false,
    "sensitive_fields_detected": [],
    "final_answer_preview": "**[검색 결과 활용]**\n위 검색 결과에서 **삼성g2b주식회사(부산진구)**, **(주)성진하이텍(해운대구)**, **(주)세풍전기(사상구)** 등 부산 소재 기업들이 확인됩니다. 이 기업들의 제품이 사업 목적에 부합한다면 수의계약 가능 여부는 관련 법령 확인이 필요합니다.\n\n**※ 계약 전 필수 확인사항:** 위 목록은 예시이며, 실제 계약 시점에는 혁신제품 지정이 유효한지, 업체의 자격에 문제가 없는지 반드시 추가 확인이 필요합니다.\n\n⚖️ 본 답변은 참고용 정보이며 법적 효력이 없습니다. 정확한 판단은 기관 내 법제 담당 부서와 최종 협의하시기 바랍니다.\n\n---\n⚠️ **확인 필요 사항**\n- 금액 한도는 법령 조회 지연으로 확정되지 않았습니다. 법제처 법령정보센터에서 최신 기준을 확인하세요.\n- 현재 응답에서는 수의계약 가능 여부와 금액 기준을 확정하지 않습니다. 실제 계약 전 혁신제품 지정 유효기간, 혁신장터 등록 여부, 조달청 계약 여부, 수요기관 적용 법령 확인이 필요합니다.\n\n---\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 혁신제품·혁신시제품 수의계약 검토 후보**\n| 제품명 | 업체명 | 소재지 | 혁신구분 | 인",
    "pass": true,
    "failure_reason": ""
  },
  {
    "test_case": "G-RT-3_Malformed_Mock",
    "test_type": "gemini_runtime_tool_call_integration",
    "query": "혁신제품이면 금액 제한 없이 수의계약 가능해?",
    "tool_called": true,
    "tool_name": "search_innovation_products",
    "attempted_tool_name": "search_innovation_products",
    "model_used": "gemini-2.5-pro",
    "legal_conclusion_allowed": false,
    "blocked_scope": [
      "amount_threshold",
      "innovation_product_special_rule",
      "no_direct_legal_basis",
      "unsupported_legal_conclusion",
      "malformed_function_call"
    ],
    "candidate_table_generated": true,
    "candidate_table_source": "server_structured_formatter",
    "llm_generated_table_discarded": true,
    "final_answer_scanned": true,
    "malformed_function_call_detected": true,
    "function_call_retry_count": 1,
    "function_call_final_status": "malformed_fail_closed",
    "prefetch_tool_called": false,
    "prefetch_tool_name": null,
    "tool_call_path": "gemini_tool_execution",
    "model_function_call_malformed": true,
    "malformed_source": "mock_injected",
    "forbidden_patterns_matched": [],
    "regex_rewrite_applied": true,
    "forbidden_patterns_detected_before_rewrite": [
      "수의계약 추진",
      "수의계약 체결",
      "수의계약으로 구매할 수"
    ],
    "forbidden_patterns_remaining_after_rewrite": [
      "수의계약 추진",
      "수의계약 체결",
      "수의계약으로 구매할 수"
    ],
    "rewritten_sentences_count": 3,
    "deterministic_template_used": true,
    "final_answer_source": "deterministic_template_plus_server_table",
    "tool_execution_attempted": true,
    "tool_execution_status": "success",
    "classified_candidate_count": 10,
    "formatter_input_count": 10,
    "formatter_output_chars": 1689,
    "contract_possible_auto_promoted": false,
    "sensitive_fields_detected": [],
    "final_answer_preview": "⚠️ 질문하신 조건에 대한 계약 가능 여부나 금액 한도는 시스템이 단정할 수 없습니다. 계약 전 관련 법령 및 지침을 직접 확인하시기 바랍니다.\n\n**[시스템 자동 추출 후보 표]**\n부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n**[표 1] 혁신제품·혁신시제품 수의계약 검토 후보**\n| 제품명 | 업체명 | 소재지 | 혁신구분 | 인증번호 | 지정/인증 유효기간 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-12.5-S, 특고압반 | 주식회사 세풍전기 | 부산광역시 사상구 새벽로167번길 92() | 혁신제품(유형1) | 2024-390 | 확인 필요 | 후보, 지정 유효기간 확인 필요 |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-12.5-N, 특고압반 | 주식회사 세풍전기 | 부산광역시 사상구 새벽로167번길 92() | 혁신제품(유형1) | 2024-390 | 확인 필요 | 후보, 지정 유효기간 확인 필요 |\n| 폐쇄형배전반, 세풍전기, SP-LM-HV-EH-VCB-630A-25-S, 특고압반 | 주식",
    "pass": true,
    "failure_reason": ""
  }
]
```

[6] Gemini runtime tool call integration: PASS
[7] Production deployment: HOLD
