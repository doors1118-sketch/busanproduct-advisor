from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import evaluate_vendor_recommendation_1000_qa_20260609 as qa1000


def clone_case(base: dict[str, Any], case_id: str, question: str, tags: list[str]) -> dict[str, Any]:
    copied = dict(base)
    copied["id"] = case_id
    copied["q"] = question
    copied["tags"] = list(dict.fromkeys([*(base.get("tags") or []), *tags]))
    return copied


def budget_label(krw: int) -> str:
    if krw >= 100_000_000:
        return f"{krw // 100_000_000}억원"
    return f"{krw // 10_000:,}만원"


def build_cases(target_count: int = 2000) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen_q: set[str] = set()

    def add(c: dict[str, Any]) -> None:
        q = str(c["q"]).strip()
        if not q or q in seen_q:
            return
        seen_q.add(q)
        cases.append(c)

    for c in qa1000.build_cases(3000):
        add(c)

    base_items = qa1000.ITEMS
    budgets = [8_000_000, 12_000_000, 18_000_000, 25_000_000, 35_000_000, 45_000_000, 55_000_000, 70_000_000, 90_000_000, 120_000_000, 200_000_000, 500_000_000]
    agency_contexts = [
        "구청 발주 담당자가",
        "공공기관 구매 담당자가",
        "부산시 산하기관에서",
        "공기업 지사에서",
        "학교 계약 담당자가",
        "복지관에서",
        "문화행사 담당부서에서",
        "시설관리 부서에서",
    ]
    purpose_contexts = [
        "빠르게 비교할 후보",
        "계약 편의성까지 고려한 후보",
        "부산 본사 중심 후보",
        "조달 등록 근거가 보이는 후보",
        "예산 범위에서 검토할 후보",
        "초기 견적 요청 대상",
        "업체 추천 화면에 보여줄 후보",
        "실무자가 바로 확인할 후보",
    ]
    exact_phrases = [
        "{ctx} {item} {purpose} 추천",
        "{ctx} {item} 예산 {budget} 기준 {purpose} 찾아줘",
        "{item} 관련해서 {purpose} 10개만 보여줘",
        "{item} 납품 또는 수행 가능한 부산업체 {purpose}",
        "{item} 계약 검토 중인데 {purpose} 알려줘",
        "{item} 지역업체 검색, {purpose}",
        "{budget} 규모 {item} 발주 예정, {purpose}",
        "{item} 업체를 정책기업 여부까지 같이 보고 싶다",
        "{item} 업체 중 사업자 상태 확인 가능한 후보",
        "{item} 부산 본사 업체와 조달 근거 같이 표출",
    ]
    convenience_phrases = {
        "shopping_or_mas": [
            "{item} 종합쇼핑몰 또는 MAS 등록 근거 있는 업체",
            "{item} 바로 구매 가능성이 높은 부산업체",
        ],
        "shopping": [
            "{item} 종합쇼핑몰 등록 부산업체",
            "{item} 쇼핑몰 품목 근거가 있는 후보",
        ],
        "mas": [
            "{item} 다수공급자계약 MAS 업체 추천",
            "{item} 2단계경쟁 검토 가능한 MAS 후보",
        ],
        "direct_production": [
            "{item} 직접생산증명서 보유 업체",
            "{item} 직접생산 가능한 부산업체",
        ],
        "sme_competition": [
            "{item} 중소기업자간 경쟁제품 관련 업체",
            "{item} 중기간경쟁제품 검토 후보",
        ],
        "capacity": [
            "{item} 시공능력평가금액 확인 가능한 업체",
            "{item} 공사 면허와 시공능력 같이 볼 업체",
        ],
        "venture_order": [
            "{item} 벤처나라 주문거래 실적 있는 업체",
            "{item} 벤처나라 거래 이력 기준 후보",
        ],
    }
    policy_labels = ["여성기업", "장애인기업", "사회적기업", "벤처기업", "창업기업", "소상공인"]

    seq = 0
    for item in base_items:
        name = item["name"]
        must = item["must"]
        for phrase in exact_phrases:
            if len(cases) >= target_count:
                return cases
            budget = budgets[seq % len(budgets)]
            q = phrase.format(
                ctx=agency_contexts[seq % len(agency_contexts)],
                item=name,
                purpose=purpose_contexts[(seq // 2) % len(purpose_contexts)],
                budget=budget_label(budget),
            )
            add(qa1000.case(
                f"ext_exact_{item['key']}_{seq:04d}",
                q,
                item["intent"],
                must,
                budget_krw=budget,
                tags=["extended2000", "exact"],
                policy=bool(item["policy"]),
                avoid_top1=item.get("avoid") or [],
            ))
            seq += 1

        for cap in item.get("caps") or []:
            for phrase in convenience_phrases.get(cap, []):
                if len(cases) >= target_count:
                    return cases
                budget = budgets[seq % len(budgets)]
                add(qa1000.case(
                    f"ext_conv_{item['key']}_{cap}_{seq:04d}",
                    phrase.format(item=name),
                    "편의조건",
                    must,
                    budget_krw=budget,
                    tags=["extended2000", "convenience"],
                    policy=bool(item["policy"]),
                    convenience=[cap],
                    avoid_top1=item.get("avoid") or [],
                    top1_any=item.get("top1") if cap == "venture_order" else [],
                ))
                seq += 1

        for label in policy_labels:
            if item["intent"] == "공사":
                continue
            if len(cases) >= target_count:
                return cases
            budget = budgets[seq % len(budgets)]
            add(qa1000.case(
                f"ext_policy_{item['key']}_{seq:04d}",
                f"{label} 조건으로 {name} 업체 추천",
                "정책기업",
                must,
                budget_krw=budget,
                tags=["extended2000", "policy"],
                policy=bool(item["policy"]),
                policy_label=label,
                avoid_top1=item.get("avoid") or [],
            ))
            seq += 1

    mixed_extra = [
        ("LED 조명", "CCTV", ["led", "조명", "cctv", "카메라"], True),
        ("컴퓨터", "보안 소프트웨어", ["컴퓨터", "소프트웨어", "보안"], True),
        ("책상", "의자", ["책상", "의자"], True),
        ("현수막", "행사 운영", ["현수막", "행사"], True),
        ("청소", "소독 방역", ["청소", "소독", "방역"], False),
        ("시설관리", "승강기 유지보수", ["시설관리", "승강기", "유지보수"], False),
        ("전기공사", "정보통신공사", ["전기", "정보통신"], False),
        ("조경식재", "포장공사", ["조경", "포장"], False),
        ("드론", "영상 제작", ["드론", "영상"], False),
        ("번역", "행사 통역", ["번역", "통역"], False),
    ]
    mixed_phrases = [
        "{left}와 {right}를 함께 검토할 부산업체",
        "{left}/{right} 둘 중 가능한 지역업체 추천",
        "{left} 또는 {right} 발주 후보 알려줘",
        "{budget} 예산으로 {left}와 {right} 후보 비교",
        "{left} plus {right} 가능한 업체 찾아줘",
        "{left}, {right} 같이 계약 편의성 높은 후보",
    ]
    scenario_suffixes = [
        "긴급발주 기준",
        "상반기 집행 기준",
        "하반기 예산 집행용",
        "소액수의 검토용",
        "2인 견적 검토용",
        "나라장터 등록 확인용",
        "정책기업 우선 검토용",
        "공공기관 구매 검토용",
        "구군 계약 검토용",
        "산하기관 집행 검토용",
        "사전 시장조사용",
        "계약담당자 검토용",
        "발주부서 요청용",
        "지역업체 우선 검토용",
        "실무자 확인용",
        "후보군 비교용",
    ]
    while len(cases) < target_count:
        left, right, must, policy = mixed_extra[seq % len(mixed_extra)]
        phrase = mixed_phrases[(seq // len(mixed_extra)) % len(mixed_phrases)]
        budget = budgets[seq % len(budgets)]
        suffix = scenario_suffixes[(seq // (len(mixed_extra) * len(mixed_phrases))) % len(scenario_suffixes)]
        ctx = agency_contexts[seq % len(agency_contexts)]
        add(qa1000.case(
            f"ext_mixed_{seq:04d}",
            f"{ctx} {phrase.format(left=left, right=right, budget=budget_label(budget))} {suffix}",
            "혼합",
            must,
            budget_krw=budget,
            tags=["extended2000", "mixed"],
            policy=policy,
        ))
        seq += 1
        if seq > 20000 and len(cases) < target_count:
            raise RuntimeError("failed to generate enough unique 2000 QA cases")

    return cases[:target_count]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://49.50.133.160:8001")
    parser.add_argument("--out-dir", default="artifacts/vendor_recommendation_quality_qa")
    parser.add_argument("--timeout-sec", type=float, default=12.0)
    parser.add_argument("--max-latency-ms", type=int, default=3000)
    parser.add_argument("--target-count", type=int, default=2000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    selected = build_cases(args.target_count)
    if len(selected) != args.target_count:
        raise SystemExit(f"generated only {len(selected)} cases")
    if len({c["q"] for c in selected}) != len(selected):
        raise SystemExit("duplicate questions detected")

    workers = max(1, min(int(args.workers or 1), 8))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(qa1000.evaluate, args.base_url, c, args.timeout_sec, args.max_latency_ms): i
            for i, c in enumerate(selected)
        }
        by_index: dict[int, dict[str, Any]] = {}
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                by_index[idx] = future.result()
            except Exception as exc:
                c = selected[idx]
                by_index[idx] = {
                    "id": c["id"],
                    "q": c["q"],
                    "intent": c["intent"],
                    "tags": c.get("tags") or [],
                    "elapsed_ms": 0,
                    "score": 0,
                    "grade": "미흡",
                    "checks": {"exception": False},
                    "first_company": "",
                    "first_match": "",
                    "first_business_status": "",
                    "first_review_score": "",
                    "rows_sample": [],
                    "error": str(exc),
                }
        records = [by_index[i] for i in range(len(selected))]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"vendor_recommendation_2000_qa_{time.strftime('%Y%m%d_%H%M%S')}"
    jsonl_path = out_dir / f"{stem}.jsonl"
    md_path = out_dir / f"{stem}.md"
    jsonl_path.write_text("\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in records) + "\n", encoding="utf-8")
    qa1000.write_report(md_path, records, args.base_url)
    report_lines = md_path.read_text(encoding="utf-8").splitlines()
    if report_lines:
        report_lines[0] = report_lines[0].replace("1000", "2000", 1)
        md_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    good = sum(1 for r in records if r["grade"] == "양호")
    print(f"jsonl={jsonl_path}")
    print(f"report={md_path}")
    print(f"good={good}/{len(records)}")
    for r in records:
        if r["grade"] != "양호":
            print("WEAK", json.dumps({
                "id": r["id"],
                "q": r["q"],
                "score": r["score"],
                "tags": r["tags"],
                "checks": r["checks"],
                "first": r["first_company"],
                "match": r["first_match"],
            }, ensure_ascii=False))
    return 0 if good == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
