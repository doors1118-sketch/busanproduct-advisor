from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class LocalPurchaseSupportRuleCondition:
    buyer_types: Optional[List[str]] = None
    buyer_type_confidence: Optional[str] = None
    contract_objects: Optional[List[str]] = None
    contract_subtypes: Optional[List[str]] = None
    contract_methods: Optional[List[str]] = None
    procurement_routes: Optional[List[str]] = None
    law_system: Optional[List[str]] = None
    quote_type: Optional[List[str]] = None
    evaluation_methods: Optional[List[str]] = None
    item_trigger_grade: Optional[str] = None
    product_type_scope: Optional[List[str]] = None
    amount_condition_type: Optional[str] = None
    amount_min: Optional[int] = None
    amount_max: Optional[int] = None

@dataclass
class LocalPurchaseSupportRule:
    rule_id: str
    category: str
    tool_code: str
    display_name: str
    condition: LocalPurchaseSupportRuleCondition
    legal_basis_source_ids: List[str]
    legal_basis_query_terms: List[str]
    legal_basis_type: str
    law_system: Optional[str] = None
    basis_summary: Optional[str] = None
    suggested_action: str
    safe_phrase: str
    required_checks: List[str]
    exclusion_conditions: List[str]
    priority: int
    review_status: str

    # 수의계약 / 견적 방식
    quote_type: Optional[str] = None

    # 지역의무공동도급 / 공동수급
    min_local_share_percent: Optional[float] = None
    max_local_share_percent: Optional[float] = None
    share_rule_summary: Optional[str] = None

    # 평가·가점
    max_score: Optional[float] = None
    score_unit: Optional[str] = None
    score_basis: Optional[str] = None
    evaluation_method_scope: List[str] = field(default_factory=list)

    # MAS / 종합쇼핑몰 / 제3자단가계약
    procurement_route_type: Optional[str] = None
    requires_second_stage_check: bool = False
    second_stage_thresholds: Optional[Dict[str, int]] = None
    regional_evaluation_available: Optional[bool] = None
    direct_order_allowed_check_required: bool = False

    # 후보 추천 연계
    candidate_lookup_type: Optional[str] = None
    candidate_required_filters: List[str] = field(default_factory=list)

    # 정량 근거
    numeric_basis: Optional[Dict[str, Any]] = None
