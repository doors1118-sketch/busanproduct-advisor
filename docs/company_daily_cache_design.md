# Phase 6 — 업체정보 Daily Cache 구조 설계

## 1. 현재 업체 검색 구조 요약 (As-Is)

Phase 1에서 구축된 현재의 업체 및 상품 검색 구조는 라이브 API 호출과 일부 로컬 파일 캐시가 혼재되어 동작합니다.

| 데이터 원천 | 현재 방식 | 실시간/API/로컬 여부 | 캐시 여부 | 갱신주기 | 주요 리스크 |
|---|---|---|---|---|---|
| **조달등록 부산업체 (`company_api`)** | `search_by_product`, `search_by_license`, `search_by_category` | **실시간 API** (`busanproduct.co.kr`) + 국세청 API | 국세청 상태 24H 인메모리 캐시 | 실시간 (API) / NTS 캐시 1일 | 매 호출마다 외부 API 의존(지연/타임아웃 리스크), 검색어 매칭 한계 |
| **종합쇼핑몰 상품 (`shopping_mall`)** | `search_mall_products` | **실시간 API** (`apis.data.go.kr`) | 없음 | 실시간 | 외부 공공 API 종속에 따른 잦은 Timeout, 지연 속도 발생 |
| **혁신제품 (`innovation_search`)** | ChromaDB Collection을 통한 유사도 기반 검색 | **로컬 DB** (ChromaDB Vector) | 영구 적재 | 수동 갱신 (스크립트 실행 시) | 데이터 Drift 발생 (인증 만료 등 실시간 변경 미반영) |
| **정책기업 (`policy_companies`)** | `policy_companies.json` 로드 후 태깅 병합 | **로컬 파일** (JSON) | 영구 적재 | 수동 갱신 (Excel 업데이트 시) | Excel 수동 관리로 인한 최신성 결여, 업체 상태 검증 누락 |
| **기술개발제품 (`tech_products`)** | `tech_products.json` 기반 매칭 | **로컬 파일** (JSON) | 영구 적재 | 수동 갱신 | 인증 만료 시점 미반영 리스크 |

---

## 2. Daily Cache 목표

부산 공공조달 AI 챗봇의 업체 추천 **속도**와 **안정성**을 극대화하기 위해, 하루 1회 배치로 갱신되는 통합 로컬 캐시 아키텍처를 도입합니다.

**핵심 원칙:**
1. 업체정보는 **Daily Cache를 우선 조회**하되, 캐시 장애·관리자 강제 갱신·누락 데이터 보완을 위한 live lookup fallback은 제한적으로 유지합니다.
2. 업체는 항상 확정된 계약 대상이 아닌 **"검토 후보"**로만 안내합니다.
3. 업체 후보가 존재한다는 사실이 계약 가능 여부의 자동 판단 기준이 될 수 없습니다.
4. `contract_possible_auto_promoted` 필드는 예외 없이 **`false`**를 유지합니다.
5. 법령 근거 상태(`source_status`)와 업체 데이터 상태(`company_source_status`)의 결합도를 분리하여 투명성을 확보합니다.

---

## 3. Daily Cache 대상 데이터

### 3.1 조달등록 부산업체
- `company_name`: 업체명
- `internal_join_key`: 사업자등록번호 기반 HMAC 내부 Join Key. 원본 사업자등록번호는 화면, 로그, Raw JSON, 보고서 등에 절대 노출하지 않습니다.
- `location` / `address`: 소재지 (시·군·구 및 상세주소)
- `procurement_registered`: 나라장터 조달업체 등록 여부
- `main_products`: 대표 취급 품명
- `category_codes`: G2B 물품분류번호 / UNSPSC
- `license_or_business_type`: 보유 면허, 공사/용역 업종, 기업구분
- `business_status`: 영업상태 (국세청 휴/폐업 여부 조회 결과)
- `source_refreshed_at`: 데이터 수집 시점

### 3.2 나라장터 종합쇼핑몰/MAS 상품
- `product_name`: 품목명/상품명
- `company_name`: 제조/공급업체명
- `contract_type`: 계약방법 (MAS, 제3자단가 등)
- `mas_registered` / `shopping_mall_registered`: 쇼핑몰 등록 여부
- `product_category`: 상품 분류 체계
- `delivery_region`: 납품 가능 지역 (부산 필터링용)
- `contract_valid_until`: 계약 종료일
- `price_reference_available`: 단가 존재 여부
- `source_refreshed_at`

### 3.3 정책기업 (여성/장애인/사회적/마을/창업 등)
- `company_name`
- `policy_tags`: 해당되는 정책기업 인증 태그 배열
- `certification_type`: 인증 유형 상세
- `certification_valid_until`: 인증 만료일
- `issuing_authority`: 인증 발급/관리 기관
- `matched_join_key`: 통합 조회를 위한 HMAC Key
- `match_confidence`: 업체명/번호 기반 매칭 신뢰도
- `source_refreshed_at`

### 3.4 혁신제품·혁신시제품
- `product_name`, `company_name`
- `innovation_type`: 혁신제품 구분 (FT1, FT2, FT3)
- `certification_no`: 지정번호
- `certification_valid_until`: 지정 유효기간
- `innovation_market_registered`: 혁신장터 등록 여부
- `special_procurement_route_candidate`: 특정 구매 방식(예: 수의계약) 후보군 상태 (값: `candidate`, `not_confirmed`, `expired`, `unknown` 등 상태형으로 지정. 계약 가능 여부를 boolean으로 절대 노출하지 않음)
- `source_refreshed_at`

### 3.5 기술개발제품 13종 / 우수조달물품
- `product_name`, `company_name`
- `certification_type`: 인증 종류 (우수제품, 신제품(NEP), 신기술(NET) 등)
- `certification_no`, `certification_date`, `certification_valid_until`
- `procurement_registration_status`: 조달청 우수물품 등록 상태
- `source_refreshed_at`

---

## 4. 계약유형별 검색 기준

### 4.1 물품 (goods)
- **검색 기준**: UNSPSC/G2B 물품분류번호, MAS 상품분류, 조달품목, 대표품목
- **특징**: 명확한 명칭 매칭과 표준 카테고리 기반 검색이 위주가 됨.

### 4.2 공사 (construction)
- **검색 기준**: KISCON 등 건설업 업종·면허 코드, 등록상태, 하도급 가능 공종, 지역
- **특징**: 특정 면허의 유효성이 핵심이므로, 해당 건설업 면허 보유 데이터 검색이 최우선 됨.

### 4.3 용역 (service)
- **검색 기준**: 직접생산확인 세부품명, 업종 등록·신고 기준, SW사업자·경비업 등 분야별 자격체계, 지역
- **특징**: 직접생산확인 증명서와 연동된 업종명 검색에 BM25/Vector 검색 혼합이 필요함.

### 4.4 혼합계약 (mixed)
- **검색 기준**: 주된 계약유형(주공종/주품목) + 보조 계약유형
- **예시**: 물품+설치, 소프트웨어 개발+장비 구매 등 다중 키워드 검색 및 면허+품명 동시 매칭.

---

## 5. 권장 저장 구조

다양한 검색 방식(정확, 필터, 벡터 등)의 니즈를 만족하기 위해 Polyglot Persistence 형태로 캐시를 구성합니다.

- **SQLite (또는 DuckDB)**: `company_master_cache.sqlite`, `shopping_mall_cache.sqlite`, `policy_company_cache.sqlite`, `innovation_product_cache.sqlite`, `tech_product_cache.sqlite`
  - *용도*: 정확 일치 검색, 필터링(지역, 만료일), 정렬 연산
- **BM25**: `company_search_bm25.pkl`
  - *용도*: 품목명, 업종, 수행분야 등의 유연한 형태소/키워드 검색
- **ChromaDB**: `company_search_vector` 컬렉션
  - *용도*: 비정형 검색(예: "공공기관 출입 통제용 얼굴인식 기기"), 의미망 기반 혁신제품 매칭
- **TTL Memory Cache**: 
  - *용도*: 빈번하게 유입되는 검색어(예: "종이컵", "PC")의 즉시 응답 반환을 위함

---

## 6. 업체 캐시 상태 필드 연계

응답 메타데이터에 포함되어야 할 업체의 상태 및 모드 필드는 다음과 같이 분기됩니다.

- **`company_cache_mode` (시스템 동작 모드)**
  - `none`, `live_only`, `daily_cache`, `hybrid`, `staging_local`
- **`company_source_status` (데이터 원천 결과 상태)**
  - `cached_daily`: 성공적으로 갱신된 최신 데일리 캐시에서 반환
  - `cached_stale`: 캐시는 있으나 갱신 주기(예: 24h) 초과
  - `company_cache_failed`: 캐시 장애/접근 불가
  - `no_company_query`: 업체 추천 쿼리 없음
  - `live_company_lookup`: 라이브 API를 통해 검색 (Fallback)
  - `mixed_company_sources`: 캐시와 라이브 검색의 결합
- **모니터링 및 상태 추적 필드**
  - `company_cache_used`: 캐시 사용 여부 (boolean)
  - `company_cache_refreshed_at`: 최종 갱신 시점
  - `company_cache_age_hours`: 갱신된 지 경과된 시간
  - `candidate_counts_by_type`: 후보군 개수 통계
  - `company_source_status_user_label`: 화면 노출용 상태 레이블

---

## 7. Atomic Swap 운영 설계

캐시 갱신 도중의 서비스 단절이나 오염을 방지하기 위해 **Atomic Swap** 방식을 엄격하게 적용합니다.

**갱신 절차:**
1. 임시 환경(`cache_new`) 생성
2. 원천 데이터 수집 (API, 파일, 크롤링 등)
3. 스키마 정규화 및 데이터 클렌징
4. 인덱스(DB, BM25, Vector) 빌드
5. 자체 무결성 검증 (스키마, 레코드 수, null 값 한계치 등)
6. 사전 정의된 샘플 검색어에 대한 응답 검증 (Smoke Test)
7. **성공 시**: 임시 환경(`cache_new`)을 운영 환경(`cache_current`)으로 원자적(Atomic) 심볼릭 링크 교체 / Rename
8. **실패 시**: `cache_current` 유지, 교체 취소 및 `cached_stale` (또는 장애 시 `company_cache_failed`) 알람 발생

**금지 사항:**
- 기존 캐시 덮어쓰기 및 선삭제 전면 금지
- 검증 파이프라인 통과 전 `cache_current` 교체 금지
- 무결성이 훼손된 실패 캐시의 서비스 승격 금지

---

## 8. Cache Manifest 설계

각 캐시 디렉토리/DB에는 갱신 이력과 데이터 품질을 보증하는 `manifest.json`이 동반되어야 합니다.

**Manifest 필수 필드 예시:**
```json
{
  "cache_type": "company_master",
  "created_at": "2026-05-01T02:00:00Z",
  "refreshed_at": "2026-05-01T02:30:00Z",
  "source_count": 4,
  "row_count": 25041,
  "product_count": 89002,
  "company_count": 18230,
  "valid_cert_count": 4120,
  "expired_cert_count": 89,
  "unknown_cert_count": 12,
  "version_hash": "a1b2c3d4...",
  "validation_status": "PASS",
  "validation_errors": [],
  "source_files": ["policy_202604.xlsx", "nts_batch_result.json"],
  "source_api_endpoints": ["api.odcloud.kr/v1/status"],
  "cache_schema_version": "1.2.0"
}
```

---

## 9. 사용자 표시 원칙

업체 정보는 맹신을 방지하기 위해 매우 제한적이고 보수적으로 표시해야 합니다.

**필수 고지 문구 (표 하단):**
> "위 업체는 최근 갱신된 캐시 데이터 기준의 검토 후보입니다. 실제 계약 전 조달등록 상태, 종합쇼핑몰 등록 여부, 인증 유효기간, 영업상태, 직접생산확인, 기관 내부 기준을 반드시 확인해야 합니다."

**표시 컬럼 원칙:**
- 🚫 **금지 컬럼명**: `계약 가능성`, `수의계약 가능`, `바로 계약 가능`, `구매 가능` (단정적, 확정적 어휘 배제)
- ✅ **권장 컬럼명**: `법적 적격성 확인`, `확인 필요사항`, `비고`, `검토 가능 경로`

---

## 10. 성능 목표

- **Tier 0 업체추천 질의**: `0.5초 ~ 2초` 이내 응답 반환
- **Tier 2 지역업체 전략 분석 중 업체표 생성**: `1초 ~ 3초` 이내 반환
- **업체 캐시 자체 I/O 및 검색 Latency**: `0.5초` 내외 (상위 95% 기준)
- *(※ 실제 성능 수치는 향후 Phase 9 성능 테스트에서 최종 검증 및 조정)*

---

## 11. 위험 요소 및 대응 방안

| 발생 가능한 위험 요소 | 영향도 | 대응 방안 |
|---|:---:|---|
| **폐업·휴업 업체 노출** | 상 | 배치 실행 시 국세청 상태조회 API를 통해 검증 후 `business_status` 플래그 반영. (※ 구체적인 휴·폐업 코드값은 구현 시점에 공식 API 문서 기준으로 재확인하여 적용) |
| **민감정보(사업자번호 등) 노출** | 상 | 원본 사업자번호 제거 후 HMAC 기반 `internal_join_key`로 대체. 원본은 화면, 로그, Raw JSON, 보고서 등 모든 데이터 흐름에서 전면 차단. |
| **인증 기한 만료** | 상 | 캐시 빌드 시 만료일(Valid Until) 필터 로직 적용, 만료 업체는 인증 태그 드랍. |
| **종합쇼핑몰/MAS 등록 상태 변경** | 중 | 캐시 주기가 1일이므로 하루 간격의 차이 발생 가능. 챗봇 경고 문구로 '계약 전 쇼핑몰 상태 필수 확인' 고지. |
| **가격·규격 변경** | 하 | 단가는 참고용으로만 표시하고, 조달청/쇼핑몰 최신 링크를 통한 확인을 강제. |
| **품목명 매칭 오류 (동음이의어 등)** | 중 | BM25와 Vector(Chroma)의 Hybrid Search 알고리즘 고도화 및 UNSPSC 분류 코드 교차 검증 적용. |
| **정책기업 태그 오분류** | 중 | 내부 HMAC Join Key 병합 시 `match_confidence` 평가 로직 추가. 낮은 점수 시 태그 부여 제외. |
| **캐시 갱신 실패 및 오염** | 상 | Atomic Swap 아키텍처 강제, Fail 시 기존 캐시 롤백 보장, `cached_stale` 메타데이터 전송하여 UI 경고 처리. |
| **ChromaDB / BM25 Drift 발생** | 중 | SQLite 원본 레코드 수 및 해시값과 Vector 인덱스의 Manifest 해시값을 비교하는 Watchdog(무결성 체크) 배치 구성. |
| **공사·용역 업종 분류 매칭 오류** | 상 | KISCON(건설산업정보센터) 업종 코드 등 공식 표준 코드 매핑 사전 정의 활용. |

---

## 12. 향후 구현 Phase 제안

- **Phase 7**: SQLite 기반 `company_master_cache` 구축 및 정책기업 태깅 ETL 기초 구현
- **Phase 8**: BM25 및 ChromaDB 인덱서 통합 및 캐시 Manifest 검증 로직 구현
- **Phase 9**: 성능 목표 검증 및 Atomic Swap 워크플로우 통합 스트레스 테스트

---

## 13. System Constraints

> [!WARNING]
> 본 설계 문서는 구조 기획 목적이며, **Production Deployment는 계속 HOLD 상태를 유지**합니다. 
> 현 시점에서는 어떠한 ETL 스크립트 작성이나, 라이브 서버 배포, MCP 코드 수정이 일절 금지됩니다.
