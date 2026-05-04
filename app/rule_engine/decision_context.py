from dataclasses import dataclass, field
from typing import List, Optional, Literal

ReviewOutcome = Literal[
    "review_candidate",
    "conditional_review",
    "manual_review_required",
    "insufficient_data",
    "not_triggered",
    "out_of_scope"
]

@dataclass
class DecisionContext:
    # 핵심 리뷰 상태
    review_outcome: ReviewOutcome
    
    # 영구적 방어 정책 (확정적 결론 도출 금지)
    legal_conclusion: Literal["not_determined"] = "not_determined"
    
    # 룰 엔진 적용 결과 매핑 (소스 분리)
    applied_source_ids: List[str] = field(default_factory=list)
    overlay_source_ids: List[str] = field(default_factory=list)
    procedure_source_ids: List[str] = field(default_factory=list)
    missing_required_slots: List[str] = field(default_factory=list)
    
    # Item Eligibility 관련
    item_eligibility_status: Optional[str] = None
    item_eligibility_grade: Optional[str] = None
    
    # Enrichment 관련
    enrichment_available: bool = False
    enrichment_judgment_effect: Literal["none"] = "none"
    
    # Answer Builder용 제어 지시자 (Action / Directive)
    item_action_required: Optional[str] = None
    route_directive: Optional[str] = None
    manual_review_reasons: List[str] = field(default_factory=list)
    
    # Phase 9.1 Local Purchase Support Rule Mapping
    local_purchase_support_review_required: bool = False
    local_purchase_support_tools: List[str] = field(default_factory=list)
    local_purchase_support_source_ids: List[str] = field(default_factory=list)
    local_purchase_support_notes: List[str] = field(default_factory=list)
    local_purchase_required_checks: List[str] = field(default_factory=list)

    # 메타 상태 및 노출 정책
    buyer_type_assumed: bool = False
    dual_routing_active: bool = False
    answer_exposure_policy: Optional[str] = None
