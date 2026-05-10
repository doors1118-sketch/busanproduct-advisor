from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import run_server_qa_4h_full as base


DEFAULT_API_URL = base.DEFAULT_API_URL
OUT_DIR = Path("artifacts/qa/server_toolmix_2h")
OUT_DIR.mkdir(parents=True, exist_ok=True)
ORIGINAL_SUMMARIZE = base.summarize


TOOL_HEAVY_CASES: list[dict[str, Any]] = [
    {
        "id": "tool_agency_national_vs_local_region",
        "category": "tool_heavy_agency_conflict",
        "agency_type": "national_agency",
        "question": "국가기관 지역제한경쟁입찰에 지방계약법의 부산 지역제한 기준을 참고해도 되는지, 국가계약 기준과 충돌되는 부분을 비교해줘.",
        "expected": ["국가기관", "국가계약", "지방계약", "지역제한"],
    },
    {
        "id": "tool_split_goods_construction",
        "category": "tool_heavy_split_procurement",
        "agency_type": "local_government",
        "question": "공사에 포함된 관급자재를 물품으로 따로 발주하려고 하는데 분리발주, 쪼개기 발주, 직접구매 기준을 같이 검토해줘.",
        "expected": ["공사", "물품", "분리발주", "직접구매"],
    },
    {
        "id": "tool_indirect_cost_extension",
        "category": "tool_heavy_construction_change",
        "agency_type": "local_government",
        "question": "공사기간이 발주기관 사유로 늘어난 경우 간접비나 계약금액 조정은 어떤 행정규칙과 절차를 봐야 해?",
        "expected": ["공사기간", "간접비", "계약금액"],
    },
    {
        "id": "tool_policy_purchase_performance",
        "category": "tool_heavy_interpretation",
        "agency_type": "local_government",
        "question": "여성기업제품과 장애인기업제품 구매도 중소기업제품 구매실적에 포함되는지 근거 중심으로 설명해줘.",
        "expected": ["여성기업", "장애인기업", "중소기업제품", "구매실적"],
    },
    {
        "id": "tool_mas_second_stage_sme",
        "category": "tool_heavy_mas",
        "agency_type": "local_government",
        "question": "종합쇼핑몰 MAS 2단계 경쟁 기준이 일반물품과 중소기업자간 경쟁제품에서 달라지는지 법령과 행정규칙 기준으로 비교해줘.",
        "expected": ["MAS", "2단계", "중소기업자간"],
    },
    {
        "id": "tool_innovation_direct_contract",
        "category": "tool_heavy_innovation",
        "agency_type": "local_government",
        "question": "혁신제품, 혁신시제품, 기술개발제품은 금액과 관계없이 수의계약 검토가 가능한지 우선구매와 수의계약 근거를 분리해서 설명해줘.",
        "expected": ["혁신제품", "기술개발제품", "수의계약", "우선구매"],
    },
    {
        "id": "tool_specific_brand_audit",
        "category": "tool_heavy_audit",
        "agency_type": "local_government",
        "question": "특정 브랜드 노트북만 규격서에 넣은 사례가 감사에서 문제될 수 있는지, 동등 이상 표현과 제한경쟁 리스크를 같이 검토해줘.",
        "expected": ["특정 브랜드", "동등", "부당제한"],
    },
    {
        "id": "tool_public_corp_law_scope",
        "category": "tool_heavy_agency_conflict",
        "agency_type": "public_corporation",
        "question": "공기업이 부산업체를 우대하려고 할 때 지방계약법, 국가계약법, 공기업 계약사무규칙 중 무엇을 우선 봐야 하는지 설명해줘.",
        "expected": ["공기업", "지방계약", "국가계약"],
    },
    {
        "id": "tool_annex_regional_points",
        "category": "tool_heavy_annex",
        "agency_type": "local_government",
        "question": "지역업체 참여도나 가점은 조문만 보면 안 되고 별표나 낙찰자 결정기준을 봐야 하는 거지? 확인 순서를 알려줘.",
        "expected": ["지역업체", "가점", "낙찰자 결정기준"],
    },
    {
        "id": "tool_mixed_design_print",
        "category": "tool_heavy_mixed_object",
        "agency_type": "local_government",
        "question": "홍보물 디자인, 편집, 인쇄, 납품이 한 사업에 섞여 있으면 용역과 물품 중 주된 계약 목적을 어떻게 판단해?",
        "expected": ["디자인", "인쇄", "용역", "물품"],
    },
]


GENERAL_CASES: list[dict[str, Any]] = [
    {
        "id": "general_goods_computer_60m",
        "category": "general_goods_route",
        "agency_type": "local_government",
        "question": "예산 6천만원으로 컴퓨터를 구매하려고 해. 계약 방법과 부산업체 후보를 안내해줘.",
        "expected": ["컴퓨터", "종합쇼핑몰", "부산"],
    },
    {
        "id": "general_cctv_candidates_only",
        "category": "general_company",
        "agency_type": "local_government",
        "question": "CCTV 부산업체 후보만 간단히 찾아줘. 계약 가능 여부 판단은 빼줘.",
        "expected": ["CCTV", "부산"],
    },
    {
        "id": "general_service_security",
        "category": "general_service",
        "agency_type": "local_government",
        "question": "청사 경비용역을 부산업체 중심으로 검토하려면 지역제한과 면허를 어떻게 봐야 해?",
        "expected": ["경비용역", "지역제한", "면허"],
    },
    {
        "id": "general_construction_landscape",
        "category": "general_construction",
        "agency_type": "local_government",
        "question": "조경공사를 부산업체 중심으로 발주하려면 지역제한과 면허요건을 어떻게 설계해야 해?",
        "expected": ["조경공사", "부산", "면허"],
    },
    {
        "id": "general_goods_procedure",
        "category": "general_procedure",
        "agency_type": "local_government",
        "question": "물품 구매 절차를 기본계획부터 검수와 대금지급까지 흐름으로 안내해줘.",
        "expected": ["물품", "검수", "대가"],
    },
    {
        "id": "general_mas_aircon",
        "category": "general_mas",
        "agency_type": "local_government",
        "question": "냉난방기 구매는 종합쇼핑몰로 처리할 수 있는지, 부산업체 고려는 어떻게 하는지 알려줘.",
        "expected": ["냉난방기", "종합쇼핑몰", "부산"],
    },
    {
        "id": "general_sme_camera",
        "category": "general_sme",
        "agency_type": "local_government",
        "question": "보안용카메라가 중소기업자간 경쟁제품이면 직접생산확인과 종합쇼핑몰 후보를 같이 봐야 해?",
        "expected": ["보안용카메라", "중소기업", "직접생산"],
    },
    {
        "id": "general_event_service",
        "category": "general_service",
        "agency_type": "local_government",
        "question": "행사용역을 부산업체 중심으로 발주하려면 참가자격을 어떻게 조심해서 설계해야 해?",
        "expected": ["행사용역", "부산업체", "참가자격"],
    },
    {
        "id": "general_price_terms",
        "category": "general_concept",
        "agency_type": "local_government",
        "question": "추정가격, 예정가격, 기초금액, 추정금액 차이를 실무적으로 설명해줘.",
        "expected": ["추정가격", "예정가격", "기초금액"],
    },
    {
        "id": "general_notebook_45m",
        "category": "general_goods_route",
        "agency_type": "local_government",
        "question": "노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?",
        "expected": ["노트북", "견적", "종합쇼핑몰"],
    },
]


QUESTION_BANK = TOOL_HEAVY_CASES + GENERAL_CASES


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def iter_toolmix_cases(seed: int):
    rng = random.Random(seed)
    heavy = TOOL_HEAVY_CASES[:]
    general = GENERAL_CASES[:]
    while True:
        rng.shuffle(heavy)
        rng.shuffle(general)
        for left, right in zip(heavy, general):
            yield left
            yield right


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [r.get("elapsed_ms_client") or 0 for r in records if r.get("ok")]
    heavy_count = sum(1 for r in records if str(r["case"].get("category", "")).startswith("tool_heavy"))
    tool_calls = []
    for r in records:
        response = r.get("response") or {}
        value = response.get("tool_call_count")
        if isinstance(value, int):
            tool_calls.append(value)
    return {
        **ORIGINAL_SUMMARIZE(records),
        "tool_heavy_count": heavy_count,
        "general_count": len(records) - heavy_count,
        "toolmix_heavy_ratio": round(heavy_count / len(records), 3) if records else 0,
        "avg_tool_call_count": round(statistics.mean(tool_calls), 2) if tool_calls else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--duration-minutes", type=float, default=120)
    parser.add_argument("--pause-seconds", type=float, default=8)
    parser.add_argument("--timeout-seconds", type=int, default=150)
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260510)
    args = parser.parse_args()

    run_id = f"toolmix_2h_{now_stamp()}"
    json_path = OUT_DIR / f"{run_id}.json"
    md_path = OUT_DIR / f"{run_id}.md"
    progress_path = OUT_DIR / "latest_progress.json"
    deadline = time.perf_counter() + args.duration_minutes * 60
    records: list[dict[str, Any]] = []

    base.QUESTION_BANK = QUESTION_BANK
    base.summarize = summarize

    for case in iter_toolmix_cases(args.seed):
        if time.perf_counter() >= deadline:
            break
        if args.max_calls and len(records) >= args.max_calls:
            break
        record = base.post_question(args.api_url, case, args.timeout_seconds)
        record["assessment"] = base.assess(record)
        records.append(record)
        base.write_outputs(
            api_url=args.api_url,
            run_id=run_id,
            json_path=json_path,
            md_path=md_path,
            progress_path=progress_path,
            records=records,
            finished=False,
        )
        time.sleep(args.pause_seconds)

    base.write_outputs(
        api_url=args.api_url,
        run_id=run_id,
        json_path=json_path,
        md_path=md_path,
        progress_path=progress_path,
        records=records,
        finished=True,
    )
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
