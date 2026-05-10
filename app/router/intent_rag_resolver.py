"""Intent RAG resolver for procurement question routing.

This module retrieves similar standard questions and manual cards before the
expensive LLM/tool-loop stage. It does not generate final answers. Its job is
to produce a structured intent/context card that can safely bias routing,
guardrails, and prefetch decisions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Any

try:
    from app.prompting.schemas import KeywordRouteResult
except Exception:  # Runtime path when app/ is on sys.path.
    try:
        from prompting.schemas import KeywordRouteResult
    except Exception:  # pragma: no cover - merge helper becomes unavailable.
        KeywordRouteResult = None  # type: ignore

try:
    from app.router.intent_normalization import normalize_query_intent
except Exception:  # Runtime path when app/ is on sys.path.
    from router.intent_normalization import normalize_query_intent


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PRACTICE_CARD_PATH = DATA_DIR / "practice_manual_cards.json"
INTENT_RAG_CORPUS_PATH = DATA_DIR / "intent_rag_corpus.json"


@dataclass(frozen=True)
class IntentRagExample:
    example_id: str
    text: str
    intent_labels: tuple[str, ...]
    sub_intents: tuple[str, ...] = ()
    answer_mode: str = "router_assist"
    keywords: tuple[str, ...] = ()
    source: str = "curated"
    weight: float = 1.0
    source_type: str = ""


@dataclass(frozen=True)
class IntentRagMatch:
    example_id: str
    text: str
    score: float
    intent_labels: tuple[str, ...]
    sub_intents: tuple[str, ...]
    answer_mode: str
    source: str
    source_type: str = ""

    def to_meta(self) -> dict[str, Any]:
        return {
            "example_id": self.example_id,
            "text": self.text,
            "score": round(self.score, 3),
            "intent_labels": list(self.intent_labels),
            "sub_intents": list(self.sub_intents),
            "answer_mode": self.answer_mode,
            "source": self.source,
            "source_type": self.source_type,
        }


@dataclass(frozen=True)
class _IndexedIntentRagExample:
    example: IntentRagExample
    compact_text: str
    tokens: frozenset[str]
    compact_keywords: tuple[str, ...]


@dataclass(frozen=True)
class IntentRagDecision:
    enabled: bool = True
    status: str = "success"
    primary_intent: str = ""
    intent_labels: tuple[str, ...] = ()
    sub_intents: tuple[str, ...] = ()
    answer_mode: str = "router_assist"
    confidence: float = 0.0
    confidence_level: str = "low"
    company_search_required: bool = False
    company_search_blocked: bool = False
    local_purchase_support_required: bool = False
    contract_review_required: bool = False
    procedure_required: bool = False
    legal_basis_required: bool = False
    llm_router_required: bool = True
    corpus_record_count: int = 0
    item_name: str = ""
    contract_object: str = ""
    amount: int | None = None
    reasons: tuple[str, ...] = ()
    matched_examples: tuple[IntentRagMatch, ...] = field(default_factory=tuple)

    def to_meta(self) -> dict[str, Any]:
        meta = asdict(self)
        meta["intent_labels"] = list(self.intent_labels)
        meta["sub_intents"] = list(self.sub_intents)
        meta["reasons"] = list(self.reasons)
        meta["matched_examples"] = [m.to_meta() for m in self.matched_examples]
        return meta


_CURATED_EXAMPLES: tuple[IntentRagExample, ...] = (
    IntentRagExample(
        example_id="std:policy_company_sme_purchase_performance",
        text="여성기업제품 장애인기업제품을 구매해도 중소기업제품 구매실적에 포함되는지",
        intent_labels=("legal_explanation", "procurement_general"),
        sub_intents=("policy_company_purchase_performance", "sme_purchase_performance"),
        answer_mode="deterministic_candidate",
        keywords=("여성기업제품", "장애인기업제품", "중소기업제품", "구매실적", "포함", "인정"),
    ),
    IntentRagExample(
        example_id="std:sme_competition_small_business_priority",
        text="중소기업자간 경쟁제품 추정가격 1억원 미만 소기업 소상공인 입찰참가자격 제한",
        intent_labels=("item_purchase", "item_eligibility", "legal_explanation"),
        sub_intents=("sme_competition_product", "small_business_priority_procurement"),
        answer_mode="deterministic_candidate",
        keywords=("중소기업자간", "중기간", "경쟁제품", "1억원", "소기업", "소상공인", "입찰참가자격"),
    ),
    IntentRagExample(
        example_id="std:service_local_supplier_methods",
        text="용역계약에서 지역업체 참여 가능한 방법 지역제한 지역업체 참여도 공동도급",
        intent_labels=("service_contract", "local_purchase_support"),
        sub_intents=("regional_restriction", "local_company_points", "regional_joint_contract"),
        answer_mode="practice_manual_card",
        keywords=("용역계약", "지역업체", "참여", "방법", "지역제한", "가점", "공동도급"),
    ),
    IntentRagExample(
        example_id="std:local_service_amount_contract_review",
        text="8천만원 청소용역 부산 지역업체 계약 제도 검토",
        intent_labels=("service_contract", "contract_review", "local_purchase_support"),
        sub_intents=("amount_based_contract_route", "regional_support_methods"),
        answer_mode="grounded_card",
        keywords=("청소용역", "부산", "지역업체", "계약", "제도", "검토", "예산", "만원"),
    ),
    IntentRagExample(
        example_id="std:goods_computer_budget_route",
        text="예산 6천만원 컴퓨터 구매 계약 방법 종합쇼핑몰 중기간 혁신제품 부산업체 후보",
        intent_labels=("item_purchase", "contract_review", "mas_shopping_mall", "local_purchase_support"),
        sub_intents=("amount_based_contract_route", "shopping_mall_check", "sme_competition_check", "innovation_product_check"),
        answer_mode="multi_route_prefetch",
        keywords=("예산", "컴퓨터", "구매", "계약방법", "종합쇼핑몰", "중기간", "혁신제품"),
    ),
    IntentRagExample(
        example_id="std:explicit_company_candidate_lookup",
        text="CCTV 부산업체 후보 추천 조달등록 업체 목록",
        intent_labels=("item_purchase", "company_search"),
        sub_intents=("local_supplier_candidate_lookup",),
        answer_mode="company_search",
        keywords=("cctv", "부산업체", "후보", "추천", "업체목록", "검색"),
    ),
    IntentRagExample(
        example_id="std:goods_purchase_procedure",
        text="물품을 구매하려고 한다 구매 절차 계약 절차 전체 흐름 안내",
        intent_labels=("item_purchase", "procedure"),
        sub_intents=("procurement_lifecycle", "practice_manual_procedure"),
        answer_mode="practice_manual_card",
        keywords=("물품", "구매", "절차", "계약절차", "흐름", "안내"),
    ),
    IntentRagExample(
        example_id="std:construction_local_support",
        text="공사 발주에서 지역업체 참여 방법 지역제한 지역의무공동도급 적격심사 가점",
        intent_labels=("construction_contract", "local_purchase_support"),
        sub_intents=("regional_restriction", "regional_mandatory_joint_contract", "local_company_points"),
        answer_mode="grounded_card",
        keywords=("공사", "지역업체", "지역제한", "지역의무공동도급", "적격심사", "가점"),
    ),
    IntentRagExample(
        example_id="std:mas_shopping_mall_route",
        text="종합쇼핑몰 MAS 물품 구매 2단계 경쟁 납품요구 부산업체",
        intent_labels=("item_purchase", "mas_shopping_mall", "procurement_route_review"),
        sub_intents=("shopping_mall_check", "mas_second_stage_competition"),
        answer_mode="grounded_card",
        keywords=("종합쇼핑몰", "mas", "2단계경쟁", "납품요구", "물품"),
    ),
    IntentRagExample(
        example_id="std:innovation_product_direct_contract",
        text="혁신제품 혁신시제품 기술개발제품 수의계약 우선구매 가능 여부",
        intent_labels=("item_purchase", "contract_review", "procurement_route_review"),
        sub_intents=("innovation_product_check", "priority_purchase_product", "direct_contract_exception"),
        answer_mode="grounded_card",
        keywords=("혁신제품", "혁신시제품", "기술개발제품", "수의계약", "우선구매"),
    ),
)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def _tokens(text: str) -> set[str]:
    text = (text or "").lower()
    tokens = set(re.findall(r"[0-9a-zA-Z가-힣]{2,}", text))
    compact = _compact(text)
    for size in (2, 3, 4):
        if len(compact) >= size:
            tokens.update(compact[i:i + size] for i in range(0, max(0, len(compact) - size + 1)))
    return tokens


def _has_any(compact_text: str, terms: tuple[str, ...]) -> bool:
    return any(_compact(term) in compact_text for term in terms)


def _extract_amount_won(text: str) -> int | None:
    return normalize_query_intent(text).amount


def _infer_contract_object(text: str) -> str:
    return normalize_query_intent(text).contract_object


def _extract_item_name(text: str) -> str:
    return normalize_query_intent(text).item_name


def _is_explicit_company_lookup(text: str) -> bool:
    norm = normalize_query_intent(text)
    return norm.company_lookup_requested and not norm.company_lookup_blocked


def _has_local_support_context(text: str) -> bool:
    return normalize_query_intent(text).local_support_requested


def _is_procedure_query(text: str) -> bool:
    return normalize_query_intent(text).procedure_requested


def _has_contract_review_context(text: str) -> bool:
    return normalize_query_intent(text).contract_review_requested


def _is_policy_company_performance_question(text: str) -> bool:
    compact = _compact(text)
    return (
        _has_any(compact, ("여성기업", "여성기업제품", "장애인기업", "장애인기업제품"))
        and ("중소기업제품" in compact or ("중소기업" in compact and "구매실적" in compact))
        and _has_any(compact, ("구매실적", "실적", "포함", "인정", "되는지", "되나요"))
    )


def _is_practice_interpretation_query(text: str) -> bool:
    return normalize_query_intent(text).interpretation_requested


def _manual_topic_to_labels(card: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    topic = str(card.get("topic") or "")
    title = str(card.get("title") or "")
    labels: list[str] = []
    sub: list[str] = []
    answer_mode = "practice_manual_card"

    if topic.startswith("lifecycle_") or card.get("flow_stage"):
        labels.append("procedure")
        sub.append("procurement_lifecycle")
    if topic in {"regional_restriction", "local_company_points", "regional_joint_contract", "policy_company_purchase"}:
        labels.append("local_purchase_support")
        sub.append(topic)
    if topic == "direct_contract":
        labels.append("contract_review")
        sub.append("direct_contract")
    if topic == "mas_shopping_mall":
        labels.extend(["mas_shopping_mall", "procurement_route_review"])
        sub.append("shopping_mall_check")
    if topic == "sme_competition":
        labels.extend(["item_purchase", "item_eligibility"])
        sub.append("sme_competition_product")
    if topic == "excellent_procurement":
        labels.extend(["item_purchase", "procurement_route_review"])
        sub.append("priority_purchase_product")
    if "용역" in title:
        labels.append("service_contract")
    elif "공사" in title:
        labels.append("construction_contract")
    elif any(term in title for term in ("물품", "구매", "제품")):
        labels.append("item_purchase")

    return tuple(dict.fromkeys(labels)), tuple(dict.fromkeys(sub)), answer_mode


@lru_cache(maxsize=1)
def _load_manual_examples() -> tuple[IntentRagExample, ...]:
    if not PRACTICE_CARD_PATH.exists():
        return ()
    try:
        data = json.loads(PRACTICE_CARD_PATH.read_text(encoding="utf-8"))
    except Exception:
        return ()

    examples: list[IntentRagExample] = []
    for card in data.get("cards") or []:
        labels, sub, answer_mode = _manual_topic_to_labels(card)
        if not labels:
            continue
        keywords = tuple(str(k) for k in (card.get("keywords") or [])[:12])
        text = " ".join([
            str(card.get("title") or ""),
            " ".join(keywords),
            str(card.get("summary") or ""),
        ]).strip()
        if not text:
            continue
        examples.append(IntentRagExample(
            example_id=f"manual:{card.get('card_id') or card.get('topic') or len(examples)}",
            text=text,
            intent_labels=labels,
            sub_intents=sub,
            answer_mode=answer_mode,
            keywords=keywords,
            source="practice_manual_cards",
            weight=0.82,
        ))
    return tuple(examples)


@lru_cache(maxsize=1)
def _load_intent_rag_corpus_examples() -> tuple[IntentRagExample, ...]:
    """Load the generated non-law Intent RAG corpus."""
    if not INTENT_RAG_CORPUS_PATH.exists():
        return ()
    try:
        data = json.loads(INTENT_RAG_CORPUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return ()

    examples: list[IntentRagExample] = []
    for record in data.get("records") or []:
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        labels = tuple(str(label) for label in (record.get("intent_labels") or []) if str(label).strip())
        if not labels:
            continue
        keywords = tuple(str(k) for k in (record.get("keywords") or []) if str(k).strip())
        sub_intents = tuple(str(s) for s in (record.get("sub_intents") or []) if str(s).strip())
        try:
            weight = float(record.get("weight", 0.75) or 0.75)
        except Exception:
            weight = 0.75
        examples.append(IntentRagExample(
            example_id=str(record.get("id") or f"corpus:{len(examples)}"),
            text=text,
            intent_labels=labels,
            sub_intents=sub_intents,
            answer_mode=str(record.get("answer_mode") or "router_assist"),
            keywords=keywords,
            source=str(record.get("source_file") or "intent_rag_corpus.json"),
            weight=max(0.1, min(1.2, weight)),
            source_type=str(record.get("source_type") or "intent_rag_corpus"),
        ))
    return tuple(examples)


@lru_cache(maxsize=1)
def _corpus() -> tuple[IntentRagExample, ...]:
    generated = _load_intent_rag_corpus_examples()
    if generated:
        return _CURATED_EXAMPLES + generated
    return _CURATED_EXAMPLES + _load_manual_examples()


def get_intent_rag_corpus_status() -> dict[str, Any]:
    examples = _load_intent_rag_corpus_examples()
    return {
        "path": str(INTENT_RAG_CORPUS_PATH),
        "available": bool(examples),
        "record_count": len(examples),
        "fallback_manual_examples": len(_load_manual_examples()) if not examples else 0,
    }


def clear_intent_rag_corpus_cache() -> None:
    _load_intent_rag_corpus_examples.cache_clear()
    _load_manual_examples.cache_clear()
    _corpus.cache_clear()
    _indexed_corpus.cache_clear()


@lru_cache(maxsize=1)
def _indexed_corpus() -> tuple[_IndexedIntentRagExample, ...]:
    return tuple(
        _IndexedIntentRagExample(
            example=example,
            compact_text=_compact(example.text),
            tokens=frozenset(_tokens(example.text)),
            compact_keywords=tuple(_compact(keyword) for keyword in example.keywords if _compact(keyword)),
        )
        for example in _corpus()
    )


def _score_example(query: str, example: IntentRagExample) -> float:
    q_compact = _compact(query)
    e_compact = _compact(example.text)
    q_tokens = _tokens(query)
    e_tokens = _tokens(example.text)
    overlap = len(q_tokens & e_tokens) / max(1, min(len(q_tokens), len(e_tokens)))
    phrase_hits = sum(1 for kw in example.keywords if _compact(kw) and _compact(kw) in q_compact)
    phrase_score = min(1.0, phrase_hits / max(2, min(6, len(example.keywords) or 2)))
    char_similarity = SequenceMatcher(None, q_compact, e_compact).ratio()

    score = (0.42 * overlap) + (0.38 * phrase_score) + (0.20 * char_similarity)
    if _extract_amount_won(query) is not None and _has_any(_compact(example.text), ("예산", "만원", "억원", "금액", "추정가격")):
        score += 0.06
    if _is_explicit_company_lookup(query) and "company_search" in example.intent_labels:
        score += 0.12
    if _has_local_support_context(query) and "local_purchase_support" in example.intent_labels:
        score += 0.08
    if _is_procedure_query(query) and "procedure" in example.intent_labels:
        score += 0.1
    if example.source_type == "pps_qa_case" and any(term in q_compact for term in ("해석사례", "질의", "회신", "설계변경", "간접비", "자동연장", "계약기간")):
        score += 0.08
    if example.source_type == "regional_support_catalog" and _has_local_support_context(query):
        score += 0.06
    return max(0.0, min(1.0, score * example.weight))


def _score_indexed_example(
    *,
    q_compact: str,
    q_tokens: set[str],
    indexed: _IndexedIntentRagExample,
    amount_present: bool,
    explicit_company_lookup: bool,
    local_support: bool,
    procedure: bool,
    interpretation_query: bool,
) -> float:
    example = indexed.example
    e_tokens = indexed.tokens
    overlap = len(q_tokens & e_tokens) / max(1, min(len(q_tokens), len(e_tokens)))
    phrase_hits = sum(1 for kw in indexed.compact_keywords if kw and kw in q_compact)
    phrase_score = min(1.0, phrase_hits / max(2, min(6, len(indexed.compact_keywords) or 2)))

    char_similarity = 0.0
    cheap_score = (0.42 * overlap) + (0.38 * phrase_score)
    if (
        cheap_score >= 0.035
        or (interpretation_query and example.source_type == "pps_qa_case")
        or (explicit_company_lookup and "company_search" in example.intent_labels)
        or (local_support and "local_purchase_support" in example.intent_labels)
        or (procedure and "procedure" in example.intent_labels)
    ):
        char_similarity = SequenceMatcher(None, q_compact, indexed.compact_text).ratio()

    score = cheap_score + (0.20 * char_similarity)
    if amount_present and _has_any(indexed.compact_text, ("예산", "만원", "억원", "금액", "추정가격")):
        score += 0.06
    if explicit_company_lookup and "company_search" in example.intent_labels:
        score += 0.12
    if local_support and "local_purchase_support" in example.intent_labels:
        score += 0.08
    if procedure and "procedure" in example.intent_labels:
        score += 0.1
    if example.source_type == "pps_qa_case" and interpretation_query:
        score += 0.08
    if example.source_type == "regional_support_catalog" and local_support:
        score += 0.06
    return max(0.0, min(1.0, score * example.weight))


def _top_matches(query: str, limit: int = 4) -> tuple[IntentRagMatch, ...]:
    q_compact = _compact(query)
    q_tokens = _tokens(query)
    amount_present = _extract_amount_won(query) is not None
    explicit_company_lookup = _is_explicit_company_lookup(query)
    local_support = _has_local_support_context(query)
    procedure = _is_procedure_query(query)
    interpretation_query = _is_practice_interpretation_query(query)

    scored: list[IntentRagMatch] = []
    for indexed in _indexed_corpus():
        example = indexed.example
        score = _score_indexed_example(
            q_compact=q_compact,
            q_tokens=q_tokens,
            indexed=indexed,
            amount_present=amount_present,
            explicit_company_lookup=explicit_company_lookup,
            local_support=local_support,
            procedure=procedure,
            interpretation_query=interpretation_query,
        )
        min_score = 0.16 if example.source_type == "pps_qa_case" and interpretation_query else 0.22
        if score < min_score:
            continue
        scored.append(IntentRagMatch(
            example_id=example.example_id,
            text=example.text[:180],
            score=score,
            intent_labels=example.intent_labels,
            sub_intents=example.sub_intents,
            answer_mode=example.answer_mode,
            source=example.source,
            source_type=example.source_type,
        ))
    scored.sort(key=lambda item: item.score, reverse=True)
    return tuple(scored[:limit])


@lru_cache(maxsize=256)
def _has_pps_qa_case_match(query: str) -> bool:
    try:
        try:
            from app.policies.pps_qa_cards import match_pps_qa_cards
        except Exception:
            from policies.pps_qa_cards import match_pps_qa_cards
        return bool(match_pps_qa_cards(query, max_cards=1))
    except Exception:
        return False


def _confidence_level(score: float) -> str:
    if score >= 0.78:
        return "high"
    if score >= 0.58:
        return "medium"
    return "low"


def _append_unique(items: list[str], *values: str) -> None:
    for value in values:
        if value and value not in items:
            items.append(value)


def resolve_intent_context(query: str) -> IntentRagDecision:
    """Retrieve similar intent examples and return a structured routing card."""
    norm = normalize_query_intent(query)
    matches = _top_matches(norm.search_text or query)
    best = matches[0] if matches else None
    labels: list[str] = list(best.intent_labels) if best and best.score >= 0.42 else []
    sub_intents: list[str] = list(best.sub_intents) if best and best.score >= 0.42 else []
    reasons: list[str] = list(norm.reasons)

    amount = norm.amount
    item_name = norm.item_name
    contract_object = norm.contract_object
    explicit_company_lookup = norm.company_lookup_requested and not norm.company_lookup_blocked
    local_support = norm.local_support_requested
    procedure = norm.procedure_requested
    contract_review = norm.contract_review_requested
    policy_performance = _is_policy_company_performance_question(query)
    interpretation_query = norm.interpretation_requested
    pps_case_available = bool(
        interpretation_query
        and (
            any(match.source_type == "pps_qa_case" for match in matches)
            or _has_pps_qa_case_match(query)
        )
    )
    compact = _compact(query)
    issue_tags = set(norm.issue_tags)

    if contract_object == "goods":
        if "mixed_contract_object" not in issue_tags:
            labels = [label for label in labels if label not in ("service_contract", "construction_contract")]
        _append_unique(labels, "item_purchase")
    elif contract_object == "service":
        if "mixed_contract_object" not in issue_tags:
            labels = [label for label in labels if label not in ("item_purchase", "construction_contract")]
        _append_unique(labels, "service_contract")
    elif contract_object == "construction":
        if "mixed_contract_object" not in issue_tags:
            labels = [label for label in labels if label not in ("item_purchase", "service_contract")]
        _append_unique(labels, "construction_contract")

    if procedure:
        _append_unique(labels, "procedure")
        _append_unique(sub_intents, "procurement_lifecycle")
        reasons.append("procedure_terms_detected")
    if local_support:
        _append_unique(labels, "local_purchase_support")
        reasons.append("local_support_terms_detected")
    if contract_review:
        _append_unique(labels, "contract_review")
        _append_unique(sub_intents, "amount_based_contract_route")
        reasons.append("amount_or_budget_contract_review_detected")
    if _has_any(compact, ("종합쇼핑몰", "mas", "다수공급자", "제3자단가")):
        _append_unique(labels, "mas_shopping_mall", "procurement_route_review")
        _append_unique(sub_intents, "shopping_mall_check")
    if _has_any(compact, ("중소기업자간", "중기간", "직접생산", "경쟁제품")):
        _append_unique(labels, "item_eligibility")
        _append_unique(sub_intents, "sme_competition_product")
    if "sme_competition_product" in issue_tags:
        _append_unique(labels, "item_purchase", "item_eligibility", "legal_explanation")
        _append_unique(sub_intents, "sme_competition_product")
    if "small_business_priority_procurement" in issue_tags:
        _append_unique(sub_intents, "small_business_priority_procurement")
    if _has_any(compact, ("혁신제품", "혁신시제품", "기술개발제품", "우수조달")):
        _append_unique(labels, "procurement_route_review")
        _append_unique(sub_intents, "innovation_product_check")
    if policy_performance:
        _append_unique(labels, "legal_explanation", "procurement_general")
        _append_unique(sub_intents, "policy_company_purchase_performance")
        reasons.append("policy_company_purchase_performance_detected")
    if interpretation_query:
        _append_unique(labels, "legal_explanation")
        _append_unique(sub_intents, "practice_interpretation_case")
        reasons.append("practice_interpretation_context_detected")
    if "split_procurement_review" in issue_tags:
        _append_unique(labels, "procurement_route_review", "legal_explanation")
        _append_unique(sub_intents, "split_procurement_review")
        reasons.append("split_procurement_phrase_detected")
    if "mixed_contract_object" in issue_tags:
        _append_unique(labels, "item_purchase", "construction_contract")
        _append_unique(sub_intents, "mixed_contract_object")
        reasons.append("mixed_contract_object_detected")
    if "construction_period_extension" in issue_tags:
        _append_unique(labels, "construction_contract", "legal_explanation")
        _append_unique(sub_intents, "construction_period_extension")
        reasons.append("construction_period_extension_detected")
    if "indirect_cost_review" in issue_tags:
        _append_unique(sub_intents, "indirect_cost_review")
        reasons.append("indirect_cost_phrase_detected")
    if explicit_company_lookup:
        _append_unique(labels, "company_search")
        reasons.append("explicit_company_lookup_detected")

    has_specific_item = bool(item_name)
    company_search_required = explicit_company_lookup
    company_search_blocked = False
    if local_support and not explicit_company_lookup:
        company_search_blocked = True
        labels = [label for label in labels if label != "company_search"]
        reasons.append("local_support_strategy_without_candidate_lookup")
    if norm.company_lookup_blocked and not explicit_company_lookup:
        company_search_blocked = True
        labels = [label for label in labels if label != "company_search"]
        reasons.append("explicit_company_lookup_negative_detected")

    if (
        contract_review
        and amount is not None
        and has_specific_item
        and not policy_performance
        and not procedure
        and not norm.company_lookup_blocked
    ):
        # 금액+품목 사안은 구매경로 카드와 후보조회가 함께 품질을 올린다.
        company_search_required = True
        company_search_blocked = False
        reasons.append("amount_item_route_review_prefetch_candidate")

    if policy_performance or procedure:
        company_search_required = False
        company_search_blocked = True

    if not labels:
        _append_unique(labels, "common_procurement")

    if company_search_required:
        _append_unique(labels, "company_search")
    elif company_search_blocked:
        labels = [label for label in labels if label != "company_search"]

    base_score = best.score if best else 0.0
    rule_score = 0.0
    if policy_performance:
        rule_score = max(rule_score, 0.88)
    if interpretation_query and pps_case_available:
        rule_score = max(rule_score, 0.62)
    if explicit_company_lookup and has_specific_item:
        rule_score = max(rule_score, 0.86)
    if contract_review and amount is not None:
        rule_score = max(rule_score, 0.76 if has_specific_item else 0.66)
    if local_support and not explicit_company_lookup:
        rule_score = max(rule_score, 0.78)
    if procedure:
        rule_score = max(rule_score, 0.8)
    if "sme_competition_product" in issue_tags:
        rule_score = max(rule_score, 0.72)
    if "small_business_priority_procurement" in issue_tags:
        rule_score = max(rule_score, 0.78)
    if "split_procurement_review" in issue_tags:
        rule_score = max(rule_score, 0.72)
    if "construction_period_extension" in issue_tags and "indirect_cost_review" in issue_tags:
        rule_score = max(rule_score, 0.68)

    confidence = round(max(base_score, rule_score), 2)
    level = _confidence_level(confidence)
    answer_mode = best.answer_mode if best and best.score >= 0.5 else "router_assist"
    if policy_performance:
        answer_mode = "deterministic_candidate"
    elif interpretation_query and pps_case_available:
        answer_mode = "pps_qa_interpretation"
    elif company_search_required and amount is not None:
        answer_mode = "multi_route_prefetch"
    elif explicit_company_lookup:
        answer_mode = "company_search"
    elif procedure:
        answer_mode = "practice_manual_card"
    elif interpretation_query and any(tag in issue_tags for tag in ("construction_period_extension", "indirect_cost_review")):
        answer_mode = "pps_qa_interpretation" if pps_case_available else "grounded_card"
    elif "split_procurement_review" in issue_tags:
        answer_mode = "grounded_card"
    elif contract_review:
        answer_mode = "grounded_card"

    llm_router_required = confidence < 0.74
    primary = labels[0] if labels else "common_procurement"

    return IntentRagDecision(
        primary_intent=primary,
        intent_labels=tuple(dict.fromkeys(labels)),
        sub_intents=tuple(dict.fromkeys(sub_intents)),
        answer_mode=answer_mode,
        confidence=confidence,
        confidence_level=level,
        company_search_required=company_search_required,
        company_search_blocked=company_search_blocked,
        local_purchase_support_required=local_support or "local_purchase_support" in labels,
        contract_review_required=contract_review or "contract_review" in labels,
        procedure_required=procedure or "procedure" in labels,
        legal_basis_required=bool(contract_review or policy_performance or norm.legal_basis_requested),
        llm_router_required=llm_router_required,
        corpus_record_count=len(_corpus()),
        item_name=item_name,
        contract_object=contract_object,
        amount=amount,
        reasons=tuple(dict.fromkeys(reasons)),
        matched_examples=matches,
    )


def augment_keyword_route(keyword_result: Any, decision: IntentRagDecision | None) -> Any:
    """Merge a high-confidence intent-RAG decision into KeywordRouteResult."""
    if KeywordRouteResult is None or keyword_result is None or decision is None:
        return keyword_result
    if decision.confidence < 0.55:
        return keyword_result

    matched = list(getattr(keyword_result, "matched_categories", []) or [])
    forced = list(getattr(keyword_result, "forced_guardrails", []) or [])
    ambiguous = list(getattr(keyword_result, "ambiguous_keywords", []) or [])
    if "unclear" in matched and decision.intent_labels:
        matched = [label for label in matched if label != "unclear"]

    for label in decision.intent_labels:
        if label == "company_search" and not decision.company_search_required:
            continue
        if label not in matched:
            matched.append(label)

    if decision.company_search_blocked:
        matched = [label for label in matched if label != "company_search"]
        forced = [label for label in forced if label != "company_search"]

    if decision.company_search_required and "company_search" not in matched:
        matched.append("company_search")

    if decision.company_search_required and decision.answer_mode == "company_search" and "company_search" not in forced:
        forced.append("company_search")

    if not matched:
        matched = ["unclear"]

    is_unambiguous = bool(getattr(keyword_result, "is_unambiguous", False))
    if (
        decision.confidence >= 0.82
        and len(matched) == 1
        and matched[0] in {
            "item_purchase", "service_contract", "construction_contract",
            "mas_shopping_mall", "company_search",
        }
    ):
        is_unambiguous = True

    return KeywordRouteResult(
        matched_categories=matched,
        forced_guardrails=forced,
        ambiguous_keywords=ambiguous,
        is_unambiguous=is_unambiguous,
    )


def format_intent_context_for_llm(decision: IntentRagDecision | None) -> str:
    """Render a compact writer-facing intent card."""
    if decision is None or decision.confidence < 0.55:
        return ""
    lines = [
        "### [Intent RAG 질문 맥락 카드]",
        f"- 주 의도: {decision.primary_intent}",
        f"- 보조 의도: {', '.join(decision.intent_labels[1:]) or '없음'}",
        f"- 답변 모드: {decision.answer_mode}",
        f"- 신뢰도: {decision.confidence_level} ({decision.confidence:.2f})",
        f"- 업체 후보 조회 필요: {decision.company_search_required}",
        f"- 지역업체 구매지원 관점 필요: {decision.local_purchase_support_required}",
        f"- 계약방법/금액 검토 필요: {decision.contract_review_required}",
        f"- 절차/매뉴얼 설명 필요: {decision.procedure_required}",
        f"- 법적 근거 표출 필요: {decision.legal_basis_required}",
    ]
    if decision.item_name:
        lines.append(f"- 추출 품목: {decision.item_name}")
    if decision.contract_object:
        lines.append(f"- 계약대상: {decision.contract_object}")
    if decision.amount:
        lines.append(f"- 추출 금액: {decision.amount}")
    if decision.sub_intents:
        lines.append(f"- 세부 쟁점: {', '.join(decision.sub_intents[:6])}")
    if decision.company_search_blocked:
        lines.append("- 주의: 질문은 업체 목록 요청이 아니라 제도/방법 안내로 우선 처리한다.")
    lines.append("- 이 카드는 라우팅 보조자료이며, 최종 법적 결론은 내부 법령 DB/source map 근거로 제한한다.")
    return "\n".join(lines)
