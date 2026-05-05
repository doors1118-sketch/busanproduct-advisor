from typing import Literal, List, Optional
from pydantic import BaseModel, Field

Intent = Literal[
    "legal_explanation",
    "contract_review",
    "local_purchase_support",
    "candidate_search",
    "item_eligibility",
    "procurement_route_review",
    "mixed",
    "out_of_scope"
]

class RouterSlots(BaseModel):
    buyer_name: Optional[str] = None
    buyer_type: Optional[str] = None
    contract_object: Optional[str] = None
    contract_subtype: Optional[str] = None
    item_name: Optional[str] = None
    detail_item_code: Optional[str] = None
    company_id: Optional[str] = None
    amount: Optional[int] = None
    amount_unit: Optional[str] = None
    procurement_route: Optional[str] = None
    contract_method: Optional[str] = None
    company_type: Optional[str] = None
    quote_type: Optional[str] = None
    service_type: Optional[str] = None
    construction_type: Optional[str] = None
    location: Optional[str] = None
    local_supplier_intent: bool = False
    candidate_lookup_requested: bool = False
    item_eligibility_requested: bool = False
    legal_topic: Optional[str] = None

class RouterResult(BaseModel):
    primary_intent: Intent
    secondary_intents: List[Intent] = Field(default_factory=list)
    confidence: float = 1.0
    slots: RouterSlots = Field(default_factory=RouterSlots)
    routing_decision: str = ""
    candidate_lookup_required: bool = False
    legal_explanation_only: bool = False
    clarification_needed: List[str] = Field(default_factory=list)
    reason: str = ""
