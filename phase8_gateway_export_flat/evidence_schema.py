"""
Phase 10.5: Evidence Schema

Evidence 기반 답변에 필요한 내부 구조 정의.
"""
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class EvidenceSourceRef(BaseModel):
    source_id: str
    title: str
    review_status: str  # verified | candidate_needs_review
    source_type: Optional[str] = None
    law_category: Optional[str] = None


class EvidenceParameterStatus(BaseModel):
    parameter_ref: str
    resolved_value: Optional[Any] = None
    display_value: Optional[str] = None
    expected_value_hint: Optional[str] = None
    requires_manual_numeric_verification: bool = True
    display_allowed: bool = False


class RuleEvidenceStatus(BaseModel):
    rule_id: str
    display_name: str
    category: str
    source_chain_status: str  # mapped_verified | mapped_candidate | partial_mapped | pending_resolution | company_api_mapping_required
    display_level: str  # source_verified | source_candidate | partial_evidence | source_missing | company_api_only
    primary_sources: List[EvidenceSourceRef] = Field(default_factory=list)
    related_sources: List[EvidenceSourceRef] = Field(default_factory=list)
    unmatched_query_terms: List[str] = Field(default_factory=list)
    numeric_parameters: List[EvidenceParameterStatus] = Field(default_factory=list)
    evidence_summary: str = ""
    cautions: List[str] = Field(default_factory=list)


class EvidenceContext(BaseModel):
    active_rule_ids: List[str] = Field(default_factory=list)
    rule_statuses: List[RuleEvidenceStatus] = Field(default_factory=list)
    source_gap_exists: bool = False
    unresolved_numeric_exists: bool = False
    threshold_ref_used: Optional[str] = None
    threshold_value_used: Optional[int] = None
