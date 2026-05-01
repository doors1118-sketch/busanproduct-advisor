# Phase 9-A — 업체 캐시 입력 원천 확정 및 스키마 검증

## 1. 조달등록 부산업체 마스터 확인 결과

- **실제 파일 경로 또는 DB 위치**: 워크스페이스 내 조회 결과 **파일 없음** (`busan_companies_raw.csv` 또는 관련 마스터 DB가 존재하지 않음)
- **파일 형식**: N/A
- **인코딩**: N/A
- **header row 위치**: N/A
- **실제 컬럼명**: N/A
- **총 row_count**: N/A
- **부산업체 필터 적용 여부**: N/A
- **사업자번호 컬럼 존재 여부**: N/A
- **업체명 컬럼 존재 여부**: N/A
- **주소/소재지 컬럼 존재 여부**: N/A
- **대표업종/면허/품목 컬럼 존재 여부**: N/A
- **공사·용역 업종 정보 포함 여부**: N/A
- **민감정보 포함 여부**: N/A

## 2. `policy_companies.json` 확인 결과

- **실제 파일 존재 여부**: Y (`app/policy_companies.json`)
- **JSON 구조**: dict
- **실제 key 목록 (Value 내부 dict)**: `name`, `location`, `biz_type`, `industry`, `product`, `manufacturer`, `registered`, `tags`
- **업체명 key**: `name`
- **정책기업 tag key**: `tags`
- **사업자번호 또는 join key 존재 여부**: Y (최상위 dict key 자체가 10자리 평문 사업자번호로 구성됨)
- **인증유효기간 필드 존재 여부**: N
- **발급기관 필드 존재 여부**: N
- **민감정보 포함 여부 스캔 결과**:
  - 평문 사업자번호 패턴: **Y** (최상위 Key)
  - 대표자명: N
  - 전화번호: N
  - 이메일: N
  - 인증번호: N

## 3. `tech_products.json` 확인 결과

- **실제 파일 존재 여부**: Y (`app/tech_products.json`)
- **JSON 구조**: dict 내의 `products` 리스트 구조 (길이 104)
- **실제 key 목록 (products 내부 dict)**: `biz_no`, `company`, `representative`, `cert_type`, `cert_no`, `product_name`, `cert_date`, `expire_date`
- **제품명 key**: `product_name`
- **업체명 key**: `company`
- **인증유형 key**: `cert_type`
- **인증번호 key**: `cert_no`
- **인증일 key**: `cert_date`
- **유효기간 key**: `expire_date`
- **조달등록 상태 key**: N (명시적 상태 필드 부재)
- **민감정보 포함 여부 스캔 결과**: **Y** (`biz_no` 평문 존재, `representative` 개인정보 존재)

## 4. 스키마 매핑표 (Target Schema Mapping)

| target field | source file | source column/key | required | transform | note |
|---|---|---|---:|---|---|
| internal_join_key | busan_companies_raw | 사업자번호 컬럼 (현재 없음) | Y | HMAC-SHA256 | 값 출력 절대 금지 |
| company_name | busan_companies_raw | 업체명 컬럼 (현재 없음) | Y | trim/normalize | |
| location | busan_companies_raw | 주소 컬럼 (현재 없음) | Y | 시도/시군구 파싱 | |
| address_region | busan_companies_raw | 주소 컬럼 (현재 없음) | Y | 부산 구군 추출 | |
| main_products_json | busan_companies_raw | 취급품목 컬럼 (현재 없음) | N | JSON array string | |
| category_codes_json | busan_companies_raw | 코드 컬럼 (현재 없음) | N | JSON array string | |
| license_or_business_type | busan_companies_raw | 면허/업종 컬럼 (현재 없음) | N | normalize | |
| procurement_registered | busan_companies_raw | 상태 컬럼 (현재 없음) | Y | boolean | |
| business_status | busan_companies_raw | 상태 컬럼 (현재 없음) | N | status normalize | |
| source_refreshed_at | busan_companies_raw | 시스템 시각 / 파일 갱신 시각 | Y | ISO datetime | |

## 5. 구현 가능성 판정

- **조달등록 부산업체 마스터**: **BLOCKED** (필수 파일 부재로 구현 불가)
- **`policy_companies.json`**: **DEGRADED_READY** (인증유효기간/발급기관은 없으나 조인용으로 MVP 구현 가능)
- **`tech_products.json`**: **READY** (필요 필드 대부분 존재하여 ETL 구현 가능)

**최종 판정**: **BLOCKED** (캐시 마스터 역할을 할 최상위 원천 파일이 워크스페이스에 없으므로 전체 파이프라인 진입 불가)

## 6. 구현 전 보완 필요사항

1. **마스터 파일 확보**: `busan_companies_raw.csv` 또는 이에 준하는 조달등록업체 마스터 파일의 제공이 선행되어야 합니다.
2. **보안 조치**: `policy_companies.json`과 `tech_products.json` 내의 평문 사업자번호(`biz_no`) 및 대표자명(`representative`)은 추출 후 HMAC-SHA256 처리하고 메모리상에서 즉각 폐기하는 로직을 반드시 파이프라인 첫 단계에 적용해야 합니다.
3. **결측치 대응**: 정책기업 JSON 내 인증유효기간이 존재하지 않으므로, 유효기간 점검 로직은 해당 출처에 대해 예외 처리(`Unknown`)를 부여하는 방향으로 조율이 필요합니다.

## 7. System Constraints

> [!WARNING]
> 본 문서는 업체 캐시 데이터 원천 확정 및 스키마 검증 결과를 담고 있으며, **Production Deployment는 계속 HOLD 상태**를 유지합니다. 
> 현 시점에서는 어떠한 ETL 스크립트 구현, DB 생성, 서버로의 배포 및 민감정보 출력도 실행되지 않았습니다.
