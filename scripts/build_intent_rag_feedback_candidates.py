"""Build review candidates from QA logs and user feedback.

This script does not update the runtime corpus directly.  It writes
`app/data/intent_rag_feedback_candidates.jsonl`, where each line is a review
candidate.  Only records later marked `review_status: approved` are included
by `build_intent_rag_corpus.py`.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
DATA_DIR = APP_DIR / "data"
QA_LOG_DIR = DATA_DIR / "qa_test_logs"
QA_FEEDBACK_DIR = DATA_DIR / "qa_feedback"
OUT_PATH = DATA_DIR / "intent_rag_feedback_candidates.jsonl"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(APP_DIR))

try:
    from app.router.intent_normalization import normalize_query_intent
    from app.router.intent_rag_resolver import resolve_intent_context
except Exception:  # Runtime path fallback.
    from router.intent_normalization import normalize_query_intent
    from router.intent_rag_resolver import resolve_intent_context


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _load_by_date(directory: Path, prefix: str, date: str | None) -> list[dict[str, Any]]:
    if date:
        return _read_jsonl(directory / f"{prefix}_{date}.jsonl")
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob(f"{prefix}_*.jsonl")):
        rows.extend(_read_jsonl(path))
    return rows


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _stable_id(text: str) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8")).hexdigest()[:12]


def _feedback_reasons(feedback_rows: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for fb in feedback_rows:
        rating = fb.get("rating")
        satisfied = fb.get("satisfied")
        tags = [str(tag) for tag in (fb.get("issue_tags") or [])]
        if isinstance(rating, int) and rating <= 2:
            reasons.append("low_user_rating")
        if satisfied is False:
            reasons.append("user_marked_unsatisfied")
        if any(tag in {"의도틀림", "근거부족", "응답느림", "업체검색오류", "답변불만족"} for tag in tags):
            reasons.append("user_issue_tag")
        if fb.get("expected_intent"):
            reasons.append("expected_intent_supplied")
        if fb.get("corrected_answer"):
            reasons.append("corrected_answer_supplied")
    return list(dict.fromkeys(reasons))


def _log_failure_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    extra = row.get("extra") or {}
    answer = str(row.get("answer") or "")
    latency = int(row.get("latency_ms") or 0)
    runtime_status = str(extra.get("runtime_status") or row.get("runtime_status") or "")

    if latency >= 30_000:
        reasons.append("slow_latency_over_30s")
    if int(row.get("tool_call_count") or 0) >= 8:
        reasons.append("many_tool_calls")
    if runtime_status == "failed" or "내부 서버 오류" in answer or "응답 지연" in answer or "타임아웃" in answer:
        reasons.append("runtime_or_timeout_failure")
    if float(extra.get("intent_rag_confidence") or 0.0) < 0.55:
        reasons.append("low_intent_rag_confidence")
    if extra.get("intent_rag_company_search_required") and extra.get("intent_rag_company_search_blocked"):
        reasons.append("conflicting_company_lookup_signals")
    if int(extra.get("evidence_missing_count") or 0) > 0:
        reasons.append("evidence_missing")
    return reasons


def _suggest_record(row: dict[str, Any], feedback_rows: list[dict[str, Any]]) -> dict[str, Any]:
    question = _compact(row.get("question") or "")
    norm = normalize_query_intent(question)
    decision = resolve_intent_context(question)

    expected_intents = [str(fb.get("expected_intent") or "").strip() for fb in feedback_rows if fb.get("expected_intent")]
    corrected_answers = [str(fb.get("corrected_answer") or "").strip() for fb in feedback_rows if fb.get("corrected_answer")]
    labels = list(decision.intent_labels or ())
    sub_intents = list(decision.sub_intents or ())
    if expected_intents:
        labels = list(dict.fromkeys(labels + expected_intents))

    keywords = [
        norm.item_name,
        norm.contract_object,
        *(norm.normalized_terms or ()),
        *(decision.sub_intents or ()),
    ]

    return {
        "id": f"qa_feedback:{row.get('qa_log_id') or _stable_id(question)}",
        "source_type": "qa_feedback_approved",
        "source_file": "intent_rag_feedback_candidates.jsonl",
        "title": question[:80],
        "text": " ".join([
            question,
            " ".join(norm.normalized_terms or ()),
            corrected_answers[0][:500] if corrected_answers else "",
        ]).strip(),
        "keywords": [str(k) for k in dict.fromkeys(keywords) if str(k).strip()][:30],
        "intent_labels": labels or ["common_procurement"],
        "sub_intents": sub_intents,
        "answer_mode": decision.answer_mode or "router_assist",
        "weight": 0.82,
        "usage_policy": "approved_qa_feedback_for_intent_routing_only; law_db_and_source_map_are_authoritative",
        "metadata": {
            "qa_log_id": row.get("qa_log_id"),
            "latency_ms": row.get("latency_ms"),
            "rating_values": [fb.get("rating") for fb in feedback_rows if fb.get("rating") is not None],
            "satisfied_values": [fb.get("satisfied") for fb in feedback_rows if fb.get("satisfied") is not None],
            "expected_intents": expected_intents,
            "has_corrected_answer": bool(corrected_answers),
        },
    }


def build_candidates(date: str | None = None, include_all_slow: bool = True) -> list[dict[str, Any]]:
    logs = _load_by_date(QA_LOG_DIR, "qa_log", date)
    feedback = _load_by_date(QA_FEEDBACK_DIR, "qa_feedback", date)

    feedback_by_log: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fb in feedback:
        qa_log_id = str(fb.get("qa_log_id") or "")
        if qa_log_id:
            feedback_by_log[qa_log_id].append(fb)

    candidates: list[dict[str, Any]] = []
    for row in logs:
        qa_log_id = str(row.get("qa_log_id") or "")
        fb_rows = feedback_by_log.get(qa_log_id, [])
        reasons = _feedback_reasons(fb_rows)
        if include_all_slow:
            reasons.extend(_log_failure_reasons(row))
        reasons = list(dict.fromkeys(reasons))
        if not reasons:
            continue

        suggested_record = _suggest_record(row, fb_rows)
        candidates.append({
            "candidate_id": f"cand_{qa_log_id or _stable_id(row.get('question', ''))}",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "review_status": "needs_review",
            "review_note": "Edit suggested_record, then set review_status to approved or copy to intent_rag_feedback_approved.jsonl.",
            "candidate_reasons": reasons,
            "qa_log_id": qa_log_id,
            "question": row.get("question", ""),
            "answer_excerpt": _compact(row.get("answer", ""))[:900],
            "latency_ms": row.get("latency_ms", 0),
            "feedback": fb_rows,
            "suggested_record": suggested_record,
        })
    return candidates


def write_candidates(candidates: list[dict[str, Any]], out_path: Path = OUT_PATH) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in candidates:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYYMMDD. Omit to scan all logs.")
    parser.add_argument("--out", default=str(OUT_PATH))
    parser.add_argument("--feedback-only", action="store_true", help="Do not add slow/failed rows unless feedback exists.")
    args = parser.parse_args()

    candidates = build_candidates(date=args.date, include_all_slow=not args.feedback_only)
    write_candidates(candidates, Path(args.out))
    print(json.dumps({
        "written": str(Path(args.out)),
        "candidate_count": len(candidates),
        "date": args.date or "all",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
