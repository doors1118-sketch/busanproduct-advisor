# read-only / no-judgment / no-write
from typing import Optional
from app.gateway.models.context import ProcedureContext, ProcedureSourceEntry
from app.gateway.db.reader import ReadOnlyDatabase

def resolve_procedures(
    buyer_type: Optional[str],
    contract_object: Optional[str],
    procurement_route: Optional[str],
    contract_method: Optional[str],
    procedure_topic: Optional[str],
    db_reader: Optional['ReadOnlyDatabase'] = None
) -> ProcedureContext:
    
    filter_applied = any(x is not None for x in [buyer_type, contract_object, procurement_route, contract_method, procedure_topic])
    
    if not db_reader:
        import os
        from app.gateway.db.reader import ReadOnlyDatabase
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'legal_db_v0_1_3.sqlite')
        db_reader = ReadOnlyDatabase(db_path)

    query = """
        SELECT source_id, source_name, normalized_title, law_category, source_type, applicability_scope
        FROM legal_source
        WHERE active_for_procedure = 1
        AND active_for_rule = 0
        AND COALESCE(judgment_eligible, 0) = 0
        AND review_status NOT IN ('wrong_match', 'needs_manual_source')
    """
    
    cursor = db_reader.conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    
    sources = []
    for r in rows:
        sources.append(ProcedureSourceEntry(
            source_id=r["source_id"],
            source_name=r["source_name"],
            source_type=r["source_type"] if "source_type" in r.keys() and r["source_type"] else "procedure",
            applicability_scope=r["applicability_scope"],
            usage="procedure_guidance_only"
        ))
        
    return ProcedureContext(
        sources=sources,
        filter_applied=filter_applied,
        usage="answer_builder_procedure_section_only",
        judgment_eligible=False
    )
