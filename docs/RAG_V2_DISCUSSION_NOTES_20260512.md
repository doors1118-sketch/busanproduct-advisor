# RAG V2 구조 토론 메모

작성일: 2026-05-12

목적: 외근 후 집에서 이어서 논의할 수 있도록, RAG V2 전환 방향에 대해 현재까지 토론한 쟁점과 잠정 결론을 정리한다.

## 1. 논의 출발점

현재 논의의 출발점은 단순히 "RAG를 붙일 것인가"가 아니다.

핵심 문제는 다음이다.

```text
1. 기존 시스템이 질문 의도를 잘못 잡는 경우가 있다.
2. 질문 의도를 잘못 잡으면 내부 DB를 엉뚱하게 찾거나 못 찾는다.
3. 답변 템플릿이 질문 맥락에 맞지 않아 사용자가 보기에는 엉뚱한 답변처럼 보인다.
4. 자연어 답변 품질이 Gemini에 직접 물었을 때보다 떨어진다.
```

즉 V2의 목적은 "기존 규칙을 더 많이 추가하는 것"이 아니라, 질문 전체의 문맥을 더 잘 이해하고 내부 자료를 활용해 구매담당자에게 실무적으로 도움 되는 답변을 만드는 것이다.

## 2. 기존 시스템과 분리 원칙

V2는 기존 운영 시스템을 수정하지 않는 별도 실험 구조로 진행한다.

기존 유지 대상:

```text
/opt/advisor
busan-advisor-pilot.service
law-chatbot.service
app/gemini_engine.py
app/api_server.py
Streamlit UI
```

V2 실험 후보:

```text
experiments/rag_advisor_v2/
로컬 실험 우선
필요 시 /opt/advisor-rag-lab
port 8011
별도 service
```

## 3. 참고한 외부 글에서 얻은 점

부트캠프 RAG 경험 글과 LangChain/대화형 챗봇 관련 글을 보며 확인한 점:

```text
RAG는 FAQ, 사내지식, 고객지원처럼 "문서 내용을 찾아 설명"하는 영역에서는 효과가 크다.
Rule-based 챗봇은 예외가 늘수록 로직이 복잡해지고 대화 depth가 깊어지면 유지보수가 어려워진다.
프롬프트 설계와 검색 문서 구성은 답변 품질에 큰 영향을 준다.
LangChain은 문서 로딩, 청킹, retriever, prompt chain, message history 구성에는 유용하다.
```

다만 조달/계약 어드바이저는 FAQ형 RAG보다 위험도가 높다.

```text
계약대상 분류
금액 기준
수의계약 한도
MAS
지역제한
면허/분리발주
업체 DB 적합성
```

위 항목은 LLM이 그럴듯하게 단정하면 실무 리스크가 있다.

## 4. 초기에 검토한 무거운 구조

처음에는 다음과 같은 검증형 구조를 논의했다.

```text
사용자 질문
-> LLM 의도분석 JSON
-> 내부 RAG 검색
-> LLM 답변 초안 + 판단 JSON
-> 내부 검증기
   - 금액 기준
   - 수의계약 한도
   - MAS 기준
   - 지역제한 기준
   - 면허/분리발주
   - 업체 후보 DB 적합성
-> 최종 답변
```

이 구조의 장점:

```text
법령/금액/업체 적합성 판단을 LLM 단독에 맡기지 않는다.
claim JSON을 검증할 수 있다.
최종 답변의 추적 가능성이 높다.
```

하지만 단점도 분명하다.

```text
LLM 호출이 많아질 수 있다.
응답시간이 길어진다.
구현 난도가 높다.
검증기가 자연어를 사후 수정하면 답변이 어색해질 수 있다.
```

따라서 1차 V2로 바로 이 구조를 구현하는 것은 부담이 크다고 판단했다.

## 5. 검증기에 대한 정리

검증기가 자연어 답변을 뒤에서 땜질하는 구조는 피해야 한다.

나쁜 구조:

```text
LLM이 완성 답변 작성
-> 검증기가 틀린 문장 삭제/삽입
-> 문맥이 깨진 최종 답변
```

더 나은 구조:

```text
LLM이 초안 또는 답변 작성
-> 시스템이 위험 표현, 근거 없는 금액/업체/무위험 단정만 가볍게 후처리
-> 필요 시 면책 및 최종확인 문구 부착
```

검증기의 역할은 처음부터 거창할 필요가 없다. 1차에서는 "답변 안전 필터" 정도가 현실적이다.

최소 후처리 후보:

```text
근거 없는 업체명 추천 감지
제공하지 않은 금액 기준 생성 감지
"법적 문제 없음", "무조건 가능", "감사 리스크 없음" 같은 법적 무위험 단정 완화
최종 판단은 사용기관에서 최신 법령과 내부 기준으로 확인해야 한다는 문구 부착
```

## 6. LLM 답변 생성에 대한 재정리

토론 중 중요한 관점 변화가 있었다.

처음에는 "LLM에게 최종 답변 생성을 맡기면 위험하다"는 쪽으로 논의했지만, 이후 다음처럼 정리했다.

```text
LLM 답변 생성 자체가 문제는 아니다.
시중의 많은 대화형 에이전트도 LLM에게 답변 생성을 맡긴다.
우리도 내부 자료를 충분히 제공하고, 마지막에 실무 의견/최종확인 문구를 붙이면 실용성이 있다.
```

다만 다음 표현은 주의한다.

허용할 수 있는 실무 판단형 표현:

```text
이 사안은 먼저 종합쇼핑몰 등록 여부를 확인하는 것이 실무상 적절합니다.
4천만원이면 일반 1인 견적보다는 2인 이상 견적 또는 쇼핑몰 경로를 우선 검토하는 편이 안전합니다.
부산업체 중심으로 추진하려면 지역제한 가능성과 면허요건을 분리해서 봐야 합니다.
```

피해야 할 법적 확정형 표현:

```text
반드시 가능합니다.
법적으로 문제 없습니다.
이 업체와 수의계약하면 됩니다.
감사 리스크가 없습니다.
```

## 7. 내부 DB와 LLM 역할

현재 법령, 행정규칙, 매뉴얼, 지침 등은 내부 DB로 보유하고 있다.

중요한 판단:

```text
LLM이 내부 DB 검색 과정에 직접 개입하면 응답시간이 늦어질 가능성이 높다.
LLM이 여러 번 "어떤 DB를 더 찾아야 하는지" 판단하고 왕복하는 구조는 피한다.
```

따라서 기본 구조는 다음이 더 현실적이다.

```text
사용자 질문
-> 시스템이 빠르게 내부 DB 검색
-> 검색 결과 상위 몇 개 또는 근거 힌트를 정리
-> LLM에게 질문 + 내부 근거 전달
-> LLM이 자연어 답변 생성
-> 최소 후처리/면책문구
```

즉 LLM은 DB 검색자가 아니라 답변 작성자다.

```text
시스템:
  내부 DB 검색
  결과 정렬
  중복 제거
  근거 힌트 구성

LLM:
  질문 문맥 이해
  검색된 근거를 조합
  구매담당자 관점의 자연어 답변 작성
```

## 8. Evidence Card와 Vertex Grounding 비유

사용자가 제시한 비유:

```text
Evidence Card = 지도
Vertex Grounding DB = 지도가 통용되는 현실
LLM = 지도를 보고 실제 자료를 찾아 읽고 설명하는 사람
```

이 비유는 V2 구조를 단순화하는 데 중요하다.

기존 생각:

```text
내부 DB 원문 검색
-> Evidence Card로 압축
-> LLM에 카드 전달
```

수정된 실험 방향:

```text
시스템이 Evidence Map 또는 검색 힌트를 제공
-> Vertex Grounded LLM이 내부 datastore에서 실제 자료를 grounding
-> LLM이 문맥에 맞게 답변 작성
-> 시스템은 최소 후처리
```

이 경우 Evidence Card는 답변 근거 본문이 아니라 grounding 방향을 잡는 지도 역할을 한다.

예:

```json
{
  "case_hint": {
    "contract_object": "goods",
    "item": "컴퓨터",
    "amount": 40000000,
    "agency_type": "local_government"
  },
  "look_up_topics": [
    "물품 수의계약 금액 기준",
    "종합쇼핑몰 MAS 구매 절차",
    "2인 이상 견적 또는 입찰 검토",
    "추정가격 기준"
  ],
  "answer_policy": {
    "answer_as": "구매담당자 실무 안내",
    "avoid": ["근거 없는 업체 추천", "법적 무위험 단정"]
  }
}
```

## 9. Vertex Grounding 활용에 대한 잠정 결론

Vertex Grounding을 LLM 호출 안에 붙일 수 있다면, 별도 다단계 DB 왕복보다 빠르고 자연스러울 가능성이 있다.

잠정 구조:

```text
질문
-> Evidence Map / case hint 생성
-> Vertex Grounded LLM single-call answer
-> Safety/Post Check
-> 최종 답변
```

장점:

```text
LLM 호출 1회
프롬프트 토큰 절약
긴 내부 문서를 직접 보내지 않아도 됨
문맥 이해와 자연어 답변 품질 개선 가능
grounding citation이 있으면 추적 가능
```

확인 필요 조건:

```text
Vertex Grounding이 실제 내부 법령/행정규칙/매뉴얼/지침 datastore에 붙어 있는지
답변에 grounding source/citation metadata가 남는지
Google Search 일반 웹 grounding이 아니라 내부 자료 grounding인지
LLM이 근거 없는 내용을 말했을 때 최소 후처리로 감지 가능한지
```

## 10. V2 1차 실험 방향 재정리

무거운 검증형 구조보다, 1차는 단순한 grounded/RAG 답변 실험이 적절하다.

1차 목표:

```text
제미나이처럼 질문 전체 문맥에 맞는 답변을 하게 한다.
다만 답변 근거는 내부 자료 또는 Vertex 내부 datastore grounding으로 제한한다.
시스템은 답변 생성에 과도하게 개입하지 않고 최소 안전장치와 로그만 담당한다.
```

후보 구조 A: 내부 DB 직접 검색형

```text
사용자 질문
-> 내부 DB 검색
-> 근거 3~7개 구성
-> LLM 답변 생성
-> 최소 후처리
-> 최종 답변
```

후보 구조 B: Vertex Grounded Single Call

```text
사용자 질문
-> Evidence Map / case hint
-> Vertex Grounded LLM 답변
-> 최소 후처리
-> 최종 답변
```

현재 토론 기준으로는 B안이 더 단순하고 자연어 품질도 기대된다. 다만 Vertex Grounding이 실제 내부 datastore와 연결되어 있고 citation을 받을 수 있는지 확인이 선행되어야 한다.

## 11. LangChain에 대한 위치

LangChain은 사용 가능하지만, 현재 논의의 본질은 LangChain 도입이 아니다.

유용한 영역:

```text
DocumentLoader
TextSplitter
Retriever
PromptTemplate / ChatPromptTemplate
Runnable chain
Message history
Golden QA 평가 보조
```

하지만 1차 V2에서는 프레임워크보다 구조 확정이 우선이다.

LangChain은 필요 시 다음 단계에서 adapter로 붙이는 것이 적절하다.

```text
우리 V2 core:
  질문/근거/답변/후처리 구조

LangChain:
  문서 로딩, 검색, 프롬프트 호출 보조
```

## 12. 남은 핵심 질문

집에서 이어서 논의할 질문:

```text
1. Vertex Grounding이 현재 우리 내부 자료 datastore와 실제로 연결 가능한가?
2. Gemini/Vertex 호출 응답에서 grounding citation metadata를 받을 수 있는가?
3. V2 1차는 내부 DB 검색형(A)과 Vertex Grounded Single Call(B) 중 무엇을 먼저 구현할 것인가?
4. 최소 후처리 필터는 어디까지 둘 것인가?
5. Golden QA 10개로 기존 시스템, 내부 DB RAG, Vertex Grounding 답변을 어떻게 비교할 것인가?
```

## 13. 현재 잠정 결론

현재까지 가장 현실적인 방향:

```text
기존 시스템은 건드리지 않는다.
V2 1차는 무거운 검증형 에이전트가 아니라 단순 grounded/RAG 답변 실험으로 간다.
LLM에게 답변 생성을 맡긴다.
단, 내부 자료 또는 Vertex internal datastore grounding을 기반으로 답하게 한다.
시스템은 최소 후처리, 로그, Golden QA 비교를 담당한다.
```

가장 유력한 1차 구조:

```text
사용자 질문
-> Evidence Map / case hint 생성
-> Vertex Grounded LLM single-call answer
-> 최소 안전 필터
-> 최종 답변
-> QA 로그
```

Fallback 구조:

```text
Vertex Grounding이 확인되지 않으면
내부 DB 검색 결과를 직접 LLM에 넣는 Simple RAG로 실험한다.
```

이 방향은 "기존 시스템은 의도와 템플릿이 약해서 Gemini 직접 질문보다 답이 어색하다"는 원래 문제의식에 가장 직접적으로 대응한다.
