from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


API_URL = "http://49.50.133.160:8001/chat"
OUT_DIR = Path("artifacts/qa/server_30min")
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUESTIONS = [
    {
        "id": "regional_limit_compare",
        "agency_type": "local_government",
        "question": "지역제한경쟁입찰 기준금액을 알려줘. 종합공사는 국가, 공기업 및 준정부기관, 지방자치단체가 각각 얼마야?",
        "expected": ["88억", "150억", "지방계약법 시행규칙", "공기업"],
    },
    {
        "id": "direct_contract_200m_goods",
        "agency_type": "local_government",
        "question": "2억 물품을 수의계약으로 살 수 있어?",
        "expected": ["2억", "수의계약", "불가", "입찰"],
    },
    {
        "id": "led_80m_local_strategy",
        "agency_type": "local_government",
        "question": "8천만원으로 LED 조명을 사려고 한다. 부산업체를 활용할 수 있는 방법과 가능한 업체 후보를 같이 알려줘.",
        "expected": ["LED", "부산", "종합쇼핑몰", "기술개발", "업체"],
    },
    {
        "id": "led_synonym",
        "agency_type": "local_government",
        "question": "엘이디등 구매할 건데 부산 지역업체 있어?",
        "expected": ["LED", "부산", "업체"],
    },
    {
        "id": "cleaning_service_local",
        "agency_type": "local_government",
        "question": "8천만원 청소용역을 부산 지역업체로 계약하려면 어떤 제도를 검토해야 해?",
        "expected": ["청소용역", "지역제한", "수의계약", "평가"],
    },
    {
        "id": "construction_joint",
        "agency_type": "local_government",
        "question": "2억원 전기공사에서 부산 지역업체 수주를 늘리려면 지역제한이나 지역의무공동도급을 쓸 수 있어?",
        "expected": ["전기공사", "지역제한", "공동", "부산"],
    },
    {
        "id": "regional_points",
        "agency_type": "local_government",
        "question": "지역업체 가점제도는 어떤 경우에 검토해야 해?",
        "expected": ["지역업체", "가점", "평가", "낙찰"],
    },
    {
        "id": "mas_regional",
        "agency_type": "local_government",
        "question": "종합쇼핑몰 MAS 2단계 경쟁에서 부산업체를 우대하거나 지역업체를 고려할 수 있어?",
        "expected": ["종합쇼핑몰", "MAS", "2단계", "부산"],
    },
    {
        "id": "sme_tech_complex",
        "agency_type": "local_government",
        "question": "중소기업자간 경쟁제품이면서 기술개발제품이면 2억 물품도 수의계약 가능성이 있어?",
        "expected": ["중소기업", "기술개발제품", "수의계약", "직접생산"],
    },
    {
        "id": "cctv_company",
        "agency_type": "local_government",
        "question": "CCTV 구매할 건데 부산업체 후보를 추천해줘. 조달등록이나 인증 여부도 같이 보여줘.",
        "expected": ["CCTV", "부산", "조달", "인증"],
    },
]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


RUN_ID = now_stamp()
JSON_PATH = OUT_DIR / f"server_qa_{RUN_ID}.json"
MD_PATH = OUT_DIR / f"server_qa_{RUN_ID}.md"
PROGRESS_PATH = OUT_DIR / "latest_progress.json"


def post_question(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    payload = {
        "message": case["question"],
        "agency_type": case.get("agency_type") or "local_government",
        "history": [],
    }
    try:
        response = requests.post(API_URL, json=payload, timeout=150)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        text = response.text
        try:
            data = response.json()
        except Exception:
            data = {"raw_response": text}
        return {
            "case": case,
            "ok": response.ok,
            "status_code": response.status_code,
            "elapsed_ms_client": elapsed_ms,
            "response": data,
            "error": None,
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
        }


def assess(record: dict[str, Any]) -> dict[str, Any]:
    case = record["case"]
    response = record.get("response") or {}
    answer = str(response.get("answer") or response.get("raw_response") or "")
    expected = case.get("expected") or []
    missing_expected = [term for term in expected if term not in answer]
    forbidden = [
        marker for marker in [
            "Traceback",
            "MCP_FAILED",
            "No module named",
            "API key",
            "GEMINI_API_KEY",
            "function_call",
        ]
        if marker in answer
    ]
    candidate_counts = response.get("candidate_counts_by_type") or {}
    candidate_total = 0
    if isinstance(candidate_counts, dict):
        candidate_total = sum(v for v in candidate_counts.values() if isinstance(v, int))
    expects_company = case["id"] in {"led_80m_local_strategy", "led_synonym", "cctv_company"}
    speed = record.get("elapsed_ms_client") or 0
    warnings = []
    if missing_expected:
        warnings.append(f"expected_terms_missing={missing_expected}")
    if forbidden:
        warnings.append(f"forbidden_markers={forbidden}")
    if speed > 60000:
        warnings.append("very_slow_over_60s")
    elif speed > 30000:
        warnings.append("slow_over_30s")
    if expects_company and candidate_total == 0 and "업체" not in answer:
        warnings.append("company_candidate_not_visible")
    if not record.get("ok"):
        warnings.append("http_or_exception_failure")
    return {
        "missing_expected": missing_expected,
        "forbidden_markers": forbidden,
        "candidate_total": candidate_total,
        "warnings": warnings,
    }


def write_outputs(records: list[dict[str, Any]], finished: bool = False) -> None:
    payload = {
        "run_id": RUN_ID,
        "api_url": API_URL,
        "started_at": RUN_ID,
        "finished": finished,
        "record_count": len(records),
        "records": records,
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    PROGRESS_PATH.write_text(
        json.dumps(
            {
                "run_id": RUN_ID,
                "finished": finished,
                "record_count": len(records),
                "json_path": str(JSON_PATH),
                "md_path": str(MD_PATH),
                "last_update": datetime.now().isoformat(timespec="seconds"),
                "last_case": records[-1]["case"]["id"] if records else None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        f"# 서버 30분 QA 리포트 ({RUN_ID})",
        "",
        f"- API: `{API_URL}`",
        f"- 완료 여부: `{finished}`",
        f"- 호출 수: `{len(records)}`",
        "",
        "## 요약",
        "",
        "| # | 질문ID | HTTP | 응답시간 | Tier | 근거카드 | 내부DB | 외부MCP | 업체후보 | 경고 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for idx, record in enumerate(records, start=1):
        response = record.get("response") or {}
        assessment = record.get("assessment") or {}
        lines.append(
            "| {idx} | `{case_id}` | {status} | {elapsed}ms | {tier} | {cards} | {internal} | {external} | {candidates} | {warnings} |".format(
                idx=idx,
                case_id=record["case"]["id"],
                status=record.get("status_code"),
                elapsed=record.get("elapsed_ms_client"),
                tier=response.get("tier_resolved", ""),
                cards=response.get("evidence_card_count", ""),
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
        answer = str(response.get("answer") or response.get("raw_response") or "")
        lines.extend([
            f"### {idx}. {record['case']['id']}",
            "",
            f"**질문**: {record['case']['question']}",
            "",
            f"**응답시간**: `{record.get('elapsed_ms_client')}ms`",
            "",
            f"**메타**: tier=`{response.get('tier_resolved', '')}`, model=`{response.get('model_selected', '')}`, evidence_cards=`{response.get('evidence_card_count', '')}`, internal_db=`{response.get('internal_db_hit_count', '')}`, external_mcp=`{response.get('external_mcp_fallback_count', '')}`, tool_calls=`{response.get('tool_call_count', '')}`",
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
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    records: list[dict[str, Any]] = []
    total_cycles = 5
    target_seconds = 30 * 60
    started = time.perf_counter()

    for cycle in range(total_cycles):
        for case in QUESTIONS:
            record = post_question(case)
            record["cycle"] = cycle + 1
            record["assessment"] = assess(record)
            records.append(record)
            write_outputs(records, finished=False)
            time.sleep(2)

        remaining_cycles = total_cycles - cycle - 1
        if remaining_cycles > 0:
            elapsed = time.perf_counter() - started
            remaining_time = max(0, target_seconds - elapsed)
            sleep_for = min(420, remaining_time / remaining_cycles)
            time.sleep(max(5, sleep_for))

    write_outputs(records, finished=True)
    print(JSON_PATH)
    print(MD_PATH)


if __name__ == "__main__":
    main()
