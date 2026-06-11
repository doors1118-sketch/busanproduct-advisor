from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import evaluate_vendor_recommendation_1000_qa_20260609 as qa1000


EXTRA_ITEMS: list[dict[str, Any]] = [
    {"key": "pc", "name": "PC", "intent": "물품", "must": ["컴퓨터", "pc", "데스크톱"], "policy": True, "caps": ["shopping_or_mas", "shopping"], "avoid": []},
    {"key": "monitor", "name": "모니터", "intent": "물품", "must": ["모니터", "디스플레이"], "policy": True, "caps": ["shopping_or_mas"], "avoid": []},
    {"key": "printer", "name": "프린터", "intent": "물품", "must": ["프린터", "복합기"], "policy": True, "caps": ["shopping_or_mas"], "avoid": []},
    {"key": "network", "name": "네트워크 장비", "intent": "물품", "must": ["네트워크", "스위치", "라우터"], "policy": True, "caps": ["shopping_or_mas"], "avoid": []},
    {"key": "sign", "name": "안내판", "intent": "물품", "must": ["안내판", "간판"], "policy": True, "caps": ["direct_production"], "avoid": []},
    {"key": "cleaning_goods", "name": "청소용품", "intent": "물품", "must": ["청소용품", "세제"], "policy": True, "caps": [], "avoid": ["청소용역"]},
    {"key": "school_temp", "name": "임시학교건물임대서비스", "intent": "용역", "must": ["임시학교", "건물임대", "임대서비스"], "policy": False, "caps": [], "avoid": []},
    {"key": "research", "name": "학술연구용역", "intent": "용역", "must": ["학술", "연구"], "policy": False, "caps": [], "avoid": []},
    {"key": "software_maintenance", "name": "소프트웨어 유지보수", "intent": "용역", "must": ["소프트웨어", "유지보수"], "policy": False, "caps": [], "avoid": []},
    {"key": "parking", "name": "주차관리용역", "intent": "용역", "must": ["주차", "관리"], "policy": False, "caps": [], "avoid": []},
    {"key": "meal", "name": "급식 위탁 용역", "intent": "용역", "must": ["급식", "위탁"], "policy": False, "caps": [], "avoid": []},
    {"key": "survey", "name": "측량용역", "intent": "용역", "must": ["측량"], "policy": False, "caps": [], "avoid": []},
    {"key": "architecture_design", "name": "건축설계용역", "intent": "용역", "must": ["건축", "설계"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "supervision", "name": "감리용역", "intent": "용역", "must": ["감리"], "policy": False, "caps": [], "avoid": []},
    {"key": "metal_window", "name": "금속창호공사", "intent": "공사", "must": ["금속", "창호"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "water_supply", "name": "상하수도설비공사", "intent": "공사", "must": ["상하수도", "설비"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "painting", "name": "도장공사", "intent": "공사", "must": ["도장"], "policy": False, "caps": ["capacity"], "avoid": []},
]


CONTEXTS = [
    "구청 발주 담당자가",
    "공공기관 구매 담당자가",
    "부산시 산하기관에서",
    "학교 계약 담당자가",
    "복지관에서",
    "문화행사 담당부서에서",
    "시설관리 부서에서",
    "정보화사업 담당자가",
    "도서관 담당자가",
    "체육시설 담당자가",
    "보건소 계약 담당자가",
    "교육청 실무자가",
]

PURPOSES = [
    "후보군 비교용",
    "조달 등록 근거 확인용",
    "계약 편의성 높은 순서로",
    "정책기업 여부까지 같이",
    "부산 본사 업체 중심으로",
    "엑셀 다운로드 전 검토용",
    "수의계약 가능성 검토 전",
    "공고 전 시장조사용",
    "MAS나 쇼핑몰 등록 여부 포함해서",
    "직접생산 필요 여부 포함해서",
    "중기간경쟁 해당 여부 포함해서",
    "면허 업종 근거가 보이게",
]

BUDGETS = [
    5_000_000,
    8_000_000,
    12_000_000,
    18_000_000,
    25_000_000,
    35_000_000,
    45_000_000,
    55_000_000,
    70_000_000,
    90_000_000,
    120_000_000,
    200_000_000,
    500_000_000,
    1_000_000_000,
]

BASE_PHRASES = [
    "{ctx} {item} 업체 후보 보여줘 {purpose}",
    "{ctx} {item} 부산 지역업체 찾아줘 {purpose}",
    "{ctx} {item} 조달 등록 업체 {purpose}",
    "{item} 예산 {budget} 기준 후보 {purpose}",
    "{item} 계약 가능한 업체 {purpose}",
    "{item} 수의계약 검토 후보 {purpose}",
    "{item} 공공기관 납품 가능한 업체 {purpose}",
    "{item} 본사 부산 업체 {purpose}",
    "{item} 빠르게 계약 가능한 업체 {purpose}",
    "{item} 관련 조달업체 {purpose}",
    "{ctx} {item} 발주 전에 업체군 확인 {purpose}",
    "{ctx} {item} 견적 받을만한 후보군 {purpose}",
]

AMBIGUOUS_PHRASES = [
    "{short} 업체 좀 찾아줘 {purpose}",
    "{short} 살만한 지역업체 {purpose}",
    "{short} 맡길 업체 {purpose}",
    "{short} 가능한 부산 업체 {purpose}",
    "{short} 관련 업체군 {purpose}",
    "{short} 비슷한 품목이나 용역까지 같이 {purpose}",
]

CONVENIENCE_PHRASES = {
    "shopping_or_mas": [
        "{item} 쇼핑몰 또는 MAS 업체 {purpose}",
        "{item} 조달청 쇼핑몰에서 바로 살 수 있는 후보 {purpose}",
        "{item} MAS/제3자단가 가능 업체 {purpose}",
    ],
    "shopping": [
        "종합쇼핑몰 등록 {item} 업체 {purpose}",
        "{item} 쇼핑몰 등록 부산업체 {purpose}",
    ],
    "mas": [
        "MAS 등록 {item} 부산업체 {purpose}",
        "{item} 다수공급자계약 업체 {purpose}",
    ],
    "direct_production": [
        "{item} 직접생산 업체 {purpose}",
        "{item} 직접생산증명서 보유 업체 {purpose}",
    ],
    "sme_competition": [
        "중기간경쟁제품 {item} 업체 {purpose}",
        "{item} 중소기업자간 경쟁제품 후보 {purpose}",
    ],
    "capacity": [
        "시공능력 확인 가능한 {item} 업체 {purpose}",
        "{item} 시공능력평가금액 있는 업체 {purpose}",
    ],
    "venture_order": [
        "{item} 벤처나라 거래실적 업체 {purpose}",
        "{item} 벤처나라 주문거래 이력 업체 {purpose}",
    ],
}

POLICY_LABELS = ["여성기업", "장애인기업", "사회적기업", "벤처기업", "창업기업", "소상공인"]

TYPO_MAP = {
    "데스크톱 컴퓨터": ["데스크탑 컴퓨터", "데스크톱 pc", "PC"],
    "노트북": ["노트북컴퓨터", "노트북 컴터"],
    "CCTV 보안카메라": ["씨씨티비", "CCTV카메라", "보안용카메라"],
    "비디오프로젝터": ["빔프로젝터", "빔프로젝트", "프로젝터"],
    "토너": ["토너카트리지", "정품토너"],
    "청소용역": ["청소 용역", "환경미화"],
    "경비용역": ["시설경비", "청사경비"],
    "행사 용역": ["행사용역", "행사대행", "이벤트"],
}


def budget_label(krw: int) -> str:
    if krw >= 100_000_000:
        if krw % 100_000_000 == 0:
            return f"{krw // 100_000_000}억원"
        return f"{krw / 100_000_000:.1f}억원"
    return f"{krw // 10_000:,}만원"


def short_name(name: str) -> str:
    return (
        name.replace(" 용역", "")
        .replace("용역", "")
        .replace("공사", "")
        .replace(" 업체", "")
        .strip()
    )


def make_case(
    case_id: str,
    q: str,
    item: dict[str, Any],
    *,
    budget_krw: int,
    tags: list[str],
    convenience: list[str] | None = None,
    policy_label: str = "",
) -> dict[str, Any]:
    return qa1000.case(
        case_id,
        q,
        item["intent"],
        item["must"],
        budget_krw=budget_krw,
        tags=tags,
        policy=bool(item.get("policy")),
        policy_label=policy_label,
        convenience=convenience or [],
        avoid_top1=item.get("avoid") or [],
        top1_any=item.get("top1") if convenience and "venture_order" in convenience else [],
    )


def build_cases(target_count: int = 5000) -> list[dict[str, Any]]:
    items = [*qa1000.ITEMS, *EXTRA_ITEMS]
    cases: list[dict[str, Any]] = []
    seen_q: set[str] = set()

    def add(c: dict[str, Any]) -> None:
        q = str(c["q"]).strip()
        if not q or q in seen_q:
            return
        seen_q.add(q)
        cases.append(c)

    try:
        for c in qa1000.build_cases(1000):
            add(c)
    except Exception:
        pass

    seq = 0
    for item in items:
        name = item["name"]
        for phrase in BASE_PHRASES:
            for purpose in PURPOSES[:6]:
                if len(cases) >= target_count:
                    return cases
                budget = BUDGETS[seq % len(BUDGETS)]
                q = phrase.format(
                    ctx=CONTEXTS[seq % len(CONTEXTS)],
                    item=name,
                    budget=budget_label(budget),
                    purpose=purpose,
                )
                add(make_case(f"v5_base_{item['key']}_{seq:05d}", q, item, budget_krw=budget, tags=["v5000", "base"]))
                seq += 1

        for phrase in AMBIGUOUS_PHRASES:
            for purpose in PURPOSES[6:]:
                if len(cases) >= target_count:
                    return cases
                budget = BUDGETS[seq % len(BUDGETS)]
                q = phrase.format(short=short_name(name), purpose=purpose)
                add(make_case(f"v5_amb_{item['key']}_{seq:05d}", q, item, budget_krw=budget, tags=["v5000", "ambiguous"]))
                seq += 1

        for cap in item.get("caps") or []:
            for phrase in CONVENIENCE_PHRASES.get(cap, []):
                for purpose in PURPOSES[::3]:
                    if len(cases) >= target_count:
                        return cases
                    budget = BUDGETS[seq % len(BUDGETS)]
                    q = phrase.format(item=name, purpose=purpose)
                    add(make_case(
                        f"v5_conv_{item['key']}_{cap}_{seq:05d}",
                        q,
                        item,
                        budget_krw=budget,
                        tags=["v5000", "convenience"],
                        convenience=[cap],
                    ))
                    seq += 1

        if item["intent"] != "공사":
            for label in POLICY_LABELS:
                for purpose in PURPOSES[1::4]:
                    if len(cases) >= target_count:
                        return cases
                    budget = BUDGETS[seq % len(BUDGETS)]
                    q = f"{label} 조건으로 {name} 업체 후보 {purpose}"
                    add(make_case(
                        f"v5_policy_{item['key']}_{seq:05d}",
                        q,
                        item,
                        budget_krw=budget,
                        tags=["v5000", "policy"],
                        policy_label=label,
                    ))
                    seq += 1

        for source, variants in TYPO_MAP.items():
            if source in name or name in source:
                for variant in variants:
                    for purpose in PURPOSES[::5]:
                        if len(cases) >= target_count:
                            return cases
                        budget = BUDGETS[seq % len(BUDGETS)]
                        q = f"{variant} 업체 후보 {purpose}"
                        add(make_case(f"v5_typo_{item['key']}_{seq:05d}", q, item, budget_krw=budget, tags=["v5000", "typo"]))
                        seq += 1

    pair_seq = 0
    while len(cases) < target_count:
        left = items[pair_seq % len(items)]
        right = items[(pair_seq * 7 + 3) % len(items)]
        if left["key"] == right["key"]:
            pair_seq += 1
            continue
        budget = BUDGETS[pair_seq % len(BUDGETS)]
        q_templates = [
            "{ctx} {left}와 {right} 둘 다 가능한 업체군 {purpose}",
            "{left}/{right} 같이 검토할 후보 {purpose}",
            "{budget} 예산으로 {left} 또는 {right} 업체 비교 {purpose}",
            "{ctx} {left} plus {right} 가능한 부산업체 {purpose}",
        ]
        tmpl = q_templates[pair_seq % len(q_templates)]
        q = tmpl.format(
            ctx=CONTEXTS[pair_seq % len(CONTEXTS)],
            left=left["name"],
            right=right["name"],
            budget=budget_label(budget),
            purpose=PURPOSES[pair_seq % len(PURPOSES)],
        )
        mixed = dict(left)
        mixed["intent"] = "혼합"
        mixed["must"] = list(dict.fromkeys([*(left.get("must") or []), *(right.get("must") or [])]))
        mixed["policy"] = bool(left.get("policy") or right.get("policy"))
        add(make_case(f"v5_mixed_{pair_seq:05d}", q, mixed, budget_krw=budget, tags=["v5000", "mixed"]))
        pair_seq += 1
        if pair_seq > 50000:
            raise RuntimeError("failed to generate enough unique QA cases")

    return cases[:target_count]


def write_report(path: Path, records: list[dict[str, Any]], base_url: str) -> None:
    scores = [int(r["score"]) for r in records]
    latencies = [int(r["elapsed_ms"]) for r in records]
    grade_counts = {k: sum(1 for r in records if r["grade"] == k) for k in ("양호", "보통", "미흡")}
    fail_counts: dict[str, int] = {}
    tag_stats: dict[str, dict[str, Any]] = {}
    for r in records:
        for key, ok in (r.get("checks") or {}).items():
            if not ok:
                fail_counts[key] = fail_counts.get(key, 0) + 1
        tag = ",".join(r.get("tags") or ["untagged"])
        stat = tag_stats.setdefault(tag, {"count": 0, "scores": [], "weak": 0})
        stat["count"] += 1
        stat["scores"].append(int(r["score"]))
        if r["grade"] != "양호":
            stat["weak"] += 1

    lines = [
        "# 업체추천 5000개 고유 Q&A 신뢰도 평가",
        "",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- base_url: {base_url}",
        f"- total_cases: {len(records)}",
        f"- unique_questions: {len({r['q'] for r in records})}",
        f"- average_score: {round(statistics.mean(scores), 2) if scores else 0}/100",
        f"- median_score: {round(statistics.median(scores), 2) if scores else 0}/100",
        f"- min_score: {min(scores) if scores else 0}/100",
        f"- grade_counts: 양호 {grade_counts['양호']} / 보통 {grade_counts['보통']} / 미흡 {grade_counts['미흡']}",
        f"- average_latency_ms: {round(statistics.mean(latencies), 1) if latencies else 0}",
        f"- p95_latency_ms: {sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else 0}",
        f"- max_latency_ms: {max(latencies) if latencies else 0}",
        "",
        "## 실패 체크 집계",
        "",
        "| check | count |",
        "|---|---:|",
    ]
    for key, count in sorted(fail_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"| {key} | {count} |")

    lines.extend(["", "## Tag Summary", "", "| tag | count | avg_score | weak |", "|---|---:|---:|---:|"])
    for tag in sorted(tag_stats):
        stat = tag_stats[tag]
        lines.append(f"| {tag} | {stat['count']} | {round(statistics.mean(stat['scores']), 2)} | {stat['weak']} |")

    weak = [r for r in records if r["grade"] != "양호"]
    lines.extend(["", "## Weak Cases", ""])
    if not weak:
        lines.append("- 없음")
    else:
        for r in weak[:200]:
            failed = [k for k, v in (r.get("checks") or {}).items() if not v]
            lines.append(f"- {r['id']} ({r['q']}): score={r['score']}, failed={failed}, first={r['first_company']} / {r['first_match']}")

    lines.extend(["", "## Lowest 100", "", "| id | score | tags | q | first | failed |", "|---|---:|---|---|---|---|"])
    for r in sorted(records, key=lambda x: (int(x["score"]), int(x["elapsed_ms"])))[:100]:
        failed = ",".join(k for k, v in (r.get("checks") or {}).items() if not v)
        lines.append(f"| {r['id']} | {r['score']} | {','.join(r.get('tags') or [])} | {r['q']} | {r['first_company']} / {r['first_match']} | {failed} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--out-dir", default="artifacts/vendor_recommendation_quality_qa")
    parser.add_argument("--timeout-sec", type=float, default=25.0)
    parser.add_argument("--max-latency-ms", type=int, default=5000)
    parser.add_argument("--target-count", type=int, default=5000)
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
    stem = f"vendor_recommendation_5000_qa_{time.strftime('%Y%m%d_%H%M%S')}"
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
