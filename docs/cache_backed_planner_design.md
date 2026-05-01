# Cache-backed Legal Chain Planner 설계

## 1. 개요 및 목표

Local Legal Corpus Cache를 단순 검색용 DB로 활용하는 것을 넘어, 기존 MCP의 `chain_full_research` 및 `chain_law_system`의 복합 탐색 논리를 내부적으로 일부 재현하는 **Cache-backed Legal Chain Planner**를 설계합니다.

### 핵심 목표
1. **사전 계획 수립**: 질문 분석 결과를 바탕으로 답변에 필요한 법령·예규·조례·사례 근거의 전체 목록(Plan)을 선제적으로 생성합니다.
2. **Local Corpus 최우선 탐색**: 네트워크 지연이 발생하는 MCP API 호출 전, 로컬 캐시(Local Legal Graph)에서 우선적으로 근거 후보를 찾습니다.
3. **법적 흐름 추적 (Graph Traversal)**: `법률 → 시행령 → 시행규칙 → 행정규칙/예규/고시 → 조례 → 판례/해석례`로 이어지는 인과적 위임 흐름을 추적합니다.
4. **최신성 검증 경로로서의 MCP**: MCP는 원천 데이터 탐색이 아닌, 로컬에서 찾은 근거의 '최신성 검증' 및 '캐시 누락분 보완' 용도로 역할을 전환합니다.
5. **결측치 제어**: 필요 근거 누락 시 `mandatory_mcp_missing` 또는 `missing_basis` 필드에 명시하여 환각을 차단합니다.
6. **안전성 (Fail-closed)**: 확보된 근거가 오직 '캐시(Local)' 기반일 경우, 법적 결론 확정을 유보(`legal_conclusion_allowed = False`)하여 운영 리스크를 원천 차단합니다.

---

## 2. Planner 입출력 (I/O) 스키마 설계

### 2.1 입력값 설계 (Input)
Planner는 LLM 응답 생성 전, 파이프라인(Router/Guardrail 이후)에서 다음 데이터를 주입받습니다.

```json
{
  "user_message": "부산시 공공기관 5천만원 물품 수의계약 가능 여부",
  "agency_type": "지방자치단체(부산광역시)",
  "contract_category": "goods",       // goods | construction | service | mixed | unknown
  "amount_detected": 50000000,
  "item_or_work_keyword": "물품",
  "intent_labels": ["sole_contract", "regional_restriction"],
  "risk_level": "high",
  "source_status": "not_called",
  "available_local_collections": ["laws", "admin_rules", "ordinances", "pps_qa"]
}
```

### 2.2 출력값 설계 (Output)
Planner는 로컬 탐색 및 체인 추적 결과를 다음과 같은 JSON 구조로 반환하며, 이는 이후 `_finalize_answer` 또는 LLM Context에 주입됩니다.

```json
{
  "basis_plan": [
    {
      "basis_id": "b_001",
      "required": true,
      "basis_type": "law",
      "target_collection": "laws",
      "query": "지방계약법 시행령 제25조",
      "expected_topic_tags": ["sole_contract"],
      "contract_category": "goods",
      "agency_scope": "local_government",
      "fallback_allowed": true,
      "mcp_verify_required": true,
      "basis_importance": "blocking",
      "blocks_legal_conclusion_if_missing": true
    }
  ],
  "local_basis_hits": [
    {
      "collection": "laws",
      "document_id": "law_253973_제25조",
      "text_snippet": "...",
      "version_hash": "abc123x"
    }
  ],
  "missing_basis": [
    "지방자치단체 입찰 및 계약집행기준 제5장 수의계약 운영요령"
  ],
  "mcp_verification_plan": [
    {
      "mcp_tool": "search_admin_rule",     // 내부 실행용 (사용자 노출 금지)
      "user_friendly_label": "행정안전부 예규 원문 조회", // 사용자 응답 표시용
      "query": "지방자치단체 입찰 및 계약집행기준 수의계약 운영요령",
      "reason": "필수 행정규칙(blocking) 캐시 누락으로 원천망 검증 필요"
    }
  ],
  "graph_traversal_steps": [
    {
      "step": 1,
      "traversal_type": "entry_point",
      "from_collection": null,
      "to_collection": "laws",
      "from_document_id": null,
      "query": "지방계약법 시행령 제25조",
      "status": "success",
      "document_id": "law_253973_제25조",
      "reason": "최초 탐색"
    },
    {
      "step": 2,
      "traversal_type": "delegated_rule",
      "from_collection": "laws",
      "to_collection": "admin_rules",
      "from_document_id": "law_253973_제25조",
      "query": "지방자치단체 입찰 및 계약집행기준 수의계약 운영요령",
      "status": "failed",
      "document_id": null,
      "reason": "캐시 데이터 내 해당 문서 부재"
    }
  ],
  "source_status_candidate": "cached_stale_but_available",
  "legal_conclusion_allowed_candidate": false,
  "planner_warnings": [
    "핵심 행정규칙(집행기준)이 로컬 캐시에서 누락되었습니다.",
    "캐시 기반 데이터에만 의존하고 있으므로 확정적 결론을 유보합니다."
  ]
}
```

---

## 3. 핵심 워크플로우 (Planner Logic)

Planner의 실행 흐름은 다음과 같은 5단계로 구성됩니다.

### Step 1: Entry Point 및 Basis Plan 생성
입력된 도메인(`contract_category`)에 따라 필요한 사전 탐색 목록(`basis_plan`)을 객체 배열로 동적 생성합니다. 각 객체는 중요도(`basis_importance`)를 지닙니다.

**계약 유형별 `basis_plan` 탐색 항목 예시:**
- **`construction` (공사)**: 지역제한, 지역의무공동도급, 공동계약 운영요령, 시설공사 적격심사, 하도급 지역업체 참여 등.
- **`service` (용역)**: 용역 지역제한, 용역 적격심사, 협상계약 제안서 평가, 공동수급 등.
- **`mixed` (혼합계약)**: 주된 계약목적, 분리발주 원칙, 통합발주 시 감사 리스크 관련 규정 및 사례 등.

### Step 2: Local Graph Traversal (구조화된 캐시 릴레이 탐색)
`basis_plan`을 바탕으로 `graph_traversal_steps` 객체 배열에 탐색 이력을 구조화하여 기록합니다.
1. `laws` 컬렉션에서 조문 원문 매칭.
2. 매칭된 조문의 `delegated_rules` 메타데이터 Edge를 따라 `admin_rules` 컬렉션 탐색.
3. `related_ordinances` 메타데이터 Edge를 따라 `ordinances` 컬렉션 탐색.
4. `risk_level="high"`인 경우, 연관 판례나 감사 지적 사항을 횡적 탐색.

### Step 3: 결측치 식별 및 Degrade 규칙 적용
로컬 탐색 중 `basis_plan` 내 `required: true`인 필수 근거를 찾지 못한 경우 이를 `missing_basis`에 포함합니다.
- **Degrade 규칙**: `target_collection`이 현재 시스템의 `available_local_collections`에 아예 없는 경우(예: `admin_rules` 미지원 상태), 해당 `basis`는 무조건 `missing_basis`로 편입되고 즉각적인 MCP Verification 대상이 됩니다.

### Step 4: MCP Verification Plan 생성
MCP는 캐시 누락분 보완 및 최신성 검증 용도로만 파이프라인 후단에서 계획됩니다.
- **사용자 노출 분리**: 계획표에는 내부 시스템용 API 호출 함수명(`mcp_tool`)과 사용자가 화면에서 보게 될 메시지(`user_friendly_label`)를 명확히 분리하여 담습니다.

### Step 5: Candidate Status 및 결론 통제 규칙 도출
가장 중요한 안전망 파라미터를 계산합니다.
- **`source_status_candidate`**: 상황에 따라 기존 표준 Status로 매핑합니다.
  - `cached_verified` (전체 검증 완료)
  - `cached_stale_but_available` (캐시 존재하나 검증 미필)
  - `partial_mcp_with_missing` (일부 MCP 및 캐시 결합 실패 시)
  - `mcp_failed_no_basis` (근거 완전 부재 시)
  - `mcp_preflight_success` / `cache_refreshed_from_mcp` / `no_mcp_required`
- **`legal_conclusion_allowed_candidate` 규칙 정교화**: 
  - **기본 원칙**: 근거가 캐시에만 존재할 경우 현재 운영 기본값은 보수적으로 **`false`**를 유지합니다.
  - **예외 처리 (Missing Blocking)**: `basis_importance`가 `blocking`인 필수 근거가 누락되었을 경우 무조건 `false`입니다.
  - **향후 확장(제한적 예외)**: 시스템이 고도화되어 `source_status`가 `cached_verified`이고 `verified_at` 시점이 정책상 허용된 유효 기간 이내일 경우에 한해, 제한적 안내 가능성(true)을 여는 방안을 설계에 남겨둡니다.

---

## 4. 제약 및 방어 원칙

1. **캐시는 결론을 대체하지 않음**: Planner는 "어떤 근거를 검토해야 하는가(Plan)"를 짜는 역할이며, "계약이 가능한가"를 판단하지 않습니다.
2. **Raw Tool Name 노출 금지**: `mcp_verification_plan` 내의 내부 실행 도구명(예: `search_law`)은 디버그용으로만 쓰고 최종 사용자 메시지에는 절대 사용하지 않습니다.
3. **Production 적용 유보**: 현재 체계는 설계 단계이며, 코드 및 ETL 구현, 서버 배포는 일절 포함하지 않습니다.

> [!IMPORTANT]
> 본 문서는 Cache-backed Legal Chain Planner에 대한 설계 문서로, 어떠한 코드 구현도 진행되지 않았습니다. 지침에 따라 **Production Deployment는 계속 HOLD 상태**를 강력하게 유지합니다.
