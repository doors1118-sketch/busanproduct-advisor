# 프런트엔드 MVP 구현 문서 (2026-04-29)

> **Production deployment: HOLD**

## 1. 파일 구조
이 MVP는 프레임워크 없는 순수 바닐라 HTML/CSS/JS로 작성되어 별도의 빌드 과정 없이 정적 서빙이 가능합니다.

- `frontend/index.html` : UI 레이아웃, 입력 폼, 메타데이터/답변/오류 표시 영역 정의
- `frontend/styles.css` : 컬러 시스템, 반응형 카드 UI, 안전 배지 및 로딩 스피너 디자인
- `frontend/app.js` : FastAPI 백엔드 연동, 안전 배지 로직, 에러 핸들링, 민감 정보 프런트엔드 레드액션(Redaction) 기능 포함
- `docs/FRONTEND_MVP_IMPLEMENTATION_20260429.md` : 현재 문서

## 2. 실행 방법

**A. FastAPI StaticFiles 서빙 (운영 MVP 권장 경로)**
```bash
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8001
```
접속: `http://127.0.0.1:8001/ui/`

**B. 로컬 정적 테스트 서버 실행 (개발용)**
```bash
python -m http.server 8503 --directory frontend
```
접속: `http://127.0.0.1:8503`

## 3. API Base URL 변경 방법
`frontend/app.js` 최상단에 상수로 정의되어 있습니다. 운영 배포 또는 다른 NCP 인스턴스 연동 시 아래 값을 수정하세요.
기본적으로 same-origin 호출을 수행하며 로컬 테스트 서버(8503) 시에는 8001로 우회합니다.
```javascript
const params = new URLSearchParams(window.location.search);
const API_BASE_URL = params.get("api") || (window.location.port === "8503" ? "http://127.0.0.1:8001" : "");
```

## 4. 화면 구성 및 Endpoint 연동
- **API 상태 영역 (상단):**
  - `/health` 호출 → 정상 시 녹색 뱃지 "OK" 표시
  - `/version` 호출 → 커밋 해시(앞 7자리) 파싱 표시
  - `/rag/status` 호출 → 모든 컬렉션 성공 시 "Ready", 지연/실패 시 "Degraded" 노란색 뱃지 표시
  - Deployment → 붉은색 "HOLD" 상시 표시
- **서비스 개요 영역:**
  - 챗봇의 기능과 구현 목적을 설명하는 안내 카드.
  - 조달 검토, 현행 법령 및 매뉴얼 활용, 지역업체 정보 제공에 대해 기술함.
  - 시스템의 결과가 법적 판단이나 계약 가능 여부를 맹목적으로 확정하지 않는다는 필수 안전 경고문을 고정 노출함.
- **입력 영역:**
  - 기관 유형 Dropdown (내부적으로 매핑된 한글 텍스트를 `/chat` 의 `agency_type` 파라미터로 전달)
  - 질문 텍스트박스
  - **질문 예시 영역**: 6개의 예시 질문 버튼 제공. 클릭 시 텍스트박스에 자동 입력되며 자동 전송은 수행하지 않음. 예시 문구는 단정적인 계약 가능 여부를 내포하지 않도록 엄격히 관리됨.
- **결과 표시 영역:**
  - `POST /chat` 호출 결과 렌더링. `marked.js`를 이용해 응답 텍스트를 Markdown으로 변환하여 표(Table)를 포함해 가독성 있게 표시합니다.

## 5. Safety Badge (안전 상태 배지) 설명
백엔드 API 응답의 메타데이터를 UI에 동적으로 렌더링합니다.
- `⚠️ 법적 결론 유보` : `legal_conclusion_allowed = false`
- `🔒 계약 가능 자동확정 없음` : `contract_possible_auto_promoted = false`
- `✅ 금지표현 검사 통과` : `forbidden_patterns_remaining_after_rewrite` 배열이 비어있음
- `📊 서버 생성 후보표` : `candidate_table_source = "server_structured_formatter"`
- `🛑 운영 배포 HOLD` : `production_deployment = "HOLD"`

## 6. 오류 / DEGRADED 표시 방식
- `API 503 / 429` (Gemini 리소스 고갈 오류) 또는 `DEGRADED` 플래그 수신 시:
  - 붉은색 시스템 에러 대신, 노란색 경고 창으로 우회 표시합니다.
  - **표시 문구:** "일부 외부 API 또는 데이터 조회가 지연되어 답변이 제한될 수 있습니다. 계약 전 관련 법령과 기관 내부 기준을 추가 확인하세요."
- `Timeout` (120초):
  - "응답이 지연되고 있습니다. 외부 API 또는 모델 응답 지연 가능성이 있습니다." 출력

## 7. 금지 UI 표현
프런트엔드 하드코딩 텍스트(UI 문구, 버튼, 툴팁 등)에는 **단정적 계약 허용 표현**을 일체 사용하지 않았습니다.
- **금지:** "수의계약 가능", "계약 가능", "바로 구매 가능" 등
- **허용 (적용됨):** "검토 결과", "참고용 도구", "자동 확정하지 않습니다", "확인 필요" 등

## 8. 보안 정책 (Frontend Redaction)
API에서 예기치 않게 노출될 수 있는 민감 정보를 브라우저 단에서도 2차 차단(Masking)하는 로직을 `app.js` 내에 구현했습니다 (`redactSensitiveInfo`).
- **사업자등록번호:** `xxx-xx-xxxxx` 패턴 검출 시 `[사업자번호 보호됨]` 치환
- **API Key/환경변수:** `AIza...`, `AKIA...`, `GEMINI_API_KEY=` 등 발견 시 `[API 키 보호됨]` 치환
- **Traceback:** `Traceback (most recent call last):` 등의 패턴 발견 시 `[시스템 오류 메시지 보호됨]` 치환

## 9. 다운로드 기능 및 법령 근거 정책
결과 화면에서 제공되는 데이터 다운로드 기능의 원칙은 다음과 같습니다.
- **답변 Markdown / 후보표 CSV 다운로드:** 시스템이 생성한 마크다운 답변 원문과, 파싱 가능한 표가 존재할 경우에 한정하여 후보표 CSV 다운로드를 지원합니다. CSV 다운로드 시에는 CSV Injection 방어를 적용하여 `=, +, -, @` 로 시작하는 셀은 수식 실행 방지를 위해 escape(`'`) 처리됩니다.
- **민감정보 보호:** 다운로드되는 모든 CSV 및 마크다운 파일은 사전에 사업자등록번호, API 키, 오류 메시지 등이 마스킹(redaction) 처리된 안전한 상태로 생성됩니다.
- **법령/행정규칙 근거 다운로드 사전 원칙 (향후 구현 예정):** 현재 `POST /chat` 응답에 `legal_basis` 등의 근거 필드가 미포함되어 있어 활성화되지 않았으나, 추후 지원 시 다음 원칙을 따릅니다.
  - 법령·행정규칙 전체 전문 다운로드를 금지하며, 답변에 사용된 **적용 조문/근거 조각만**을 대상으로 합니다.
  - 다운로드 파일에는 법령명, 조문번호, 조항, 출처, 기준일, relevance, supports_claims 여부만 포함합니다.
  - 직접적인 법령 근거가 없으면 `legal_conclusion_allowed = false`를 유지합니다.
  - 제공되는 모든 다운로드 자료는 참고용일 뿐, 계약 가능 여부를 확정하는 법적 판단 자료가 아님을 명시합니다.

## 10. Production Deployment = HOLD
현재 시스템은 로컬 및 개발 검증 환경이며, 운영 배포(`law-chatbot.service` 패치 및 운영 DB 변경)는 이뤄지지 않은 `HOLD` 상태입니다.

## 11. 다음 단계
- 프런트엔드 환경에서의 사용성 Smoke QA 완료
- 실제 운영 담당자에게 MVP 공유 후 피드백 수렴
- 최종 운영 승인(Deployment Approval) 완료 시 운영 배포 가이드에 따라 릴리스 진행
