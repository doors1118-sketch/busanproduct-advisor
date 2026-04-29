# 부산 공공조달 AI 챗봇 — 운영 롤백 계획 (Rollback Plan)

이 문서는 배포 직후 장애 발생 시 이전 상태로 복구하기 위한 절차를 문서화한 것입니다.
**(경고: 실제 롤백 명령은 반드시 운영자 승인 후 수행되어야 하며, 임의 스크립트 기반 강제 실행이나 무분별한 파일 삭제는 엄격히 금지됩니다.)**

## 1. 커밋 해시 기준점

롤백을 실행하기 위해서는 변경 이전 상태의 해시값과 문제 발생 버전의 해시값이 필수적으로 기록되어야 합니다.

- **현재 안정 운영 (Rollback Target) Commit Hash**: `[운영 배포 시 확정하여 기록할 것]`
- **신규 배포 대상 (Problematic) Commit Hash**: `[운영 배포 시 확정하여 기록할 것]`

## 2. 롤백 원칙

- 롤백 절차는 반드시 운영 총괄 책임자의 사전 **승인 후 수행**되어야 합니다.
- 서버 운영 디렉터리(`/opt/busan`) 내부의 코드를 **수동으로 직접 수정하는 행위를 엄밀히 금지**합니다.
- 복구는 반드시 안전한 Git 명령체계를 따르며, 코드 유실을 야기할 수 있는 `git reset --hard`의 사용은 금지됩니다. (권장: `git checkout <안정 해시>` 또는 Release Tag 기반 복구)

## 3. 롤백 수행 절차 (문서화 전용 가이드)

### 단계 1: 서비스 기동 중지
비정상 동작 중인 FastAPI와 Streamlit 프로세스의 트래픽 처리를 우선 중지합니다.
```bash
sudo systemctl stop law-chatbot.service
sudo systemctl stop busan-fastapi.service  # (신규 생성된 경우)
```

### 단계 2: 안정화된 코드 버전으로 복구
가장 마지막으로 안정성이 확보된 커밋 해시 또는 릴리스 태그로 전환합니다.
```bash
cd /opt/busan
# 기존 상태 보호를 원할 경우 임시 브랜치 생성 후 전환
git checkout <안정화 커밋 해시 또는 Release Tag>
```

### 단계 3: 백업 데이터 및 의존성 무결성 점검
코드 버전 변경 후 의존성 충돌이나 RAG 데이터 불일치가 발생할 수 있으므로, 아래 요소들을 점검합니다.
- `requirements.txt`와 현재 파이썬 가상환경 의존성 상태 대조.
- 기존 Chroma DB 백업 데이터 확인: `app/.chroma` 디렉터리가 정상인지 확인.
- 운영 환경변수(`.env`) 파일 백업 무결성 확인.

### 단계 4: 서비스 재가동
```bash
sudo systemctl start law-chatbot.service
sudo systemctl start busan-fastapi.service
```

## 4. 롤백 직후 검증 (Smoke Test)

롤백이 올바르게 적용되었는지 최소한 다음 기능들이 모두 정상 작동하는지 확인합니다.

1. **상태 점검**: GET `/health` 호출 후 HTTP 200 반환 여부 확인.
2. **RAG 인덱스 확인**: GET `/rag/status` 호출 후 각 컬렉션(laws, manuals, innovation) 상태가 `SUCCESS`인지 점검.
3. **챗봇 검증**: POST `/chat`으로 간단한 질문 테스트 발송 후 답변 및 메타데이터 정상 반환 확인.
4. **UI 확인**: 기존 Streamlit UI(포트 8502) 및 Frontend MVP 접근 정상 여부 브라우저 테스트.
