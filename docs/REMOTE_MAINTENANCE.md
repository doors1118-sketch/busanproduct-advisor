# 원격 유지보수

운영 기준 경로는 `/opt/advisor`, 배포 브랜치는 `codex/vendor-api-v2-handoff-20260524`이다. GitHub Actions의 수동 배포는 운영 작업트리가 깨끗하고 현재 커밋에서 지정 브랜치 최신 커밋으로 fast-forward할 수 있을 때만 실행된다.

현재 운영 서버에는 GitHub에 아직 정리되지 않은 변경이 있으므로 자동 배포가 의도적으로 차단된다. 운영 코드를 먼저 보존·검토하고 GitHub와 일치시킨 뒤 배포를 활성화한다. `/opt/busan` 공공조달 서비스와 `/opt/advisor` 추천·법령지원 서비스는 별도 작업트리와 서비스로 유지한다.

새 PC 설정과 공통 배포 절차는 신용보증 저장소의 `docs/REMOTE_MAINTENANCE.md` 및 `scripts/setup-new-pc.ps1`을 기준으로 한다.
