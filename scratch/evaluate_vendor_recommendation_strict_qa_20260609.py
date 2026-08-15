from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


CASES: list[dict[str, Any]] = [
    # Goods
    {"id": "goods_led", "intent": "물품", "q": "LED 조명 5천만원 구매 업체 추천", "budget_krw": 50_000_000, "must": ["led", "조명"], "policy": True, "convenience": ["shopping_or_mas"]},
    {"id": "goods_cctv", "intent": "물품", "q": "CCTV 보안카메라 구매 업체", "budget_krw": 70_000_000, "must": ["cctv", "카메라", "영상감시"], "policy": True},
    {"id": "goods_desktop", "intent": "물품", "q": "데스크톱 컴퓨터 4천만원 구매 부산업체", "budget_krw": 40_000_000, "must": ["컴퓨터", "데스크톱", "데스크탑", "pc"], "policy": True, "convenience": ["shopping_or_mas"]},
    {"id": "goods_notebook", "intent": "물품", "q": "노트북 구매 업체 추천", "budget_krw": 30_000_000, "must": ["노트북", "컴퓨터"], "policy": True},
    {"id": "goods_server", "intent": "물품", "q": "서버 컴퓨터 구매 업체", "budget_krw": 90_000_000, "must": ["서버", "컴퓨터"], "policy": True},
    {"id": "goods_security_sw", "intent": "물품", "q": "보안 소프트웨어 구매 업체", "budget_krw": 40_000_000, "must": ["소프트웨어", "보안", "sw", "프로그램"], "policy": True},
    {"id": "goods_firewall", "intent": "물품", "q": "방화벽 장비 구매 업체", "budget_krw": 80_000_000, "must": ["방화벽", "보안", "장치"], "policy": True},
    {"id": "goods_toner", "intent": "물품", "q": "정품토너 구매 업체 추천", "budget_krw": 20_000_000, "must": ["토너"], "policy": True, "avoid_top1": ["축산", "식육", "식품"]},
    {"id": "goods_projector", "intent": "물품", "q": "비디오프로젝터 구매 업체", "budget_krw": 45_000_000, "must": ["프로젝터", "비디오"], "policy": True},
    {"id": "goods_drone", "intent": "물품", "q": "드론 구매 업체", "budget_krw": 35_000_000, "must": ["드론"], "policy": True},
    {"id": "goods_switchboard", "intent": "물품", "q": "분전반 구매 업체", "budget_krw": 80_000_000, "must": ["분전반", "배전반"], "policy": True, "convenience": ["shopping_or_mas"]},
    {"id": "goods_venture_switchboard", "intent": "벤처나라+물품", "q": "분전반 벤처나라 거래실적 업체", "budget_krw": 50_000_000, "must": ["분전반", "배전반"], "policy": True, "convenience": ["venture_order"], "top1_any": ["세풍전기"]},
    {"id": "goods_aircon", "intent": "물품", "q": "냉난방기 에어컨 구매 부산업체", "budget_krw": 60_000_000, "must": ["냉난방", "에어컨", "공기조화"], "policy": True},
    {"id": "goods_furniture", "intent": "물품", "q": "사무용 책상 의자 구매 업체", "budget_krw": 30_000_000, "must": ["가구", "책상", "의자"], "policy": True},
    {"id": "goods_cabinet", "intent": "물품", "q": "문서보관 캐비닛 구매 업체", "budget_krw": 25_000_000, "must": ["캐비닛", "보관함", "가구"], "policy": True},
    {"id": "goods_kitchen", "intent": "물품", "q": "급식실 주방기기 구매 업체", "budget_krw": 70_000_000, "must": ["주방", "급식", "조리"], "policy": True},
    {"id": "goods_remicon", "intent": "물품", "q": "레미콘 구매 부산 업체", "budget_krw": 100_000_000, "must": ["레미콘", "콘크리트"], "policy": True},
    {"id": "goods_ascon", "intent": "물품", "q": "아스콘 구매 업체", "budget_krw": 100_000_000, "must": ["아스콘", "아스팔트"], "policy": True},
    {"id": "goods_elastic_paving", "intent": "물품", "q": "체육시설 탄성포장재 구매 업체", "budget_krw": 90_000_000, "must": ["탄성포장", "포장재"], "policy": True},
    {"id": "goods_printing", "intent": "물품", "q": "홍보물 인쇄 업체 추천", "budget_krw": 20_000_000, "must": ["인쇄", "홍보물", "책자", "현수막"], "policy": True},
    # Services
    {"id": "service_event", "intent": "용역", "q": "발대식 행사 용역 업체 추천", "budget_krw": 200_000_000, "must": ["행사", "이벤트", "공연", "전시"], "policy": False},
    {"id": "service_translation", "intent": "용역", "q": "번역용역 부산 업체 추천", "budget_krw": 40_000_000, "must": ["번역", "통역"], "policy": False},
    {"id": "service_interpretation", "intent": "용역", "q": "국제행사 통역 용역 업체", "budget_krw": 35_000_000, "must": ["통역", "번역"], "policy": False},
    {"id": "service_cleaning", "intent": "용역", "q": "건물 청소용역 부산업체", "budget_krw": 70_000_000, "must": ["청소", "환경미화"], "policy": False},
    {"id": "service_security", "intent": "용역", "q": "청사 경비용역 부산 업체", "budget_krw": 80_000_000, "must": ["경비", "시설경비"], "policy": False},
    {"id": "service_facility", "intent": "용역", "q": "시설관리 용역 부산 업체", "budget_krw": 120_000_000, "must": ["시설관리", "건물관리", "유지관리"], "policy": False},
    {"id": "service_disinfection", "intent": "용역", "q": "소독 방역 용역 업체", "budget_krw": 30_000_000, "must": ["소독", "방역"], "policy": False, "avoid_top1": ["손소독제", "살균제"]},
    {"id": "service_waste", "intent": "용역", "q": "폐기물 처리 용역 업체", "budget_krw": 50_000_000, "must": ["폐기물"], "policy": False},
    {"id": "service_maintenance", "intent": "용역", "q": "승강기 유지보수 용역 업체", "budget_krw": 60_000_000, "must": ["승강기", "유지보수"], "policy": False},
    {"id": "service_accounting", "intent": "용역", "q": "원가계산 용역 업체", "budget_krw": 30_000_000, "must": ["원가", "계산"], "policy": False},
    {"id": "service_legal", "intent": "용역", "q": "법률자문 용역 업체", "budget_krw": 30_000_000, "must": ["법무", "법률", "변호"], "policy": False},
    {"id": "service_bus", "intent": "용역", "q": "전세버스 임차 용역 업체", "budget_krw": 40_000_000, "must": ["버스", "여객", "전세"], "policy": False},
    # Works / licenses
    {"id": "work_electric", "intent": "공사", "q": "전기공사 부산 업체", "budget_krw": 100_000_000, "must": ["전기공사"], "policy": False, "convenience": ["capacity"]},
    {"id": "work_communication", "intent": "공사", "q": "정보통신공사 업체", "budget_krw": 100_000_000, "must": ["정보통신"], "policy": False, "convenience": ["capacity"]},
    {"id": "work_fire", "intent": "공사", "q": "소방시설공사 업체", "budget_krw": 100_000_000, "must": ["소방"], "policy": False, "convenience": ["capacity"]},
    {"id": "work_landscape", "intent": "공사", "q": "조경식재공사 부산 업체", "budget_krw": 100_000_000, "must": ["조경", "식재"], "policy": False, "convenience": ["capacity"]},
    {"id": "work_paving", "intent": "공사", "q": "도로 포장공사 업체", "budget_krw": 150_000_000, "must": ["포장", "도로"], "policy": False, "convenience": ["capacity"]},
    {"id": "work_indoor", "intent": "공사", "q": "실내건축공사 업체", "budget_krw": 80_000_000, "must": ["실내건축", "건축"], "policy": False, "convenience": ["capacity"]},
    {"id": "work_mechanical", "intent": "공사", "q": "기계설비공사 부산 업체", "budget_krw": 100_000_000, "must": ["기계설비"], "policy": False, "convenience": ["capacity"]},
    # Policy/convenience preferences
    {"id": "policy_women_led", "intent": "정책기업+물품", "q": "여성기업 LED 조명 업체", "budget_krw": 50_000_000, "must": ["led", "조명"], "policy": True, "policy_label": "여성기업"},
    {"id": "policy_women_event", "intent": "정책기업+용역", "q": "여성기업 행사 용역 업체", "budget_krw": 50_000_000, "must": ["행사", "이벤트"], "policy": False, "policy_label": "여성기업"},
    {"id": "policy_disabled_cleaning", "intent": "정책기업+용역", "q": "장애인기업 청소용역 업체", "budget_krw": 50_000_000, "must": ["청소", "환경미화"], "policy": False, "policy_label": "장애인기업"},
    {"id": "policy_social_computer", "intent": "정책기업+물품", "q": "사회적기업 컴퓨터 구매 업체", "budget_krw": 40_000_000, "must": ["컴퓨터"], "policy": True, "policy_label": "사회적기업"},
    {"id": "policy_venture_sw", "intent": "정책기업+물품", "q": "벤처기업 소프트웨어 구매 업체", "budget_krw": 40_000_000, "must": ["소프트웨어", "프로그램"], "policy": True, "policy_label": "벤처기업"},
    {"id": "convenience_mas_led", "intent": "MAS+물품", "q": "LED 조명 MAS 등록 부산업체", "budget_krw": 80_000_000, "must": ["led", "조명"], "policy": True, "convenience": ["mas"]},
    {"id": "convenience_shopping_pc", "intent": "쇼핑몰+물품", "q": "종합쇼핑몰 등록 데스크톱 컴퓨터 업체", "budget_krw": 40_000_000, "must": ["컴퓨터", "데스크톱"], "policy": True, "convenience": ["shopping"]},
    {"id": "convenience_direct_print", "intent": "직생+물품", "q": "직접생산 가능한 인쇄물 업체", "budget_krw": 30_000_000, "must": ["인쇄"], "policy": True, "convenience": ["direct_production"]},
    {"id": "convenience_competition_furniture", "intent": "중기간+물품", "q": "중기간경쟁제품 사무용가구 업체", "budget_krw": 60_000_000, "must": ["가구", "책상", "의자"], "policy": True, "convenience": ["sme_competition"]},
    {"id": "convenience_capacity_fire", "intent": "시공능력+공사", "q": "시공능력 확인 가능한 소방시설공사 업체", "budget_krw": 150_000_000, "must": ["소방"], "policy": False, "convenience": ["capacity"]},
]


POSITIVE_MISSING = ("", "없음", "미확인", "확인 필요", "DB 등록정보 없음", "미검증", "미매칭")


def norm(value: Any) -> str:
    return str(value or "").lower().replace(" ", "")


def contains_any(text: str, needles: list[str]) -> bool:
    folded = norm(text)
    return any(norm(needle) in folded for needle in needles)


def is_positive(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return not any(term in text for term in POSITIVE_MISSING if term)


def row_text(row: dict[str, Any]) -> str:
    keys = (
        "company_name",
        "main_products",
        "license_or_business_type",
        "matched_query_label",
        "shopping_mall_product_summary",
        "mas_product_summary",
        "direct_production_certificate_products",
        "direct_production_summary",
        "certified_product_summary",
        "construction_capacity_summary",
        "venture_nara_product_summary",
        "venture_nara_order_summary",
    )
    return " ".join(str(row.get(key) or "") for key in keys)


def convenience_ok(rows: list[dict[str, Any]], name: str, top_n: int = 5) -> bool:
    sample = rows[:top_n]
    if name == "shopping_or_mas":
        return any(is_positive(row.get("shopping_mall_status_label")) or is_positive(row.get("mas_status_label")) for row in sample)
    if name == "shopping":
        return any(is_positive(row.get("shopping_mall_status_label")) for row in sample)
    if name == "mas":
        return any(is_positive(row.get("mas_status_label")) for row in sample)
    if name == "direct_production":
        return any(is_positive(row.get("direct_production_certificate_status")) or is_positive(row.get("direct_production_certificate_products")) for row in sample)
    if name == "sme_competition":
        return any(is_positive(row.get("sme_competition_product_label")) for row in sample)
    if name == "capacity":
        return any(is_positive(row.get("construction_capacity_summary")) for row in sample)
    if name == "venture_order":
        return any(is_positive(row.get("venture_nara_order_summary")) for row in sample)
    return True


def evaluate(base_url: str, case: dict[str, Any], timeout_sec: float, max_latency_ms: int) -> dict[str, Any]:
    params = {
        "q": case["q"],
        "region": "busan",
        "limit": 10,
        "budget_krw": case.get("budget_krw") or "",
        "include_product_policy": "true",
    }
    started = time.perf_counter()
    resp = requests.get(f"{base_url.rstrip('/')}/vendor-recommendations/search", params=params, timeout=timeout_sec)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    data = resp.json()
    rows = [row for row in data.get("rows") or [] if isinstance(row, dict)]
    top = rows[0] if rows else {}
    top1_text = row_text(top)
    top3_text = " ".join(row_text(row) for row in rows[:3])
    top5_text = " ".join(row_text(row) for row in rows[:5])
    policy_summary = data.get("item_policy_summary") or {}
    policy_pref = data.get("policy_preference_summary") or {}
    bad_status = [
        row.get("company_name")
        for row in rows
        if str(row.get("business_status") or "").lower() in {"closed", "suspended", "inactive"}
    ]
    requested_convenience = case.get("convenience") or []
    convenience_results = {name: convenience_ok(rows, name) for name in requested_convenience}
    policy_label = case.get("policy_label")
    policy_label_ok = True
    if policy_label:
        top10_policy = " ".join(str(row.get("policy_company_labels") or "") for row in rows[:10])
        pref_status = str(policy_pref.get("status") or "")
        policy_label_ok = policy_label in top10_policy or pref_status in {"matched", "not_found_in_candidates"}
    avoid_ok = True
    if case.get("avoid_top1"):
        avoid_ok = not contains_any(top1_text, case["avoid_top1"])
    top1_requested_ok = True
    if case.get("top1_any"):
        top1_requested_ok = contains_any(top1_text, case["top1_any"])

    policy_ok = True
    if case.get("policy"):
        policy_ok = policy_summary.get("status") == "matched" and bool(policy_summary.get("matched_products"))
    else:
        policy_ok = policy_summary.get("status") in {"not_requested", "matched", "not_found_or_unavailable"}

    labels_ok = bool(top.get("company_name")) and bool(top.get("business_status_label")) and bool(top.get("recommended_checks"))
    checks = {
        "status_code_ok": resp.status_code == 200,
        "count_ok": len(rows) > 0,
        "latency_ok": elapsed_ms <= max_latency_ms,
        "top1_match": contains_any(top1_text, case["must"]),
        "top3_match": contains_any(top3_text, case["must"]),
        "top5_match": contains_any(top5_text, case["must"]),
        "status_ok": not bad_status,
        "labels_ok": labels_ok,
        "policy_ok": policy_ok,
        "policy_label_ok": policy_label_ok,
        "avoid_ok": avoid_ok,
        "top1_requested_ok": top1_requested_ok,
        "convenience_ok": all(convenience_results.values()) if requested_convenience else True,
    }
    weights = {
        "status_code_ok": 5,
        "count_ok": 10,
        "latency_ok": 5,
        "top1_match": 25,
        "top3_match": 15,
        "top5_match": 5,
        "status_ok": 10,
        "labels_ok": 5,
        "policy_ok": 5,
        "policy_label_ok": 5,
        "avoid_ok": 5,
        "top1_requested_ok": 3,
        "convenience_ok": 2,
    }
    score = sum(weights[key] for key, ok in checks.items() if ok)
    grade = "양호" if score >= 88 else "보통" if score >= 75 else "미흡"
    return {
        "id": case["id"],
        "q": case["q"],
        "intent": case["intent"],
        "elapsed_ms": elapsed_ms,
        "score": score,
        "grade": grade,
        "checks": checks,
        "convenience_results": convenience_results,
        "policy_status": policy_summary.get("status"),
        "policy_preference_status": policy_pref.get("status"),
        "bad_status_rows": bad_status,
        "first_company": top.get("company_name", ""),
        "first_match": top.get("matched_query_label", ""),
        "first_review_score": top.get("review_score", ""),
        "first_business_status": top.get("business_status_label", ""),
        "first_evidence": {
            "policy_company_labels": top.get("policy_company_labels"),
            "shopping_mall_status_label": top.get("shopping_mall_status_label"),
            "mas_status_label": top.get("mas_status_label"),
            "direct_production_certificate_status": top.get("direct_production_certificate_status"),
            "sme_competition_product_label": top.get("sme_competition_product_label"),
            "construction_capacity_summary": top.get("construction_capacity_summary"),
            "venture_nara_order_summary": top.get("venture_nara_order_summary"),
        },
        "rows_sample": [
            {
                "company_name": row.get("company_name"),
                "matched_query_label": row.get("matched_query_label"),
                "business_status_label": row.get("business_status_label"),
                "policy_company_labels": row.get("policy_company_labels"),
                "shopping_mall_status_label": row.get("shopping_mall_status_label"),
                "mas_status_label": row.get("mas_status_label"),
                "direct_production_certificate_status": row.get("direct_production_certificate_status"),
                "sme_competition_product_label": row.get("sme_competition_product_label"),
                "construction_capacity_summary": row.get("construction_capacity_summary"),
                "venture_nara_order_summary": row.get("venture_nara_order_summary"),
                "review_score": row.get("review_score"),
            }
            for row in rows[:5]
        ],
    }


def write_report(path: Path, records: list[dict[str, Any]], base_url: str) -> None:
    scores = [int(r["score"]) for r in records]
    avg = round(statistics.mean(scores), 1) if scores else 0
    med = round(statistics.median(scores), 1) if scores else 0
    grades = {g: sum(1 for r in records if r["grade"] == g) for g in ("양호", "보통", "미흡")}
    avg_latency = round(statistics.mean([int(r["elapsed_ms"]) for r in records]), 1) if records else 0
    lines = [
        "# 업체추천 엄격 Q&A 신뢰도 평가",
        "",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- base_url: {base_url}",
        f"- total_cases: {len(records)}",
        f"- average_score: {avg}/100",
        f"- median_score: {med}/100",
        f"- grade_counts: 양호 {grades['양호']} / 보통 {grades['보통']} / 미흡 {grades['미흡']}",
        f"- average_latency_ms: {avg_latency}",
        "",
        "## Summary",
        "",
        "| id | intent | score | grade | ms | top1 | top3 | policy | conv | first_company |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in records:
        c = r["checks"]
        lines.append(
            f"| {r['id']} | {r['intent']} | {r['score']} | {r['grade']} | {r['elapsed_ms']} | "
            f"{c['top1_match']} | {c['top3_match']} | {c['policy_ok']} | {c['convenience_ok']} | {r['first_company']} |"
        )
    lines.extend(["", "## Weak Cases", ""])
    weak = [r for r in records if r["grade"] != "양호"]
    if not weak:
        lines.append("- 없음")
    else:
        for r in weak:
            failed = [k for k, v in r["checks"].items() if not v]
            lines.append(f"- {r['id']} ({r['q']}): score={r['score']}, failed={failed}, first={r['first_company']} / {r['first_match']}")
    lines.extend(["", "## Case Samples", ""])
    for r in records:
        lines.append(f"### {r['id']} - {r['q']}")
        lines.append(f"- score={r['score']} grade={r['grade']} elapsed_ms={r['elapsed_ms']}")
        lines.append(f"- first={r['first_company']} / {r['first_match']} / {r['first_business_status']} / review_score={r['first_review_score']}")
        lines.append(f"- checks={json.dumps(r['checks'], ensure_ascii=False)}")
        for row in r["rows_sample"][:3]:
            lines.append("- " + json.dumps(row, ensure_ascii=False, default=str))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://49.50.133.160:8001")
    parser.add_argument("--timeout-sec", type=float, default=15)
    parser.add_argument("--max-latency-ms", type=int, default=3000)
    parser.add_argument("--out-dir", default="artifacts/vendor_recommendation_quality_qa")
    args = parser.parse_args()

    records = [evaluate(args.base_url, case, args.timeout_sec, args.max_latency_ms) for case in CASES]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"vendor_recommendation_strict_qa_{time.strftime('%Y%m%d_%H%M%S')}"
    jsonl_path = out_dir / f"{stem}.jsonl"
    md_path = out_dir / f"{stem}.md"
    jsonl_path.write_text("\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in records) + "\n", encoding="utf-8")
    write_report(md_path, records, args.base_url)
    good = sum(1 for r in records if r["grade"] == "양호")
    print(f"jsonl={jsonl_path}")
    print(f"report={md_path}")
    print(f"good={good}/{len(records)}")
    for r in records:
        if r["grade"] != "양호":
            print("WEAK", json.dumps({"id": r["id"], "score": r["score"], "checks": r["checks"], "first": r["first_company"], "match": r["first_match"]}, ensure_ascii=False))
    return 0 if good == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
