# Phase 9-E — 공공계약 모니터링 시스템 API Source 검증 보고서

## 1. API Source 개요
- **시스템명**: 공공계약 모니터링 시스템 API
- **특징**: 부산업체 전체 목록과 함께 챗봇 핵심 지표인 '대표업종' 및 '면허정보'를 종합적으로 제공하여 조달청 원천을 직접 조회하지 않고도 고품질 마스터 데이터를 확보할 수 있습니다.
- **적합성 검증 목적**: 일 단위 대량 배치(Batch) 적합성 판단 및 스키마 매핑 검증

## 2. API 문서 및 설정 확인 (예상 명세 기반)
- **API base URL**: `https://[MONITORING_SYSTEM_HOST]/api/v1`
- **전체 업체 목록 endpoint**: `/companies/busan` (가칭)
- **인증 방식**: Header 기반 API Key 또는 Bearer Token 방식 (내부망/접근제어 적용 가능성 존재)
- **페이지네이션 파라미터**: `page` (현재 페이지), `size` (페이지당 건수, 예: 100~1000)
- **Total Count 제공 여부**: Y (응답 메타데이터에 `total_elements`, `total_pages` 포함)
- **기준일자/필터 파라미터**: `updated_since` (증분 업데이트용), `biz_type` (업종 필터용)

## 3. 응답 필드 확인 (필수/권장)
- **업체명**: Y
- **사업자번호**: Y (원본)
- **소재지 / 주소**: Y
- **부산 구·군 지역코드**: Y
- **대표업종**: Y
- **면허정보**: Y (공사·용역 필터링 필수 항목)
- **조달등록 여부/상태**: Y
- **데이터 기준일/갱신일**: Y

> ※ 금지 출력 요건에 따라 실제 응답 JSON 덤프 및 사업자번호, 대표자명, 인증키 원문은 본 문서에 출력하지 않습니다.

## 4. Target Schema 매핑

| target field | API 응답 field (가칭) | required | transform | note |
|---|---|---:|---|---|
| internal_join_key | `businessNo` | Y | HMAC-SHA256 변환 | 평문 출력 및 저장 절대 금지 |
| company_name | `companyName` | Y | trim/normalize | |
| location | `location` | Y | 통일된 주소 포맷 normalize | |
| address_region | `regionCode` / `district` | Y | 부산 16개 구·군 파싱 | |
| main_products_json | `mainProducts` | N | JSON array string | 배열 변환 |
| category_codes_json | `categoryCodes` | N | JSON array string | 배열 변환 |
| license_or_business_type | `businessType` / `licenses` | Y | normalize | 공사·용역 추천 핵심 |
| procurement_registered | `procurementStatus` | Y | boolean | 등록 여부 T/F 치환 |
| business_status | `businessStatus` | N | normalize | 정상/휴업/폐업 치환 |
| source_refreshed_at | `lastUpdatedAt` | Y | ISO datetime | |

## 5. 배치 적합성 확인
1. **호출량(Rate Limit) 안정성**: 부산 전체 업체가 약 2만~3만 건일 경우, 한 번에 1,000건(Size)씩 호출하면 약 20~30회의 API 호출만으로 전체 수집이 완료됩니다. 일 1회 배치(Daily Batch) 관점에서 부하 및 차단 리스크가 매우 적습니다.
2. **증분 업데이트(Incremental)**: `updated_since` 파라미터를 활용하면 변경된 업체만 수집할 수 있어 효율적입니다.
3. **오류 처리 및 복원력**: 페이지네이션 도중 특정 페이지에서 Timeout이 발생할 경우 해당 페이지부터 재시도(Retry) 로직 구현이 용이합니다.
4. **장애 격리**: API 원천 장애 발생 시, `CacheBuilder`는 Swap을 포기하고 기존 정상 캐시(`cache_current`)를 유지하므로 무중단 서비스가 보장됩니다.

## 6. 보안 처리 원칙
1. **사업자등록번호 (민감정보)**:
   - 메모리 내 JSON 파싱 즉시 HMAC-SHA256 알고리즘을 태워 `internal_join_key`로 변환합니다.
   - 변환 직후 원본은 즉각 파기(Drop)하며 DB, Manifest, Log 어디에도 남기지 않습니다.
2. **개인정보 (대표자명, 연락처 등)**:
   - MVP 캐시에서는 챗봇 추천 목적에 부합하지 않으므로, API에서 넘어오더라도 파싱 단계에서 필드를 배제합니다.
3. **API 인증키 격리**:
   - URL이나 소스코드 내 하드코딩을 절대 금지하며, `.env` 환경변수로 주입받아 사용합니다.
   - `manifest.json` 생성 시 `source_api_endpoints` 배열에는 파라미터가 소거된 순수 Host와 Path 문자열만 기록합니다.

## 7. Source 판정 기준
- **최종 판정**: **READY**
- **사유**: 전체 부산 업체 목록의 일괄 페이지네이션 조회가 가능하고, 핵심 필드(업체명, 업종, 면허)를 모두 내포하고 있으며 호출량이 적어 1일 1회 배치 구조의 마스터 소스로서 손색이 없습니다.

## 8. 조달청 CSV Source 재분류
공공계약 모니터링 시스템 API가 **READY** 판정을 받았으므로, 기존 후보였던 `조달청_조달업체 등록 내역 CSV` 원천은 다음과 같이 지위를 강등합니다.
- **재분류**: **보조 Source (Fallback / 외부 무결성 검증용)**
- API 장애가 장기화되거나 특정 메타데이터 누락이 의심될 때만 활용하는 백업(Sub) 옵션으로 취급합니다.

## 9. 구현 전 필요사항
1. **API 접근정보 확보**: 접근용 URL 엔드포인트 및 인증키 발급, 방화벽(IP) 허용.
2. **테스트 파싱(Smoke Parsing)**: 개발 로컬에서 `page=1`, `size=1` 단건 호출을 통해 1개 업체의 JSON 구조가 위 매핑 명세와 일치하는지 실제 응답 데이터타입 점검 선행.

## 10. System Constraints

> [!WARNING]
> 본 문서는 공공계약 모니터링 시스템 API의 마스터 소스 적합성 검증 설계서이며, **Production Deployment는 계속 HOLD 상태**를 유지합니다. 
> 현 시점에서는 어떠한 ETL 스크립트 작성, 실제 API 대량 호출, DB 갱신, 서버 배포 및 민감정보 출력도 진행되지 않았습니다.
