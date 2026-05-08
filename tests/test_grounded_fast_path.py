import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from gemini_engine import (
    _parse_amount,
    _should_skip_gemini_intent_router,
    _should_use_grounded_single_pass_llm,
)
from router.query_gateway import decide_query_gateway


def test_grounded_fast_path_understands_can_buy_expression():
    question = "2억 물품을 수의계약으로 살 수 있어?"

    assert _parse_amount(question) == 200_000_000
    assert _should_use_grounded_single_pass_llm(question, 2, _parse_amount(question)) is True


def test_clear_amount_contract_question_skips_gemini_intent_router():
    question = "2억 물품을 수의계약으로 살 수 있어?"

    assert _should_skip_gemini_intent_router(question, decide_query_gateway(question)) is True


def test_local_company_amount_question_keeps_gemini_intent_router():
    question = "8천만원 LED 조명을 부산업체로 구매할 방법이 있어?"

    assert _should_skip_gemini_intent_router(question, decide_query_gateway(question)) is False
