from dataclasses import dataclass, field
from typing import List, Optional, Literal

@dataclass
class LocalPurchaseSupportRuleCondition:
    buyer_types: Optional[List[str]] = None
    contract_objects: Optional[List[str]] = None
    contract_methods: Optional[List[str]] = None
    procurement_routes: Optional[List[str]] = None
    amount_condition_type: Optional[str] = None
    amount_min: Optional[int] = None
    amount_max: Optional[int] = None
    item_trigger_grade: Optional[str] = None
    buyer_type_confidence: Optional[str] = None

@dataclass
class LocalPurchaseSupportRule:
    rule_id: str
    tool_code: str
    display_name: str
    condition: LocalPurchaseSupportRuleCondition
    legal_basis_source_ids: List[str]
    policy_basis_type: str
    suggested_action: str
    safe_phrase: str
    required_checks: List[str]
    exclusion_conditions: List[str]
    priority: int
    review_status: str
