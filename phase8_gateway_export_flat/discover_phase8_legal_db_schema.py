import sqlite3
import json
import os
from collections import defaultdict

def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'app', 'data', 'legal_db_v0_1_3.sqlite')

def discover_schema():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Error: DB not found at {db_path}")
        return

    # Use read-only mode
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    schema_info = {
        "tables": {},
        "target_column_checks": {
            "source_id_name_title_mapping": {},
            "active_for_rule": [],
            "active_for_procedure": [],
            "judgment_eligible": [],
            "activation_mode": []
        },
        "review_status_distribution": {},
        "mapping_tables": {
            "buyer_type_to_jurisdiction": [],
            "procurement_route_overlay": [],
            "procedure_only_flag": []
        }
    }

    # 1. Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row["name"] for row in cursor.fetchall()]

    for table in tables:
        # 2. Get columns for each table
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = [row["name"] for row in cursor.fetchall()]
        schema_info["tables"][table] = columns

        # Check target columns
        has_source_id = "source_id" in columns
        has_source_name = "source_name" in columns
        has_normalized_title = "normalized_title" in columns
        
        if has_source_id or has_source_name or has_normalized_title:
             schema_info["target_column_checks"]["source_id_name_title_mapping"][table] = {
                 "source_id": has_source_id,
                 "source_name": has_source_name,
                 "normalized_title": has_normalized_title
             }
             
        if "active_for_rule" in columns:
            schema_info["target_column_checks"]["active_for_rule"].append(table)
        if "active_for_procedure" in columns:
            schema_info["target_column_checks"]["active_for_procedure"].append(table)
        if "judgment_eligible" in columns:
            schema_info["target_column_checks"]["judgment_eligible"].append(table)
        if "activation_mode" in columns:
            schema_info["target_column_checks"]["activation_mode"].append(table)

        # Review status distribution
        if "review_status" in columns:
            try:
                cursor.execute(f"SELECT review_status, COUNT(*) as cnt FROM '{table}' GROUP BY review_status")
                dist = {str(r["review_status"]): r["cnt"] for r in cursor.fetchall()}
                schema_info["review_status_distribution"][table] = dist
            except Exception as e:
                schema_info["review_status_distribution"][table] = f"Error: {str(e)}"
                
        # Mapping table checks based on names or columns
        if "buyer_type" in columns and ("jurisdiction" in columns or "applicability_scope" in columns):
            schema_info["mapping_tables"]["buyer_type_to_jurisdiction"].append(table)
            
        if "procurement_route" in columns or "route" in table.lower() or "overlay" in table.lower():
            schema_info["mapping_tables"]["procurement_route_overlay"].append(table)
            
        if "procedure" in table.lower() or "active_for_procedure" in columns or "procedure_only" in columns:
            schema_info["mapping_tables"]["procedure_only_flag"].append(table)

    conn.close()

    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "phase8_legal_db_schema_map.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema_info, f, ensure_ascii=False, indent=2)
        
    print(f"Schema map saved to {output_path}")

if __name__ == "__main__":
    discover_schema()
