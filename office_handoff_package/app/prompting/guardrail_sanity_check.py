"""
Guardrail Sanity Check — 최종 보정
"""
import re


def apply_guardrail_sanity_check(
    question: str,
    selected: list[str],
) -> list[str]:
    """질문 내용 기반으로 누락 가드레일 보정"""
    final = set(selected)
    q = question.lower()

    # 업체/추천 키워드 → company_search 보정
    if any(kw in q for kw in ["업체", "추천", "살 수 있", "공급"]):
        final.add("company_search")

    # 공사+물품 혼합 → mixed_contract 보정
    has_construction = any(kw in q for kw in ["공사", "시공", "철거"])
    has_item = any(kw in q for kw in ["물품", "구매", "장비", "납품"])
    has_service = any(kw in q for kw in ["용역", "대행", "위탁"])

    mixed_count = sum([has_construction, has_item, has_service])
    if mixed_count >= 2:
        final.add("mixed_contract")

    # 금액 포함 → common_procurement 보정 (금액 판단 필수)
    if re.search(r"\d+\s*(만원|억|원|백만)", q):
        final.add("common_procurement")

    # 수의계약 키워드 → common_procurement 보정
    if any(kw in q for kw in ["수의계약", "1인 견적", "견적"]):
        final.add("common_procurement")

    # 개별 계약유형 추가 보정 (P0-2)
    if has_construction:
        final.add("construction_contract")
    if has_service:
        final.add("service_contract")
    if has_item:
        final.add("item_purchase")
    if any(kw in q for kw in ["mas", "종합쇼핑몰", "쇼핑몰", "다수공급자"]):
        final.add("mas_shopping_mall")

    return sorted(final)
