---
description: 작업 마무리 — 하네스 검증 + 대화 맥락 저장 및 체크리스트 업데이트
---

# /end 워크플로

// turbo-all

세션 종료 시 실행합니다. 오늘 작업 내용을 검증하고 정리하여 다음 세션에서 이어갈 수 있도록 합니다.

## 1단계: 대화 맥락 저장

오늘 날짜로 `대화맥락_YYYYMMDD.md` 파일을 생성합니다:

1. `c:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작\대화맥락_YYYYMMDD.md` 파일 생성 (날짜는 오늘 날짜)
   - 이 세션에서 결정한 사항
   - 변경된 파일 목록
   - 해결한 문제 / 남은 이슈
   - 다음 세션에서 해야 할 일

## 2단계: 체크리스트 업데이트

2. 해당 대화의 `task.md` 업데이트
   - 완료 항목 `[x]` 체크
   - 진행 중 항목 `[/]` 표시
   - 새로 발견된 작업 추가

## 3단계: 하네스 자동 검증 (자동 실행)

이 세션에서 코드가 변경되었다면 아래를 자동 실행합니다:

// turbo
3-1. 구문 검증 — 변경된 Python 파일 전체:
```
python -m py_compile [변경된_파일.py]
```

// turbo
3-2. 모듈 import 검증:
```
python -c "import sys; sys.path.insert(0,'app'); import law_api_client; import gemini_engine; import system_prompt; print('All imports OK')"
```

3-3. 하네스 정합성 체크 — system_prompt.py가 변경된 경우:
- [ ] 정체성 정의 존재 확인
- [ ] 답변 형식 강제 존재 확인
- [ ] 행동 제약 6가지 존재 확인
- [ ] 도구 사용 규칙 존재 확인
- [ ] 면책 고지 존재 확인

3-4. 검증 결과를 대화맥락 파일에 기록

## 4단계: /start 워크플로 업데이트

4. `.agents/workflows/start.md`의 대화맥락 파일 경로를 **최신 날짜 파일**로 교체

## 5단계: Git Push

// turbo
5. 변경사항 Git 커밋 및 푸시:
```
cd "c:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작"; git add -A; git commit -m "세션 종료: YYYYMMDD 작업 내용 반영"; git push
```

## 6단계: 보고

사용자에게 간략히 보고:
- 오늘 한 일 요약 (3줄 이내)
- 검증 결과 (통과/실패)
- Git push 결과
- 내일 해야 할 일 (우선순위 순)

