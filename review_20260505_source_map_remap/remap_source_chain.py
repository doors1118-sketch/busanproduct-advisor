"""
Source Map 재매핑 스크립트 v2.0

v1.0 대비 변경사항:
1. mapped_verified 판정 엄격화 (모든 primary가 verified + numeric resolved)
2. old unmatched_query_terms를 resolver 입력에 포함
3. remaining_gap_reason 재계산
4. related_source_details 생성
5. 지역제한/제3자단가 규칙 약칭 재투입
6. MAS 수치 미확정 유지
7. 감사 리포트 강화

금지사항 준수:
- source map 직접 덮어쓰기 금지 → .merged.v2.json 출력
- legal_db write 금지
- expected_value_hint 사용자 답변 출력 금지

생성일: 2026-05-05
"""

import json
import sqlite3
import re
import sys
import os
from collections import defaultdict
from pathlib import Path

# ──────────────────────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────────────────────
BASE_DIR = Path(r"c:\Users\COMTREE\Desktop\메뉴얼 제작")
CATALOG_PATH = BASE_DIR / "local_purchase_support_rule_catalog.json"
SMAP_PATH = BASE_DIR / "purchase_support_rule_source_map.json"
DB_PATH = BASE_DIR / "app" / "data" / "legal_db_v0_1_3.sqlite"
OUT_MERGED = BASE_DIR / "purchase_support_rule_source_map.merged.v2.json"
OUT_REPORT = BASE_DIR / "scratch" / "remap_audit_report_v2.txt"

sys.path.insert(0, str(BASE_DIR))
from app.data.law_alias_map import LAW_ALIAS_MAP, resolve_alias, parse_law_reference


# ──────────────────────────────────────────────────────────
# 1. 데이터 로드
# ──────────────────────────────────────────────────────────
with open(CATALOG_PATH, "r", encoding="utf-8") as f:
    catalog = json.load(f)

with open(SMAP_PATH, "r", encoding="utf-8") as f:
    source_map = json.load(f)

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()


# ──────────────────────────────────────────────────────────
# 2. DB 인덱스 구축
# ──────────────────────────────────────────────────────────
cursor.execute("""
    SELECT source_id, source_name, source_type, law_category, review_status
    FROM legal_source
""")
db_rows = cursor.fetchall()

name_to_id: dict[str, str] = {}
id_to_row: dict[str, dict] = {}

for row in db_rows:
    sid, sname, stype, lcat, rstatus = row
    name_to_id[sname] = sid
    id_to_row[sid] = {
        "source_id": sid,
        "source_name": sname,
        "source_type": stype,
        "law_category": lcat,
        "review_status": rstatus,
    }

conn.close()


# ──────────────────────────────────────────────────────────
# 3. 무관 source 제거 기준
# ──────────────────────────────────────────────────────────
IRRELEVANT_TITLE_KEYWORDS = {
    "공정거래위원회", "국가인권위원회", "보훈", "군수품", "자회사",
    "경쟁촉진을 위한 공사의 수의계약사유", "국방전자조달", "국방부",
    "군시설", "해양수산부", "산림청", "전투근무", "장비정비",
    "국외조달", "국제운송", "재외공관", "매장유산", "우편기계",
    "국가유산수리",
}

# 너무 일반적인 용어 (부분 매칭 스킵 대상)
GENERAL_TERMS = {
    "수의계약", "제한경쟁", "적격심사", "지역제한", "공동계약",
    "입찰", "낙찰", "특례", "우선구매", "지역업체", "평가기준",
    "1인 견적", "2인 이상 견적", "내부규정", "조례", "가점",
    "주된 영업소", "입찰참가자격 제한", "지역업체 가점",
    "지역업체 참여도", "지역업체 배점", "다수공급자계약",
    "지역상품", "사회적가치", "중증장애인생산품",
    "사회적경제기업", "장애인생산품", "표준평가방식",
    "종합평가방식", "기술평가", "제안서평가",
    "종합쇼핑몰", "지역업체 등록현황",
    "중소기업 제조품목", "일반제품", "기준금액",
    "직접 납품요구", "2단계경쟁 예외",
    "제3자단가계약", "제3자를 위한 단가계약", "납품요구",
    "직접생산확인증명서", "성능인증", "기술개발제품",
    "혁신제품", "우수조달", "물품구매", "일반용역",
    "소액수의계약", "금액 초과",
}


def is_irrelevant_source(source_name: str) -> bool:
    for kw in IRRELEVANT_TITLE_KEYWORDS:
        if kw in source_name:
            return True
    return False


# ──────────────────────────────────────────────────────────
# 4. 규칙별 올바른 source_id 산출
#    v2: old unmatched_query_terms도 resolver 입력에 포함
# ──────────────────────────────────────────────────────────
def find_correct_source_ids(
    rule: dict, old_entry: dict
) -> tuple[list[str], list[str], list[str]]:
    """
    Returns: (primary_ids, related_ids, resolved_terms)
    """
    # v2: catalog query terms + old unmatched terms 합쳐서 중복 제거
    catalog_terms = rule.get("legal_basis_query_terms", [])
    old_unmatched = old_entry.get("unmatched_query_terms", [])
    query_terms = list(dict.fromkeys(catalog_terms + old_unmatched))

    primary_ids = []
    related_ids = []
    resolved_terms = []

    for term in query_terms:
        # 1) 약칭 직접 매칭
        full_name = resolve_alias(term)
        if full_name and full_name in name_to_id:
            sid = name_to_id[full_name]
            row = id_to_row[sid]
            if row["source_type"] in ("law", "law_decree", "law_rule"):
                if sid not in primary_ids:
                    primary_ids.append(sid)
            else:
                if sid not in related_ids:
                    related_ids.append(sid)
            resolved_terms.append(term)
            continue

        # 2) 조항 참조 ("지방계약법 시행령 제25조")
        alias, article = parse_law_reference(term)
        if alias:
            full_name = resolve_alias(alias)
            if full_name and full_name in name_to_id:
                sid = name_to_id[full_name]
                row = id_to_row[sid]
                if row["source_type"] in ("law", "law_decree", "law_rule"):
                    if sid not in primary_ids:
                        primary_ids.append(sid)
                else:
                    if sid not in related_ids:
                        related_ids.append(sid)
                resolved_terms.append(term)
                continue

        # 3) 정식명 직접 매칭
        if term in name_to_id:
            sid = name_to_id[term]
            if sid not in related_ids and sid not in primary_ids:
                related_ids.append(sid)
            resolved_terms.append(term)
            continue

        # 4) 일반 용어는 스킵
        if term in GENERAL_TERMS:
            continue

    return primary_ids, related_ids, resolved_terms


def build_source_detail(sid: str, is_alias_resolved: bool) -> dict:
    """source_id로부터 detail dict 생성 (primary/related 공용)"""
    row = id_to_row.get(sid, {})
    if not row:
        return {"id": sid, "title": "[UNKNOWN]", "status": "unknown",
                "rank_score": 0, "mapping_method": "unknown"}

    if row["review_status"] == "verified":
        review_score = 50
    elif row["review_status"] == "candidate_needs_review":
        review_score = 20
    else:
        review_score = 10

    source_type_score = 30 if row["source_type"] in ("law", "law_decree", "law_rule") else 20
    alias_bonus = 30 if is_alias_resolved else 15

    return {
        "id": sid,
        "title": row["source_name"],
        "status": row["review_status"],
        "source_type": row["source_type"],
        "law_category": row["law_category"],
        "rank_score": review_score + source_type_score + alias_bonus,
        "mapping_method": "alias_resolved" if is_alias_resolved else "keyword_match",
    }


# ──────────────────────────────────────────────────────────
# 5. source_chain_status 판정 (v2 엄격 기준)
# ──────────────────────────────────────────────────────────
def determine_status(
    old_status: str,
    final_primary_ids: list[str],
    new_unmatched: list[str],
    numeric_parameters: list[dict],
) -> str:
    """
    mapped_verified 조건 (모두 만족해야 함):
      1) primary_source_ids 비어있지 않음
      2) unmatched_query_terms 비어있음
      3) 모든 primary source가 review_status == verified
      4) numeric_parameters가 없거나 모든 resolved_value가 not None
      5) requires_manual_numeric_verification=true + resolved_value=null 없어야 함
    """
    if old_status == "company_api_mapping_required":
        return old_status

    has_primary = len(final_primary_ids) > 0
    has_unmatched = len(new_unmatched) > 0
    has_unresolved_numeric = any(
        p.get("resolved_value") is None
        and p.get("requires_manual_numeric_verification", False)
        for p in numeric_parameters
    )
    has_candidate_primary = any(
        id_to_row.get(sid, {}).get("review_status") != "verified"
        for sid in final_primary_ids
        if sid in id_to_row
    )

    if not has_primary:
        return "pending_resolution"
    elif has_unmatched or has_unresolved_numeric:
        return "partial_mapped"
    elif has_candidate_primary:
        return "mapped_candidate"
    else:
        return "mapped_verified"


# ──────────────────────────────────────────────────────────
# 6. remaining_gap_reason 재계산 (v2)
# ──────────────────────────────────────────────────────────
def compute_gap_reason(
    final_primary_ids: list[str],
    new_unmatched: list[str],
    numeric_parameters: list[dict],
) -> str:
    has_unresolved_numeric = any(
        p.get("resolved_value") is None
        and p.get("requires_manual_numeric_verification", False)
        for p in numeric_parameters
    )
    has_candidate_primary = any(
        id_to_row.get(sid, {}).get("review_status") != "verified"
        for sid in final_primary_ids
        if sid in id_to_row
    )

    if has_unresolved_numeric:
        return "Numeric parameters pending manual verification"
    elif len(new_unmatched) > 0:
        return f"Unmatched required terms: {', '.join(new_unmatched)}"
    elif has_candidate_primary:
        return "Candidate source requires manual review"
    else:
        return "None"


# ──────────────────────────────────────────────────────────
# 7. 메인 교정 루프
# ──────────────────────────────────────────────────────────
merged_map = {}
audit_lines = []
stats = defaultdict(int)

for rule in catalog:
    rule_id = rule["rule_id"]
    old_entry = source_map.get(rule_id, {})
    old_primary_ids = old_entry.get("primary_source_ids", [])
    old_status = old_entry.get("source_chain_status", "unknown")
    old_unmatched = old_entry.get("unmatched_query_terms", [])

    # 올바른 source_id 산출 (v2: old unmatched 포함)
    new_primary_ids, new_related_ids, resolved_terms = find_correct_source_ids(rule, old_entry)

    # 기존 primary에서 무관 source 제거
    cleaned_old_primary = []
    removed_sources = []
    for sid in old_primary_ids:
        if sid in id_to_row:
            row = id_to_row[sid]
            if is_irrelevant_source(row["source_name"]):
                removed_sources.append(row["source_name"])
            else:
                cleaned_old_primary.append(sid)
        else:
            removed_sources.append(f"[DB missing] {sid[:8]}...")

    # 병합: 약칭 매핑 우선 + 기존 cleaned
    final_primary_ids = list(new_primary_ids)
    for sid in cleaned_old_primary:
        if sid not in final_primary_ids:
            final_primary_ids.append(sid)

    # related_ids 병합
    old_related_ids = old_entry.get("related_source_ids", [])
    final_related_ids = list(new_related_ids)
    for sid in old_related_ids:
        if sid not in final_related_ids:
            final_related_ids.append(sid)

    # v2.1: primary → related 자동 분류 (근거 우선순위 정제)
    # 기준: alias_resolved이거나 verified이거나 법령 타입이면 primary 유지
    #        그 외 keyword_match + candidate_needs_review + 비법령 → related로 이동
    # 안전장치: demotion 후 primary가 비게 되면 롤백 (데이터 손실 방지)
    LAW_SOURCE_TYPES = {"law", "law_decree", "law_rule"}
    demoted_sources = []
    refined_primary = []
    for sid in final_primary_ids:
        is_alias = sid in new_primary_ids
        row = id_to_row.get(sid, {})
        is_law_type = row.get("source_type", "") in LAW_SOURCE_TYPES
        is_verified = row.get("review_status", "") == "verified"

        if is_alias or is_law_type or is_verified:
            refined_primary.append(sid)
        else:
            demoted_sources.append((sid, row.get("source_name", sid[:12])))

    if refined_primary:
        # demotion 실행: demoted를 related로 이동
        for sid, name in demoted_sources:
            if sid not in final_related_ids:
                final_related_ids.append(sid)
        final_primary_ids = refined_primary
        demoted_names = [name for _, name in demoted_sources]
    else:
        # primary가 비게 되면 롤백 — 기존 배치 유지
        demoted_sources = []
        demoted_names = []

    # unmatched 업데이트 (해소된 것 제거)
    # v2: catalog terms + old unmatched 합친 것에서 resolved 제거
    all_terms = list(dict.fromkeys(
        rule.get("legal_basis_query_terms", []) + old_unmatched
    ))
    new_unmatched = [t for t in all_terms if t not in resolved_terms and t not in GENERAL_TERMS]

    # numeric_parameters 가져오기
    numeric_parameters = old_entry.get("numeric_parameters", [])

    # v2: source_chain_status 엄격 판정
    new_status = determine_status(
        old_status, final_primary_ids, new_unmatched, numeric_parameters
    )

    # v2: remaining_gap_reason 재계산
    gap_reason = compute_gap_reason(final_primary_ids, new_unmatched, numeric_parameters)

    # primary_source_details 구성
    primary_details = []
    for sid in final_primary_ids:
        is_alias = sid in new_primary_ids
        detail = build_source_detail(sid, is_alias)
        primary_details.append(detail)
    primary_details.sort(key=lambda x: x["rank_score"], reverse=True)

    # v2: related_source_details 구성 (기존에는 빈 배열)
    related_details = []
    for sid in final_related_ids:
        is_alias = sid in new_related_ids
        detail = build_source_detail(sid, is_alias)
        related_details.append(detail)
    related_details.sort(key=lambda x: x["rank_score"], reverse=True)

    # numeric_parameters 내 candidate_source_ids 업데이트
    updated_numeric = []
    for np in numeric_parameters:
        np_copy = dict(np)
        if "candidate_source_ids" in np_copy:
            np_copy["candidate_source_ids"] = final_primary_ids
        updated_numeric.append(np_copy)

    # merged entry 구성
    merged_entry = {
        "rule_id": rule_id,
        "display_name": rule.get("display_name", ""),
        "category": rule.get("category", ""),
        "primary_source_ids": final_primary_ids,
        "related_source_ids": final_related_ids,
        "matched_query_terms": {
            "original": [t for t in rule.get("legal_basis_query_terms", []) if t in resolved_terms],
            "alias_resolved": resolved_terms,
        },
        "unmatched_query_terms": new_unmatched,
        "numeric_parameters": updated_numeric,
        "source_chain_status": new_status,
        "primary_source_details": primary_details,
        "related_source_details": related_details,
        "high_priority_source_count": len([d for d in primary_details if d["rank_score"] >= 80]),
        "remaining_gap_reason": gap_reason,
    }

    merged_map[rule_id] = merged_entry

    # 감사 로그
    changes = []
    if removed_sources:
        changes.append(f"  removed irrelevant: {len(removed_sources)}")
        for s in removed_sources:
            changes.append(f"    - {s}")
    if new_primary_ids:
        changes.append(f"  alias-resolved primary: {len(new_primary_ids)}")
        for sid in new_primary_ids:
            row = id_to_row.get(sid, {})
            changes.append(f"    + {row.get('source_name', sid)}")
    if new_related_ids:
        changes.append(f"  alias-resolved related: {len(new_related_ids)}")
        for sid in new_related_ids:
            row = id_to_row.get(sid, {})
            changes.append(f"    + {row.get('source_name', sid)}")
    if demoted_names:
        changes.append(f"  demoted to related: {len(demoted_names)}")
        for s in demoted_names:
            changes.append(f"    > {s}")
    if resolved_terms:
        changes.append(f"  resolved terms: {resolved_terms}")
    if old_status != new_status:
        changes.append(f"  status: {old_status} -> {new_status}")
    if gap_reason != old_entry.get("remaining_gap_reason", ""):
        changes.append(f"  gap_reason: {gap_reason}")

    if changes:
        stats["changed"] += 1
        audit_lines.append(f"\n{'='*60}")
        audit_lines.append(f"[{rule_id}] {rule.get('display_name', '')}")
        audit_lines.append(f"  before: {old_status} (primary={len(old_primary_ids)}, unmatched={old_unmatched})")
        audit_lines.append(f"  after:  {new_status} (primary={len(final_primary_ids)}, unmatched={new_unmatched})")
        audit_lines.extend(changes)
    else:
        stats["unchanged"] += 1


# ──────────────────────────────────────────────────────────
# 8. 결과 저장
# ──────────────────────────────────────────────────────────
with open(OUT_MERGED, "w", encoding="utf-8") as f:
    json.dump(merged_map, f, ensure_ascii=False, indent=2)

# 감사 리포트
status_summary = defaultdict(int)
for entry in merged_map.values():
    status_summary[entry["source_chain_status"]] += 1

# numeric unresolved 목록
numeric_unresolved_rules = []
for rule_id, entry in merged_map.items():
    for np in entry.get("numeric_parameters", []):
        if np.get("resolved_value") is None and np.get("requires_manual_numeric_verification"):
            numeric_unresolved_rules.append(rule_id)
            break

report_header = [
    "=" * 60,
    "Source Map v2 Audit Report",
    f"Generated: 2026-05-05",
    f"Total rules: {len(merged_map)}",
    f"Changed: {stats['changed']} / Unchanged: {stats['unchanged']}",
    "",
    "=== source_chain_status distribution (after) ===",
]
for status, cnt in sorted(status_summary.items(), key=lambda x: -x[1]):
    report_header.append(f"  {status}: {cnt}")

report_header.append("")
report_header.append("=== Numeric unresolved rules ===")
if numeric_unresolved_rules:
    for rid in numeric_unresolved_rules:
        report_header.append(f"  {rid}")
else:
    report_header.append("  (none)")

report_header.append("")
report_header.append("=== Change details ===")

with open(OUT_REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(report_header))
    f.write("\n".join(audit_lines))

print(f"[OK] merged v2: {OUT_MERGED}")
print(f"[OK] audit v2: {OUT_REPORT}")
print(f"\n[SUMMARY]")
print(f"  total: {len(merged_map)}")
print(f"  changed: {stats['changed']}")
print(f"  unchanged: {stats['unchanged']}")
print(f"\n[STATUS]")
for status, cnt in sorted(status_summary.items(), key=lambda x: -x[1]):
    print(f"  {status}: {cnt}")
print(f"\n[NUMERIC UNRESOLVED] {len(numeric_unresolved_rules)} rules")
