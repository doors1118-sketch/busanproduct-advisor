# RAG V2 기본구조 및 작업순서

작성일: 2026-05-13

목적: 기존 시스템을 수정하지 않고, 지역상품/지역업체 구매지원을 위한 V2 어드바이저를 원점에서 새로 설계하기 위한 기준 구조와 작업 순서를 고정한다.

## 1. 절대 유지 조건

기존 운영 시스템은 시연 및 운영 안정성을 위해 건드리지 않는다.

유지 대상:

```text
/opt/advisor
busan-advisor-pilot.service
law-chatbot.service
기존 FastAPI API 서버
기존 Streamlit UI
기존 app/gemini_engine.py
기존 app/api_server.py
```

V2는 별도 실험 구조로만 진행한다.

로컬 작업 위치:

```text
experiments/rag_advisor_v2/
```

네이버클라우드 실험 배포 위치:

```text
/opt/advisor-rag-lab
```

네이버클라우드 실험 API:

```text
port 8011
service: busan-advisor-rag-lab.service
```

UI가 필요하면 별도 포트를 사용한다.

```text
port 8512 후보
service는 기존 law-chatbot.service와 분리
```

## 2. 서비스 정체성

V2는 일반 법령 질의응답 챗봇이 아니다.

정체성:

```text
지역상품/지역업체 구매를 망설이는 구매담당자에게
법령, 규정, 지침, 매뉴얼 해석과 지역업체/지역상품 정보를 함께 제공하는
지역구매 지원 어드바이저
```

따라서 질문 해석의 기본 정책은 다음과 같다.

```text
사용자가 품목, 공사, 용역, 예산, 구매 절차를 묻는 경우
명시적으로 "지역업체 추천" 또는 "부산업체"라고 말하지 않아도
지역업체/지역상품 활용 검토 의도가 있다고 본다.
```

예:

```text
예산이 4천만원인데, 컴퓨터 구매 절차 알려줘
```

이 질문은 단순 계약방법 질문이 아니라 다음 의도를 포함한 것으로 본다.

```text
컴퓨터 구매 절차
계약/구매 경로
지역업체 활용 가능성
지역상품 또는 지역 공급 후보 확인
```

## 3. 기본 구조

V2는 기존 키워드 라우터, 규칙 템플릿, deterministic answer를 고치는 방향이 아니다.

기본 구조:

```text
사용자 질문
-> LangGraph prepare_context
-> Grounded LLM Answer
-> Vendor/Product Lookup
-> Post Check
-> Final Builder
-> QA Log
```

핵심 역할 분리:

```text
LLM:
  질문 의도 파악
  내부 grounding 자료 기반 답변 작성
  구매담당자 관점의 실무 설명

Vertex Grounding / LLM 연결형 datastore:
  법령
  행정규칙
  매뉴얼
  지침
  모범답안
  구매지원 정책 문서

시스템 DB/API:
  지역업체 후보
  지역상품 정보
  업종/면허/인증/품목 매칭
  일일/주간 업데이트 데이터

LangGraph:
  답변 정책 주입
  실행 흐름 관리
  조건부 분기
  근거 확인
  업체 후보 결합
  fallback
  QA 로그 저장
```

## 4. 왜 이 구조인가

기존 문제:

```text
질문 의도 파악이 키워드/규칙에 치우쳐 있다.
질문 전체 맥락을 놓치면 답변이 엉뚱해진다.
템플릿 답변은 구매담당자 관점에서 자연스럽지 않다.
지역업체 구매지원이라는 서비스 목적이 답변에 항상 반영되지 않는다.
```

V2 구조의 목표:

```text
LLM이 질문 전체를 읽고 의도를 파악한다.
LLM이 내부 법령/지침/매뉴얼 grounding 자료를 활용해 답변한다.
지역업체/지역상품 후보는 최신 시스템 DB/API에서 붙인다.
LangGraph가 답변 흐름과 품질 게이트를 관리한다.
```

## 5. 데이터 처리 원칙

고정 지식과 변동 데이터를 분리한다.

고정 지식:

```text
법령
행정규칙
조달/MAS 지침
실무 매뉴얼
자주 쓰는 모범답안
구매지원 정책 설명 자료
```

처리 방식:

```text
Vertex Grounding 또는 유사한 LLM 연결형 datastore에 구축
LLM이 한 번의 grounded answer 호출 안에서 활용
```

변동 데이터:

```text
지역업체 후보
지역상품 현황
업체 면허/업종/인증
공급 가능 품목
업체 API 일일/주간 업데이트
```

처리 방식:

```text
시스템 DB/API로 조회
LLM이 업체를 생성하지 않음
최종 답변에 시스템이 업체 후보 섹션으로 결합
```

## 6. 답변 생성 원칙

LLM은 답변 생성을 담당한다.

다만 답변 정책을 명확히 주입한다.

필수 정책:

```text
지역상품/지역업체 구매지원 관점을 기본 포함한다.
결론을 먼저 말한다.
구매담당자가 바로 실행할 수 있는 절차를 제시한다.
법령/규정 근거는 내부 grounding 자료를 우선 사용한다.
근거 없는 업체명은 만들지 않는다.
특정 업체의 적격성이나 계약 가능성을 확정하지 않는다.
법적 무위험, 감사 리스크 없음, 반드시 가능 같은 표현을 피한다.
최종 판단은 사용기관의 최신 법령, 내부 기준, 계약부서 검토로 확정하도록 안내한다.
```

기본 답변 섹션:

```text
1. 핵심 결론
2. 계약/구매 경로
3. 지역업체/지역상품 활용 방향
4. 지역업체/지역상품 후보 조회 결과
5. 실무 절차
6. 주의사항
7. 최종 확인사항
```

질문이 단순 법령 개념 질문이면 업체 후보 섹션은 생략할 수 있다.

품목, 공사, 용역, 예산, 구매절차가 있으면 업체 후보 섹션은 기본 포함한다.

## 7. LangGraph 기준 노드 설계

초기 V2 그래프:

```text
START
-> prepare_context_node
-> grounded_llm_answer_node
-> vendor_product_lookup_node
-> post_check_node
-> conditional_route
   ├─ clean -> final_builder_node
   ├─ needs_caution -> caution_builder_node
   └─ unsafe_or_no_grounding -> fallback_builder_node
-> qa_log_node
-> END
```

### 7.1 prepare_context_node

역할:

```text
사용자 질문 원문 유지
서비스 목적 주입
지역업체 구매지원 정책 주입
답변 섹션 요구
금지 표현 주입
grounding 사용 지시
업체 후보 조회 기본 정책 설정
```

이 노드는 기존 키워드 라우터처럼 최종 route를 결정하지 않는다.

주요 state:

```json
{
  "question": "...",
  "product_policy": {
    "mission": "local_vendor_purchase_support",
    "default_region": "Busan",
    "infer_vendor_intent_when_item_or_work_identified": true
  },
  "answer_contract": {
    "required_sections": [
      "핵심 결론",
      "계약/구매 경로",
      "지역업체/지역상품 활용 방향",
      "실무 절차",
      "주의사항",
      "최종 확인사항"
    ],
    "vendor_section_policy": "include_when_item_work_service_or_budget_detected"
  }
}
```

### 7.2 grounded_llm_answer_node

역할:

```text
LLM이 질문 의도를 파악한다.
Vertex Grounding 또는 내부 datastore를 사용한다.
법령/규정/매뉴얼 기반으로 자연어 답변을 작성한다.
지역업체 구매지원 관점을 반영한다.
```

LLM 호출은 1차에서 가능하면 1회로 유지한다.

출력 후보:

```json
{
  "answer_text": "...",
  "detected_case": {
    "item_or_work": "컴퓨터",
    "amount": 40000000,
    "contract_object": "goods",
    "vendor_lookup_needed": true
  },
  "grounding_sources": [
    {
      "title": "...",
      "source_type": "manual",
      "citation": "..."
    }
  ]
}
```

### 7.3 vendor_product_lookup_node

역할:

```text
LLM이 감지한 품목/공사/용역 또는 시스템이 추출한 단서로
지역업체/지역상품 후보를 최신 DB/API에서 조회한다.
```

원칙:

```text
업체 후보는 LLM이 만들지 않는다.
시스템 DB/API 결과만 표시한다.
후보는 참고 정보이며 최종 적격성은 확인사항으로 둔다.
```

조회 조건 예:

```json
{
  "region": "Busan",
  "item_or_work": "컴퓨터",
  "contract_object": "goods",
  "keywords": ["컴퓨터", "PC", "전산장비", "유지보수"]
}
```

### 7.4 post_check_node

역할:

```text
grounding source 존재 여부 확인
법적 무위험 단정 표현 확인
근거 없는 업체명 생성 여부 확인
답변 섹션 누락 확인
업체 후보 출처 확인
```

위험 수준:

```text
clean
needs_caution
unsafe_or_no_grounding
```

### 7.5 final_builder_node

역할:

```text
LLM 답변
+ 업체 후보 섹션
+ 최종 확인 문구
+ QA meta
```

최종 확인 문구 예:

```text
이 답변은 지역상품 구매 검토를 돕기 위한 실무 의견입니다.
최종 계약방법과 발주 조건은 최신 법령, 조달 등록 현황,
기관 내부 기준, 계약부서 검토에 따라 확정해 주세요.
```

### 7.6 fallback_builder_node

grounding이 없거나 위험이 큰 경우에는 답변을 확인사항 중심으로 낮춘다.

예:

```text
현재 내부 근거가 충분히 확인되지 않아 계약방법을 단정하기는 어렵습니다.
다만 이 사안은 다음 순서로 확인하는 것이 좋습니다.
```

## 8. 파인튜닝 위치

파인튜닝은 지식 주입용이 아니다.

파인튜닝에 넣지 않을 것:

```text
법령 원문
행정규칙 원문
업체 현황
지역상품 최신 목록
금액 기준 최신 데이터
```

파인튜닝 후보:

```text
지역업체 구매지원 관점
답변 섹션 구조
결론 먼저 말하는 방식
구매담당자 실무어
업체 후보를 참고 후보로 표현하는 방식
불확실성을 확인사항으로 분리하는 방식
법적 무위험 단정 회피
```

우선순위:

```text
1. Golden QA
2. 프롬프트/답변계약
3. Grounding 품질 개선
4. 후처리 및 LangGraph 분기
5. 반복되는 스타일 문제가 남을 때 파인튜닝 검토
```

## 9. 작업순서

### 0단계: 운영 분리 원칙 고정

목표:

```text
기존 운영 시스템 수정 금지
V2 실험 위치와 포트 고정
```

산출물:

```text
docs/RAG_V2_BASE_ARCHITECTURE_AND_WORKPLAN_20260513.md
experiments/rag_advisor_v2/ 작업 폴더
```

### 1단계: V2 로컬 골격 생성

로컬 폴더:

```text
experiments/rag_advisor_v2/
```

초기 파일:

```text
README.md
api.py
graph.py
state.py
settings.py
prompts/
  system_policy.md
  answer_contract.md
  grounded_answer.md
post_checks/
  safety_filter.py
  citation_checker.py
vendors/
  vendor_adapter.py
  mock_vendor_adapter.py
tests/
  golden_cases/
```

기능:

```text
/health
/chat
LangGraph skeleton
mock grounded answer
mock vendor lookup
```

### 2단계: Golden QA 10개 기준 고정

초기 10개 질문:

```text
1. 예산이 4천만원인데, 컴퓨터 구매 절차 알려줘
2. 노트북 4천5백만원 구매하려고 한다. 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?
3. 조경공사를 부산업체 중심으로 발주하려면 지역제한, 면허요건, 업체 추천을 어떻게 설계해야 해?
4. 1억원으로 학교 운동장 천연잔디 조성공사를 하려고 하는데 계약방법, 면허요건, 부산업체 후보를 알려줘
5. 청사 경비용역을 부산업체 중심으로 검토하려면 지역제한과 면허를 어떻게 봐야 해?
6. 발달장애 행사 용역 예산 2억원으로 사업 추진하고 싶어. 계약 방법 안내해줘.
7. 소방시설공사 2천만원에서 지역제한과 전문공사 기준을 같이 검토해줘
8. 정보통신공사 1천만원이면 지역제한, 면허요건, 분리발주 필요성을 종합 검토해줘
9. 번역용역 4천만원에서 부산업체 활용 조건을 넣을 수 있는지 계약방식과 평가항목 관점에서 검토해줘
10. 사회적기업 물품 3천만원이면 중소기업자간 경쟁제품이어도 수의계약 가능한가?
```

각 case 필드:

```yaml
id:
question:
expected_intent:
required_sections:
must_include:
vendor_candidate_expected:
forbidden_patterns:
quality_notes:
```

### 3단계: Vertex Grounding 가능성 확인

확인할 것:

```text
현재 Vertex 내부 datastore를 Gemini 호출에 연결할 수 있는가?
법령/행정규칙/매뉴얼/지침 데이터를 datastore로 구성할 수 있는가?
응답에서 grounding citation/source metadata를 받을 수 있는가?
grounding 실패 여부를 코드에서 감지할 수 있는가?
```

결정:

```text
가능하면 Vertex Grounded LLM을 primary로 사용
불가능하거나 citation 추적이 약하면 내부 DB simple RAG를 fallback으로 사용
```

### 4단계: Grounded LLM 프롬프트/답변계약 작성

핵심 프롬프트 정책:

```text
당신은 부산 지역상품 구매지원 어드바이저입니다.
품목, 공사, 용역, 예산, 구매 절차가 제시되면
명시적 요청이 없어도 지역업체/지역상품 활용 가능성을 함께 검토하세요.
내부 grounding 자료를 우선 사용하세요.
근거 없는 업체명은 만들지 마세요.
```

출력 정책:

```text
구매담당자용 자연어 답변
가능하면 감지한 품목/금액/업체후보 필요 여부를 구조화 meta로 함께 반환
```

### 5단계: Vendor/Product Adapter 구현

초기:

```text
mock vendor adapter
```

이후:

```text
현재 업체 API 또는 DB adapter 연결
일일/주간 업데이트 데이터 조회
지역/품목/업종/면허/인증 기반 후보 반환
```

업체 후보 출력:

```text
업체명
지역
관련 품목/업종
확인 필요사항
출처/조회일
```

### 6단계: Post Check 최소 구현

검사:

```text
grounding source 없음
업체 DB에 없는 업체명 추천
법적 무위험 단정 표현
답변 섹션 누락
최종 확인 문구 누락
```

결과:

```text
clean
needs_caution
unsafe_or_no_grounding
```

### 7단계: Final Builder 구현

조립:

```text
LLM 답변
지역업체/지역상품 후보 섹션
주의사항
최종 확인 문구
```

원칙:

```text
업체 후보표는 시스템이 작성
LLM 답변 본문은 가능한 유지
위험한 경우 caution/fallback 문구로 낮춤
```

### 8단계: 로컬 API 테스트

로컬 실행:

```text
uvicorn experiments.rag_advisor_v2.api:app --host 127.0.0.1 --port 8011
```

테스트:

```text
GET /health
POST /chat
Golden QA 10개 수동/자동 비교
```

비교 항목:

```text
의도 파악
지역업체 활용 안내 포함 여부
근거/citation
업체 후보 섹션
답변 자연스러움
위험 단정 표현
응답시간
```

### 9단계: 네이버클라우드 별도 실험 배포

서버 작업 폴더:

```text
/opt/advisor-rag-lab
```

서비스:

```text
busan-advisor-rag-lab.service
```

포트:

```text
8011
```

주의:

```text
/opt/advisor 수정 금지
busan-advisor-pilot.service 수정 금지
law-chatbot.service 수정 금지
기존 .env 덮어쓰기 금지
V2용 .env 별도 사용
```

### 10단계: 품질 개선 루프

반복:

```text
Golden QA 실행
답변 품질 평가
실패 유형 분류
프롬프트/답변계약 수정
grounding 문서 보강
업체 adapter 개선
필요 시 LangGraph 분기 추가
```

파인튜닝 검토 시점:

```text
Grounding과 프롬프트로도 반복적으로 답변 스타일/구조가 흔들릴 때
```

## 10. 1차 구현 범위

1차는 완전한 운영 시스템이 아니라 구조 검증이다.

포함:

```text
FastAPI skeleton
LangGraph skeleton
Grounded answer node interface
Mock LLM 또는 실제 Gemini adapter 선택 가능 구조
Mock vendor adapter
Post check 최소 버전
Golden QA 10개
README
```

제외:

```text
기존 운영 API 수정
기존 Streamlit UI 수정
기존 rule engine 이식
기존 템플릿 재사용 전제
운영 배포 자동화
파인튜닝
```

## 11. 최종 기준선

V2 기준선:

```text
LLM 중심 질문 이해
+ Vertex Grounding 기반 법령/규정/매뉴얼 활용
+ 시스템 DB/API 기반 지역업체/지역상품 후보 결합
+ LangGraph 기반 흐름 통제
+ Golden QA 기반 품질 관리
```

이 구조를 기준으로 이후 구현한다.
