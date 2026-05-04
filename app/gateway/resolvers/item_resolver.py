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
    
    # Mock logic based on keywords
    if "CCTV" in user_query or detail_item_code:
        return ItemEligibilityResult(
            resolver_status="resolved",
            unavailable_reason=None,
            context=ItemEligibilityContext(
                item_eligibility_required=True,
                trigger_grade="explicit",
                triggered_by=["T1_keyword" if not detail_item_code else "T2_detail_item_code"],
                detail_item_resolved=bool(detail_item_code),
                detail_item_code=detail_item_code or "1234567890",
                detail_item_name=item_name or "CCTV",
                detail_item_candidates=None,
                is_sme_competition_product=True,
                direct_production_required=True,
                company_cert_status=None,
                eligibility_status="eligible",
                candidate_action="select_company"
            )
        )
    elif "컴퓨터" in user_query:
        return ItemEligibilityResult(
            resolver_status="resolved",
            unavailable_reason=None,
            context=ItemEligibilityContext(
                item_eligibility_required=True,
                trigger_grade="silent",
                triggered_by=["T3_alias_map_sme_candidate"],
                detail_item_resolved=False,
                detail_item_code=None,
                detail_item_name=item_name or "컴퓨터",
                detail_item_candidates=None,
                is_sme_competition_product=True,
                direct_production_required=None,
                company_cert_status=None,
                eligibility_status="eligible",
                candidate_action="select_company"
            )
        )
    elif "소프트웨어" in user_query:
         return ItemEligibilityResult(
            resolver_status="ambiguous",
            unavailable_reason="detail_item_code_ambiguous",
            context=ItemEligibilityContext(
                item_eligibility_required=True,
                trigger_grade="explicit",
                triggered_by=["T1_keyword"],
                detail_item_resolved=False,
                detail_item_code=None,
                detail_item_name=item_name or "소프트웨어",
                detail_item_candidates=[{"detail_item_code": "11111111"}, {"detail_item_code": "22222222"}],
                is_sme_competition_product=None,
                direct_production_required=None,
                company_cert_status=None,
                eligibility_status=None,
                candidate_action=None
            )
        )
        
    return ItemEligibilityResult(
        resolver_status="not_triggered",
        unavailable_reason=None,
        context=None
    )
