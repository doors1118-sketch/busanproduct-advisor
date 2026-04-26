"""
Monitoring Policy — PII 마스킹 + 환경별 로그 출력
"""
import os
import re
import json
import hashlib
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

APP_ENV = os.getenv("APP_ENV", "local")

# ─── PII 마스킹 ───
_BIZ_NO_PATTERN = re.compile(r"\d{3}-?\d{2}-?\d{5}")
_PHONE_PATTERN = re.compile(r"0\d{1,2}-?\d{3,4}-?\d{4}")
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

LOG_POLICY = {
    "redact_business_number": True,
    "redact_phone": True,
    "redact_email": True,
    "retention_days": 30,
    "log_level_prod": "summary",
    "log_level_dev": "full",
}


def redact_pii(text: str) -> str:
    """사업자번호, 전화번호, 이메일 마스킹"""
    if not text:
        return text
    result = text
    if LOG_POLICY["redact_business_number"]:
        result = _BIZ_NO_PATTERN.sub("***-**-*****", result)
    if LOG_POLICY["redact_phone"]:
        result = _PHONE_PATTERN.sub("***-****-****", result)
    if LOG_POLICY["redact_email"]:
        result = _EMAIL_PATTERN.sub("***@***.***", result)
    return result


def hash_question(question: str) -> str:
    """user_question_hash 생성 (PII 대체용)"""
    return hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]


# ─── 로거 설정 ───
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOG_DIR = os.path.join(_BASE_DIR, "logs")


def _get_logger(name: str, filename: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    if APP_ENV == "prod":
        # stdout structured logging
        handler = logging.StreamHandler()
    else:
        # local: 파일 로깅 + rotation
        os.makedirs(_LOG_DIR, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(_LOG_DIR, filename),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )

    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


_routing_logger = None
_failure_logger = None


def _get_routing_logger():
    global _routing_logger
    if _routing_logger is None:
        _routing_logger = _get_logger("routing", "routing_log.jsonl")
    return _routing_logger


def _get_failure_logger():
    global _failure_logger
    if _failure_logger is None:
        _failure_logger = _get_logger("classification_failure", "classification_failures.jsonl")
    return _failure_logger


def log_routing(
    request_id: str,
    question: str,
    keyword_result: dict,
    intent_result: dict,
    selected_guardrails: list[str],
    sanity_added_guardrails: list[str] = None,
    core_prompt_hash: str = "",
    prompt_prefix_hash: str = "",
    elapsed_ms: int = 0,
):
    """라우팅 결과 로그"""
    record = {
        "timestamp": datetime.now().isoformat(),
        "request_id": request_id,
        "keyword_result": keyword_result,
        "intent_result": intent_result,
        "selected_guardrails": selected_guardrails,
        "sanity_added_guardrails": sanity_added_guardrails or [],
        "core_prompt_hash": core_prompt_hash,
        "prompt_prefix_hash": prompt_prefix_hash,
        "elapsed_ms": elapsed_ms,
    }

    if APP_ENV == "prod":
        record["user_question_hash"] = hash_question(question)
    else:
        record["user_question"] = redact_pii(question)

    _get_routing_logger().info(json.dumps(record, ensure_ascii=False))


def log_classification_failure(
    request_id: str,
    question: str,
    router_status: str,
    candidates: list[dict],
    reason: str = "",
):
    """분류 실패 로그"""
    record = {
        "timestamp": datetime.now().isoformat(),
        "request_id": request_id,
        "router_status": router_status,
        "candidates": candidates,
        "reason": reason,
    }

    if APP_ENV == "prod":
        record["user_question_hash"] = hash_question(question)
    else:
        record["user_question"] = redact_pii(question)

    _get_failure_logger().info(json.dumps(record, ensure_ascii=False))
