from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


DEFAULT_API_URL = "http://49.50.133.160:8001/chat"
OUT_DIR = Path("artifacts/qa/server_varied_1h")
OUT_DIR.mkdir(parents=True, exist_ok=True)


QUESTION_BANK: list[dict[str, Any]] = [
    # 개념/용어 설명
    {"id": "concept_price_terms", "agency_type": "local_government", "question": "추정가격, 예정가격, 기초금액, 추정금액 차이가 뭐야?", "expected": ["추정가격", "예정가격", "기초금액"]},
    {"id": "concept_contract_methods", "agency_type": "local_government", "question": "일반경쟁, 제한경쟁, 지명경쟁, 수의계약 개념 차이를 설명해줘.", "expected": ["일반경쟁", "제한경쟁", "수의계약"]},
    {"id": "concept_contract_types", "agency_type": "local_government", "question": "총액계약, 단가계약, 장기계속계약, 계속비계약은 어떻게 구분해?", "expected": ["총액", "단가", "장기계속"]},
    {"id": "concept_mas_third_party", "agency_type": "local_government", "question": "제3자단가계약과 다수공급자계약(MAS)은 무슨 차이야?", "expected": ["제3자", "다수공급자", "MAS"]},
    {"id": "concept_rfp_scope", "agency_type": "local_government", "question": "용역계약에서 제안요청서와 과업지시서 차이가 뭐야?", "expected": ["제안요청서", "과업지시서", "용역"]},
    {"id": "concept_main_incidental_work", "agency_type": "local_government", "question": "공사계약에서 주된 공사와 부대공사 개념 차이를 알려줘.", "expected": ["주된 공사", "부대공사", "공사"]},
    {"id": "concept_joint_methods", "agency_type": "local_government", "question": "공동이행방식과 분담이행방식은 어떻게 달라?", "expected": ["공동이행", "분담이행", "공동"]},
    {"id": "concept_delay_penalty", "agency_type": "local_government", "question": "지체상금과 지연배상금은 같은 말이야? 실무상 어떻게 설명하면 돼?", "expected": ["지체", "지연", "계약"]},

    # 물품 구매/지역상품 지원
    {"id": "goods_led_80m_local", "agency_type": "local_government", "question": "8천만원으로 LED 조명을 사려고 해. 부산업체 활용 방법과 후보를 같이 알려줘.", "expected": ["LED", "부산", "업체"]},
    {"id": "goods_led_synonym", "agency_type": "local_government", "question": "엘이디등 구매할 건데 부산 지역업체 있어? 조달등록이나 인증도 같이 봐줘.", "expected": ["LED", "부산", "업체"]},
    {"id": "goods_cctv_candidates", "agency_type": "local_government", "question": "CCTV 구매 예정인데 부산업체 후보와 종합쇼핑몰 등록 여부를 알려줘.", "expected": ["CCTV", "부산", "종합쇼핑몰"]},
    {"id": "goods_furniture_mas", "agency_type": "local_government", "question": "사무용 가구를 종합쇼핑몰로 사면 부산업체를 고려할 수 있는 방법이 있어?", "expected": ["가구", "종합쇼핑몰", "부산"]},
    {"id": "goods_laptop_no_company", "agency_type": "local_government", "question": "노트북 3천만원 구매는 계약방법을 어떻게 잡아야 해?", "expected": ["노트북", "계약", "구매"]},
    {"id": "goods_software", "agency_type": "local_government", "question": "상용소프트웨어를 구매할 때 MAS나 제3자단가계약을 검토해야 해?", "expected": ["소프트웨어", "MAS", "제3자"]},
    {"id": "goods_excellent_procurement", "agency_type": "local_government", "question": "우수조달물품 지정 제품이면 부산 지역상품 구매에 어떻게 활용할 수 있어?", "expected": ["우수조달", "부산", "구매"]},
    {"id": "goods_innovation_product", "agency_type": "local_government", "question": "혁신제품이나 혁신시제품이면 수의계약이나 우선구매 검토가 가능해?", "expected": ["혁신제품", "수의계약", "확인"]},
    {"id": "goods_sme_direct_production", "agency_type": "local_government", "question": "중소기업자간 경쟁제품이면 직접생산확인증명서를 어떻게 확인해야 해?", "expected": ["중소기업", "직접생산", "확인"]},
    {"id": "goods_public_purchase", "agency_type": "local_government", "question": "공공구매 우선구매 제도로 부산업체 제품을 연결하려면 어떤 제도를 봐야 해?", "expected": ["공공구매", "우선구매", "부산"]},

    # 수의계약/금액/법령 판단
    {"id": "direct_20m_goods", "agency_type": "local_government", "question": "2천만원 물품은 1인 견적 수의계약이 가능해?", "expected": ["2천만원", "수의계약", "견적"]},
    {"id": "direct_50m_policy_company", "agency_type": "local_government", "question": "5천만원 여성기업 물품 구매는 수의계약으로 검토할 수 있어?", "expected": ["여성기업", "수의계약", "확인"]},
    {"id": "direct_200m_goods", "agency_type": "local_government", "question": "2억 물품을 그냥 수의계약으로 살 수 있어?", "expected": ["2억", "수의계약", "입찰"]},
    {"id": "direct_tech_product_200m", "agency_type": "local_government", "question": "기술개발제품이면 2억 물품도 수의계약 가능성이 있는지 검토해줘.", "expected": ["기술개발제품", "수의계약", "확인"]},
    {"id": "direct_sme_and_tech", "agency_type": "local_government", "question": "중소기업자간 경쟁제품이면서 기술개발제품인 경우 구매경로를 어떻게 봐야 해?", "expected": ["중소기업", "기술개발제품", "구매"]},
    {"id": "direct_exception_unknown_item", "agency_type": "local_government", "question": "품목은 아직 정하지 않았는데 8천만원 예산이면 수의계약 가능 여부를 어떻게 검토해?", "expected": ["품목", "8천만원", "수의계약"]},

    # 지역제한/가점/공동도급
    {"id": "regional_limit_compare", "agency_type": "local_government", "question": "지역제한경쟁입찰 기준금액을 국가, 공기업 및 준정부기관, 지방자치단체로 비교해줘.", "expected": ["지역제한", "국가", "지방"]},
    {"id": "regional_limit_local_construction", "agency_type": "local_government", "question": "지방계약에서 종합공사 지역제한 기준은 어떻게 확인해야 해?", "expected": ["지방계약", "종합공사", "지역제한"]},
    {"id": "regional_limit_service", "agency_type": "local_government", "question": "용역계약도 지역제한경쟁입찰을 검토할 수 있어? 부산업체 활용 관점에서 설명해줘.", "expected": ["용역", "지역제한", "부산"]},
    {"id": "regional_points_service", "agency_type": "local_government", "question": "용역 적격심사에서 지역업체 참여도나 가점은 어떤 때 검토해야 해?", "expected": ["용역", "지역업체", "평가"]},
    {"id": "regional_points_compare", "agency_type": "local_government", "question": "지역업체 가점제도는 국가계약, 지방계약, 공기업 기준이 서로 다를 수 있어?", "expected": ["지역업체", "국가", "지방"]},
    {"id": "joint_contract_construction", "agency_type": "local_government", "question": "전기공사에서 지역의무공동도급이나 공동수급을 활용할 수 있는지 검토해줘.", "expected": ["전기공사", "공동", "지역"]},
    {"id": "joint_contract_public_corp", "agency_type": "public_corporation", "question": "공기업 발주 공사에서 지역업체 공동도급을 검토할 때 주의할 점은 뭐야?", "expected": ["공기업", "공동", "지역업체"]},

    # 용역
    {"id": "service_cleaning_80m", "agency_type": "local_government", "question": "8천만원 청소용역을 부산 지역업체로 계약하려면 어떤 제도를 검토해야 해?", "expected": ["청소", "용역", "부산"]},
    {"id": "service_event", "agency_type": "local_government", "question": "행사용역을 부산업체 중심으로 발주하려면 참가자격을 어떻게 조심해서 설계해야 해?", "expected": ["용역", "부산", "참가자격"]},
    {"id": "service_research", "agency_type": "local_government", "question": "학술용역에서 지역업체를 우대하고 싶을 때 평가항목으로 넣어도 돼?", "expected": ["학술용역", "지역업체", "평가"]},
    {"id": "service_maintenance", "agency_type": "local_government", "question": "시스템 유지보수 용역은 물품 구매랑 다르게 어떤 계약 쟁점을 봐야 해?", "expected": ["유지보수", "용역", "계약"]},
    {"id": "service_proposal_eval", "agency_type": "local_government", "question": "협상에 의한 계약에서 제안서 평가와 가격평가는 어떻게 설명하면 돼?", "expected": ["협상", "제안서", "가격"]},
    {"id": "service_rfp_local", "agency_type": "local_government", "question": "과업지시서에 부산업체 활용 조건을 넣으면 부당제한이 될 수 있어?", "expected": ["과업지시서", "부산", "제한"]},

    # 공사
    {"id": "construction_electric_200m", "agency_type": "local_government", "question": "2억원 전기공사를 부산 지역업체 중심으로 발주하려면 지역제한을 먼저 봐야 해?", "expected": ["전기공사", "지역제한", "부산"]},
    {"id": "construction_info_telecom", "agency_type": "local_government", "question": "정보통신공사는 종합공사와 전문공사 기준을 어떻게 구분해서 봐야 해?", "expected": ["정보통신공사", "공사", "구분"]},
    {"id": "construction_split_order", "agency_type": "local_government", "question": "공사를 물품이랑 나눠 발주하면 분리발주나 쪼개기 발주 문제가 생길 수 있어?", "expected": ["분리발주", "공사", "물품"]},
    {"id": "construction_material_direct", "agency_type": "local_government", "question": "공사용자재 직접구매 대상 품목인지 확인하려면 어떤 기준을 봐야 해?", "expected": ["공사용자재", "직접구매", "품목"]},
    {"id": "construction_main_incidental", "agency_type": "local_government", "question": "부대공사로 묶을 수 있는지 판단할 때 어떤 자료를 확인해야 해?", "expected": ["부대공사", "확인", "공사"]},
    {"id": "construction_completion_inspection", "agency_type": "local_government", "question": "공사 준공검사와 기성검사는 계약 단계에서 어떻게 설명하면 돼?", "expected": ["준공검사", "기성검사", "공사"]},

    # 기관유형
    {"id": "agency_public_corp_direct", "agency_type": "public_corporation", "question": "공기업 및 준정부기관 계약사무규칙 기준으로 수의계약을 볼 때 국가계약법과 뭐가 달라?", "expected": ["공기업", "준정부기관", "수의계약"]},
    {"id": "agency_national_regional", "agency_type": "national_agency", "question": "국가기관에서 지역제한경쟁입찰을 검토할 때 지방계약과 혼동하면 안 되는 점을 알려줘.", "expected": ["국가기관", "지역제한", "지방"]},
    {"id": "agency_local_default", "agency_type": "local_government", "question": "부산시 기준으로 지역상품 구매지원 제도를 한 번에 정리해줘.", "expected": ["부산", "지역상품", "구매"]},
    {"id": "agency_invested", "agency_type": "invested_institution", "question": "부산 출자출연기관이 지역업체 활용을 검토할 때 지방계약법을 그대로 보면 돼?", "expected": ["출자", "지방계약", "확인"]},

    # 감사/리스크/절차
    {"id": "audit_local_preference", "agency_type": "local_government", "question": "부산업체를 활용하려고 할 때 감사에서 특혜로 보이지 않게 하려면 뭘 남겨야 해?", "expected": ["부산", "감사", "특혜"]},
    {"id": "audit_restrictive_qualification", "agency_type": "local_government", "question": "입찰참가자격을 너무 좁게 잡으면 부당제한이 될 수 있어? 예시와 함께 설명해줘.", "expected": ["입찰참가자격", "부당제한", "확인"]},
    {"id": "procedure_contract_review", "agency_type": "local_government", "question": "발주 전에 계약심사나 일상감사를 거쳐야 하는지 어떻게 판단해?", "expected": ["계약심사", "일상감사", "발주"]},
    {"id": "procedure_full_flow", "agency_type": "local_government", "question": "공공계약 절차를 처음부터 끝까지 흐름으로 설명해줘.", "expected": ["기본계획", "입찰", "계약"]},
    {"id": "procedure_bid_notice", "agency_type": "local_government", "question": "입찰공고문 만들 때 지역업체 활용과 관련해서 꼭 확인해야 할 항목은 뭐야?", "expected": ["입찰공고", "지역업체", "확인"]},
    {"id": "procedure_contract_change", "agency_type": "local_government", "question": "계약금액 조정이나 설계변경 질문이 들어오면 어떤 순서로 검토해야 해?", "expected": ["계약금액", "설계변경", "검토"]},

    # 업체 후보/표시 품질
    {"id": "company_led_cert", "agency_type": "local_government", "question": "LED 조명 부산업체 후보 중 기술개발제품이나 우수조달물품 관련 표시가 있으면 같이 보여줘.", "expected": ["LED", "부산", "기술개발"]},
    {"id": "company_cctv_policy", "agency_type": "local_government", "question": "CCTV 부산업체 후보에서 여성기업이나 장애인기업 같은 정책기업 여부도 확인해줘.", "expected": ["CCTV", "부산", "정책기업"]},
    {"id": "company_service_license", "agency_type": "local_government", "question": "청소용역 부산업체 후보를 볼 때 면허나 업종 정보도 확인할 수 있어?", "expected": ["청소", "부산", "업체"]},
    {"id": "company_construction_license", "agency_type": "local_government", "question": "전기공사 부산업체 후보는 제품이 아니라 면허 기준으로 찾아야 하는 거지?", "expected": ["전기공사", "면허", "부산"]},
]


FORBIDDEN_MARKERS = [
    "Traceback",
    "MCP_FAILED",
    "No module named",
    "GEMINI_API_KEY",
    "function_call",
    "Internal Server Error",
    "gs_certified_product",
    "priority_purchase_product",
    "smpp_tech_product_api",
    "mas_excel_bootstrap",
    "| 인증유형 |",
    "| 유효기간 |",
]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def post_question(api_url: str, case: dict[str, Any], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    payload = {
        "message": case["question"],
        "agency_type": case.get("agency_type") or "local_government",
        "history": [],
    }
    try:
        response = requests.post(api_url, json=payload, timeout=timeout)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            data = response.json()
        except Exception:
            data = {"raw_response": response.text}
        return {
            "case": case,
            "ok": response.ok,
            "status_code": response.status_code,
            "elapsed_ms_client": elapsed_ms,
            "response": data,
            "error": None,
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "case": case,
            "ok": False,
            "status_code": None,
            "elapsed_ms_client": elapsed_ms,
            "response": {},
            "error": repr(exc),
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }


def _answer_text(response: dict[str, Any]) -> str:
    return str(response.get("answer") or response.get("raw_response") or "")


def assess(record: dict[str, Any]) -> dict[str, Any]:
    case = record["case"]
    response = record.get("response") or {}
    answer = _answer_text(response)
    expected = case.get("expected") or []
    missing_expected = [term for term in expected if term not in answer]
    forbidden = [marker for marker in FORBIDDEN_MARKERS if marker in answer]
    candidate_counts = response.get("candidate_counts_by_type") or {}
    candidate_total = sum(v for v in candidate_counts.values() if isinstance(v, int)) if isinstance(candidate_counts, dict) else 0
    warnings = []
    speed = record.get("elapsed_ms_client") or 0
    if missing_expected:
        warnings.append(f"expected_terms_missing={missing_expected}")
    if forbidden:
        warnings.append(f"forbidden_markers={forbidden}")
    if speed > 60000:
        warnings.append("very_slow_over_60s")
    elif speed > 30000:
        warnings.append("slow_over_30s")
    if not record.get("ok"):
        warnings.append("http_or_exception_failure")
    if response.get("post_scan_critical_count", 0):
        warnings.append("post_scan_critical")
    if "company" in case["id"] and candidate_total == 0 and "업체" not in answer:
        warnings.append("company_candidate_not_visible")
    if "개념" in case["question"] or "차이" in case["question"] or "뭐야" in case["question"]:
        if not any(token in answer for token in ["개념", "뜻", "차이", "구분"]):
            warnings.append("concept_explanation_may_be_weak")
    return {
        "missing_expected": missing_expected,
        "forbidden_markers": forbidden,
        "candidate_total": candidate_total,
        "warnings": warnings,
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [r.get("elapsed_ms_client") or 0 for r in records if r.get("ok")]
    warnings = [w for r in records for w in (r.get("assessment") or {}).get("warnings", [])]
    by_case: dict[str, int] = {}
    for r in records:
        cid = r["case"]["id"]
        by_case[cid] = by_case.get(cid, 0) + 1
    return {
        "record_count": len(records),
        "unique_case_count": len(by_case),
        "ok_count": sum(1 for r in records if r.get("ok")),
        "warning_count": len(warnings),
        "avg_latency_ms": int(statistics.mean(latencies)) if latencies else 0,
        "p50_latency_ms": int(statistics.median(latencies)) if latencies else 0,
        "max_latency_ms": max(latencies) if latencies else 0,
        "warning_samples": warnings[:30],
        "case_repetition_max": max(by_case.values()) if by_case else 0,
    }


def write_outputs(
    *,
    api_url: str,
    run_id: str,
    json_path: Path,
    md_path: Path,
    progress_path: Path,
    records: list[dict[str, Any]],
    finished: bool,
) -> None:
    summary = summarize(records)
    payload = {
        "run_id": run_id,
        "api_url": api_url,
        "finished": finished,
        "question_bank_count": len(QUESTION_BANK),
        "summary": summary,
        "records": records,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    progress_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "finished": finished,
                "summary": summary,
                "json_path": str(json_path),
                "md_path": str(md_path),
                "last_update": datetime.now().isoformat(timespec="seconds"),
                "last_case": records[-1]["case"]["id"] if records else None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        f"# 서버 1시간 다양질문 QA 리포트 ({run_id})",
        "",
        f"- API: `{api_url}`",
        f"- 완료 여부: `{finished}`",
        f"- 질문 풀: `{len(QUESTION_BANK)}개`",
        f"- 호출 수: `{len(records)}`",
        f"- 고유 질문 수: `{summary['unique_case_count']}`",
        f"- 평균 응답시간: `{summary['avg_latency_ms']}ms`",
        f"- P50 응답시간: `{summary['p50_latency_ms']}ms`",
        f"- 최대 응답시간: `{summary['max_latency_ms']}ms`",
        f"- 경고 수: `{summary['warning_count']}`",
        "",
        "## 요약",
        "",
        "| # | 질문ID | HTTP | 응답시간 | Tier | 모델 | 근거카드 | 실무카드 | 해석사례 | 내부DB | 외부MCP | 업체후보 | 경고 |",
        "|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for idx, record in enumerate(records, start=1):
        response = record.get("response") or {}
        assessment = record.get("assessment") or {}
        lines.append(
            "| {idx} | `{case_id}` | {status} | {elapsed}ms | {tier} | {model} | {cards} | {manual_cards} | {pps_cards} | {internal} | {external} | {candidates} | {warnings} |".format(
                idx=idx,
                case_id=record["case"]["id"],
                status=record.get("status_code"),
                elapsed=record.get("elapsed_ms_client"),
                tier=response.get("tier_resolved", ""),
                model=response.get("model_selected", ""),
                cards=response.get("evidence_card_count", ""),
                manual_cards=response.get("practice_manual_card_count", ""),
                pps_cards=response.get("pps_qa_card_count", ""),
                internal=response.get("internal_db_hit_count", ""),
                external=response.get("external_mcp_fallback_count", ""),
                candidates=assessment.get("candidate_total", ""),
                warnings=", ".join(assessment.get("warnings") or []),
            )
        )

    lines.extend(["", "## 질문별 상세", ""])
    for idx, record in enumerate(records, start=1):
        response = record.get("response") or {}
        assessment = record.get("assessment") or {}
        answer = _answer_text(response)
        lines.extend([
            f"### {idx}. {record['case']['id']}",
            "",
            f"**기관유형**: `{record['case'].get('agency_type', '')}`",
            "",
            f"**질문**: {record['case']['question']}",
            "",
            f"**응답시간**: `{record.get('elapsed_ms_client')}ms`",
            "",
            f"**메타**: tier=`{response.get('tier_resolved', '')}`, model=`{response.get('model_selected', '')}`, evidence_cards=`{response.get('evidence_card_count', '')}`, practice_cards=`{response.get('practice_manual_card_count', '')}`, pps_qa_cards=`{response.get('pps_qa_card_count', '')}`, internal_db=`{response.get('internal_db_hit_count', '')}`, external_mcp=`{response.get('external_mcp_fallback_count', '')}`, tool_calls=`{response.get('tool_call_count', '')}`",
            "",
            f"**자동 경고**: {', '.join(assessment.get('warnings') or []) or '없음'}",
            "",
            "**답변**",
            "",
            answer.strip() or "(empty)",
            "",
            "---",
            "",
        ])
    md_path.write_text("\n".join(lines), encoding="utf-8")


def iter_cases(seed: int):
    rng = random.Random(seed)
    while True:
        batch = QUESTION_BANK[:]
        rng.shuffle(batch)
        for case in batch:
            yield case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--duration-minutes", type=float, default=60)
    parser.add_argument("--pause-seconds", type=float, default=35)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--max-calls", type=int, default=0, help="0 means run until duration expires")
    parser.add_argument("--seed", type=int, default=20260509)
    args = parser.parse_args()

    run_id = now_stamp()
    json_path = OUT_DIR / f"server_qa_varied_1h_{run_id}.json"
    md_path = OUT_DIR / f"server_qa_varied_1h_{run_id}.md"
    progress_path = OUT_DIR / "latest_progress.json"
    deadline = time.perf_counter() + args.duration_minutes * 60
    records: list[dict[str, Any]] = []

    for case in iter_cases(args.seed):
        if time.perf_counter() >= deadline:
            break
        if args.max_calls and len(records) >= args.max_calls:
            break
        record = post_question(args.api_url, case, args.timeout_seconds)
        record["assessment"] = assess(record)
        records.append(record)
        write_outputs(
            api_url=args.api_url,
            run_id=run_id,
            json_path=json_path,
            md_path=md_path,
            progress_path=progress_path,
            records=records,
            finished=False,
        )
        time.sleep(args.pause_seconds)

    write_outputs(
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
