from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from google import genai
from google.genai import types


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_JSONL = PROJECT_ROOT / "artifacts" / "vertex_grounding" / "corpus" / "authority_chunks.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "artifacts" / "vertex_grounding" / "runs"
DEFAULT_BASELINE_URL = "http://49.50.133.160:8001/chat"


EXPERIMENT_CASES: list[dict[str, Any]] = [
    {
        "id": "performance_women_disabled_sme",
        "agency_type": "local_government",
        "question": "여성기업제품, 장애인기업제품을 구매해도 중소기업제품 구매실적에 포함이 되는지 근거 중심으로 설명해줘.",
        "terms": ["여성기업", "장애인기업", "중소기업제품", "구매실적", "판로지원"],
    },
    {
        "id": "goods_computer_60m_route",
        "agency_type": "local_government",
        "question": "예산 6천만원으로 컴퓨터를 구매하려고 해. 계약 방법과 부산업체 구매 확대 방안을 근거 중심으로 안내해줘.",
        "terms": [
            "컴퓨터",
            "물품",
            "6천만원",
            "지방계약법 시행령 제25조",
            "지방계약법 시행령 제30조",
            "수의계약",
            "2인 이상 견적",
            "종합쇼핑몰",
            "물품 다수공급자계약 업무처리규정",
            "중소기업자간",
            "지역업체",
        ],
    },
    {
        "id": "notebook_45m_route",
        "agency_type": "local_government",
        "question": "노트북 4천5백만원어치를 사려면 1인 수의계약, 2인 견적, 종합쇼핑몰 중 어떤 경로를 봐야 해?",
        "terms": [
            "노트북",
            "4천5백만원",
            "지방계약법 시행령 제25조",
            "지방계약법 시행령 제30조",
            "수의계약",
            "1인 견적",
            "2인 이상 견적",
            "종합쇼핑몰",
            "물품 다수공급자계약 업무처리규정",
            "MAS",
        ],
    },
    {
        "id": "agency_national_local_region",
        "agency_type": "national_agency",
        "question": "국가기관 지역제한경쟁입찰에 지방계약법의 부산 지역제한 기준을 참고해도 되는지 국가계약 기준과 비교해줘.",
        "terms": ["국가기관", "국가계약", "지방계약", "지역제한", "제한경쟁"],
    },
    {
        "id": "split_goods_construction",
        "agency_type": "local_government",
        "question": "공사에 포함된 관급자재를 물품으로 따로 발주하려고 하는데 분리발주, 쪼개기 발주, 직접구매 기준을 같이 검토해줘.",
        "terms": ["공사", "물품", "관급자재", "분리발주", "분할발주", "직접구매"],
    },
]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_corpus(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _score_chunk(chunk: dict[str, Any], terms: list[str]) -> int:
    metadata = chunk.get("metadata") or {}
    text = " ".join(
        [
            chunk.get("content") or "",
            metadata.get("source_id") or "",
            metadata.get("source_type") or "",
            metadata.get("authority_level") or "",
            metadata.get("law_name") or "",
            metadata.get("article_no") or "",
            metadata.get("title") or "",
            metadata.get("lookup_key") or "",
            metadata.get("rule_id") or "",
        ]
    ).lower()
    score = 0
    for term in terms:
        term_l = term.lower()
        if term_l in text:
            score += 4 if term_l in (metadata.get("lookup_key") or "").lower() else 2
    source_type = metadata.get("source_type")
    if source_type in {"law", "admin_rule", "source_map"}:
        score += 1
    if source_type in {"manual", "qa"}:
        score -= 1
    return score


def _source_group_key(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") or {}
    return str(
        metadata.get("law_name")
        or metadata.get("source_type")
        or metadata.get("source_file")
        or metadata.get("source_id")
    )


def _select_allowed_sources(
    corpus: list[dict[str, Any]],
    terms: list[str],
    max_sources: int,
    *,
    max_per_source_name: int,
) -> list[dict[str, Any]]:
    scored = [(chunk, _score_chunk(chunk, terms)) for chunk in corpus]
    scored = [(chunk, score) for chunk, score in scored if score > 0]
    scored.sort(
        key=lambda pair: (
            pair[1],
            1 if (pair[0].get("metadata") or {}).get("source_type") in {"law", "admin_rule", "source_map"} else 0,
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    group_counts: dict[str, int] = {}
    for chunk, _ in scored:
        group = _source_group_key(chunk)
        if group_counts.get(group, 0) >= max_per_source_name:
            continue
        selected.append(chunk)
        group_counts[group] = group_counts.get(group, 0) + 1
        if len(selected) >= max_sources:
            return selected
    return selected


def _source_line(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") or {}
    label = metadata.get("lookup_key") or metadata.get("title") or metadata.get("source_id")
    return (
        f"- source_id={metadata.get('source_id')} | type={metadata.get('source_type')} | "
        f"authority={metadata.get('authority_level')} | role={metadata.get('use_role')} | "
        f"current={metadata.get('is_current')} | label={label}"
    )


def _build_prompt(case: dict[str, Any], allowed: list[dict[str, Any]]) -> str:
    source_lines = "\n".join(_source_line(chunk) for chunk in allowed) or "- no preselected source_id"
    return f"""당신은 공공계약·조달 답변 작성자입니다.

아래 허용 근거 범위와 Vertex grounding 결과 안에서만 답하세요.

[허용 source_id 후보]
{source_lines}

[강제 규칙]
1. 법적 결론은 source_type=law, admin_rule, source_map만 primary basis로 사용하세요.
2. manual, qa는 절차 설명·표현 보조로만 사용하고, 금액·현행 기준·최종 법적 결론의 단독 근거로 쓰지 마세요.
3. 허용 source_id 후보 또는 grounding metadata로 확인되는 근거 밖의 문서를 사용하지 마세요.
4. 금액, 기한, 조문번호, 시행일은 원문/근거값을 바꾸지 말고 그대로 쓰세요.
5. 근거가 부족하면 부족하다고 표시하고 단정하지 마세요.
6. 답변 마지막에 사용한 근거를 표로 정리하세요. 표 열은 source_id, 근거명, 조문/항목, 사용역할입니다.

[질문]
{case["question"]}
"""


def _baseline_call(api_url: str, case: dict[str, Any], timeout: int) -> dict[str, Any]:
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
            body = response.json()
        except Exception:
            body = {"raw_response": response.text}
        return {"ok": response.ok, "status_code": response.status_code, "elapsed_ms": elapsed_ms, "response": body}
    except Exception as exc:
        return {"ok": False, "status_code": None, "elapsed_ms": int((time.perf_counter() - started) * 1000), "error": str(exc)}


def _metadata_to_dict(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if hasattr(value, "to_json_dict"):
        return value.to_json_dict()
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_metadata_to_dict(v) for v in value]
    if isinstance(value, dict):
        return {k: _metadata_to_dict(v) for k, v in value.items()}
    return str(value)


def _vertex_tool(args: argparse.Namespace):
    if args.datastore:
        vertex_search = types.VertexAISearch(
            datastore=args.datastore,
            filter=args.vertex_filter or None,
            max_results=args.max_results,
        )
        return types.Tool(retrieval=types.Retrieval(vertex_ai_search=vertex_search))
    if args.rag_corpus:
        rag_resource = types.VertexRagStoreRagResource(rag_corpus=args.rag_corpus)
        rag_store = types.VertexRagStore(
            rag_resources=[rag_resource],
            similarity_top_k=args.max_results,
        )
        return types.Tool(retrieval=types.Retrieval(vertex_rag_store=rag_store))
    raise ValueError("Either --datastore or --rag-corpus is required for live Vertex experiment.")


def _vertex_call(client, args: argparse.Namespace, prompt: str) -> dict[str, Any]:
    started = time.perf_counter()
    tool = _vertex_tool(args)
    response = client.models.generate_content(
        model=args.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[tool],
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_budget=args.thinking_budget),
        ),
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    candidate = response.candidates[0] if response.candidates else None
    grounding_metadata = getattr(candidate, "grounding_metadata", None) if candidate else None
    usage_metadata = getattr(response, "usage_metadata", None)
    return {
        "ok": True,
        "elapsed_ms": elapsed_ms,
        "answer": response.text,
        "grounding_metadata": _metadata_to_dict(grounding_metadata),
        "usage_metadata": _metadata_to_dict(usage_metadata),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    _load_dotenv(PROJECT_ROOT / ".env")
    corpus = _load_corpus(args.corpus_jsonl)
    selected_cases = EXPERIMENT_CASES
    if args.case_id:
        selected_cases = [case for case in EXPERIMENT_CASES if case["id"] in set(args.case_id)]

    client = None
    if not args.dry_run:
        client = genai.Client(
            vertexai=True,
            project=args.project,
            location=args.location,
            http_options=types.HttpOptions(api_version="v1", timeout=args.http_timeout_ms),
        )

    records: list[dict[str, Any]] = []
    for case in selected_cases:
        for repeat_index in range(args.repeat):
            allowed = _select_allowed_sources(
                corpus,
                case.get("terms") or [],
                args.max_allowed_sources,
                max_per_source_name=args.max_per_source_name,
            )
            prompt = _build_prompt(case, allowed)
            record: dict[str, Any] = {
                "case": case,
                "repeat_index": repeat_index + 1,
                "allowed_sources": [
                    {
                        "source_id": (chunk.get("metadata") or {}).get("source_id"),
                        "source_type": (chunk.get("metadata") or {}).get("source_type"),
                        "authority_level": (chunk.get("metadata") or {}).get("authority_level"),
                        "lookup_key": (chunk.get("metadata") or {}).get("lookup_key"),
                        "title": (chunk.get("metadata") or {}).get("title"),
                    }
                    for chunk in allowed
                ],
                "prompt_chars": len(prompt),
                "prompt_preview": prompt[: args.prompt_preview_chars],
            }
            if args.run_baseline:
                record["baseline"] = _baseline_call(args.baseline_url, case, args.baseline_timeout)
            if args.dry_run:
                record["vertex"] = {"ok": None, "skipped": "dry_run"}
            else:
                vertex_started = time.perf_counter()
                try:
                    record["vertex"] = _vertex_call(client, args, prompt)
                except Exception as exc:
                    record["vertex"] = {
                        "ok": False,
                        "elapsed_ms": int((time.perf_counter() - vertex_started) * 1000),
                        "error": str(exc),
                    }
            records.append(record)

    run_data = {
        "schema_version": "vertex_grounding_experiment_v1",
        "run_id": f"vertex_grounding_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": args.dry_run,
        "model": args.model,
        "project": args.project,
        "location": args.location,
        "datastore": args.datastore,
        "rag_corpus": args.rag_corpus,
        "vertex_filter": args.vertex_filter,
        "corpus_jsonl": str(args.corpus_jsonl),
        "records": records,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{run_data['run_id']}.json"
    out_path.write_text(json.dumps(run_data, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = args.out_dir / "latest.json"
    latest_path.write_text(json.dumps({"json_path": str(out_path)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"json_path": str(out_path), "records": len(records), "dry_run": args.dry_run}, ensure_ascii=False, indent=2))
    return run_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare current server answers with Vertex grounding/RAG answers.")
    parser.add_argument("--corpus-jsonl", type=Path, default=DEFAULT_CORPUS_JSONL)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_VERTEX_PROJECT") or "carbide-team-457809-a8")
    parser.add_argument("--location", default=os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("GOOGLE_VERTEX_LOCATION") or "asia-northeast3")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    parser.add_argument("--datastore", default=os.getenv("VERTEX_AI_SEARCH_DATASTORE", ""))
    parser.add_argument("--rag-corpus", default=os.getenv("VERTEX_RAG_CORPUS", ""))
    parser.add_argument("--vertex-filter", default=os.getenv("VERTEX_GROUNDING_FILTER", ""))
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--max-allowed-sources", type=int, default=12)
    parser.add_argument("--max-per-source-name", type=int, default=3)
    parser.add_argument("--thinking-budget", type=int, default=0)
    parser.add_argument("--http-timeout-ms", type=int, default=30000)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat each case to observe implicit cache hit behavior.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-baseline", action="store_true")
    parser.add_argument("--baseline-url", default=DEFAULT_BASELINE_URL)
    parser.add_argument("--baseline-timeout", type=int, default=45)
    parser.add_argument("--prompt-preview-chars", type=int, default=3000)
    args = parser.parse_args()

    if not args.dry_run and not (args.datastore or args.rag_corpus):
        parser.error("live mode requires --datastore or --rag-corpus. Use --dry-run to inspect prompts first.")
    run(args)


if __name__ == "__main__":
    main()
