# Phase 7 — Cache Manifest + Atomic Swap 운영 상세 설계

## 1. 운영 설계 목표

업체 Daily Cache를 안전하고 무중단으로 갱신하기 위한 운영 아키텍처를 정의합니다.

1. **안전성 우선**: 캐시 갱신 실패 시 기존 캐시를 절대 삭제하지 않습니다.
2. **검증 의무**: 검증 파이프라인을 통과하지 않은 캐시를 운영 환경(current)에 승격하지 않습니다.
3. **무중단 교체**: `cache_new` → `validation` → `cache_current`로 이어지는 Atomic Swap 구조를 확립합니다.
4. **추적성 확보**: `manifest.json`을 통해 데이터 품질, 갱신 시각, 행 수, 해시 무결성을 엄격하게 추적합니다.
5. **상태 연동**: 캐시의 최신성 및 가용성 상태(`stale`, `failed` 등)를 API 응답 메타데이터(`company_source_status`)와 직결시킵니다.

---

## 2. 디렉터리 구조 설계

동시성 이슈를 방지하고 롤백을 용이하게 하기 위해 아래와 같은 디렉터리 구조를 사용합니다.

```text
cache/company/
├── cache_current/         # (Symlink) 현재 서비스가 읽고 있는 운영 캐시 디렉터리
├── cache_previous/        # (Symlink) 롤백을 대비한 직전 정상 캐시 디렉터리
├── cache_new/             # 갱신 작업이 진행 중인 격리된 임시 캐시 디렉터리
├── archive/
│   ├── 20260501_020000/   # (Directory) 최근 N개 버전 보관용 1
│   └── 20260502_020000/   # (Directory) 최근 N개 버전 보관용 2
└── manifest_history.jsonl # 전체 갱신 이력 및 해시 변동 기록 로그
```

**운영 원칙:**
- 챗봇 서버는 항상 `cache/company/cache_current` 경로만 참조합니다.
- `cache_new` 검증 실패 시, 해당 디렉터리는 폐기하거나 디버깅용으로 남기며 `cache_current`의 심볼릭 링크는 변경하지 않습니다.
- 교체 작업은 새 symlink를 임시 이름으로 생성한 뒤 `mv -T` 방식으로 진행하여 완벽한 원자성(Atomicity)을 보장합니다.

---

## 3. Cache Manifest 스키마

각 캐시 디렉터리 내부(`cache_current/manifest.json`)에 저장될 스키마 구조입니다.

```json
{
  "cache_type": "company_daily_integrated",
  "cache_schema_version": "1.0.0",
  "created_at": "2026-05-01T02:00:00Z",
  "refreshed_at": "2026-05-01T02:35:00Z",
  "source_count": 5,
  "row_count": 45000,
  "product_count": 120500,
  "company_count": 25000,
  "valid_cert_count": 8400,
  "expired_cert_count": 120,
  "unknown_cert_count": 15,
  "source_files": ["policy_202605.xlsx", "tech_dev_2026.json"],
  "source_api_endpoints": ["api.odcloud.kr/api/nts-businessman/v1/status"],
  "version_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "db_hash": "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
  "bm25_hash": "a4d3a... (생략)",
  "vector_index_hash": "b2c3d... (생략)",
  "validation_status": "PASS",
  "validation_errors": [],
  "validation_warnings": ["일부 정책기업 매칭 신뢰도(Confidence) 낮음"]
}
```

**보안 통제 원칙:**
- `source_api_endpoints` 배열에는 URL 엔드포인트만 기록하며, `serviceKey`, `API_KEY`, `OC_KEY`, `Token` 등 쿼리 파라미터나 헤더 인증 정보는 절대 기록하지 않습니다.
- 내부 HMAC 알고리즘에 사용된 `secret` 문자열은 manifest에 저장하지 않습니다.
- 원본 사업자등록번호 및 개인정보는 본 manifest 파일은 물론, 로깅, Raw JSON, 사용자 응답에도 포함되지 않아야 합니다.

---

## 4. Validation Checklist (검증 단계 설계)

`cache_new`가 생성된 후, 다음 체크리스트를 100% 통과해야만 승격(Swap)할 수 있습니다.

1. **필수 파일 존재 검증**
   - `company_master_cache.sqlite` (또는 DuckDB 파일)
   - `company_search_bm25.pkl` (BM25 인덱스)
   - `vector_index/` (ChromaDB 컬렉션 디렉터리, 존재하는 경우)
   - `manifest.json`

2. **스키마 및 데이터 타입 검증**
   - SQLite 마스터 테이블 내 필수 컬럼(예: `internal_join_key`, `company_name`) 존재 여부
   - 숫자/날짜 필드 타입 무결성 검증
   - Null 값 비율 한계치(예: 필수 필드 null 0%) 검증

3. **데이터 품질(Quality) 검증**
   - `row_count`, `company_count`, `product_count`가 이전 대비 급격히 감소(예: -20% 이상)하지 않았는지 확인
   - 인증서 만료 비율(`expired_cert_count` / `valid_cert_count`) 정상 범위 확인
   - `business_status` (휴/폐업/정상) 상태 분포 밸런스 검증

4. **검색 Smoke Test (가상 쿼리 자동 실행)**
   - 키워드: `CCTV`, `컴퓨터`, `전기공사`, `청소용역`, `행사대행`, `혁신제품`, `우수조달물품`
   - 검증 기준: 모든 테스트 쿼리에 대해 에러가 미발생해야 하며, 응답 시간은 0.5초 이내여야 합니다. 
   - Seed 데이터가 존재하는 쿼리는 반드시 1건 이상의 후보를 반환해야 하며, Seed가 없는 쿼리의 경우 `no_results` 반환도 정상 응답으로 간주합니다 (애플리케이션 오류와 명확히 구분).

5. **보안 검증 (Security Check)**
   - DB 및 텍스트 인덱스 내에 원본 사업자등록번호 정규식(예: `\d{3}-\d{2}-\d{5}` 또는 연속된 10자리 숫자 패턴) 검출 여부 스캔 (발견 시 Fail)
   - 전화번호, 대표자명 등 불필요한 개인 식별 정보 무단 적재 여부 샘플링 검사
   - API 키, Password 등 크리덴셜 문자열 하드코딩 검출 테스트

---

## 5. Atomic Swap 절차

검증(Validation)을 통과한 후의 물리적 교체 절차입니다. `mv -T`를 활용하여 원자성을 극대화하고 `cache_previous`의 안전성을 보장합니다.

1. **Locking**: 갱신 프로세스 중복 실행을 막기 위해 파일 Lock 획득.
2. **Read Current Target**: 현재 `cache_current` 심볼릭 링크가 가리키고 있는 실제 경로(Target)를 읽어서 변수(예: `old_target`)에 임시 보관합니다.
3. **Prepare Swap**: 
   - `cache_new` 폴더의 이름을 현재 타임스탬프 폴더(예: `archive/20260501_023500`)로 변경.
   - 새 심볼릭 링크를 임시 이름으로 생성: `ln -s archive/20260501_023500 cache_current.new`
4. **Atomic Swap**: `mv -T cache_current.new cache_current` 명령을 실행하여 현재 운영 중인 캐시 링크를 끊김 없이 원자적으로 교체합니다.
5. **Update Previous**: Swap이 성공적으로 완료된 후, 2번 단계에서 보관해 둔 `old_target` 경로를 바라보도록 `cache_previous` 심볼릭 링크를 갱신합니다. (Swap 성공 전에는 절대 기존 `cache_previous`를 임의 삭제하지 않음)
6. **Cleanup**: 보관 기간(예: 7일 또는 최근 N개 버전)이 지난 `archive/` 폴더 내 과거 캐시 데이터 백그라운드 삭제. 
   - 장기적인 이력 관리는 디렉터리를 지우더라도 `manifest_history.jsonl` (또는 압축 스냅샷)을 통해 별도 관리합니다.
7. **Unlock**: 파일 Lock 해제.

---

## 6. `company_source_status` 상태 매핑

캐시 가용성 여부에 따라 챗봇 메타데이터를 결정합니다.

| 조건 | `company_source_status` | `company_cache_mode` | 설명 |
|---|---|---|---|
| 캐시 존재 + 24시간 이내 갱신 | `cached_daily` | `daily_cache` | 최상 상태. 로컬 캐시 100% 의존. |
| 캐시 존재 + 24시간 초과 | `cached_stale` | `daily_cache` | 어제 데이터를 사용함. 배치 실패 가능성 큼. |
| 캐시 갱신 실패 + 기존 캐시 유지 | `cached_stale` | `daily_cache` | 배치가 터졌으나 기존 캐시로 서비스 연명 중. |
| 캐시 없음 + Live Fallback 성공 | `live_company_lookup` | `live_only` | 최초 구동이거나 로컬 디스크 장애 시. API 응답 정상. |
| 캐시 없음 + Live Fallback 실패 | `company_cache_failed` | `none` | 전면 장애. 후보를 반환하지 못함. |
| 특정 항목 캐시 조회 + 부족분 Live 조회 | `mixed_company_sources` | `hybrid` | 제한적 Fallback 발동 상태. |

---

## 7. 장애 및 롤백 시나리오

| 장애 상황 | 사용자 영향 | `company_source_status` | 롤백/복구 방식 | 알림 여부 | 운영자 조치 |
|---|---|---|---|:---:|---|
| **`cache_new` 생성 실패** (API 연동 장애 등) | 없음 | `cached_stale` | Swap 미실행, `cache_current` 자연 유지 | Y | 원천 API 상태 확인 및 수동 배치 재실행 |
| **행 수(Row Count) 급감** | 없음 | `cached_stale` | Validation 실패로 Swap 중단 | Y | 원천 파일 누락 여부 확인 |
| **BM25 / Vector Index 빌드 실패** | 없음 | `cached_stale` | Validation 실패로 Swap 중단 | Y | 메모리/디스크 공간 및 형태소 분석기 확인 |
| **Manifest Validation 실패** | 없음 | `cached_stale` | Swap 중단 및 `validation_errors` 기록 | Y | 스키마 변경 사항 또는 누락 필드 디버깅 |
| **Symlink Swap(원자 교체) 실패** | 없음 (이론상) | `cached_stale` | `mv -T` 실패 시 기존 `cache_current` 그대로 유지됨 | Y | 파일 시스템 권한 및 I/O 에러 점검 |
| **`cache_current` 디스크 손상** | 조회 지연 발생 | `live_company_lookup` | `cache_previous`로 심볼릭 링크 수동 복구 또는 Live API Fallback | Y | 파일 시스템 복구 후 캐시 재생성 |
| **Live Fallback마저 실패** | 추천 불가 알림 | `company_cache_failed` | 롤백 불가 (최종 장애) | Y (Critical) | 시스템 전면 점검 및 외부망(NTS 등) 확인 |

---

## 8. 향후 구현 Phase 제안

- **Phase 8**: Python 기반 `CacheBuilder` 클래스 및 ETL 로직 초안 작성 (DB 생성 및 무결성 검증 함수 구현)
- **Phase 9**: `company_api.py` 내부 라우팅 로직(캐시 우선, 실패 시 fallback) 변경 및 UI 응답 포맷 연동

---

## 9. System Constraints

> [!WARNING]
> 본 문서는 Cache 운영 방식 상세 기획을 위한 설계 문서입니다. **Production Deployment는 계속 HOLD 상태**를 유지합니다. 
> 현 시점에서는 어떠한 ETL 파이프라인 구현이나, 라이브 서버로의 배포, MCP 코드 수정도 실행되지 않았습니다.
