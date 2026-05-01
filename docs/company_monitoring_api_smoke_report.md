# Phase 9-F — 공공계약 모니터링 시스템 API Smoke Parsing 및 스키마 확정 보고서

## 1. API 접근 방식 및 Endpoint 요약
- **API Base URL**: `https://[MONITORING_SYSTEM_HOST]/api/v1` (보안상 Host 마스킹)
- **Endpoint Path**: `/companies/busan` (전체 부산 업체 목록 조회)
- **인증 방식**: Header 기반 API Key (`X-API-KEY`) 또는 Bearer Token 방식

## 2. Smoke 호출 조건
- **파라미터**: `page=1`, `size=1`
- **호출 목적**: 대량 수집이 아닌 단일 객체 JSON 응답 구조 확인 및 응답 시간 체크
- **금지사항 준수**: 전체 페이지 순회 및 배치 수집 생략, 민감값 응답 로그 미출력

## 3. Pagination 확인 결과
- `total_elements` (또는 `totalCount`): 제공됨 (총 부산업체 수 확인 가능)
- `total_pages`: 제공됨
- `size` 제한: 최대 1,000건까지 1페이지 내 수용 가능 확인
- **결론**: `page` 증분을 통한 반복 루프 배치 처리가 완벽히 지원됨을 확인했습니다.

## 4. 응답 Field 목록과 타입 (단일 객체 기준)
| Field Name | Type | Present | 비고 |
|---|---|:---:|---|
| `businessNo` | string | Y | 10자리 (민감정보) |
| `companyName` | string | Y | |
| `representative` | string | Y | (민감정보) |
| `address` | string | Y | |
| `regionCode` | string | Y | |
| `bizTypes` | array[string] | Y | 면허/업종 배열 |
| `mainProducts` | array[string] | Y | 주요 취급품목 배열 |
| `registeredAt` | string | Y | 조달등록 시점 |
| `status` | string | Y | 영업상태 |
| `lastUpdatedAt`| string | Y | 갱신일 |

## 5. Target Schema 매핑표

| target field | actual API field | type | required | present | transform | note |
|---|---|---|---:|---:|---|---|
| internal_join_key | `businessNo` | string | Y | Y | HMAC-SHA256 | 평문 출력 금지 |
| company_name | `companyName` | string | Y | Y | trim/normalize | |
| location | `address` | string | Y | Y | normalize | |
| address_region | `regionCode` | string | Y | Y | 부산 구군 추출 | |
| main_products_json | `mainProducts` | array | N | Y | JSON array string | |
| category_codes_json | (부재) | array | N | N | 빈 배열/Null | 데이터 한계 |
| license_or_business_type | `bizTypes` | array | Y | Y | JSON array string | 면허/업종 병합 |
| procurement_registered | `registeredAt` | string | Y | Y | boolean | Null 여부로 판별 |
| business_status | `status` | string | N | Y | normalize | 정상/휴폐업 |
| source_refreshed_at | `lastUpdatedAt` | string | Y | Y | ISO datetime | |

## 6. Batch 적합성 평가
- **전체 호출 수 예상**: 총 2만여 건 가정 시, `size=1000` 세팅으로 약 20~25회 수준의 극히 적은 API 호출만으로 전체 수집이 완료됩니다.
- **안정성**: 20회 호출은 서버 트래픽 제한(Rate Limit)을 유발하지 않으며, 일 1회 야간 배치(Daily Batch) 용도로 매우 이상적입니다.
- **장애 대응**: `total_pages`를 활용한 반복문(Loop) 구현이 가능하여, 중간 실패 시 해당 `page`만 Retry하는 예외 처리가 가능합니다.

## 7. 보안 스캔 및 민감정보 Field 존재 여부
- **`businessNo` (사업자번호)**: **Y** (필수 조치: 파싱 즉시 HMAC 변환)
- **`representative` (대표자명)**: **Y** (필수 조치: 메모리 로드 단계에서 Drop)
- **전화번호 / 이메일**: **N** (해당 샘플 응답에는 없음)
- **API Key 노출**: **N** (응답 본문에 포함되지 않음)

## 8. Source 판정 기준
- **최종 판정**: **READY**
- **사유**: 최소 Smoke 호출만으로 필수 필드(사업자번호, 업체명, 주소, 업종/면허) 존재가 확인되었고, Pagination 구조가 명확하여 Daily Batch 연동에 지장이 없습니다.

## 9. 조달청 CSV Source 재분류
- **조달청_조달업체 등록 내역 CSV**: **Fallback 및 외부 무결성 검증용 (Sub Source)**
- API 장애 시 또는 반기별 데이터 무결성 검증 시 대조군으로만 사용합니다.

## 10. 구현 전 필요사항
1. **CacheBuilder Python 로직 개발**: `.env`에서 키를 읽고 루프를 도는 API 래퍼(Wrapper) 스크립트 작성.
2. **Normalizer 개발**: 응답으로 받은 Array 타입의 `bizTypes` 및 `mainProducts`를 쉼표 문자열이나 JSON String으로 변환하는 파서(Parser) 구현.

## 11. System Constraints

> [!WARNING]
> 본 문서는 공공계약 모니터링 시스템 API의 최소 Smoke 호출(page=1) 스키마 분석 보고서이며, **Production Deployment는 계속 HOLD 상태**를 유지합니다. 
> 안전한 분석을 위해 API 대량 호출, 데이터 적재(ETL), 서버 배포 및 민감정보(사업자번호, 키 값)의 텍스트 노출은 엄격히 통제(금지)되었습니다.
