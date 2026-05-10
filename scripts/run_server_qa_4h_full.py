from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_server_qa_varied_1h import QUESTION_BANK as BASE_QUESTIONS  # noqa: E402
from run_server_qa_varied_1h import FORBIDDEN_MARKERS  # noqa: E402


DEFAULT_API_URL = "http://49.50.133.160:8001/chat"
OUT_DIR = Path("artifacts/qa/server_4h_full")
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXTRA_QUESTIONS: list[dict[str, Any]] = [
    # 물품: 품목 다양화
    {"id": "goods_computer_60m_route", "category": "goods_route", "agency_type": "local_government", "question": "예산 6천만원으로 컴퓨터를 구매하려고 해. 계약 방법과 부산업체 후보를 안내해줘.", "expected": ["컴퓨터", "2인", "종합쇼핑몰", "부산"]},
    {"id": "goods_notebook_45m_policy_hidden", "category": "goods_route", "agency_type": "local_government", "question": "노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?", "expected": ["노트북", "견적", "종합쇼핑몰"]},
    {"id": "goods_printer_tech", "category": "goods_cert", "agency_type": "local_government", "question": "프린터 구매할 때 기술개발제품이나 우수조달물품 후보가 있으면 어떤 순서로 검토해?", "expected": ["프린터", "기술개발", "우수조달"]},
    {"id": "goods_server_sw_mixed", "category": "goods_service_boundary", "agency_type": "local_government", "question": "서버 장비와 설치 용역이 같이 있는 사업은 물품구매와 용역을 어떻게 나눠 봐야 해?", "expected": ["서버", "물품", "용역"]},
    {"id": "goods_air_conditioner_mas", "category": "shopping_mall", "agency_type": "local_government", "question": "냉난방기 구매는 종합쇼핑몰 MAS로 처리할 수 있는지, 부산업체 고려는 어떻게 하는지 알려줘.", "expected": ["냉난방기", "종합쇼핑몰", "부산"]},
    {"id": "goods_ev_charger_innovation", "category": "innovation", "agency_type": "local_government", "question": "전기차 충전기 구매에서 혁신제품이나 우수조달제품이 있으면 수의계약 검토가 가능해?", "expected": ["전기차", "혁신제품", "수의계약"]},
    {"id": "goods_security_camera_sme", "category": "sme_competition", "agency_type": "local_government", "question": "보안용카메라가 중소기업자간 경쟁제품이면 직접생산확인과 종합쇼핑몰 후보를 같이 봐야 해?", "expected": ["보안용카메라", "중소기업", "직접생산"]},
    {"id": "goods_lab_equipment", "category": "goods_route", "agency_type": "local_government", "question": "실험실 장비 구매는 특정 규격을 넣으면 부당제한이 될 수 있어? 구매 절차도 같이 알려줘.", "expected": ["장비", "부당제한", "절차"]},
    {"id": "goods_furniture_direct_production", "category": "sme_competition", "agency_type": "local_government", "question": "사무용 책상과 의자 구매는 중기간 경쟁제품이나 직접생산확인 대상인지 먼저 봐야 해?", "expected": ["책상", "의자", "직접생산"]},
    {"id": "goods_uniform_public_purchase", "category": "public_purchase", "agency_type": "local_government", "question": "근무복이나 단체복 구매에서 중소기업자간 경쟁제품, 직접생산확인, 지역업체 후보를 어떻게 확인해?", "expected": ["근무복", "직접생산", "지역업체"]},

    # 종합쇼핑몰/MAS/우선구매
    {"id": "mas_second_stage_threshold", "category": "shopping_mall", "agency_type": "local_government", "question": "종합쇼핑몰 MAS 2단계 경쟁은 일반물품과 중기간 경쟁제품에서 기준이 다를 수 있어?", "expected": ["MAS", "2단계", "중기간"]},
    {"id": "mas_third_party_order", "category": "shopping_mall", "agency_type": "local_government", "question": "제3자단가계약 물품은 납품요구 방식으로 바로 구매하는 건지 절차를 설명해줘.", "expected": ["제3자단가", "납품요구", "절차"]},
    {"id": "innovation_market_route", "category": "innovation", "agency_type": "local_government", "question": "혁신장터에 있는 제품을 구매할 때 확인해야 할 지정상태와 계약 경로를 알려줘.", "expected": ["혁신장터", "지정", "계약"]},
    {"id": "priority_green_product", "category": "priority_purchase", "agency_type": "local_government", "question": "녹색제품이나 창업기업제품 같은 우선구매 제품은 부산업체 구매전략에 어떻게 붙일 수 있어?", "expected": ["녹색제품", "창업기업", "부산"]},

    # 용역: 과업 다양화
    {"id": "service_security_guard", "category": "service", "agency_type": "local_government", "question": "청사 경비용역을 부산업체 중심으로 검토하려면 지역제한, 평가항목, 면허를 어떻게 봐야 해?", "expected": ["경비용역", "지역제한", "면허"]},
    {"id": "service_waste_treatment", "category": "service", "agency_type": "local_government", "question": "폐기물 처리 용역은 지역업체 활용과 허가업종 제한을 어떻게 조심해야 해?", "expected": ["폐기물", "용역", "허가"]},
    {"id": "service_design_print", "category": "service", "agency_type": "local_government", "question": "홍보물 디자인과 인쇄가 같이 있는 사업은 용역과 물품 중 어떻게 판단하고 발주해야 해?", "expected": ["디자인", "인쇄", "용역"]},
    {"id": "service_video_content", "category": "service", "agency_type": "local_government", "question": "영상 제작 용역에서 부산업체 참여를 평가항목으로 넣고 싶으면 어떤 리스크가 있어?", "expected": ["영상", "부산업체", "평가"]},
    {"id": "service_translation", "category": "service", "agency_type": "local_government", "question": "번역 용역은 수의계약이나 2인 견적을 검토할 때 어떤 확인사항이 필요해?", "expected": ["번역", "용역", "견적"]},
    {"id": "service_food_catering", "category": "service", "agency_type": "local_government", "question": "행사 급식 또는 케이터링 용역은 지역업체 제한과 위생 인허가를 어떻게 확인해야 해?", "expected": ["급식", "용역", "인허가"]},
    {"id": "service_cloud_subscription", "category": "service_goods_boundary", "agency_type": "local_government", "question": "클라우드 서비스 구독은 물품, 용역, 소프트웨어 구매 중 어디에 가깝고 계약 절차는 어떻게 잡아야 해?", "expected": ["클라우드", "용역", "소프트웨어"]},

    # 공사: 공종 다양화
    {"id": "construction_fire_facility", "category": "construction", "agency_type": "local_government", "question": "소방시설공사는 전문공사 기준과 지역제한 기준을 어떻게 확인해야 해?", "expected": ["소방시설공사", "전문공사", "지역제한"]},
    {"id": "construction_landscape", "category": "construction", "agency_type": "local_government", "question": "조경공사를 부산업체 중심으로 발주하려면 지역제한과 면허요건을 어떻게 설계해야 해?", "expected": ["조경공사", "부산", "면허"]},
    {"id": "construction_architecture_repair", "category": "construction", "agency_type": "local_government", "question": "청사 보수공사는 종합공사인지 전문공사인지에 따라 수의계약 한도가 달라질 수 있어?", "expected": ["보수공사", "종합공사", "전문공사"]},
    {"id": "construction_road_pavement", "category": "construction", "agency_type": "local_government", "question": "도로 포장공사에서 지역업체 참여도를 높이려면 지역제한, 공동도급, 적격심사를 어떻게 연결해?", "expected": ["포장공사", "공동도급", "적격심사"]},
    {"id": "construction_telecom_materials", "category": "construction_goods_boundary", "agency_type": "local_government", "question": "정보통신공사에 들어가는 관급자재는 공사용자재 직접구매와 물품구매를 같이 봐야 해?", "expected": ["정보통신공사", "관급자재", "직접구매"]},
    {"id": "construction_demolition_waste", "category": "construction_service_boundary", "agency_type": "local_government", "question": "철거공사와 폐기물처리 용역을 묶어 발주하면 분리발주나 부당제한 문제가 생길 수 있어?", "expected": ["철거공사", "폐기물", "분리발주"]},

    # 기관유형/법령 충돌/해석
    {"id": "agency_national_goods_regional_conflict", "category": "agency_conflict", "agency_type": "national_agency", "question": "국가기관이 컴퓨터 구매에서 부산 지역업체를 우대하고 싶을 때 지방계약 지역제한 기준을 그대로 쓰면 안 되지?", "expected": ["국가기관", "지방계약", "지역"]},
    {"id": "agency_public_corp_mas", "category": "agency_conflict", "agency_type": "public_corporation", "question": "공기업이 종합쇼핑몰로 물품을 구매할 때 공기업 계약사무규칙과 조달청 쇼핑몰 규정을 어떻게 같이 봐야 해?", "expected": ["공기업", "종합쇼핑몰", "규정"]},
    {"id": "agency_school_private", "category": "agency_conflict", "agency_type": "national_agency", "question": "사립대학교가 국고보조금으로 용역을 발주하면 국가계약법 절차를 따라야 하는지 어떻게 확인해?", "expected": ["사립대학교", "국고보조금", "국가계약"]},

    # 절차/개념/감사
    {"id": "procedure_goods_full_flow", "category": "procedure", "agency_type": "local_government", "question": "물품을 구매하려고 한다. 구매 절차를 처음부터 끝까지 안내해줘.", "expected": ["물품", "계약 절차", "source map"]},
    {"id": "procedure_service_full_flow", "category": "procedure", "agency_type": "local_government", "question": "용역계약 절차를 기본계획부터 대금지급까지 흐름으로 설명해줘.", "expected": ["용역", "기본계획", "대금지급"]},
    {"id": "procedure_construction_full_flow", "category": "procedure", "agency_type": "local_government", "question": "공사계약 절차를 발주 전 사전절차부터 준공검사까지 알려줘.", "expected": ["공사", "사전절차", "준공검사"]},
    {"id": "audit_split_purchase", "category": "audit", "agency_type": "local_government", "question": "같은 부서에서 컴퓨터를 여러 번 나눠 사면 쪼개기 수의계약으로 볼 수 있어? 감사 대응 자료는 뭐가 필요해?", "expected": ["컴퓨터", "쪼개기", "감사"]},
    {"id": "audit_specific_brand", "category": "audit", "agency_type": "local_government", "question": "특정 브랜드 노트북만 규격서에 넣으면 부당제한이 될 수 있어? 동등 이상 표현은 어떻게 써야 해?", "expected": ["특정 브랜드", "부당제한", "동등"]},
]

QUESTION_BANK: list[dict[str, Any]] = []
_seen_ids: set[str] = set()
for _case in [*BASE_QUESTIONS, *EXTRA_QUESTIONS]:
    case = dict(_case)
    case.setdefault("category", case["id"].split("_", 1)[0])
    if case["id"] not in _seen_ids:
        QUESTION_BANK.append(case)
        _seen_ids.add(case["id"])


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


def _compact_for_expected_match(text: str) -> str:
    return "".join(str(text or "").split()).lower()


EXPECTED_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "부당제한": ("부당제한", "부당한제한", "과도한제한"),
    "분리발주": ("분리발주", "분리발주", "분리할경우"),
    "행사용역": ("행사용역", "행사용역", "행사운영용역"),
    "부산업체": ("부산업체", "부산업체", "부산지역업체"),
    "구매실적": ("구매실적", "구매실적", "총실적", "실적"),
    "공사기간": ("공사기간", "공사기간", "공사중지기간"),
    "중소기업자간": ("중소기업자간", "중소기업자간", "중기간"),
    "보안용카메라": ("보안용카메라", "보안용카메라", "cctv카메라"),
    "대가": ("대가", "대금지급", "대금"),
}


def _expected_term_present(term: str, answer: str) -> bool:
    compact_answer = _compact_for_expected_match(answer)
    aliases = EXPECTED_TERM_ALIASES.get(term, (term,))
    return any(_compact_for_expected_match(alias) in compact_answer for alias in aliases)


def assess(record: dict[str, Any]) -> dict[str, Any]:
    case = record["case"]
    response = record.get("response") or {}
    answer = _answer_text(response)
    expected = case.get("expected") or []
    missing_expected = [term for term in expected if not _expected_term_present(term, answer)]
    forbidden = [marker for marker in FORBIDDEN_MARKERS if marker in answer]
    candidate_counts = response.get("candidate_counts_by_type") or {}
    candidate_total = sum(v for v in candidate_counts.values() if isinstance(v, int)) if isinstance(candidate_counts, dict) else 0
    warnings: list[str] = []
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
    if response.get("external_mcp_fallback_count", 0):
        warnings.append("external_mcp_fallback_used")
    if case.get("category") in {"goods_route", "goods_cert", "shopping_mall", "innovation", "sme_competition"}:
        if "구매" not in answer and "계약" not in answer:
            warnings.append("purchase_route_language_missing")
    if case.get("category") in {"procedure"}:
        if "법령/source map으로 따로 검증할 지점" not in answer and "source map" not in answer:
            warnings.append("procedure_source_map_boundary_missing")
    if "company" in case["id"] and candidate_total == 0 and "업체" not in answer:
        warnings.append("company_candidate_not_visible")

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
    by_category: dict[str, int] = {}
    slow_cases = []
    for r in records:
        case = r["case"]
        by_case[case["id"]] = by_case.get(case["id"], 0) + 1
        category = case.get("category") or "unknown"
        by_category[category] = by_category.get(category, 0) + 1
        if (r.get("elapsed_ms_client") or 0) > 30000:
            slow_cases.append({"id": case["id"], "elapsed_ms": r.get("elapsed_ms_client"), "question": case["question"]})
    return {
        "record_count": len(records),
        "question_bank_count": len(QUESTION_BANK),
        "unique_case_count": len(by_case),
        "category_count": by_category,
        "ok_count": sum(1 for r in records if r.get("ok")),
        "warning_count": len(warnings),
        "avg_latency_ms": int(statistics.mean(latencies)) if latencies else 0,
        "p50_latency_ms": int(statistics.median(latencies)) if latencies else 0,
        "max_latency_ms": max(latencies) if latencies else 0,
        "slow_cases": slow_cases[-20:],
        "warning_samples": warnings[-40:],
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
        f"# 서버 4시간 전체 분야 QA 리포트 ({run_id})",
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
        "## 사용자 품질 판정 가이드",
        "",
        "각 질문 상세의 `사용자 판정` 칸에 직접 적어 주세요.",
        "",
        "- 점수: `1~5`",
        "- 판정: `좋음 / 보통 / 나쁨`",
        "- 문제유형: `의도오판 / 근거누락 / 법령오류 / 업체후보문제 / 너무느림 / 답변장황 / 질문미응답 / 기타`",
        "- 개선메모: 어떤 문장이나 방향이 문제였는지 짧게 적으면 됩니다.",
        "",
        "## 요약",
        "",
        "| # | 분야 | 질문ID | HTTP | 응답시간 | Tier | 모델 | 근거카드 | 커버리지 | 도구호출 | 업체후보 | 경고 | 사용자점수 | 판정 |",
        "|---:|---|---|---:|---:|---:|---|---:|---|---:|---:|---|---|---|",
    ]
    for idx, record in enumerate(records, start=1):
        response = record.get("response") or {}
        assessment = record.get("assessment") or {}
        lines.append(
            "| {idx} | {category} | `{case_id}` | {status} | {elapsed}ms | {tier} | {model} | {cards} | {coverage} | {tools} | {candidates} | {warnings} |  |  |".format(
                idx=idx,
                category=record["case"].get("category", ""),
                case_id=record["case"]["id"],
                status=record.get("status_code"),
                elapsed=record.get("elapsed_ms_client"),
                tier=response.get("tier_resolved", ""),
                model=response.get("model_selected", ""),
                cards=response.get("evidence_card_count", ""),
                coverage=response.get("evidence_coverage_status", ""),
                tools=response.get("tool_call_count", ""),
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
            f"**분야**: `{record['case'].get('category', '')}`",
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
            "### 사용자 판정",
            "",
            "| 항목 | 입력 |",
            "|---|---|",
            "| 점수(1~5) |  |",
            "| 판정(좋음/보통/나쁨) |  |",
            "| 문제유형 |  |",
            "| 개선메모 |  |",
            "",
            "### 시스템 메타",
            "",
            f"- coverage: `{response.get('evidence_coverage_status', '')}` score=`{response.get('evidence_coverage_score', '')}` missing_topics=`{response.get('missing_evidence_topics', '') or response.get('evidence_coverage_missing_topics', '')}`",
            f"- context: raw=`{response.get('mcp_context_raw_chars', '')}`, card=`{response.get('mcp_context_card_chars', '')}`, llm=`{response.get('mcp_context_llm_chars', '')}`, savings=`{response.get('mcp_context_char_savings_pct', '')}`",
            f"- tool response context: raw=`{response.get('tool_response_context_raw_chars', '')}`, llm=`{response.get('tool_response_context_llm_chars', '')}`, savings=`{response.get('tool_response_context_char_savings_pct', '')}`",
            f"- llm payload: core=`{response.get('llm_payload_core_prompt_chars', '')}`, dynamic=`{response.get('llm_payload_dynamic_context_chars', '')}`, rag=`{response.get('llm_payload_rag_context_chars', '')}`, mcp=`{response.get('llm_payload_mcp_context_chars', '')}`, initial=`{response.get('llm_payload_initial_contents_chars', '')}`, max=`{response.get('llm_payload_max_contents_chars', '')}`, tools_available=`{response.get('llm_payload_tool_count_available', '')}`, model_timeouts=`{response.get('llm_payload_model_timeout_count', '')}`",
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
    parser.add_argument("--duration-minutes", type=float, default=240)
    parser.add_argument("--pause-seconds", type=float, default=12)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--max-calls", type=int, default=0, help="0 means run until duration expires")
    parser.add_argument("--seed", type=int, default=20260509)
    args = parser.parse_args()

    run_id = now_stamp()
    json_path = OUT_DIR / f"server_qa_4h_full_{run_id}.json"
    md_path = OUT_DIR / f"server_qa_4h_full_{run_id}.md"
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
