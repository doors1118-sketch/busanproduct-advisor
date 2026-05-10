import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from gemini_engine import _build_llm_tool_response, _select_evidence_context, _summarize_tool_response_context


def test_shadow_mode_keeps_raw_context_but_reports_card_comparison():
    selected, meta = _select_evidence_context(
        raw_context="RAW LAW TEXT" * 100,
        card_context="CARD SUMMARY",
        mode="shadow",
        prefix="mcp_context",
        cards=[{"status": "hit"}],
    )

    assert selected.startswith("RAW LAW TEXT")
    assert meta["mcp_context_mode_requested"] == "shadow"
    assert meta["mcp_context_mode_applied"] == "raw"
    assert meta["mcp_context_comparison_enabled"] is True
    assert meta["mcp_context_card_hit_count"] == 1


def test_card_mode_sends_card_context_to_llm():
    selected, meta = _select_evidence_context(
        raw_context="RAW LAW TEXT" * 100,
        card_context="CARD SUMMARY",
        mode="card",
        prefix="mcp_context",
        cards=[{"status": "hit"}],
    )

    assert selected == "CARD SUMMARY"
    assert meta["mcp_context_mode_applied"] == "card"
    assert meta["mcp_context_llm_chars"] == len("CARD SUMMARY")


def test_llm_tool_response_can_be_card_compressed(monkeypatch):
    monkeypatch.setenv("EVIDENCE_TOOL_RESPONSE_MODE", "card")

    class FakeFunctionCall:
        name = "search_law"
        args = {"query": "지방계약법 시행령 제30조 수의계약"}

    raw_result = (
        "[내부DB] 지방계약법 시행령 제30조\n"
        + ("일반 설명 " * 360)
        + "제30조는 수의계약 대상자 선정과 견적 제출 절차를 정한다. "
        "금액 기준과 1인 견적 가능 여부는 별도로 구분해야 한다."
    )

    selected, card, meta = _build_llm_tool_response(FakeFunctionCall(), raw_result)

    assert card is not None
    assert selected.startswith("### [구조화 근거카드 컨텍스트]")
    assert "제30조" in selected
    assert "수의계약" in selected
    assert meta["tool_response_context_mode_applied"] == "card"
    assert meta["tool_response_context_compressed_for_llm"] is True
    assert len(selected) < len(raw_result)


def test_tool_response_summary_treats_uncompressed_results_as_same_size():
    summary = _summarize_tool_response_context([
        {"tool_name": "search_local_company_by_product", "result": "abc", "elapsed_ms": 1},
    ])

    assert summary["tool_response_context_raw_chars"] == 3
    assert summary["tool_response_context_llm_chars"] == 3
    assert summary["tool_response_context_char_savings_pct"] == 0.0
