# Local Legal Corpus Cache 구조 설계

## 1. 현재 Legal Corpus 구조 요약 및 Gap 분석

현재 RAG 캐시 구조를 점검한 결과, 법령과 행정규칙이 파편화되어 있으며 구조화된 탐색(Graph)이 불가능한 한계가 존재합니다.

| 분석 대상 | 현재 상태 (As-Is) | Gap / 한계점 |
| :--- | :--- | :--- |
| **법률·시행령·시행규칙** (`laws`) | 국가계약법, 지방계약법, 중소기업구매촉진법, 조달사업법 등 핵심 법령의 법·영·규칙 조문이 구조화되어 적재됨. | 조항 단위 메타데이터는 있으나, 예외나 특례를 다루는 하위 행정규칙(고시/예규)과의 연결 고리가 없음. |
| **행정규칙, 예규, 고시** (`manuals`) | 지방계약 집행기준, 조달청 훈령 등이 PDF 원문 텍스트 통째로 청킹(Chunking)되어 `manuals` 컬렉션에 적재됨. | 조문 단위 구조화 corpus가 아닌 단순 페이지/글자수 기반 청크이므로, 조항 번호 기반의 정확한 매칭 및 법령과의 계층적 검색이 불가능함. 추후 `admin_rules` / `pps_rules`로의 재구성(Re-indexing)이 필요함. |
| **부산시 조례** | 존재하지 않음. | 지자체 특화 구매 조건, 우선구매 가점 등을 판단할 근거가 누락됨. |
| **판례·해석례·감사사례** | 조달청 QA(`pps_qa`)만 API로 수집되어 존재함. | 유권해석, 법원 판례, 감사원 지적사례 등 고위험 판단을 방어할 실제 규제 사례 코퍼스가 없음. |
| **법령 체계도** (`law_hierarchy_2.json`) | 법률 → 시행령 → 시행규칙 3단 비교까지만 지원함. | 법령 조문에서 위임한 행정규칙, 별표, 지자체 조례로의 횡적/종적 확장이 불가능함. |
| **인덱스 동기화 상태** | `ingest_laws.py` 내에 ChromaDB와 `bm25_laws_index.pkl`의 수정 시간을 비교하여 1시간 초과 시 Drift 경고를 띄우는 Watchdog 존재함. | 파일 수정 시간 기반의 단순 비교이므로, 레코드(문서) 단위의 세밀한 무결성 검증은 어려움. |

---

## 2. 권장 컬렉션 구조 (To-Be)

법령의 계층과 도메인 특성을 반영하여 컬렉션을 세분화하고, 단일 검색이 아닌 연계 검색이 가능하도록 설계합니다.

1. **`laws` (핵심 법령)**
   - 국가계약법, 지방계약법, 조달사업법, 판로지원법 및 각 시행령, 시행규칙
2. **`admin_rules` (계약 행정규칙 및 예규)**
   - 지방자치단체 입찰 및 계약집행기준, 낙찰자 결정기준, 국가계약예규, 기재부 고시
3. **`pps_rules` (조달청 규정)**
   - 다수공급자계약(MAS) 업무처리규정, 우수조달물품 지정관리규정, 혁신제품 구매운영 규정
4. **`ordinances` (자치법규)**
   - 부산광역시 지역상품 우선구매 조례, 지역건설산업 활성화 조례 등
5. **`public_institution_rules` (공공기관 자체 규정)**
   - 공기업·준정부기관 계약사무규칙, 기타공공기관 계약사무 운영규정
   - 지방공기업 및 부산시 출자·출연기관 자체 계약규정 후보 (단, 기관별 자체규정은 확보 가능성과 최신성에 대한 지속적인 확인이 선행되어야 함)
6. **`interpretations` / `precedents` / `audit_cases` / `pps_qa` (사례 및 해석)**
   - 법제처 유권해석, 대법원/하급심 판례, 감사원 지적 사례, 조달청 종합민원센터 질의응답

---

## 3. Metadata 설계

정확한 필터링과 Graph 탐색을 위해 각 Chunk(또는 Node)에 다음과 같은 메타데이터 스키마를 적용합니다.

### 3.1 필수 기본 메타데이터
- `document_id`: 고유 식별자 (예: `law_253973_제25조`)
- `source_type`: 코퍼스 유형 (`law`, `decree`, `rule`, `admin_rule`, `ordinance`, `case`)
- `law_name` / `law_alias`: 공식 명칭 및 약칭
- `article` / `article_title`: 조 번호 및 제목
- `paragraph` / `item`: 항, 호 정보 (조문 내 세부 파싱 가능 시)
- `effective_date` / `promulgation_date`: 시행일 및 공포일
- `version_hash` / `text_hash`: 조문 내용의 위변조 및 업데이트 추적용 해시

### 3.2 관계형 메타데이터 (Graph Edge 역할)
- `parent_law`: 상위 법령 ID (시행령인 경우 모법 ID)
- `child_rules` / `delegated_rules`: 하위 위임 규정 ID 배열 (예: 이 조항이 위임한 고시 목록)
- `related_admin_rules`: 연관된 예규/집행기준 ID 배열
- `related_ordinances`: 연관된 지자체 조례 ID 배열
- `related_cases` / `related_interpretations` / `related_pps_qa`: 이 조항과 관련된 판례, 해석례, QA ID 배열

### 3.3 계약 도메인 메타데이터 (Context Filter 역할)
- `agency_scope`: 적용 기관 필터 (`local_government`, `national_agency`, `public_corporation` 등)
- `contract_category`: 계약 유형 (`goods`, `construction`, `service`, `mixed`)
- `topic_tags`: 핵심 토픽 태그 배열 (`sole_contract`, `regional_restriction`, `innovation_product`, `audit_risk` 등)

---

## 4. Local Legal Graph 설계

조문 간의 단순 Text Vector 검색을 넘어, 관계형 메타데이터를 활용하여 답변의 근거를 계층적으로 추적하는 Graph 검색 파이프라인입니다.

**탐색 시나리오 (예시: 지방계약법에 따른 5천만 원 물품 수의계약)**
1. **Node Entry**: `laws` 컬렉션에서 `지방계약법 시행령 제25조(수의계약에 의할 수 있는 경우)` 매칭.
2. **Edge Traversal (하위 위임)**: 해당 조문의 `delegated_rules`를 참조하여 `admin_rules` 컬렉션의 `지방자치단체 입찰 및 계약집행기준(수의계약 요령)` 추출.
3. **Edge Traversal (지역 특화)**: `related_ordinances`를 참조하여 부산시 지역상품 우선구매 관련 `ordinances` 추출.
4. **Edge Traversal (리스크 체크)**: `related_audit_cases`를 참조하여 "수의계약 쪼개기(분할 발주)" 관련 감사 지적 사례 병합.

이러한 Graph 탐색은 AI가 구조화된 근거 흐름을 따라 답변하도록 유도하여 환각 가능성을 낮춤으로써 신뢰도를 높입니다.

---

## 5. Cache-Backed Legal Chain vs 현재 MCP Chain 비교 및 역할 분리

Local Legal Graph와 MCP(원천 API)는 서로 보완하는 관계로, 역할을 명확히 분리합니다.

- **Local Graph의 역할**: 빠른 근거 탐색, 복합 계층 조문 간의 즉각적 연결 제공.
- **MCP의 역할**: 법적 판단에 대한 최종 최신성 검증.
- **방어 로직 원칙**: 시스템이 캐시 기반 근거만을 확보한 상태라면 법적 결론은 확정하지 않으며 판단을 유보하거나 제한적으로만 안내합니다.

| 기능 | 현재 MCP Chain (API 의존) | 개선된 Cache-Backed Chain (Local Graph) | 효과 및 장점 |
| :--- | :--- | :--- | :--- |
| **원문 조회 속도** | API 호출당 3~10초 대기, 타임아웃 잦음 | 로컬 DB 즉각 조회 (Vector + BM25) | 목표 Latency 확보 (실제 수치는 Phase 9 성능 테스트에서 검증) 및 API 장애 내성 확보 |
| **시행령·시행규칙 연결** | `chain_law_system` 내부에서 다중 API 호출 필요 | `parent_law`, `child_rules` 기반 매핑 | 단일 검색 쿼리로 3단 비교 텍스트 즉시 구성 |
| **행정규칙·예규 추적** | `search_admin_rule` 호출. 매칭 실패 잦음 | `admin_rules` 및 `delegated_rules` 엣지 활용 | 조문 단위의 정확한 예규/기준 매칭 재현성 향상 |
| **부산시 조례 추적** | `chain_ordinance_compare` 의존 (범용 검색 한계) | `ordinances` 컬렉션 및 메타데이터 필터 적용 | 지자체 특화 질문에 대한 검색 재현성과 근거 추적 가능성을 높임 |
| **해석례·판례·감사 탐색** | 제한적 지원 (일부 QA만) | 별도 컬렉션을 통한 횡적 탐색 체계 마련 | 수의계약 등 고위험군 질의에 대해 선제적 방어/경고 제공 |

---

## 6. 위험 요소 및 대응 계획

1. **Edge 매핑의 신뢰성 확보 (위험도: 상)**
   - 법률 → 시행령 → 시행규칙 관계는 법제처 규칙 기반 파싱(Deterministic)을 적용합니다.
   - 행정규칙·조례·판례·감사사례 간의 연관 Edge 생성 시, LLM 단독의 자동 매핑은 운영 근거로 사용하지 않습니다.
   - 이러한 비정형 문서는 1차 자동 매핑 후 반드시 Human Review 또는 관리자 검수(Rule-based Verification) 프로세스를 거치도록 파이프라인을 제한합니다.
2. **기관별 자체규정 최신성 유지 (위험도: 중)**
   - 공사/공단 등 `public_institution_rules` 대상 기관은 자체 규정 개정 주기를 중앙에서 파악하기 어려우므로, 정기 수집 스케줄러(Crawling 등) 적용에 한계가 있음을 고려해야 합니다.

---

> [!IMPORTANT]
> 본 설계 문서는 구조 기획 및 Gap 분석을 위한 것이며, 현재 **Production Deployment는 계속 HOLD 상태**를 유지합니다.
