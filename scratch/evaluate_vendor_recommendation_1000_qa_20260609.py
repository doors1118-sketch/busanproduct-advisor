from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluate_vendor_recommendation_comprehensive_qa_20260609 import evaluate


def case(
    case_id: str,
    q: str,
    intent: str,
    must: list[str],
    *,
    budget_krw: int,
    tags: list[str],
    policy: bool = False,
    policy_label: str = "",
    convenience: list[str] | None = None,
    avoid_top1: list[str] | None = None,
    top1_any: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "q": q,
        "intent": intent,
        "must": must,
        "budget_krw": budget_krw,
        "tags": tags,
        "policy": policy,
        "policy_label": policy_label,
        "convenience": convenience or [],
        "avoid_top1": avoid_top1 or [],
        "top1_any": top1_any or [],
    }


ITEMS: list[dict[str, Any]] = [
    # Goods
    {"key": "led", "name": "LED 조명", "intent": "물품", "must": ["led", "조명"], "policy": True, "caps": ["shopping_or_mas", "shopping", "mas"], "avoid": []},
    {"key": "cctv", "name": "CCTV 보안카메라", "intent": "물품", "must": ["cctv", "카메라", "영상감시"], "policy": True, "caps": ["shopping", "shopping_or_mas"], "avoid": []},
    {"key": "desktop", "name": "데스크톱 컴퓨터", "intent": "물품", "must": ["컴퓨터", "데스크톱", "데스크탑", "pc"], "policy": True, "caps": ["shopping_or_mas", "shopping", "mas"], "avoid": []},
    {"key": "notebook", "name": "노트북", "intent": "물품", "must": ["노트북", "컴퓨터"], "policy": True, "caps": ["shopping_or_mas"], "avoid": []},
    {"key": "server", "name": "서버 컴퓨터", "intent": "물품", "must": ["서버", "컴퓨터"], "policy": True, "caps": [], "avoid": []},
    {"key": "security_sw", "name": "보안 소프트웨어", "intent": "물품", "must": ["소프트웨어", "보안", "sw", "프로그램"], "policy": True, "caps": [], "avoid": []},
    {"key": "firewall", "name": "방화벽 장비", "intent": "물품", "must": ["방화벽", "보안", "장치"], "policy": True, "caps": [], "avoid": []},
    {"key": "toner", "name": "정품토너", "intent": "물품", "must": ["토너"], "policy": True, "caps": [], "avoid": ["축산", "식육", "식품"]},
    {"key": "projector", "name": "비디오프로젝터", "intent": "물품", "must": ["프로젝터", "비디오"], "policy": True, "caps": [], "avoid": []},
    {"key": "beam_typo", "name": "빔프로젝트", "intent": "물품", "must": ["프로젝터", "비디오"], "policy": True, "caps": [], "avoid": []},
    {"key": "drone", "name": "드론", "intent": "물품", "must": ["드론"], "policy": True, "caps": [], "avoid": []},
    {"key": "switchboard", "name": "분전반", "intent": "물품", "must": ["분전반", "배전반"], "policy": True, "caps": ["shopping_or_mas", "shopping", "mas", "venture_order"], "avoid": [], "top1": ["세풍전기"]},
    {"key": "aircon", "name": "냉난방기 에어컨", "intent": "물품", "must": ["냉난방", "에어컨", "공기조화"], "policy": True, "caps": [], "avoid": []},
    {"key": "furniture", "name": "사무용가구", "intent": "물품", "must": ["가구", "책상", "의자"], "policy": True, "caps": ["direct_production", "sme_competition"], "avoid": []},
    {"key": "desk", "name": "책상", "intent": "물품", "must": ["책상"], "policy": True, "caps": ["direct_production", "sme_competition"], "avoid": []},
    {"key": "chair", "name": "의자", "intent": "물품", "must": ["의자"], "policy": True, "caps": ["direct_production", "sme_competition"], "avoid": []},
    {"key": "cabinet", "name": "문서보관 캐비닛", "intent": "물품", "must": ["캐비닛", "보관함", "가구"], "policy": True, "caps": [], "avoid": []},
    {"key": "kitchen", "name": "급식실 주방기기", "intent": "물품", "must": ["주방", "급식", "조리"], "policy": True, "caps": [], "avoid": []},
    {"key": "remicon", "name": "레미콘", "intent": "물품", "must": ["레미콘", "콘크리트"], "policy": True, "caps": [], "avoid": []},
    {"key": "ascon", "name": "아스콘", "intent": "물품", "must": ["아스콘", "아스팔트"], "policy": True, "caps": [], "avoid": []},
    {"key": "elastic", "name": "체육시설 탄성포장재", "intent": "물품", "must": ["탄성포장", "포장재"], "policy": True, "caps": [], "avoid": []},
    {"key": "printing", "name": "홍보물 인쇄물", "intent": "물품", "must": ["인쇄", "홍보물", "책자", "현수막"], "policy": True, "caps": ["direct_production", "sme_competition"], "avoid": []},
    {"key": "banner", "name": "현수막", "intent": "물품", "must": ["현수막"], "policy": True, "caps": ["direct_production", "sme_competition"], "avoid": []},
    # Services
    {"key": "event", "name": "행사 용역", "intent": "용역", "must": ["행사", "이벤트", "공연", "전시"], "policy": False, "caps": [], "avoid": []},
    {"key": "translation", "name": "번역용역", "intent": "용역", "must": ["번역", "통역"], "policy": False, "caps": [], "avoid": []},
    {"key": "interpretation", "name": "국제행사 통역", "intent": "용역", "must": ["통역", "번역"], "policy": False, "caps": [], "avoid": []},
    {"key": "cleaning", "name": "건물 청소용역", "intent": "용역", "must": ["청소", "환경미화"], "policy": False, "caps": [], "avoid": []},
    {"key": "security", "name": "청사 경비용역", "intent": "용역", "must": ["경비", "시설경비"], "policy": False, "caps": [], "avoid": []},
    {"key": "facility", "name": "시설관리 용역", "intent": "용역", "must": ["시설관리", "건물관리", "건물(시설)관리"], "policy": False, "caps": [], "avoid": []},
    {"key": "disinfection", "name": "소독 방역 용역", "intent": "용역", "must": ["소독", "방역"], "policy": False, "caps": [], "avoid": ["손소독제", "살균제"]},
    {"key": "waste", "name": "폐기물 처리 용역", "intent": "용역", "must": ["폐기물"], "policy": False, "caps": [], "avoid": []},
    {"key": "elevator", "name": "승강기 유지보수", "intent": "용역", "must": ["승강기", "유지보수"], "policy": False, "caps": [], "avoid": []},
    {"key": "accounting", "name": "원가계산 용역", "intent": "용역", "must": ["원가", "계산"], "policy": False, "caps": [], "avoid": []},
    {"key": "legal", "name": "법률자문 용역", "intent": "용역", "must": ["법률", "변호", "법무"], "policy": False, "caps": [], "avoid": []},
    {"key": "bus", "name": "전세버스 임차", "intent": "용역", "must": ["버스", "여객", "전세"], "policy": False, "caps": [], "avoid": []},
    {"key": "design", "name": "디자인 서비스", "intent": "용역", "must": ["디자인", "시각", "환경"], "policy": False, "caps": [], "avoid": []},
    {"key": "video", "name": "영상 제작 용역", "intent": "용역", "must": ["영상", "동영상", "비디오"], "policy": False, "caps": [], "avoid": []},
    {"key": "marketing", "name": "홍보 마케팅 용역", "intent": "용역", "must": ["홍보", "마케팅"], "policy": False, "caps": [], "avoid": []},
    {"key": "signage", "name": "간판 안내판 제작", "intent": "용역", "must": ["간판", "안내판", "옥외광고"], "policy": False, "caps": [], "avoid": []},
    {"key": "system", "name": "정보시스템 구축", "intent": "용역", "must": ["시스템", "소프트웨어", "정보"], "policy": False, "caps": [], "avoid": []},
    # Works
    {"key": "electric", "name": "전기공사", "intent": "공사", "must": ["전기공사"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "communication", "name": "정보통신공사", "intent": "공사", "must": ["정보통신"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "fire", "name": "소방시설공사", "intent": "공사", "must": ["소방"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "landscape", "name": "조경식재공사", "intent": "공사", "must": ["조경", "식재"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "paving", "name": "도로 포장공사", "intent": "공사", "must": ["포장", "도로"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "indoor", "name": "실내건축공사", "intent": "공사", "must": ["실내건축", "건축"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "mechanical", "name": "기계설비공사", "intent": "공사", "must": ["기계설비"], "policy": False, "caps": ["capacity"], "avoid": []},
    {"key": "waterproof", "name": "방수공사", "intent": "공사", "must": ["방수"], "policy": False, "caps": ["capacity"], "avoid": []},
]


BASE_PHRASES = [
    "{item} 업체 추천",
    "{item} 부산 지역업체 찾아줘",
    "{item} 조달 등록 업체",
    "{item} 예산 {budget} 후보",
    "{item} 계약 가능한 업체",
    "{item} 수의계약 검토 후보",
    "{item} 공공기관 납품 가능한 업체",
    "{item} 구청에서 쓸 지역업체",
    "{item} 본사 부산 업체",
    "{item} 빠르게 계약 가능한 업체",
]

AMBIGUOUS_PHRASES = [
    "{short} 업체 좀 찾아줘",
    "{short} 살만한 지역업체",
    "{short} 맡길 업체",
    "{short} 가능한 부산 업체",
    "{short} 관련 조달업체",
]

CONVENIENCE_PHRASES = {
    "shopping_or_mas": ["{item} 계약 편한 업체", "{item} 쇼핑몰 또는 MAS 업체"],
    "shopping": ["종합쇼핑몰 등록 {item} 업체", "{item} 쇼핑몰 등록 부산업체"],
    "mas": ["MAS 등록 {item} 부산업체", "{item} 다수공급자계약 업체"],
    "direct_production": ["{item} 직접생산 업체", "{item} 직접생산증명서 보유 업체"],
    "sme_competition": ["중기간경쟁제품 {item} 업체", "{item} 중소기업자간 경쟁제품 업체"],
    "capacity": ["시공능력 확인 가능한 {item} 업체", "{item} 시공능력평가금액 있는 업체"],
    "venture_order": ["{item} 벤처나라 거래실적 업체", "{item} 벤처나라 주문거래 이력 업체"],
}

POLICY_PHRASES = [
    ("여성기업", "{label} {item} 업체"),
    ("장애인기업", "{label} {item} 업체"),
    ("사회적기업", "{label} {item} 업체"),
    ("벤처기업", "{label} {item} 업체"),
    ("창업기업", "{label} {item} 업체"),
]

MIXED_PAIRS = [
    ("LED 조명", "CCTV", ["led", "조명", "cctv", "카메라"], True),
    ("청소", "경비", ["청소", "경비"], False),
    ("행사 운영", "홍보물 인쇄", ["행사", "인쇄", "홍보"], True),
    ("컴퓨터", "보안 소프트웨어", ["컴퓨터", "소프트웨어", "보안"], True),
    ("전기공사", "소방공사", ["전기", "소방"], False),
    ("조경식재", "포장공사", ["조경", "포장"], False),
    ("주방기기", "냉난방기", ["주방", "냉난방", "에어컨"], True),
    ("통역", "행사 운영", ["통역", "번역", "행사"], False),
    ("책상 의자", "캐비닛", ["책상", "의자", "캐비닛", "가구"], True),
    ("드론", "영상 제작", ["드론", "영상"], False),
]


def short_name(name: str) -> str:
    return (
        name.replace(" 용역", "")
        .replace(" 구매", "")
        .replace("공사", "")
        .replace("부산", "")
        .strip()
    )


def build_cases(target_count: int) -> list[dict[str, Any]]:
    budgets = [10_000_000, 20_000_000, 30_000_000, 40_000_000, 50_000_000, 80_000_000, 100_000_000, 150_000_000, 300_000_000]
    out: list[dict[str, Any]] = []
    seen_q: set[str] = set()

    def add(c: dict[str, Any]) -> None:
        if c["q"] in seen_q:
            return
        seen_q.add(c["q"])
        out.append(c)

    seq = 0
    for item in ITEMS:
        for phrase in BASE_PHRASES:
            budget = budgets[seq % len(budgets)]
            add(case(
                f"base_{item['key']}_{seq:04d}",
                phrase.format(item=item["name"], budget=f"{budget // 10_000:,}만원"),
                item["intent"],
                item["must"],
                budget_krw=budget,
                tags=["base1000"],
                policy=bool(item["policy"]),
                avoid_top1=item.get("avoid") or [],
            ))
            seq += 1
        for phrase in AMBIGUOUS_PHRASES:
            budget = budgets[seq % len(budgets)]
            add(case(
                f"amb_{item['key']}_{seq:04d}",
                phrase.format(short=short_name(item["name"])),
                "모호",
                item["must"],
                budget_krw=budget,
                tags=["ambiguous"],
                policy=bool(item["policy"]),
                avoid_top1=item.get("avoid") or [],
            ))
            seq += 1
        for cap in item.get("caps") or []:
            for phrase in CONVENIENCE_PHRASES.get(cap, []):
                budget = budgets[seq % len(budgets)]
                add(case(
                    f"conv_{item['key']}_{cap}_{seq:04d}",
                    phrase.format(item=item["name"]),
                    "편의조건",
                    item["must"],
                    budget_krw=budget,
                    tags=["convenience"],
                    policy=bool(item["policy"]),
                    convenience=[cap],
                    avoid_top1=item.get("avoid") or [],
                    top1_any=item.get("top1") if cap == "venture_order" else [],
                ))
                seq += 1
        for label, phrase in POLICY_PHRASES:
            if item["intent"] == "공사":
                continue
            budget = budgets[seq % len(budgets)]
            add(case(
                f"policy_{item['key']}_{seq:04d}",
                phrase.format(label=label, item=item["name"]),
                "정책기업",
                item["must"],
                budget_krw=budget,
                tags=["policy"],
                policy=bool(item["policy"]),
                policy_label=label,
                avoid_top1=item.get("avoid") or [],
            ))
            seq += 1

    for idx, (left, right, must, policy) in enumerate(MIXED_PAIRS):
        for phrasing in (
            "{left} 또는 {right} 가능한 업체",
            "{left}랑 {right} 같이 검토할 업체",
            "{left}/{right} 계약 후보",
            "예산 {budget}으로 {left}와 {right} 업체",
        ):
            budget = budgets[(seq + idx) % len(budgets)]
            add(case(
                f"mixed_{idx}_{seq:04d}",
                phrasing.format(left=left, right=right, budget=f"{budget // 10_000:,}만원"),
                "혼합",
                must,
                budget_krw=budget,
                tags=["mixed"],
                policy=policy,
            ))
            seq += 1

    return out[:target_count]


CASES = build_cases(1000)


def write_report(path: Path, records: list[dict[str, Any]], base_url: str) -> None:
    scores = [int(r["score"]) for r in records]
    latencies = [int(r["elapsed_ms"]) for r in records]
    grades = {g: sum(1 for r in records if r["grade"] == g) for g in ("양호", "보통", "미흡")}
    tag_stats: dict[str, dict[str, Any]] = {}
    intent_stats: dict[str, dict[str, Any]] = {}
    for r in records:
        for bucket, key in ((tag_stats, ",".join(r.get("tags") or ["untagged"])), (intent_stats, r.get("intent") or "unknown")):
            stat = bucket.setdefault(key, {"count": 0, "scores": [], "weak": 0})
            stat["count"] += 1
            stat["scores"].append(int(r["score"]))
            if r["grade"] != "양호":
                stat["weak"] += 1
    lines = [
        "# 업체추천 1000개 고유 Q&A 신뢰도 평가",
        "",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- base_url: {base_url}",
        f"- total_cases: {len(records)}",
        f"- unique_questions: {len({r['q'] for r in records})}",
        f"- average_score: {round(statistics.mean(scores), 1) if scores else 0}/100",
        f"- median_score: {round(statistics.median(scores), 1) if scores else 0}/100",
        f"- min_score: {min(scores) if scores else 0}/100",
        f"- grade_counts: 양호 {grades['양호']} / 보통 {grades['보통']} / 미흡 {grades['미흡']}",
        f"- average_latency_ms: {round(statistics.mean(latencies), 1) if latencies else 0}",
        f"- p95_latency_ms: {sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else 0}",
        "",
        "## Tag Summary",
        "",
        "| tag | count | avg_score | weak |",
        "|---|---:|---:|---:|",
    ]
    for tag in sorted(tag_stats):
        stat = tag_stats[tag]
        lines.append(f"| {tag} | {stat['count']} | {round(statistics.mean(stat['scores']), 1)} | {stat['weak']} |")
    lines.extend(["", "## Intent Summary", "", "| intent | count | avg_score | weak |", "|---|---:|---:|---:|"])
    for intent in sorted(intent_stats):
        stat = intent_stats[intent]
        lines.append(f"| {intent} | {stat['count']} | {round(statistics.mean(stat['scores']), 1)} | {stat['weak']} |")
    weak = [r for r in records if r["grade"] != "양호"]
    lines.extend(["", "## Weak Cases", ""])
    if not weak:
        lines.append("- 없음")
    else:
        for r in weak:
            failed = [k for k, v in r["checks"].items() if not v]
            lines.append(f"- {r['id']} ({r['q']}): score={r['score']}, failed={failed}, first={r['first_company']} / {r['first_match']}")
    lines.extend(["", "## Lowest 50", "", "| id | score | tags | q | first | failed |", "|---|---:|---|---|---|---|"])
    for r in sorted(records, key=lambda x: (int(x["score"]), int(x["elapsed_ms"])))[:50]:
        failed = ",".join(k for k, v in r["checks"].items() if not v)
        lines.append(f"| {r['id']} | {r['score']} | {','.join(r.get('tags') or [])} | {r['q']} | {r['first_company']} | {failed} |")
    lines.extend(["", "## Sample Cases", ""])
    sample_records = [r for r in records if r["grade"] != "양호"][:30]
    if not sample_records:
        sample_records = sorted(records, key=lambda x: (int(x["score"]), int(x["elapsed_ms"])))[:30]
    for r in sample_records:
        lines.append(f"### {r['id']} - {r['q']}")
        lines.append(f"- tags={','.join(r.get('tags') or [])} score={r['score']} grade={r['grade']} elapsed_ms={r['elapsed_ms']}")
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
    parser.add_argument("--target-count", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    selected = CASES[: args.target_count]
    if len({c["q"] for c in selected}) != len(selected):
        raise SystemExit("duplicate questions detected")

    records: list[dict[str, Any]] = []
    workers = max(1, min(int(args.workers or 1), 8))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(evaluate, args.base_url, c, args.timeout_sec, args.max_latency_ms): i
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
    stem = f"vendor_recommendation_1000_qa_{time.strftime('%Y%m%d_%H%M%S')}"
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
            print("WEAK", json.dumps({"id": r["id"], "q": r["q"], "score": r["score"], "tags": r["tags"], "checks": r["checks"], "first": r["first_company"], "match": r["first_match"]}, ensure_ascii=False))
    return 0 if good == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
