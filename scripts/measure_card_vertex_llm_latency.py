"""Measure server-card, Vertex Search, and LLM generation latency separately.

This script is intentionally outside the production request path. It builds the
same kind of internal evidence cards the chatbot server uses, queries a Vertex AI
Search data store explicitly, then sends both evidence sets to Gemini for a
single writer-only answer. That gives separate wall-clock timings for:

1. chatbot/server evidence card preparation,
2. Vertex Search retrieval,
3. final LLM generation from the combined evidence.

If --run-grounded-combined is set, it also measures the actual Gemini
VertexAISearch grounding call as one combined "search + generation" latency.
Google's grounded generate_content response does not expose retrieval latency as
a separate field, so explicit Vertex Search is the split-latency measurement.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from google import genai
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.genai import types


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
DEFAULT_MANIFESTS = (
    PROJECT_ROOT / "artifacts/vertex_grounding/vertex_search_full_db_no_company_manifest.json",
    PROJECT_ROOT / "artifacts/vertex_grounding/vertex_search_full_db_manifest.json",
    PROJECT_ROOT / "artifacts/vertex_grounding/vertex_search_datastore_manifest.json",
)
DEFAULT_QUESTIONS = (
    "전기공사 1억5천만원을 부산 지역제한으로 발주할 수 있는지, 법령 근거와 실무 리스크를 함께 검토해줘",
    "소방시설공사 2억2천만원에서 지역제한과 전문공사 기준을 같이 검토해줘",
    "정보통신공사 1억8천만원이면 지역제한, 면허요건, 분리발주 필요성을 종합 검토해줘",
    "예산 6천만원으로 컴퓨터 구매하려고 하는데 계약방법, 내부 근거, 부산업체 후보를 종합해서 답변해줘",
)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _default_datastore() -> str:
    env_value = os.getenv("VERTEX_AI_SEARCH_DATASTORE", "").strip()
    if env_value:
        return env_value
    for path in DEFAULT_MANIFESTS:
        if path.exists():
            data = _load_json(path)
            value = data.get("data_store") or data.get("datastore")
            if value:
                return str(value)
    return ""


def _project_from_key_file(key_file: str) -> str:
    try:
        data = _load_json(Path(key_file))
        return str(data.get("project_id") or "")
    except Exception:
        return ""


def _datastore_parts(datastore: str) -> tuple[str, str, str]:
    parts = datastore.split("/")
    try:
        project = parts[parts.index("projects") + 1]
        location = parts[parts.index("locations") + 1]
        data_store_id = parts[parts.index("dataStores") + 1]
        return project, location, data_store_id
    except Exception as exc:
        raise ValueError(f"Invalid Vertex AI Search datastore path: {datastore}") from exc


def _percentile(values: list[int], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    k = (len(xs) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return float(xs[f])
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 1)


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    def vals(key: str) -> list[int]:
        return [
            int(r[key])
            for r in records
            if isinstance(r.get(key), (int, float)) and r.get(key) is not None
        ]

    summary: dict[str, Any] = {"count": len(records)}
    for key in (
        "server_card_generation_elapsed_ms",
        "mcp_preflight_elapsed_ms",
        "vertex_search_elapsed_ms",
        "llm_generation_elapsed_ms",
        "total_split_pipeline_elapsed_ms",
        "grounded_combined_elapsed_ms",
    ):
        xs = vals(key)
        summary[key] = {
            "avg": round(statistics.mean(xs), 1) if xs else None,
            "p50": _percentile(xs, 50),
            "p90": _percentile(xs, 90),
            "max": max(xs) if xs else None,
        }
    summary["errors"] = sum(1 for r in records if r.get("error"))
    return summary


def build_server_cards(question: str, agency_type: str, tier: int, max_cards: int) -> dict[str, Any]:
    sys.path.insert(0, str(APP_DIR))
    started = time.perf_counter()

    import gemini_engine as ge  # noqa: WPS433
    from policies.model_routing_policy import generate_mandatory_mcp_plan  # noqa: WPS433
    from policies.practice_manual_cards import (  # noqa: WPS433
        format_practice_manual_cards_for_llm,
        match_practice_manual_cards,
    )
    from policies.pps_qa_cards import format_pps_qa_cards_for_llm, match_pps_qa_cards  # noqa: WPS433

    plan = generate_mandatory_mcp_plan(question, tier, agency_type=agency_type)

    mcp_context = ""
    executed: list[str] = []
    missing: list[str] = []
    cache_stats: dict[str, Any] = {}
    preflight_elapsed_ms = 0
    if plan:
        preflight_start = time.perf_counter()
        mcp_context, _, executed, missing, cache_stats = ge._execute_tier_2_mandatory_mcp(  # noqa: SLF001
            question,
            plan,
            None,
        )
        preflight_elapsed_ms = int((time.perf_counter() - preflight_start) * 1000)

    practice_start = time.perf_counter()
    practice_cards = match_practice_manual_cards(
        question,
        agency_type=agency_type,
        max_cards=max_cards,
    )
    practice_context = format_practice_manual_cards_for_llm(practice_cards)
    practice_elapsed_ms = int((time.perf_counter() - practice_start) * 1000)

    pps_start = time.perf_counter()
    pps_cards = match_pps_qa_cards(question, max_cards=min(3, max_cards))
    pps_context = format_pps_qa_cards_for_llm(pps_cards)
    pps_elapsed_ms = int((time.perf_counter() - pps_start) * 1000)

    server_context = "\n\n".join(
        part for part in (mcp_context, practice_context, pps_context) if part
    ).strip()
    return {
        "server_context": server_context,
        "server_card_generation_elapsed_ms": int((time.perf_counter() - started) * 1000),
        "mcp_preflight_elapsed_ms": preflight_elapsed_ms,
        "practice_card_elapsed_ms": practice_elapsed_ms,
        "pps_qa_card_elapsed_ms": pps_elapsed_ms,
        "mandatory_mcp_plan_count": len(plan),
        "mandatory_mcp_executed_count": len(executed),
        "mandatory_mcp_missing_count": len(missing),
        "mcp_context_chars": len(mcp_context),
        "practice_context_chars": len(practice_context),
        "pps_qa_context_chars": len(pps_context),
        "server_context_chars": len(server_context),
        "mcp_context_mode_applied": cache_stats.get("mcp_context_mode_applied"),
        "mcp_context_card_chars": cache_stats.get("mcp_context_card_chars"),
        "mcp_context_raw_chars": cache_stats.get("mcp_context_raw_chars"),
    }


def _credentials(key_file: str):
    creds = service_account.Credentials.from_service_account_file(
        key_file,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    refresh_start = time.perf_counter()
    creds.refresh(Request())
    return creds, int((time.perf_counter() - refresh_start) * 1000)


def vertex_search(question: str, datastore: str, key_file: str, page_size: int) -> dict[str, Any]:
    creds, token_elapsed_ms = _credentials(key_file)
    url = f"https://discoveryengine.googleapis.com/v1/{datastore}/servingConfigs/default_search:search"
    rich_body = {
        "query": question,
        "pageSize": page_size,
        "contentSearchSpec": {
            "snippetSpec": {"returnSnippet": True},
            "extractiveContentSpec": {
                "maxExtractiveAnswerCount": 1,
                "maxExtractiveSegmentCount": 1,
            },
        },
    }
    started = time.perf_counter()
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        },
        json=rich_body,
        timeout=45,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    retry_without_enterprise_features = False
    data: dict[str, Any] = {}
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text[:1000]}

    # Standard edition data stores can reject extractive/snippet features. Fall
    # back to a plain search so we still get a real Vertex retrieval latency.
    if resp.status_code == 400 and "Enterprise edition" in json.dumps(data, ensure_ascii=False):
        retry_without_enterprise_features = True
        basic_body = {"query": question, "pageSize": page_size}
        retry_started = time.perf_counter()
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json",
            },
            json=basic_body,
            timeout=45,
        )
        elapsed_ms += int((time.perf_counter() - retry_started) * 1000)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:1000]}

    results = []
    for item in data.get("results", []) or []:
        doc = item.get("document") or {}
        derived = doc.get("derivedStructData") or {}
        snippets = []
        for snippet in derived.get("snippets", []) or []:
            text = snippet.get("snippet") if isinstance(snippet, dict) else str(snippet)
            if text:
                snippets.append(text)
        extracts = []
        for extract in derived.get("extractive_answers", []) or []:
            text = extract.get("content") if isinstance(extract, dict) else str(extract)
            if text:
                extracts.append(text)
        for extract in derived.get("extractive_segments", []) or []:
            text = extract.get("content") if isinstance(extract, dict) else str(extract)
            if text:
                extracts.append(text)
        results.append(
            {
                "id": doc.get("id"),
                "title": derived.get("title") or doc.get("id"),
                "link": derived.get("link"),
                "snippets": snippets[:2],
                "extracts": extracts[:2],
            }
        )

    context_lines = []
    for idx, result in enumerate(results, 1):
        text = "\n".join((result.get("extracts") or []) + (result.get("snippets") or []))
        context_lines.append(
            f"[Vertex {idx}] {result.get('title')}\n"
            f"{text[:1200] if text else '(본문 발췌 없음, 문서 제목/랭킹만 확인)'}"
        )
    return {
        "vertex_search_status_code": resp.status_code,
        "vertex_token_refresh_elapsed_ms": token_elapsed_ms,
        "vertex_search_elapsed_ms": elapsed_ms,
        "vertex_search_retried_without_enterprise_features": retry_without_enterprise_features,
        "vertex_search_result_count": len(results),
        "vertex_context": "\n\n".join(context_lines),
        "vertex_context_chars": len("\n\n".join(context_lines)),
        "vertex_results": results,
        "vertex_error": data.get("error"),
    }


def llm_generate(
    *,
    question: str,
    server_context: str,
    vertex_context: str,
    project: str,
    location: str,
    model: str,
    thinking_budget: int,
    timeout_ms: int,
) -> dict[str, Any]:
    client = genai.Client(
        vertexai=True,
        project=project,
        location=location,
        http_options=types.HttpOptions(api_version="v1", timeout=timeout_ms),
    )
    prompt = f"""
당신은 공공계약 담당자를 돕는 실무형 답변 작성자입니다.

[작성 원칙]
- 내부도구 호출 없이 아래 제공자료만 바탕으로 답변하세요.
- [챗봇 서버 제공 근거카드]와 [Vertex Search 검색 결과]가 충돌하면 더 구체적인 법령·행정규칙 근거를 우선하세요.
- 부족한 부분은 "추가 확인 필요"라고 쓰세요.
- 사용자에게 내부 시스템명, source map, 함수명, 데이터스토어명은 노출하지 마세요.

[사용자 질문]
{question}

[챗봇 서버 제공 근거카드]
{server_context[:18000]}

[Vertex Search 검색 결과]
{vertex_context[:9000]}
""".strip()
    started = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        ),
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    usage = getattr(response, "usage_metadata", None)
    return {
        "llm_generation_elapsed_ms": elapsed_ms,
        "llm_prompt_chars": len(prompt),
        "llm_answer_chars": len(response.text or ""),
        "llm_answer_head": (response.text or "")[:500],
        "llm_usage_metadata": _to_jsonable(usage),
        "llm_internal_label_leak": any(
            token in (response.text or "")
            for token in ("source map", "source_map", "get_company_detail", "dataStore", "datastore")
        ),
    }


def grounded_combined_generate(
    *,
    question: str,
    server_context: str,
    datastore: str,
    project: str,
    location: str,
    model: str,
    max_results: int,
    thinking_budget: int,
    timeout_ms: int,
) -> dict[str, Any]:
    client = genai.Client(
        vertexai=True,
        project=project,
        location=location,
        http_options=types.HttpOptions(api_version="v1", timeout=timeout_ms),
    )
    tool = types.Tool(
        retrieval=types.Retrieval(
            vertex_ai_search=types.VertexAISearch(
                datastore=datastore,
                max_results=max_results,
            )
        )
    )
    prompt = f"""
아래 챗봇 서버 제공 근거카드를 우선 참고하고, 필요한 경우 연결된 Vertex AI Search 자료를 함께 사용해 답변하세요.
내부 시스템명, source map, 함수명, 데이터스토어명은 사용자에게 노출하지 마세요.

[사용자 질문]
{question}

[챗봇 서버 제공 근거카드]
{server_context[:18000]}
""".strip()
    started = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[tool],
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        ),
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    candidate = response.candidates[0] if response.candidates else None
    grounding_metadata = getattr(candidate, "grounding_metadata", None) if candidate else None
    return {
        "grounded_combined_elapsed_ms": elapsed_ms,
        "grounded_combined_prompt_chars": len(prompt),
        "grounded_combined_answer_chars": len(response.text or ""),
        "grounded_combined_answer_head": (response.text or "")[:500],
        "grounded_combined_metadata": _to_jsonable(grounding_metadata),
    }


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_json_dict"):
        try:
            return value.to_json_dict()
        except Exception:
            pass
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    return str(value)


def run(args: argparse.Namespace) -> dict[str, Any]:
    _load_dotenv(PROJECT_ROOT / ".env")
    _load_dotenv(PROJECT_ROOT / "pilot_auth.env")
    os.environ["LLM_TOOL_LOOP_ENABLED"] = "false"
    os.environ.setdefault("EVIDENCE_CONTEXT_MODE", "card")

    datastore = args.datastore or _default_datastore()
    if not datastore:
        raise SystemExit("Vertex AI Search datastore is required.")
    datastore_project, datastore_location, data_store_id = _datastore_parts(datastore)
    key_file = args.key_file or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    project = args.project or _project_from_key_file(key_file) or datastore_project

    questions = args.question or list(DEFAULT_QUESTIONS)
    records = []
    for idx, question in enumerate(questions, 1):
        total_started = time.perf_counter()
        record: dict[str, Any] = {
            "case_index": idx,
            "question": question,
            "datastore": datastore,
            "data_store_id": data_store_id,
            "datastore_location": datastore_location,
            "model": args.model,
        }
        try:
            cards = build_server_cards(question, args.agency_type, args.tier, args.max_cards)
            record.update({k: v for k, v in cards.items() if k != "server_context"})

            search = vertex_search(question, datastore, key_file, args.page_size)
            record.update({k: v for k, v in search.items() if k != "vertex_context"})

            llm = llm_generate(
                question=question,
                server_context=cards["server_context"],
                vertex_context=search["vertex_context"],
                project=project,
                location=args.model_location,
                model=args.model,
                thinking_budget=args.thinking_budget,
                timeout_ms=args.http_timeout_ms,
            )
            record.update(llm)
            record["total_split_pipeline_elapsed_ms"] = int((time.perf_counter() - total_started) * 1000)

            if args.run_grounded_combined:
                record.update(
                    grounded_combined_generate(
                        question=question,
                        server_context=cards["server_context"],
                        datastore=datastore,
                        project=project,
                        location=args.model_location,
                        model=args.model,
                        max_results=args.page_size,
                        thinking_budget=args.thinking_budget,
                        timeout_ms=args.http_timeout_ms,
                    )
                )
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["total_case_elapsed_ms"] = int((time.perf_counter() - total_started) * 1000)
        record.setdefault("total_split_pipeline_elapsed_ms", record["total_case_elapsed_ms"])
        records.append(record)

    output = {
        "schema_version": "card_vertex_llm_latency_v1",
        "generated_at": datetime.now().isoformat(),
        "settings": {
            "model": args.model,
            "model_location": args.model_location,
            "datastore": datastore,
            "page_size": args.page_size,
            "tier": args.tier,
            "agency_type": args.agency_type,
            "run_grounded_combined": args.run_grounded_combined,
        },
        "summary": _summarize(records),
        "records": records,
    }
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"card_vertex_llm_latency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = out_dir / "latest.json"
    latest_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    output["output_path"] = str(out_path)
    output["latest_path"] = str(latest_path)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure split latency for server cards, Vertex Search, and final LLM generation."
    )
    parser.add_argument("--question", action="append", help="Question to test. Repeat for multiple cases.")
    parser.add_argument("--datastore", default=os.getenv("VERTEX_AI_SEARCH_DATASTORE", ""))
    parser.add_argument("--key-file", default=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/opt/advisor/vertex-ai-key.json"))
    parser.add_argument("--project", default="")
    parser.add_argument("--model-location", default=os.getenv("GOOGLE_CLOUD_LOCATION", "asia-northeast3"))
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    parser.add_argument("--agency-type", default="local_government")
    parser.add_argument("--tier", type=int, default=2)
    parser.add_argument("--max-cards", type=int, default=5)
    parser.add_argument("--page-size", type=int, default=5)
    parser.add_argument("--thinking-budget", type=int, default=0)
    parser.add_argument("--http-timeout-ms", type=int, default=60000)
    parser.add_argument("--run-grounded-combined", action="store_true")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "artifacts/qa/card_vertex_llm_latency"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2))
