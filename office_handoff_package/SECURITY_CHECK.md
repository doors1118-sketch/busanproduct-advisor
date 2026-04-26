# SECURITY CHECK

인수인계 파일(`office_handoff_package.zip`) 패키징 전 다음 보안 항목들을 점검 및 제외 처리하였습니다.

- [x] 실제 `.env` 파일 제외 (템플릿인 `.env.example`만 포함)
- [x] `GEMINI_API_KEY` 원본 및 하드코딩 여부 점검 후 제외
- [x] `ODCLOUD_API_KEY` (공공데이터포털) 원본 제외
- [x] `LAW_OC` / `LAW_API_KEY` (국가법령정보센터) 원본 제외
- [x] 런타임 로그 원본 폴더(`logs/*.jsonl`, `.system_generated` 등) 제외
- [x] 사업자번호, 개인정보가 들어있는 실제 데이터 원본 파일 제외
- [x] 불필요한 개발 환경 캐시 및 가상환경 디렉터리 제외 (`.venv`, `venv`, `__pycache__`, `.pytest_cache`, `app/.chroma`, `ChromaDB` 원본 등)
