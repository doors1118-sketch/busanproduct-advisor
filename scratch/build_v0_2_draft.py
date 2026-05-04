import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

# 1. legal_buyer_type_scope_map_v0_2_draft.json
buyer_type_map = {
  "national_government": {"jurisdiction_scope": "national_contract", "label": "국가기관"},
  "central_government_agency": {"jurisdiction_scope": "national_contract", "label": "중앙행정기관"},
  "national_agency": {"jurisdiction_scope": "national_contract", "label": "국가기관 소속기관"},
  "local_government": {"jurisdiction_scope": "local_contract", "label": "지방자치단체"},
  "metropolitan_city": {"jurisdiction_scope": "local_contract", "label": "광역자치단체"},
  "city_county_district": {"jurisdiction_scope": "local_contract", "label": "시·군·구"},
  "education_office": {"jurisdiction_scope": "local_contract", "label": "교육청"},
  "public_institution": {"jurisdiction_scope": "public_institution_contract", "label": "공공기관"},
  "public_enterprise": {"jurisdiction_scope": "public_institution_contract", "label": "공기업"},
  "quasi_government_institution": {"jurisdiction_scope": "public_institution_contract", "label": "준정부기관"},
  "other_public_institution": {"jurisdiction_scope": "public_institution_contract", "label": "기타공공기관"},
  "local_public_company": {"jurisdiction_scope": "local_contract", "label": "지방공기업"},
  "local_public_corporation": {"jurisdiction_scope": "local_contract", "label": "지방공사·공단"},
  "local_invested_institution": {"jurisdiction_scope": "local_contract", "label": "지방출자기관"},
  "local_affiliated_institution": {"jurisdiction_scope": "local_contract", "label": "지방출연기관"}
}

with open(os.path.join(base, 'legal_buyer_type_scope_map_v0_2_draft.json'), 'w', encoding='utf-8') as f:
    json.dump(buyer_type_map, f, ensure_ascii=False, indent=2)

# 2. institutional_rule_layer_schema.json
institutional_schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Institutional Rule Layer Schema",
  "description": "Schema for specific institutional internal rules, separated from the general legal master registry.",
  "type": "object",
  "properties": {
    "rule_id": {
      "type": "string",
      "description": "Unique identifier for the institutional rule."
    },
    "institution_id": {
      "type": "string",
      "description": "Unique identifier for the institution (e.g., 'busan_metro_transit')."
    },
    "institution_name": {
      "type": "string",
      "description": "Full name of the institution."
    },
    "rule_name": {
      "type": "string",
      "description": "Official name of the internal rule (e.g., '계약사무처리규정')."
    },
    "base_jurisdiction": {
      "type": "string",
      "enum": ["national_contract", "local_contract", "public_institution_contract"],
      "description": "The primary master jurisdiction this institution falls back to."
    },
    "review_status": {
      "type": "string",
      "enum": ["needs_review", "verified", "out_of_date"],
      "default": "needs_review",
      "description": "Verification status of the rule. Defaults to needs_review upon ingestion."
    },
    "active_for_rule": {
      "type": "boolean",
      "default": False,
      "description": "Whether this rule is active and can be referenced by the Rule Engine. False until verified."
    },
    "articles": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "article_number": {"type": "string"},
          "article_title": {"type": "string"},
          "content": {"type": "string"}
        }
      }
    }
  },
  "required": ["rule_id", "institution_id", "institution_name", "rule_name", "base_jurisdiction", "review_status", "active_for_rule"]
}

with open(os.path.join(base, 'institutional_rule_layer_schema.json'), 'w', encoding='utf-8') as f:
    json.dump(institutional_schema, f, ensure_ascii=False, indent=2)

# 3. local_public_institution_routing_policy.md
routing_policy = """# Local Public Institution Routing Policy (v0.2 Draft)

본 정책은 챗봇 및 RAG 시스템이 지방공기업 및 출자·출연기관(Local Public Institutions)과 관련된 사용자의 질의를 처리할 때 적용되는 라우팅 정책을 정의합니다.

## 1. 기본 원칙 (Base Principle)
지방공기업 및 자치단체 출자·출연기관은 실무적으로 **독립적인 계약 법령 체계를 갖지 않으며, 대부분 「지방계약법령(local_contract)」 체계를 준용**합니다. 따라서 별도의 독립 관할(Jurisdiction)로 취급하지 않고, `local_contract` 체계 내에 편입하여 처리합니다.

## 2. 라우팅 룰 (Routing Rules)

### Rule 1: 명시적인 기관 ID(`institution_id`)가 제공된 경우
- **조건**: 사용자 질의에 특정 기관명(예: "부산교통공사 계약규정에서는...", "서울시설공단 수의계약 기준은?")이 명시되어 시스템이 `institution_id`를 식별한 경우.
- **액션**: 
  1. `Institutional Rule Layer`에서 해당 `institution_id`의 규정을 최우선으로 검색합니다.
  2. 조회된 규정 중 `active_for_rule = true` 인 조항을 바탕으로 답변을 생성합니다.

### Rule 2: 기관별 규정이 없거나 승인되지 않은 경우 (Fallback)
- **조건**: Rule 1이 발동되었으나 해당 기관의 규정이 시스템에 미적재 상태이거나, 적재되었으나 아직 검수되지 않아 `active_for_rule = false` 인 경우.
- **액션**: 
  - 기관 규정을 무시(또는 규정이 없음을 안내)하고, **해당 기관의 `base_jurisdiction`인 `local_contract`(지방계약법 체계) 기준**으로 우회(Fallback)하여 일반론적인 답변을 제공합니다.

### Rule 3: 특정 기관 명시 없이 범용 질의인 경우
- **조건**: 사용자가 "지방공기업은 수의계약 한도가 어떻게 돼?", "출자출연기관 계약 담당자인데..." 와 같이 특정 기관을 지칭하지 않고 범용적인 `buyer_type_scope`만을 지칭한 경우.
- **액션**: 
  - `Institutional Rule Layer`를 전혀 조회하지 않습니다.
  - 즉시 **`local_contract` (지방계약법 체계)** 및 관련된 행정안전부 예규(지방공기업 예산편성기준 등)를 바탕으로 답변을 제공합니다.
"""

with open(os.path.join(base, 'local_public_institution_routing_policy.md'), 'w', encoding='utf-8') as f:
    f.write(routing_policy)

# 4. legal_registry_v0_2_adjustment_report.json
adjustment_report = {
  "title": "Phase 7-B v0.2 Architecture Adjustment Report",
  "description": "Summary of adjustments made to transition local public institutions from an independent jurisdiction to the local_contract jurisdiction with an auxiliary Institutional Rule Layer.",
  "adjustments": [
    {
      "target": "Buyer Type Scope Map",
      "change": "Reassigned 4 local public institution buyer types (local_public_company, local_public_corporation, local_invested_institution, local_affiliated_institution) from 'local_public_institution_contract' to 'local_contract'.",
      "impact": "Queries regarding these buyer types will now naturally route to local_contract laws without needing artificial fallback relations."
    },
    {
      "target": "Master Registry Jurisdiction Scope",
      "change": "Abolished the conceptual 'local_public_institution_contract' jurisdiction for future rule ingestions.",
      "impact": "Simplifies the top-level jurisdiction tree to 3 pillars: national_contract, local_contract, public_institution_contract."
    },
    {
      "target": "Institutional Rule Layer",
      "change": "Created a dedicated JSON schema ('institutional_rule_layer_schema.json') to isolate specific internal rules of individual organizations from the master registry.",
      "impact": "Prevents Master Registry pollution. Internal rules are quarantined with 'needs_review' and 'active_for_rule=false' upon ingestion."
    },
    {
      "target": "Routing Policy",
      "change": "Drafted 'local_public_institution_routing_policy.md' to strictly define conditional routing based on the presence of 'institution_id' in user queries.",
      "impact": "Ensures the chatbot safely falls back to local_contract when specific institutional rules are unavailable or unverified."
    }
  ]
}

with open(os.path.join(base, 'legal_registry_v0_2_adjustment_report.json'), 'w', encoding='utf-8') as f:
    json.dump(adjustment_report, f, ensure_ascii=False, indent=2)

print("Created all 4 artifacts successfully.")
