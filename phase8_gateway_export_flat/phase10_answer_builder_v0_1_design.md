# Phase 10 Answer Builder v0.1 Design

본 문서는 `GatewayResponse`와 Rule Engine의 `DecisionContext`를 입력받아 최종 사용자에게 렌더링될 구조화된 답변을 조립하는 **Answer Builder v0.1**의 설계 원칙과 아키텍처를 정의합니다.

## 1. 아키텍처 및 역할
- **역할**: Answer Builder는 **법적 결론 생성기가 아니라 "사용자 응답 조립기(Response Assembler)"** 입니다. 제공된 컨텍스트 데이터를 기반으로 각 역할을 담당하는 섹션을 안전하게 텍스트화하고 조합합니다.
- **입력**: `GatewayResponse`와 `DecisionContext` 두 가지만을 입력으로 허용합니다.
- **출력**: 구조화된 `AnswerBuilderOutput` 객체 (렌더링된 Markdown 문자열 포함).

## 2. 엄격한 섹션 격리 정책 (Section Isolation)
각 데이터 파트는 허용된 섹션에만 독립적으로 배치되어 의미상 혼선이나 법적 단언으로 해석되는 것을 막습니다.
- `procedure_context`: 오직 **절차 안내 섹션(Procedure Guidance Section)** 에서만 참고용 텍스트로 사용합니다.
- `company_candidate_context`: 오직 **후보표 섹션(Candidate Table Section)** 의 구조화된 Row 데이터 렌더링에만 사용합니다.
- `enrichment_data`: 후보표의 **참고용 보조정보(보조 열)** 로만 표시되며, 이 데이터의 유무가 전체 리뷰 결과(`review_outcome`)를 변경하거나 적격성을 확정하는 뉘앙스로 표기되어서는 안 됩니다.

## 3. Forbidden Phrase Scan (금지 표현 통제 및 Fallback)
최종 문자열 `rendered_markdown`이 생성되기 전후로 반드시 금지 표현 스캔 파이프라인을 통과해야 합니다.
- 스캔 대상: 요약, 룰 리뷰, 절차, 후보표, 주의사항, 면책 조항을 포함한 렌더링된 전체 Markdown 문자열.
- 차단 조치: 금지 표현이 단 1개라도 탐지될 경우 `forbidden_phrase_scan_passed = False` 및 `fallback_applied = True`로 마킹하고, 안전한 기본(Fallback) 템플릿으로 응답 텍스트를 대체합니다.
- **Fallback 템플릿 구조**:
  - 요약: "내부 검토 로직에 따라 안전한 답변 생성을 위해 일시적으로 답변이 제한되었습니다."
  - 주의사항: "정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다."
  - 나머지 모든 동적 정보(후보표 등)는 삭제 또는 마스킹 처리됨.
