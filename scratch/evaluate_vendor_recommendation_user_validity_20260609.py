from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


CASES: list[dict[str, Any]] = [
    {
        "id": "goods_led",
        "q": "LED 조명 5천만원 구매 업체 추천",
        "budget_krw": 50_000_000,
        "intent": "물품",
        "row_any": ["LED", "조명", "등기구"],
        "policy_expected": True,
    },
    {
        "id": "goods_desktop",
        "q": "데스크톱 컴퓨터 4천만원 구매 부산업체",
        "budget_krw": 40_000_000,
        "intent": "물품",
        "row_any": ["컴퓨터", "데스크", "PC"],
        "policy_expected": True,
    },
    {
        "id": "goods_toner",
        "q": "정품토너 구매 업체 추천",
        "budget_krw": 20_000_000,
        "intent": "물품",
        "row_any": ["토너"],
        "policy_expected": True,
    },
    {
        "id": "goods_projector",
        "q": "비디오프로젝터 구매 업체",
        "budget_krw": 45_000_000,
        "intent": "물품",
        "row_any": ["프로젝터", "비디오"],
        "policy_expected": True,
    },
    {
        "id": "goods_switchboard",
        "q": "분전반 구매 업체",
        "budget_krw": 80_000_000,
        "intent": "물품",
        "row_any": ["분전반", "배전반"],
        "policy_expected": True,
    },
    {
        "id": "service_event",
        "q": "발대식 행사 용역 업체 추천",
        "budget_krw": 200_000_000,
        "intent": "용역",
        "row_any": ["행사", "이벤트", "공연", "전시"],
        "policy_expected": False,
    },
    {
        "id": "service_translation",
        "q": "번역용역 부산 업체 추천",
        "budget_krw": 40_000_000,
        "intent": "용역",
        "row_any": ["번역", "통역"],
        "policy_expected": False,
    },
    {
        "id": "service_cleaning",
        "q": "건물 청소용역 부산업체",
        "budget_krw": 70_000_000,
        "intent": "용역",
        "row_any": ["청소", "환경미화"],
        "policy_expected": False,
    },
    {
        "id": "service_security",
        "q": "청사 경비용역 부산 업체",
        "budget_krw": 80_000_000,
        "intent": "용역",
        "row_any": ["경비", "시설경비"],
        "policy_expected": False,
    },
    {
        "id": "work_electric",
        "q": "전기공사 부산 업체",
        "budget_krw": 100_000_000,
        "intent": "공사",
        "row_any": ["전기공사"],
        "policy_expected": False,
        "capacity_expected": True,
    },
    {
        "id": "work_communication",
        "q": "정보통신공사 업체",
        "budget_krw": 100_000_000,
        "intent": "공사",
        "row_any": ["정보통신"],
        "policy_expected": False,
        "capacity_expected": True,
    },
    {
        "id": "work_fire",
        "q": "소방시설공사 업체",
        "budget_krw": 100_000_000,
        "intent": "공사",
        "row_any": ["소방"],
        "policy_expected": False,
        "capacity_expected": True,
    },
    {
        "id": "policy_women_led",
        "q": "여성기업 LED 조명 업체",
        "budget_krw": 50_000_000,
        "intent": "정책기업+물품",
        "row_any": ["LED", "조명"],
        "policy_expected": True,
        "policy_company_expected": "여성기업",
    },
    {
        "id": "policy_disabled_cleaning",
        "q": "장애인기업 청소용역 업체",
        "budget_krw": 50_000_000,
        "intent": "정책기업+용역",
        "row_any": ["청소", "환경미화"],
        "policy_expected": False,
        "policy_company_expected": "장애인기업",
    },
    {
        "id": "venture_order_switchboard",
        "q": "분전반 벤처나라 거래실적 업체",
        "budget_krw": 50_000_000,
        "intent": "벤처나라+물품",
        "row_any": ["분전반", "배전반"],
        "policy_expected": True,
        "venture_expected": True,
    },
]


CONVENIENCE_FIELDS = (
    "shopping_mall_status_label",
    "mas_status_label",
    "direct_production_certificate_status",
    "certified_product_labels",
    "policy_company_labels",
    "sme_competition_product_label",
    "cooperative_purchase_route_label",
    "construction_capacity_summary",
    "venture_nara_product_summary",
    "venture_nara_order_summary",
)


def contains_any(text: str, needles: list[str]) -> bool:
    folded = text.lower()
    return any(needle.lower() in folded for needle in needles)


def is_positive_value(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    negative_terms = ("없음", "미확인", "확인 필요", "DB 등록정보 없음", "미검증")
    return not any(term in text for term in negative_terms)


def row_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in (
            "company_name",
            "main_products",
            "license_or_business_type",
            "matched_query_label",
            "shopping_mall_product_summary",
            "mas_product_summary",
            "direct_production_certificate_products",
            "certified_product_summary",
        )
    )


def evaluate_case(base_url: str, case: dict[str, Any], timeout_sec: float, max_latency_ms: int) -> dict[str, Any]:
    params = {
        "q": case["q"],
        "region": "busan",
        "limit": 10,
        "budget_krw": case.get("budget_krw") or "",
        "include_product_policy": "true",
    }
    started = time.perf_counter()
    response = requests.get(f"{base_url.rstrip('/')}/vendor-recommendations/search", params=params, timeout=timeout_sec)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    data = response.json()
    rows = [row for row in data.get("rows") or [] if isinstance(row, dict)]
    top5_text = " ".join(row_text(row) for row in rows[:5])
    top = rows[0] if rows else {}
    policy_summary = data.get("item_policy_summary") or {}
    policy_pref = data.get("policy_preference_summary") or {}
    active_rows = [
        row for row in rows if str(row.get("business_status") or "").lower() in {"active", "unknown", ""}
    ]
    bad_status_rows = [
        row.get("company_name")
        for row in rows
        if str(row.get("business_status") or "").lower() in {"closed", "suspended", "inactive"}
    ]
    convenience_hits = [
        field
        for field in CONVENIENCE_FIELDS
        if any(is_positive_value(row.get(field)) for row in rows[:5])
    ]
    labels_present = all(
        top.get(field)
        for field in ("company_name", "business_status_label", "business_status_freshness_label", "budget_review_hint", "recommended_checks")
    ) if top else False
    capacity_ok = True
    if case.get("capacity_expected"):
        capacity_ok = any(is_positive_value(row.get("construction_capacity_summary")) for row in rows[:5])
    venture_ok = True
    if case.get("venture_expected"):
        venture_ok = any(is_positive_value(row.get("venture_nara_order_summary")) or is_positive_value(row.get("venture_nara_product_summary")) for row in rows[:10])
    policy_company_ok = True
    if case.get("policy_company_expected"):
        expected = case["policy_company_expected"]
        labels = " ".join(str(row.get("policy_company_labels") or "") for row in rows[:10])
        pref_status = str(policy_pref.get("status") or "")
        policy_company_ok = expected in labels or pref_status in {"matched", "not_found_in_candidates"}

    policy_ok = True
    if case.get("policy_expected"):
        policy_ok = policy_summary.get("status") == "matched" and bool(policy_summary.get("matched_products"))
    else:
        policy_ok = policy_summary.get("status") in {"not_requested", "matched", "not_found_or_unavailable"}

    checks = {
        "status_code": response.status_code,
        "count": len(rows),
        "latency_ok": elapsed_ms <= max_latency_ms,
        "intent_match": contains_any(top5_text, case["row_any"]),
        "no_closed_or_suspended": not bad_status_rows,
        "business_labels_present": labels_present,
        "policy_ok": policy_ok,
        "convenience_evidence_count": len(convenience_hits),
        "capacity_ok": capacity_ok,
        "venture_ok": venture_ok,
        "policy_company_ok": policy_company_ok,
    }
    score = 0
    weights = {
        "count": 15,
        "latency_ok": 10,
        "intent_match": 25,
        "no_closed_or_suspended": 15,
        "business_labels_present": 10,
        "policy_ok": 10,
        "capacity_ok": 5,
        "venture_ok": 5,
        "policy_company_ok": 5,
    }
    score += weights["count"] if checks["count"] > 0 else 0
    for key in ("latency_ok", "intent_match", "no_closed_or_suspended", "business_labels_present", "policy_ok", "capacity_ok", "venture_ok", "policy_company_ok"):
        score += weights[key] if checks[key] else 0

    return {
        "id": case["id"],
        "q": case["q"],
        "intent": case["intent"],
        "elapsed_ms": elapsed_ms,
        "score": score,
        "grade": "양호" if score >= 85 else "보통" if score >= 70 else "미흡",
        "checks": checks,
        "convenience_hits": convenience_hits,
        "bad_status_rows": bad_status_rows,
        "policy_status": policy_summary.get("status"),
        "policy_preference_status": policy_pref.get("status"),
        "first_company": top.get("company_name", ""),
        "first_match": top.get("matched_query_label", ""),
        "first_business_status": top.get("business_status_label", ""),
        "first_freshness": top.get("business_status_freshness_label", ""),
        "first_convenience": {field: top.get(field) for field in CONVENIENCE_FIELDS if top.get(field)},
        "rows_sample": [
            {
                "company_name": row.get("company_name"),
                "matched_query_label": row.get("matched_query_label"),
                "business_status_label": row.get("business_status_label"),
                "business_status_freshness_label": row.get("business_status_freshness_label"),
                "policy_company_labels": row.get("policy_company_labels"),
                "shopping_mall_status_label": row.get("shopping_mall_status_label"),
                "mas_status_label": row.get("mas_status_label"),
                "direct_production_certificate_status": row.get("direct_production_certificate_status"),
                "construction_capacity_summary": row.get("construction_capacity_summary"),
                "venture_nara_order_summary": row.get("venture_nara_order_summary"),
                "review_score": row.get("review_score"),
            }
            for row in rows[:3]
        ],
    }


def write_report(path: Path, records: list[dict[str, Any]], base_url: str) -> None:
    avg_score = round(sum(record["score"] for record in records) / len(records), 1) if records else 0
    grades = {grade: sum(1 for record in records if record["grade"] == grade) for grade in ("양호", "보통", "미흡")}
    avg_latency = round(sum(record["elapsed_ms"] for record in records) / len(records), 1) if records else 0
    lines = [
        "# 업체추천 사용자 관점 Q&A 유효성 평가",
        "",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- base_url: {base_url}",
        f"- total_cases: {len(records)}",
        f"- average_score: {avg_score}/100",
        f"- grade_counts: 양호 {grades['양호']} / 보통 {grades['보통']} / 미흡 {grades['미흡']}",
        f"- average_latency_ms: {avg_latency}",
        "",
        "## 요약 테이블",
        "",
        "| id | intent | score | grade | elapsed_ms | count | intent_match | status_ok | policy_ok | convenience | first_company |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in records:
        c = r["checks"]
        lines.append(
            f"| {r['id']} | {r['intent']} | {r['score']} | {r['grade']} | {r['elapsed_ms']} | "
            f"{c['count']} | {c['intent_match']} | {c['no_closed_or_suspended']} | {c['policy_ok']} | "
            f"{c['convenience_evidence_count']} | {r['first_company']} |"
        )
    lines.extend(["", "## 주요 발견", ""])
    weak = [r for r in records if r["grade"] != "양호"]
    if not weak:
        lines.append("- 전체 케이스가 자동 기준상 양호입니다.")
    else:
        for r in weak:
            lines.append(f"- {r['id']}: score={r['score']}, checks={r['checks']}")
    lines.extend(["", "## 케이스별 상위 표본", ""])
    for r in records:
        lines.append(f"### {r['id']} - {r['q']}")
        lines.append(f"- score: {r['score']} / grade: {r['grade']} / elapsed_ms: {r['elapsed_ms']}")
        lines.append(f"- first: {r['first_company']} / {r['first_match']} / {r['first_business_status']} / {r['first_freshness']}")
        for row in r["rows_sample"]:
            lines.append(
                "- "
                + json.dumps(row, ensure_ascii=False, default=str)
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://49.50.133.160:8001")
    parser.add_argument("--timeout-sec", type=float, default=15)
    parser.add_argument("--max-latency-ms", type=int, default=3000)
    parser.add_argument("--out-dir", default="artifacts/vendor_recommendation_quality_qa")
    args = parser.parse_args()

    records = [evaluate_case(args.base_url, case, args.timeout_sec, args.max_latency_ms) for case in CASES]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"vendor_user_validity_eval_{time.strftime('%Y%m%d_%H%M%S')}"
    jsonl_path = out_dir / f"{stem}.jsonl"
    md_path = out_dir / f"{stem}.md"
    jsonl_path.write_text("\n".join(json.dumps(record, ensure_ascii=False, default=str) for record in records) + "\n", encoding="utf-8")
    write_report(md_path, records, args.base_url)
    ok_count = sum(1 for r in records if r["grade"] == "양호")
    print(f"jsonl={jsonl_path}")
    print(f"report={md_path}")
    print(f"good={ok_count}/{len(records)}")
    for record in records:
        if record["grade"] != "양호":
            print("WEAK", json.dumps({"id": record["id"], "score": record["score"], "checks": record["checks"]}, ensure_ascii=False))
    return 0 if ok_count == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
