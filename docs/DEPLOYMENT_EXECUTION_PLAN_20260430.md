# 부산 공공조달 AI 챗봇 — 배포 실행 계획서 (Deployment Execution Plan)

본 문서는 실제 운영 배포를 진행하기 위한 방식, 명령어, 롤백 절차 및 Smoke Test 시나리오를 구체화한 가이드라인입니다. **이 문서는 운영자 최종 승인 전 검토 목적으로 작성되었으며, 승인 시 본 절차에 따라 배포를 실행합니다.** (현재 상태: `Production deployment=HOLD`)

---

## 1. 배포 방식 결론

- **추천 배포 방식**: **A안 — 기존 Streamlit UI 유지 + 신규 FastAPI/Frontend 병행 배포**
- **명시 사항**:
  - 기존 Streamlit 서비스(`law-chatbot.service`)는 유지하여 하위 호환성과 기존 사용자 접근성을 보장합니다.
  - 신규 FastAPI API 레이어는 별도의 백엔드 서비스로 추가 구동됩니다.
  - 신규 Frontend MVP는 FastAPI와 연동되는 별도 정적 경로를 통해 제공됩니다.
  - 현재는 정식 전면 배포가 아닌 "내부 제한 공개 및 병행 운영 방식"입니다.
  - `Production deployment`는 안정성 최종 확인 전까지 `HOLD`를 유지합니다.

---

## 2. 서비스 구성안

**현재 구성:**
- Streamlit UI: port `8502`
- FastAPI API: port `8001`
- Frontend static: `frontend/` 디렉터리 내 파일들

**권장 배포 구성:**
- **FastAPI**: `127.0.0.1:8001` 포트에서 실행 (외부망 직접 노출 차단)
- **Frontend MVP**: 배포 초기(MVP 단계)에는 FastAPI의 `StaticFiles` 라우팅을 활용하거나 별도 테스트용 Static Server 구동.
- **정식 운영**: Nginx Reverse Proxy를 도입하여 정적 파일은 Nginx가 직접 서빙하고, `/api` 경로는 `127.0.0.1:8001`로 포워딩하는 구조를 권장합니다.

---

## 3. FastAPI systemd 서비스 초안

신규 API 백엔드 안정화를 위해 systemd 등록을 권장합니다.
*(※ 아래 명령 및 설정은 운영자 승인 후에만 반영한다. 현재 단계에서는 실행 금지.)*

**파일 위치 예시**: `/etc/systemd/system/busan-advisor-api.service`

```ini
[Unit]
Description=Busan Procurement AI Chatbot - FastAPI API Service
After=network.target

[Service]
User=root
WorkingDirectory=/opt/busan
EnvironmentFile=/opt/busan/.env
ExecStart=/opt/busan/.venv/bin/python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5
StandardOutput=append:/var/log/busan_fastapi_out.log
StandardError=append:/var/log/busan_fastapi_err.log

[Install]
WantedBy=multi-user.target
```
*(주의: 본 서비스 파일 내에는 어떠한 API Key나 `.env` 평문 값을 하드코딩하지 않습니다.)*

---

## 4. Frontend 서빙 선택지 (비교표)

| 선택지 | 장점 | 단점 | 추천 여부 |
|---|---|---|---|
| **A. FastAPI StaticFiles** | 구조가 단순하며, API 서버가 정적 파일까지 원스톱으로 제공하므로 MVP 배포가 매우 빠름 | 트래픽 증가 시 FastAPI 스레드를 소모하여 병목이 될 수 있음 | **MVP 단계 추천** |
| **B. Nginx static + /api proxy** | 정적 리소스 로딩이 매우 빠르며, 로드밸런싱 및 SSL 엣지 처리에 가장 적합함 | Nginx 설정 추가 작업 및 파일 권한 관리가 필요함 | **정식 운영 추천** |
| **C. python http.server** | 개발 및 로컬 테스트 목적 시 명령 한 줄로 구동 가능 | 보안성, 성능, 동시성 처리가 극히 취약하여 프로덕션 용도로 부적합 | 비추천 (테스트 전용) |

---

## 5. 배포 전 필수 조건 (체크리스트)

배포 실행 전 다음 항목이 모두 확인되어야 합니다.

- [ ] **NCP root password rotation 완료** (운영 필수 사항)
- [ ] 운영 배포 최종 승인자 확인 (결재 및 인가 기록)
- [ ] 배포 대상(Target) commit hash 확정
- [ ] Rollback 대상(이전 안정 버전) commit hash 확정 기록
- [ ] `.env` 및 API key 세팅 무결성 확인 (문서/로그에 값 출력 여부 점검)
- [ ] 기존 운영 RAG 데이터 정상 상태 확인 (`/rag/status` PASS)
- [ ] 로컬 또는 스테이징 단계의 `/chat` Smoke Test 완료 (PASS)
- [ ] 기존 운영 Streamlit UI 서비스 정상 구동 확인
- [ ] 문서화된 QA 30개 시나리오 중 최소 필수 10개 시나리오 점검 완료
- [ ] `production_deployment=HOLD` 플래그 유지 상태 재확인

---

## 6. 배포 실행 절차 (Draft)

*(※ 아래 절차는 운영자 승인 후 문서에 따라 순차적으로 수행한다. 현재 임의 실행 금지.)*

1. **현재 운영 상태 기록**: 진행 전 시스템 상태(commit hash, 로그) 스냅샷.
2. **root password rotation 확인**: 보안상 완료 여부 체크.
3. **코드 최신화**: 운영 대상 commit checkout 또는 `git pull` 수행.
4. **의존성 설치**: `pip install -r requirements.txt` (필요 시).
5. **RAG status 확인**: ChromaDB 데이터 무결성 체크.
6. **FastAPI service 등록 및 실행**: systemd unit 파일 등록 및 `systemctl start busan-advisor-api`.
7. **Frontend 정적 경로 확인**: FastAPI StaticFiles 또는 Nginx 등 결정된 서빙 경로 오픈.
8. **Smoke test**: 본 문서 7항의 검증 시나리오 실행.
9. **제한 공개 승인**: 문제 없을 시 제한적 타겟(내부 IP 등) 대상 서비스 URL 오픈 및 `production_deployment` HOLD 해제(승인 시).
10. **이상 발생 시 Rollback**: 장애 징후 시 즉각 8항에 따른 롤백 가동.

> **⚠️ 절대 금지 명령:**
> - `git reset --hard` 금지
> - `rm -rf` 를 이용한 수동 파일 임의 삭제 금지
> - 기존 운영 DB 및 ChromaDB 데이터 삭제 금지
> - ChromaDB Symlink 우회 금지

---

## 7. 운영 Smoke Test 시나리오

배포 직후 서비스 정상 작동 여부를 판단하기 위한 필수 테스트 항목입니다.

- **GET `/health`**: `status=ok` 확인
- **GET `/version`**: 배포된 commit hash 일치 확인
- **GET `/rag/status`**: laws, manuals, innovation 콜렉션 각각 `SUCCESS` 확인
- **POST `/chat`**: payload `{"message": "CCTV 부산 업체 추천해줘", "agency_type": "local_government", "history": []}` 전송 후 테이블 소스 정상 렌더링 확인
- **기존 Streamlit UI 확인**: 브라우저로 Streamlit UI 포트 접속 여부 확인
- **Frontend 접속**: 브라우저로 Frontend 정적 페이지 오픈 및 화면 노출 확인
- **배포 플래그**: `production_deployment` 값이 HOLD 또는 승인 후 지정된 값으로 반환되는지 확인

---

## 8. 롤백(Rollback) 요약

배포 중 문제 발생 시 `docs/ROLLBACK_PLAN_20260430.md` 지침에 따라 즉각 복구합니다.

- **Rollback Trigger**: 시스템 크래시, Critical Safety Error 발견, API 500 오류 반복 등.
- **Rollback 대상 Commit**: 배포 전 기록된 최후 안정화 버전 Hash.
- **서비스 중지/재시작**: 반드시 관리자 승인 후 `systemctl stop/start` 진행.
- **Rollback 후 확인**: RAG/Chroma DB 연결이 이전 상태로 정상 복구되었는지 7항의 Smoke Test를 재수행.

---

```json
{
  "deployment_execution_plan_created": true,
  "recommended_deployment_mode": "parallel_deployment",
  "streamlit_existing_service": "keep",
  "fastapi_service": "add",
  "frontend_static": "add",
  "password_rotation_required": true,
  "password_rotation_completed": false,
  "deployment_approved": false,
  "production_deployment": "HOLD"
}
```
