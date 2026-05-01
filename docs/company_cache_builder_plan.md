# Phase 8 — CacheBuilder / ETL 최소 구현 계획

## 1. MVP 범위 (최소 구현 범위)
초기 안정성 확보를 위해 캐시 파이프라인의 뼈대를 세우는 데 집중합니다.

- **조달등록 부산업체**: `company_master_cache` 구축
- **정책기업 태그**: `policy_companies.json` 데이터를 로드하여 조달업체와 Join (`internal_join_key` 사용)
- **기술개발제품 후보**: `tech_products.json` 기반 매칭
- **혁신제품**: 기존 Innovation ChromaDB는 읽기 전용으로 사용하며 이번 파이프라인에서 재구축하지 않음
- **종합쇼핑몰/MAS**: 실시간 API 연동으로 유지하며, 배치 수집은 후속 Phase로 연기

## 2. 제외 범위
MVP 단계에서 아래 항목들은 과감히 제외하여 복잡도를 낮춥니다.

- 나라장터 MAS 전체 상품 대량 캐시화
- 국세청 상태조회 API 대량 호출 자동화 (초기엔 정적 결과만 활용)
- ChromaDB 신규 Vector 인덱스 빌드 파이프라인
- 공사·용역 전체 업종의 세부 표준코드 매핑 (기본 키워드 매칭만 수행)
- `company_api.py` 내의 Live Fallback 라우팅 구조 본격 변경
- 챗봇 UI 상의 메타데이터 표시 및 포맷 변경

---

## 3. CacheBuilder 클래스 책임
`CacheBuilder` 클래스는 캐시의 생애주기 중 갱신 및 검증 단계를 전담하는 컨트롤 타워 역할을 수행합니다.

- `cache_new` 디렉터리 등 임시 워크스페이스 생성
- 데이터 원천(파일, API 등) 로드
- 스키마 정규화 (Normalization)
- 정책기업 및 기술개발제품 태그 병합 (Join)
- SQLite (또는 DuckDB) 데이터베이스 파일 생성 및 데이터 적재
- `manifest.json` 생성 (통계 및 해시 기록)
- `cache_new` 무결성, 보안, 스모크 테스트 실행 (Validation)
- 검증 완료 시 Atomic Swap 계획(Plan) 준비
- 교체 후 `manifest_history.jsonl`에 이력 기록

---

## 4. 메서드 설계 (권장)
- `prepare_workspace()`: `cache_new` 폴더 생성 및 초기화
- `load_sources()`: 원천 파일 로드
- `normalize_company_master()`: 업체 마스터 데이터 클렌징
- `join_policy_tags()`: 정책 태그 매핑 로직
- `join_tech_products()`: 기술개발제품 데이터 결합
- `write_sqlite_cache()`: DB 커넥션 및 Insert 실행
- `build_bm25_index()`: 텍스트 검색 인덱스 빌드 (MVP에서는 설계만 반영 또는 Skip 가능)
- `write_manifest()`: 메타데이터 추출 및 JSON 생성
- `validate_cache()`: 품질, 스키마, 보안 검증 실행
- `promote_cache()`: (설계) Atomic Swap 실행
- `rollback()`: (설계) 검증 실패 시 정리 및 로깅

---

## 5. 입력 데이터 원천표

조달등록 부산업체 Source가 구체화되지 않으면 구현에 진입할 수 없습니다. 따라서 아래와 같이 명세를 확정합니다.

| source | 조달등록 부산업체 (Master) | policy_companies.json | tech_products.json |
|---|---|---|---|
| **source_path_or_endpoint** | `data/busan_companies_raw.csv` (가칭) | `app/policy_companies.json` | `app/tech_products.json` |
| **source_format** | CSV (수동 추출) 또는 DB | JSON | JSON |
| **required_columns** | 업체명, 사업자번호(필수), 주소, 대표업종, 주생산품 | `name`, `tags`, `biz_no` 등 | `product_name`, `company_name` 등 |
| **business_no_available** | **Y** | **Y** | N (업체명 의존) |
| **refresh_method** | 수동 업데이트 후 배치 재실행 | 수동 업데이트 | 수동 업데이트 |
| **expected_row_count** | ~ 20,000 | ~ 5,000 | ~ 3,000 |
| **owner** | 시스템 관리자 | 시스템 관리자 | 시스템 관리자 |
| **민감정보 포함 여부** | **Y** (원본 사업자번호 포함) | 구현 전 민감정보 스캔 필수 | N |
| **MVP 포함 여부** | **Y** | **Y** | **Y** |

> **[보안 원칙: `policy_companies.json` 민감정보 재확인]**
> 구현 파이프라인 진입 직전, 해당 JSON 내에 평문 사업자번호, 대표자명, 연락처, 인증번호가 포함되어 있는지 반드시 스캔해야 합니다. 원본 사업자번호가 존재한다면 HMAC 변환 후 메모리에서 즉시 폐기합니다.

---

## 6. SQLite 스키마 초안 (제약조건 및 인덱스 포함)

### 6.1 `companies` 테이블
- `internal_join_key` (TEXT)
- `company_name` (TEXT)
- `location` (TEXT)
- `address_region` (TEXT)
- `main_products_json` (TEXT) - MVP에서는 JSON array string으로 저장, 후속 고도화 시 정규화 테이블 전환 권장
- `category_codes_json` (TEXT) - MVP에서는 JSON array string으로 저장
- `license_or_business_type` (TEXT)
- `procurement_registered` (BOOLEAN)
- `business_status` (TEXT)
- `source_refreshed_at` (DATETIME)
- **Constraints & Indexes**:
  - `PRIMARY KEY (internal_join_key)`
  - `INDEX idx_company_name (company_name)`
  - `INDEX idx_address_region (address_region)`
  - `INDEX idx_license_or_business_type (license_or_business_type)`

### 6.2 `policy_tags` 테이블
- `internal_join_key` (TEXT)
- `company_name` (TEXT)
- `policy_tag` (TEXT)
- `certification_type` (TEXT)
- `certification_valid_until` (DATE)
- `issuing_authority` (TEXT)
- `match_confidence` (REAL)
- `source_refreshed_at` (DATETIME)
- **Constraints & Indexes**:
  - `UNIQUE (internal_join_key, policy_tag, certification_type)`
  - `INDEX idx_policy_join_key (internal_join_key)`
  - `INDEX idx_policy_tag (policy_tag)`

### 6.3 `tech_products` 테이블
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT) - Surrogate PK
- `product_name` (TEXT)
- `company_name` (TEXT)
- `internal_join_key` (TEXT)
- `certification_type` (TEXT)
- `certification_no` (TEXT)
- `certification_date` (DATE)
- `certification_valid_until` (DATE)
- `procurement_registration_status` (TEXT)
- `source_refreshed_at` (DATETIME)
- **Constraints & Indexes**:
  - `UNIQUE (product_name, company_name, certification_type)`
  - `INDEX idx_tech_company_name (company_name)`
  - `INDEX idx_tech_cert_type (certification_type)`
  - `INDEX idx_tech_cert_valid_until (certification_valid_until)`

> **[보안 금지사항]**
> - 원본 사업자등록번호는 어떠한 테이블에도 저장하지 않습니다.
> - 대표자명, 전화번호 등 검색에 불필요한 개인 식별 정보는 적재하지 않습니다.
> - API Key, ServiceKey 등 크리덴셜 값은 DB에 저장하지 않습니다.

---

## 7. HMAC 내부 Join Key 설계

**원본 사업자등록번호가 존재하는 경우:**
- 사업자번호를 평문으로 쓰지 않고 `HMAC-SHA256` 해시 기반의 `internal_join_key`로 변환하여 사용합니다.
- HMAC 서명에 사용될 `secret` 키는 소스코드에 하드코딩하지 않고 환경변수(Environment Variables) 또는 분리된 Secret Store에서만 읽어옵니다.
- 해당 `secret`은 `manifest.json`, 로그, Raw JSON에 절대 노출되거나 기록되어서는 안 됩니다.

**원본 사업자등록번호가 없는 경우:**
- 업체명과 소재지(주소)를 결합한 Fuzzy Match 알고리즘을 사용합니다.
- 이 경우 교차 검증의 불확실성을 반영하여 `match_confidence`를 낮게(예: 0.8 미만) 부여합니다.
- `match_confidence`가 기준치 이하인 레코드는 여성/장애인/사회적기업 등의 민감한 정책 태그 자동 부여를 **금지**합니다.

---

## 8. Validation 함수 목록

`CacheBuilder.validate_cache()` 내부에서 실행할 필수 검증 함수입니다.

**데이터 및 스키마 검증:**
- `check_required_files_exist()`: SQLite DB, Manifest 존재 여부
- `check_sqlite_schema_valid()`: 필수 테이블 및 컬럼 무결성 검증
- `check_row_count_minimum()`: 전체 데이터 건수가 임계치 이상인지 검증
- `check_join_key_not_null_ratio()`: `internal_join_key`의 결측치 비율 확인
- `check_policy_tag_join_sanity()`: 비정상적으로 조인된 정책 태그 급증 확인
- `compute_expired_certification_count()`: 만료된 인증서 집계 확인

**보안 검증:**
- `scan_raw_business_number_pattern()`: \d{3}-\d{2}-\d{5} 등 원본 사업자번호 잔존 여부 (발견 시 Fail)
- `scan_api_token_pattern_absent()`: DB/Manifest 내 API 키 패턴 하드코딩 여부 스캔

**Sample Query Smoke Test:**
1. **Seed 데이터 존재 확인 쿼리 (min_results >= 1 필수)**:
   - "CCTV", "컴퓨터", "기술개발제품", "우수조달물품"
2. **No Results 허용 그룹 (에러가 발생하지 않으면 정상 간주)**:
   - "전기공사", "청소용역" (MVP에서는 기본 키워드 매칭만 수행하므로 Seed 확정 전까지 결과 없음을 허용)
   - 극히 희귀한 키워드 조회

> ※ 테스트에 사용된 Seed Query 목록은 `manifest.json`에 `seed_queries` 필드로 명시하여 기록으로 남깁니다.

---

## 9. Manifest 작성 규칙

Manifest는 데이터의 버저닝과 품질 보증을 위한 메타데이터 파일입니다.

**포함 필드:**
- `cache_type`, `cache_schema_version`
- `created_at`, `refreshed_at`
- `row_count`, `company_count`
- `valid_cert_count`, `expired_cert_count`, `unknown_cert_count`
- `source_files`, `version_hash`, `db_hash`
- `seed_queries` (Smoke test용 시드 배열)
- `validation_status`, `validation_errors`, `validation_warnings`

**기록 전면 금지 항목 (Security Blacklist):**
- 공공데이터포털 등 `serviceKey`
- 기타 모든 `API key`, `OC_KEY`, `password`, `token`
- 원본 사업자등록번호 평문
- HMAC 해시 알고리즘에 사용된 `secret`

---

## 10. Atomic Swap 구현 계획 (Phase 8 설계 전용)

실제 코드로 구현하지 않으며 절차만 명세합니다.

1. 갱신 프로세스 중복 방지를 위한 **Lock 획득**
2. 현재 활성 캐시 경로 파악을 위한 **`current_target` 읽기 및 임시 보관**
3. `cache_new` 디렉터리 **검증 (Validation) 파이프라인 실행**
4. 성공 시 `cache_new`를 `archive/[timestamp]` 디렉터리로 **Rename**
5. 새 경로를 바라보는 임시 심볼릭 링크 **`cache_current.new` 생성**
6. **`mv -T cache_current.new cache_current`** 명령을 통한 원자적(Atomic) 교체
7. 교체 성공 후 보관해 둔 구 타겟(`current_target`)을 향하도록 **`cache_previous` 갱신**
8. 전체 이력을 **`manifest_history.jsonl`에 기록**
9. 파일 **Unlock** 및 배치 종료

---

## 11. 구현 순서 (향후 Phase 참조)

1. `CacheBuilder` 클래스 및 빈 메서드 스켈레톤 작성
2. 로컬 데이터 원천 로드 로직
3. 업체 마스터 데이터 및 HMAC Join Key 정규화 모듈 (`Normalizer`)
4. SQLite DB 스키마 생성 및 데이터 적재기 (`Writer`)
5. 보안, 품질, 스모크 테스트를 포함한 검증 로직 (`Validator`)
6. Atomic Swap 제어 로직 (`Promoter`) 통합

---

## 12. 위험 요소

- **HMAC Secret 노출**: `.env` 관리 소홀 시 키 노출 위험.
- **원천 파일 결측**: 마스터 데이터나 JSON 소스 파일이 워크스페이스에 없을 경우 ETL 정지.
- **가짜 매칭 (False Positive)**: 사업자번호 부재 시 Fuzzy Match로 인한 엉뚱한 정책기업 태그 부여 발생 (Confidence 제한으로 방어 필수).

---

## 13. System Constraints

> [!WARNING]
> 본 문서는 `CacheBuilder` 클래스의 최소 구현 범위 기획 목적이며, **Production Deployment는 계속 HOLD 상태**를 유지합니다. 
> 현 시점에서는 어떠한 파이썬 스크립트 작성, ETL 파이프라인 로직 구현, 서버로의 배포, MCP 코드 수정도 실행되지 않았습니다.
