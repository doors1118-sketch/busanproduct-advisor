import json, os, sys, sqlite3, shutil
sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
db_old = os.path.join(base, 'legal_db_v0_1.sqlite')
db_v0_1_2 = os.path.join(base, 'legal_db_v0_1_2.sqlite')
db_v0_1_3 = os.path.join(base, 'legal_db_v0_1_3.sqlite')
patch_file = os.path.join(base, 'legal_source_activation_mode_patch_v0_1_3a.json')

# 1. Verification of the base DB (v0.1.2)
conn = sqlite3.connect(db_old)
cur = conn.cursor()
active_count = cur.execute("SELECT COUNT(*) FROM legal_source WHERE active_for_rule = 1").fetchone()[0]

t1 = "지방자치단체 입찰 및 계약집행기준"
t2 = "지방자치단체 입찰시 낙찰자 결정기준"
t1_active = cur.execute("SELECT active_for_rule FROM legal_source WHERE normalized_title = ?", (t1,)).fetchone()
t2_active = cur.execute("SELECT active_for_rule FROM legal_source WHERE normalized_title = ?", (t2,)).fetchone()

conn.close()

if active_count != 31:
    print(f"Error: active_count is {active_count}, expected 31.")
    sys.exit(1)
if not t1_active or t1_active[0] != 1:
    print(f"Error: {t1} is not active.")
    sys.exit(1)
if not t2_active or t2_active[0] != 1:
    print(f"Error: {t2} is not active.")
    sys.exit(1)

print("Base DB verified successfully as v0.1.2.")

# Rename/Copy to formalize v0_1_2
shutil.copy2(db_old, db_v0_1_2)

# Create v0.1.3 Staging DB
shutil.copy2(db_v0_1_2, db_v0_1_3)

# 2. Schema Expansion
conn = sqlite3.connect(db_v0_1_3)
cur = conn.cursor()
cur.execute('PRAGMA foreign_keys = ON;')

try:
    cur.executescript("""
        ALTER TABLE legal_source ADD COLUMN activation_mode VARCHAR(100);
        ALTER TABLE legal_source ADD COLUMN required_slots TEXT;
        ALTER TABLE legal_source ADD COLUMN procurement_route_scope TEXT;
        ALTER TABLE legal_source ADD COLUMN project_subtype_scope TEXT;
        ALTER TABLE legal_source ADD COLUMN contract_object_scope TEXT;
        ALTER TABLE legal_source ADD COLUMN active_for_procedure BOOLEAN DEFAULT 0;
        ALTER TABLE legal_source ADD COLUMN judgment_eligible BOOLEAN DEFAULT 1;
    """)
    print("Schema extended successfully.")
except sqlite3.OperationalError as e:
    print(f"Note: Schema might already be extended: {e}")

# 3. Patch Application
with open(patch_file, encoding='utf-8') as f:
    patch_data = json.load(f)

for p in patch_data:
    sid = p['source_id']
    title = p['normalized_title']
    
    act_mode = p.get('activation_mode')
    
    # Validation/Refinement for Technical Service logic
    if title in ["기술용역 적격심사 및 협상에 의한 낙찰자 결정기준", "기술용역 적격심사기준에 관한 훈령", "기술용역적격심사 세부기준"]:
        if act_mode == "procurement_route_and_subtype_required":
            act_mode = "procurement_route_and_object_required"
            
    active_for_rule = p.get('active_for_rule', False)
    active_for_procedure = p.get('active_for_procedure', False)
    judgment_eligible = p.get('judgment_eligible', True)
    
    # Enforce procedure_only logic overrides
    if act_mode == "procedure_only":
        active_for_rule = False
        active_for_procedure = True
        judgment_eligible = False

    req_slots = json.dumps(p.get('required_slots', []), ensure_ascii=False)
    route_scope = json.dumps(p.get('procurement_route_scope', []), ensure_ascii=False)
    sub_scope = json.dumps(p.get('project_subtype_scope', []), ensure_ascii=False)
    obj_scope = json.dumps(p.get('contract_object_scope', []), ensure_ascii=False)

    cur.execute("""
        UPDATE legal_source 
        SET active_for_rule = ?,
            activation_mode = ?,
            required_slots = ?,
            procurement_route_scope = ?,
            project_subtype_scope = ?,
            contract_object_scope = ?,
            active_for_procedure = ?,
            judgment_eligible = ?
        WHERE source_id = ?
    """, (
        active_for_rule, act_mode, req_slots, route_scope, sub_scope, obj_scope, 
        active_for_procedure, judgment_eligible, sid
    ))

conn.commit()
print("Patch applied to Staging DB successfully.")

# 4. Verification and Reports Generation
total_active = cur.execute("SELECT COUNT(*) FROM legal_source WHERE active_for_rule = 1").fetchone()[0]
total_proc_only = cur.execute("SELECT COUNT(*) FROM legal_source WHERE active_for_procedure = 1").fetchone()[0]
proc_eligible_err = cur.execute("SELECT COUNT(*) FROM legal_source WHERE activation_mode = 'procedure_only' AND judgment_eligible = 1").fetchone()[0]
mode_missing_err = cur.execute("SELECT COUNT(*) FROM legal_source WHERE active_for_rule = 1 AND activation_mode IS NULL").fetchone()[0]

print(f"Total Active for Rule: {total_active}")
print(f"Total Active for Procedure: {total_proc_only}")

# legal_import_validation_report_v0_1_3.json
validation_report = {
    "title": "Legal DB Import Validation Report v0.1.3",
    "total_sources": cur.execute("SELECT COUNT(*) FROM legal_source").fetchone()[0],
    "integrity_checks": {
        "orphan_jurisdictions": cur.execute("SELECT COUNT(*) FROM legal_jurisdiction_mapping WHERE source_id NOT IN (SELECT source_id FROM legal_source)").fetchone()[0],
        "orphan_buyers": cur.execute("SELECT COUNT(*) FROM legal_buyer_type_mapping WHERE source_id NOT IN (SELECT source_id FROM legal_source)").fetchone()[0],
        "orphan_overlays": cur.execute("SELECT COUNT(*) FROM legal_overlay_mapping WHERE source_id NOT IN (SELECT source_id FROM legal_source)").fetchone()[0],
        "orphan_seed_mappings": cur.execute("SELECT COUNT(*) FROM legal_source_seed_mapping WHERE canonical_source_id NOT IN (SELECT source_id FROM legal_source)").fetchone()[0]
    },
    "v0_1_3_checks": {
        "active_for_rule_count": total_active,
        "active_for_procedure_count": total_proc_only,
        "procedure_only_judgment_eligible": proc_eligible_err,
        "activation_mode_missing_in_active": mode_missing_err
    }
}
with open(os.path.join(base, 'legal_import_validation_report_v0_1_3.json'), 'w', encoding='utf-8') as f:
    json.dump(validation_report, f, ensure_ascii=False, indent=2)

# active_for_rule_filter_report_v0_1_3.json
active_true = cur.execute("SELECT normalized_title, activation_mode, registry_trust_level FROM legal_source WHERE active_for_rule = 1").fetchall()
filter_report = {
    "title": "Active For Rule Filter Report v0.1.3",
    "active_true_count": len(active_true),
    "active_false_count": cur.execute("SELECT COUNT(*) FROM legal_source WHERE active_for_rule = 0").fetchone()[0],
    "active_true_samples": [{"title": r[0], "activation_mode": r[1], "trust_level": r[2]} for r in active_true]
}
with open(os.path.join(base, 'active_for_rule_filter_report_v0_1_3.json'), 'w', encoding='utf-8') as f:
    json.dump(filter_report, f, ensure_ascii=False, indent=2)

# activation_mode_distribution_report_v0_1_3.json
mode_dist = cur.execute("SELECT activation_mode, COUNT(*) FROM legal_source WHERE activation_mode IS NOT NULL GROUP BY activation_mode").fetchall()
dist_report = {
    "title": "Activation Mode Distribution Report v0.1.3",
    "distribution": [{"activation_mode": r[0], "count": r[1]} for r in mode_dist]
}
with open(os.path.join(base, 'activation_mode_distribution_report_v0_1_3.json'), 'w', encoding='utf-8') as f:
    json.dump(dist_report, f, ensure_ascii=False, indent=2)

# procedure_only_filter_report_v0_1_3.json
proc_only_items = cur.execute("SELECT normalized_title, active_for_rule, judgment_eligible FROM legal_source WHERE active_for_procedure = 1").fetchall()
proc_report = {
    "title": "Procedure Only Filter Report v0.1.3",
    "procedure_only_count": len(proc_only_items),
    "items": [{"title": r[0], "active_for_rule": bool(r[1]), "judgment_eligible": bool(r[2])} for r in proc_only_items]
}
with open(os.path.join(base, 'procedure_only_filter_report_v0_1_3.json'), 'w', encoding='utf-8') as f:
    json.dump(proc_report, f, ensure_ascii=False, indent=2)

conn.close()
print("All reports generated successfully.")
