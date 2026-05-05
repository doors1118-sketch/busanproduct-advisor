"""
Source Map merged v2 검증 스크립트

v1 대비 추가 검증:
- mapped_verified에 candidate_needs_review primary 없어야 함
- mapped_verified에 unresolved numeric parameter 없어야 함
- remaining_gap_reason이 numeric unresolved에서 None이면 FAIL
- old unmatched가 resolver에 재투입되는지 확인
- R_REGIONAL_RESTRICTION_GOODS에 지방/국가계약법 시행령 매핑 확인
- R_THIRD_PARTY_UNIT_PRICE에 조달사업법 시행령 매핑 확인
- related_source_ids 있으면 related_source_details 비어있지 않아야 함
- expected_value_hint 있고 resolved_value 없는데 parameter_status==resolved이면 FAIL
- 무관 source keyword 검사 유지
- 모든 source_id DB 존재 확인
"""
import json
import sqlite3
from pathlib import Path
from collections import Counter

BASE_DIR = Path(r"c:\Users\COMTREE\Desktop\메뉴얼 제작")
OLD_PATH = BASE_DIR / "purchase_support_rule_source_map.json"
NEW_PATH = BASE_DIR / "purchase_support_rule_source_map.merged.v2.json"
DB_PATH = BASE_DIR / "app" / "data" / "legal_db_v0_1_3.sqlite"
OUT = BASE_DIR / "scratch" / "remap_verify_result_v2.txt"

with open(OLD_PATH, "r", encoding="utf-8") as f:
    old_map = json.load(f)
with open(NEW_PATH, "r", encoding="utf-8") as f:
    new_map = json.load(f)

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

lines = []
passed = 0
failed = 0
warnings = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        lines.append(f"  [PASS] {label}")
    else:
        failed += 1
        lines.append(f"  [FAIL] {label}")
    if detail:
        lines.append(f"         {detail}")


def warn(label, detail=""):
    global warnings
    warnings += 1
    lines.append(f"  [WARN] {label}")
    if detail:
        lines.append(f"         {detail}")


lines.append("=" * 60)
lines.append("Source Map Merged v2 Verification Report")
lines.append("=" * 60)

# ── TEST 1: 규칙 수 일치 ──
lines.append("\n--- TEST 1: Rule count match ---")
check("old/new rule count identical", len(old_map) == len(new_map),
      f"old={len(old_map)}, new={len(new_map)}")

# ── TEST 2: R_DIRECT_GENERAL_SMALL_AMOUNT 핵심 교정 ──
lines.append("\n--- TEST 2: R_DIRECT_GENERAL_SMALL_AMOUNT corrections ---")
rule_key = "R_DIRECT_GENERAL_SMALL_AMOUNT"
old_entry = old_map[rule_key]
new_entry = new_map[rule_key]
new_titles = [d["title"] for d in new_entry.get("primary_source_details", [])]

check("Irrelevant '공정거래위원회' removed",
      not any("공정거래위원회" in t for t in new_titles))
check("지방계약법 시행령 added",
      any("지방자치단체를 당사자로 하는 계약에 관한 법률 시행령" in t for t in new_titles))
check("국가계약법 시행령 added",
      any("국가를 당사자로 하는 계약에 관한 법률 시행령" in t for t in new_titles))

# ── TEST 3: 무관 source 전수 제거 ──
lines.append("\n--- TEST 3: Irrelevant source removal ---")
irrelevant_kws = ["공정거래위원회", "국가인권위원회", "보훈", "자회사", "군수품"]
remaining_irrelevant = 0
for rule_id, entry in new_map.items():
    for detail in entry.get("primary_source_details", []):
        for kw in irrelevant_kws:
            if kw in detail.get("title", ""):
                remaining_irrelevant += 1
                warn(f"Remaining irrelevant: [{rule_id}] {detail['title']}")
check("All irrelevant sources removed", remaining_irrelevant == 0,
      f"remaining={remaining_irrelevant}")

# ── TEST 4: mapped_verified 엄격성 ──
lines.append("\n--- TEST 4: mapped_verified strictness ---")
for rule_id, entry in new_map.items():
    if entry["source_chain_status"] != "mapped_verified":
        continue

    # 4a: no candidate_needs_review in primary
    for detail in entry.get("primary_source_details", []):
        if detail.get("status") == "candidate_needs_review":
            check(f"[{rule_id}] no candidate_needs_review in mapped_verified primary", False,
                  f"found: {detail['title']}")
            break
    else:
        check(f"[{rule_id}] all primary sources verified", True)

    # 4b: no unresolved numeric
    has_unresolved = any(
        p.get("resolved_value") is None and p.get("requires_manual_numeric_verification")
        for p in entry.get("numeric_parameters", [])
    )
    check(f"[{rule_id}] no unresolved numeric in mapped_verified", not has_unresolved)

# ── TEST 5: remaining_gap_reason consistency ──
lines.append("\n--- TEST 5: remaining_gap_reason consistency ---")
gap_failures = 0
for rule_id, entry in new_map.items():
    has_unresolved = any(
        p.get("resolved_value") is None and p.get("requires_manual_numeric_verification")
        for p in entry.get("numeric_parameters", [])
    )
    gap = entry.get("remaining_gap_reason", "")
    if has_unresolved and gap == "None":
        gap_failures += 1
        check(f"[{rule_id}] gap_reason not None when numeric unresolved", False,
              f"gap={gap}")
check("No numeric-unresolved rules with gap_reason=None", gap_failures == 0)

# ── TEST 6: old unmatched re-input ──
lines.append("\n--- TEST 6: old unmatched terms re-input ---")

# R_REGIONAL_RESTRICTION_GOODS had unmatched "지방계약법 시행령"
rr_goods = new_map.get("R_REGIONAL_RESTRICTION_GOODS", {})
resolved_terms = rr_goods.get("matched_query_terms", {}).get("alias_resolved", [])
check("R_REGIONAL_RESTRICTION_GOODS: '지방계약법 시행령' resolved",
      "지방계약법 시행령" in resolved_terms,
      f"resolved={resolved_terms}")

# R_THIRD_PARTY had unmatched "조달사업법 시행령"
rtp = new_map.get("R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW", {})
resolved_terms_rtp = rtp.get("matched_query_terms", {}).get("alias_resolved", [])
check("R_THIRD_PARTY: '조달사업법 시행령' resolved",
      "조달사업법 시행령" in resolved_terms_rtp,
      f"resolved={resolved_terms_rtp}")

# ── TEST 7: Regional restriction rules have 지방/국가계약법 시행령 ──
lines.append("\n--- TEST 7: Regional restriction core law mapping ---")
cursor.execute("SELECT source_id FROM legal_source WHERE source_name='지방자치단체를 당사자로 하는 계약에 관한 법률 시행령'")
local_sid = cursor.fetchone()
cursor.execute("SELECT source_id FROM legal_source WHERE source_name='국가를 당사자로 하는 계약에 관한 법률 시행령'")
nat_sid = cursor.fetchone()

if local_sid and nat_sid:
    local_sid = local_sid[0]
    nat_sid = nat_sid[0]
    for rid in ["R_REGIONAL_RESTRICTION_GOODS", "R_REGIONAL_RESTRICTION_SERVICE", "R_REGIONAL_RESTRICTION_CONSTRUCTION"]:
        entry = new_map.get(rid, {})
        pids = entry.get("primary_source_ids", [])
        check(f"[{rid}] has 지방계약법 시행령", local_sid in pids)
        check(f"[{rid}] has 국가계약법 시행령", nat_sid in pids)

# ── TEST 8: R_THIRD_PARTY has 조달사업법 시행령 ──
lines.append("\n--- TEST 8: Third party rule has 조달사업법 시행령 ---")
cursor.execute("SELECT source_id FROM legal_source WHERE source_name='조달사업에 관한 법률 시행령'")
jodal_sid = cursor.fetchone()
if jodal_sid:
    jodal_sid = jodal_sid[0]
    rtp_entry = new_map.get("R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW", {})
    check("R_THIRD_PARTY has 조달사업법 시행령", jodal_sid in rtp_entry.get("primary_source_ids", []))

# ── TEST 9: related_source_details populated ──
lines.append("\n--- TEST 9: related_source_details populated ---")
details_missing = 0
for rule_id, entry in new_map.items():
    rel_ids = entry.get("related_source_ids", [])
    rel_details = entry.get("related_source_details", [])
    if len(rel_ids) > 0 and len(rel_details) == 0:
        details_missing += 1
        warn(f"[{rule_id}] related_source_ids={len(rel_ids)} but details empty")
check("related_source_details populated when ids exist", details_missing == 0,
      f"missing={details_missing}")

# ── TEST 10: numeric parameter_status integrity ──
lines.append("\n--- TEST 10: numeric parameter_status integrity ---")
param_violations = 0
for rule_id, entry in new_map.items():
    for p in entry.get("numeric_parameters", []):
        if p.get("resolved_value") is None and p.get("parameter_status") == "resolved":
            param_violations += 1
            check(f"[{rule_id}] no resolved status without resolved_value", False,
                  f"param={p.get('parameter_ref')}")
check("No parameter_status=resolved without resolved_value", param_violations == 0)

# ── TEST 11: all source_ids exist in DB ──
lines.append("\n--- TEST 11: all source_ids exist in DB ---")
all_sids = set()
for entry in new_map.values():
    all_sids.update(entry.get("primary_source_ids", []))
    all_sids.update(entry.get("related_source_ids", []))
missing_in_db = 0
for sid in all_sids:
    cursor.execute("SELECT COUNT(*) FROM legal_source WHERE source_id=?", (sid,))
    cnt = cursor.fetchone()[0]
    if cnt == 0:
        missing_in_db += 1
        warn(f"DB missing source_id: {sid[:12]}...")
check("All source_ids exist in DB", missing_in_db == 0, f"missing={missing_in_db}")

# ── TEST 12: status distribution improvement ──
lines.append("\n--- TEST 12: status distribution improvement ---")
old_status_dist = Counter(e["source_chain_status"] for e in old_map.values())
new_status_dist = Counter(e["source_chain_status"] for e in new_map.values())
check("pending_resolution reduced",
      new_status_dist.get("pending_resolution", 0) < old_status_dist.get("pending_resolution", 0),
      f"old={old_status_dist.get('pending_resolution', 0)}, new={new_status_dist.get('pending_resolution', 0)}")

lines.append(f"\n  Status distribution comparison:")
lines.append(f"  {'status':<35} {'old':>4} {'new':>4}")
all_statuses = set(list(old_status_dist.keys()) + list(new_status_dist.keys()))
for s in sorted(all_statuses):
    lines.append(f"  {s:<35} {old_status_dist.get(s,0):>4} {new_status_dist.get(s,0):>4}")

conn.close()

# ── RESULT ──
lines.append("\n" + "=" * 60)
lines.append(f"RESULT: {passed} PASSED / {failed} FAILED / {warnings} WARNINGS")
lines.append("=" * 60)

result_text = "\n".join(lines)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(result_text)

print(f"[VERIFY v2] {passed} PASSED / {failed} FAILED / {warnings} WARNINGS")
print(f"[SAVED] {OUT}")
