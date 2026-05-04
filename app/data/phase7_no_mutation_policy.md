# Phase 7 No-Mutation Policy

> **적용 범위**: Phase 7 Final Baseline Freeze ~ Phase 8 Internal Legal MCP Gateway 설계·구현 완료 시점까지  
> **작성일**: 2026-05-04

본 문서는 Phase 7에서 고정된 기준 DB, 정책 문서, 파이프라인 설정을 Phase 8 Gateway 설계·구현이 완료될 때까지 **임의 변경하지 못하도록** 원칙을 명문화합니다.

---

## 1. 절대 금지 (DB·인프라)

| # | 금지 행위 | 이유 |
|:-:|----------|------|
| M1 | **운영 DB 변경** | Production 데이터 무결성 보장 |
| M2 | **기준 DB (`legal_db_v0_1_3.sqlite`) 스키마 변경** | Baseline 고정 원칙. 테이블 추가/삭제/열 변경 금지 |
| M3 | **기준 DB 레코드 INSERT / UPDATE / DELETE** | Baseline 데이터 무결성 보장 |
| M4 | **`active_for_rule` 값 임의 변경** | 판단 근거 source 변경은 Review Queue를 거쳐야 함 |
| M5 | **`active_for_procedure` 값 임의 변경** | 절차 안내 source 변경은 Review Queue를 거쳐야 함 |
| M6 | **scheduler 등록** (cron, systemd timer, Windows Task Scheduler 등) | 자동 실행으로 인한 의도치 않은 데이터 변경 방지 |
| M7 | **Production 배포** | Staging 미검증 상태에서 배포 금지 |

---

## 2. 절대 금지 (외부 연동)

| # | 금지 행위 | 이유 |
|:-:|----------|------|
| E1 | **실제 법제처 law API 호출** | 원문 자동 수집으로 인한 데이터 변경 방지 |
| E2 | **실제 법제처 admrul API 호출** | 행정규칙 자동 수집으로 인한 데이터 변경 방지 |
| E3 | **실제 원문 refresh** (PDF 재다운로드 포함) | Baseline 데이터 고정 원칙 |
| E4 | **실제 외부 API 호출** (NTS, 조달청 OpenAPI 등) | 외부 연동으로 인한 상태 변경 방지 |
| E5 | **NCP 서버 원격 명령 실행** (deploy, service restart 등) | 운영 환경 변경 금지 |

---

## 3. 절대 금지 (정책 구조)

| # | 금지 행위 | 이유 |
|:-:|----------|------|
| S1 | **`procedure_only`를 판단근거(`active_for_rule=true`)로 승격** | 절차 전용 분리 원칙(v0.1.3a) 위반 |
| S2 | **Item Eligibility를 선행 게이트(❶ 이전)로 재배치** | Optional Layer(❽) 원칙 위반 |
| S3 | **T3 Silent를 Explicit으로 재승격** | 과활성화 방지 원칙 위반 |
| S4 | **T4 Enrichment를 초기 라우팅 트리거로 재배치** | Enrichment 분리 원칙 위반 |
| S5 | **Rule Engine 우선순위(❶~❽) 순서 변경** | Baseline 고정 원칙 |
| S6 | **Answer Builder trigger_grade별 노출 규칙 변경** | 정합성 보완 결과 고정 |

---

## 4. 허용되는 작업

| # | 허용 작업 | 조건 |
|:-:|----------|------|
| A1 | **문서 정리** | 오탈자 수정, 명확화, 중복 제거. 정책 의미 변경 금지 |
| A2 | **manifest 작성** | 기준선 inventory 정리. DB 변경 없음 |
| A3 | **read-only Gateway 설계** | API 스펙, 인터페이스 설계. 구현 시 DB read만 허용 |
| A4 | **dry-run 테스트 설계** | 테스트 케이스 작성, mock data 정의. 실제 실행 금지 |
| A5 | **mock response 정의** | Gateway 테스트용 mock response 구조 정의 |
| A6 | **코드 리뷰** | 기존 코드 분석, 개선점 문서화. 코드 변경 금지 |
| A7 | **아키텍처 문서 작성** | Phase 8 설계 문서, 시퀀스 다이어그램 등 |
| A8 | **대화맥락 기록** | 세션 종료 시 대화맥락 파일 작성 |
| A9 | **Phase 8 Gateway 신규 코드 작성** | 아래 허용 조건 **모두** 충족 시에만 허용 |

### A9 상세 조건

**허용 조건** (7개 모두 충족):
1. 기준 DB schema 변경 없음
2. 기준 DB INSERT / UPDATE / DELETE 없음
3. 외부 API 호출 없음
4. scheduler 등록 없음
5. Production 배포 없음
6. read-only local DB query 또는 mock response 기반
7. 별도 branch 또는 별도 module에서 구현

**금지**:
- baseline asset 직접 수정
- 운영 서비스 재시작
- 실제 외부 API 연동

---

## 5. 예외 처리 절차

Baseline을 변경해야 하는 긴급 사유가 발생한 경우:

1. **사유 문서화**: 변경 사유를 `phase7_baseline_change_request.md`로 작성
2. **영향 분석**: 변경으로 인한 12건 회귀 테스트 영향 범위 분석
3. **사용자 승인**: 변경 사유와 영향 분석을 사용자에게 제시하고 명시적 승인 획득
4. **변경 실행**: 승인 후에만 변경 실행
5. **검증**: 12건 회귀 테스트 재실행
6. **manifest 갱신**: `phase7_final_baseline_manifest.json` 갱신

---

## 6. 정책 해제 조건

본 No-Mutation Policy는 다음 조건이 **모두** 충족될 때 해제됩니다:

1. Phase 8 Internal Legal MCP Gateway 설계 완료
2. Gateway dry-run 테스트 PASS
3. 12건 회귀 테스트 PASS
4. 사용자의 명시적 해제 승인
