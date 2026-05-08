import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from internal_law_lookup import search_internal_law
from policies.legal_evidence_cards import build_evidence_card, summarize_evidence_counts
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
