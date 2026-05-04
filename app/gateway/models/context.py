from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class SourceEntry:
    source_id: str
    source_name: str
    normalized_title: str
    law_category: Optional[str]
    source_type: Optional[str]
    applicability_scope: Optional[str]
    active_for_rule: bool                   # 항상 True
    activation_mode: Optional[str]

@dataclass
class SourceContext:
    sources: List[SourceEntry]
    assumed_buyer_type: Optional[str]
    assumption_reason: Optional[str]
    buyer_type_confidence: Optional[str]
    required_slots_missing: List[str]

@dataclass
class RouteContext:
    base_jurisdiction: str
    overlay_applied: bool
    overlay_scope: Optional[str]
    overlay_sources: List[SourceEntry]
    dual_routing: bool

@dataclass
class ProcedureSourceEntry:
    source_id: str
    source_name: str
    source_type: Optional[str]
    applicability_scope: Optional[str]
    usage: str = "procedure_guidance_only"

@dataclass
class ProcedureContext:
    sources: List[ProcedureSourceEntry]
    filter_applied: bool
    usage: str = "answer_builder_procedure_section_only"
    judgment_eligible: bool = False         # 항상 False

@dataclass
class ItemEligibilityContext:
    trigger_grade: str                      # "explicit" | "silent"
    triggered_by: List[str]
    detail_item_resolved: bool
    detail_item_code: Optional[str]
    detail_item_name: Optional[str]
    detail_item_candidates: Optional[List[dict]]
    is_sme_competition_product: Optional[bool]
    direct_production_required: Optional[bool]
    company_cert_status: Optional[str]
    eligibility_status: Optional[str]
    candidate_action: Optional[str]
    item_eligibility_required: bool = True

@dataclass
class ItemEligibilityResult:
    resolver_status: str                    # "resolved" | "not_triggered" | "data_unavailable" | "ambiguous"
    unavailable_reason: Optional[str]
    context: Optional[ItemEligibilityContext]

@dataclass
class EnrichmentData:
    cert_status: Optional[str]
    cert_expiry: Optional[str]
    detail_item_codes: Optional[List[str]]
    matched_by: Optional[str]
    per_candidate_match: Optional[List[dict]]

@dataclass
class CompanyCandidate:
    company_id: str
    company_name_masked: str
    location: str
    business_type: Optional[str]
    contract_count: Optional[int]
    contract_amount: Optional[int]
    enrichment_data: Optional[EnrichmentData]

@dataclass
class CompanyCandidateContext:
    candidates: List[CompanyCandidate]
    enrichment_applied: bool
    enrichment_scope: Optional[str]
    total_found: int

@dataclass
class GatewayMetadata:
    total_sources_matched: int
    procedure_sources_matched: int
    overlay_applied: bool
    item_eligibility_resolver_status: str
    item_eligibility_trigger_grade: Optional[str]
    company_candidates_found: int
    enrichment_applied: bool
    enrichment_scope: Optional[str]

@dataclass
class GatewayResponse:
    request_id: str
    source_context: SourceContext
    route_context: RouteContext
    procedure_context: ProcedureContext
    item_eligibility_result: ItemEligibilityResult
    metadata: GatewayMetadata
    company_candidate_context: Optional[CompanyCandidateContext] = None
    error: Optional[str] = None
    gateway_version: str = "v0.1.1"
    baseline_db: str = "legal_db_v0_1_3.sqlite"
