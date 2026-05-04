import sqlite3, os, json
sys_stdout = os.sys.stdout
base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
db_path = os.path.join(base, 'legal_db_v0_1_3.sqlite')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Backfill core_common for already active items missing activation_mode
cur.execute("UPDATE legal_source SET activation_mode = 'core_common' WHERE active_for_rule = 1 AND activation_mode IS NULL")
conn.commit()

mode_missing_err = cur.execute("SELECT COUNT(*) FROM legal_source WHERE active_for_rule = 1 AND activation_mode IS NULL").fetchone()[0]
print(f'Missing after backfill: {mode_missing_err}')

# Update validation report
report_path = os.path.join(base, 'legal_import_validation_report_v0_1_3.json')
with open(report_path, encoding='utf-8') as f:
    report = json.load(f)
report['v0_1_3_checks']['activation_mode_missing_in_active'] = mode_missing_err
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# Also update the active_for_rule_filter_report
active_true = cur.execute("SELECT normalized_title, activation_mode, registry_trust_level FROM legal_source WHERE active_for_rule = 1").fetchall()
filter_report_path = os.path.join(base, 'active_for_rule_filter_report_v0_1_3.json')
with open(filter_report_path, encoding='utf-8') as f:
    filter_report = json.load(f)
filter_report['active_true_samples'] = [{"title": r[0], "activation_mode": r[1], "trust_level": r[2]} for r in active_true]
with open(filter_report_path, 'w', encoding='utf-8') as f:
    json.dump(filter_report, f, ensure_ascii=False, indent=2)

conn.close()
