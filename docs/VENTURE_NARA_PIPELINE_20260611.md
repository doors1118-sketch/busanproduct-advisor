# 벤처나라 데이터 적재 및 업데이트 파이프라인

작성일: 2026-06-11

## 목적

지역업체 추천에서 다음 판단 근거를 보강한다.

- 부산업체가 벤처나라 등록 상품을 보유하는지
- 벤처나라 상품명, 카테고리, 규격, 단가, 유효기간, 인증목록
- 벤처나라 지정업체 여부와 지정 제품명
- 후보 업체 표출 시 `venture_nara_product_summary` 근거 표시

## 공식 원천

1. 조달청_벤처나라 상품 등록 내역
   - OAS: https://infuser.odcloud.kr/oas/docs?namespace=15127733/v1
   - API path: `/15127733/v1/uddi:4d326451-9f87-4727-a6e8-b83afcffc021`
   - 명세상 주요 필드: 물품식별번호, 벤처나라물품명, 업체명, 업체사업자등록번호, 벤처나라카테고리명, 단가, 규격, 중기간경쟁제품, 벤처기업여부, 유효기간, 인증목록

2. 조달청_벤처나라_지정업체
   - OAS: https://infuser.odcloud.kr/oas/docs?namespace=15131213/v1
   - API path: `/15131213/v1/uddi:5d678896-c435-4ac9-b67f-a319fab61f33`
   - 명세상 주요 필드: 사업자번호, 제품명목록, 지역명, 지정년도, 지정차수, 확정여부, 확정일자, 입력일자

두 API 모두 `page`, `perPage`, `returnType`, `serviceKey` 기반 조회다. 명세상 증분 조회용 수정일자 조건은 확인되지 않았다. 따라서 현재 파이프라인은 전체 refresh 방식으로 설계한다.

## 적재 코드

- 로컬 소스: `scripts/import_venture_nara_api.py`
- 운영 배치 위치: `/opt/busan/import_venture_nara_api.py`
- 대상 DB: `/opt/busan/chatbot_company.db`
- 인증키 우선순위:
  - `VENTURE_NARA_SERVICE_KEY`
  - `ODCLOUD_VENTURE_NARA_SERVICE_KEY`
  - `ODCLOUD_API_KEY`
  - `SERVICE_KEY`

실행 예:

```bash
cd /opt/busan
. /opt/busan/.env
CHATBOT_DB=/opt/busan/chatbot_company.db /opt/busan/venv/bin/python3 import_venture_nara_api.py --per-page 1000 --max-pages 20
```

## DB 테이블

### `venture_nara_product`

벤처나라 상품 등록 내역 전체를 저장한다. 부산업체 여부는 사업자등록번호를 `company_identity.canonical_business_no`와 매칭해서 `company_internal_id`를 채운다.

주요 컬럼:

- `product_identifier`
- `venture_product_name`
- `bizno`
- `company_internal_id`
- `company_name`
- `category_name`
- `parent_category_name`
- `price_amount`
- `spec`
- `is_sme_competition_product`
- `venture_company_flag`
- `valid_from`
- `valid_to`
- `company_cert_list`
- `mandatory_purchase_cert_list`
- `preferential_purchase_cert_list`
- `venture_nara_cert_list`
- `source_name`
- `source_refreshed_at`

### `venture_nara_designated_company`

벤처나라 지정업체 목록을 저장한다. 이 테이블도 사업자등록번호로 부산업체 내부 ID와 연결한다.

주요 컬럼:

- `bizno`
- `company_internal_id`
- `designated_year`
- `designated_round`
- `designated_seq`
- `product_names`
- `region_name`
- `confirmed_yn`
- `confirmed_date`
- `input_date`
- `source_name`
- `source_refreshed_at`

## 운영 반영 결과

2026-06-11 기준 운영 DB 적재 결과:

- `venture_nara_product`: 11,411건
- `venture_nara_product` 중 부산업체 매칭: 639건
- 벤처나라 상품이 후보 view에 표출되는 부산업체: 130개사
- `venture_nara_designated_company`: 5,705건
- `venture_nara_designated_company` 중 부산업체 매칭: 435건

적재 전 운영 DB 백업:

```text
/opt/busan/db_backups/chatbot_company.before_venture_nara_20260611_085811.db
```

## 챗봇 조회 DB 반영

운영 원천 DB는 `/opt/busan/chatbot_company.db`다. 챗봇은 원천 DB를 직접 읽지 않고 검증된 배포본을 사용한다.

동기화 명령:

```bash
cd /opt/advisor
python3 scripts/sync_company_view_db.py --source /opt/busan/chatbot_company.db --cache-root /opt/advisor/cache/company --apply
```

2026-06-11 반영 후 검증 결과:

- `/opt/advisor/cache/company/cache_current/chatbot_company.db`에도 동일 건수 반영
- `venture_nara_product`: 11,411건
- 부산업체 매칭 상품: 639건
- 후보 view 표출 업체: 130개사
- `product_policy_summary`: 4,315건 유지
- `direct_production_certificate`: 11,291건 유지

## 자동 업데이트 방식

권장 크론:

```cron
25 6 * * * cd /opt/busan && . /opt/busan/.env && CHATBOT_DB=/opt/busan/chatbot_company.db /opt/busan/venv/bin/python3 import_venture_nara_api.py --per-page 1000 --max-pages 20 >> /opt/busan/sync_log/chatbot_venture_nara.log 2>&1
```

이 시간은 기존 운영 배치 흐름을 기준으로 잡았다.

- 06:05 종합쇼핑몰 카탈로그 적재 이후
- 06:45 여성/장애인 정책기업 API 이전
- 07:10 전후 챗봇 업체 DB cache sync 이전

크론 설치 스크립트:

```bash
sudo bash /opt/advisor/scripts/install_venture_nara_pipeline_cron.sh
```

단, 운영 서버에서는 `/opt/advisor/scripts/install_venture_nara_pipeline_cron.sh` 또는 같은 내용의 스크립트를 먼저 배포해야 한다. 로컬 원본은 `scripts/install_venture_nara_pipeline_cron.sh`다.

## 실패 처리

현재 실패 처리 방식:

- HTTP 429, 502, 503, 504 또는 네트워크 예외는 3회 지연 재시도
- 실패 시 `etl_job_log`에 `import_venture_nara_api` 실패 기록
- 성공 시 `etl_job_log`, `source_manifest` 갱신
- DB 반영은 source 단위 삭제 후 insert를 하나의 transaction으로 수행

운영 보강 과제:

- `alert_check.py`에서 `import_venture_nara_product_api`, `import_venture_nara_designated_company_api`의 당일 성공 여부를 경보 대상으로 추가
- `chatbot_venture_nara.log` logrotate 등록
- ODCloud 원천의 기준일이 `20240331`, `20240806`으로 표시되어 있으므로, API를 매일 실행해도 원천 데이터 자체가 매일 갱신된다는 뜻은 아니다. 실제 최신성은 data.go.kr/ODCloud의 데이터 갱신 주기에 종속된다.

## 추천 서비스에서의 의미

벤처나라 데이터는 단독으로 “계약 가능”을 확정하지 않는다. 하지만 다음 경우에는 추천 우선순위와 표출 근거로 의미가 있다.

- 사용자가 “벤처나라”, “창업/벤처 제품”, “혁신·인증 제품”, “구매 편의성”을 언급한 경우
- 종합쇼핑몰/MAS나 직접생산증명서 근거가 약하지만 벤처나라 등록 상품이 있는 경우
- 후보 업체 속성 카드에 벤처나라 상품명, 유효기간, 인증목록을 표시해 담당자가 추가 확인할 수 있게 하는 경우

제한:

- 벤처나라 등록 여부가 곧 해당 발주 건의 구매 가능 방식 확정은 아니다.
- 유효기간, 단가, 인증목록은 API 원천 값 기준이며, 최종 계약 전 나라장터/벤처나라 화면 재확인이 필요하다.
- 부산업체 매칭은 사업자등록번호 기준이다. API 사업자번호가 누락 또는 오류인 경우 자동 연결되지 않는다.
