# Item Eligibility Update Policy

## 1. 기본 원칙
Item Eligibility 데이터는 Legal DB 업데이트와 **별도 트랙**으로 관리합니다.

## 2. 업데이트 주기

| 데이터 | 주기 | 방법 |
|---|---|---|
| 중소기업자간 경쟁제품 목록 | Weekly~Monthly | SMPP 엑셀/API 다운로드 후 diff |
| 직접생산확인 기준 | Weekly~Monthly | 기준 변경 감지 시 selective refresh |
| 업체별 직접생산확인 인증 | Daily (유효기간) / Query-time | valid_to 기준 만료 자동 계산 |
| item_alias_map | 수시 | 사용자 질의 로그 기반 월간 보강 |
| 전체 Item DB 정합성 | Monthly | audit script |

## 3. 외부 API 활용 원칙
1. 외부 API(SMPP 등)는 **update pipeline 전용**으로 사용합니다.
2. 사용자 질의마다 외부 API를 실시간 호출하지 않습니다.
3. 챗봇 답변은 **내부 Item Eligibility DB**를 기준으로 합니다.
4. 외부 API 장애 시 기존 내부 DB를 사용하고, 최신성 경고만 추가합니다.
5. 공식 원천 변경 시 staging DB에서 먼저 반영하고 검증합니다.

## 4. 배포 프로세스
Item Eligibility 데이터도 Legal DB와 동일하게 staging → validation → release 프로세스를 따릅니다.
