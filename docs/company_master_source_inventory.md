# Phase 9-B — 조달등록 부산업체 마스터 확보 및 Source 확정

## 1. 검색 경로 및 점검 대상
- **검색 경로**: 워크스페이스 루트 (`c:/Users/doors/OneDrive/바탕 화면/사무실 메뉴얼 제작_추출/메뉴얼 제작`) 및 하위 전체 디렉터리 (`app/`, `data/` 등 포함)
- **검색 포맷**: `.csv`, `.xlsx`, `.xls`, `.json`, `.sqlite`, `.db`, `.parquet`
- **검색 키워드**: busan, company, procurement, supplier, vendor, 조달, 업체, 등록, g2b, local

## 2. 발견된 후보 파일 목록
전체 부산 업체를 커버하는 마스터 파일(예: `busan_companies_raw.csv`)은 발견되지 않았으며, 아래와 같은 특정 카테고리의 부분집합 엑셀 파일들만 발견되었습니다.

1. `여성기업 조달업체 등록 내역(20260422).xlsx` (228KB)
2. `사회적기업 조달업체 등록 내역.xlsx` (19KB)
3. `장애인기업 조달업체 등록 내역.xlsx` (29KB)
4. `국가공공기관_지역업체_계약률_순위.xlsx` (6KB, 통계용 파일)

## 3. 후보별 상세 점검 결과 및 사용 가능성

위 3개 엑셀 파일에 대한 공통 점검 결과입니다.
- **file_path**: 워크스페이스 루트
- **file_format**: XLSX
- **header row**: 프롬프트 검색 조건 메타데이터가 상단에 포함된 비표준 헤더 양식
- **row_count**: 각 파일별로 수백~수천 건 내외 추정 (전체 부산 업체 2만 건에 한참 미달)
- **business_no_column_exists**: Y (내용 상 존재할 것으로 추정)
- **company_name_column_exists**: Y
- **address_column_exists**: Y
- **busan_filter_applied**: Y (검색 조건에 부산 식별자 포함)
- **usable_as_master**: **불가** (여성/사회적/장애인 기업이라는 극히 일부 집합만 포함하고 있어 전체 마스터로 쓸 수 없음)

## 4. 운영 API / DB Export 가능성 확인
`app/company_api.py` 내부 스펙 및 워크스페이스 설정 파일 점검 결과:
- **전체 Export Endpoint**: 존재하지 않음. 
- **API 특성**: `busanproduct.co.kr` 등의 특정 키워드(품목, 면허) 기반 단건 검색이나 페이지네이션 응답에 최적화되어 있음.
- **Batch 제약**: 수만 건을 순회 조회(Scraping)할 경우 Rate Limit 한계나 Timeout 장애가 발생할 구조이므로 Batch Export 용도로 부적합.
- **DB Credential**: 소스코드나 설정 파일 내부에 원천 DB로 직결할 수 있는 접속 정보(Host, ID, Password)가 전혀 존재하지 않음.

## 5. 민감정보 존재 여부
- 해당 부분집합 엑셀 파일들 내부에 **원본 사업자번호, 대표자명, 연락처** 등의 민감정보가 포함되어 있을 가능성이 매우 큼. 
- 향후 ETL 구현 시 반드시 HMAC-SHA256 변환(`internal_join_key`) 및 민감 컬럼 Drop 조치를 선행해야 함.

## 6. Source 후보 최종 판정
- **판정 결과**: **BLOCKED**
- **사유**: 현재 워크스페이스 내 파일 시스템 및 연결 가능한 API/DB 환경 어디에도 전체 부산 조달등록 업체를 포괄하는 **Master Source가 존재하지 않습니다**.

## 7. 최종 권장 Source 및 확보 방안
현재 챗봇 생태계에 의존하는 방식으로는 해결이 불가능하므로, 아래와 같은 외부 공공데이터 원천 재수집을 권장합니다.
- **권장 소스**: [공공데이터포털] 조달청 나라장터 업체 등록 정보 (Open API 또는 주기적 CSV 덤프)
- **처리 방안**: 부산 지역(소재지 코드) 필터링 적용 후 `busan_companies_raw.csv` 형태로 다운로드 받아 워크스페이스 `data/` 디렉터리에 수동 반입.

## 8. 구현 전 필요 조치
1. **데이터 반입**: 조달청 제공 전국 업체 데이터에서 부산 업체만 추출한 최신 마스터 CSV 확보 및 업로드.
2. **비밀키 세팅**: 원본 사업자번호 암호화(HMAC)를 위한 `.env` 기반 Secret Key 환경변수 주입 체계 구축 (코드 내 하드코딩 엄금).

## 9. System Constraints
> [!WARNING]
> 본 문서는 조달등록 마스터 확보 및 Source 확정을 위한 설계 진단 결과이며, **Production Deployment는 계속 HOLD 상태**를 유지합니다. 
> 현 시점에서는 어떠한 ETL 구현, DB 테이블 생성, 외부망 수집 스크립트 실행, 서버 배포, 그리고 민감정보의 텍스트 노출도 진행되지 않았습니다.
