from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


DEFAULT_API_URL = "http://49.50.133.160:8001/chat"
OUT_DIR = Path("artifacts/qa/server_3h")
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
        "expected": ["2억", "수의계약", "입찰"],
    },
    {
        "id": "led_80m_local_strategy",
        "agency_type": "local_government",
        "question": "8천만원으로 LED 조명을 사려고 한다. 부산업체를 활용할 수 있는 방법과 가능한 업체 후보를 같이 알려줘.",
        "expected": ["LED", "부산", "종합쇼핑몰", "업체"],
    },
    {
        "id": "led_synonym",
        "agency_type": "local_government",
        "question": "엘이디등 구매할 건데 부산 지역업체 있어? 조달등록이나 인증 여부도 같이 알려줘.",
        "expected": ["LED", "부산", "업체"],
    },
    {
        "id": "cleaning_service_local",
        "agency_type": "local_government",
        "question": "8천만원 청소용역을 부산 지역업체로 계약하려면 어떤 제도를 검토해야 해?",
        "expected": ["청소", "용역", "지역"],
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
        "question": "지역업체 가점제도는 국가계약, 지방계약, 공기업 및 준정부기관에서 어떻게 다르게 봐야 해?",
        "expected": ["지역업체", "가점", "평가"],
    },
    {
        "id": "mas_regional",
        "agency_type": "local_government",
        "question": "종합쇼핑몰 MAS 2단계 경쟁에서 부산업체를 우대하거나 지역업체를 고려할 수 있어?",
        "expected": ["종합쇼핑몰", "MAS", "부산"],
    },
    {
        "id": "sme_tech_complex",
        "agency_type": "local_government",
        "question": "중소기업자간 경쟁제품이면서 기술개발제품이면 2억 물품도 수의계약 가능성이 있어?",
        "expected": ["중소기업", "기술개발제품", "수의계약"],
    },
    {
        "id": "cctv_company",
        "agency_type": "local_government",
        "question": "CCTV 구매할 건데 부산업체 후보를 추천해줘. 조달등록이나 인증 여부도 같이 보여줘.",
        "expected": ["CCTV", "부산", "조달"],
    },
    {
        "id": "excellent_procurement",
        "agency_type": "local_government",
        "question": "우수조달물품이나 제3자단가계약 제품을 활용하면 부산 지역상품 구매에 도움이 될까?",
        "expected": ["우수조달", "제3자", "부산"],
    },
    {
        "id": "audit_risk",
        "agency_type": "local_government",
        "question": "부산업체를 활용하려고 할 때 감사에서 문제되지 않게 어떤 점을 조심해야 해?",
        "expected": ["부산", "감사", "확인"],
    },
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
            "GEMINI_API_KEY",
            "function_call",
            "Internal Server Error",
        ]
        if marker in answer
    ]
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
    return {
        "missing_expected": missing_expected,
        "forbidden_markers": forbidden,
        "candidate_total": candidate_total,
        "warnings": warnings,
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [r.get("elapsed_ms_client") or 0 for r in records if r.get("ok")]
    warnings = [w for r in records for w in (r.get("assessment") or {}).get("warnings", [])]
    return {
        "record_count": len(records),
        "ok_count": sum(1 for r in records if r.get("ok")),
        "warning_count": len(warnings),
        "avg_latency_ms": int(statistics.mean(latencies)) if latencies else 0,
        "p50_latency_ms": int(statistics.median(latencies)) if latencies else 0,
        "max_latency_ms": max(latencies) if latencies else 0,
        "warning_samples": warnings[:20],
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
        f"# 서버 3시간 QA 리포트 ({run_id})",
        "",
        f"- API: `{api_url}`",
        f"- 완료 여부: `{finished}`",
        f"- 호출 수: `{len(records)}`",
        f"- 평균 응답시간: `{summary['avg_latency_ms']}ms`",
        f"- P50 응답시간: `{summary['p50_latency_ms']}ms`",
        f"- 최대 응답시간: `{summary['max_latency_ms']}ms`",
        "",
        "## 요약",
        "",
        "| # | Cycle | 질문ID | HTTP | 응답시간 | Tier | 모델 | 근거카드 | 실무카드 | 내부DB | 외부MCP | 업체후보 | 경고 |",
        "|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for idx, record in enumerate(records, start=1):
        response = record.get("response") or {}
        assessment = record.get("assessment") or {}
        lines.append(
            "| {idx} | {cycle} | `{case_id}` | {status} | {elapsed}ms | {tier} | {model} | {cards} | {manual_cards} | {internal} | {external} | {candidates} | {warnings} |".format(
                idx=idx,
                cycle=record.get("cycle", ""),
                case_id=record["case"]["id"],
                status=record.get("status_code"),
                elapsed=record.get("elapsed_ms_client"),
                tier=response.get("tier_resolved", ""),
                model=response.get("model_selected", ""),
                cards=response.get("evidence_card_count", ""),
                manual_cards=response.get("practice_manual_card_count", ""),
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
            f"### {idx}. {record['case']['id']} / cycle {record.get('cycle')}",
            "",
            f"**질문**: {record['case']['question']}",
            "",
            f"**응답시간**: `{record.get('elapsed_ms_client')}ms`",
            "",
            f"**메타**: tier=`{response.get('tier_resolved', '')}`, model=`{response.get('model_selected', '')}`, evidence_cards=`{response.get('evidence_card_count', '')}`, practice_cards=`{response.get('practice_manual_card_count', '')}`, internal_db=`{response.get('internal_db_hit_count', '')}`, external_mcp=`{response.get('external_mcp_fallback_count', '')}`, tool_calls=`{response.get('tool_call_count', '')}`",
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--duration-minutes", type=float, default=180)
    parser.add_argument("--pause-seconds", type=float, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means run until duration expires")
    args = parser.parse_args()

    run_id = now_stamp()
    json_path = OUT_DIR / f"server_qa_3h_{run_id}.json"
    md_path = OUT_DIR / f"server_qa_3h_{run_id}.md"
    progress_path = OUT_DIR / "latest_progress.json"
    deadline = time.perf_counter() + args.duration_minutes * 60
    records: list[dict[str, Any]] = []
    cycle = 0

    while time.perf_counter() < deadline:
        cycle += 1
        if args.max_cycles and cycle > args.max_cycles:
            break
        for case in QUESTIONS:
            if time.perf_counter() >= deadline:
                break
            record = post_question(args.api_url, case, args.timeout_seconds)
            record["cycle"] = cycle
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
