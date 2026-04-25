import sys
import os

filepath = r'c:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작\대화맥락_20260425.md'

text = """
## [오후 세션 업데이트]
### 1. 이 세션에서 추가 결정한 사항
- 제미나이 2.5 Pro의 도구 피로도(Tool Fatigue) 문제를 해결하기 위해 프롬프트의 복잡한 다단계 도구 호출을 폐기하고, **단일 체인 위임(Single-hop Delegation)**으로 아키텍처 변경.
- 향후 법령 개정에 대비하여 시스템 프롬프트 내의 하드코딩된 수치(종합공사 150억, 의무공동도급 40% 등)를 전면 삭제하고 MCP(chain_law_system) 원문을 무조건 신뢰하도록 룰 수정.
- 외부 아키텍처 평가를 수용하여 RAG(맥락) -> MCP(법적 팩트) -> LLM(설명)으로 데이터 신뢰도 계층을 확립함.

### 2. 추가 변경/생성된 파일 목록
- app/system_prompt.py: 도구 호출 강제 규칙 단순화 및 수치 하드코딩 제거 완료 (update_prompt.py, remove_fallbacks.py 활용).
- implementation_plan.md: 차세대 아키텍처 구현 계획(동적 프롬프트 조립, 캐싱 등) 정리 아티팩트 생성.
- company_search_pipeline.md: 로컬 업체 검색 API 및 데이터 처리 4단계 파이프라인 명세 작성.

### 3. 다음 세션(차세대 고도화)에서 해야 할 일
- JSON/YAML 기반의 프롬프트 스니펫화 및 동적 조립 로직 리팩토링.
- 구글 제미나이 Context Caching(접두어 캐싱) 적용을 위한 프롬프트 분리 설계.
- MCP 백엔드의 Fail-fast 및 Partial Result 반환 여부 검토 및 모니터링 적용.
"""

with open(filepath, 'a', encoding='utf-8') as f:
    f.write(text)

print('Context updated.')

os.system('git add .')
os.system('git commit -m "End session: Refactored system prompt for MCP delegation and removed hardcoded fallbacks"')
os.system('git push')
