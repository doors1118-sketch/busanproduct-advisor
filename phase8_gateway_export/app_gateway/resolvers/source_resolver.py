# mock-only / no-judgment / no-write
from typing import Optional
from app.gateway.models.context import SourceContext, SourceEntry

def resolve_sources(buyer_type: Optional[str], contract_object: Optional[str]) -> SourceContext:
    assumed = None
    confidence = "high"
    missing = []
    
    if buyer_type is None:
        assumed = "local_government"
        confidence = "low"
        missing.append("buyer_type")
        
    # Dummy mock sources
    sources = [
        SourceEntry(
            source_id="local_contract_law_1",
            source_name="지방계약법",
            normalized_title="지방계약법",
            law_category="law",
            source_type="base",
            applicability_scope="local_government",
            active_for_rule=True,
            activation_mode="default"
        )
    ]
    
    return SourceContext(
        sources=sources,
        assumed_buyer_type=assumed,
        assumption_reason="부산시 업무 기본 맥락에 따른 임시 추정" if assumed else None,
        buyer_type_confidence=confidence,
        required_slots_missing=missing
    )
