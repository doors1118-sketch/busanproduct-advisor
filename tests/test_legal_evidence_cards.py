import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from internal_law_lookup import search_internal_law
from policies.legal_evidence_cards import build_evidence_card, render_evidence_card_context, summarize_evidence_counts
from policies.model_routing_policy import generate_mandatory_mcp_plan


def test_short_alias_hits_actual_sme_purchase_law_name():
    result = search_internal_law("중소기업구매촉진법 제6조")

    assert result is not None
    assert "[내부DB]" in result
    assert "중소기업제품 구매촉진" in result


def test_deleted_article_is_still_internal_db_hit():
    result = search_internal_law("지방계약법 시행규칙 제28조")

    assert result is not None
    assert "제28조 삭제" in result


def test_preflight_plan_uses_db_backed_law_names():
    plan = generate_mandatory_mcp_plan("2억 물품 살 건데 수의계약 가능해?", 2, agency_type="default")
    queries = [item["args"]["query"] for item in plan if item["name"] == "search_law"]

    assert "중소기업제품 구매촉진 및 판로지원법 제6조" in queries
    assert "중소기업제품 구매촉진 및 판로지원법 제12조" in queries


def test_evidence_card_marks_internal_db_source_and_effective_date():
    result = search_internal_law("지방계약법 시행령 제30조")
    card = build_evidence_card(
        tool_name="search_law",
        args={"query": "지방계약법 시행령 제30조"},
        result=result,
        from_cache=False,
        elapsed_ms=1,
    )

    assert card["status"] == "hit"
    assert card["source"] == "internal_db"
    assert card["law_name"] == "지방계약법 시행령"
    assert card["article_no"] == "제30조"
    assert card["effective_date"] == "20260102"
    assert "direct_contract" in card["supports"]
    assert "amount_threshold" in card["supports"]
    assert card["required_checks"]
    assert card["practical_meaning"]
    assert card["legal_risks"]


def test_evidence_count_summary_distinguishes_sources():
    cards = [
        {"status": "hit", "source": "internal_db"},
        {"status": "hit", "source": "external_mcp"},
        {"status": "miss", "source": "missing"},
    ]

    summary = summarize_evidence_counts(cards)

    assert summary == {
        "evidence_card_count": 3,
        "internal_db_hit_count": 1,
        "external_mcp_fallback_count": 1,
        "evidence_missing_count": 1,
    }


def test_evidence_card_context_keeps_targeted_excerpt_without_full_raw_text():
    long_prefix = "일반 설명 " * 260
    result = (
        f"[내부DB] 지방계약법 시행령 제30조\n{long_prefix}"
        "제30조는 수의계약 대상자 선정과 견적 제출 절차를 정하고, "
        "추정가격과 1인 견적 가능 여부를 구분하여 검토해야 한다. "
        "다만 예외 사유는 별도 조문과 행정규칙 확인이 필요하다."
    )
    card = build_evidence_card(
        tool_name="search_law",
        args={"query": "지방계약법 시행령 제30조 수의계약 1인 견적"},
        result=result,
        from_cache=False,
        elapsed_ms=1,
    )

    context = render_evidence_card_context([card], max_cards=1, excerpt_limit=500)

    assert "구조화 근거카드 컨텍스트" in context
    assert "excerpt:" in context
    assert "제30조" in context
    assert "수의계약" in context
    assert "required_checks=" in context
    assert "practical_meaning:" in context
    assert len(context) < len(result)
