# Handoff Context - 2026-05-11

이 문서는 집/사무실을 오가며 이어서 작업하기 위한 작업 맥락 요약이다.
민감정보(API key, SSH password, 서버 비밀번호, 토큰)는 포함하지 않는다.

## 현재 동기화 상태

- GitHub `main`: `3bac74c Bust UI cache for streaming client`
- 집 로컬: `main` 기준 clean
- 서버 `/opt/advisor`: `3bac74c`
- 서버 서비스: `busan-advisor-pilot.service` active
- 서버 `/version` 확인값:
  - `commit_hash`: `3bac74c`
  - `model_primary`: `gemini-2.5-flash`
  - `model_fallback`: `gemini-2.5-flash`
  - `prompt_mode`: `dynamic_v1_4_4`
  - `production_deployment`: `HOLD`

## 핵심 사용자 의도

최근 작업의 중심은 다음이다.

1. LLM 내부 도구호출을 중단하고, 챗봇 서버가 내부 법령/행정규칙/매뉴얼/업체 자료를 먼저 조회한다.
2. LLM이 필요한 경우에는 서버가 만든 근거카드와 요약자료를 함께 넘겨 single-pass로 답변을 생성한다.
3. 이때 카드 생성 시간, 내부 DB/Vertex 검색 시간, LLM 생성 시간을 분리해 관찰하고, 전체 응답 지연이 과도하지 않은지 본다.
4. 답변 품질은 자연스럽되, 내부 용어가 사용자에게 노출되지 않아야 한다.
5. 기관 유형이 섞이면 안 된다. 특히 국가공기업/준정부기관 질문에 지방자치단체 기준이나 국가기관 표현이 부정확하게 섞이면 안 된다.
6. 지역업체 추천에서는 질문 품목과 무관한 기술개발제품/쇼핑몰 제품이 후보로 섞이지 않도록 계속 점검한다.
7. 사용자가 LLM 답변을 기다릴 때 UI가 멈춘 것처럼 보이지 않도록 진행상태 스트리밍을 제공한다.

## 최근 커밋 연혁

- `3bac74c` `Bust UI cache for streaming client`
  - `frontend/index.html`에서 `app.js?v=20260511-stream`을 사용해 브라우저 캐시로 예전 JS가 남는 문제를 방지.
- `2afa268` `Add chat progress streaming`
  - `/chat/stream` SSE endpoint 추가.
  - 프런트가 POST 스트림을 읽어 진행 문구를 실시간 갱신.
  - 실패 시 기존 `/chat` JSON endpoint로 fallback.
  - 현재는 token streaming이 아니라 progress-event streaming + final-answer 방식.
- `6460f72` `Skip writer on model fallback answers`
  - Gemini 503 등 model-error fallback 답변이 이미 사용자 노출용으로 정리된 경우 natural writer를 다시 태우지 않도록 조정.
  - notebook/general fallback 경로의 15초대 응답을 대체로 9~11초대로 줄임.
- `cc41170` `Polish grounded fallback basis wording`
  - 사용자 노출 문구에서 내부 DB/근거카드/기술명 느낌을 줄이는 후속 문구 정리.
- `5d61d03` `Clean user-facing fallback wording`
  - `내부 DB 사전조회`, `Gemini`, `fallback`, `업체 API` 등 내부 운영 표현 노출을 줄임.
- `bf9a991` `Fix public corporation agency guidance`
  - 공기업/준정부기관 질문에서 국가기관 표현으로 답하는 문제 수정.
  - 공공기관운영법, 공기업·준정부기관 계약사무규칙, 자체규정 확인 중심으로 답변.
- `aa8f2c9` `Sync advisor quality and routing updates`
  - 낮/사무실 작업분과 서버 변경사항을 정리해 GitHub main에 통합.

## 2시간 서버 QA 결과

실행 위치:

- 서버: `/opt/advisor`
- 결과 파일:
  - `/opt/advisor/artifacts/qa/server_toolmix_2h/toolmix_2h_20260511_031229.json`
  - `/opt/advisor/artifacts/qa/server_toolmix_2h/toolmix_2h_20260511_031229.md`

요약:

- 총 564건
- HTTP ok: 564건
- 평균 응답시간: 약 6,655ms
- p50: 약 6,149ms
- 최대: 약 15,503ms
- 30초 초과: 0건
- 15초 초과: 10건
- 대부분 `general_notebook_45m` 계열에서 15초 안팎 지연 발생
- warning 190건은 상당수가 공백/동의어 기반 false positive
  - 예: `분리 발주` vs `분리발주`
  - 예: `부당한 제한` vs `부당제한`
  - 예: `보안용 카메라` vs `보안용카메라`

실제 문제로 판단해 수정한 항목:

- 공기업/준정부기관 질문에서 국가기관 문구가 섞임.
- 사용자 답변에 내부 운영 표현이 보일 수 있는 문구가 일부 남아 있었음.
- model-error fallback 답변에 natural writer가 다시 붙으면서 일부 응답이 불필요하게 길어짐.

확인된 금지/내부 표현:

- QA 답변에서 다음 표현은 최종적으로 실제 노출 문제가 없는 것으로 확인됨.
  - `재제조토너`
  - `패키지소프트웨어개발및도입서비스`
  - `컴퓨터지원제조소프트웨어`
  - `source map`
  - `소스맵`
  - `자료 출처`
  - `dataStore`
  - `resolved_value`
  - `업체 API`

## LLM 도구호출 중단 관련 현재 이해

- `LLM_TOOL_LOOP_ENABLED=false`가 LLM 내부 도구호출 중단 설정으로 사용된다.
- 현재 운영 의도는 LLM이 자체 tool loop를 돌며 외부/내부도구를 계속 호출하지 않게 하는 것.
- 챗봇 서버는 자체 내부 DB와 업체자료를 먼저 조회하고, 필요한 경우 그 요약카드/근거카드를 LLM에 넘긴다.
- LLM 개입 경로는 대체로 `grounded single-pass LLM` 또는 natural writer 성격이다.
- fast-path로 자체 답변이 가능한 경우는 LLM 본문 생성을 쓰지 않고 deterministic/template 답변을 낸다.

## 답변 생성 구조 메모

현재 큰 흐름:

1. 질문/기관유형 입력
2. intent/routing 및 fast-path 판단
3. 내부 법령/행정규칙/매뉴얼/업체 자료 조회
4. 충분하면 서버 템플릿/구조화 답변 생성
5. 자연어 보강이 필요하면 LLM에 근거카드와 요약자료를 같이 전달
6. LLM 도구호출 없이 한 번만 답변 생성
7. 후처리/금지표현 검사
8. 응답 메타데이터와 QA 로그 저장

주의:

- 기존의 티어 분류 체계를 메인 로직처럼 설명하면 안 된다.
- 현재 사용자가 중요하게 보는 것은 “답변수행계획/라우팅/근거수집 후 어떤 답변 경로로 갈지”이다.
- 티어는 일부 메타데이터나 fast-path 설명에 남아 있지만, 앞으로 문서화/설명에서는 답변수행계획 중심으로 표현하는 것이 맞다.

## UI 스트리밍 작업 상태

구현된 것:

- 서버: `POST /chat/stream`
- 방식: SSE progress events
- 최종 답변: 기존 `/chat`과 같은 JSON을 `final` event로 반환
- 프런트: `fetch()` + `ReadableStream`으로 SSE 직접 파싱
- fallback: `/chat/stream`이 없거나 불완전하면 기존 `/chat`으로 전환

실제 서버 테스트:

- 질문: `CCTV 부산 지역업체 추천해줘`
- 기관유형: `local_government`
- 진행 이벤트:
  - 질문 접수
  - 질문 의도와 기관 유형 확인
  - 초고속 지역업체 검색
  - 법령 인용 검증
- 최종 응답: 약 2.9초
- 후보 카운트:
  - 조달등록 부산업체: 19
  - 종합쇼핑몰 등록 후보: 9
  - 정책기업 태그 확인: 5
  - 혁신제품: 0
  - 기술개발제품: 0

또 다른 서버 테스트:

- 질문: `부산 공공기관이 보안용카메라를 구매할 때 지역업체 우선 검토가 가능한가요?`
- 기관유형: `public_corporation`
- 최종 응답: 약 6.5초
- `model_selected`: `practice_manual_fast_gate`
- `tool_call_count`: 0

남은 점:

- 지금은 답변 본문 token streaming이 아니다.
- 실제로 한 문장씩 표시하려면 LLM 호출부를 stream generation 기반으로 더 깊게 바꿔야 한다.
- 우선은 사용자가 기다리는 동안 처리상태가 보이도록 하는 1차 UX 개선이다.

## 사무실에서 이어받는 절차

사무실 PC에서:

```powershell
cd "C:\dev\busanproduct-advisor\메뉴얼 제작"
git fetch origin
git checkout main
git pull --ff-only origin main
git log --oneline -5
git status --short --branch
```

서버 상태 확인:

```powershell
curl http://49.50.133.160:8001/version
```

UI 확인:

```text
http://49.50.133.160:8001/ui/
```

## 다음 작업 후보

우선순위 높은 순서:

1. 답변 품질 QA 계속
   - 지역업체 추천에서 질문 품목과 무관한 후보가 섞이는지 확인.
   - 국가공기업/준정부기관, 지방공사·공단, 출자출연기관, 지자체 간 법령 기준이 섞이지 않는지 확인.
   - `근거`, `검토`, `가능성`, `별도 확인` 문장이 너무 딱딱하거나 반복적인지 확인.
2. natural writer 프롬프트 개선
   - LLM은 새 사실을 만들지 않고 서버 근거카드 안에서 문장만 자연스럽게 다듬도록 제한.
   - 15초 timeout은 유지하되, 빠른 fallback이 가능해야 한다.
3. 후보 필터링 개선
   - 품목별로 쇼핑몰/기술개발제품/혁신제품 후보가 불필요하게 붙는 조건을 재검토.
   - 특히 `컴퓨터`, `CCTV`, `전기공사`, `청소용역`, `인쇄물`, `소프트웨어` 등 다양하게 테스트.
4. UI 개선
   - 현재 progress streaming은 완료.
   - 다음은 답변 영역 레이아웃, 후보표/근거/주의사항 구획 정리.
   - 필요하면 token streaming은 별도 단계로 설계.
5. 계측 고도화
   - 카드 생성 시간
   - Vertex/internal DB 검색 시간
   - LLM 생성 시간
   - natural writer 시간
   - 최종 후처리 시간
   - 위 항목을 답변 메타데이터와 QA 로그에서 더 쉽게 비교 가능하게 정리.

## 안전 메모

- `.env`와 실제 API key는 Git에 올리지 않는다.
- 서버 접속 비밀번호, OpenAI/Gemini 키, 공공데이터 키는 문서에 적지 않는다.
- QA artifact에는 답변 내용이 포함될 수 있으므로 공개 저장소에 올릴 때는 민감정보가 없는지 확인한다.
- 현재 `production_deployment`는 계속 `HOLD`다.

