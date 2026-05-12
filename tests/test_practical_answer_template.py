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
            amount_value=60_000_000,
        )
    )

    assert "### 6천만원(60,000,000원) 규모 컴퓨터 구매 실무 가이드" in rendered
    assert "### 핵심 요약 (결론)" in rendered
    assert "일반 업체 대상 1인 견적 수의계약 기준" in rendered
    assert "### 1. 법적 근거에 따른 구매 경로 비교" in rendered
    assert "| 추천 1 | 종합쇼핑몰/MAS 직접구매 |" in rendered
    assert "| 추천 2 | 정책기업 1인 견적 |" in rendered
    assert "| 대안 | 부산 지역제한 2인 이상 견적 |" in rendered
    assert "| 제한 | 일반 1인 견적 수의계약 |" in rendered
    assert "정책기업 1인 견적" in rendered
    assert "금액상 우선 제외" in rendered
    assert "### 2. 계약방법 및 구매 경로 세부 검토" in rendered
    assert "### 3. 부산 지역업체 구매 확대 전략" in rendered
    assert "### 4. 검토 대상 부산 지역업체 후보" in rendered
    assert "### 5. 실무자 필수 체크포인트" in rendered
    assert "### 6. 참고 근거" in rendered
    assert "#### 실무 매뉴얼 보조 체크포인트" in rendered
    assert "요건이 충족되면" not in rendered
    assert "원천 차단" not in rendered
    assert "금액에 상관없이" not in rendered
    assert "전체 후보 63건은 답변 하단의 엑셀 다운로드" in rendered
    assert "분할발주 주의" in rendered


def test_multi_route_template_uses_dynamic_priority_for_amountless_goods_questions():
    rendered = "\n".join(
        build_multi_route_practical_answer_parts(
            amount_label="금액 미확인",
            item_label="냉난방기",
            contract_object="goods",
            route_guidance="| 순위 | 경로 | 판단 | 법적 근거 | 실무 의미 |\n|---|---|---|---|---|",
            candidate_table_text="**[표 1] 부산 지역업체 후보**",
        )
    )

    assert "우선순위는 고정하지 않습니다" in rendered
    assert "| 상황 | 먼저 볼 경로 | 부산업체 수주 지원 방법 | 확인 근거 |" in rendered
    assert "금액·사유 충족 시에만 적용" in rendered
    assert "현장설치도" in rendered
    assert "전기 용량" in rendered
    assert "고효율 에너지기자재" in rendered
    assert "무조건" not in rendered
