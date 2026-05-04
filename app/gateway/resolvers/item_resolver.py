# mock-only / no-judgment / no-write
from typing import Optional
from app.gateway.models.context import ItemEligibilityResult, ItemEligibilityContext

def resolve_item_eligibility(
    user_query: str,
    item_name: Optional[str],
    detail_item_code: Optional[str],
    company_id: Optional[str],
    procurement_route: Optional[str],
    contract_method: Optional[str]
) -> ItemEligibilityResult:
    
    # 1. Explicit Trigger
    explicit_keywords = ["직생", "직접생산", "중기경쟁"]
    has_explicit_keyword = any(k in user_query for k in explicit_keywords)
    
    if detail_item_code or has_explicit_keyword:
        return ItemEligibilityResult(
            resolver_status="resolved",
            unavailable_reason=None,
            context=ItemEligibilityContext(
                trigger_grade="explicit",
                triggered_by=["T2_detail_item_code"] if detail_item_code else ["T1_keyword"],
                detail_item_resolved=bool(detail_item_code),
                detail_item_code=detail_item_code if detail_item_code else None,
                detail_item_name=item_name or "직생/중기경쟁품목",
                detail_item_candidates=None,
                is_sme_competition_product=True,
                direct_production_required=True,
                company_cert_status=None,
                eligibility_status="eligible",
                candidate_action="select_company",
                item_eligibility_required=True
            )
        )
        
    # 2. Silent Trigger
    silent_keywords = ["CCTV", "컴퓨터", "노트북"]
    has_silent_keyword = any(k in user_query for k in silent_keywords)
    
    if has_silent_keyword or item_name in silent_keywords:
        return ItemEligibilityResult(
            resolver_status="resolved",
            unavailable_reason=None,
            context=ItemEligibilityContext(
                trigger_grade="silent",
                triggered_by=["T3_alias_map_sme_candidate"],
                detail_item_resolved=False,
                detail_item_code=None,
                detail_item_name=item_name or "무명품목",
                detail_item_candidates=[{"detail_item_code": "11111111", "detail_item_name": "후보1"}, {"detail_item_code": "22222222", "detail_item_name": "후보2"}] if not detail_item_code else None,
                is_sme_competition_product=True,
                direct_production_required=None,
                company_cert_status=None,
                eligibility_status="eligible",
                candidate_action="select_company",
                item_eligibility_required=True
            )
        )
        
    # 3. Ambiguous Trigger (소프트웨어)
    if "소프트웨어" in user_query:
         return ItemEligibilityResult(
            resolver_status="ambiguous",
            unavailable_reason="detail_item_code_ambiguous",
            context=ItemEligibilityContext(
                trigger_grade="explicit",
                triggered_by=["T1_keyword"],
                detail_item_resolved=False,
                detail_item_code=None,
                detail_item_name=item_name or "소프트웨어",
                detail_item_candidates=[{"detail_item_code": "33333333"}, {"detail_item_code": "44444444"}],
                is_sme_competition_product=None,
                direct_production_required=None,
                company_cert_status=None,
                eligibility_status=None,
                candidate_action=None,
                item_eligibility_required=True
            )
        )
        
    return ItemEligibilityResult(
        resolver_status="not_triggered",
        unavailable_reason=None,
        context=None
    )
