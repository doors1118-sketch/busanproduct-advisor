# Handoff Context - 2026-05-12

이 문서는 2026-05-13 사무실 작업 재개용 요약이다.
민감정보(API key, SSH password, 서버 비밀번호, 토큰)는 포함하지 않는다.

## 현재 동기화 상태

- GitHub `main`: `23735c9 Improve procurement legal answer gates`
- 로컬 `main`: `23735c9`
- 서버 `/opt/advisor`: `23735c9`
- 서버 서비스: `busan-advisor-pilot` active 확인
- 서버 `/version` 확인값:
  - `commit_hash`: `23735c9`
  - `model_primary`: `gemini-2.5-flash`
  - `model_fallback`: `gemini-2.5-flash`
  - `prompt_mode`: `dynamic_v1_4_4`
  - `model_routing_mode`: `risk_based`
  - `production_deployment`: `HOLD`

## 오늘 반영한 주요 커밋

- `c47fdc2` `docs: document chatbot architecture and answer flow`
  - 챗봇 아키텍처, 질문 처리 흐름, LLM/RAG/내부DB 역할 문서화.
  - 파일: `docs/CHATBOT_ARCHITECTURE_AND_ANSWER_FLOW_20260512.md`
- `23735c9` `Improve procurement legal answer gates`
  - 오늘 사용자 평가/모범답안 기준으로 수의계약 관련 결정형 답변과 fast answer 보강.
  - GitHub push 완료.
  - 서버 `/opt/advisor` 동기화 및 서비스 재시작 완료.

## 반영한 답변 품질 보강 범위

1. **VAT 포함/제외 질문**
   - 수의계약 한도 판단 기준이 `부가가치세 제외 추정가격`임을 직접 답변.
   - 엉뚱하게 공사/물품 한도를 나열하던 흐름을 deterministic gate로 보강.

2. **여성기업 SW 4,500만원**
   - VAT 제외 추정가격 5천만원 기준.
   - SW 영향평가, 과업내용 확정 심의, 보안성 검토, 디지털서비스몰/종합쇼핑몰 확인, 여성기업 확인서, SW사업자 신고확인서, 직접생산확인증명서 확인 흐름 추가.

3. **장애인기업 용역 7,000만원**
   - 정책기업이라도 1인 견적은 추정가격 5천만원 이하가 핵심이라는 설명 보강.
   - 7천만원은 1인 지정 곤란, G2B 2인 이상 견적/부산 지역제한/평가항목 대안으로 유도.

4. **사회적협동조합 5천만원**
   - 사회적협동조합 인가만으로 부족하다는 점 명시.
   - 취약계층 고용비율 30% 이상, 수의계약 대상 확인서, 직접생산/직접공급, 가격 적정성, 내부 한도관리 체크 추가.

5. **혁신제품 금액 제한**
   - 혁신제품은 일반 소액수의 한도와 별개로 검토 가능하되, 지정 유효기간/제품명/모델명/규격 일치/조달등록/내부심사 확인 필요.
   - 지방계약 기준 근거를 `지방계약법 시행령 제25조제1항제8호다목` 및 `제30조제1항제1호` 연결 구조로 보강.

6. **공기업/보안용카메라/보안용역**
   - 국가공기업/준정부기관 질문에서 지방계약법 기준을 그대로 가져오지 않도록 안내.
   - 보안용카메라(CCTV)는 물품, 정보통신공사, SW, 경비용역 범위를 분리해서 검토하도록 fast practice answer 보강.
   - 경비·무인경비 용역은 경비업 허가와 과업 범위를 먼저 보도록 보강.

## 검증 결과

로컬 테스트:

```powershell
python -m pytest tests/test_deterministic_legal_answer_gate.py tests/test_grounded_fast_path.py tests/test_query_gateway.py
```

결과:

- `205 passed`
- warning 1건: google genai types 관련 deprecation warning

서버 반영:

- `/opt/advisor`에서 `git reset --hard origin/main`
- `systemctl restart busan-advisor-pilot`
- `systemctl is-active busan-advisor-pilot` 결과: `active`
- 서버 `pytest`는 설치되어 있지 않아 원격 pytest는 실행 불가: `/usr/bin/python3: No module named pytest`
- `scripts/server_preflight.py` 결과: `warning`
  - 데이터 파일, 서비스 파일, Gemini key, Chroma 경로는 OK
  - `ADMIN_HEALTH_TOKEN` 미설정으로 warning: localhost-only admin health

서버 smoke 확인 질문:

- `수의계약 한도를 계산할 때 부가가치세를 포함해야 하나요, 제외해야 하나요?`
  - `model_selected`: `deterministic_internal_law_db`
  - `model_decision_reason`: `vat_threshold_basis_fast_answer`
- `사회적협동조합 제품 5천만원 1인 수의계약 검토`
  - 취약계층 고용비율/확인서 요건 포함 확인
- `4,500만 원 상당의 소프트웨어를 부산 소재 여성기업으로부터 1인 수의로 사고 싶습니다. 절차가 어떻게 되나요?`
  - SW 사전 행정절차/쇼핑몰/여성기업 확인 절차 포함 확인
- `부산에 본사를 둔 장애인기업과 7,000만 원 규모의 용역 계약을 1인 수의로 진행할 수 있나요?`
  - 1인 지정 곤란 및 2인 이상 견적 대안 포함 확인
- `혁신제품으로 지정된 부산 기업 제품은 금액 제한 없이 1인 수의계약이 가능한가요?`
  - 혁신제품 법령 근거와 지정/규격 확인 체크 포함 확인

## 내일 이어서 볼 것

1. **자연어 품질**
   - deterministic answer가 정확해졌지만 일부 답변은 여전히 딱딱하다.
   - Natural writer가 적용된 답변과 미적용 답변을 나눠 비교할 것.

2. **LLM 질문 맥락 분석 강화**
   - 현재 LLM은 상시 1차 intent analyzer가 아니라 조건부 route adjudicator에 가깝다.
   - `LLM Context Analyzer`를 앞단에 추가할지 설계 필요.
   - 단, 법령 수치와 최종 가능/불가 판단은 내부 DB/rule layer가 계속 담당해야 한다.

3. **Vertex grounding 확인**
   - 코드상 Vertex는 model provider로는 사용 가능하지만, Vertex datastore/RAG corpus를 Gemini 요청에 붙이는 연결은 확인되지 않았다.
   - 실제 Vertex 콘솔 자료와 운영 request payload를 비교해야 한다.

4. **QA 확장**
   - 오늘 반영한 대표 질문 외에 다음 유형 추가 테스트:
     - 특허 2억원 수의계약
     - 학술연구용역 3천만원 대학 부설 연구소
     - 긴급 재난복구 1억원 공사
     - 동일 품목 2천만원씩 3회 분할발주
     - 공기업/준정부기관과 지방공기업 구분 질문

## 사무실에서 시작 명령

```powershell
cd "C:\dev\busanproduct-advisor\메뉴얼 제작"
git fetch origin
git checkout main
git pull --ff-only origin main
git log --oneline -5
git status --short --branch
curl http://49.50.133.160:8001/version
```

기대 상태:

- local branch: `main`
- latest commit: `23735c9` 또는 그 이후 handoff 문서 커밋
- server `/version.commit_hash`: `23735c9`
- `production_deployment`: `HOLD`

## 안전 메모

- `.env`, 실제 API key, SSH password, pilot auth 값은 Git에 올리지 않는다.
- 서버에는 untracked shell profile/cache류 파일과 `scratch/run_server_answer_quality_qa.py`가 있었으나 tracked 변경은 없었다.
- 오늘 서버 동기화는 tracked 파일을 `origin/main`으로 맞춘 것이다.
