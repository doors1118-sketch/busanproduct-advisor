# 부산지역상품 구매 확대 지원 도우미(AI 챗봇) — 배포 후보 패키지

- **프로젝트명**: 부산지역상품 구매 확대 지원 도우미
- **목적**: 조달 수요기관 담당자의 지역업체 계약 검토 지원
- **배포 후보 상태**: RELEASE CANDIDATE
- **운영 배포 상태**: HOLD
- **배포 승인 여부**: false
- **작성일**: 2026-04-30
- **기준 commit hash**: febecef4fb78a13fa422f4d4f0be8a1e2eadf5ab
- **NCP E2E PASS 기준선 문서 링크**: [docs/NCP_E2E_BASELINE_20260429.md](NCP_E2E_BASELINE_20260429.md)
- **운영 배포 체크리스트 링크**: [docs/DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)
- **QA 시나리오 링크**: [docs/QA_SCENARIOS_20260429.md](QA_SCENARIOS_20260429.md)
- **QA 실행 요약 링크**: [docs/QA_RUN_SUMMARY_20260429.md](QA_RUN_SUMMARY_20260429.md)

---

## 배포 대상 구성

본 패키지는 아래와 같이 기존 Streamlit UI와 신규 FastAPI 기반 백엔드 및 Frontend 정적 파일이 병행되는 아키텍처를 가집니다.
(※ 주의: 운영 배포 시 FastAPI와 Frontend 정적 파일 서빙 방식을 별도 결정해야 하며, 현재는 로컬 테스트 명령어 기준입니다.)

- **기존 Streamlit UI**
  - **port**: 8502
  - **기존 서비스명**: law-chatbot.service
  - **상태**: 유지
- **신규 FastAPI API**
  - **port**: 8001
  - **실행 명령**: `python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8001`
- **신규 Frontend MVP**
  - **정적 파일**: `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`
  - **로컬 테스트 명령**: `python -m http.server 8503 --directory frontend`

---

## 검증 기준선 요약

| 항목 | 상태 | 기준 |
|---|---|---|
| NCP E2E | PASS | py_compile, RAG, staging, TC7/G-RT |
| laws RAG | SUCCESS | 808 docs |
| manuals RAG | SUCCESS | split_collections, 3,361 docs |
| innovation index | SUCCESS | 771 products |
| staging verification | PASS | 4/4 |
| TC7/G-RT | PASS | 8/8 |
| API smoke | PASS | /health, /version, /rag/status, /chat |
| QA 30개 | PASS | critical safety failure 0 |
| Frontend MVP | PASS | API 연동, safety badge, metadata whitelist |
| Production deployment | HOLD | 배포 미승인 |

---

## API Endpoint 요약

| endpoint | method | 목적 | 운영 전 확인 |
|---|---|---|---|
| `/health` | GET | API 상태 확인 | status=ok |
| `/version` | GET | commit/model/prompt 상태 | commit hash 일치 |
| `/rag/status` | GET | RAG/Index 상태 | laws/manuals/innovation SUCCESS |
| `/chat` | POST | 챗봇 질의 | safety metadata 포함 |

**POST /chat 응답 필수 필드**:
- `answer`
- `candidate_table_source`
- `legal_conclusion_allowed`
- `contract_possible_auto_promoted`
- `forbidden_patterns_remaining_after_rewrite`
- `final_answer_scanned`
- `sensitive_fields_detected`
- `model_selected`
- `model_decision_reason`
- `latency_ms`
- `production_deployment`

---

## Safety 기준

운영 배포 시 다음의 Safety 제약이 반드시 만족되어야 합니다.

- `candidate_table_source` 허용값: `server_structured_formatter` 또는 `none`
- `candidate_table_source="llm"`이면 배포 금지
- `legal_conclusion_allowed`는 직접 근거가 없을 시 강제 `false`
- `contract_possible_auto_promoted`는 무조건 `false`
- `forbidden_patterns_remaining_after_rewrite`=`[]` (빈 배열) 필수
- `final_answer_scanned=false`인데 전체 상태 PASS 처리 금지
- 시스템 Traceback 내역 등 raw API error 사용자 노출 엄격히 금지
- 사업자등록번호 / 대표자명 / API key / `.env` 환경변수의 원문 노출 금지
- `Production deployment`는 별도 운영 책임자의 최종 배포 승인 전까지 `HOLD`를 유지함

---

## 운영 전 필수 조치

**배포를 진행하기 전에 반드시 수행해야 하는 항목입니다.**

- NCP root password rotation 완료 (필수)
- 최종 운영 승인자 확인 및 배포 결재
- 운영 대상 commit hash 확정
- rollback 대상(기존 안정 버전) commit hash 기록
- 현재 운영 중인 Streamlit 서비스(law-chatbot.service) 상태 확인
- FastAPI 서비스 실행 방식 결정
  - (대안) systemd unit 신규 생성 여부
  - (대안) 기존 Nginx 등 reverse proxy 경로 구성
- frontend 정적 파일 서빙 방식 결정
  - (대안) FastAPI StaticFiles 모듈 사용
  - (대안) Nginx 등 전용 웹서버 사용
  - (대안) 별도 static server
- 배포 직전 `/health`, `/version`, `/rag/status`, `/chat` 엔드포인트 운영 Smoke Test 수행
- 기존 확보된 QA 시나리오 최소 10개 이상 재실행(Smoke 검증)
- `production_deployment=HOLD` 해제 여부는 위 항목이 모두 완료된 이후 별도 승인을 거쳐 결정

---

## 배포 금지 조건

아래 항목 중 단 하나라도 발생하는 경우, 즉각 배포 프로세스를 중단해야 합니다.

- NCP E2E FAIL 또는 DEGRADED 원인 미해소 상태
- FastAPI API smoke FAIL
- Frontend smoke FAIL
- 대표 QA에서 Critical safety failure 발생
- `forbidden_patterns_remaining_after_rewrite` 필드가 빈 배열 `[]`이 아님
- `legal_conclusion_allowed` 필드가 부적절하게 `true`로 설정됨
- `contract_possible_auto_promoted` 필드가 `true`로 발생됨
- `candidate_table_source`가 비인가 값인 `"llm"`으로 반환됨
- 사용자의 프런트엔드 화면에 Raw API error나 서버 Traceback이 노출됨
- 사업자번호 등 필터링되지 않은 민감정보가 응답 내에 노출됨
- `.env` 내 비밀키나 API Key가 화면이나 응답 Payload에 평문 출력됨
- NCP root password rotation(패스워드 변경)이 완료되지 않음
- Rollback 계획 및 절차가 문서화 또는 수립되어 있지 않음
- `Production deployment` 필드가 HOLD가 아닌 배포 모드 상태인데 배포 승인 공식 기록이 부재함

---

## 롤백 및 런북 (참고문서)

상세 운영 가이드 및 장애 시 롤백 절차는 다음 별도 문서를 참조하십시오.
- **Rollback Plan**: [docs/ROLLBACK_PLAN_20260430.md](ROLLBACK_PLAN_20260430.md)
- **Operations Runbook**: [docs/OPERATIONS_RUNBOOK_20260430.md](OPERATIONS_RUNBOOK_20260430.md)

---

```json
{
  "release_candidate_created": true,
  "deployment_approved": false,
  "production_deployment": "HOLD",
  "ncp_e2e_status": "PASS",
  "api_smoke_status": "PASS",
  "frontend_mvp_status": "PASS",
  "qa_status": "PASS",
  "security_cleanup_status": "PASS",
  "password_rotation_required": true,
  "password_rotation_completed": false,
  "next_step": "Obtain operational approval and complete password rotation before deployment"
}
```
