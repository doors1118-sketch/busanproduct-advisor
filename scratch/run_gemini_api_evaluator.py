from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(r"C:\Users\COMTREE\Desktop\Busan_Local_Procurement_Chatbot_Questions.md")
DEFAULT_MODEL = "gemini-3-pro-preview"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


@dataclass
class QuestionItem:
    id: str
    no: int
    category: str
    question: str


def read_text_auto(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in read_text_auto(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_questions(path: Path) -> list[QuestionItem]:
    text = read_text_auto(path)
    items: list[QuestionItem] = []
    category = "미분류"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = re.match(r"^##\s+\d+\.\s+(.+?)\s*$", line)
        if heading:
            category = heading.group(1).strip()
            continue
        match = re.match(r"^(\d{1,3})\.\s+(.+?)\s*$", line)
        if not match:
            continue
        no = int(match.group(1))
        items.append(QuestionItem(id=f"q{no:03d}", no=no, category=category, question=match.group(2).strip()))
    return items


def load_answers_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return answers
    for line in read_text_auto(path).splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        item_id = str(row.get("id") or "").strip()
        if item_id:
            answers[item_id] = row
    return answers


def call_chat(base_url: str, question: str, agency_type: str, timeout_sec: int) -> dict[str, Any]:
    payload = json.dumps(
        {"message": question, "agency_type": agency_type, "history": []},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        data = {
            "answer": "",
            "chat_error": f"HTTP {exc.code}",
            "chat_error_body": body[:1000],
        }
    except Exception as exc:
        data = {
            "answer": "",
            "chat_error": type(exc).__name__,
            "chat_error_body": str(exc)[:1000],
        }
    data["_elapsed_ms"] = int((time.time() - started) * 1000)
    return data


def build_prompt(item: QuestionItem, chatbot_answer: str) -> str:
    return f"""당신은 한국 지방계약 실무 답변 품질 평가자입니다.

목표:
- 아래 질문 1개와 챗봇 답변 1개만 평가하세요.
- Gemini의 역할은 최종 정답 생성기가 아니라 외부 리뷰어입니다.
- 법령·금액 기준을 확신하지 못하면 단정하지 말고 "최신 확인 필요"라고 표시하세요.
- "가능 경로"와 "추천 경로"를 반드시 분리하세요.
- 물품 질문에서는 종합쇼핑몰/MAS/제3자단가계약 가능성을 배제해도 되는지 반드시 판단하세요.
- 지역업체 우대는 법정 수의계약 사유와 구분하세요.
- 수의계약 가능 범위, 1인 견적 가능 범위, 2인 이상 견적 절차를 혼동하지 마세요.
- 기존 답변의 좋은 부분은 유지 대상으로 표시하고, 나쁜 부분만 고치세요.
- 모범답안은 실무자가 바로 읽을 수 있게 결론 우선, 한국어로 작성하세요.

현재 평가일: 2026-05-11
기관 유형 기본값: 지방자치단체

질문 ID: {item.id}
질문 분야: {item.category}

[질문]
{item.question}

[현재 챗봇 답변]
{chatbot_answer.strip() or "(답변 없음)"}

출력은 반드시 아래 JSON 하나만 반환하세요. 마크다운 코드블록은 쓰지 마세요.

{{
  "id": "{item.id}",
  "question": "{json_escape(item.question)}",
  "verdict": "채택|수정후채택|부분채택|폐기",
  "severity": "low|medium|high",
  "current_answer_strengths": [],
  "current_answer_problems": [],
  "missing_core_judgments": [],
  "gemini_answer_risks_to_verify": [],
  "must_keep_from_current_answer": [],
  "must_include": [],
  "must_not_include": [],
  "possible_routes": [],
  "recommended_route": "",
  "routes_not_to_exclude": [],
  "contract_object": "",
  "item_or_work": "",
  "amount": null,
  "legal_basis_to_check": [],
  "model_answer": "",
  "fix_targets": [],
  "test_case_idea": "",
  "one_line_summary": ""
}}
"""


def json_escape(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def gemini_payload(prompt: str, *, thinking_level: str, temperature: float, max_output_tokens: int) -> dict[str, Any]:
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingLevel": thinking_level},
        },
    }


def extract_text(response: dict[str, Any]) -> str:
    parts = (
        response.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    texts = [str(part.get("text") or "") for part in parts if part.get("text")]
    return "\n".join(texts).strip()


def call_gemini(
    *,
    api_key: str,
    model: str,
    prompt: str,
    thinking_level: str,
    temperature: float,
    max_output_tokens: int,
    timeout_sec: int,
    max_retries: int,
) -> tuple[dict[str, Any], str]:
    url = GEMINI_ENDPOINT.format(model=model)
    payload = json.dumps(
        gemini_payload(
            prompt,
            thinking_level=thinking_level,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-goog-api-key": api_key,
    }

    last_error = ""
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                return data, extract_text(data)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {body[:1000]}"
            if exc.code not in (408, 409, 429, 500, 502, 503, 504) or attempt >= max_retries:
                break
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
            if attempt >= max_retries:
                break
        sleep_for = min(60.0, (2**attempt) + random.random())
        time.sleep(sleep_for)
    raise RuntimeError(last_error)


def call_gemini_vertex(
    *,
    project: str,
    location: str,
    credentials: str,
    model: str,
    prompt: str,
    thinking_level: str,
    temperature: float,
    max_output_tokens: int,
    timeout_sec: int,
    max_retries: int,
) -> tuple[dict[str, Any], str]:
    try:
        from google import genai
        from google.genai import types
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"google-genai import failed: {exc!r}") from exc

    if credentials:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials
    timeout_ms = max(1, timeout_sec) * 1000
    client = genai.Client(
        vertexai=True,
        project=project,
        location=location,
        http_options=types.HttpOptions(timeout=timeout_ms),
    )
    last_error = ""
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
                ),
            )
            break
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
            if attempt >= max_retries:
                raise RuntimeError(last_error) from exc
            sleep_for = min(60.0, (2**attempt) + random.random())
            time.sleep(sleep_for)
    text = response.text or ""
    raw = {
        "text": text,
        "usage_metadata": _to_jsonable(getattr(response, "usage_metadata", None)),
        "model_version": getattr(response, "model_version", None),
    }
    return raw, text


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump())
    if hasattr(value, "to_dict"):
        return _to_jsonable(value.to_dict())
    if hasattr(value, "__dict__"):
        return {k: _to_jsonable(v) for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)


def parse_json_result(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return json.loads(stripped)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_markdown_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    parts = ["# Gemini API 단건 평가 결과", ""]
    for row in rows:
        result = row.get("result") or {}
        parts.extend(
            [
                f"## {row.get('id')} {row.get('question')}",
                "",
                f"- verdict: {result.get('verdict', '')}",
                f"- severity: {result.get('severity', '')}",
                f"- recommended_route: {result.get('recommended_route', '')}",
                "",
                "### 문제점",
                *[f"- {x}" for x in result.get("current_answer_problems") or []],
                "",
                "### 누락 판단",
                *[f"- {x}" for x in result.get("missing_core_judgments") or []],
                "",
                "### 배제하면 안 되는 경로",
                *[f"- {x}" for x in result.get("routes_not_to_exclude") or []],
                "",
                "### 모범답안",
                str(result.get("model_answer") or "").strip(),
                "",
            ]
        )
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one-question-at-a-time Gemini API evaluation.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="100-question markdown file")
    parser.add_argument("--answers-jsonl", default="", help="Existing chatbot answers JSONL. Optional.")
    parser.add_argument("--chat-url", default="", help="If set, call this /chat endpoint to get fresh chatbot answers.")
    parser.add_argument("--agency-type", default="local_government")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--thinking-level", default=os.environ.get("GEMINI_THINKING_LEVEL", "high"))
    parser.add_argument("--vertex", action="store_true", help="Use Vertex AI instead of Gemini Developer API.")
    parser.add_argument("--vertex-project", default=os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GOOGLE_VERTEX_PROJECT") or "carbide-team-457809-a8")
    parser.add_argument("--vertex-location", default=os.environ.get("GOOGLE_CLOUD_LOCATION") or os.environ.get("GOOGLE_VERTEX_LOCATION") or "asia-northeast3")
    parser.add_argument("--vertex-credentials", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""))
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--chat-timeout-sec", type=int, default=45)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--sleep-sec", type=float, default=2.0)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv(Path(".env"))
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if args.vertex:
        if args.vertex_credentials and not Path(args.vertex_credentials).exists() and not args.dry_run:
            raise SystemExit(f"Vertex credential file not found: {args.vertex_credentials}")
        if not args.vertex_project and not args.dry_run:
            raise SystemExit("--vertex-project 또는 GOOGLE_CLOUD_PROJECT가 필요합니다.")
    elif not api_key and not args.dry_run:
        raise SystemExit("GEMINI_API_KEY 또는 GOOGLE_API_KEY 환경변수를 설정하세요.")

    items = [item for item in parse_questions(Path(args.input)) if item.no >= args.start]
    if args.limit > 0:
        items = items[: args.limit]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else Path("artifacts") / f"gemini_api_eval_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    results_jsonl = out_dir / "gemini_eval_results.jsonl"
    answers_jsonl = out_dir / "chatbot_answers_used.jsonl"
    summary_md = out_dir / "gemini_eval_results.md"

    existing_ids: set[str] = set()
    rows_for_summary: list[dict[str, Any]] = []
    if args.resume and results_jsonl.exists():
        for line in results_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            existing_ids.add(str(row.get("id")))
            rows_for_summary.append(row)

    existing_answers = load_answers_jsonl(Path(args.answers_jsonl)) if args.answers_jsonl else {}

    manifest = {
        "created_at": stamp,
        "model": args.model,
        "backend": "vertex" if args.vertex else "developer_api",
        "thinking_level": args.thinking_level,
        "temperature": args.temperature,
        "vertex_project": args.vertex_project if args.vertex else "",
        "vertex_location": args.vertex_location if args.vertex else "",
        "input": str(Path(args.input).resolve()),
        "answers_jsonl": args.answers_jsonl,
        "chat_url": args.chat_url,
        "start": args.start,
        "limit": args.limit,
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    for index, item in enumerate(items, start=1):
        if args.resume and item.id in existing_ids:
            print(f"[skip] {item.id}")
            continue

        print(f"[{index}/{len(items)}] {item.id} {item.question}")
        answer_payload = existing_answers.get(item.id, {})
        if args.chat_url:
            answer_payload = call_chat(args.chat_url, item.question, args.agency_type, args.chat_timeout_sec)
            answer_payload = {"id": item.id, "question": item.question, **answer_payload}
            append_jsonl(answers_jsonl, answer_payload)

        chatbot_answer = str(answer_payload.get("answer") or "")
        prompt = build_prompt(item, chatbot_answer)
        (raw_dir / f"{item.id}_prompt.md").write_text(prompt, encoding="utf-8")

        if args.dry_run:
            result = {
                "id": item.id,
                "question": item.question,
                "dry_run": True,
                "prompt_file": str((raw_dir / f"{item.id}_prompt.md").resolve()),
            }
            raw_text = ""
            response = {}
        else:
            started = time.time()
            if args.vertex:
                response, raw_text = call_gemini_vertex(
                    project=args.vertex_project,
                    location=args.vertex_location,
                    credentials=args.vertex_credentials,
                    model=args.model,
                    prompt=prompt,
                    thinking_level=args.thinking_level,
                    temperature=args.temperature,
                    max_output_tokens=args.max_output_tokens,
                    timeout_sec=args.timeout_sec,
                    max_retries=args.max_retries,
                )
            else:
                response, raw_text = call_gemini(
                    api_key=api_key or "",
                    model=args.model,
                    prompt=prompt,
                    thinking_level=args.thinking_level,
                    temperature=args.temperature,
                    max_output_tokens=args.max_output_tokens,
                    timeout_sec=args.timeout_sec,
                    max_retries=args.max_retries,
                )
            elapsed_ms = int((time.time() - started) * 1000)
            (raw_dir / f"{item.id}_response.json").write_text(
                json.dumps(response, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (raw_dir / f"{item.id}_response_text.json").write_text(raw_text, encoding="utf-8")
            try:
                result = parse_json_result(raw_text)
            except Exception as exc:  # noqa: BLE001
                result = {"id": item.id, "parse_error": repr(exc), "raw_text": raw_text}
            result["_elapsed_ms"] = elapsed_ms

        row = {
            "id": item.id,
            "no": item.no,
            "category": item.category,
            "question": item.question,
            "chatbot_answer": chatbot_answer,
            "result": result,
        }
        append_jsonl(results_jsonl, row)
        rows_for_summary.append(row)
        write_markdown_summary(summary_md, rows_for_summary)

        if not args.dry_run and args.sleep_sec > 0:
            time.sleep(args.sleep_sec)

    print(f"saved: {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
