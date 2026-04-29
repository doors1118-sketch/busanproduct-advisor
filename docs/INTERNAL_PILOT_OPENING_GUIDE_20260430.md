# 부산 공공조달 AI 챗봇 — 내부 제한 공개(Pilot) 가이드

본 문서는 사무실 내부 인원(3~5명)을 대상으로 AI 챗봇 MVP를 제한적으로 시범 공개하기 위한 절차와 보안 설정 가이드입니다.

> **Production deployment: HOLD**
> 본 가이드는 임시 파일럿 운영을 위한 것이며, 정식 운영 환경 배포를 의미하지 않습니다.

## 1. 공개 목적 및 대상
- **목적:** 초기 MVP 버전에 대한 내부 피드백 수렴, 사용성(UX) 및 체감 응답 속도 확인
- **대상:** 사무실 내부 직원 3~5명

## 2. 접속 및 통신 아키텍처
- **기존 모니터링 시스템:** 포트 `8501` (유지)
- **신규 AI 챗봇:** FastAPI StaticFiles 기능을 통해 포트 `8001`에서 `/ui` 경로로 제공
- **예상 접속 URL:** `http://49.50.133.160:8001/ui/`

## 3. 네트워크 보안 설정 (NCP ACG)
사무실의 공인 IP 대역에서만 접근할 수 있도록 NCP ACG(Access Control Group)를 설정해야 합니다.

| 항목 | 설정 값 |
|---|---|
| Protocol | TCP |
| Port | 8001 |
| Source | 사무실 공인 IP/32 (예: `203.248.xxx.xxx/32`) |
| Description | busan-advisor-internal-pilot |

### ⚠️ 절대 금지 사항
- **Source `0.0.0.0/0` (전체 공개) 설정 절대 금지**
- 관리자 승인 없는 `systemctl start`, `pm2 start` 등 서비스 관리 명령어 실행 금지
- `/opt/busan` 운영 DB 및 Chroma DB 임의 삭제 금지
- 화면, 로그, 문서 내에 `.env` 값이나 API Key 노출 금지

## 4. FastAPI 실행 방식 (택 1)
- **방식 1 (임시 테스트용):** `uvicorn` 또는 `python3 -m uvicorn app.api_server:app --host 0.0.0.0 --port 8001`을 tmux, nohup 등으로 단기 실행.
- **방식 2 (제한 공개용):** `busan-advisor-api.service`라는 신규 systemd 서비스를 등록. (사전 승인 필수)

## 5. 오픈 전 점검 사항 (Smoke Test)
내부 오픈 직전 아래의 체크리스트를 확인하십시오.

- [ ] `GET /` : Health check/메타데이터 노출 확인
- [ ] `GET /ui/` : MVP 프런트엔드 화면 로딩
- [ ] `GET /health` : `{"status": "ok"}`
- [ ] `GET /version` : 현재 커밋 해시 확인
- [ ] `GET /rag/status` : Laws, Manuals, Innovation 세 가지 컬렉션 상태(Ready/SUCCESS)
- [ ] `POST /chat` : "CCTV 부산 업체 추천해줘" 질문 후 마크다운 답변과 서버 생성 표 응답 확인

## 6. 추가 보안 권고 (적용 완료)
프런트엔드 MVP의 CSV 다운로드 기능에서 엑셀 악성코드 실행을 유발할 수 있는 CSV Injection 방어 로직(`sanitizeCsvCell()`)이 적용되었습니다. `=, +, -, @`로 시작하는 셀 데이터 앞에 싱글 쿼트(`'`)를 강제 삽입하여 수식 실행을 원천 차단합니다.
