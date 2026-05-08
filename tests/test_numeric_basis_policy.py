from app.policies.numeric_basis_policy import (
    find_unresolved_numeric_parameters,
    get_numeric_display,
    get_numeric_value,
)


def test_source_map_numeric_parameters_are_displayed_by_unit():
    assert get_numeric_value("P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD") == 15_000_000_000
    assert get_numeric_display("P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD") == "150억원"
    assert get_numeric_display("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_FULL_RATE") == "30%"
    assert get_numeric_display("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_FULL_SCORE") == "3점"


def test_manual_or_missing_numeric_parameters_are_not_displayed():
    unresolved = find_unresolved_numeric_parameters([
        "P_LOCAL_LIMITED_BID_GOODS_SERVICE_NOTICE_THRESHOLD",
        "P_DOES_NOT_EXIST",
    ])

    assert "P_LOCAL_LIMITED_BID_GOODS_SERVICE_NOTICE_THRESHOLD" in unresolved
    assert "P_DOES_NOT_EXIST" in unresolved
    assert get_numeric_display("P_LOCAL_LIMITED_BID_GOODS_SERVICE_NOTICE_THRESHOLD") is None
