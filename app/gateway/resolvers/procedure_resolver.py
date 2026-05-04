# mock-only / no-judgment / no-write
from typing import Optional
from app.gateway.models.context import ProcedureContext, ProcedureSourceEntry

def resolve_procedures(
    buyer_type: Optional[str],
    contract_object: Optional[str],
    procurement_route: Optional[str],
    contract_method: Optional[str],
    procedure_topic: Optional[str]
) -> ProcedureContext:
    
    filter_applied = any(x is not None for x in [buyer_type, contract_object, procurement_route, contract_method, procedure_topic])
    
    sources = []
    if contract_object == "construction" or procedure_topic is not None:
        sources.append(
            ProcedureSourceEntry(
                source_id="proc_1",
                source_name="공사/특정 절차 일반 안내",
                source_type="procedure",
                applicability_scope="general",
                usage="procedure_guidance_only"
            )
        )
    
    return ProcedureContext(
        sources=sources,
        filter_applied=filter_applied,
        usage="answer_builder_procedure_section_only",
        judgment_eligible=False
    )
