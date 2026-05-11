# 답변품질 향상 개선 과제 메모

작성일: 2026-05-12

목적: 구매담당자 업무지원용 챗봇을 내부 파일럿/자율 사용 도구로 배포하기 전에, 답변 품질을 체계적으로 끌어올리기 위해 무엇을 우선 개선해야 하는지 정리한다.

## 1. 현재 상태에 대한 객관적 판단

현재 시스템은 공식 계약 판단 시스템이 아니라 구매담당자의 업무 참고 도구다. 이 전제에서는 제한적 배포가 가능하다. 다만 답변 품질에 대한 우려는 분명히 남아 있다.

가장 큰 리스크는 속도보다 **그럴듯한 답변을 사용자가 공식 판단처럼 받아들이는 것**이다. 따라서 답변 품질 개선은 단순히 문장을 자연스럽게 만드는 문제가 아니라, 다음 네 단계를 안정화하는 일이다.

```text
질문 이해
  -> 근거 선택
  -> 답변 작성
  -> 검증/피드백
```

현재 구조의 강점은 내부 법령 DB, deterministic gate, 업체 API, 실무카드, QA meta가 잘 쌓여 있다는 점이다. 반대로 약점은 질문 맥락 이해가 여러 규칙과 RAG 힌트에 분산되어 있고, LLM이 질문 이해의 상시 1차 엔진으로 작동하지 않는다는 점이다.

## 2. 우선순위 결론

답변 품질 향상을 위해 가장 먼저 할 일은 모범답안을 계속 추가하는 것이 아니다.

우선순위는 다음 순서가 적절하다.

1. Golden QA 세트 구축
2. LLM Context Analyzer 추가
3. Intent RAG 역할 재정의 및 보정
4. 답변 섹션 표준화
5. Natural Writer 적용 확대 및 통제
6. 서버 QA 자동화
7. 사용자 피드백 루프 구축

## 3. Golden QA 세트 구축

### 왜 필요한가

지금처럼 문제 답변을 발견할 때마다 모범답안을 넣는 방식은 단기 처방에는 도움이 된다. 하지만 시스템 성능을 객관적으로 평가하기 어렵다.

수정 후 다음을 판단할 수 있어야 한다.

- 이번 수정으로 원래 문제는 해결됐는가
- 다른 질문이 새로 망가지지는 않았는가
- 답변 속도는 유지되는가
- 법령 근거와 금액 기준은 안정적으로 남는가
- 자연어 품질은 실제로 좋아졌는가

### 구성 방식

처음에는 50개, 이후 100개 정도로 늘린다.

각 문항은 다음 필드를 가진다.

```yaml
id: vat_threshold_001
question: 수의계약 한도를 계산할 때 부가가치세를 포함해야 하나요, 제외해야 하나요?
agency_type: local_government
question_type: legal_basis_explanation
expected_conclusion: 수의계약 한도는 VAT 제외 추정가격 기준
required_legal_basis:
  - 추정가격
  - 지방계약법령상 계약방법 결정 기준
required_practice_points:
  - 예정가격/계약금액과 구분
  - 정책기업 5천만원 특례도 추정가격 기준
forbidden_answers:
  - 공사 수의계약 한도만 나열
  - VAT 포함 여부를 직접 답하지 않음
quality_tags:
  - vat
  - direct_contract
  - amount_basis
```

### 우선 포함할 문항군

- VAT 포함/제외
- 일반 물품 1,800만원 1인 수의
- 여성기업 SW 4,500만원
- 장애인기업 용역 7,000만원
- 사회적협동조합 5,000만원
- 분할발주 2,000만원 3회
- 재난복구 공사 1억원
- 학술연구용역 3,000만원 대학 연구소
- 혁신제품 금액 제한
- 특허 보유 업체 2억원
- 공기업/준정부기관과 지방계약법 혼동
- 보안용카메라 물품/공사/SW/경비 경계
- 경비용역/무인경비 면허
- 업체추천과 계약방법 복합 질문

## 4. LLM Context Analyzer 추가

### 문제의식

현재 LLM은 주로 조건부 route adjudicator, grounded single-pass writer, natural writer로 개입한다. 즉, 사용자가 기대하는 "처음부터 질문의 맥락을 깊게 읽는 역할"은 제한적이다.

질문 오해가 발생하면 이후 내부 DB 검색이나 template이 좋아도 답변이 엉뚱해질 수 있다.

### 권장 역할

LLM Context Analyzer는 답변을 쓰면 안 된다. 법령 수치나 가능/불가능 결론도 만들면 안 된다.

해야 할 일은 질문을 구조화하는 것이다.

```json
{
  "question_type": "case_judgment",
  "contract_object": "goods",
  "amount": 45000000,
  "amount_basis_required": true,
  "institution_type_hint": "local_government",
  "policy_company_type": "women_enterprise",
  "special_basis": ["software_purchase"],
  "local_support_intent": true,
  "company_lookup_intent": false,
  "legal_basis_required": true,
  "answer_sections_required": [
    "conclusion",
    "legal_basis",
    "procedure",
    "documents",
    "cautions"
  ],
  "must_not_answer_as": [
    "company_recommendation_only"
  ],
  "confidence": 0.86,
  "reason": "금액, SW, 여성기업, 부산 소재, 1인 수의 절차가 함께 있는 사안형 질문"
}
```

### 설계 원칙

- 모델: 빠른 Flash급 모델
- thinking budget: 0
- timeout: 1.5초에서 3초
- 출력: JSON only
- 실패 시 기존 Keyword/Intent RAG 경로로 fallback
- 법령 수치, 최종 결론, 업체 적격성 판단 금지
- 내부 DB/rule layer가 최종 판단권을 유지

### 기대 효과

- 질문이 업체추천인지 계약방법 검토인지 더 안정적으로 구분
- 물품/용역/공사/SW/정보통신공사/경비용역 경계 질문 처리 개선
- 기관유형 혼동 감소
- 답변 섹션 누락 감소

## 5. Intent RAG 역할 재정의

### 현재 한계

Intent RAG는 유사 질문과 실무카드를 찾아 라우팅을 보강한다. 그러나 복합 법령 질문에서는 표면상 비슷한 질문에 끌려가 잘못된 label을 줄 수 있다.

Intent RAG를 정답 엔진처럼 취급하면 위험하다.

### 개선 방향

- 명칭과 문서상 역할을 "정답 근거"가 아니라 "질문 맥락 힌트"로 정의
- QA 로그에 top match, score, source를 더 잘 노출
- 잘못 매칭된 사례를 negative example로 추가
- 위험 쟁점은 유사도보다 issue tag 우선

위험 쟁점 예시:

- VAT
- 혁신제품
- 특허
- 사회적협동조합
- 분할발주
- 재난복구
- 학술연구
- 공기업/준정부기관
- 보안용카메라
- 경비용역

### 권장 제한

Intent RAG가 다음을 직접 결정하지 않도록 한다.

- 가능/불가능 결론
- 금액 기준
- 법령 조항 확정
- 업체 적격성
- 중소기업자간 경쟁제품 여부
- 직접생산확인 대상 여부

## 6. 답변 섹션 표준화

### 기본 구조

구매담당자용 답변은 대부분 다음 구조를 따른다.

```text
결론
법적 근거
이 건 판단
실무 절차
확인 서류
주의사항
대안 경로
```

질문 유형별로 필요 없는 섹션은 생략하되, 사안형 질문에서는 `결론`, `법적 근거`, `이 건 판단`, `주의사항`은 기본적으로 유지한다.

### 장점

- 담당자가 빠르게 스캔 가능
- 답변 누락 여부를 자동 평가하기 쉬움
- Natural Writer가 다듬을 범위를 정하기 쉬움
- 법령 근거와 실무 조언이 섞이지 않음

### 주의점

모든 답변을 장문 매뉴얼처럼 만들면 사용성이 떨어진다. 질문이 단순하면 짧게 답하고, 복합질문만 섹션을 넓힌다.

## 7. Natural Writer 개선

### 현재 문제

Deterministic answer는 정확성에는 유리하지만 문장이 딱딱할 수 있다. 반대로 LLM writer를 무제한 적용하면 새 사실이나 새 결론을 만들어낼 위험이 있다.

### 권장 정책

Writer는 다음을 바꾸면 안 된다.

- 법령명
- 조문번호
- 금액 기준
- 가능/불가능 결론
- 표의 수치
- 확인서/증빙명

Writer가 바꿔도 되는 것:

- 도입 문장
- 설명 문단
- 실무 조언 표현
- 중복 문장 정리
- 내부 용어 제거

### 구현 아이디어

- 답변을 freeze block과 rewrite block으로 분리
- 법령/금액/결론/표는 freeze
- 본문 설명만 rewrite
- rewrite 후 금지표현, 근거 누락, 숫자 변조를 검사
- QA meta에 writer 적용 여부와 skip reason을 필수 기록

## 8. 서버 QA 자동화

### 최소 회귀 테스트

수정할 때마다 다음을 자동 실행한다.

- 핵심 50문항 regression
- 오늘 보강한 수의계약 특례 문항
- 기관유형 혼재 문항
- 업체추천+계약방법 복합문항
- 공기업/준정부기관 문항

### 측정 지표

- HTTP success rate
- 평균 응답시간
- p50, p95, max latency
- 15초 초과 건수
- 30초 초과 건수
- `model_selected`
- `model_decision_reason`
- `deterministic_template_used`
- `intent_rag_confidence`
- `llm_adjudicator_called`
- `natural_language_writer_applied`
- `legal_basis` 존재 여부
- 금지표현 잔존 여부

### 자동 평가 항목

각 Golden QA 문항에 대해 다음을 검사한다.

- required keywords 포함
- forbidden keywords 미포함
- required legal basis 포함
- 기관유형 혼동 없음
- 답변 타입 일치
- 업체추천 금지 질문에서 업체표 미출력
- 금액 기준이 VAT 제외 추정가격인지 명시

## 9. 사용자 피드백 루프

실제 구매담당자가 쓰면 예상 밖 질문이 나온다. 따라서 UI에 간단한 피드백을 붙여야 한다.

권장 버튼:

- 도움이 됨
- 애매함
- 틀림

틀림/애매함 선택 시 사유:

- 금액 기준 오류
- 법령 근거 오류
- 기관유형 오류
- 계약대상 구분 오류
- 업체추천 오류
- 절차 누락
- 표현이 어려움
- 기타

피드백은 QA 로그와 연결되어야 한다.

## 10. 배포 전 안내 문구

내부 파일럿 배포 시 다음 성격을 분명히 해야 한다.

```text
이 챗봇은 구매담당자의 업무 검토를 돕는 참고 도구입니다.
답변은 최종 계약 판단이나 법적 의견이 아니며,
실제 계약 진행 전에는 최신 법령, 행정규칙, 기관 내부 기준,
계약부서 검토를 반드시 확인해야 합니다.
```

특히 다음 표현은 피한다.

- 공식 판단 시스템
- 계약 가능 자동 판정
- 법률 검토 완료
- 이 답변대로 진행 가능

## 11. 실행 로드맵

### 1단계: 평가 기반 만들기

- Golden QA 50문항 작성
- 현재 서버 답변 baseline 저장
- 자동 평가 스크립트 초안 작성
- QA 결과를 Markdown/JSON으로 출력

### 2단계: 질문 이해 보강

- LLM Context Analyzer schema 설계
- 기존 Gateway/Keyword/Intent RAG 결과와 병합
- timeout/fallback 정책 적용
- QA meta에 analyzer 결과 저장

### 3단계: 답변 구조 안정화

- 질문 유형별 섹션 템플릿 정리
- deterministic answer를 섹션 단위로 정규화
- Writer freeze/rewrite block 분리

### 4단계: 운영 피드백 반영

- UI 피드백 버튼 추가
- 틀린 답변 로그 수집
- negative example/Golden QA 지속 보강
- 주 1회 품질 리포트 생성

## 12. 최종 의견

지금 시스템은 내부 업무 보조용 파일럿으로는 의미가 있다. 다만 성능 향상은 "모범답안 추가"만으로는 한계가 있다.

가장 중요한 개선축은 다음 세 가지다.

```text
Golden QA 세트
LLM Context Analyzer
답변 섹션 표준화
```

이 세 가지를 먼저 잡으면, 이후 개별 답변 보강이 감에 의존하지 않고 성능 개선 루프로 들어간다. 특히 구매담당자에게 배포할 시스템이라면 정확성뿐 아니라 "왜 이런 답변이 나왔는지 추적 가능해야 한다"는 점이 중요하다.

따라서 내일 개선 연구는 새로운 모범답안을 더 넣는 것보다, 위 세 가지를 설계하고 작은 실험으로 검증하는 방향이 가장 효과적이다.
