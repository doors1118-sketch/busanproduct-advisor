"""Compare Gemini and OpenAI GPT as answer-polishing writers.

This is an offline measurement harness. It does not change the production
request path. For each question it:

1. calls the running chatbot server,
2. sends the server answer to Gemini as a conservative rewrite task,
3. sends the same server answer to OpenAI Responses API as the same rewrite task,
4. records latency, rough token usage, leak checks, and answer heads.

If an API key is missing, that provider is skipped and the rest still runs.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

try:
    from google import genai
    from google.genai import types as google_types
except Exception:  # pragma: no cover - optional runtime dependency
    genai = None
    google_types = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_URL = "http://49.50.133.160:8001/chat"
DEFAULT_OUT_DIR = PROJECT_ROOT / "artifacts" / "qa" / "writer_model_compare"

DEFAULT_QUESTIONS: list[dict[str, str]] = [
    {
        "id": "bid_notice_local_company",
        "agency_type": "local_government",
        "question": "입찰공고문 작성할 때 지역업체 활용 조건을 넣으려면 어떤 점을 조심해야 해?",
    },
    {
        "id": "goods_direct_100m",
        "agency_type": "local_government",
        "question": "물품 1억원 구매는 수의계약이 가능한지 근거 중심으로 설명해줘.",
    },
    {
        "id": "computer_60m_candidates",
        "agency_type": "local_government",
        "question": "예산 6천만원으로 컴퓨터 구매하려고 하는데 계약방법, 내부 근거, 부산업체 후보를 종합해서 답변해줘.",
    },
    {
        "id": "regional_limit_compare",
        "agency_type": "local_government",
        "question": "지역제한경쟁입찰 기준금액을 국가, 공기업 및 준정부기관, 지방자치단체로 비교해줘.",
    },
]

FORBIDDEN_MARKERS = (
    "source map",
    "source_map",
    "dataStore",
    "datastore",
    "get_company_detail",
    "function_call",
    "candidate 없음",
    "후보표 생략 대상",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
)

USD_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    # OpenAI public API list, May 2026. Keep this as an estimate only; the
    # API response usage is the source of token counts, not billing.
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "cached_input": 0.10, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "cached_input": 0.025, "output": 0.40},
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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


def _stats(values: list[int]) -> dict[str, Any]:
    return {
        "count": len(values),
        "avg": round(statistics.mean(values), 1) if values else None,
        "p50": _percentile(values, 50),
        "p90": _percentile(values, 90),
        "max": max(values) if values else None,
    }


def _rough_cost_usd(model: str, usage: dict[str, Any] | None) -> float | None:
    if not usage:
        return None
    prices = USD_PER_MILLION_TOKENS.get(model)
    if not prices:
        return None
    input_tokens = int(
        usage.get("input_tokens")
        or usage.get("prompt_token_count")
        or usage.get("prompt_tokens")
        or 0
    )
    output_tokens = int(
        usage.get("output_tokens")
        or usage.get("candidates_token_count")
        or usage.get("completion_tokens")
        or 0
    )
    return round(
        (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000,
        6,
    )


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


def _extract_openai_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    chunks: list[str] = []
    for item in data.get("output") or []:
        for content in item.get("content") or []:
            if isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def build_writer_prompt(question: str, original_answer: str) -> str:
    return f"""
아래 [원래 답변]을 공공계약 담당자가 읽기 쉬운 자연스러운 한국어로만 다듬어 주세요.

[엄격한 조건]
- 법적 결론, 금액, 조문명, 업체명, 표의 행/열 정보는 바꾸지 마세요.
- 새로운 법령·판단·업체를 추가하지 마세요.
- 표가 있으면 표 구조를 유지하세요.
- 내부 시스템명, 함수명, source map, dataStore 같은 개발/검색 용어를 노출하지 마세요.
- 근거가 부족하다는 취지의 문장은 유지하세요.
- 답변만 출력하세요.

[사용자 질문]
{question}

[원래 답변]
{original_answer[:18000]}
""".strip()


def call_chatbot(api_url: str, question: str, agency_type: str, timeout_sec: int) -> dict[str, Any]:
    started = time.perf_counter()
    response = requests.post(
        api_url,
        json={"message": question, "agency_type": agency_type, "history": []},
        timeout=timeout_sec,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    try:
        data = response.json()
    except Exception:
        data = {"raw_response": response.text}
    return {
        "ok": response.ok,
        "status_code": response.status_code,
        "elapsed_ms": elapsed_ms,
        "data": data,
    }


def call_gemini_writer(prompt: str, model: str, timeout_ms: int, thinking_budget: int) -> dict[str, Any]:
    if genai is None or google_types is None:
        return {"skipped": True, "skip_reason": "google-genai package is not installed"}
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"skipped": True, "skip_reason": "GEMINI_API_KEY is missing"}

    client = genai.Client(
        api_key=api_key,
        http_options=google_types.HttpOptions(timeout=timeout_ms),
    )
    started = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=google_types.GenerateContentConfig(
            temperature=0.1,
            thinking_config=google_types.ThinkingConfig(thinking_budget=thinking_budget),
        ),
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    text = response.text or ""
    usage = _to_jsonable(getattr(response, "usage_metadata", None))
    return {
        "skipped": False,
        "model": model,
        "elapsed_ms": elapsed_ms,
        "answer_chars": len(text),
        "answer_head": text[:700],
        "usage": usage,
        "rough_cost_usd": _rough_cost_usd(model, usage if isinstance(usage, dict) else None),
        "internal_label_leak": any(marker in text for marker in FORBIDDEN_MARKERS),
    }


def call_openai_writer(prompt: str, model: str, timeout_sec: int, max_output_tokens: int) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"skipped": True, "skip_reason": "OPENAI_API_KEY is missing"}

    body: dict[str, Any] = {
        "model": model,
        "instructions": "You are a conservative Korean public procurement answer editor. Rewrite only; do not add facts.",
        "input": prompt,
        "max_output_tokens": max_output_tokens,
        "store": False,
        "tool_choice": "none",
    }
    if model.startswith("gpt-5"):
        body["reasoning"] = {"effort": "minimal"}

    started = time.perf_counter()
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout_sec,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    try:
        data = response.json()
    except Exception:
        data = {"raw_response": response.text}
    text = _extract_openai_text(data)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
    result = {
        "skipped": False,
        "model": model,
        "ok": response.ok,
        "status_code": response.status_code,
        "elapsed_ms": elapsed_ms,
        "answer_chars": len(text),
        "answer_head": text[:700],
        "usage": usage,
        "rough_cost_usd": _rough_cost_usd(model, usage),
        "internal_label_leak": any(marker in text for marker in FORBIDDEN_MARKERS),
    }
    if not response.ok:
        result["error"] = data.get("error") or data
    return result


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    server_ms = [r["server"]["elapsed_ms"] for r in records if r.get("server")]
    gemini_ms = [
        r["gemini_writer"]["elapsed_ms"]
        for r in records
        if r.get("gemini_writer") and not r["gemini_writer"].get("skipped")
    ]
    openai_ms = [
        r["openai_writer"]["elapsed_ms"]
        for r in records
        if r.get("openai_writer") and not r["openai_writer"].get("skipped")
    ]
    return {
        "count": len(records),
        "server_elapsed_ms": _stats(server_ms),
        "gemini_writer_elapsed_ms": _stats(gemini_ms),
        "openai_writer_elapsed_ms": _stats(openai_ms),
        "openai_skipped": sum(1 for r in records if r.get("openai_writer", {}).get("skipped")),
        "gemini_skipped": sum(1 for r in records if r.get("gemini_writer", {}).get("skipped")),
        "provider_errors": {
            "openai": sum(1 for r in records if r.get("openai_writer", {}).get("error")),
            "gemini": sum(1 for r in records if r.get("gemini_writer", {}).get("error")),
        },
    }


def _questions_from_args(args: argparse.Namespace) -> list[dict[str, str]]:
    if not args.question:
        return DEFAULT_QUESTIONS
    return [
        {
            "id": f"custom_{idx}",
            "agency_type": args.agency_type,
            "question": question,
        }
        for idx, question in enumerate(args.question, 1)
    ]


def run(args: argparse.Namespace) -> dict[str, Any]:
    _load_dotenv(PROJECT_ROOT / ".env")
    _load_dotenv(PROJECT_ROOT / "pilot_auth.env")

    records: list[dict[str, Any]] = []
    for case in _questions_from_args(args):
        question = case["question"]
        agency_type = case.get("agency_type") or args.agency_type
        record: dict[str, Any] = {
            "id": case["id"],
            "question": question,
            "agency_type": agency_type,
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            server = call_chatbot(args.api_url, question, agency_type, args.server_timeout_sec)
            record["server"] = {
                "ok": server["ok"],
                "status_code": server["status_code"],
                "elapsed_ms": server["elapsed_ms"],
                "server_latency_ms": server["data"].get("latency_ms"),
                "route": server["data"].get("route") or server["data"].get("routing_decision"),
                "tier_resolved": server["data"].get("tier_resolved"),
                "tool_call_count": server["data"].get("tool_call_count"),
                "llm_internal_tools_disabled": server["data"].get("llm_internal_tools_disabled"),
                "answer_chars": len(str(server["data"].get("answer") or "")),
                "answer_head": str(server["data"].get("answer") or "")[:700],
            }
            original_answer = str(server["data"].get("answer") or server["data"].get("raw_response") or "")
            prompt = build_writer_prompt(question, original_answer)
            record["writer_prompt_chars"] = len(prompt)
            record["gemini_writer"] = call_gemini_writer(
                prompt,
                args.gemini_model,
                args.provider_timeout_ms,
                args.gemini_thinking_budget,
            )
            record["openai_writer"] = call_openai_writer(
                prompt,
                args.openai_model,
                max(1, int(args.provider_timeout_ms / 1000)),
                args.max_output_tokens,
            )
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)

    output = {
        "schema_version": "writer_model_compare_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "settings": {
            "api_url": args.api_url,
            "gemini_model": args.gemini_model,
            "openai_model": args.openai_model,
            "provider_timeout_ms": args.provider_timeout_ms,
            "max_output_tokens": args.max_output_tokens,
            "openai_api_key_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "gemini_api_key_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        },
        "summary": _summarize(records),
        "records": records,
    }
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"writer_model_compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = out_dir / "latest.json"
    latest_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    output["output_path"] = str(out_path)
    output["latest_path"] = str(latest_path)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Gemini and OpenAI GPT writer latency.")
    parser.add_argument("--api-url", default=os.getenv("CHATBOT_API_URL", DEFAULT_API_URL))
    parser.add_argument("--question", action="append", help="Question to test. Repeat for multiple cases.")
    parser.add_argument("--agency-type", default="local_government")
    parser.add_argument("--gemini-model", default=os.getenv("WRITER_GEMINI_MODEL", "gemini-2.5-flash"))
    parser.add_argument("--openai-model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    parser.add_argument("--gemini-thinking-budget", type=int, default=0)
    parser.add_argument("--max-output-tokens", type=int, default=1800)
    parser.add_argument("--server-timeout-sec", type=int, default=90)
    parser.add_argument("--provider-timeout-ms", type=int, default=60000)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT_DIR))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2))
