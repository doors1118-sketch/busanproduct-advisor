# 강제 작업 지침 (Mandatory Work Guidelines)

## 1. 외부 에이전트 연동 폴더 동기화 필수 (Export Directory Sync)
- **대상 폴더**: `phase8_gateway_export_flat/` (또는 추후 지정되는 export 전용 폴더)
- **강제 규칙**: 사용자가 "작업해" 또는 "수정해"라고 지시한 직후 코드/설계 문서 작성이 끝나면, **그 즉시, 사용자에게 답변을 보내기 전에, 예외 없이** 해당 export 폴더에 대상 파일을 복사(`Copy-Item`)하고 `git commit` 및 `git push`를 100% 완료해야 한다.
- 사용자의 특별한 명시적 대기(Hold) 명령이 과거에 있었다 하더라도, 현재 지시가 "구현"이나 "수정"이라면 무조건 동기화를 수반한다.

## 2. No-Conclusion & 방어 로직 준수
- 법적 확정 표현 금지 원칙 준수
- 항상 `not_determined` 및 `fallback` 방어선 유지
