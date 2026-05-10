from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PROGRESS = Path("artifacts/qa/server_toolmix_2h/latest_progress.json")


def _load_run(path: Path | None) -> tuple[Path, dict[str, Any]]:
    if path is None:
        latest = json.loads(DEFAULT_PROGRESS.read_text(encoding="utf-8"))
        path = Path(latest["json_path"])
    return path, json.loads(path.read_text(encoding="utf-8"))


def _reason_bucket(item: dict[str, Any]) -> str:
    reason = str(item.get("selected_reason") or "")
    if reason.startswith("route_plan:"):
        return "route_plan"
    if reason.startswith("dynamic_internal_discovery"):
        return "dynamic_internal_discovery"
    if reason.startswith("regional_support_catalog:"):
        return "regional_support_catalog"
    if reason.startswith("tool_orchestration:"):
        return "tool_orchestration"
    return "topic_cluster_or_legacy"


def _query_of(item: dict[str, Any]) -> str:
    args = item.get("args") or {}
    return str(args.get("query") or args.get("law_name") or args.get("mst") or args.get("rule_id") or "")


def _tool_of(item: dict[str, Any]) -> str:
    return str(item.get("name") or "")


def _response(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("response") or {}


def _metrics(record: dict[str, Any]) -> dict[str, Any]:
    response = _response(record)
    plan = response.get("mandatory_mcp_plan") or []
    warnings = (record.get("assessment") or {}).get("warnings") or []
    return {
        "case_id": (record.get("case") or {}).get("id", ""),
        "category": (record.get("case") or {}).get("category", ""),
        "question": (record.get("case") or {}).get("question", ""),
        "elapsed_ms": record.get("elapsed_ms_client") or 0,
        "warnings": warnings,
        "payload_initial": response.get("llm_payload_initial_contents_chars") or 0,
        "payload_dynamic": response.get("llm_payload_dynamic_context_chars") or 0,
        "payload_mcp": response.get("llm_payload_mcp_context_chars") or 0,
        "mcp_raw": response.get("mcp_context_raw_chars") or 0,
        "mcp_card": response.get("mcp_context_card_chars") or 0,
        "mcp_llm": response.get("mcp_context_llm_chars") or 0,
        "mcp_savings": response.get("mcp_context_char_savings_pct") or 0,
        "mcp_mode": response.get("mcp_context_mode_applied") or "",
        "plan_count": len(plan),
        "timeout_count": response.get("llm_payload_model_timeout_count") or 0,
        "model_errors": response.get("llm_payload_model_error_statuses") or [],
        "tool_call_count": response.get("tool_call_count") or 0,
        "model_reason": response.get("model_decision_reason") or "",
        "route_plan": response.get("route_plan") or {},
        "plan": plan,
    }


def _needs_attention(m: dict[str, Any], payload_threshold: int, slow_threshold_ms: int) -> bool:
    return bool(
        m["elapsed_ms"] >= slow_threshold_ms
        or m["payload_initial"] >= payload_threshold
        or m["mcp_llm"] >= payload_threshold
        or m["timeout_count"]
        or m["warnings"]
    )


def build_report(data: dict[str, Any], source_path: Path, *, payload_threshold: int, slow_threshold_ms: int) -> str:
    records = data.get("records") or []
    metrics = [_metrics(record) for record in records]
    attention = [m for m in metrics if _needs_attention(m, payload_threshold, slow_threshold_ms)]

    bucket_counter: Counter[str] = Counter()
    tool_counter: Counter[str] = Counter()
    query_counter: Counter[str] = Counter()
    by_case_payload: dict[str, list[int]] = defaultdict(list)
    by_case_elapsed: dict[str, list[int]] = defaultdict(list)
    by_case_plan: dict[str, list[int]] = defaultdict(list)

    for m in metrics:
        by_case_payload[m["case_id"]].append(int(m["payload_initial"]))
        by_case_elapsed[m["case_id"]].append(int(m["elapsed_ms"]))
        by_case_plan[m["case_id"]].append(int(m["plan_count"]))
        for item in m["plan"]:
            bucket_counter[_reason_bucket(item)] += 1
            tool_counter[_tool_of(item)] += 1
            query = _query_of(item)
            if query:
                query_counter[query] += 1

    def avg(values: list[int]) -> int:
        return int(sum(values) / len(values)) if values else 0

    worst_cases = sorted(
        by_case_payload,
        key=lambda case_id: (avg(by_case_payload[case_id]), avg(by_case_elapsed[case_id])),
        reverse=True,
    )[:15]

    lines = [
        f"# LLM 루프 Payload 분석 리포트",
        "",
        f"- 생성시각: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- 입력 QA: `{source_path}`",
        f"- run_id: `{data.get('run_id', '')}`",
        f"- records: `{len(records)}`",
        f"- attention records: `{len(attention)}`",
        f"- payload threshold: `{payload_threshold}` chars",
        f"- slow threshold: `{slow_threshold_ms}` ms",
        "",
        "## 핵심 요약",
        "",
        "| 구분 | 값 |",
        "|---|---:|",
        f"| 최대 initial payload chars | {max((m['payload_initial'] for m in metrics), default=0)} |",
        f"| 최대 MCP LLM context chars | {max((m['mcp_llm'] for m in metrics), default=0)} |",
        f"| 최대 MCP raw chars | {max((m['mcp_raw'] for m in metrics), default=0)} |",
        f"| 최대 MCP card chars | {max((m['mcp_card'] for m in metrics), default=0)} |",
        f"| 최대 MCP plan count | {max((m['plan_count'] for m in metrics), default=0)} |",
        f"| 모델 timeout 발생 records | {sum(1 for m in metrics if m['timeout_count'])} |",
        "",
        "## 조회계획 구성",
        "",
        "### selected_reason 계열",
        "",
        "| 계열 | 호출 수 |",
        "|---|---:|",
    ]
    for key, count in bucket_counter.most_common():
        lines.append(f"| {key} | {count} |")

    lines.extend(["", "### 도구별 호출 수", "", "| 도구 | 호출 수 |", "|---|---:|"])
    for key, count in tool_counter.most_common():
        lines.append(f"| {key} | {count} |")

    lines.extend(["", "### 반복 조회 상위 쿼리", "", "| 쿼리 | 반복 수 |", "|---|---:|"])
    for key, count in query_counter.most_common(30):
        lines.append(f"| {key} | {count} |")

    lines.extend(["", "## 케이스별 평균 payload 상위", "", "| 질문ID | 평균 initial | 평균 MCP llm | 평균 plan | 평균 응답시간 |", "|---|---:|---:|---:|---:|"])
    for case_id in worst_cases:
        case_metrics = [m for m in metrics if m["case_id"] == case_id]
        lines.append(
            f"| {case_id} | {avg([m['payload_initial'] for m in case_metrics])} | "
            f"{avg([m['mcp_llm'] for m in case_metrics])} | "
            f"{avg(by_case_plan[case_id])} | {avg(by_case_elapsed[case_id])} |"
        )

    lines.extend(["", "## 주의 필요 상세", ""])
    for idx, m in enumerate(sorted(attention, key=lambda value: (value["payload_initial"], value["elapsed_ms"]), reverse=True), start=1):
        route_plan = m["route_plan"] or {}
        topics = route_plan.get("evidence_topics") or []
        retrieval = route_plan.get("retrieval_needs") or []
        lines.extend([
            f"### {idx}. {m['case_id']}",
            "",
            f"- category: `{m['category']}`",
            f"- elapsed_ms: `{m['elapsed_ms']}`",
            f"- warning: `{', '.join(m['warnings']) or '없음'}`",
            f"- model_reason: `{m['model_reason']}`",
            f"- context mode: `{m['mcp_mode']}`",
            f"- payload: initial=`{m['payload_initial']}`, dynamic=`{m['payload_dynamic']}`, mcp=`{m['payload_mcp']}`",
            f"- mcp context: raw=`{m['mcp_raw']}`, card=`{m['mcp_card']}`, llm=`{m['mcp_llm']}`, savings=`{m['mcp_savings']}`",
            f"- plan_count: `{m['plan_count']}`, tool_calls=`{m['tool_call_count']}`, timeouts=`{m['timeout_count']}`, errors=`{m['model_errors']}`",
            f"- route retrieval: `{retrieval}`",
            f"- route topics: `{topics}`",
            "",
            f"**질문**: {m['question']}",
            "",
            "| # | 계열 | 도구 | 쿼리 |",
            "|---:|---|---|---|",
        ])
        for plan_idx, item in enumerate(m["plan"][:40], start=1):
            lines.append(f"| {plan_idx} | {_reason_bucket(item)} | {_tool_of(item)} | {_query_of(item)} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--payload-threshold", type=int, default=20000)
    parser.add_argument("--slow-threshold-ms", type=int, default=5000)
    args = parser.parse_args()

    source_path, data = _load_run(args.json_path)
    output = args.output or source_path.with_name(source_path.stem + "_payload_analysis.md")
    output.write_text(
        build_report(
            data,
            source_path,
            payload_threshold=args.payload_threshold,
            slow_threshold_ms=args.slow_threshold_ms,
        ),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
