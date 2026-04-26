# TC8 모델 라우팅 정책 검증 보고서

## Path Validation Status
- **Routing policy static validation**: CONDITIONAL_PASS
- **MODEL_ROUTING_MODE**: risk_based
- **GEMINI_MODEL (Pro)**: gemini-2.5-pro
- **FALLBACK_MODEL (Flash)**: gemini-2.5-flash
- **Runtime model execution**: NOT_RUN
- **Production deployment**: HOLD

## 라우팅 정책 요약

| 위험도 | 기본 모델 | 조건 |
| :--- | :--- | :--- |
| low | Flash | 업체 추천, 절차 안내, 목록 조회 등 |
| high | Pro | 수의계약, 금액 한도, 1인 견적, 법령 해석 등 |
| medium | Pro | 미분류 → 안전 우선 |

## Fallback 정책 요약

| 조건 | 결과 |
| :--- | :--- |
| Pro 실패 + legal_basis 충분 | Flash fallback 허용 |
| Pro 실패 + legal_basis 부족 | deterministic fail-closed |
| Pro 실패 + legal_conclusion_allowed=false | deterministic fail-closed |
| Pro 실패 + blocked_scope + 업체검색 성공 | Flash 제한 fallback |
| Pro 실패 + blocked_scope + 업체검색 없음 | deterministic fail-closed |

## Raw JSON Output

### TC8-1
```json
{
  "test_case": "TC8-1",
  "description": "저위험: 업체 후보 추천 → Flash",
  "query": "CCTV 부산 업체 추천해줘",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-flash",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "저위험 패턴 매칭 → Flash 사용",
  "risk_level": "low",
  "high_risk_triggers": [],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": "not_applicable",
  "legal_judgment_requested": false,
  "legal_judgment_allowed": false,
  "company_table_allowed": true,
  "blocked_scope": [],
  "direct_legal_basis_count": 0,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": ""
}
```

### TC8-2
```json
{
  "test_case": "TC8-2",
  "description": "저위험: 업체 후보 검색 → Flash",
  "query": "LED 조명 부산 업체 후보 있어?",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-flash",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "저위험 패턴 매칭 → Flash 사용",
  "risk_level": "low",
  "high_risk_triggers": [],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": "not_applicable",
  "legal_judgment_requested": false,
  "legal_judgment_allowed": false,
  "company_table_allowed": true,
  "blocked_scope": [],
  "direct_legal_basis_count": 0,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": ""
}
```

### TC8-3
```json
{
  "test_case": "TC8-3",
  "description": "저위험: 쇼핑몰 업체 목록 → Flash",
  "query": "종합쇼핑몰 등록 부산업체 후보 보여줘",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-flash",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "저위험 패턴 매칭 → Flash 사용",
  "risk_level": "low",
  "high_risk_triggers": [],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": "not_applicable",
  "legal_judgment_requested": false,
  "legal_judgment_allowed": false,
  "company_table_allowed": true,
  "blocked_scope": [],
  "direct_legal_basis_count": 0,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": ""
}
```

### TC8-4
```json
{
  "test_case": "TC8-4",
  "description": "고위험: 수의계약 가능 여부 + 금액 → Pro",
  "query": "조경공사 3천만원 수의계약 가능해?",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-pro",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "고위험 트리거 감지: ['수의계약 가능', '천만원']",
  "risk_level": "high",
  "high_risk_triggers": [
    "수의계약 가능",
    "천만원"
  ],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": true,
  "legal_judgment_requested": true,
  "legal_judgment_allowed": true,
  "company_table_allowed": true,
  "blocked_scope": [],
  "direct_legal_basis_count": 2,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": "",
  "fallback_policy": {
    "fallback_allowed": true,
    "flash_company_table_fallback_allowed": true,
    "flash_legal_judgment_fallback_allowed": true,
    "deterministic_template_required": false,
    "fallback_model": "gemini-2.5-flash",
    "fallback_reason": "MCP legal_basis 충분(2건) & claim_validation_pass → Flash fallback 허용"
  }
}
```

### TC8-5
```json
{
  "test_case": "TC8-5",
  "description": "고위험: 1인 견적 가능 여부 + 금액 → Pro",
  "query": "8천만원 컴퓨터 1인 견적 가능해?",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-pro",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "고위험 트리거 감지: ['천만원', '1인 견적']",
  "risk_level": "high",
  "high_risk_triggers": [
    "천만원",
    "1인 견적"
  ],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": false,
  "legal_judgment_requested": true,
  "legal_judgment_allowed": true,
  "company_table_allowed": true,
  "blocked_scope": [
    "amount_threshold",
    "one_person_quote"
  ],
  "direct_legal_basis_count": 0,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": "",
  "fallback_policy": {
    "fallback_allowed": false,
    "flash_company_table_fallback_allowed": false,
    "flash_legal_judgment_fallback_allowed": false,
    "deterministic_template_required": true,
    "fallback_model": null,
    "fallback_reason": "legal_conclusion_allowed=false 또는 blocked_scope 존재 → deterministic fail-closed"
  }
}
```

### TC8-6
```json
{
  "test_case": "TC8-6",
  "description": "고위험: 정책기업 특례 + 수의계약 → Pro",
  "query": "여성기업이면 바로 수의계약 가능해?",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-pro",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "고위험 트리거 감지: ['수의계약 가능', '바로 수의', '바로 수의계약 가능']",
  "risk_level": "high",
  "high_risk_triggers": [
    "수의계약 가능",
    "바로 수의",
    "바로 수의계약 가능"
  ],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": false,
  "legal_judgment_requested": true,
  "legal_judgment_allowed": false,
  "company_table_allowed": true,
  "blocked_scope": [
    "policy_company_special_rule",
    "sole_contract_possibility"
  ],
  "direct_legal_basis_count": 0,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": "",
  "fallback_policy": {
    "fallback_allowed": true,
    "flash_company_table_fallback_allowed": true,
    "flash_legal_judgment_fallback_allowed": false,
    "deterministic_template_required": true,
    "fallback_model": "gemini-2.5-flash",
    "fallback_reason": "업체 후보 표 정리만 허용; 계약 가능 판단은 fail-closed"
  }
}
```

### TC8-7
```json
{
  "test_case": "TC8-7",
  "description": "고위험: 혁신제품 수의계약 + 금액 제한 → Pro",
  "query": "혁신제품이면 금액 제한 없이 수의계약 가능해?",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-pro",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "고위험 트리거 감지: ['수의계약 가능', '금액 제한', '혁신제품이면']",
  "risk_level": "high",
  "high_risk_triggers": [
    "수의계약 가능",
    "금액 제한",
    "혁신제품이면",
    "금액 제한 없이"
  ],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": false,
  "legal_judgment_requested": true,
  "legal_judgment_allowed": false,
  "company_table_allowed": true,
  "blocked_scope": [
    "amount_threshold"
  ],
  "direct_legal_basis_count": 0,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": "",
  "fallback_policy": {
    "fallback_allowed": false,
    "flash_company_table_fallback_allowed": false,
    "flash_legal_judgment_fallback_allowed": false,
    "deterministic_template_required": true,
    "fallback_model": null,
    "fallback_reason": "legal_conclusion_allowed=false 또는 blocked_scope 존재 → deterministic fail-closed"
  }
}
```

### TC8-8
```json
{
  "test_case": "TC8-8",
  "description": "고위험 Pro→fallback: legal_basis 충분 시 Flash fallback 허용",
  "query": "조경공사 3천만원 수의계약 가능해?",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-pro",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "고위험 트리거 감지: ['수의계약 가능', '천만원']",
  "risk_level": "high",
  "high_risk_triggers": [
    "수의계약 가능",
    "천만원"
  ],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": true,
  "legal_judgment_requested": true,
  "legal_judgment_allowed": true,
  "company_table_allowed": true,
  "blocked_scope": [],
  "direct_legal_basis_count": 3,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": "",
  "fallback_policy": {
    "fallback_allowed": true,
    "flash_company_table_fallback_allowed": true,
    "flash_legal_judgment_fallback_allowed": true,
    "deterministic_template_required": false,
    "fallback_model": "gemini-2.5-flash",
    "fallback_reason": "MCP legal_basis 충분(3건) & claim_validation_pass → Flash fallback 허용"
  }
}
```

### TC8-9
```json
{
  "test_case": "TC8-9",
  "description": "고위험 Pro→fallback: legal_conclusion_allowed=false → fail-closed",
  "query": "8천만원 컴퓨터 1인 견적 가능해?",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-pro",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "고위험 트리거 감지: ['천만원', '1인 견적']",
  "risk_level": "high",
  "high_risk_triggers": [
    "천만원",
    "1인 견적"
  ],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": false,
  "legal_judgment_requested": true,
  "legal_judgment_allowed": false,
  "company_table_allowed": true,
  "blocked_scope": [
    "amount_threshold",
    "one_person_quote"
  ],
  "direct_legal_basis_count": 0,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": "",
  "fallback_policy": {
    "fallback_allowed": false,
    "flash_company_table_fallback_allowed": false,
    "flash_legal_judgment_fallback_allowed": false,
    "deterministic_template_required": true,
    "fallback_model": null,
    "fallback_reason": "legal_conclusion_allowed=false 또는 blocked_scope 존재 → deterministic fail-closed"
  }
}
```

### TC8-10
```json
{
  "test_case": "TC8-10",
  "description": "고위험 Pro→fallback: blocked_scope + 업체검색 성공 → 제한 Flash fallback",
  "query": "여성기업이면 바로 수의계약 가능해?",
  "test_type": "routing_policy_static",
  "model_routing_mode": "risk_based",
  "model_selected": "gemini-2.5-pro",
  "model_used": "not_executed",
  "pro_call_executed": false,
  "model_decision_reason": "고위험 트리거 감지: ['수의계약 가능', '바로 수의', '바로 수의계약 가능']",
  "risk_level": "high",
  "high_risk_triggers": [
    "수의계약 가능",
    "바로 수의",
    "바로 수의계약 가능"
  ],
  "fallback_used": false,
  "fallback_reason": "",
  "retry_count": 0,
  "legal_conclusion_allowed": false,
  "legal_judgment_requested": true,
  "legal_judgment_allowed": false,
  "company_table_allowed": true,
  "blocked_scope": [
    "sole_contract"
  ],
  "direct_legal_basis_count": 0,
  "deterministic_template_used": false,
  "flash_answer_discarded": false,
  "pass": true,
  "failure_reason": "",
  "fallback_policy": {
    "fallback_allowed": true,
    "flash_company_table_fallback_allowed": true,
    "flash_legal_judgment_fallback_allowed": false,
    "deterministic_template_required": true,
    "fallback_model": "gemini-2.5-flash",
    "fallback_reason": "업체 후보 표 정리만 허용; 계약 가능 판단은 fail-closed"
  }
}
```

