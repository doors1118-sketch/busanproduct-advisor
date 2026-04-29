# 부산 공공조달 AI 챗봇 — 운영 배포 직전 최종 준비 상태 (Pre-Deployment Readiness)

본 문서는 운영 배포 직전의 시스템과 프로세스, 보안의 준비 상태를 요약한 최종 점검 결과입니다.
*(※ 이 문서는 배포 명령어가 아니며, 어떠한 배포나 설정 변경, systemctl 명령도 아직 실행되지 않았습니다.)*

## 1. 배포 준비 지표 요약

| 지표 (Metrics) | 상태 (Status) | 비고 |
|---|---|---|
| `technical_ready` | **true** | E2E, FastAPI, QA, Frontend, Security 모두 통과됨 |
| `password_rotation_pending` | **false** | 사용자가 NCP root 패스워드 변경을 완료함 |
| `deployment_approved` | **false** | 운영자 최종 배포 승인 미완료 |
| `production_deployment` | **HOLD** | 운영 서비스 진입 전까지 상태 유지 중 |

---

## 2. Frontend 정적 파일 제공 (StaticFiles) 구현 현황

현재 운영 권장 사항인 **FastAPI StaticFiles를 통한 `/ui` 경로 통합 제공 방식**에 대한 코드 구현 상태를 점검했습니다.

- **현재 구현 여부**: 미구현 (`frontend_static_serving: missing`)
- **원인**: `app/api_server.py` 내에 `StaticFiles` import 및 mount 로직이 아직 추가되지 않았습니다.
- **추천 변경 사항**: FastAPI 코드에 `app.mount("/ui", StaticFiles(directory="frontend", html=True), name="frontend")` 추가 및 `index.html` fallback 구현.
*(※ 본 단계에서는 구현을 보류하며, 별도 승인 후 코드 수정 예정입니다.)*

---

## 3. 운영 서비스 설계 및 배포 포트 확정

| 항목 | 상세 설계 방향 |
|---|---|
| **기존 Streamlit 서비스** | `law-chatbot.service` 포트 8502 (기존대로 무중단 유지) |
| **FastAPI API 서비스** | 신규 추가 구동 (`busan-advisor-api.service` 생성 예정) |
| **FastAPI 바인딩** | `127.0.0.1:8001` (보안을 위해 내부망 구동 원칙) |
| **Frontend 정적 서빙** | FastAPI StaticFiles 연동을 통한 `/ui` 제공 권장 |
| **Nginx 요구 여부** | 현재 1차 제한 공개 단계에서는 불필요 (`nginx_required_now: false`) |

---

## 4. NCP Root Password Rotation 보안 권고사항

현재 NCP 클라우드 접속을 위한 Root 계정 자격 증명이 임시 스크립트에 포함되었던 이슈가 정리되었으나, **비밀번호 유출 가능성**이 존재합니다. 
이를 위해 배포 실행 전 다음이 이루어져야 합니다.

- `password_rotation_owner`: 사용자(User) 직접 수행.
- `password_rotation_completed`: `true` (수행 완료).

*(※ 보안 원칙에 따라 본 문서나 로그에 절대로 비밀번호를 묻거나 평문 출력하지 않습니다.)*

---

## 5. 최종 배포 전(Pre-Deployment) 필수 체크리스트

실제 운영 환경에 배포가 가동되기 전, 다음의 항목이 최종 확인되어야 합니다.

- [x] **Password Rotation 완료**: NCP `root` 계정의 패스워드 변경이 완료되었는가?
- [ ] **Frontend Static Files 구현 승인**: `/ui`를 FastAPI로 서빙하는 코드 반영을 승인할 것인가?
- [ ] **배포 대상 Commit Hash 확정**: `febecef`를 기반으로 운영 서비스에 배포를 시작할 것인가?
- [ ] **Rollback 절차 인지**: 장애 시 이전 Commit으로 되돌리고 `systemctl`을 롤백할 준비가 되어 있는가?
- [ ] **운영 책임자 최종 승인**: 위 사항이 확인된 후 `deployment_approved=true`로 전환할 수 있는가?

---

> **⚠️ 다시 한 번 강조합니다.**
> 현재까지 `systemctl start/restart/stop` 명령, 백그라운드 `pm2` 실행, 운영 디렉터리(`/opt/busan`) 직접 코드 덮어쓰기 등 실제 운영 설정 변경은 **전혀 수행되지 않았습니다.**
