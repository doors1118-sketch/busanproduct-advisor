# Answer Builder Forbidden Phrases Test Cases

이 문서는 Answer Builder가 생성한 최종 결과물(`rendered_markdown`) 내부의 금지 표현 필터링 로직이 정상 작동하는지 확인하는 BDD 방식의 테스트 명세입니다.

## 테스트 대상 및 범위
- **검사 대상**: `AnswerBuilderOutput.rendered_markdown` (문자열 전체)
- **포함 영역**: 후보표, 주의사항, Disclaimer 등 예외 없이 렌더링된 전체 텍스트 스캔
- **차단 기준**: 아래 목록 중 하나라도 부분 일치(Substring Match)할 경우 실패(`forbidden_phrase_scan_passed = False`) 처리

## 금지 표현 리스트 (Blacklist)
1. `"계약 가능합니다"`
2. `"구매 가능합니다"`
3. `"수의계약 가능합니다"`
4. `"지역제한 가능합니다"`
5. `"낙찰 가능합니다"`

## 시나리오 1: 안전한 정상 생성 케이스
- **Given**: 유효한 DecisionContext와 GatewayResponse 주입
- **When**: Answer Builder가 `rendered_markdown`을 생성 및 스캔 로직을 수행함
- **Then**: 
  - `forbidden_phrase_scan_passed`는 `True`여야 한다.
  - `blocked_phrases_found`는 빈 배열(`[]`)이어야 한다.
  - `fallback_applied`는 `False`여야 한다.
  - 생성된 문자열 내부를 Regex로 스캔해도 위 5개 표현이 검출되지 않아야 한다.

## 시나리오 2: 금지 표현 누출(Leak) 케이스 차단 및 Fallback 발동
- **Given**: 후보표 내부의 Enrichment 보조 정보 영역이나, 혹은 면책조항 어딘가에 실수로 `"수의계약 가능합니다"`라는 텍스트가 조립된 상황
- **When**: Answer Builder가 최종 출력 전후로 스캔 로직을 수행함
- **Then**:
  - `forbidden_phrase_scan_passed`는 `False`로 변환되어야 한다.
  - `blocked_phrases_found` 배열에 `["수의계약 가능합니다"]`가 포함되어야 한다.
  - **`fallback_applied`는 `True`로 설정되어야 한다.**
  - 시스템은 해당 문자열 반환을 멈추고 기본(Fallback) 에러 메시지 객체로 응답을 철저히 대체해야 한다.
