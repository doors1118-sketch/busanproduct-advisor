# 부산 공공조달 AI 챗봇 — 운영 배포 직전 최종 준비 상태 (Pre-Deployment Readiness)

본 문서는 실제 운영 배포를 가동하기 전 마지막 시스템/보안 정합성을 점검한 문서입니다.
*(※ 이 문서는 배포 명령어가 아니며, 어떠한 배포나 설정 변경, systemctl 명령도 아직 실행되지 않았습니다.)*

## 1. Password Rotation 상태 업데이트

NCP 서버 접속 패스워드 로테이션 보안 조치에 대한 현재 상태입니다. (※ 비밀번호 값 절대 출력 금지)

```json
{
  "password_rotation_required": true,
  "password_rotation_completed": true
}
```

## 2. Frontend 정적 파일(StaticFiles) 제공 여부 확인

프런트엔드 정적 파일(`frontend/`)을 운영 환경에서 제공하기 위한 권장 선택지입니다.

- **A안**: FastAPI StaticFiles로 `/ui` 제공 (현재 1차 MVP 내부 제한 공개용 추천)
- **B안**: Nginx static + `/api` reverse proxy (정식 운영 시 추천)
- **C안**: `python http.server` (테스트 전용, 운영 비추천)

이번 1차 제한 공개에서는 **A안(FastAPI StaticFiles)** 을 권장합니다.

### 2.1 FastAPI StaticFiles 구현 여부 확인

현재 `app/api_server.py` 내부의 StaticFiles 마운트 구현 상태 점검 결과입니다.

```json
{
  "frontend_static_serving": "exists",
  "frontend_path": "/ui"
}
```
*(※ 본 단계에서 FastAPI StaticFiles 연동이 성공적으로 구현 및 테스트 완료되었습니다.)*

## 3. 운영 서비스 설계 확정

운영 배포 시 서비스 및 포트 구성 방안입니다.

```json
{
  "streamlit_service": "keep",
  "streamlit_port": 8502,
  "fastapi_service": "add",
  "fastapi_bind": "127.0.0.1:8001",
  "frontend_serving_recommended": "FastAPI StaticFiles /ui for MVP",
  "nginx_required_now": false
}
```

## 4. 최종 Pre-Deployment Checklist

배포 전 시스템 및 프로세스의 안정성 점검 표입니다.

| 점검 항목 | 상태 | 비고 |
|---|---|---|
| NCP E2E PASS | **PASS** | 기준선 통과 |
| FastAPI API smoke PASS | **PASS** | `/health`, `/version`, `/rag/status`, `/chat` 정상 |
| Frontend MVP PASS | **PASS** | API 연동 및 UI 동작 정상 |
| QA 30개 PASS | **PASS** | Critical safety failure 0건 |
| Security cleanup PASS | **PASS** | 하드코딩된 비밀번호 제거 및 `.gitignore` 보강 완료 |
| NCP root password rotation 완료 | **완료** | 사용자가 변경 수행 완료 |
| 배포 대상 commit hash 확정 필요 | **대기중** | 승인 시 확정 예정 |
| rollback 대상 commit hash 확정 필요 | **대기중** | 승인 시 확정 예정 |
| FastAPI service 등록 방식 결정 필요 | **대기중** | 승인 시 확정 예정 |
| frontend static serving 방식 결정 완료 | **완료** | FastAPI StaticFiles /ui로 확정됨 |
| 운영 승인자 최종 확인 필요 | **대기중** | 승인 대기 중 |
| Production deployment=HOLD 유지 | **유지 중** | 배포 승인 시 해제 여부 결정 |

## 5. 운영 배포 전 남은 승인 항목 (TODO)

배포 실행 전 관리자가 직접 최종 승인해야 하는 남은 안건들입니다.

- [ ] 배포 대상 commit hash 최종 확정
- [ ] rollback 대상 commit hash 최종 확정
- [ ] FastAPI service unit 실제 생성 승인
- [ ] frontend serving 방식 승인 (StaticFiles `/ui` 코드 추가 승인 여부 등)
- [ ] 최종 운영 smoke test 승인
- [ ] Production deployment HOLD 해제 여부 승인

---

```json
{
  "pre_deployment_readiness_created": true,
  "technical_ready": true,
  "password_rotation_required": true,
  "password_rotation_completed": true,
  "deployment_approved": false,
  "production_deployment": "HOLD",
  "recommended_next_step": "Decide frontend serving mode and approve parallel deployment execution"
}
```
