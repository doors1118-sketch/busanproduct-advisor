import sys

file_path = r'c:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작\app\system_prompt.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update 100억 limit -> 150억
content = content.replace('| 공사(종합) | 추정가격 100억원 미만 |', '| 공사(종합) | 추정가격 150억원 미만 |')

# 2. Add 40% rule
content = content.replace('- 시행령 제88조 제6항: 공동수급체 지역업체 참여비율', '- 시행령 제88조 제6항: 공동수급체 지역업체 참여비율 (★ 행안부 예규에 따라 특별한 규정이 없는 한 40%, 최대 49% 적용. 30%로 응답하는 것은 오답!)')

# 3. Simplify Multi-hop routing
old_routing = """[★★ 법령 + 행정규칙 종합 검색 — 실무 질문의 핵심! ★★]
  수의계약, 입찰, 적격심사, 가점 등 실무 질문에는 법령(법률·시행령)만으로 부족합니다!
  반드시 행정규칙(예규·훈령)까지 함께 검색하세요:
  
  → chain_law_system("지방계약법") — 법률→시행령→시행규칙→행정규칙 전체 체계 탐색
  → chain_action_basis("수의계약") — 관련 법체계 전체 분석
  
  예시: "2억 물품 수의계약 가능해?" 질문 시:
    1단계: search_law("지방계약법") → get_law_text(시행령, "제25조") — 수의계약 근거 조항
    2단계: search_law("입찰 및 계약집행기준") — 행정규칙에서 세부 절차·서류·요건 확인
    3단계: search_law("낙찰자 결정기준") — 적격심사·가점 관련 행정규칙 확인
    → 법령 + 행정규칙을 종합하여 답변!"""

new_routing = """[★★ 법령 + 행정규칙 종합 검색 — 실무 질문의 핵심! (위임 원칙) ★★]
  수의계약, 입찰, 적격심사, 지역의무공동도급 비율 등 법적 판단이나 수치를 묻는 질문에는 
  절대 개별 도구(search_law, get_law_text 등)를 조합하려 하지 마세요! 
  
  대신, 반드시 아래의 통합 체인 도구를 딱 1회 호출하여 결과를 확인하세요:
  → chain_full_research("질문 키워드") : 종합 질문 시 (법령+판례+해석례+행정규칙 모두 포함)
  → chain_law_system("키워드") : 상위법과 하위 행정규칙(예규)의 수치 등을 확인할 때
  
  예시: "출자출연기관 150억 수의계약 가능해?" 또는 "지역의무공동도급 비율은?" 질문 시:
    ✅ 1단계: chain_full_research("출자출연기관 종합공사 금액") 또는 chain_law_system("지역의무공동도급 비율") 1회 호출!
    ✅ 2단계: 체인 도구가 반환한 최신 법령/행정규칙 원문(결과값)을 바탕으로 답변. (수동 도구 연쇄 금지)"""

content = content.replace(old_routing, new_routing)

old_step1 = """🔗 [① search_law → get_law_text 연쇄 호출 — 강제 프로세스]
  법령 조문을 인용하려면, 반드시 아래 2단계를 거쳐라. 바로 답변하지 말 것!

  Step 1: search_law(query="지방계약법 시행령")
    → 법령의 고유 식별자(MST 값)를 획득
  Step 2: get_law_text(mst="획득한 MST", jo="제25조")
    → 획득한 MST + RAG에서 파악한 조항 번호를 조합하여 최신 조문 원문 조회

  이 연쇄를 거치지 않고 조문을 인용하면 → 개정 전 내용 인용 위험!
  RAG에서 "제25조가 관련 있을 것 같다"고 힌트를 얻었더라도,
  반드시 MCP로 원문을 확인한 후에만 인용할 것.

  예시 흐름:
    사용자: "수의계약 한도가 얼마야?"
    → RAG: "시행령 제25조, 제30조가 관련" (맥락 파악)
    → Step 1: search_law("지방계약법 시행령") → MST="002660"
    → Step 2: get_law_text(mst="002660", jo="제25조") → 최신 조문 원문 획득
    → Step 3: get_law_text(mst="002660", jo="제30조") → 1인 견적 한도 확인
    → 답변: 조문 원문 기반 + [최신 법령 확인 완료]"""

new_step1 = """🔗 [① 체인 도구를 활용한 단일 호출 강제 프로세스]
  법령 조문을 인용하거나 수치를 확인할 때 수동으로 여러 도구를 연쇄 호출(Multi-hop)하지 마세요!
  대신 통합 체인 도구를 사용하여 한 번에 정보를 획득하세요.
  
  ✅ chain_full_research("질문 키워드") 또는 chain_law_system("질문 키워드")
  이렇게 체인 도구 하나만 호출하면 MCP 백엔드가 알아서 법령의 MST 식별자, 조문 번호 매핑,
  심지어 관련 하위 행정규칙까지 전부 한 번에 검색하여 제공합니다.
  
  예시 흐름:
    사용자: "수의계약 한도가 얼마야?"
    → RAG: "시행령 제25조, 제30조가 관련" (맥락 파악)
    → Step 1: chain_law_system("수의계약 한도") 딱 1회 호출!
    → 답변: 체인 도구가 가져온 결과값 기반 + [최신 법령 확인 완료]"""

content = content.replace(old_step1, new_step1)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("System prompt updated successfully!")
