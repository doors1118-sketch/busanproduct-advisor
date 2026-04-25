import sys
import re

file_path = r'c:\Users\doors\OneDrive\바탕 화면\사무실 메뉴얼 제작_추출\메뉴얼 제작\app\system_prompt.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the entire manual 3-step routing and hardcoded fallback table for 지역제한
old_region_limit = """    ★★ "행정안전부장관이 고시하는 금액" 확인 방법 (반드시 이 순서로!):
    1단계: get_law_text(시행규칙, "제24조") → "고시하는 금액"이라고만 나옴
    2단계: search_law("지방자치단체 입찰 유자격자 등록") 또는 search_law("지역제한 고시") → 행정규칙(고시)에서 실제 금액 확인!
    3단계: 고시를 못 찾을 경우 아래 확정 금액을 사용 (검증 완료):
    ⚠️ 단, 이 확정 금액을 사용할 때는 반드시 다음 문구를 답변에 포함하라:
       "본 금액은 2024년 7월 매뉴얼 기준이며, 이후 고시 개정으로 현재와 다를 수 있습니다.
        정확한 기준은 행정안전부 고시 원문을 확인하세요."
    
      | 계약유형 | 지역제한 금액기준 (2024.07 매뉴얼 기준) |
      |---------|--------------------------------------|
      | 공사(종합) | 추정가격 150억원 미만 |
      | 공사(전문) | 추정가격 10억원 미만 |
      | 물품 | 추정가격 **1억원** 미만 |
      | 용역 | 추정가격 **3.3억원** 미만 |
    
    ⛔ 금지어: "3.77억", "2.2억" → 전부 오답! 물품=1억, 용역=3.3억만 맞음"""

new_region_limit = """    ★★ "행정안전부장관이 고시하는 금액" 등 수치 확인 시 절대 규칙:
    과거 지식이나 프롬프트에 의존하지 마세요! 법령은 계속 개정됩니다.
    반드시 chain_law_system("지역제한 금액기준") 단일 호출을 통해 행정안전부 고시의 최신 원문을 확인한 후 답변하십시오."""

content = content.replace(old_region_limit, new_region_limit)

# Remove the hardcoded 40% rule
old_joint_venture = """  - 시행령 제88조 제6항: 공동수급체 지역업체 참여비율 (★ 행안부 예규에 따라 특별한 규정이 없는 한 40%, 최대 49% 적용. 30%로 응답하는 것은 오답!)"""
new_joint_venture = """  - 시행령 제88조 제6항: 공동수급체 지역업체 참여비율 (★ 반드시 chain_law_system("공동수급체 지역업체 참여비율")을 호출하여 최신 예규 수치를 확인할 것)"""

content = content.replace(old_joint_venture, new_joint_venture)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Hardcoded numbers removed and updated to strict MCP routing successfully.")
