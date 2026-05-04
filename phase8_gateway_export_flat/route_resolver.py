# read-only / no-judgment / no-write
from typing import Optional
from app.gateway.models.context import RouteContext, SourceEntry
from app.gateway.db.reader import ReadOnlyDatabase

def resolve_routes(
    procurement_route: Optional[str],
    contract_method: Optional[str],
    item_name: Optional[str],
    db_reader: Optional['ReadOnlyDatabase'] = None
) -> RouteContext:
    
    if not procurement_route:
        return RouteContext(
            base_jurisdiction="local_government",
            overlay_applied=False,
            overlay_scope=None,
            overlay_sources=[],
            dual_routing=False
        )
        
    if not db_reader:
        import os
        from app.gateway.db.reader import ReadOnlyDatabase
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'legal_db_v0_1_3.sqlite')
        db_reader = ReadOnlyDatabase(db_path)

    query = """
        SELECT ls.source_id, ls.source_name, ls.normalized_title, ls.law_category, ls.activation_mode, ls.source_type, ls.applicability_scope
        FROM legal_source ls
        JOIN legal_overlay_mapping om ON ls.source_id = om.source_id
        WHERE om.overlay_scope = ?
        AND ls.active_for_rule = 1
        AND COALESCE(ls.judgment_eligible, 1) = 1
        AND ls.review_status NOT IN ('wrong_match', 'needs_manual_source')
    """
    
    cursor = db_reader.conn.cursor()
    cursor.execute(query, [procurement_route])
    rows = cursor.fetchall()
    
    sources = []
    for r in rows:
        sources.append(SourceEntry(
            source_id=r["source_id"],
            source_name=r["source_name"],
            normalized_title=r["normalized_title"],
            law_category=r["law_category"],
            activation_mode=r["activation_mode"],
            source_type=r["source_type"] if "source_type" in r.keys() and r["source_type"] else "guideline",
            applicability_scope=r["applicability_scope"],
            active_for_rule=True
        ))
        
    return RouteContext(
        base_jurisdiction="local_government",
        overlay_applied=len(sources) > 0,
        overlay_scope=procurement_route,
        overlay_sources=sources,
        dual_routing=False
    )
