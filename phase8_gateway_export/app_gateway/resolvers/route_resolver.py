# mock-only / no-judgment / no-write
from typing import Optional
from app.gateway.models.context import RouteContext, SourceEntry

def resolve_route(buyer_type: Optional[str], procurement_route: Optional[str]) -> RouteContext:
    overlay_applied = False
    overlay_sources = []
    
    if procurement_route in ["mas", "pps_shopping_mall", "pps_delegated_contract"]:
        overlay_applied = True
        overlay_sources = [
            SourceEntry(
                source_id="pps_route_law_1",
                source_name="조달청 지침",
                normalized_title="조달청 지침",
                law_category="guideline",
                source_type="overlay",
                applicability_scope="pps",
                active_for_rule=True,
                activation_mode="overlay"
            )
        ]
        
    return RouteContext(
        base_jurisdiction="local_contract",
        overlay_applied=overlay_applied,
        overlay_scope=procurement_route if overlay_applied else None,
        overlay_sources=overlay_sources,
        dual_routing=overlay_applied
    )
