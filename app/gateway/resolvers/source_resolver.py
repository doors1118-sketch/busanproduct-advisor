# read-only / no-judgment / no-write
from typing import Optional
from app.gateway.models.context import SourceContext, SourceEntry
from app.gateway.db.reader import ReadOnlyDatabase

def resolve_sources(
    buyer_type: Optional[str],
    contract_object: Optional[str],
    procurement_route: Optional[str],
    contract_method: Optional[str],
    item_name: Optional[str],
    db_reader: Optional['ReadOnlyDatabase'] = None
) -> SourceContext:
    
    if not db_reader:
        import os
        from app.gateway.db.reader import ReadOnlyDatabase
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'legal_db_v0_1_3.sqlite')
        db_reader = ReadOnlyDatabase(db_path)

    bt = buyer_type if buyer_type else "local_government"
    
    query = """
        SELECT ls.source_id, ls.source_name, ls.normalized_title, ls.law_category, ls.activation_mode, ls.source_type, ls.applicability_scope
        FROM legal_source ls
        JOIN legal_buyer_type_mapping bm ON ls.source_id = bm.source_id
        WHERE bm.buyer_type_scope = ?
        AND ls.active_for_rule = 1
        AND COALESCE(ls.judgment_eligible, 1) = 1
        AND ls.activation_mode IS NOT NULL
        AND ls.review_status NOT IN ('wrong_match', 'needs_manual_source')
    """
    params = [bt]
    
    if contract_object:
        query += " AND (ls.contract_object_scope IS NULL OR ls.contract_object_scope = '' OR ls.contract_object_scope = ? OR ls.contract_object_scope LIKE ?)"
        params.extend([contract_object, f"%{contract_object}%"])
        
    rows = db_reader.execute(query, tuple(params))
    
    sources = []
    for r in rows:
        sources.append(SourceEntry(
            source_id=r["source_id"],
            source_name=r["source_name"],
            normalized_title=r["normalized_title"],
            law_category=r["law_category"],
            activation_mode=r["activation_mode"],
            source_type=r["source_type"] if "source_type" in r.keys() and r["source_type"] else "law",
            applicability_scope=r["applicability_scope"],
            active_for_rule=True
        ))
        
    return SourceContext(
        sources=sources,
        assumed_buyer_type="local_government" if not buyer_type else None,
        assumption_reason="부산시 업무 기본 맥락에 따른 임시 추정" if not buyer_type else None,
        buyer_type_confidence="low" if not buyer_type else "high",
        required_slots_missing=["buyer_type"] if not buyer_type else []
    )
