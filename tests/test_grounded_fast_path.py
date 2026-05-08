import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from gemini_engine import _parse_amount, _should_use_grounded_single_pass_llm


def test_grounded_fast_path_understands_can_buy_expression():
    question = "2억 물품을 수의계약으로 살 수 있어?"

    assert _parse_amount(question) == 200_000_000
    assert _should_use_grounded_single_pass_llm(question, 2, _parse_amount(question)) is True

