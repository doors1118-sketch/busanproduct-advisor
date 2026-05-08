"""Graded final-answer scanner.

critical: must trigger fail-closed rewrite or deterministic replacement.
warning: record and review, but do not discard a useful practical answer.
info: telemetry only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class ScanFinding:
    severity: str
    pattern: str
    category: str

    def to_dict(self) -> dict:
        return asdict(self)


CRITICAL_PATTERNS: list[tuple[str, str]] = [
    (r"수의계약\s*(이\s*)?가능합니다", "unsupported_contract_conclusion"),
    (r"1인\s*견적\s*(이\s*)?가능합니다", "unsupported_contract_conclusion"),
    (r"계약\s*(이\s*)?가능합니다", "unsupported_contract_conclusion"),
    (r"구매\s*(가\s*)?가능합니다", "unsupported_contract_conclusion"),
    (r"불가능합니다", "unsupported_contract_conclusion"),
    (r"바로\s*(계약|구매|가능)", "unsupported_contract_conclusion"),
    (r"금액\s*(제한|한도)\s*없이\s*(가능|진행|수의계약)", "unsupported_amount_claim"),
    (r"금액에\s*관계없이\s*수의계약", "unsupported_amount_claim"),
    (r"여성기업이므로\s*수의계약\s*가능합니다", "unsupported_policy_company_claim"),
    (r"해당\s*업체와\s*직접\s*계약", "vendor_specific_direct_contract"),
    (r"수의계약을\s*진행할\s*수\s*있습니다", "unsupported_contract_conclusion"),
    (r"수의계약으로\s*구매할\s*수", "unsupported_contract_conclusion"),
    (r"수의계약\s*진행\s*가능", "unsupported_contract_conclusion"),
]

WARNING_PATTERNS: list[tuple[str, str]] = [
    (r"수의계약\s*추진", "needs_contextual_review"),
    (r"수의계약을\s*추진", "needs_contextual_review"),
    (r"수의계약\s*체결", "needs_contextual_review"),
    (r"1인\s*견적\s*수의계약", "needs_contextual_review"),
    (r"직접\s*수의계약", "needs_contextual_review"),
    (r"계약을\s*추진", "needs_contextual_review"),
    (r"직접\s*계약", "needs_contextual_review"),
    (r"수의계약을\s*검토해\s*볼\s*수", "acceptable_but_review"),
    (r"수의계약으로\s*진행", "needs_contextual_review"),
]

PROMPT_LEAK_PATTERNS: list[tuple[str, str]] = [
    (r"중요 지침", "prompt_leak"),
    (r"내부 처리", "prompt_leak"),
    (r"초안 답변", "prompt_leak"),
    (r"알겠습니다", "assistant_process_leak"),
    (r"수정하겠습니다", "assistant_process_leak"),
    (r"시스템 지침", "prompt_leak"),
    (r"프롬프트", "prompt_leak"),
    (r"\[MCP_FAILED\]", "raw_tool_leak"),
    (r"MCP_FAILED", "raw_tool_leak"),
    (r"RAG 검색", "raw_pipeline_leak"),
    (r"조회 실패로 법적 판단", "unsafe_failure_wording"),
    (r"확인되지 않았습니다\)", "format_leak"),
    (r"MCP 호출", "raw_tool_leak"),
]


def _match(text: str, patterns: Iterable[tuple[str, str]], severity: str) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    for pattern, category in patterns:
        if re.search(pattern, text or ""):
            findings.append(ScanFinding(severity=severity, pattern=pattern, category=category))
    return findings


def scan_final_answer(text: str) -> dict:
    findings = []
    findings.extend(_match(text, CRITICAL_PATTERNS, "critical"))
    findings.extend(_match(text, WARNING_PATTERNS, "warning"))
    findings.extend(_match(text, PROMPT_LEAK_PATTERNS, "critical"))
    critical = [f for f in findings if f.severity == "critical"]
    warning = [f for f in findings if f.severity == "warning"]
    return {
        "findings": [f.to_dict() for f in findings],
        "critical_patterns": [f.pattern for f in critical],
        "warning_patterns": [f.pattern for f in warning],
        "critical_count": len(critical),
        "warning_count": len(warning),
        "prompt_leak_detected": any(f.category in {"prompt_leak", "assistant_process_leak", "raw_tool_leak", "raw_pipeline_leak"} for f in critical),
        "scanner_policy_version": "graded_v1",
    }
