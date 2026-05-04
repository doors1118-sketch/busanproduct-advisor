# Local Public Institution Routing Policy (v0.2 Draft)

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
