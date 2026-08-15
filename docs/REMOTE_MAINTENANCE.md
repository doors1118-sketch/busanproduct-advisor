# 원격 유지보수

운영 기준 경로는 `/opt/advisor`, 배포 브랜치는 `main`이다. GitHub Actions의 수동 배포는 운영 작업트리가 깨끗하고 현재 커밋에서 `main` 최신 커밋으로 fast-forward할 수 있을 때만 실행된다.

2026-08-15에 최신 운영 브랜치 `codex/server-final-20260813`의 검증된 변경을 `main`에 통합했다. 이후 일상 개발과 배포는 `main`만 사용한다. `/opt/busan` 공공조달 서비스와 `/opt/advisor` 추천·법령지원 서비스는 계속 별도 작업트리와 서비스로 유지한다.

새 PC 설정과 공통 배포 절차는 신용보증 저장소의 `docs/REMOTE_MAINTENANCE.md` 및 `scripts/setup-new-pc.ps1`을 기준으로 한다.
