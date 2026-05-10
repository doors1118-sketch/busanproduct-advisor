import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from policies.answer_builder_policy import strip_raw_tool_names
from policies.company_policy import format_company_for_llm
from policies.regional_support_catalog import format_catalog_matches_for_llm


def test_strip_raw_tool_names_removes_internal_rendering_leaks():
    raw = "\n".join(
        [
            "- 후보표 생략 대상: policy_company",
            "- 작성 원칙: 후보표는 구매경로 판단과 맞는 표만 사용한다.",
            "내부 source map의 소액수의 2인 이상 견적 검토 구간입니다.",
            "explicit_keyword local_government",
            "중소기업자간경쟁제품",
            '→ 상세조회: get_company_detail("4996240f6fcb30a80dd154a2f9640fcd")',
        ]
    )

    cleaned = strip_raw_tool_names(raw)

    assert "후보표 생략 대상" not in cleaned
    assert "작성 원칙" not in cleaned
    assert "source map" not in cleaned
    assert "explicit_keyword" not in cleaned
    assert "local_government" not in cleaned
    assert "get_company_detail" not in cleaned
    assert "중소기업자간경쟁제품" in cleaned


def test_company_policy_uses_user_facing_no_result_and_hides_detail_tool():
    no_result = format_company_for_llm({"candidates": []})
    assert "candidate 없음" not in no_result
    assert "현재 조건에 맞는 업체 후보를 찾지 못했습니다" in no_result

    with_result = format_company_for_llm(
        {
            "candidates": [
                {
                    "company_id": "4996240f6fcb30a80dd154a2f9640fcd",
                    "company_name": "테스트업체",
                    "location": "부산광역시",
                    "business_status": "active",
                    "main_products": ["CCTV"],
                }
            ]
        }
    )
    assert "get_company_detail" not in with_result
    assert "4996240f6fcb30a80dd154a2f9640fcd" not in with_result


def test_regional_support_catalog_formats_human_readable_reason_and_agency():
    rendered = format_catalog_matches_for_llm(
        "부산 지역업체로 6천만원 물품 구매할 때 지원제도 알려줘",
        contract_object="goods",
        agency_type="local_government",
    )

    assert rendered == ""
