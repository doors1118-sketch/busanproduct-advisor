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
    legal_conclusion: str = "not_determined"
    
    # 룰 엔진 적용 결과 매핑
    applied_source_ids: List[str] = field(default_factory=list)
    missing_required_slots: List[str] = field(default_factory=list)
    
    # Answer Builder용 제어 지시자 (Action / Directive)
    item_action_required: Optional[str] = None
    route_directive: Optional[str] = None
    manual_review_reasons: List[str] = field(default_factory=list)
    
    # 메타 상태
    buyer_type_assumed: bool = False
    dual_routing_active: bool = False
