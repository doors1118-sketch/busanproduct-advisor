"""
v1.4.4 라우팅·프롬프트 조립 스키마 정의
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KeywordRouteResult:
    """Keyword Pre-Router 결과"""
    matched_categories: list[str] = field(default_factory=list)
    forced_guardrails: list[str] = field(default_factory=list)
    ambiguous_keywords: list[str] = field(default_factory=list)
    is_unambiguous: bool = False  # fast path 판단용


@dataclass
class IntentCandidate:
    label: str
    confidence: float


@dataclass
class IntentRouteResult:
    """LLM Intent Router 결과"""
    candidates: list[IntentCandidate] = field(default_factory=list)
    agency_type: str = "local_government"
    needs_clarification: Optional[str] = None
    mcp_required: bool = True
    router_status: str = "success"  # success | failed | skipped


@dataclass
class SanityCheckResult:
    """Guardrail Sanity Check 결과"""
    final_guardrails: list[str] = field(default_factory=list)
    sanity_added: list[str] = field(default_factory=list)


@dataclass
class LegalConclusionScope:
    """MCP 결과 기반 법적 결론 범위 제어"""
    legal_conclusion_allowed: bool = True
    allowed_scope: list[str] = field(default_factory=list)
    blocked_scope: list[str] = field(default_factory=list)
    critical_missing: list[str] = field(default_factory=list)


@dataclass
class ApiStatus:
    """외부 API 상태 집계"""
    mcp_status: str = "not_called"  # success | partial | timeout | failed | not_called
    rag_status: str = "success"
    company_search_status: str = "not_called"
    timeout_sources: list[str] = field(default_factory=list)
    legal_scope: LegalConclusionScope = field(default_factory=LegalConclusionScope)

    def to_display(self) -> str:
        """사용자 노출용 상태 문자열"""
        parts = []
        if self.mcp_status == "partial":
            parts.append("일부 법령 조회 지연으로 확인되지 않은 항목이 있습니다.")
        elif self.mcp_status == "timeout":
            parts.append("[확인 필요] 법령 조회 지연으로 법적 결론을 확정할 수 없습니다.")
        elif self.mcp_status == "failed":
            parts.append("법령 조회에 실패하여 현재 확인이 불가합니다.")
        if self.company_search_status in ("timeout", "failed"):
            parts.append("업체 검색 결과를 가져오지 못했습니다.")
        return "\n".join(parts)


@dataclass
class CompanyResult:
    """구조화된 업체 결과 — contract_possible=False 강제"""
    company_name: str = ""
    location: str = ""
    main_products: list[str] = field(default_factory=list)
    policy_tags: list[str] = field(default_factory=list)
    tag_source: str = "internal_policy_company_db"
    business_status: str = "unknown"
    contract_possible: bool = False  # 항상 False — 자동 승격 금지
    legal_eligibility_status: str = "unverified"
    candidate_status: str = "candidate"  # candidate | 추가 확인 필요 | 법적 적격성 확인 필요


def validate_company_result(result: CompanyResult) -> None:
    """1차 구조화 검증: contract_possible 자동 승격 방지"""
    assert result.contract_possible is False, \
        f"contract_possible must be False, got {result.contract_possible}"
    assert result.legal_eligibility_status in ("unverified", "requires_check"), \
        f"Invalid legal_eligibility_status: {result.legal_eligibility_status}"


@dataclass
class AssembledPrompt:
    """조립된 프롬프트 — Core(불변) + Dynamic(가변) 분리"""
    core_prompt: str = ""        # system_instruction에 주입 (캐시 고정)
    dynamic_context: str = ""    # user content 첫 메시지로 주입 (가변)
    core_prompt_hash: str = ""
    prompt_prefix_hash: str = "" # Core + Guardrail 영역 해시 (캐시 효율 추적)
    selected_guardrails: list[str] = field(default_factory=list)
