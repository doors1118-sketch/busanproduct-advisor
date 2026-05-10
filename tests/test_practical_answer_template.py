import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from policies.practical_answer_template import build_multi_route_practical_answer_parts


def test_multi_route_practical_answer_template_keeps_quality_structure():
    rendered = "\n".join(
        build_multi_route_practical_answer_parts(
            amount_label="6천만원(60,000,000원)",
            item_label="컴퓨터",
            contract_object="goods",
            route_guidance="| 순위 | 경로 | 판단 | 법적 근거 | 실무 의미 |\n|---|---|---|---|---|",
            practice_manual_text="### 실무 매뉴얼 보조 체크포인트\n- 확인",
            candidate_table_text="**[표 1] 나라장터 종합쇼핑몰 등록 부산업체 후보**",
            candidate_export_row_count=63,
            policy_company_sections_skipped=True,
        )
    )

    assert "### 6천만원(60,000,000원) 규모 컴퓨터 구매 실무 가이드" in rendered
    assert "### 1. 계약방법 및 구매 경로 검토" in rendered
    assert "### 2. 부산 지역업체 구매 확대 전략" in rendered
    assert "### 3. 검토 대상 부산 지역업체 후보" in rendered
    assert "### 4. 실무자 필수 체크포인트" in rendered
    assert "### 5. 참고 근거" in rendered
    assert "#### 실무 매뉴얼 보조 체크포인트" in rendered
    assert "요건이 충족되면" not in rendered
    assert "원천 차단" not in rendered
    assert "금액에 상관없이" not in rendered
    assert "전체 후보 63건은 답변 하단의 엑셀 다운로드" in rendered
    assert "분할발주 주의" in rendered
