"""
QA 테스트 로그 저장 모듈
━━━━━━━━━━━━━━━━━━━━━━━
직원 내부 테스트 시 모든 질문/답변/파이프라인 메타데이터를
JSON Lines 형식으로 저장하여 일괄 검토 가능하게 합니다.

저장 위치: /opt/advisor/app/data/qa_test_logs/
파일 형식: qa_log_YYYYMMDD.jsonl (1일 1파일)
"""
import os
import json
import time
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "qa_test_logs")


def save_qa_log(
    question: str,
    answer: str,
    agency_type: str = None,
    latency_ms: int = 0,
    tier_resolved: int = None,
    tool_call_count: int = 0,
    mcp_preflight_elapsed_ms: int = 0,
    mandatory_mcp_plan: list = None,
    mandatory_mcp_executed: list = None,
    mandatory_mcp_missing: list = None,
    model_used: str = None,
    pipeline_mode: str = None,
    extra_meta: dict = None,
):
    """
    QA 테스트 로그 1건 저장.
    
    파일: qa_log_YYYYMMDD.jsonl
    각 행: {"timestamp", "question", "answer", "pipeline", ...}
    """
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(_LOG_DIR, f"qa_log_{today}.jsonl")
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer,
            "answer_length": len(answer),
            "agency_type": agency_type,
            "latency_ms": latency_ms,
            "tier_resolved": tier_resolved,
            "tool_call_count": tool_call_count,
            "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
            "pipeline_mode": pipeline_mode,
            "model_used": model_used,
            "mandatory_mcp_plan": _safe_serialize(mandatory_mcp_plan),
            "mandatory_mcp_executed": mandatory_mcp_executed or [],
            "mandatory_mcp_missing": mandatory_mcp_missing or [],
        }
        
        if extra_meta:
            record["extra"] = _safe_serialize(extra_meta)
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        
        print(f"  [QA_LOG] Saved to {log_file}")
    except Exception as e:
        print(f"  [QA_LOG] Error: {e}")


def _safe_serialize(obj):
    """직렬화 안전 변환."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_safe_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    return str(obj)


def get_qa_logs(date_str: str = None, limit: int = 100) -> list:
    """
    QA 로그 조회.
    
    Args:
        date_str: "20260507" 형식. None이면 오늘.
        limit: 최대 반환 건수.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    
    log_file = os.path.join(_LOG_DIR, f"qa_log_{date_str}.jsonl")
    if not os.path.exists(log_file):
        return []
    
    records = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    return records[-limit:]


def get_qa_summary(date_str: str = None) -> dict:
    """QA 로그 일별 요약 통계."""
    records = get_qa_logs(date_str, limit=9999)
    if not records:
        return {"count": 0}
    
    latencies = [r.get("latency_ms", 0) for r in records]
    tiers = [r.get("tier_resolved", 0) for r in records]
    tool_counts = [r.get("tool_call_count", 0) for r in records]
    
    return {
        "date": date_str or datetime.now().strftime("%Y%m%d"),
        "count": len(records),
        "avg_latency_ms": int(sum(latencies) / len(latencies)),
        "max_latency_ms": max(latencies),
        "min_latency_ms": min(latencies),
        "avg_tool_calls": round(sum(tool_counts) / len(tool_counts), 1),
        "tier_distribution": {f"tier_{t}": tiers.count(t) for t in set(tiers)},
    }
