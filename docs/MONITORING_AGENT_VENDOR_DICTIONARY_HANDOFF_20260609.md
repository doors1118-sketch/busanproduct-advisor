# Monitoring Agent Handoff - Vendor Dictionary and Procurement Item Catalog

작성일: 2026-06-09
대상: 모니터링 시스템 담당 에이전트
범위: 지역기업 추천/검색 서비스의 품목, 면허, 정책조건 사전 통합 운영

## 1. 현재 결론

업체추천 서비스는 LLM/Vertex 없이 내부 DB 기반으로 운영한다.

모니터링 시스템은 데이터 생산자 역할을 맡고, 챗봇/V2는 검증된 read-only cache DB를 소비하는 구조가 맞다.

```text
조달청 물품목록정보서비스
  -> 모니터링 파이프라인 수집/정제
  -> /opt/busan/chatbot_company.db 또는 모니터링 원천 DB에 적재
  -> 검증
  -> /opt/advisor/cache/company/cache_current/chatbot_company.db 배포
  -> 챗봇 업체추천 API read-only 조회
```

챗봇 런타임에서 조달청 API를 직접 호출하지 않는다. 외부 API 지연, 장애, 트래픽 제한이 사용자 응답시간에 직접 반영되기 때문이다.

## 2. 오늘 챗봇 쪽 변경 내역

수정 파일:

- `app/policies/item_normalization_policy.py`
- `app/api_server.py`
- `tests/test_item_normalization_policy.py`
- `tests/test_vendor_api_endpoints.py`
- `scratch/run_vendor_expansion_probe.py`

주요 보강:

- 품목/면허 사전 확장
  - 도서, 우유, 식육, 채소, 과일, 김치
  - 건축설계, 디자인, 영상제작, 홍보마케팅
  - 정보시스템, 디지털콘텐츠, 방송장치, 비디오프로젝터
  - 배전반, UPS, 태양광, 승강기
  - 방역/소독, 폐기물, 지질조사, 측량, 원가계산, 법무, 여행/전세버스
  - 피복, 안전화, 마스크, 손소독제, 복사용지, 토너, 드론

- 우선순위 보정
  - `홍보 마케팅 용역 업체`가 `행사용역`으로 과매칭되는 문제 보정
  - `음향 조명 장비 임대 업체`가 `구내방송장치`로 과매칭되는 문제 보정
  - `손소독제 구매 업체`가 `소독업/방역서비스`로 과매칭되는 문제 보정
  - `LED 조명`이 음향조명임대로 잡히지 않도록 `음향조명임대` override 범위 축소

- 정책조건 사전 확장
  - 기존: 여성기업, 장애인기업, 사회적기업
  - 추가: 소상공인, 창업기업, 청년창업기업, 벤처기업, 사회적협동조합, 자활기업, 마을기업

## 3. 서버 반영 상태

반영 위치:

- `/opt/advisor/app/api_server.py`
- `/opt/advisor/app/policies/item_normalization_policy.py`

서비스 상태:

- `busan-advisor-pilot.service=active`
- 최종 재시작: `2026-06-09 11:07:40 KST`

서버 백업:

- `/opt/advisor/backups/codex_vendor_dict_priority_20260609_110240`
- `/opt/advisor/backups/codex_vendor_policy_rules_20260609_110733`

주의: 오늘 변경은 챗봇/업체추천 API 쪽 반영이다. 모니터링 DB schema에는 아직 반영하지 않았다.

## 4. QA 결과

로컬 단위 테스트:

```text
PYTHONPATH=. pytest -q tests/test_item_normalization_policy.py tests/test_vendor_api_endpoints.py
32 passed in 0.40s
```

확장 probe:

```text
python -X utf8 scratch/run_vendor_expansion_probe.py --base-url http://49.50.133.160:8001
ok=52/52
avg_ms=707.7
p50_ms=611.0
max_ms=1896
```

artifact:

- `artifacts/vendor_recommendation_quality_qa/vendor_expansion_probe_20260609_110925.jsonl`

기존 100개 품질 QA 회귀:

```text
python -X utf8 scratch/run_vendor_recommendation_quality_qa.py --base-url http://49.50.133.160:8001
ok=100/100
avg_score=100.0
min_score=100
avg_latency_ms=954.6
p50_ms=802.5
max_latency_ms=2557
```

artifact:

- `artifacts/vendor_recommendation_quality_qa/vendor_recommendation_quality_qa_20260609_110930.md`
- `artifacts/vendor_recommendation_quality_qa/vendor_recommendation_quality_qa_20260609_110930.jsonl`

## 5. 모니터링 시스템에서 해야 할 작업

### 5.1 조달청 물품목록정보서비스 적재

공공데이터포털 조달청 물품목록정보서비스를 런타임 호출하지 말고 배치/캐시로 적재한다.

권장 테이블:

```sql
CREATE TABLE procurement_item_catalog (
  item_class_code TEXT,
  item_class_name TEXT,
  detail_item_code TEXT PRIMARY KEY,
  detail_item_name TEXT NOT NULL,
  source_updated_at TEXT,
  ingested_at TEXT NOT NULL
);
```

목적:

- 사용자 검색어를 조달 표준 품명/세부품명번호로 연결
- `product_policy_summary.detail_product_code`와 안정적으로 조인
- 챗봇 코드에 품목명을 계속 하드코딩하지 않도록 개선

### 5.2 alias/rule DB화

현재 챗봇 코드에 있는 `item_normalization_policy.py`는 운영 사전의 임시 fallback으로 보고, 모니터링 DB가 아래 사전을 생산해야 한다.

```sql
CREATE TABLE procurement_item_alias (
  alias TEXT NOT NULL,
  canonical_type TEXT NOT NULL,     -- item / license / policy
  canonical_name TEXT NOT NULL,
  search_term TEXT NOT NULL,
  detail_item_code TEXT,
  priority INTEGER DEFAULT 100,
  confidence REAL DEFAULT 0.90,
  negative_context TEXT,
  source TEXT DEFAULT 'manual',
  source_date TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (alias, canonical_type, search_term)
);
```

필요한 표현 예:

```text
백신 프로그램 -> 보안소프트웨어
손소독제 -> 손소독제
소독업체 -> 소독업
홍보 마케팅 -> 홍보및마케팅서비스
음향 조명 장비 임대 -> 영상.음향및조명장치임대서비스
건축설계 -> 건축설계용역 / 건축사사무소
방역서비스 -> 방역서비스 / 소독업
정보시스템 개발 -> 정보시스템개발서비스 / 소프트웨어사업자
```

negative context가 중요하다.

```text
백신 프로그램: 의약품/예방접종 쪽으로 보내지 않음
손소독제 구매: 소독업체/방역서비스로 보내지 않음
홍보 마케팅: 행사대행 단독으로 보내지 않음
음향 조명 임대: LED 조명 구매로 보내지 않음
```

### 5.3 품목-면허 매핑

조달청 물품목록 API만으로 면허 매핑은 해결되지 않는다.

별도 rule table이 필요하다.

```sql
CREATE TABLE item_license_map (
  detail_item_code TEXT,
  detail_item_name TEXT,
  required_license TEXT NOT NULL,
  match_type TEXT NOT NULL,         -- required / recommended / review
  source TEXT,
  memo TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (detail_item_code, required_license, match_type)
);
```

예:

```text
방역서비스 -> 소독업
건축설계용역 -> 건축사사무소
정보시스템개발서비스 -> 소프트웨어사업자
승강기유지보수서비스 -> 승강기유지관리업
폐기물수집운반 -> 폐기물수집운반업
측량용역 -> 측량업
```

### 5.4 정책조건 데이터 보강

챗봇 API는 아래 정책조건 표현을 인식한다.

```text
여성기업
장애인기업
사회적기업
소상공인
창업기업
청년창업기업
벤처기업
사회적협동조합
자활기업
마을기업
```

현재 확인된 제한:

- 소상공인, 창업기업은 일부 후보 row에서 매칭됨.
- 벤처기업, 사회적협동조합, 자활기업, 마을기업은 질문 조건 인식은 되지만 현재 후보 row/보조 JSON에 충분한 데이터가 없어 `not_found_in_candidates`가 발생할 수 있다.
- 따라서 모니터링 DB가 정책기업 원천을 확장해야 한다.

현재 보조 JSON:

- `app/policy_companies.json`
- 주로 여성기업, 장애인기업, 사회적기업 중심
- 벤처/사회적협동조합/자활/마을기업 보강 필요

## 6. 챗봇 쪽 다음 변경 방향

모니터링 DB가 alias/rule 테이블을 제공하면 챗봇은 아래 순서로 바꾸면 된다.

```text
1. DB 기반 alias/rule adapter 추가
2. procurement_item_alias 우선 조회
3. item_license_map으로 면허 search_plan 추가
4. product_policy_summary와 detail_item_code 조인
5. 기존 item_normalization_policy.py는 fallback 유지
6. QA 실패 케이스를 alias 후보 CSV/JSONL로 export
```

중요 원칙:

- 챗봇은 모니터링 운영 DB를 직접 수정하지 않는다.
- 챗봇은 `/opt/advisor/cache/company/cache_current/chatbot_company.db`만 read-only 조회한다.
- 모니터링 파이프라인은 검증 통과한 DB만 cache로 배포한다.
- 외부 API는 모니터링 배치에서만 호출한다.

## 7. 모니터링 에이전트에게 전달할 즉시 작업

1. 조달청 물품목록정보서비스 수집 PoC
   - 품명/세부품명번호를 SQLite table로 적재
   - 최소 1회 전체 또는 키워드 기반 샘플 수집

2. `procurement_item_alias` 초안 생성
   - 오늘 챗봇 코드의 `_ITEM_SYNONYM_GROUPS`와 `_PREFERRED_ITEM_QUERY_OVERRIDES`를 DB row로 변환
   - source는 `chatbot_manual_20260609`

3. `item_license_map` 초안 생성
   - 오늘 추가한 품목 중 면허 의존성이 강한 항목부터 작성
   - 건축설계, 방역, 정보시스템, 승강기, 폐기물, 측량, 전세버스, 법무

4. 정책기업 원천 보강
   - 벤처기업
   - 사회적협동조합
   - 자활기업
   - 마을기업
   - 소상공인/소기업 여부

5. 캐시 배포 전 검증에 추가할 항목

```sql
SELECT COUNT(*) FROM procurement_item_catalog;
SELECT COUNT(*) FROM procurement_item_alias;
SELECT COUNT(*) FROM item_license_map;
SELECT COUNT(*) FROM product_policy_summary;
SELECT COUNT(*) FROM chatbot_company_candidate_view;
```

6. 배포 후 smoke QA

```text
도서 구매 업체
건축설계용역 업체
홍보 마케팅 용역 업체
음향 조명 장비 임대 업체
손소독제 구매 업체
소상공인 LED 업체
벤처기업 정보시스템 업체
```

## 8. 주의할 점

- 조달청 물품목록정보서비스는 품목 표준화에는 유용하지만 면허 판단을 직접 제공하지 않는다.
- 품목 표준화만으로 업체추천 품질이 완성되지 않는다. `품목 -> 면허`, `품목 -> 정책조건`, `alias -> negative context`가 함께 필요하다.
- QA 통과 수치는 현재 서버/현재 DB 기준이다. 모니터링 DB schema 변경 후에는 동일 QA를 다시 돌려야 한다.
- 챗봇 쪽 하드코딩 사전은 운영 전환 시 DB fallback으로 낮춰야 한다. 단, DB 전환 초기에 즉시 제거하면 회귀 위험이 크다.

## 9. 업체추천 챗봇 운영 구성

### 9.1 프로세스와 포트

현재 업체추천 API는 기존 챗봇 API 서비스에 붙어 있다.

```text
API service: busan-advisor-pilot.service
API port: 8001
Streamlit UI service: law-chatbot.service
Streamlit UI port: 8502
```

기본 외부 확인 URL:

```text
http://49.50.133.160:8001/health
http://49.50.133.160:8001/version
http://49.50.133.160:8502
```

2026-06-09 확인 결과:

```json
GET /health
{"status":"ok","service":"busanproduct-advisor-api","production_deployment":"HOLD"}

GET /version
{"commit_hash":"ed722e5","model_primary":"gemini-2.5-flash","model_fallback":"gemini-2.5-flash","prompt_mode":"dynamic_v1_4_4","model_routing_mode":"risk_based","production_deployment":"HOLD"}
```

`production_deployment=HOLD`는 이 API가 운영 확정판이라기보다 테스트/파일럿 성격임을 나타낸다.

### 9.2 주요 코드 경로

```text
app/api_server.py
  - /vendor-recommendations/search
  - /vendors/search
  - /vendors/query.csv
  - /vendors/download.csv
  - /vendors/download.zip

app/company_db.py
  - chatbot_company.db read-only adapter
  - chatbot_company_candidate_view 조회
  - product_policy_summary 조회

app/policies/item_normalization_policy.py
  - 현재 코드 기반 품목 alias fallback
  - 운영 DB alias/rule로 이전할 대상

app/pages/vendor_search.py
  - 별도 업체추천 Streamlit 화면
  - 품목/예산 입력
  - 정책요약/업체카드 표시
  - 검색결과 CSV 다운로드
  - 전체 ZIP 다운로드

app/pages/💬_법령챗봇.py
  - 기존 챗봇 화면에 붙인 간단 업체검색 패널
  - 현재는 별도 업체추천 화면이 더 중요
```

### 9.3 환경변수

챗봇 API:

```text
CHATBOT_COMPANY_DB_PATH=/opt/advisor/cache/company/cache_current/chatbot_company.db
COMPANY_VIEW_DB_ENABLED=true
MONITORING_COMPANY_API_BASE_URL=http://127.0.0.1:8000
```

의미:

- `CHATBOT_COMPANY_DB_PATH`: 챗봇이 읽는 read-only 배포본 DB. 운영 기본 경로.
- `COMPANY_VIEW_DB_ENABLED`: DB 직접조회 사용 여부.
- `MONITORING_COMPANY_API_BASE_URL`: DB view/schema 불일치 시 fallback. 기본 경로가 아니다.

Streamlit UI:

```text
CHATBOT_API_URL=http://127.0.0.1:8001/chat
VENDOR_SEARCH_REGION=busan
VENDOR_CARD_DISPLAY_LIMIT=12
PILOT_AUTH_USER=...
PILOT_AUTH_PASSWORD=...
```

주의: 문서에는 인증값을 적지 않는다.

## 10. 업체추천 API 명세 요약

상세 명세 문서:

```text
docs/VENDOR_RECOMMENDATION_API_SPEC_20260609.md
```

### 10.1 추천 검색

```http
GET /vendor-recommendations/search?q=LED&region=busan&limit=30&budget_krw=50000000&include_product_policy=true
```

역할:

- 품목/면허/정책조건 검색어 정규화
- 업체 후보 조회
- 품목 정책요약 조회
- 정책기업 조건 요약
- LLM 사용 없음

중요 response fields:

```text
rows[]
search_plan[]
item_policy_summary
product_policy_checks[]
policy_preference_summary
policy_company_alternatives[]
mode=vendor_recommendation_only
llm_used=false
limitations[]
```

### 10.2 단순 업체검색

```http
GET /vendors/search?q=LED&region=busan&limit=50
```

역할:

- 가벼운 업체 후보 row 조회
- 기존 챗봇 패널 또는 CSV export용
- 품목정책 요약은 `/vendor-recommendations/search`가 더 적합

### 10.3 검색결과 CSV 다운로드

```http
GET /vendors/query.csv?q=LED&region=busan&limit=50
GET /vendors/search.csv?q=LED&region=busan&limit=50
```

### 10.4 전체 ZIP 다운로드

```http
GET /vendors/download.zip?active_only=true&limit=0
GET /vendors/download.csv?active_only=true&limit=0
```

2026-06-09 운영 수정:

- 기존에는 `active_only=true`가 `business_status='active'`만 내보냈다.
- 현재 DB는 `business_status=unknown`, `display_status=후보` 중심이라 기본 ZIP이 헤더만 내려가는 문제가 있었다.
- 수정 후 기준:
  - `active_only=true`는 `inactive`, `closed`, `폐업`, `휴업`, `종료`, `cancelled`, `canceled`만 제외한다.
  - `unknown/후보`는 다운로드에 포함한다.

검증:

```text
/vendors/download.zip?active_only=true&limit=20
csv_rows_including_header=21
```

관련 백업:

```text
/opt/advisor/backups/codex_vendor_download_filter_20260609_142542
```

## 11. DB와 캐시 운영

### 11.1 권장 운영 경로

```text
원천 DB:
/opt/busan/chatbot_company.db
  - 모니터링 파이프라인 생성/갱신
  - 챗봇이 직접 읽지 않는 것이 원칙

챗봇 조회 DB:
/opt/advisor/cache/company/cache_current/chatbot_company.db
  - 검증 통과 후 배포된 read-only 스냅샷
  - 챗봇 API가 이 DB만 읽음
```

### 11.2 필수 view/table

```text
chatbot_company_candidate_view
product_policy_summary
direct_production_certificate
```

최소 검증 SQL:

```sql
SELECT COUNT(*) FROM chatbot_company_candidate_view;
SELECT COUNT(*) FROM product_policy_summary;
SELECT COUNT(*) FROM direct_production_certificate;
```

이전 운영 기준 하한값:

```text
chatbot_company_candidate_view >= 46,000
product_policy_summary >= 4,000
direct_production_certificate >= 11,000
```

실제 배포 전에는 최신 운영 DB 기준으로 다시 잡아야 한다.

### 11.3 cache sync 자동화

현재 검증된 자동화 형태:

```text
/opt/advisor/scripts/sync_company_view_db.py --apply
/etc/systemd/system/busan-company-cache-sync.service
/etc/systemd/system/busan-company-cache-sync.timer
schedule: daily 07:10 KST
```

역할:

```text
/opt/busan/chatbot_company.db
  -> archive/{timestamp}/chatbot_company.db
  -> manifest.json 작성
  -> DB 검증
  -> cache_current symlink 원자 교체
  -> cache_previous 보존
```

배포 후 smoke check:

```bash
systemctl is-active busan-company-cache-sync.timer
systemctl list-timers | grep busan-company-cache-sync
readlink -f /opt/advisor/cache/company/cache_current
cat /opt/advisor/cache/company/cache_current/manifest.json
```

## 12. UI 운영

### 12.1 별도 업체추천 화면

파일:

```text
app/pages/vendor_search.py
```

기능:

- 검색어 입력
- 예산 입력
- 후보 건수 선택
- 품목정책 요약 표시
- 업체별 카드 표시
- 검색결과 CSV 다운로드
- 전체 ZIP 다운로드

현재 기본 API:

```text
CHATBOT_API_URL.rsplit("/", 1)[0] + "/vendor-recommendations/search"
```

즉 `CHATBOT_API_URL=http://127.0.0.1:8001/chat`이면 업체추천 API base는 `http://127.0.0.1:8001`이다.

### 12.2 기존 챗봇 화면 내 검색 패널

파일:

```text
app/pages/💬_법령챗봇.py
```

기능:

- `/vendors/search` 기반 간단 업체검색
- `/vendors/query.csv`
- `/vendors/download.zip`

운영 방향:

- 법령/계약검토와 업체추천은 분리 운영하는 것이 맞다.
- 기존 챗봇 패널은 임시 접근 경로로 유지하고, 공개용은 별도 업체추천 화면을 우선한다.

## 13. QA 운영

### 13.1 고정 품질 QA

```bash
python -X utf8 scratch/run_vendor_recommendation_quality_qa.py --base-url http://49.50.133.160:8001
```

최신 결과:

```text
artifact:
artifacts/vendor_recommendation_quality_qa/vendor_recommendation_quality_qa_20260609_142642.md
artifacts/vendor_recommendation_quality_qa/vendor_recommendation_quality_qa_20260609_142642.jsonl

ok=100/100
avg_score=100.0
avg_latency_ms=925.7
```

### 13.2 확장 probe

```bash
python -X utf8 scratch/run_vendor_expansion_probe.py --base-url http://49.50.133.160:8001
```

최신 결과:

```text
artifact:
artifacts/vendor_recommendation_quality_qa/vendor_expansion_probe_20260609_142636.jsonl

ok=52/52
```

확장 probe 커버:

- 품목 alias
- 면허성 검색어
- 정책조건 검색어
- 오탐 방지 케이스
  - 홍보마케팅 vs 행사
  - 음향조명임대 vs LED/구내방송
  - 손소독제 vs 소독업/방역

### 13.3 로컬 단위 테스트

```bash
$env:PYTHONPATH='.'
pytest -q tests/test_item_normalization_policy.py tests/test_vendor_api_endpoints.py
```

최신 결과:

```text
33 passed in 0.39s
```

주의:

- 이 repo는 `PYTHONPATH=.` 없이 pytest를 돌리면 `ModuleNotFoundError: No module named 'app'`가 날 수 있다.
- broad `pytest -q`는 기존 하네스 문제로 실패할 수 있으므로 업체추천 관련 targeted test를 우선한다.

## 14. 운영 장애 대응

### 14.1 API 응답 없음

확인:

```bash
systemctl is-active busan-advisor-pilot.service
journalctl -u busan-advisor-pilot.service -n 100 --no-pager
curl -s http://127.0.0.1:8001/health
```

조치:

```bash
systemctl restart busan-advisor-pilot.service
```

### 14.2 업체 후보가 0건으로 나올 때

확인 순서:

```bash
echo $CHATBOT_COMPANY_DB_PATH
ls -l /opt/advisor/cache/company/cache_current/chatbot_company.db
sqlite3 /opt/advisor/cache/company/cache_current/chatbot_company.db "SELECT COUNT(*) FROM chatbot_company_candidate_view;"
sqlite3 /opt/advisor/cache/company/cache_current/chatbot_company.db "SELECT COUNT(*) FROM product_policy_summary;"
```

API 내부 확인:

```http
GET /vendor-recommendations/search?q=LED&region=busan&limit=5&include_product_policy=true
```

응답에서 확인할 것:

```text
count
search_plan
item_policy_summary.status
product_policy_checks[0].matched_policy_source
```

### 14.3 품목정책이 비는 경우

원인 후보:

- `product_policy_summary` view/table 없음
- 세부품명번호 기준 데이터 미적재
- `CHATBOT_COMPANY_DB_PATH`가 구버전 DB를 가리킴
- fallback인 `MONITORING_COMPANY_API_BASE_URL` 장애

확인:

```sql
SELECT COUNT(*) FROM product_policy_summary;
SELECT * FROM product_policy_summary WHERE detail_product_code = '3011150501';
```

레미콘 샘플인 `3011150501`은 품목정책 확인용으로 계속 쓸 수 있다.

### 14.4 정책기업 조건이 비는 경우

현재 구조:

- 일반 후보 row의 `policy_subtypes_raw`
- 보조 JSON `app/policy_companies.json`

제약:

- 여성기업/장애인기업/사회적기업 중심
- 벤처기업/사회적협동조합/자활기업/마을기업 데이터는 부족

조치:

- 모니터링 쪽 정책기업 원천 확장
- `policy_companies.json` 또는 DB table로 배포
- QA에서 `policy_preference_summary` 확인

### 14.5 전체 다운로드가 빈 파일일 때

2026-06-09에 수정 완료된 이슈다.

재발 확인:

```bash
python -X utf8 -c "import urllib.request, zipfile, io, csv; data=urllib.request.urlopen('http://49.50.133.160:8001/vendors/download.zip?active_only=true&limit=20').read(); z=zipfile.ZipFile(io.BytesIO(data)); rows=list(csv.reader(io.TextIOWrapper(z.open('busan_vendor_candidates.csv'), encoding='utf-8-sig'))); print(len(rows))"
```

정상:

```text
21
```

헤더만 있으면:

- `/opt/advisor/app/api_server.py`의 `_vendor_download_rows` active filter 확인
- `business_status` 값 분포 확인

## 15. Rollback

챗봇 API 코드 rollback:

```bash
cp /opt/advisor/backups/{backup_name}/app/api_server.py /opt/advisor/app/api_server.py
python3 -m py_compile /opt/advisor/app/api_server.py
systemctl restart busan-advisor-pilot.service
systemctl is-active busan-advisor-pilot.service
```

품목 사전 rollback:

```bash
cp /opt/advisor/backups/{backup_name}/app/policies/item_normalization_policy.py /opt/advisor/app/policies/item_normalization_policy.py
python3 -m py_compile /opt/advisor/app/policies/item_normalization_policy.py
systemctl restart busan-advisor-pilot.service
```

관련 백업:

```text
/opt/advisor/backups/codex_vendor_dict_priority_20260609_110240
/opt/advisor/backups/codex_vendor_policy_rules_20260609_110733
/opt/advisor/backups/codex_vendor_download_filter_20260609_142542
```

DB cache rollback:

```bash
readlink -f /opt/advisor/cache/company/cache_previous
ln -sfn /opt/advisor/cache/company/cache_previous /opt/advisor/cache/company/cache_current.new
mv -T /opt/advisor/cache/company/cache_current.new /opt/advisor/cache/company/cache_current
```

주의:

- DB symlink rollback 후 API 재시작이 항상 필요한 것은 아니지만, SQLite connection/cache 의심 시 `busan-advisor-pilot.service` 재시작으로 확인한다.
- rollback 후 반드시 `/vendor-recommendations/search` smoke QA를 실행한다.

## 16. 공개 전 체크리스트

최소 기준:

```text
[ ] /health OK
[ ] /vendor-recommendations/search?q=LED count > 0
[ ] /vendor-recommendations/search?q=장애인기업 청소용역 policy_preference_summary 확인
[ ] /vendor-recommendations/search?q=손소독제 구매 업체 top rows가 방역업체로만 치우치지 않음
[ ] /vendor-recommendations/search?q=홍보 마케팅 용역 업체가 행사대행으로만 과매칭되지 않음
[ ] /vendor-recommendations/search?q=음향 조명 장비 임대 업체가 LED 조명으로 오탐되지 않음
[ ] /vendors/download.zip?active_only=true 실제 row 포함
[ ] 확장 probe 52/52
[ ] 기존 100 QA 100/100
[ ] cache_current manifest validation_status=PASS
```

기관 테스트용 안내 문구:

```text
이 서비스는 계약 가능 업체를 확정하는 기능이 아니라, 부산 지역 업체 후보와 검토해야 할 근거 항목을 빠르게 찾는 기능입니다.
공고 전에는 면허, 직접생산증명서, MAS/종합쇼핑몰 계약상태, 정책기업 지위, 인증 유효성을 원천 자료로 재확인해야 합니다.
```

## 17. 모니터링 에이전트에게 추가로 넘길 작업 항목

업체추천 운영 관점에서 모니터링 에이전트가 가져가야 할 항목:

```text
1. 조달청 물품목록정보서비스 배치 적재
2. procurement_item_catalog 생성
3. procurement_item_alias 생성
4. item_license_map 생성
5. 정책기업 원천 확장
6. chatbot_company_candidate_view_v2 또는 호환 alias view 제공
7. product_policy_summary 최신성 보장
8. direct_production_certificate 최신성 보장
9. cache sync 검증 항목에 alias/rule table count 추가
10. 배포 후 업체추천 smoke QA 자동 실행
```

모니터링 파이프라인 검증 SQL에 추가:

```sql
SELECT COUNT(*) FROM procurement_item_catalog;
SELECT COUNT(*) FROM procurement_item_alias;
SELECT COUNT(*) FROM item_license_map;
SELECT COUNT(*) FROM policy_company_registry;
```

아직 없는 table 이름은 제안명이다. 실제 구현 시 모니터링 DB naming convention에 맞춰 조정한다.

## 18. 현 상태의 기술적 한계

- 검색어 이해는 아직 DB 기반이 아니라 코드 fallback 중심이다.
- 조달청 물품목록 API는 품목 표준화용이고 면허/업종 판단용이 아니다.
- 벤처기업, 사회적협동조합, 자활기업, 마을기업은 query recognition은 되지만 후보 데이터가 부족하다.
- `review_score`는 내부 정렬 점수이며 계약 가능성 점수가 아니다.
- `business_status=unknown` 후보가 많다. 공고 전 영업상태 확인이 필수다.
- 법령해석/계약방법 판단은 업체추천 API 범위 밖이다. 별도 계약검토 서비스에서 처리해야 한다.
- 공개 전 동시접속 부하 테스트는 아직 충분하지 않다. 현재 QA는 기능 품질/응답시간 중심이다.

## 2026-06-10 기준 전체 운영 구조와 역할 경계

이 섹션은 후임자와 다른 Codex 작업트리가 먼저 읽어야 하는 전체 구조 요약이다. 모니터링 시스템, 업체추천 백엔드, 법령해석 탭은 같은 정책 목표를 공유하지만 책임 범위가 다르다.

### 1. 시스템의 정책 목적

부산 공공계약 모니터링 및 지능형 수주지원 체계는 단순 대시보드가 아니라 지역제품 구매 확대를 위한 실행 도구다. 핵심 목적은 다음 4가지다.

1. 부산시, 자치구군, 공사공단, 출자출연기관 및 부산 소재 국가/공공기관의 계약 흐름을 모니터링한다.
2. 부산업체 수주율, 유출계약, 보호제도 미적용 가능 건, 현장소재지 판단 등 정책 지표를 계산한다.
3. 발주 담당자가 물품, 용역, 공사 면허, 예산, 구매 목적을 입력했을 때 부산 지역업체 후보와 근거 데이터를 빠르게 확인하게 한다.
4. 별도 법령해석 탭에서 계약금액, 계약유형, 보호제도, 수의계약 또는 지역제한 가능성 등을 RAG/LLM 기반으로 검토하게 한다.

이 시스템은 계약 가능 여부를 자동 확정하는 시스템이 아니다. 추천 결과는 후보 탐색 및 사전검토 자료이며, 최종 계약 방식, 법적 한계, 업체 자격, 인증 유효성은 발주 담당자가 원천자료로 재확인해야 한다.

### 2. 모듈별 책임 분리

| 영역 | 주 담당 기능 | 주요 데이터 | 산출물 | 하지 않는 것 |
|---|---|---|---|---|
| 모니터링 시스템 | 계약 데이터 수집, 부산현장/부산업체 판정, 수주율/보호제도/유출계약 계산, 캐시 생성, 경보 문자 | 조달청 계약/공고/API, 부산 수요기관 DB, 부산 조달업체 마스터 DB, 현장소재지 보정 DB | Streamlit 대시보드, API 캐시, 월별 캐시, 경보 문자, 챗봇용 업체 DB | 개별 계약의 법적 가능 여부 확정 |
| 업체추천 백엔드 | 물품/면허/업종/정책기업/인증/MAS/직접생산/중기간경쟁 등 근거 기반 후보 검색 | `chatbot_company.db`, `chatbot_company_candidate_view`, `product_policy_summary`, 직접생산/MAS/정책기업/면허 테이블 | 후보 업체 목록, 매칭 근거, 정책·인증 요약, 검색 API | 수의계약 가능 여부를 최종 판단하거나 법령 해석을 생성 |
| 법령해석 탭 | 계약금액과 계약유형에 따른 보호제도, 수의계약, 지역제한, 공동계약, 우선구매 검토 | 법령, 예규, 지침, 내부 정책자료, 업체추천 결과 컨텍스트 | 법령 근거와 확인 필요사항이 포함된 설명 | DB에 없는 업체를 임의 생성하거나 후보를 꾸며냄 |
| 운영/인수인계 문서 | 구조, 데이터 흐름, 크론, 장애 원인, 복구 절차, 한계 기록 | 실제 서버 확인 결과와 코드 검증 결과 | 후임자용 단일 운영 문서와 작업트리 간 handoff 문서 | 검증되지 않은 추정 사항을 사실처럼 기재 |

### 3. 운영 서버와 데이터 흐름

운영 서버는 1대이며 서비스와 폴더가 분리되어 있다.

```text
조달청/공공데이터 API, 수동 임포트 원천자료
        ↓
/opt/busan  (모니터링 운영 루트)
        ↓
procurement_contracts.db
busan_companies_master.db
busan_agencies_master.db
chatbot_company.db
api_cache.json / monthly_cache.json
        ↓
검증된 챗봇용 DB 배포본 생성 및 cache_current 원자 교체
        ↓
/opt/advisor/cache/company/cache_current/chatbot_company.db
        ↓
업체추천 API / Streamlit UI / 법령해석 탭 컨텍스트
```

운영 원칙은 다음과 같다.

1. `/opt/busan/chatbot_company.db`는 모니터링 쪽에서 생성하는 원천 DB다.
2. 챗봇은 `/opt/busan`을 직접 읽기보다 검증된 read-only 배포본을 `/opt/advisor/cache/company/cache_current/chatbot_company.db`로 받아서 사용한다.
3. 배포본 교체는 검증 후 archive 생성, `cache_current` symlink 또는 디렉토리 원자 교체 방식으로 한다.
4. 업체추천 API는 DB 직접 조회를 기본으로 하고, 모니터링 API 호출은 fallback 또는 보조 확인 수단으로만 둔다.
5. DB 스냅샷 기준 시점을 맞추는 것이 중요하다. 업체 후보와 품목정책 요약이 서로 다른 시점이면 추천 근거가 흔들릴 수 있다.

### 4. 부산업체 DB 구축 및 갱신 구조

부산 조달업체 DB는 최초 구축 DB에 일일/주기 보강을 얹는 구조다.

- 조달업체 기본정보: 조달청 업체 API 변경분을 기준으로 부산 본사 업체를 `company_master`에 upsert한다.
- 면허/업종: 조달청 업체 업종/면허 API 변경분을 기준으로 `company_industry` 또는 관련 면허 테이블을 보강한다.
- 사업자 유효성: 국세청 휴폐업 API로 정상/휴업/폐업 상태를 주기 검증한다. API 오류 시 재검증 queue 또는 후속 재처리 대상에 남겨야 한다.
- 정책기업: 여성기업, 장애인기업, 사회적기업 등은 수동 임포트 원천 DB와 API 검증을 병행한다. 사회적기업은 사업자등록번호 기반 자동 검증이 제한적이므로 수동 임포트 신뢰도가 더 중요하다.
- 직접생산증명: 계약 실무상 중요도가 높으므로 API 전체/증분 수집, 실패 페이지 재시도, 실패 queue 재처리 구조를 둔다.
- 기술개발제품 13종: 혁신제품과 일부 중복될 수 있으므로 추천 근거에서는 13종 인증 데이터를 우선 활용한다.
- MAS/종합쇼핑몰/벤처나라/중기간경쟁제품: 발주 담당자가 구매 편의성과 제도 적용 가능성을 빠르게 확인할 수 있도록 업체추천 DB에 요약 테이블 또는 view로 결합한다.

### 5. 수주율 및 현장소재지 판단의 책임

수주율 계산은 모니터링 시스템의 책임이다. 기본 원칙은 다음과 같다.

- 보호제도 분석은 추정가격 또는 공고 기준 금액을 사용한다.
- 수주율 계산은 실계약금액을 사용한다.
- 공동계약은 운영 코드에서 적용 중인 지분율 반영 방식이 기준이다. 변경 시 과거 수치와 비교 가능성이 깨지므로 기준 변경 이력을 문서화해야 한다.
- 장기계속계약은 운영 코드가 실제 포함하는 연도/금액 기준을 그대로 문서화해야 한다. 정책 판단으로 바꾸려면 별도 검증이 필요하다.
- 미분류 건은 수주율 모수에서 제외하는 것이 현재 사용자 판단이다.

현장소재지 판단은 완전 자동 확정이 어렵다. 특히 국가기관 및 정부공공기관은 본사가 부산이어도 지사가 전국에 있으므로, 지사 실적을 부산 실적으로 넣으면 정책 신뢰도가 떨어진다. 따라서 부산시 소속기관과 부산시 통제 가능 기관은 부산현장으로 보는 정책 기준을 적용하되, 국가기관/정부공공기관은 공고문, 조달요청, 납품장소, 계약명, 보정 데이터, 수동 로데이터 임포트를 결합해 보수적으로 판단한다.

### 6. 업체추천 서비스의 현재 설계 기준

업체추천 서비스의 핵심은 “발주 담당자가 지금 구매하려는 대상에 대해 부산 지역업체 후보와 검증 근거를 빠르게 확인하는 것”이다.

우선순위는 다음과 같다.

1. 질문 의도에 맞는 품목, 세부품명, 면허, 업종을 정확히 매칭한다.
2. 후보가 여러 곳이면 계약 편의성이 높은 근거를 함께 보여준다. 예: 정책기업, 직접생산증명, MAS/종합쇼핑몰 등록, 조합추천 관련 데이터, 중증장애인 생산품 등.
3. 유효 사업자 여부, 부산 본사 여부, 조달등록 여부, 인증 유효기간을 확인 가능한 형태로 노출한다.
4. 사용자가 법적 가능성을 오해하지 않도록 “추천 후보”와 “계약 가능 판단”을 분리해 표출한다.

현재 기준점으로 관리해야 하는 업체추천 백엔드 상태는 다음과 같다.

```text
로컬/서버 기준 브랜치: codex/vendor-api-v2-handoff-20260524
기준 커밋: c4f6d89 Stabilize vendor recommendation backend
운영 API 서비스: busan-advisor-pilot.service
운영 API 포트: 8001
주요 검증: 2,000개 고유 QA, 2,000/2,000 양호, 평균 99.84/100, 평균 응답 994.5ms
```

위 수치는 2026-06-09 QA 기준이며, DB 스냅샷이 바뀌면 재평가가 필요하다.

### 7. 후임자와 다른 작업트리용 확인 순서

후임자는 다음 순서로 확인하면 된다.

1. 이 문서의 “전체 운영 구조와 역할 경계” 섹션을 먼저 읽는다.
2. 모니터링 서버 구조, 크론, 캐시, 경보, 백업 절차를 확인한다.
3. 업체추천 작업은 `MONITORING_AGENT_VENDOR_DICTIONARY_HANDOFF_20260609.md`와 `VENDOR_RECOMMENDATION_API_SPEC_20260609.md`를 같이 본다.
4. 운영 DB는 `/opt/busan`이 원천이고, 챗봇 조회 DB는 `/opt/advisor/cache/company/cache_current`의 검증 배포본이라는 점을 혼동하지 않는다.
5. 법령해석 탭은 업체추천 API가 아니라 별도 RAG/LLM 서비스 책임이다. 단, 업체추천 결과를 법령해석 탭에 컨텍스트로 넘기는 연동은 가능하다.
6. GitHub 기준점과 운영 서버 HEAD가 다르면 먼저 dirty 상태와 운영 변경분을 보존한 뒤 작업한다.

### 8. 현재 남은 한계와 운영 주의사항

- 업체추천 QA는 자동 평가다. 실제 계약 적합성을 보증하지 않는다.
- 인증/정책기업/직접생산/MAS/벤처나라/중기간경쟁제품은 원천 API 또는 수동 임포트의 최신성에 의존한다.
- 사회적기업은 사업자등록번호 기반 자동 검증이 제한적이므로 수동 임포트와 사후 검증이 중요하다.
- 국가기관 및 정부공공기관 계약은 현장소재지 오판 가능성이 가장 크다. 수동 보정 데이터와 조달데이터허브 원천자료 임포트가 필요할 수 있다.
- 서버의 `/opt/busan`과 `/opt/advisor`는 역할이 다르며 Git 저장소도 다르다. 한쪽 변경이 다른 쪽 작업트리에 자동 반영된다고 보면 안 된다.
- 운영 hotfix 후에는 문서, Git 기준점, 서버 배포 상태를 같이 맞춰야 한다.
