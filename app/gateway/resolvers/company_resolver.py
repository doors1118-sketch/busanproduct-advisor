# mock-only / no-judgment / no-write
from typing import Optional, List
from app.gateway.models.context import CompanyCandidateContext, CompanyCandidate, EnrichmentData

def resolve_company_candidates(
    item_name: Optional[str],
    location: str,
    company_id: Optional[str],
    detail_item_code: Optional[str],
    detail_item_codes_from_candidates: Optional[List[str]]
) -> Optional[CompanyCandidateContext]:
    
    if not item_name and not detail_item_code and not detail_item_codes_from_candidates:
        return None
        
    enrichment_applied = bool(detail_item_code or detail_item_codes_from_candidates)
    
    enrichment_scope = None
    if enrichment_applied:
        if detail_item_code:
            enrichment_scope = "specific_item"
        elif detail_item_codes_from_candidates:
            enrichment_scope = "candidate_items"
        else:
            enrichment_scope = "general"
    
    enrichment_data = None
    if enrichment_applied:
        enrichment_data = EnrichmentData(
            cert_status="valid",
            cert_expiry="2027-12",
            detail_item_codes=[detail_item_code] if detail_item_code else detail_item_codes_from_candidates,
            matched_by="specific_code" if detail_item_code else ("candidate_match" if detail_item_codes_from_candidates else "company_level"),
            per_candidate_match=None
        )
        
    candidates = [
        CompanyCandidate(
            company_id="hash_12345",
            company_name_masked="가나다***",
            location=location,
            business_type="manufacturer",
            contract_count=5,
            contract_amount=150000000,
            enrichment_data=enrichment_data
        )
    ]
    
    return CompanyCandidateContext(
        candidates=candidates,
        enrichment_applied=enrichment_applied,
        enrichment_scope=enrichment_scope,
        total_found=len(candidates)
    )
